"""Project the verified S2 evidence graph into the runtime Gear Release shape.

The closure report is deliberately an evidence document.  It is not read by
the mini program and it does not contain resolver-ready static attributes for
every variant.  This module is the small, deterministic boundary between that
report and the existing immutable Gear Release rows.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


_SLOT_ALIASES = {
    "mainhand": "main_hand",
    "offhand": "off_hand",
    "trinket_1": "trinket1",
    "trinket_2": "trinket2",
}

_STAT_TYPE_KEYS = {
    "STRENGTH": "strength",
    "AGILITY": "agility",
    "INTELLECT": "intellect",
    "STAMINA": "stamina",
    "CRIT_RATING": "crit_rating",
    "CRITICAL_STRIKE": "crit_rating",
    "HASTE_RATING": "haste_rating",
    "HASTE": "haste_rating",
    "MASTERY_RATING": "mastery_rating",
    "MASTERY": "mastery_rating",
    "VERSATILITY": "versatility_rating",
    "VERSATILITY_RATING": "versatility_rating",
    "ARMOR": "armor",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slot(value: Any) -> str:
    normalized = _text(value).lower().replace("-", "_").replace(" ", "_")
    return _SLOT_ALIASES.get(normalized, normalized)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.replace(",", "/").split("/")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = value
    else:
        return []
    return [_text(item) for item in values if _text(item)]


def _numeric_map(value: Any) -> dict[str, int | float]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int | float] = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key)
        if (
            not key
            or isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
            or raw_value < 0
        ):
            continue
        result[key] = raw_value
    return dict(sorted(result.items()))


def _official_base_stats(payload: Mapping[str, Any] | None) -> dict[str, int | float]:
    value = payload if isinstance(payload, Mapping) else {}
    preview = value.get("preview_item")
    preview = preview if isinstance(preview, Mapping) else {}
    stats = preview.get("stats")
    if not isinstance(stats, list):
        return {}
    result: dict[str, int | float] = {}
    for raw_stat in stats:
        if not isinstance(raw_stat, Mapping):
            continue
        stat_type = raw_stat.get("type")
        stat_type = stat_type if isinstance(stat_type, Mapping) else {}
        key = _text(stat_type.get("type") or stat_type.get("name")).upper()
        value = raw_stat.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            continue
        normalized_key = _STAT_TYPE_KEYS.get(key) or key.lower()
        if normalized_key:
            result[normalized_key] = value
    return dict(sorted(result.items()))


def _official_equipment(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    value = payload if isinstance(payload, Mapping) else {}
    preview = value.get("preview_item")
    preview = preview if isinstance(preview, Mapping) else {}
    inventory = value.get("inventory_type")
    inventory = inventory if isinstance(inventory, Mapping) else preview.get("inventory_type")
    inventory = inventory if isinstance(inventory, Mapping) else {}
    item_class = value.get("item_class")
    item_class = item_class if isinstance(item_class, Mapping) else preview.get("item_class")
    item_class = item_class if isinstance(item_class, Mapping) else {}
    item_subclass = value.get("item_subclass")
    item_subclass = item_subclass if isinstance(item_subclass, Mapping) else preview.get("item_subclass")
    item_subclass = item_subclass if isinstance(item_subclass, Mapping) else {}
    result: dict[str, Any] = {}
    inventory_type = _text(inventory.get("type"))
    if inventory_type:
        result["inventoryType"] = inventory_type
    if item_class:
        result["itemClass"] = {
            key: item_class[key]
            for key in ("id", "name")
            if item_class.get(key) not in (None, "")
        }
    if item_subclass:
        result["itemSubclass"] = {
            key: item_subclass[key]
            for key in ("id", "name")
            if item_subclass.get(key) not in (None, "")
        }
    subclass_name = _text(item_subclass.get("name"))
    class_name = _text(item_class.get("name")).lower()
    if subclass_name and class_name == "armor":
        result["armorType"] = subclass_name
    if subclass_name and class_name == "weapon":
        result["weaponType"] = subclass_name
    return result


def _source_refs(
    item_definition: Mapping[str, Any],
    *,
    extra: Sequence[str] = (),
) -> list[str]:
    refs = set(_text_list(item_definition.get("sourceRefIds")))
    refs.update(_text(ref) for ref in extra if _text(ref))
    identity = item_definition.get("itemIdentity")
    item_id = _text(item_definition.get("itemId"))
    if isinstance(identity, Mapping) and item_id:
        refs.add(f"official-api:/data/wow/item/{item_id}#/id")
    return sorted(refs)


def _variant_id(item_id: str, variant_key: str) -> str:
    digest = hashlib.sha256(
        f"s2-runtime-variant\0{item_id}\0{variant_key}".encode("utf-8")
    ).hexdigest()
    return f"s2-variant:{digest}"


def _readback_slot(slot: str, readback: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = readback.get(slot)
    if isinstance(direct, Mapping):
        return direct
    aliases = {
        "wrist": ("wrist", "wrists"),
        "shoulder": ("shoulder", "shoulders"),
        "trinket1": ("trinket1", "trinket"),
        "trinket2": ("trinket2", "trinket"),
        "finger1": ("finger1", "finger"),
        "finger2": ("finger2", "finger"),
    }
    for key in aliases.get(slot, ()):
        value = readback.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _readback_identity(
    readback: Mapping[str, Any],
) -> tuple[str, list[str], int | None, str]:
    encoded = _text(readback.get("encoded_item"))
    item_match = re.search(r"(?:^|,)id=([^,]+)", encoded)
    bonus_match = re.search(r"(?:^|,)bonus_id=([^,]+)", encoded)
    level_match = re.search(r"(?:^|,)ilevel=([^,]+)", encoded)
    item_id = _text(item_match.group(1)) if item_match else ""
    bonus_ids = _text_list(bonus_match.group(1)) if bonus_match else []
    item_level = _int(readback.get("ilevel"))
    if item_level is None and level_match:
        item_level = _int(level_match.group(1))
    return item_id, bonus_ids, item_level, encoded


def _readback_stats(readback: Mapping[str, Any]) -> dict[str, int | float]:
    excluded = {"name", "encoded_item", "ilevel"}
    return _numeric_map(
        {
            key: value
            for key, value in readback.items()
            if _text(key) not in excluded
        }
    )


def _expected_identity(variant: Mapping[str, Any]) -> tuple[str, list[str], int | None, str]:
    canonical = variant.get("canonicalSimcInput")
    canonical = canonical if isinstance(canonical, Mapping) else {}
    options = canonical.get("simcOptions")
    options = options if isinstance(options, Mapping) else {}
    bonus_ids = _text_list(canonical.get("bonusIds"))
    if not bonus_ids:
        bonus_ids = _text_list(options.get("bonus_id"))
    return (
        _text(canonical.get("itemId") or variant.get("itemId")),
        bonus_ids,
        _int(canonical.get("itemLevel")),
        _text(canonical.get("slot") or variant.get("itemSlot")),
    )


def _identity_blockers(
    variant: Mapping[str, Any],
    item_definition: Mapping[str, Any],
    readback: Mapping[str, Any],
) -> list[str]:
    expected_id, expected_bonus_ids, expected_level, expected_slot = _expected_identity(variant)
    actual_id, actual_bonus_ids, actual_level, _encoded = _readback_identity(readback)
    blockers: list[str] = []
    if _text(item_definition.get("itemId")) != expected_id:
        blockers.append("S2_CANDIDATE_ITEM_ID_MISMATCH")
    if _text(item_definition.get("itemSlot")) != _slot(expected_slot):
        blockers.append("S2_CANDIDATE_SLOT_MISMATCH")
    if actual_id != expected_id:
        blockers.append("S2_SIMC_READBACK_ITEM_ID_MISMATCH")
    if sorted(actual_bonus_ids, key=lambda value: (not value.isdigit(), value)) != sorted(
        expected_bonus_ids,
        key=lambda value: (not value.isdigit(), value),
    ):
        blockers.append("S2_SIMC_READBACK_BONUS_VECTOR_MISMATCH")
    if expected_level is None or actual_level != expected_level:
        blockers.append("S2_SIMC_READBACK_ITEM_LEVEL_MISMATCH")
    if not _readback_stats(readback):
        blockers.append("S2_SIMC_READBACK_STATIC_ATTRIBUTES_MISSING")
    if any(
        code in blockers
        for code in (
            "S2_SIMC_READBACK_ITEM_ID_MISMATCH",
            "S2_SIMC_READBACK_BONUS_VECTOR_MISMATCH",
            "S2_SIMC_READBACK_ITEM_LEVEL_MISMATCH",
        )
    ):
        blockers.append("S2_SIMC_READBACK_IDENTITY_MISMATCH")
    return sorted(set(blockers))


def materialize_s2_item(
    item_definition: Mapping[str, Any],
    *,
    base_stats: Mapping[str, Any] | None = None,
    official_payload: Mapping[str, Any] | None = None,
    source_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Project one verified candidate ItemDefinition into a release item row."""

    item_id = _text(item_definition.get("itemId"))
    slot = _slot(item_definition.get("itemSlot"))
    identity = item_definition.get("itemIdentity")
    identity = identity if isinstance(identity, Mapping) else {}
    db2 = item_definition.get("db2StaticFacts")
    db2 = db2 if isinstance(db2, Mapping) else {}
    socket_count = _int(db2.get("socketCount")) or 0
    blockers = []
    if not item_id:
        blockers.append("S2_ITEM_ID_MISSING")
    if not slot:
        blockers.append("S2_ITEM_SLOT_MISSING")
    if item_definition.get("evidenceStatus") != "verified":
        blockers.append("S2_ITEM_EVIDENCE_UNVERIFIED")
    if item_definition.get("simcReadiness") != "ready":
        blockers.append("S2_ITEM_SIMC_UNREADY")
    status = "verified" if not blockers else "blocked"
    normalized_stats = _numeric_map(base_stats)
    refs = _source_refs(item_definition, extra=source_refs)
    payload = {
        "displayName": _text(item_definition.get("itemName")) or _text(identity.get("name")),
        "inventoryType": _text(identity.get("inventoryType")),
        "quality": _text(identity.get("quality")),
        "equipment": _official_equipment(official_payload),
        "baseStats": normalized_stats,
        "baseCapabilities": {
            "socketCount": socket_count,
            "canEnchant": slot in {
                "back",
                "chest",
                "wrist",
                "legs",
                "feet",
                "finger1",
                "finger2",
                "main_hand",
                "off_hand",
            },
            "canEmbellish": slot in {"head", "shoulder", "chest", "wrist", "waist", "legs", "feet", "finger1", "finger2", "main_hand", "off_hand"},
        },
        "sourceRefIds": refs,
        "db2StaticFacts": _canonical(db2),
        "authority": "s2-equipment-library-candidate-v69",
    }
    return {
        "itemId": item_id,
        "name": _text(item_definition.get("itemName")) or _text(identity.get("name")),
        "slot": slot,
        "itemLevel": _int(identity.get("previewItemLevel") or identity.get("itemLevel")) or _int(db2.get("ItemLevel")) or 0,
        "sourceStatus": status,
        "payload": payload,
        "blockers": sorted(set(blockers)),
        "updatedAt": "",
    }


def materialize_s2_variant(
    variant: Mapping[str, Any],
    item_definition: Mapping[str, Any],
    readback_by_slot: Mapping[str, Any],
    *,
    source_type: str = "",
    source_key: str = "",
    source_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Project one exact SimC readback into a resolver-ready variant row."""

    canonical = variant.get("canonicalSimcInput")
    canonical = canonical if isinstance(canonical, Mapping) else {}
    item_id = _text(variant.get("itemId"))
    slot = _slot(variant.get("itemSlot") or canonical.get("slot"))
    variant_key = _text(variant.get("variantKey"))
    readback = _readback_slot(slot, readback_by_slot)
    blockers = _identity_blockers(variant, item_definition, readback)
    if variant.get("status") != "verified":
        blockers.append("S2_CANDIDATE_VARIANT_UNVERIFIED")
    if variant.get("simcReadiness") != "ready":
        blockers.append("S2_CANDIDATE_VARIANT_SIMC_UNREADY")
    blockers = sorted(set(blockers))
    item_level = _int(canonical.get("itemLevel")) or 0
    track_key = _text(
        variant.get("trackKey")
        or variant.get("craftedTrackKey")
        or canonical.get("craftedTrackKey")
    )
    if source_type == "crafted" and not track_key:
        track_key = "crafted_quality"
    rank = _int(variant.get("rank"))
    max_rank = _int(variant.get("maxRank"))
    if track_key and rank and max_rank:
        label = f"{track_key} {rank}/{max_rank}"
    elif track_key:
        label = track_key
    else:
        label = str(item_level) if item_level else ""
    expected_options = canonical.get("simcOptions")
    expected_options = expected_options if isinstance(expected_options, Mapping) else {}
    stats = _readback_stats(readback)
    matrix_evidence = variant.get("simcEvidence")
    matrix_evidence = matrix_evidence if isinstance(matrix_evidence, Mapping) else {}
    quality = variant.get("quality")
    quality = quality if isinstance(quality, Mapping) else {}
    refs = set(_text(ref) for ref in source_refs if _text(ref))
    refs.update(_text(ref) for ref in _text_list(matrix_evidence.get("matrixReportId")))
    if not refs:
        refs.add("s2-equipment-library-candidate-v69")
    payload = {
        "authority": "s2-equipment-library-candidate-v69",
        "canonicalSimcInput": _canonical(canonical),
        "sourceRefIds": sorted(refs),
        "sourceKey": _text(source_key),
        "trackKey": track_key,
        "qualityKey": _text(quality.get("qualityId")),
        "rank": rank,
        "maxRank": max_rank,
        "statDeltas": {},
        "simcReadbackStatus": "verified" if not blockers else "blocked",
        "simcEncodedItem": _text(readback.get("encoded_item")),
        "simcItemId": _readback_identity(readback)[0],
        "simcItemLevel": _readback_identity(readback)[2],
    }
    if not blockers:
        payload.update({
            "resolvedStats": stats,
            "staticStats": stats,
            "itemStats": stats,
            "stats": stats,
        })
    return {
        "variantId": _variant_id(item_id, variant_key),
        "itemId": item_id,
        "variantKey": variant_key,
        "slot": slot,
        "label": label,
        "sourceType": _text(source_type),
        "sourceKey": _text(source_key),
        "difficultyKey": "",
        "itemLevel": item_level,
        "simcOptions": _canonical(expected_options),
        "status": "verified" if not blockers else "blocked",
        "blockers": blockers,
        "payload": payload,
        "updatedAt": "",
    }


def _source_row_id(item_id: str, source_type: str, source_key: str) -> str:
    digest = hashlib.sha256(
        f"s2-runtime-source\0{item_id}\0{source_type}\0{source_key}".encode("utf-8")
    ).hexdigest()
    return f"s2-source:{digest}"


def _source_label(source_type: str, source_key: str) -> str:
    labels = {
        "raid": "Raid",
        "mythic_plus": "Mythic+",
        "crafted": "Crafted",
        "tier_set": "Tier set",
    }
    return f"{labels.get(source_type, source_type)} · {source_key}" if source_key else labels.get(source_type, source_type)


def _source_candidates(candidate: Mapping[str, Any], season_revision: str) -> dict[str, list[dict[str, Any]]]:
    by_item: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

    def add(
        raw: Mapping[str, Any],
        *,
        source_type: str,
        source_key: str,
        evidence_status: str,
        raw_source_type: str = "",
    ) -> None:
        item_id = _text(raw.get("itemId"))
        if not item_id or not source_type or not source_key:
            return
        if _text(raw.get("scopeStatus")).lower() != "included":
            return
        if evidence_status.lower() not in {"verified", ""}:
            return
        key = (source_type, source_key)
        by_item.setdefault(item_id, {})[key] = {
            "sourceId": _source_row_id(item_id, source_type, source_key),
            "itemId": item_id,
            "sourceType": source_type,
            "sourceKey": source_key,
            "sourceLabel": _source_label(source_type, source_key),
            "instanceId": "",
            "encounterId": "",
            "difficultyKey": "",
            "seasonRevision": season_revision,
            "payload": {
                "authority": "s2-equipment-library-candidate-v69",
                "sourceMembershipStatus": evidence_status or "verified",
                "rawSourceType": raw_source_type or source_type,
            },
            "updatedAt": "",
        }

    for raw in candidate.get("sourceMemberships") or []:
        if not isinstance(raw, Mapping):
            continue
        source_type = _text(raw.get("logicalSource"))
        source_key = _text(raw.get("rawSourceKey"))
        add(
            raw,
            source_type=source_type,
            source_key=source_key,
            raw_source_type=_text(raw.get("rawSourceType")),
            evidence_status=_text(raw.get("sourceMembershipStatus")) or "verified",
        )

    for raw in candidate.get("craftedRelationships") or []:
        if not isinstance(raw, Mapping):
            continue
        recipe_id = _text(raw.get("recipeId"))
        add(
            raw,
            source_type="crafted",
            source_key=f"crafted:recipe:{recipe_id}" if recipe_id else "",
            evidence_status=_text(raw.get("outputStatus") or raw.get("status")) or "verified",
            raw_source_type="crafted",
        )

    for raw in candidate.get("tierSetMemberships") or []:
        if not isinstance(raw, Mapping):
            continue
        set_id = _text(raw.get("setId"))
        add(
            raw,
            source_type="tier_set",
            source_key=_text(raw.get("rawSourceKey")) or f"tier_set:item-set:{set_id}",
            evidence_status=_text(raw.get("sourceMembershipStatus")) or "verified",
            raw_source_type="tier_set",
        )

    return {
        item_id: [
            rows[key]
            for key in sorted(rows, key=lambda value: (value[0], value[1]))
        ]
        for item_id, rows in sorted(by_item.items())
    }


def _materialize_s2_options(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    catalog = candidate.get("enhancementCatalog")
    catalog = catalog if isinstance(catalog, Mapping) else {}
    options: list[dict[str, Any]] = []
    for raw in catalog.get("options") or []:
        if not isinstance(raw, Mapping):
            continue
        option_id = _text(raw.get("optionId"))
        option_key = _text(raw.get("optionKey"))
        option_type = _text(raw.get("optionType")).lower()
        if not option_id or not option_key:
            continue
        if option_type == "gem":
            runtime_type = "socket"
        elif option_type == "crafted_stats":
            runtime_type = "crafted"
        else:
            runtime_type = option_type
        payload = raw.get("payload")
        payload = _canonical(payload) if isinstance(payload, Mapping) else {}
        payload.update({
            "authority": "s2-equipment-library-candidate-v69",
            "sourceRefs": _text_list(raw.get("sourceRefs")),
            "statSummary": _text(raw.get("statSummary")),
            "optionType": runtime_type,
            "candidateOptionType": option_type,
        })
        options.append({
            "optionId": option_id,
            "variantId": "",
            "optionKey": option_key,
            "optionType": runtime_type,
            "name": _text(raw.get("name")) or option_key,
            "applicableSlots": [
                _slot(value)
                for value in raw.get("applicableSlots") or []
                if _slot(value)
            ],
            "simcOptions": _canonical(raw.get("simcOptions") if isinstance(raw.get("simcOptions"), Mapping) else {}),
            "status": _text(raw.get("status")) or "blocked",
            "isVisible": True,
            "payload": payload,
            "updatedAt": "",
        })
    return sorted(options, key=lambda row: (_text(row.get("optionType")), _text(row.get("optionKey"))))


def _variant_source(
    item_definition: Mapping[str, Any],
    sources: Mapping[str, list[dict[str, Any]]],
    variant: Mapping[str, Any],
) -> tuple[str, str]:
    item_id = _text(variant.get("itemId"))
    rows = sources.get(item_id) or []
    variant_key = _text(variant.get("variantKey"))
    if variant_key.startswith("s2-crafted:"):
        crafted = [row for row in rows if row.get("sourceType") == "crafted"]
        if crafted:
            recipe_match = re.search(r":recipe:([^:]+):", variant_key)
            if recipe_match:
                wanted = f"crafted:recipe:{recipe_match.group(1)}"
                for row in crafted:
                    if _text(row.get("sourceKey")) == wanted:
                        return "crafted", wanted
            return "crafted", _text(crafted[0].get("sourceKey"))
        return "crafted", "crafted:s2"
    logical_sources = item_definition.get("logicalSources")
    preferred = _text_list(logical_sources)
    for source_type in [*preferred, "raid", "mythic_plus", "tier_set", "crafted"]:
        for row in rows:
            if _text(row.get("sourceType")) == source_type:
                return source_type, _text(row.get("sourceKey"))
    return "", ""


def build_s2_runtime_snapshot(
    candidate: Mapping[str, Any],
    readback_report: Mapping[str, Any],
    *,
    official_items: Mapping[str, Any] | None = None,
    season_revision: str,
) -> dict[str, Any]:
    """Build one complete release snapshot, failing closed on missing facts."""

    candidate_value = candidate if isinstance(candidate, Mapping) else {}
    readback = readback_report if isinstance(readback_report, Mapping) else {}
    official = official_items if isinstance(official_items, Mapping) else {}
    candidate_report_id = _text(candidate_value.get("reportId"))
    blockers: list[str] = []
    if _text(candidate_value.get("status")) != "verified":
        blockers.append("S2_CANDIDATE_REPORT_UNVERIFIED")
    if _text(readback.get("status")) != "verified":
        blockers.append("S2_SIMC_READBACK_REPORT_UNVERIFIED")
    if not _text(season_revision).startswith("season-midnight-season-2:"):
        blockers.append("S2_SEASON_REVISION_INVALID")

    item_definitions = [
        row
        for row in candidate_value.get("itemDefinitions") or []
        if isinstance(row, Mapping)
    ]
    definitions_by_id = {
        _text(row.get("itemId")): row
        for row in item_definitions
        if _text(row.get("itemId"))
    }
    source_by_item = _source_candidates(candidate_value, season_revision)
    report_refs = [candidate_report_id] if candidate_report_id else []
    items: list[dict[str, Any]] = []
    for item_id in sorted(definitions_by_id, key=lambda value: int(value) if value.isdigit() else value):
        definition = definitions_by_id[item_id]
        item = materialize_s2_item(
            definition,
            base_stats=_official_base_stats(official.get(item_id)),
            official_payload=official.get(item_id),
            source_refs=report_refs,
        )
        item["payload"]["sources"] = _canonical(source_by_item.get(item_id) or [])
        items.append(item)

    options = _materialize_s2_options(candidate_value)
    visible_options = [row for row in options if row.get("status") == "verified" and row.get("isVisible") is True]
    for item in items:
        capabilities = item["payload"].get("baseCapabilities")
        capabilities = capabilities if isinstance(capabilities, dict) else {}
        item_slot = _slot(item.get("slot"))
        applicable = lambda option: not option.get("applicableSlots") or "*" in option.get("applicableSlots") or item_slot in option.get("applicableSlots", [])
        capabilities["allowedGemOptionIds"] = [
            row["optionId"] for row in visible_options
            if row.get("optionType") == "socket" and applicable(row)
        ]
        capabilities["allowedEnchantOptionIds"] = [
            row["optionId"] for row in visible_options
            if row.get("optionType") == "enchant" and applicable(row)
        ]
        capabilities["allowedEmbellishmentOptionIds"] = [
            row["optionId"] for row in visible_options
            if row.get("optionType") == "embellishment" and applicable(row)
        ]
        capabilities["allowedCraftedOptionIds"] = [
            row["optionId"] for row in visible_options
            if row.get("optionType") == "crafted" and applicable(row)
        ]
        item["payload"]["baseCapabilities"] = capabilities

    sources = [
        row
        for item_id in sorted(source_by_item)
        for row in source_by_item[item_id]
    ]
    readbacks = readback.get("readbacks")
    readbacks = readbacks if isinstance(readbacks, Mapping) else {}
    variants: list[dict[str, Any]] = []
    candidate_variants = [
        row
        for row in candidate_value.get("variants") or []
        if isinstance(row, Mapping)
        and _text(row.get("simcReadiness")) == "ready"
    ]
    candidate_variants.extend(
        row
        for row in candidate_value.get("craftedVariantTemplates") or []
        if isinstance(row, Mapping)
        and _text(row.get("simcReadiness")) == "ready"
    )
    seen_variant_keys: set[tuple[str, str]] = set()
    for raw_variant in candidate_variants:
        item_id = _text(raw_variant.get("itemId"))
        variant_key = _text(raw_variant.get("variantKey"))
        identity = (item_id, variant_key)
        if identity in seen_variant_keys:
            blockers.append("S2_RUNTIME_VARIANT_DUPLICATE")
            continue
        seen_variant_keys.add(identity)
        definition = definitions_by_id.get(item_id, {})
        readback_row = readbacks.get(variant_key)
        gear = readback_row.get("gear") if isinstance(readback_row, Mapping) else {}
        source_type, source_key = _variant_source(definition, source_by_item, raw_variant)
        row = materialize_s2_variant(
            raw_variant,
            definition,
            gear if isinstance(gear, Mapping) else {},
            source_type=source_type,
            source_key=source_key,
            source_refs=report_refs,
        )
        if not source_type or not source_key:
            row["status"] = "blocked"
            row["blockers"] = sorted(set(row.get("blockers") or []) | {"S2_RUNTIME_VARIANT_SOURCE_MISSING"})
        variants.append(row)

    blocked_variant_count = sum(row.get("status") != "verified" for row in variants)
    if blocked_variant_count:
        blockers.append("S2_RUNTIME_VARIANT_BLOCKED")
    expected_variant_count = len(candidate_variants)
    if len(variants) != expected_variant_count:
        blockers.append("S2_RUNTIME_VARIANT_COUNT_MISMATCH")
    if not items:
        blockers.append("S2_RUNTIME_ITEMS_EMPTY")
    if not sources:
        blockers.append("S2_RUNTIME_SOURCES_EMPTY")
    if not variants:
        blockers.append("S2_RUNTIME_VARIANTS_EMPTY")
    option_blockers = sum(row.get("status") != "verified" for row in options)
    if option_blockers:
        blockers.append("S2_RUNTIME_OPTION_BLOCKED")
    blockers = sorted(set(blockers))
    return {
        "schemaRevision": "s2-equipment-library-runtime-snapshot-v1",
        "status": "verified" if not blockers else "blocked",
        "seasonRevision": _text(season_revision),
        "items": items,
        "sources": sources,
        "variants": sorted(variants, key=lambda row: (_text(row.get("itemId")), _text(row.get("variantKey")))),
        "options": options,
        "runtimeEvidence": {
            "candidateReportId": candidate_report_id,
            "simcReadbackReportId": _text(readback.get("reportId")),
            "simcRuntimeIdentity": _text(readback.get("runtimeIdentity")),
            "candidateStatus": _text(candidate_value.get("status")),
            "readbackStatus": _text(readback.get("status")),
        },
        "counts": {
            "items": len(items),
            "sources": len(sources),
            "variants": len(variants),
            "verifiedVariants": len(variants) - blocked_variant_count,
            "blockedVariants": blocked_variant_count,
            "options": len(options),
            "blockedOptions": option_blockers,
        },
        "blockers": blockers,
    }


def assemble_s2_simc_readback_report(
    plan: Mapping[str, Any],
    batches: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Retain the exact static-attribute readback needed by the materializer.

    The normal matrix report intentionally keeps only pass/fail evidence.  A
    release build needs the numeric readback as a separate, immutable build
    artifact.  Set/representative jobs are ignored here because they do not
    identify a publishable catalog variant.
    """

    try:
        from .s2_equipment_library_simc_matrix import validate_s2_item_probe_result
    except ImportError:
        from s2_equipment_library_simc_matrix import validate_s2_item_probe_result

    jobs = [
        job
        for job in plan.get("jobs") or []
        if isinstance(job, Mapping)
        and _text(job.get("kind")) in {"public_variant", "crafted_variant"}
    ]
    results_by_key: dict[str, Mapping[str, Any]] = {}
    runtime_statuses = set()
    for batch in batches or []:
        if not isinstance(batch, Mapping):
            continue
        runtime_statuses.add(_text(batch.get("runtimeIdentityStatus")))
        for raw_result in batch.get("results") or []:
            if isinstance(raw_result, Mapping) and _text(raw_result.get("jobKey")):
                results_by_key[_text(raw_result.get("jobKey"))] = raw_result

    readbacks: dict[str, dict[str, Any]] = {}
    blocked: list[dict[str, Any]] = []
    duplicate_keys: set[str] = set()
    for job in jobs:
        job_key = _text(job.get("jobKey"))
        variant_key = _text(job.get("variantKey"))
        result = results_by_key.get(job_key, {})
        validation = validate_s2_item_probe_result(job, result)
        status = _text(validation.get("status"))
        if status != "verified" or _int(result.get("returncode")) != 0:
            status = "blocked"
        if not variant_key or variant_key in readbacks:
            if variant_key:
                duplicate_keys.add(variant_key)
            status = "blocked"
        record = {
            "variantKey": variant_key,
            "itemId": _text(job.get("itemId")),
            "slot": _slot(job.get("slot")),
            "status": status,
            "gear": _canonical(result.get("gear") if isinstance(result.get("gear"), Mapping) else {}),
            "validation": _canonical(validation),
        }
        if variant_key and variant_key not in readbacks:
            readbacks[variant_key] = record
        if status != "verified":
            blocked.append({
                "jobKey": job_key,
                "variantKey": variant_key,
                "itemId": _text(job.get("itemId")),
                "failureCodes": list(validation.get("failureCodes") or []),
            })

    for variant_key in sorted(duplicate_keys):
        blocked.append({
            "variantKey": variant_key,
            "failureCodes": ["S2_SIMC_READBACK_VARIANT_KEY_DUPLICATE"],
        })
    blocked.sort(key=lambda row: (_text(row.get("jobKey")), _text(row.get("variantKey"))))
    verified_count = sum(row.get("status") == "verified" for row in readbacks.values())
    expected_count = len(jobs)
    runtime_verified = runtime_statuses == {"verified"}
    status = (
        "verified"
        if expected_count > 0 and runtime_verified and not blocked and verified_count == expected_count
        else "partial"
    )
    return {
        "schemaRevision": "s2-equipment-library-simc-readback-v1",
        "status": status,
        "candidateReportId": _text(plan.get("candidateReportId")),
        "runtimeIdentity": _text(plan.get("runtimeIdentity")),
        "runtimeIdentityStatus": "verified" if runtime_verified else "UNVERIFIED",
        "counts": {
            "expected": expected_count,
            "verified": verified_count,
            "blocked": len(blocked),
        },
        "blocked": blocked,
        "readbacks": {
            key: readbacks[key]
            for key in sorted(readbacks)
        },
    }


__all__ = (
    "assemble_s2_simc_readback_report",
    "build_s2_runtime_snapshot",
    "materialize_s2_item",
    "materialize_s2_variant",
)
