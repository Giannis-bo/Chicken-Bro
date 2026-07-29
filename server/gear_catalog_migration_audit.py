#!/usr/bin/env python3
"""Pure, deterministic Phase 0 audit policy for the gear catalog migration.

This module owns no database, filesystem, environment, network, clock, process,
or runtime behavior. Callers provide already-bounded observations explicitly.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

try:
    from server.gear_track_authority import (
        resolve_exact_instance_progression,
        resolve_legacy_browse_progression,
        track_authority_for_binding,
    )
except ImportError:
    from gear_track_authority import (
        resolve_exact_instance_progression,
        resolve_legacy_browse_progression,
        track_authority_for_binding,
    )

AUDIT_SCHEMA_REVISION = "equipment-simulator-catalog-migration-audit-v2"
AUDIT_REPORT_PREFIX = "catalog-migration-audit:sha256:"
_STATUS_RANK = {"verified": 0, "partial": 1, "blocked": 2}
_NON_IDENTITY_KEYS = {
    "checkedAt",
    "createdAt",
    "databaseRowId",
    "displayLabel",
    "displayName",
    "observedAt",
    "rowId",
    "updatedAt",
}
_SENSITIVE_KEYS = {
    "character",
    "characterName",
    "databaseUrl",
    "profile",
    "rawString",
    "realm",
    "token",
    "userId",
}
_RESOURCE_FIELDS = (
    "databaseRelationsBytes",
    "activeMaterializationBytes",
    "rollbackMaterializationBytes",
    "diagnosticBytesObserved",
    "filesystemTotalBytes",
    "filesystemUsedBytes",
    "filesystemFreeBytes",
    "filesystemUsedPercent",
)
_PROBLEM_SAMPLE_LIMIT = 20


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


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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


def _non_negative_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)) or value < 0:
        return None
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _row_value(row: Mapping[str, Any], *keys: str) -> Any:
    payload = _mapping(row.get("payload"))
    value = _first(row, *keys)
    return value if value is not None else _first(payload, *keys)


def _status(values: Iterable[Any], *, default: str = "verified") -> str:
    statuses = [
        _text(value)
        for value in values
        if _text(value) in _STATUS_RANK
    ]
    return max(statuses, key=lambda value: _STATUS_RANK[value]) if statuses else default


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


def _problem_counts(problems: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for problem in problems:
        code = _text(problem.get("code"))
        if code:
            counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _problem_samples(problems: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    canonical = [
        _canonical(problem)
        for problem in problems
        if isinstance(problem, Mapping)
    ]
    canonical.sort(
        key=lambda problem: (
            _text(problem.get("code")),
            _text(problem.get("path")),
            _text(problem.get("message")),
        )
    )
    return canonical[:_PROBLEM_SAMPLE_LIMIT]


def _without_non_identity_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_non_identity_fields(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _NON_IDENTITY_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_without_non_identity_fields(item) for item in value]
    return value


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, (list, tuple)):
        return None
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        result.append(item.strip())
    return result


def _static_stats(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    result: dict[str, int | float] = {}
    for key, amount in value.items():
        normalized_key = _text(key)
        if not normalized_key or isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return None
        result[normalized_key] = amount
    return result


def _crafted_stats_choice(row: Mapping[str, Any]) -> tuple[str, ...] | None:
    simc_options = _mapping(row.get("simcOptions"))
    value = simc_options.get("crafted_stats")
    if isinstance(value, str):
        normalized = value.strip()
        return (normalized,) if normalized else None
    if isinstance(value, (list, tuple)):
        normalized = _string_list(value)
        return tuple(normalized) if normalized else None
    return None


def _canonical_progression_key(
    item_id: str,
    progression_state: Mapping[str, Any],
) -> tuple[str, str]:
    return (
        item_id,
        json.dumps(
            _canonical(progression_state),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


def _is_crafted_progression(
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


def audit_catalog_mapping(binding: Any, rows: Any) -> dict[str, Any]:
    """Classify whether one authoritative release can become a Catalog."""

    active_binding = _mapping(binding)
    source = _mapping(rows)
    variant_summary = _mapping(source.get("variantSummary"))
    items = [row for row in source.get("items") or [] if isinstance(row, Mapping)]
    variants = [row for row in source.get("variants") or [] if isinstance(row, Mapping)]
    options = [row for row in source.get("options") or [] if isinstance(row, Mapping)]
    problems: list[dict[str, str]] = []

    if (
        not _text(active_binding.get("manifestRevision"))
        and _text(active_binding.get("bindingMode"))
        != "validated_release_pair"
    ):
        problems.append(_problem(
            "CATALOG_ACTIVE_MANIFEST_MISSING",
            "binding.manifestRevision",
            "The active Manifest revision is required.",
        ))
    if not _text(active_binding.get("gearReleaseId")):
        problems.append(_problem(
            "CATALOG_ACTIVE_RELEASE_MISSING",
            "binding.gearReleaseId",
            "The active Gear Release identity is required.",
        ))

    variant_ref_item_ids = {
        _text(_row_value(row, "itemId"))
        for row in variants
        if _text(_row_value(row, "itemId"))
    }
    mapped_item_ids: set[str] = set()
    seen_item_ids: set[str] = set()
    excluded_non_catalog_item_count = 0
    for index, row in enumerate(items):
        item_id = _text(_row_value(row, "itemId", "id"))
        slot = _text(_row_value(row, "slot"))
        has_source_refs = row.get("hasSourceRefs") is True
        has_variant_refs = (
            row.get("hasVariantRefs") is True
            or item_id in variant_ref_item_ids
        )
        if not item_id:
            problems.append(_problem(
                "CATALOG_ITEM_ID_MISSING",
                f"rows.items[{index}].itemId",
                "ItemDefinition mapping requires itemId.",
            ))
        elif item_id in seen_item_ids:
            problems.append(_problem(
                "CATALOG_ITEM_ID_DUPLICATE",
                f"rows.items[{index}].itemId",
                "ItemDefinition mapping requires one active row per itemId.",
            ))
        if not slot:
            if item_id and not has_source_refs and not has_variant_refs:
                excluded_non_catalog_item_count += 1
            else:
                problems.append(_problem(
                    "CATALOG_ITEM_SLOT_MISSING",
                    f"rows.items[{index}].slot",
                    "ItemDefinition mapping requires a canonical slot.",
                ))
        if item_id and slot and item_id not in seen_item_ids:
            mapped_item_ids.add(item_id)
        if item_id:
            seen_item_ids.add(item_id)

    track_authority = track_authority_for_binding(active_binding)
    if track_authority.get("status") != "verified":
        for authority_problem in track_authority.get("problems") or []:
            if not isinstance(authority_problem, Mapping):
                continue
            problems.append(_problem(
                _text(authority_problem.get("code"))
                or "TRACK_AUTHORITY_BINDING_UNSUPPORTED",
                "binding.trackAuthority",
                _text(authority_problem.get("message"))
                or "Track Authority binding is unsupported.",
            ))

    observed_ascendant_item_ids = {
        _text(value)
        for value in variant_summary.get(
            "observedAscendantItemIds"
        ) or []
        if _text(value)
    }
    observed_ascendant_item_ids.update({
        _text(_row_value(row, "itemId"))
        for row in variants
        if _text(row.get("rowFamily")) == "exact_instance"
        and _positive_int(_row_value(row, "itemLevel", "ilevel")) == 298
        and _text(row.get("status")) == "verified"
        and _static_stats(_row_value(row, "staticStats", "itemStats")) is not None
        and _text(_row_value(row, "itemId"))
    })
    variant_candidates: dict[tuple[str, str], dict[str, Any]] = {}
    legacy_browse_variant_total = 0
    crafted_enhancement_selection_row_count = 0
    summarized_exact_count = _positive_int(
        variant_summary.get("exactInstanceRowCount")
    )
    excluded_exact_instance_count = summarized_exact_count
    excluded_placeholder_variant_count = 0
    excluded_reference_variant_count = 0
    progression_counts = {
        "upgrade_track": {
            "legacyRowCount": 0,
            "canonicalCandidateCount": 0,
            "mappedCandidateCount": 0,
        },
        "crafted_quality": {
            "legacyRowCount": 0,
            "canonicalCandidateCount": 0,
            "mappedCandidateCount": 0,
        },
        "ascendant": {
            "legacyRowCount": 0,
            "canonicalCandidateCount": 0,
            "mappedCandidateCount": 0,
            "craftedLegacyRowCount": 0,
            "craftedCanonicalCandidateCount": 0,
            "craftedMappedCandidateCount": 0,
        },
    }
    for index, row in enumerate(variants):
        row_family = _text(row.get("rowFamily"))
        if row_family == "exact_instance":
            if not summarized_exact_count:
                excluded_exact_instance_count += 1
            continue
        if row_family == "placeholder":
            excluded_placeholder_variant_count += 1
            continue
        if row_family == "reference":
            excluded_reference_variant_count += 1
            continue
        if row_family != "browse":
            problems.append(_problem(
                "CATALOG_VARIANT_FAMILY_UNCLASSIFIED",
                f"rows.variants[{index}].rowFamily",
                "Legacy variant must be classified before Catalog mapping.",
            ))
            continue
        legacy_browse_variant_total += 1
        item_id = _text(_row_value(row, "itemId"))
        item_level = _positive_int(_row_value(row, "itemLevel", "ilevel"))
        bonus_ids = _string_list(_row_value(row, "bonusIds"))
        static_stats = _static_stats(_row_value(row, "staticStats", "itemStats"))
        row_problems: list[dict[str, str]] = []
        if not item_id:
            row_problems.append(_problem(
                "CATALOG_VARIANT_ITEM_ID_MISSING",
                f"rows.variants[{index}].itemId",
                "BrowseVariant mapping requires itemId.",
            ))
        elif item_id not in mapped_item_ids:
            row_problems.append(_problem(
                "CATALOG_VARIANT_ITEM_ORPHAN",
                f"rows.variants[{index}].itemId",
                "BrowseVariant must reference a mapped ItemDefinition.",
            ))
        if not item_level:
            row_problems.append(_problem(
                "CATALOG_VARIANT_ILEVEL_MISSING",
                f"rows.variants[{index}].itemLevel",
                "BrowseVariant mapping requires a positive item level.",
            ))
        if bonus_ids is None:
            row_problems.append(_problem(
                "CATALOG_VARIANT_BONUS_IDS_MALFORMED",
                f"rows.variants[{index}].bonusIds",
                "BrowseVariant bonus IDs must be an explicit string array.",
            ))
        if static_stats is None:
            row_problems.append(_problem(
                "CATALOG_VARIANT_STATIC_STATS_MISSING",
                f"rows.variants[{index}].staticStats",
                "BrowseVariant mapping requires verified static stats.",
            ))

        progression_result: Mapping[str, Any] = {}
        progression_state: Mapping[str, Any] = {}
        if track_authority.get("status") == "verified":
            authority_row = dict(row)
            if item_id in observed_ascendant_item_ids:
                authority_row["hasObservedAscendantEvidence"] = True
            progression_result = resolve_legacy_browse_progression(
                active_binding,
                authority_row,
            )
            progression_state = _mapping(
                progression_result.get("progressionState")
            )
            if progression_result.get("status") != "verified":
                for authority_problem in progression_result.get("problems") or []:
                    if not isinstance(authority_problem, Mapping):
                        continue
                    row_problems.append(_problem(
                        _text(authority_problem.get("code"))
                        or "TRACK_AUTHORITY_ROW_MALFORMED",
                        f"rows.variants[{index}].progressionState",
                        _text(authority_problem.get("message"))
                        or "Track Authority could not resolve this Browse row.",
                    ))

        problems.extend(row_problems)
        if not item_id or not progression_state:
            continue

        progression_kind = _text(progression_state.get("kind"))
        is_crafted = _is_crafted_progression(row, progression_state)
        if progression_kind in progression_counts:
            progression_counts[progression_kind]["legacyRowCount"] += 1
            if progression_kind == "ascendant" and is_crafted:
                progression_counts["ascendant"]["craftedLegacyRowCount"] += 1

        candidate_key = _canonical_progression_key(item_id, progression_state)
        candidate = variant_candidates.setdefault(candidate_key, {
            "itemId": item_id,
            "progressionState": _canonical(progression_state),
            "progressionKind": progression_kind,
            "isCrafted": is_crafted,
            "rowIndexes": [],
            "valid": True,
            "craftedStatsChoices": set(),
        })
        candidate["rowIndexes"].append(index)
        if row_problems:
            candidate["valid"] = False

        if is_crafted:
            crafted_enhancement_selection_row_count += 1
            crafted_stats_choice = _crafted_stats_choice(row)
            if crafted_stats_choice is None:
                candidate["valid"] = False
            elif crafted_stats_choice in candidate["craftedStatsChoices"]:
                problems.append(_problem(
                    "CATALOG_CRAFTED_STATS_DUPLICATE",
                    f"rows.variants[{index}].simcOptions.crafted_stats",
                    "One canonical crafted BrowseVariant cannot repeat the same crafted-stat selection.",
                ))
                candidate["valid"] = False
            else:
                candidate["craftedStatsChoices"].add(crafted_stats_choice)

    mapped_variant_count = 0
    for candidate_key, candidate in sorted(variant_candidates.items()):
        if not candidate["isCrafted"] and len(candidate["rowIndexes"]) != 1:
            problems.append(_problem(
                "CATALOG_VARIANT_CANONICAL_DUPLICATE",
                f"rows.variants[{candidate['itemId']}:{candidate_key[1]}]",
                "One non-crafted canonical BrowseVariant must map from exactly one legacy row.",
            ))
            candidate["valid"] = False

        progression_kind = candidate["progressionKind"]
        if progression_kind in progression_counts:
            progression_counts[progression_kind]["canonicalCandidateCount"] += 1
            if progression_kind == "ascendant" and candidate["isCrafted"]:
                progression_counts["ascendant"]["craftedCanonicalCandidateCount"] += 1
        if candidate["valid"]:
            mapped_variant_count += 1
            if progression_kind in progression_counts:
                progression_counts[progression_kind]["mappedCandidateCount"] += 1
                if progression_kind == "ascendant" and candidate["isCrafted"]:
                    progression_counts["ascendant"]["craftedMappedCandidateCount"] += 1

    canonical_browse_variant_total = len(variant_candidates)
    crafted_canonical_candidate_count = sum(
        1 for candidate in variant_candidates.values()
        if candidate["isCrafted"]
    )
    collapsed_crafted_variant_row_count = max(
        0,
        crafted_enhancement_selection_row_count - crafted_canonical_candidate_count,
    )

    mapped_option_count = 0
    seen_option_keys: set[str] = set()
    for index, row in enumerate(options):
        option_id = _text(_row_value(row, "optionId", "id"))
        option_key = _text(_row_value(row, "optionKey"))
        option_type = _text(_row_value(row, "optionType"))
        if not option_id:
            problems.append(_problem(
                "CATALOG_OPTION_ID_MISSING",
                f"rows.options[{index}].optionId",
                "Enhancement option mapping requires optionId.",
            ))
        if not option_key:
            problems.append(_problem(
                "CATALOG_OPTION_KEY_MISSING",
                f"rows.options[{index}].optionKey",
                "Enhancement option mapping requires optionKey.",
            ))
        elif option_key in seen_option_keys:
            problems.append(_problem(
                "CATALOG_OPTION_KEY_DUPLICATE",
                f"rows.options[{index}].optionKey",
                "Enhancement option keys must be unique.",
            ))
        if not option_type:
            problems.append(_problem(
                "CATALOG_OPTION_TYPE_MISSING",
                f"rows.options[{index}].optionType",
                "Enhancement option mapping requires optionType.",
            ))
        if option_id and option_key and option_type and option_key not in seen_option_keys:
            mapped_option_count += 1
        if option_key:
            seen_option_keys.add(option_key)

    status = "blocked" if problems else "verified"
    materialized_exact_count = sum(
        _text(row.get("rowFamily")) == "exact_instance"
        for row in variants
    )
    total_variant_count = (
        len(variants)
        - materialized_exact_count
        + summarized_exact_count
        if summarized_exact_count
        else len(variants)
    )
    return {
        "schemaRevision": "gear-catalog-mapping-audit-v2",
        "status": status,
        "manifestRevision": _text(active_binding.get("manifestRevision")),
        "gearReleaseId": _text(active_binding.get("gearReleaseId")),
        "trackAuthority": track_authority,
        "itemTotal": len(items),
        "mappedItemCount": len(mapped_item_ids),
        "excludedNonCatalogItemCount": excluded_non_catalog_item_count,
        "variantTotal": total_variant_count,
        "browseVariantTotal": legacy_browse_variant_total,
        "legacyBrowseVariantTotal": legacy_browse_variant_total,
        "canonicalBrowseVariantTotal": canonical_browse_variant_total,
        "mappedBrowseVariantCount": mapped_variant_count,
        "mappedVariantCount": mapped_variant_count,
        "craftedEnhancementSelectionRowCount": (
            crafted_enhancement_selection_row_count
        ),
        "collapsedCraftedVariantRowCount": collapsed_crafted_variant_row_count,
        "progressionCounts": progression_counts,
        "excludedLowerRankCount": 0,
        "excludedExactInstanceCount": excluded_exact_instance_count,
        "excludedPlaceholderVariantCount": excluded_placeholder_variant_count,
        "excludedReferenceVariantCount": excluded_reference_variant_count,
        "optionTotal": len(options),
        "mappedOptionCount": mapped_option_count,
        "problemCodes": _problem_codes(problems),
        "problemCounts": _problem_counts(problems),
        "problems": _problem_samples(problems),
    }


def project_template_exact_instances(
    binding: Any,
    template_rows: Any,
    catalog_rows: Any,
) -> list[dict[str, Any]]:
    """Join sealed community Intent to one verified exact catalog variant."""

    variants_by_identity: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    catalog = catalog_rows if isinstance(catalog_rows, Mapping) else {}
    for variant in catalog.get("variants") or []:
        if not isinstance(variant, Mapping):
            continue
        key = (_text(variant.get("itemId")), _text(variant.get("variantKey")))
        if all(key):
            variants_by_identity.setdefault(key, []).append(variant)

    projected: list[dict[str, Any]] = []
    for template in template_rows or []:
        if not isinstance(template, Mapping):
            continue
        template_copy = copy.deepcopy(dict(template))
        items = template_copy.get("gearItems")
        if not isinstance(items, list):
            projected.append(template_copy)
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = _text(item.get("itemId"))
            variant_key = _text(item.get("variantKey"))
            if not item_id or not variant_key:
                continue
            candidates = variants_by_identity.get((item_id, variant_key), [])
            if len(candidates) != 1:
                item["exactProgressionProblems"] = [_problem(
                    "TEMPLATE_EXACT_VARIANT_UNAVAILABLE",
                    "variantKey",
                    "Sealed community Intent must resolve to exactly one catalog variant.",
                )]
                continue
            variant = candidates[0]
            observed_item_level = _positive_int(item.get("observedItemLevel"))
            exact_item_level = _positive_int(variant.get("itemLevel"))
            if (
                observed_item_level
                and observed_item_level != exact_item_level
            ):
                item["exactProgressionProblems"] = [_problem(
                    "TEMPLATE_EXACT_ILEVEL_MISMATCH",
                    "observedItemLevel",
                    "Sealed observed item level does not match the exact catalog variant.",
                )]
                continue
            item["ilevel"] = exact_item_level
            item["bonusIds"] = list(variant.get("bonusIds") or [])
            resolved = resolve_exact_instance_progression(binding, variant)
            if resolved.get("status") != "verified":
                item["exactProgressionProblems"] = [
                    dict(problem)
                    for problem in resolved.get("problems") or []
                    if isinstance(problem, Mapping)
                ]
                continue
            progression = dict(resolved["progressionState"])
            item["progressionState"] = progression
            item["trackKey"] = _text(progression.get("trackKey"))
            if progression.get("kind") == "upgrade_track":
                item["rank"] = _positive_int(progression.get("rank"))
            else:
                item.pop("rank", None)
        projected.append(template_copy)
    return projected


def _template_item_state(item: Any, path: str) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(item, Mapping):
        return "blocked", [_problem(
            "TEMPLATE_EXACT_ITEM_MALFORMED",
            path,
            "Exact item input must be an object.",
        )]
    problems: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    for problem in item.get("exactProgressionProblems") or []:
        if isinstance(problem, Mapping) and _text(problem.get("code")):
            problems.append(_problem(
                _text(problem.get("code")),
                path,
                _text(problem.get("message"))
                or "Exact progression authority rejected the item.",
            ))
    if not _text(item.get("itemId")):
        problems.append(_problem(
            "TEMPLATE_EXACT_ITEM_ID_MISSING",
            f"{path}.itemId",
            "Exact item identity requires itemId.",
        ))

    if "bonusIds" not in item:
        missing.append(_problem(
            "TEMPLATE_EXACT_BONUS_IDS_MISSING",
            f"{path}.bonusIds",
            "Exact item identity requires an explicit bonus ID array.",
        ))
    elif _string_list(item.get("bonusIds")) is None:
        problems.append(_problem(
            "TEMPLATE_EXACT_BONUS_IDS_MALFORMED",
            f"{path}.bonusIds",
            "Exact item bonus IDs must be a string array.",
        ))

    progression = item.get("progressionState")
    if problems and not isinstance(progression, Mapping):
        pass
    elif isinstance(progression, Mapping):
        kind = _text(progression.get("kind"))
        track_key = _text(progression.get("trackKey"))
        rank = _positive_int(progression.get("rank"))
        if kind == "upgrade_track":
            if not track_key or not rank:
                missing.append(_problem(
                    "TEMPLATE_EXACT_TRACK_RANK_MISSING",
                    path,
                    "Upgrade-track exact identity requires trackKey and positive rank.",
                ))
        elif kind in {"crafted_quality", "ascendant"}:
            if not track_key:
                missing.append(_problem(
                    "TEMPLATE_EXACT_TRACK_MISSING",
                    path,
                    "Crafted and Ascendant exact identity requires trackKey.",
                ))
            if _positive_int(item.get("rank")):
                problems.append(_problem(
                    "TEMPLATE_EXACT_RANK_FORBIDDEN",
                    path,
                    "Crafted and Ascendant exact identity must not carry rank.",
                ))
        else:
            problems.append(_problem(
                "TEMPLATE_EXACT_PROGRESSION_MALFORMED",
                path,
                "Exact item progressionState has an unsupported kind.",
            ))
    else:
        track_key = _text(item.get("trackKey"))
        rank = _positive_int(item.get("rank"))
        if not track_key or not rank:
            missing.append(_problem(
                "TEMPLATE_EXACT_TRACK_RANK_MISSING",
                path,
                "Exact item identity requires both trackKey and positive rank.",
            ))
    if not _positive_int(_first(item, "ilevel", "itemLevel")):
        missing.append(_problem(
            "TEMPLATE_EXACT_ILEVEL_MISSING",
            f"{path}.ilevel",
            "Exact item identity requires a positive item level.",
        ))

    list_fields = (
        ("gemIds", "TEMPLATE_EXACT_GEM_IDS_MALFORMED"),
        ("craftedStats", "TEMPLATE_EXACT_CRAFTED_STATS_MALFORMED"),
        ("embellishmentIds", "TEMPLATE_EXACT_EMBELLISHMENT_IDS_MALFORMED"),
    )
    for field, code in list_fields:
        if field in item and _string_list(item.get(field)) is None:
            problems.append(_problem(
                code,
                f"{path}.{field}",
                f"Explicit {field} must be a string array.",
            ))
    if "enchantId" in item and not isinstance(item.get("enchantId"), str):
        problems.append(_problem(
            "TEMPLATE_EXACT_ENCHANT_ID_MALFORMED",
            f"{path}.enchantId",
            "Explicit enchantId must be a string.",
        ))

    if problems:
        return "blocked", [*problems, *missing]
    if missing:
        return "partial", missing
    return "verified", []


def _template_category(rows: Any, category: str) -> dict[str, Any]:
    templates = [row for row in rows or [] if isinstance(row, Mapping)]
    exact_count = 0
    partial_count = 0
    blocked_count = 0
    problems: list[dict[str, str]] = []
    sample_hashes: set[str] = set()
    required_category_missing = category == "community" and not templates
    if required_category_missing:
        problems.append(_problem(
            "TEMPLATE_EXACT_COMMUNITY_MISSING",
            "community",
            "The active Manifest must expose at least one community gear template.",
        ))
    for index, template in enumerate(templates):
        sample_hashes.add(
            "sha256:" + _sha256(_without_non_identity_fields(template))
        )
        gear_items = template.get("gearItems")
        if not isinstance(gear_items, list) or not gear_items:
            blocked_count += 1
            problems.append(_problem(
                "TEMPLATE_EXACT_GEAR_ITEMS_MISSING",
                f"{category}[{index}].gearItems",
                "A gear template must contain at least one item.",
            ))
            continue
        item_results = [
            _template_item_state(item, f"{category}[{index}].gearItems[{item_index}]")
            for item_index, item in enumerate(gear_items)
        ]
        template_status = _status(result[0] for result in item_results)
        for _, item_problems in item_results:
            problems.extend(item_problems)
        if template_status == "verified":
            exact_count += 1
        elif template_status == "partial":
            partial_count += 1
        else:
            blocked_count += 1
    category_status = (
        "blocked" if blocked_count or required_category_missing
        else "partial" if partial_count
        else "verified"
    )
    return {
        "status": category_status,
        "total": len(templates),
        "exactCount": exact_count,
        "partialCount": partial_count,
        "blockedCount": blocked_count,
        "sampleHashes": sorted(sample_hashes)[:20],
        "problemCodes": _problem_codes(problems),
        "problemCounts": _problem_counts(problems),
        "problems": _problem_samples(problems),
    }


def audit_template_exactness(community_rows: Any, personal_rows: Any) -> dict[str, Any]:
    """Classify community and account gear templates without data substitution."""

    community = _template_category(community_rows, "community")
    personal = _template_category(personal_rows, "personal")
    problems = [
        *(community.get("problems") or []),
        *(personal.get("problems") or []),
    ]
    problem_codes = sorted({
        *list(community.get("problemCodes") or []),
        *list(personal.get("problemCodes") or []),
    })
    return {
        "schemaRevision": "gear-template-exactness-audit-v1",
        "status": _status((community["status"], personal["status"])),
        "community": community,
        "personal": personal,
        "problemCodes": problem_codes,
        "problemCounts": {
            code: (
                _positive_int(community.get("problemCounts", {}).get(code))
                + _positive_int(personal.get("problemCounts", {}).get(code))
            )
            for code in problem_codes
        },
        "problems": _problem_samples(problems),
    }


def audit_spec_coverage(spec_rows: Any) -> dict[str, Any]:
    """Require exactly forty unique, non-blocked specialization browse rows."""

    rows = [row for row in spec_rows or [] if isinstance(row, Mapping)]
    verified_count = 0
    partial_count = 0
    blocked_count = 0
    problems: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        class_key = _text(row.get("classKey"))
        spec_key = _text(row.get("specKey"))
        key = (class_key, spec_key)
        candidate_count = _positive_int(row.get("candidateCount"))
        blockers = [
            _text(value)
            for value in row.get("blockerCodes") or []
            if _text(value)
        ]
        row_status = _text(row.get("status"))
        if not class_key or not spec_key:
            row_status = "blocked"
            problems.append(_problem(
                "SPEC_COVERAGE_IDENTITY_MISSING",
                f"specRows[{index}]",
                "Specialization coverage requires classKey and specKey.",
            ))
        elif key in seen:
            row_status = "blocked"
            problems.append(_problem(
                "SPEC_COVERAGE_DUPLICATE",
                f"specRows[{index}]",
                "Specialization coverage identities must be unique.",
            ))
        if row_status == "verified" and candidate_count > 0 and not blockers:
            verified_count += 1
        elif row_status == "partial" and candidate_count > 0:
            partial_count += 1
        else:
            blocked_count += 1
            if not candidate_count:
                problems.append(_problem(
                    "SPEC_COVERAGE_CANDIDATES_MISSING",
                    f"specRows[{index}].candidateCount",
                    "Blocked or empty candidates do not count as coverage.",
                ))
            for blocker in blockers:
                problems.append(_problem(
                    blocker,
                    f"specRows[{index}].blockerCodes",
                    "Backend specialization browse blocker.",
                ))
        if class_key and spec_key:
            seen.add(key)

    if len(seen) != 40:
        problems.append(_problem(
            "SPEC_COVERAGE_COUNT_MISMATCH",
            "specRows",
            f"Expected 40 unique specializations, observed {len(seen)}.",
        ))
    complete = len(seen) == 40 and verified_count == 40 and not partial_count and not blocked_count
    status = "verified" if complete else ("blocked" if blocked_count or len(seen) != 40 else "partial")
    return {
        "schemaRevision": "gear-spec-coverage-audit-v1",
        "status": status,
        "specTotal": len(seen),
        "verifiedSpecCount": verified_count,
        "partialSpecCount": partial_count,
        "blockedSpecCount": blocked_count,
        "complete": complete,
        "problemCodes": _problem_codes(problems),
        "problemCounts": _problem_counts(problems),
        "problems": _problem_samples(problems),
    }


def audit_resource_baseline(resource_rows: Any) -> dict[str, Any]:
    """Preserve missing resource evidence as unknown instead of a numeric default."""

    source = _mapping(resource_rows)
    measured: dict[str, int | float | None] = {}
    problems: list[dict[str, str]] = []
    blocked = False
    for field in _RESOURCE_FIELDS:
        value = _non_negative_number(source.get(field))
        measured[field] = value
        if value is None:
            blocked = True
            problems.append(_problem(
                "RESOURCE_BASELINE_REQUIRED_MISSING",
                field,
                f"{field} must be measured before a schema-shadow plan.",
            ))

    optional: dict[str, dict[str, Any]] = {}
    for field, output_key in (
        ("peakRssObservedBytes", "peakRss"),
        ("temporaryBytesObserved", "temporaryBytes"),
    ):
        value = _non_negative_number(source.get(field))
        optional[output_key] = {
            "status": "measured" if value is not None else "unknown",
            "bytes": value,
        }
        if value is None:
            problems.append(_problem(
                "RESOURCE_BASELINE_UNKNOWN",
                field,
                f"{field} is unavailable and remains unknown.",
            ))

    probe_status = _text(source.get("resourceProbeStatus"))
    probe_problem_codes = sorted({
        _text(code)
        for code in source.get("resourceProbeProblemCodes") or []
        if _text(code)
    })
    if probe_status == "blocked":
        blocked = True
        exceeded = any(
            code.endswith("_EXCEEDED")
            for code in probe_problem_codes
        )
        problems.append(_problem(
            "RESOURCE_BASELINE_EXCEEDED"
            if exceeded
            else "RESOURCE_BASELINE_INVALID",
            "resourceProbe",
            (
                "The bounded Community builder resource probe exceeded a hard limit."
                if exceeded
                else "The bounded Community builder resource probe did not preserve its read-only stability contract."
            ),
        ))

    status = "blocked" if blocked else (
        "partial"
        if any(value["status"] == "unknown" for value in optional.values())
        else "verified"
    )
    return {
        "schemaRevision": "gear-resource-baseline-audit-v1",
        "status": status,
        "measured": measured,
        **optional,
        "probe": {
            "status": probe_status or "not_supplied",
            "problemCodes": probe_problem_codes,
        },
        "problemCodes": _problem_codes(problems),
        "problemCounts": _problem_counts(problems),
        "problems": _problem_samples(problems),
    }


def _report_identity_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return _without_non_identity_fields({
        "schemaRevision": report.get("schemaRevision"),
        "status": report.get("status"),
        "catalogMapping": report.get("catalogMapping"),
        "templateExactness": report.get("templateExactness"),
        "specCoverage": report.get("specCoverage"),
        "resources": report.get("resources"),
        "callers": report.get("callers"),
        "problems": report.get("problems"),
    })


def build_phase0_report(
    *,
    catalog: Any,
    templates: Any,
    coverage: Any,
    resources: Any,
    callers: Any,
    observed_at: str,
) -> dict[str, Any]:
    """Build one aggregate-only, content-addressed Phase 0 audit report."""

    sections = {
        "catalogMapping": _canonical(catalog),
        "templateExactness": _canonical(templates),
        "specCoverage": _canonical(coverage),
        "resources": _canonical(resources),
        "callers": _canonical(callers),
    }
    statuses = [
        _text(section.get("status"))
        for section in sections.values()
        if isinstance(section, Mapping)
    ]
    problems = []
    for name, section in sections.items():
        if not isinstance(section, Mapping) or not section:
            problems.append(_problem(
                "AUDIT_SECTION_INVALID",
                name,
                f"{name} is required.",
            ))
            continue
        for code in section.get("problemCodes") or []:
            problems.append(_problem(
                _text(code) or "AUDIT_SECTION_PROBLEM",
                name,
                f"{name} reported a bounded audit problem.",
            ))
    report = {
        "schemaRevision": AUDIT_SCHEMA_REVISION,
        "reportId": "",
        "observedAt": _text(observed_at),
        "status": _status(statuses, default="blocked"),
        **sections,
        "problems": _canonical(problems),
    }
    if problems:
        report["status"] = _status((report["status"], "partial"))
    report["reportId"] = AUDIT_REPORT_PREFIX + _sha256(_report_identity_payload(report))
    return report


def _sensitive_paths(value: Any, path: str = "report") -> list[str]:
    if isinstance(value, Mapping):
        paths = []
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if str(key) in _SENSITIVE_KEYS:
                paths.append(child_path)
            paths.extend(_sensitive_paths(item, child_path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_sensitive_paths(item, f"{path}[{index}]"))
        return paths
    return []


def validate_phase0_report(report: Any) -> list[dict[str, str]]:
    """Validate one detached Phase 0 report without accessing external state."""

    if not isinstance(report, Mapping):
        return [_problem("AUDIT_REPORT_INVALID", "report", "Audit report must be an object.")]
    issues: list[dict[str, str]] = []
    if report.get("schemaRevision") != AUDIT_SCHEMA_REVISION:
        issues.append(_problem(
            "AUDIT_SCHEMA_INVALID",
            "report.schemaRevision",
            "Audit schema revision is invalid.",
        ))
    if _text(report.get("status")) not in _STATUS_RANK:
        issues.append(_problem(
            "AUDIT_STATUS_INVALID",
            "report.status",
            "Audit status must be verified, partial, or blocked.",
        ))
    if not _text(report.get("observedAt")):
        issues.append(_problem(
            "AUDIT_OBSERVED_AT_MISSING",
            "report.observedAt",
            "Audit observation time is required but is not part of immutable identity.",
        ))
    for section in (
        "catalogMapping",
        "templateExactness",
        "specCoverage",
        "resources",
        "callers",
    ):
        if not isinstance(report.get(section), Mapping) or not report.get(section):
            issues.append(_problem(
                "AUDIT_SECTION_INVALID",
                f"report.{section}",
                f"{section} must be a non-empty object.",
            ))
    report_id = _text(report.get("reportId"))
    if not re.fullmatch(r"catalog-migration-audit:sha256:[0-9a-f]{64}", report_id):
        issues.append(_problem(
            "AUDIT_REPORT_ID_INVALID",
            "report.reportId",
            "Audit report identity is invalid.",
        ))
    else:
        expected = AUDIT_REPORT_PREFIX + _sha256(_report_identity_payload(report))
        if report_id != expected:
            issues.append(_problem(
                "AUDIT_REPORT_ID_MISMATCH",
                "report.reportId",
                "Audit report content does not match its identity.",
            ))
    for path in _sensitive_paths(report):
        issues.append(_problem(
            "AUDIT_SENSITIVE_FIELD_PRESENT",
            path,
            "Aggregate audit reports cannot contain sensitive fields.",
        ))
    return issues


__all__ = (
    "AUDIT_REPORT_PREFIX",
    "AUDIT_SCHEMA_REVISION",
    "audit_catalog_mapping",
    "audit_resource_baseline",
    "audit_spec_coverage",
    "audit_template_exactness",
    "build_phase0_report",
    "validate_phase0_report",
)
