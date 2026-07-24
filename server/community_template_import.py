#!/usr/bin/env python3
"""Pure projection of one sealed observed community template into canonical gear input."""

from __future__ import annotations

import json
from typing import Any


COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION = "websim-community-template-import-v2"
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_V1 = "community-template-import-evidence-v1"
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_V2 = "community-template-import-evidence-v2"
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION = "community-template-import-evidence-v3"
_SUPPORTED_COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISIONS = {
    COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_V1,
    COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_V2,
    COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
}
PUBLIC_OBSERVED_SOURCE_KEY = "raiderio_observed_profile"
_ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION = "gear-attribute-stable-effects-v1"

_OPTION_FIELDS = (
    ("gemOptionIds", "gem", "gemCount"),
    ("enchantOptionId", "enchant", "enchantCount"),
    ("embellishmentOptionId", "embellishment", "embellishmentCount"),
    ("craftedOptionId", "crafted", "craftedCount"),
    ("catalystOptionId", "catalyst", "catalystCount"),
)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _attribute_race_key(value: Any) -> str:
    key = _text(value)
    return key if key and len(key) <= 80 and key[0].isalpha() and key == key.lower() and all(
        character.isalnum() or character == "_" for character in key
    ) else ""


def _attribute_character_context_from_evidence(evidence: dict[str, Any]) -> dict[str, str]:
    if (
        _text(evidence.get("schemaRevision")) in {
            COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_V2,
            COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
        }
        and _text(evidence.get("sourceRaceOrigin")) == "source_profile"
        and (race_key := _attribute_race_key(evidence.get("sourceRaceKey")))
    ):
        return {
            "schemaRevision": "gear-attribute-character-v1",
            "raceKey": race_key,
            "origin": "source_profile",
        }
    return {
        "schemaRevision": "gear-attribute-character-v1",
        "raceKey": "human",
        "origin": "default_human",
    }


def _attribute_stable_effect_context_from_evidence(evidence: dict[str, Any]) -> dict[str, Any] | None:
    if _text(evidence.get("schemaRevision")) != COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION:
        return None
    context = evidence.get("sourceStableEffects")
    if not isinstance(context, dict) or context.get("status") != "verified":
        return None
    effect_ids = context.get("effectIds")
    signature = _text(context.get("loadoutSignature"))
    if (
        set(context) != {
            "schemaRevision", "status", "origin", "effectIds", "loadoutSignature"
        }
        or context.get("schemaRevision") != _ATTRIBUTE_STABLE_EFFECT_CONTEXT_REVISION
        or context.get("origin") != "source_profile"
        or not isinstance(effect_ids, list)
        or effect_ids != sorted(set(effect_ids))
        or any(
            not isinstance(effect_id, str)
            or not effect_id
            or effect_id != effect_id.lower()
            or len(effect_id) > 256
            for effect_id in effect_ids
        )
        or len(signature) != 71
        or not signature.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in signature[7:])
    ):
        return None
    return _copy(context)


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _problem(code: str, title: str, *, retryable: bool = False) -> dict[str, Any]:
    return {"code": code, "title": title, "retryable": retryable}


def community_template_import_problem(code: str, title: str, *, retryable: bool = False) -> dict[str, Any]:
    """Return a bounded public problem without source payload details."""

    return _problem(_text(code), _text(title), retryable=retryable)


def _blocked(problem: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "blocked",
        "template": {},
        "importedGearBySlot": {},
        "visibleOptionsBySlot": {},
        "selectionIntent": None,
        "problems": [problem],
    }


def _option_is_usable(option: Any, slot: str, expected_type: str) -> bool:
    value = option if isinstance(option, dict) else {}
    applicable_slots = value.get("applicableSlots")
    option_type = _text(value.get("optionType"))
    return (
        bool(_text(value.get("optionKey")))
        and (option_type == expected_type or (expected_type == "gem" and option_type == "socket"))
        and _text(value.get("status")) == "verified"
        and value.get("isVisible") is True
        and isinstance(applicable_slots, list)
        and (slot in applicable_slots or "*" in applicable_slots)
    )


def _winner_import_evidence(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    evidence = payload.get("importEvidence") if isinstance(payload.get("importEvidence"), dict) else {}
    slots = evidence.get("slots") if isinstance(evidence.get("slots"), dict) else {}
    if (
        _text(evidence.get("schemaRevision")) not in _SUPPORTED_COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISIONS
        or not _text(evidence.get("sourceFingerprint")).startswith("sha256:")
        or not slots
    ):
        return None
    if (
        _text(evidence.get("schemaRevision")) == COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION
        and not isinstance(evidence.get("sourceStableEffects"), dict)
    ):
        return None
    return evidence


def _verified_item_icon(
    item: dict[str, Any],
    sealed_evidence: dict[str, Any],
) -> tuple[str, dict[str, str]] | None:
    """Return the sealed observed icon, optionally corroborated by catalog metadata."""

    sealed_icon_url = _text(sealed_evidence.get("iconUrl"))
    if not sealed_icon_url:
        return None
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
    game_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), dict) else {}
    icon_url = _text(metadata.get("iconUrl"))
    if _text(game_asset.get("status")) == "verified" and icon_url == sealed_icon_url:
        return sealed_icon_url, {
            "source": _text(game_asset.get("source")) or "blizzard",
            "status": "verified",
            "iconUrl": sealed_icon_url,
        }
    # The release materializer only seals this field after binding it to the
    # selected observed item. A slim or divergent generic catalog row cannot
    # replace that player-specific display fact or make the import partial.
    return sealed_icon_url, {
        "source": "sealed_observed_profile",
        "status": "verified",
        "iconUrl": sealed_icon_url,
    }


def build_community_template_import_source(
    winner: Any,
    variants: Any,
    options: Any,
    *,
    items: Any = None,
    sources: Any = None,
) -> dict[str, Any]:
    """Build canonical import facts from immutable, already-bound Release rows only."""

    row = winner if isinstance(winner, dict) else {}
    if row.get("role") != "winner" or row.get("sourceKey") != PUBLIC_OBSERVED_SOURCE_KEY:
        return _blocked(_problem("template_not_active", "The requested observed template is not active."))

    class_key = _text(row.get("classKey"))
    spec_key = _text(row.get("specKey"))
    intent = row.get("selectionIntent") if isinstance(row.get("selectionIntent"), dict) else {}
    eligibility = intent.get("eligibilityContext") if isinstance(intent.get("eligibilityContext"), dict) else {}
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    authored = intent.get("authoredAgainst") if isinstance(intent.get("authoredAgainst"), dict) else {}
    if (
        not _text(row.get("templateId"))
        or not class_key
        or not spec_key
        or intent.get("schemaRevision") != "selection-intent-v1"
        or eligibility.get("classKey") != class_key
        or eligibility.get("specKey") != spec_key
        or not isinstance(eligibility.get("level"), int)
        or isinstance(eligibility.get("level"), bool)
        or eligibility.get("level") <= 0
        or not _text(authored.get("seasonRevision"))
        or not _text(authored.get("gearCatalogRevision"))
        or not slots
    ):
        return _blocked(_problem("template_inapplicable", "The active template cannot be imported."))

    import_evidence = _winner_import_evidence(row)
    if import_evidence is None:
        return _blocked(_problem(
            "template_import_evidence_incomplete",
            "The active template lacks complete sealed import evidence.",
        ))
    evidence_slots = import_evidence["slots"]
    if set(evidence_slots) != set(slots):
        return _blocked(_problem(
            "template_import_evidence_incomplete",
            "The active template lacks complete sealed import evidence.",
        ))

    variants_by_identity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for value in variants if isinstance(variants, list) else []:
        if not isinstance(value, dict):
            continue
        item_id = _text(value.get("itemId"))
        variant_key = _text(value.get("variantKey"))
        if not item_id or not variant_key:
            continue
        variants_by_identity.setdefault((item_id, variant_key), []).append(value)
    options_by_key = {
        _text(value.get("optionKey")): value
        for value in options if isinstance(options, list) and isinstance(value, dict)
        if _text(value.get("optionKey"))
    }
    items_by_id: dict[str, list[dict[str, Any]]] = {}
    for value in items if isinstance(items, list) else []:
        if isinstance(value, dict) and _text(value.get("itemId")):
            items_by_id.setdefault(_text(value.get("itemId")), []).append(value)

    canonical_slots: dict[str, dict[str, Any]] = {}
    imported_gear_by_slot: dict[str, dict[str, Any]] = {}
    visible_options_by_slot: dict[str, dict[str, dict[str, str]]] = {}
    for slot in sorted(slots):
        selection = slots.get(slot)
        if not isinstance(selection, dict) or not _text(slot):
            return _blocked(_problem("template_inapplicable", "The active template contains an invalid slot."))
        item_id = _text(selection.get("itemId"))
        variant_key = _text(selection.get("variantKey"))
        evidence = evidence_slots.get(slot) if isinstance(evidence_slots.get(slot), dict) else {}
        if (
            _text(evidence.get("itemId")) != item_id
            or _text(evidence.get("variantKey")) != variant_key
            or not isinstance(evidence.get("observedItemLevel"), int)
            or isinstance(evidence.get("observedItemLevel"), bool)
            or evidence.get("observedItemLevel") <= 0
            or not _text(evidence.get("iconUrl"))
        ):
            return _blocked(_problem(
                "template_import_evidence_incomplete",
                "The active template lacks complete sealed import evidence.",
            ))
        candidate_variants = variants_by_identity.get((item_id, variant_key)) or []
        variant = candidate_variants[0] if len(candidate_variants) == 1 else None
        if (
            not isinstance(variant, dict)
            or _text(variant.get("slot")) != slot
            or _text(variant.get("status")) != "verified"
            or _int(variant.get("itemLevel")) != evidence["observedItemLevel"]
        ):
            return _blocked(_problem(
                "template_import_evidence_incomplete",
                "The active template does not match its sealed observed gear.",
            ))
        active_variant_key = _text(variant.get("variantKey"))
        item_candidates = items_by_id.get(item_id) or []
        item = item_candidates[0] if len(item_candidates) == 1 else None
        image = (
            _verified_item_icon(item, evidence)
            if isinstance(item, dict)
            else None
        )
        if not active_variant_key or image is None:
            return _blocked(_problem(
                "template_import_evidence_incomplete",
                "The active template does not have a verified matching item image.",
            ))
        icon_url, game_asset = image

        canonical_slot = {
            "itemId": item_id,
            "variantKey": active_variant_key,
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        display_name = _text(item.get("name")) or _text(variant.get("label")) or item_id
        imported = {
            "variantId": _text(variant.get("id") or variant.get("variantId")),
            "itemId": item_id,
            "variantKey": active_variant_key,
            "slot": slot,
            "label": _text(variant.get("label")),
            "displayName": display_name,
            "name": display_name,
            "itemLevel": evidence["observedItemLevel"],
            "ilevel": evidence["observedItemLevel"],
            "iconUrl": icon_url,
            "gameAsset": game_asset,
        }
        imported_gear_by_slot[slot] = imported
        slot_visible_options: dict[str, dict[str, str]] = {}
        for field, expected_type, count_field in _OPTION_FIELDS:
            raw_values = selection.get(field, [] if field == "gemOptionIds" else "")
            if field == "gemOptionIds":
                if not isinstance(raw_values, list):
                    return _blocked(_problem("template_import_enhancement_unavailable", "The active template has an invalid gem selection."))
                values = raw_values
            elif isinstance(raw_values, str):
                values = [raw_values]
            else:
                return _blocked(_problem("template_import_enhancement_unavailable", "The active template has an invalid enhancement selection."))
            accepted: list[str] = []
            for value in values:
                option_key = _text(value)
                if not option_key:
                    continue
                option = options_by_key.get(option_key)
                if not _option_is_usable(option, slot, expected_type):
                    return _blocked(_problem(
                        "template_import_enhancement_unavailable",
                        "The active template has an unavailable enhancement.",
                    ))
                accepted.append(option_key)
                slot_visible_options[option_key] = {
                    "optionKey": option_key,
                    "optionType": expected_type,
                    "name": _text(option.get("name")),
                }
            if field == "gemOptionIds":
                canonical_slot[field] = accepted
            elif len(accepted) > 1:
                return _blocked(_problem("template_import_enhancement_unavailable", "The active template has an invalid enhancement selection."))
            elif accepted:
                canonical_slot[field] = accepted[0]
        canonical_slots[slot] = canonical_slot
        if slot_visible_options:
            visible_options_by_slot[slot] = slot_visible_options

    template = {
        "id": _text(row.get("templateId")),
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": PUBLIC_OBSERVED_SOURCE_KEY,
        "name": _text((row.get("payload") or {}).get("name")) if isinstance(row.get("payload"), dict) else "",
        "profileHash": _text(row.get("profileHash")),
        "gearHash": _text(row.get("gearHash")),
        "sourceFingerprint": _text(import_evidence.get("sourceFingerprint")),
        "attributeCharacterContext": _attribute_character_context_from_evidence(import_evidence),
    }
    stable_effect_context = _attribute_stable_effect_context_from_evidence(import_evidence)
    if stable_effect_context:
        template["attributeStableEffectContext"] = stable_effect_context

    source = {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "verified",
        "template": template,
        "importedGearBySlot": imported_gear_by_slot,
        "visibleOptionsBySlot": visible_options_by_slot,
        "selectionIntent": {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": _text(authored.get("seasonRevision")),
                "gearCatalogRevision": _text(authored.get("gearCatalogRevision")),
            },
            "eligibilityContext": {
                "classKey": class_key,
                "specKey": spec_key,
                "level": eligibility.get("level"),
            },
            "slots": canonical_slots,
        },
        "problems": [],
    }
    return _copy(source)


def build_community_template_selection_intent(source: Any) -> dict[str, Any] | None:
    """Return only the projector-built canonical Intent for Resolver consumption."""

    value = source if isinstance(source, dict) else {}
    if value.get("status") != "verified":
        return None
    intent = value.get("selectionIntent")
    return _copy(intent) if isinstance(intent, dict) else None


def _verified_game_asset(value: Any, icon_url: str) -> dict[str, str] | None:
    asset = value if isinstance(value, dict) else {}
    if (
        not icon_url
        or _text(asset.get("status")) != "verified"
        or (
            _text(asset.get("iconUrl"))
            and _text(asset.get("iconUrl")) != icon_url
        )
    ):
        return None
    source = _text(asset.get("source"))
    if not source:
        return None
    return {
        "status": "verified",
        "source": source,
        "iconUrl": icon_url,
    }


def _complete_imported_gear_display(
    source: dict[str, Any],
    resolved_snapshot: Any,
    authority_context: Any,
) -> dict[str, dict[str, Any]] | None:
    """Bind any thin observed rows to the exact Resolver display authority.

    Observed Build projections intentionally retain only player selection facts.
    They must not become a second, lossy source for names or media.  A row that
    is already sealed remains intact; a thin row is populated only when the
    just-verified Resolver snapshot and its exact Authority Context agree.
    """

    imported = source.get("importedGearBySlot")
    if not isinstance(imported, dict) or not imported:
        return None
    snapshot = resolved_snapshot if isinstance(resolved_snapshot, dict) else {}
    resolved_slots = snapshot.get("resolvedSlots")
    resolved_slots = resolved_slots if isinstance(resolved_slots, dict) else {}
    authority = authority_context if isinstance(authority_context, dict) else {}
    items_by_id = authority.get("itemsById")
    items_by_id = items_by_id if isinstance(items_by_id, dict) else {}
    completed: dict[str, dict[str, Any]] = {}

    for slot in sorted(imported):
        row = imported.get(slot)
        if not isinstance(row, dict) or _text(row.get("slot")) not in {"", slot}:
            return None
        item_id = _text(row.get("itemId"))
        variant_key = _text(row.get("variantKey"))
        if not item_id or not variant_key:
            return None
        existing_icon_url = _text(row.get("iconUrl"))
        existing_asset = _verified_game_asset(row.get("gameAsset"), existing_icon_url)
        existing_name = _text(row.get("displayName")) or _text(row.get("name"))
        if existing_name and existing_asset is not None:
            completed[slot] = _copy({
                **row,
                "slot": slot,
                "name": existing_name,
                "displayName": existing_name,
                "iconUrl": existing_icon_url,
                "gameAsset": existing_asset,
            })
            continue

        resolved = resolved_slots.get(slot)
        item = items_by_id.get(item_id)
        if not isinstance(resolved, dict) or not isinstance(item, dict):
            return None
        resolved_name = _text(resolved.get("displayName"))
        authority_name = _text(item.get("displayName"))
        icon_url = _text(item.get("iconUrl"))
        game_asset = _verified_game_asset(item.get("gameAsset"), icon_url)
        if (
            not resolved_name
            or resolved_name != authority_name
            or _text(resolved.get("itemId")) != item_id
            or _text(resolved.get("variantKey")) != variant_key
            or game_asset is None
        ):
            return None
        completed[slot] = _copy({
            **row,
            "slot": slot,
            "name": resolved_name,
            "displayName": resolved_name,
            "iconUrl": icon_url,
            "gameAsset": game_asset,
        })
    return completed


def community_template_import_public_data(
    source: Any,
    resolved_snapshot: Any,
    release_context: Any,
    *,
    authority_context: Any = None,
) -> dict[str, Any] | None:
    """Expose bounded import facts; never serialize the sealed source Intent or rows."""

    value = source if isinstance(source, dict) else {}
    status = "verified" if value.get("status") == "verified" else "blocked"
    context = release_context if isinstance(release_context, dict) else {}
    imported = (
        _complete_imported_gear_display(value, resolved_snapshot, authority_context)
        if status == "verified"
        else {}
    )
    if status == "verified" and imported is None:
        return None
    return _copy({
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": status,
        "template": value.get("template") if status == "verified" and isinstance(value.get("template"), dict) else {},
        "manifest": {
            "manifestRevision": _text(context.get("manifestRevision")),
            "pointerGeneration": context.get("pointerGeneration") if isinstance(context.get("pointerGeneration"), int) else 0,
        },
        "importedGearBySlot": imported if status == "verified" else {},
        "resolvedSnapshot": resolved_snapshot if status == "verified" and isinstance(resolved_snapshot, dict) else {},
    })


__all__ = [
    "COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION",
    "COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION",
    "PUBLIC_OBSERVED_SOURCE_KEY",
    "build_community_template_import_source",
    "build_community_template_selection_intent",
    "community_template_import_problem",
    "community_template_import_public_data",
]
