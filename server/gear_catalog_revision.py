#!/usr/bin/env python3
"""Pure deterministic builder for dormant Gear Catalog revisions.

The builder owns canonical CatalogRevision, ItemDefinition membership and one
BrowseVariant per governed progression state. It has no database, filesystem,
network, clock, process or active-pointer behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from .gear_catalog_migration_audit import audit_catalog_mapping
    from .gear_track_authority import (
        resolve_exact_instance_progression,
        resolve_legacy_browse_progression,
    )
    from .websim_payload import item_type_metadata_from_payload
except ImportError:
    from gear_catalog_migration_audit import audit_catalog_mapping
    from gear_track_authority import (
        resolve_exact_instance_progression,
        resolve_legacy_browse_progression,
    )
    from websim_payload import item_type_metadata_from_payload


LEGACY_CATALOG_SCHEMA_REVISION = "gear-catalog-revision-v1"
VARIANT_SHAPE_CATALOG_SCHEMA_REVISION = "gear-catalog-revision-v2"
CATALOG_SCHEMA_REVISION = "gear-catalog-revision-v3"
CATALOG_BUILDER_REVISION = "gear-catalog-builder-v4"
CATALOG_REVISION_PATTERN = re.compile(
    r"^gear-catalog:sha256:[0-9a-f]{64}$"
)
BROWSE_VARIANT_KEY_PATTERN = re.compile(
    r"^browse-variant:sha256:[0-9a-f]{64}$"
)
VARIANT_SHAPE_KEY_PATTERN = re.compile(
    r"^variant-shape:sha256:[0-9a-f]{64}$"
)

_NON_IDENTITY_KEYS = {
    "checkedAt",
    "createdAt",
    "displayLabel",
    "displayName",
    "jobId",
    "logPath",
    "observedAt",
    "sourceLabel",
    "sourceUpdatedAt",
    "updatedAt",
}
_ITEM_MEDIA_KEYS = ("icon", "iconUrl")
_ITEM_EQUIPMENT_KEYS = (
    "armorType",
    "inventoryType",
    "itemClass",
    "itemSubclass",
    "weaponType",
)
_ITEM_RESTRICTION_KEYS = (
    "canDualWield",
    "classIds",
    "itemLimitCategory",
    "requiredClassIds",
    "specIds",
    "uniqueEquipped",
)
_CRAFTED_SELECTION_STAT_KEYS = frozenset(
    {
        "crit",
        "crit_rating",
        "critical_strike",
        "critical_strike_rating",
        "haste",
        "haste_rating",
        "mastery",
        "mastery_rating",
        "versatility",
        "versatility_rating",
    }
)
_CATALOG_ARMOR_SLOTS = frozenset(
    {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}
)
_CATALOG_WEAPON_SLOTS = frozenset({"main_hand", "off_hand"})


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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _hash(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    return parsed if parsed > 0 else 0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _strip_non_identity(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_non_identity(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _NON_IDENTITY_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_non_identity(item) for item in value]
    return value


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    result = []
    for item in value:
        normalized = _text(item)
        if not normalized:
            return None
        result.append(normalized)
    return sorted(
        set(result),
        key=lambda item: (
            0,
            int(item),
        )
        if item.isdigit()
        else (1, item),
    )


def _static_facts(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    result: dict[str, int | float] = {}
    for key, amount in value.items():
        normalized = _text(key)
        if (
            not normalized
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
        ):
            return None
        result[normalized] = amount
    return dict(sorted(result.items()))


def _problem(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _problem_codes(problems: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            _text(problem.get("code"))
            for problem in problems
            if _text(problem.get("code"))
        }
    )


def _canonical_progression_key(progression_state: Mapping[str, Any]) -> str:
    return _hash("progression:sha256:", progression_state)


def catalog_browse_variant_key(
    catalog_revision: str,
    item_id: str,
    progression_state: Mapping[str, Any],
    variant_shape_key: str = "",
) -> str:
    """Derive a Catalog-bound BrowseVariant identity after Catalog hashing."""

    identity = {
        "catalogRevision": _text(catalog_revision),
        "itemId": _text(item_id),
        "progressionState": _canonical(progression_state),
    }
    if _text(variant_shape_key):
        identity["variantShapeKey"] = _text(variant_shape_key)
    return _hash(
        "browse-variant:sha256:",
        identity,
    )


def _variant_shape_key(
    item_level: int,
    bonus_ids: Iterable[str],
    static_facts: Mapping[str, int | float],
) -> str:
    return _hash(
        "variant-shape:sha256:",
        {
            "itemLevel": item_level,
            "bonusIds": list(bonus_ids),
            "staticFacts": _canonical(static_facts),
        },
    )


def _item_payload_section(
    payload: Mapping[str, Any],
    keys: Iterable[str],
) -> dict[str, Any]:
    result = {}
    for key in keys:
        if key not in payload or payload[key] in (None, "", [], {}):
            continue
        value = _strip_non_identity(payload[key])
        if (
            key in {"classIds", "requiredClassIds", "specIds"}
            and isinstance(value, list)
        ):
            value = sorted(
                {_text(item) for item in value if _text(item)},
                key=lambda item: (
                    0,
                    int(item),
                )
                if item.isdigit()
                else (1, item),
            )
        result[key] = value
    return result


def _catalog_item_has_governed_equipment_type(
    row: Mapping[str, Any],
) -> bool:
    """Return whether a non-portable item has its governing type fact."""

    slot = _text(row.get("slot")).lower().replace("-", "_")
    equipment = _catalog_item_equipment(row)
    if slot in _CATALOG_ARMOR_SLOTS:
        return bool(_text(equipment.get("armorType")))
    if slot in _CATALOG_WEAPON_SLOTS:
        return bool(_text(equipment.get("weaponType")))
    return True


def _catalog_item_equipment(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project governed equipment facts from internal or official BNet payloads."""

    payload = _mapping(row.get("payload"))
    existing = _mapping(payload.get("equipment"))
    bnet = _mapping(item_type_metadata_from_payload(payload))
    raw_inventory = _mapping(payload.get("inventory_type"))
    result = {
        "armorType": (
            _text(payload.get("armorType"))
            or _text(existing.get("armorType"))
            or _text(bnet.get("armorType"))
        ),
        "inventoryType": (
            _text(payload.get("inventoryType"))
            or _text(existing.get("inventoryType"))
            or _text(raw_inventory.get("type"))
        ),
        "itemClass": (
            payload.get("itemClass")
            or existing.get("itemClass")
            or _mapping(payload.get("item_class"))
        ),
        "itemSubclass": (
            payload.get("itemSubclass")
            or existing.get("itemSubclass")
            or _mapping(payload.get("item_subclass"))
        ),
        "weaponType": (
            _text(payload.get("weaponType"))
            or _text(existing.get("weaponType"))
            or _text(bnet.get("weaponType"))
        ),
    }
    return {
        key: value
        for key, value in result.items()
        if value not in (None, "", [], {})
    }


def _source_definition(row: Mapping[str, Any]) -> dict[str, Any]:
    source = {
        "sourceType": _text(row.get("sourceType")),
        "sourceKey": _text(row.get("sourceKey")),
        "instanceId": _text(row.get("instanceId")),
        "encounterId": _text(row.get("encounterId")),
        "difficultyKey": _text(row.get("difficultyKey")),
        "seasonRevision": _text(row.get("seasonRevision")),
        "status": _text(row.get("status") or row.get("sourceStatus") or "unknown"),
    }
    canonical = {
        key: value
        for key, value in source.items()
        if value
    }
    canonical["sourceIdentity"] = _hash(
        "catalog-source:sha256:",
        canonical,
    )
    return canonical


def _catalog_identity_seed(
    *,
    schema_revision: str,
    builder_revision: str,
    season_revision: str,
    dependency_vector: Mapping[str, Any],
    source_summary: Mapping[str, Any],
    item_definitions: Iterable[Mapping[str, Any]],
    browse_variant_seeds: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    canonical_definitions = [
        {
            key: _canonical(value)
            for key, value in definition.items()
            if key != "definitionHash"
        }
        for definition in item_definitions
    ]
    canonical_definitions.sort(
        key=lambda definition: (
            _text(definition.get("itemId")),
            _canonical_bytes(definition),
        )
    )
    canonical_variant_seeds = [
        {
            key: _canonical(value)
            for key, value in variant.items()
            if key
            not in {
                "browseVariantKey",
                "progressionKey",
                "variantHash",
            }
        }
        for variant in browse_variant_seeds
    ]
    canonical_variant_seeds.sort(
        key=lambda variant: (
            _text(variant.get("itemId")),
            _canonical_bytes(variant.get("progressionState")),
            _canonical_bytes(variant),
        )
    )
    return {
        "schemaRevision": _text(schema_revision),
        "builderRevision": _text(builder_revision),
        "seasonRevision": _text(season_revision),
        "dependencyVector": _canonical(dependency_vector),
        "sourceSummary": _canonical(source_summary),
        "itemDefinitions": canonical_definitions,
        "browseVariantMembershipSeeds": canonical_variant_seeds,
    }


def _is_crafted(
    row: Mapping[str, Any],
    progression_state: Mapping[str, Any],
) -> bool:
    return (
        _text(row.get("sourceType")).lower() == "crafted"
        and (
            progression_state.get("kind") == "crafted_quality"
            or progression_state.get("originKind") == "crafted_quality"
        )
    )


def _crafted_invariant_facts(
    static_facts: Mapping[str, int | float],
) -> dict[str, int | float]:
    return {
        key: value
        for key, value in sorted(static_facts.items())
        if key.lower() not in _CRAFTED_SELECTION_STAT_KEYS
    }


def _blocked_result(
    binding: Mapping[str, Any],
    problems: list[dict[str, str]],
) -> dict[str, Any]:
    canonical_problems = sorted(
        (_canonical(problem) for problem in problems),
        key=lambda problem: (
            _text(problem.get("code")),
            _text(problem.get("path")),
            _text(problem.get("message")),
        ),
    )
    return {
        "schemaRevision": CATALOG_SCHEMA_REVISION,
        "status": "blocked",
        "seasonRevision": _text(binding.get("seasonRevision")),
        "problemCodes": _problem_codes(canonical_problems),
        "problemCount": len(canonical_problems),
        "problems": canonical_problems[:20],
    }


def build_catalog_revision(
    binding: Any,
    rows: Any,
    *,
    builder_revision: str = CATALOG_BUILDER_REVISION,
) -> dict[str, Any]:
    """Build one immutable dormant Catalog or return a blocked report."""

    active = _mapping(binding)
    source_rows = _mapping(rows)
    problems: list[dict[str, str]] = []
    season_revision = _text(active.get("seasonRevision"))
    builder = _text(builder_revision)
    gear_content_hash = _text(active.get("gearReleaseContentHash"))
    gear_schema_revision = _text(active.get("gearReleaseSchemaRevision"))
    if not builder:
        problems.append(_problem(
            "CATALOG_BUILDER_REVISION_MISSING",
            "binding.builderRevision",
            "Catalog builder revision is required.",
        ))
    if not gear_content_hash:
        problems.append(_problem(
            "CATALOG_SOURCE_CONTENT_HASH_MISSING",
            "binding.gearReleaseContentHash",
            "Sealed Gear Release content hash is required.",
        ))
    if not gear_schema_revision:
        problems.append(_problem(
            "CATALOG_SOURCE_SCHEMA_REVISION_MISSING",
            "binding.gearReleaseSchemaRevision",
            "Sealed Gear Release schema revision is required.",
        ))

    mapping_audit = audit_catalog_mapping(active, source_rows)
    if mapping_audit.get("status") != "verified":
        for code in mapping_audit.get("problemCodes") or []:
            problems.append(_problem(
                _text(code),
                "mappingAudit",
                "Phase 0 Catalog mapping contract is not verified.",
            ))

    raw_items = [
        row
        for row in source_rows.get("items") or []
        if isinstance(row, Mapping)
    ]
    raw_sources = [
        row
        for row in source_rows.get("sources") or []
        if isinstance(row, Mapping)
    ]
    raw_variants = [
        row
        for row in source_rows.get("variants") or []
        if isinstance(row, Mapping)
    ]
    type_excluded_item_ids = {
        _text(row.get("itemId") or row.get("id"))
        for row in raw_items
        if (
            _text(row.get("itemId") or row.get("id"))
            and not _catalog_item_has_governed_equipment_type(row)
        )
    }
    verified_exact_item_ids = {
        _text(row.get("itemId"))
        for row in raw_variants
        if (
            _text(row.get("rowFamily")) == "exact_instance"
            and _text(row.get("status")).lower() == "verified"
            and _text(row.get("itemId"))
        )
    }
    observed_ascendant_item_ids = {
        _text(row.get("itemId"))
        for row in raw_variants
        if (
            _text(row.get("rowFamily")) == "exact_instance"
            and _positive_int(row.get("itemLevel")) == 298
            and _text(row.get("status")).lower() == "verified"
            and _static_facts(row.get("staticStats")) is not None
            and _text(row.get("itemId"))
        )
    }
    sources_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in raw_sources:
        item_id = _text(row.get("itemId"))
        if item_id:
            sources_by_item.setdefault(item_id, []).append(
                _source_definition(row)
            )

    candidate_rows: dict[
        tuple[str, str, str],
        list[dict[str, Any]],
    ] = {}
    legacy_browse_count = 0
    type_excluded_browse_count = 0
    crafted_selection_count = 0
    exact_instance_count = 0
    exact_eligible_count = 0
    exact_excluded_count = 0
    for index, row in enumerate(raw_variants):
        if _text(row.get("rowFamily")) != "browse":
            continue
        legacy_browse_count += 1
        authority_row = dict(row)
        if _text(row.get("itemId")) in observed_ascendant_item_ids:
            authority_row["hasObservedAscendantEvidence"] = True
        resolution = resolve_legacy_browse_progression(
            active,
            authority_row,
        )
        progression_state = _mapping(resolution.get("progressionState"))
        if resolution.get("status") != "verified" or not progression_state:
            continue
        item_id = _text(row.get("itemId"))
        if item_id in type_excluded_item_ids:
            type_excluded_browse_count += 1
            continue
        item_level = _positive_int(row.get("itemLevel"))
        bonus_ids = _string_list(row.get("bonusIds"))
        facts = _static_facts(row.get("staticStats"))
        if (
            not item_id
            or not item_level
            or bonus_ids is None
            or facts is None
        ):
            continue
        if _text(row.get("status")).lower() != "verified":
            problems.append(_problem(
                "CATALOG_VARIANT_STATUS_UNVERIFIED",
                f"rows.variants[{index}].status",
                "BrowseVariant source row must be verified.",
            ))
        if row.get("blockers"):
            problems.append(_problem(
                "CATALOG_VARIANT_BLOCKERS_PRESENT",
                f"rows.variants[{index}].blockers",
                "BrowseVariant source row cannot retain blockers.",
            ))
        crafted = _is_crafted(row, progression_state)
        if crafted:
            crafted_selection_count += 1
            facts = _crafted_invariant_facts(facts)
            if not facts:
                problems.append(_problem(
                    "CATALOG_CRAFTED_INVARIANT_FACTS_MISSING",
                    f"rows.variants[{index}].staticStats",
                    "Crafted BrowseVariant requires selection-independent static facts.",
                ))
        source_variant_key = _text(
            row.get("variantKey") or row.get("variantId")
        )
        if not source_variant_key:
            problems.append(_problem(
                "CATALOG_SOURCE_VARIANT_KEY_MISSING",
                f"rows.variants[{index}].variantKey",
                "BrowseVariant migration requires a legacy source variant key.",
            ))
            continue
        progression_key = json.dumps(
            _canonical(progression_state),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        shape_key = _variant_shape_key(item_level, bonus_ids, facts)
        candidate_rows.setdefault(
            (item_id, progression_key, shape_key),
            [],
        ).append({
            "itemId": item_id,
            "progressionState": _canonical(progression_state),
            "progressionKind": _text(progression_state.get("kind")),
            "variantShapeKey": shape_key,
            "itemLevel": item_level,
            "bonusIds": bonus_ids,
            "staticFacts": facts,
            "sourceVariantKey": source_variant_key,
            "sourceType": _text(row.get("sourceType")),
            "crafted": crafted,
            "rowFamily": "browse",
            "enhancementFieldCount": 0,
            "rowIndex": index,
        })

    for index, row in enumerate(raw_variants):
        if _text(row.get("rowFamily")) != "exact_instance":
            continue
        exact_instance_count += 1
        if (
            _text(row.get("status")).lower() != "verified"
            or row.get("blockers")
        ):
            exact_excluded_count += 1
            continue
        resolution = resolve_exact_instance_progression(active, row)
        progression_state = _mapping(resolution.get("progressionState"))
        item_id = _text(row.get("itemId"))
        item_level = _positive_int(row.get("itemLevel"))
        bonus_ids = _string_list(row.get("bonusIds"))
        facts = _static_facts(row.get("staticStats"))
        source_variant_key = _text(
            row.get("variantKey") or row.get("variantId")
        )
        if (
            resolution.get("status") != "verified"
            or not progression_state
            or not item_id
            or item_id not in verified_exact_item_ids
            or not item_level
            or bonus_ids is None
            or facts is None
            or not source_variant_key
        ):
            exact_excluded_count += 1
            continue
        # ExactItemInstance rows belong to the separate exact registry. They
        # can establish governed Track Authority evidence, but never create or
        # extend a public BrowseVariant or its ItemDefinition membership.
        exact_eligible_count += 1

    normal_browse_groups: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}
    crafted_browse_groups: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}
    for (
        item_id,
        progression_key,
        _shape_key,
    ), candidates in candidate_rows.items():
        for candidate in candidates:
            if not candidate["crafted"]:
                normal_browse_groups.setdefault(
                    (item_id, progression_key),
                    [],
                ).append(candidate)
            if (
                candidate["crafted"]
            ):
                crafted_browse_groups.setdefault(
                    (item_id, progression_key),
                    [],
                ).append(candidate)
    for (item_id, _), candidates in sorted(
        normal_browse_groups.items()
    ):
        if len(candidates) > 1:
            problems.append(_problem(
                "CATALOG_VARIANT_CANONICAL_DUPLICATE",
                f"rows.variants[{item_id}]",
                "One non-crafted progression must map from exactly one verified Browse row.",
            ))
    for (item_id, _), candidates in sorted(
        crafted_browse_groups.items()
    ):
        exemplar = candidates[0]
        expected = {
            "itemLevel": exemplar["itemLevel"],
            "bonusIds": exemplar["bonusIds"],
            "staticFacts": exemplar["staticFacts"],
            "sourceType": exemplar["sourceType"],
        }
        if any(
            {
                "itemLevel": candidate["itemLevel"],
                "bonusIds": candidate["bonusIds"],
                "staticFacts": candidate["staticFacts"],
                "sourceType": candidate["sourceType"],
            }
            != expected
            for candidate in candidates[1:]
        ):
            problems.append(_problem(
                "CATALOG_CRAFTED_INVARIANT_FACT_CONFLICT",
                f"rows.variants[{item_id}]",
                "Crafted stat selections disagree on selection-independent facts.",
            ))

    variant_seeds: list[dict[str, Any]] = []
    progressions_by_item: dict[
        str,
        dict[str, dict[str, Any]],
    ] = {}
    for (item_id, progression_key, _shape_key), candidates in sorted(
        candidate_rows.items()
    ):
        exemplar = candidates[0]
        browse_candidates = [
            candidate
            for candidate in candidates
            if candidate["rowFamily"] == "browse"
        ]
        if (
            browse_candidates
            and not browse_candidates[0]["crafted"]
            and len(browse_candidates) != 1
        ):
            # The Phase 0 audit also reports this, but keep the builder
            # independently fail-closed if the audit implementation changes.
            problems.append(_problem(
                "CATALOG_VARIANT_CANONICAL_DUPLICATE",
                f"rows.variants[{item_id}]",
                "One non-crafted progression must map from exactly one legacy row.",
            ))
            continue
        invariant_shape = {
            "itemLevel": exemplar["itemLevel"],
            "bonusIds": exemplar["bonusIds"],
            "staticFacts": exemplar["staticFacts"],
        }
        if any(
            {
                "itemLevel": candidate["itemLevel"],
                "bonusIds": candidate["bonusIds"],
                "staticFacts": candidate["staticFacts"],
            }
            != invariant_shape
            for candidate in candidates[1:]
        ):
            problems.append(_problem(
                "CATALOG_CRAFTED_INVARIANT_FACT_CONFLICT",
                f"rows.variants[{item_id}]",
                "Crafted stat selections disagree on selection-independent facts.",
            ))
            continue
        source_variant_keys = sorted(
            {candidate["sourceVariantKey"] for candidate in candidates}
        )
        canonical_candidate = min(
            candidates,
            key=lambda candidate: (
                0 if candidate["rowFamily"] == "browse" else 1,
                candidate["enhancementFieldCount"],
                candidate["sourceVariantKey"],
            ),
        )
        source_type = next(
            (
                candidate["sourceType"]
                for candidate in sorted(
                    browse_candidates,
                    key=lambda candidate: candidate["sourceVariantKey"],
                )
                if candidate["sourceType"]
            ),
            "",
        )
        seed = {
            "itemId": item_id,
            "progressionState": exemplar["progressionState"],
            "progressionKind": exemplar["progressionKind"],
            "itemLevel": exemplar["itemLevel"],
            "bonusIds": exemplar["bonusIds"],
            "staticFacts": exemplar["staticFacts"],
            "sourceType": source_type,
            "sourceVariantKeys": source_variant_keys,
            "canonicalSourceVariantKey": canonical_candidate[
                "sourceVariantKey"
            ],
            "sourceFamilies": ["browse"],
            "evidenceStatus": "verified",
        }
        variant_seeds.append(seed)
        progressions_by_item.setdefault(item_id, {})[
            progression_key
        ] = exemplar["progressionState"]

    item_definitions: list[dict[str, Any]] = []
    membership_item_ids = set(progressions_by_item)
    excluded_dormant_item_count = 0
    for index, row in enumerate(raw_items):
        item_id = _text(row.get("itemId") or row.get("id"))
        slot = _text(row.get("slot"))
        if not slot and (
            row.get("hasSourceRefs") is not True
            and row.get("hasVariantRefs") is not True
        ):
            continue
        if item_id not in membership_item_ids:
            excluded_dormant_item_count += 1
            continue
        legacy_source_status = _text(row.get("sourceStatus")).lower()
        item_sources = sorted(
            {
                json.dumps(
                    source,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ): source
                for source in sources_by_item.get(item_id, [])
            }.values(),
            key=_canonical_bytes,
        )
        if not item_sources:
            problems.append(_problem(
                "CATALOG_ITEM_SOURCE_MISSING",
                f"rows.items[{index}].sources",
                "ItemDefinition requires at least one current PVE source.",
            ))
        source_status = (
            "verified"
            if (
                legacy_source_status == "verified"
                or any(
                    _text(source.get("status")).lower() == "verified"
                    for source in item_sources
                )
            )
            else legacy_source_status or "unknown"
        )
        if source_status != "verified":
            problems.append(_problem(
                "CATALOG_ITEM_SOURCE_STATUS_UNVERIFIED",
                f"rows.items[{index}].sourceStatus",
                "ItemDefinition source status must be verified.",
            ))
        payload = _mapping(row.get("payload"))
        definition = {
            "itemId": item_id,
            "name": _text(row.get("name")),
            "slot": slot,
            "itemLevel": _positive_int(row.get("itemLevel")),
            "sourceStatus": source_status,
            "legacySourceStatus": legacy_source_status or "unknown",
            "media": _item_payload_section(payload, _ITEM_MEDIA_KEYS),
            "equipment": _catalog_item_equipment(row),
            "restrictions": _item_payload_section(
                payload,
                _ITEM_RESTRICTION_KEYS,
            ),
            "sources": item_sources,
            "availableProgressions": sorted(
                (
                    _canonical(progression)
                    for progression in progressions_by_item.get(
                        item_id,
                        {},
                    ).values()
                ),
                key=_canonical_bytes,
            ),
        }
        definition["definitionHash"] = _hash(
            "item-definition:sha256:",
            definition,
        )
        item_definitions.append(definition)

    item_definitions.sort(key=lambda row: _text(row.get("itemId")))
    variant_seeds.sort(
        key=lambda row: (
            _text(row.get("itemId")),
            _canonical_bytes(row.get("progressionState")),
        )
    )
    if problems:
        return _blocked_result(active, problems)

    dependency_vector = _canonical(
        _mapping(active.get("dependencyVector"))
    )
    source_summary = _canonical({
        "gearReleaseContentHash": gear_content_hash,
        "gearReleaseSchemaRevision": gear_schema_revision,
        "source": _strip_non_identity(
            _mapping(active.get("sourceSummary"))
        ),
    })
    identity_seed = _catalog_identity_seed(
        schema_revision=CATALOG_SCHEMA_REVISION,
        builder_revision=builder,
        season_revision=season_revision,
        dependency_vector=dependency_vector,
        source_summary=source_summary,
        item_definitions=item_definitions,
        browse_variant_seeds=variant_seeds,
    )
    catalog_revision = _hash("gear-catalog:sha256:", identity_seed)

    browse_variants: list[dict[str, Any]] = []
    for seed in variant_seeds:
        variant = {
            "browseVariantKey": catalog_browse_variant_key(
                catalog_revision,
                seed["itemId"],
                seed["progressionState"],
            ),
            "progressionKey": _canonical_progression_key(
                seed["progressionState"]
            ),
            **seed,
        }
        variant["variantHash"] = _hash(
            "browse-variant-row:sha256:",
            variant,
        )
        browse_variants.append(variant)

    content_summary = {
        "itemDefinitionCount": len(item_definitions),
        "legacyBrowseVariantRowCount": legacy_browse_count,
        "exactInstanceRowCount": exact_instance_count,
        "exactEligibleRowCount": exact_eligible_count,
        "exactExcludedRowCount": exact_excluded_count,
        "exactDerivedVariantCount": 0,
        "browseVariantCount": len(browse_variants),
        "craftedEnhancementSelectionRowCount": crafted_selection_count,
        "collapsedCraftedVariantRowCount": max(
            0,
            crafted_selection_count
            - sum(
                1
                for variant in browse_variants
                if (
                    variant.get("progressionState", {}).get("kind")
                    == "crafted_quality"
                    or variant.get("progressionState", {}).get("originKind")
                    == "crafted_quality"
                )
            ),
        ),
        "excludedDormantItemCount": excluded_dormant_item_count,
        "typeExcludedItemCount": len(type_excluded_item_ids),
        "typeExcludedBrowseRowCount": type_excluded_browse_count,
    }
    return {
        "schemaRevision": CATALOG_SCHEMA_REVISION,
        "status": "verified",
        "catalogRevision": catalog_revision,
        "builderRevision": builder,
        "seasonRevision": season_revision,
        "dependencyVector": dependency_vector,
        "sourceSummary": source_summary,
        "contentSummary": content_summary,
        "itemDefinitions": item_definitions,
        "browseVariants": browse_variants,
        "provenance": {
            "sourceGearReleaseId": _text(active.get("gearReleaseId")),
            "sourceManifestRevision": _text(active.get("manifestRevision")),
        },
        "problemCodes": [],
        "problems": [],
    }


def verify_catalog_revision(catalog: Any) -> list[str]:
    """Return stable problem codes for one fully materialized Catalog."""

    if not isinstance(catalog, Mapping):
        return ["CATALOG_RECORD_MALFORMED"]
    problems: list[str] = []
    if catalog.get("status") != "verified":
        problems.append("CATALOG_STATUS_UNVERIFIED")
    catalog_revision = _text(catalog.get("catalogRevision"))
    if not CATALOG_REVISION_PATTERN.fullmatch(catalog_revision):
        problems.append("CATALOG_REVISION_INVALID")

    definitions = [
        dict(row)
        for row in catalog.get("itemDefinitions") or []
        if isinstance(row, Mapping)
    ]
    variants = [
        dict(row)
        for row in catalog.get("browseVariants") or []
        if isinstance(row, Mapping)
    ]
    if len(definitions) != len(catalog.get("itemDefinitions") or []):
        problems.append("CATALOG_ITEM_DEFINITION_MALFORMED")
    if len(variants) != len(catalog.get("browseVariants") or []):
        problems.append("CATALOG_BROWSE_VARIANT_MALFORMED")

    expected_revision = _hash(
        "gear-catalog:sha256:",
        _catalog_identity_seed(
            schema_revision=_text(catalog.get("schemaRevision")),
            builder_revision=_text(catalog.get("builderRevision")),
            season_revision=_text(catalog.get("seasonRevision")),
            dependency_vector=_mapping(catalog.get("dependencyVector")),
            source_summary=_mapping(catalog.get("sourceSummary")),
            item_definitions=definitions,
            browse_variant_seeds=variants,
        ),
    )
    if catalog_revision and expected_revision != catalog_revision:
        problems.append("CATALOG_REVISION_MISMATCH")

    seen_items: set[str] = set()
    for definition in definitions:
        item_id = _text(definition.get("itemId"))
        if not item_id or item_id in seen_items:
            problems.append("CATALOG_ITEM_ID_DUPLICATE_OR_MISSING")
        seen_items.add(item_id)
        expected_hash = _hash(
            "item-definition:sha256:",
            {
                key: value
                for key, value in definition.items()
                if key != "definitionHash"
            },
        )
        if _text(definition.get("definitionHash")) != expected_hash:
            problems.append("CATALOG_ITEM_DEFINITION_HASH_MISMATCH")

    seen_variants: set[str] = set()
    seen_shapes: set[tuple[str, str, str]] = set()
    schema_revision = _text(catalog.get("schemaRevision"))
    if schema_revision not in {
        LEGACY_CATALOG_SCHEMA_REVISION,
        VARIANT_SHAPE_CATALOG_SCHEMA_REVISION,
        CATALOG_SCHEMA_REVISION,
    }:
        problems.append("CATALOG_SCHEMA_REVISION_UNSUPPORTED")
    for variant in variants:
        item_id = _text(variant.get("itemId"))
        progression = _mapping(variant.get("progressionState"))
        key = _text(variant.get("browseVariantKey"))
        variant_shape_key = _text(variant.get("variantShapeKey"))
        if not BROWSE_VARIANT_KEY_PATTERN.fullmatch(key):
            problems.append("CATALOG_BROWSE_VARIANT_KEY_INVALID")
        if schema_revision == VARIANT_SHAPE_CATALOG_SCHEMA_REVISION:
            expected_shape_key = _variant_shape_key(
                _positive_int(variant.get("itemLevel")),
                _string_list(variant.get("bonusIds")) or [],
                _static_facts(variant.get("staticFacts")) or {},
            )
            if (
                not VARIANT_SHAPE_KEY_PATTERN.fullmatch(variant_shape_key)
                or variant_shape_key != expected_shape_key
            ):
                problems.append("CATALOG_VARIANT_SHAPE_KEY_MISMATCH")
        elif schema_revision == CATALOG_SCHEMA_REVISION and variant_shape_key:
            problems.append("CATALOG_VARIANT_SHAPE_KEY_UNEXPECTED")
        expected_key = catalog_browse_variant_key(
            catalog_revision,
            item_id,
            progression,
            (
                variant_shape_key
                if schema_revision == VARIANT_SHAPE_CATALOG_SCHEMA_REVISION
                else ""
            ),
        )
        if key != expected_key:
            problems.append("CATALOG_BROWSE_VARIANT_KEY_MISMATCH")
        if key in seen_variants:
            problems.append("CATALOG_BROWSE_VARIANT_KEY_DUPLICATE")
        seen_variants.add(key)
        shape_identity = (
            item_id,
            _canonical_progression_key(progression),
            (
                variant_shape_key
                if schema_revision == VARIANT_SHAPE_CATALOG_SCHEMA_REVISION
                else ""
            ),
        )
        if shape_identity in seen_shapes:
            problems.append("CATALOG_BROWSE_VARIANT_SHAPE_DUPLICATE")
        seen_shapes.add(shape_identity)
        if item_id not in seen_items:
            problems.append("CATALOG_BROWSE_VARIANT_ITEM_ORPHAN")
        expected_hash = _hash(
            "browse-variant-row:sha256:",
            {
                key_name: value
                for key_name, value in variant.items()
                if key_name != "variantHash"
            },
        )
        if _text(variant.get("variantHash")) != expected_hash:
            problems.append("CATALOG_BROWSE_VARIANT_HASH_MISMATCH")

    summary = _mapping(catalog.get("contentSummary"))
    if (
        _positive_int(summary.get("itemDefinitionCount"))
        != len(definitions)
        or _positive_int(summary.get("browseVariantCount"))
        != len(variants)
    ):
        problems.append("CATALOG_CONTENT_SUMMARY_MISMATCH")
    return sorted(set(problems))


__all__ = (
    "BROWSE_VARIANT_KEY_PATTERN",
    "CATALOG_BUILDER_REVISION",
    "CATALOG_REVISION_PATTERN",
    "CATALOG_SCHEMA_REVISION",
    "build_catalog_revision",
    "catalog_browse_variant_key",
    "verify_catalog_revision",
)
