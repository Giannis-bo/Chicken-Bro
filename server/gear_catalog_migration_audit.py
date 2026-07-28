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


AUDIT_SCHEMA_REVISION = "equipment-simulator-catalog-migration-audit-v1"
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


def audit_catalog_mapping(binding: Any, rows: Any) -> dict[str, Any]:
    """Classify whether one active release can become a catalog deterministically."""

    active_binding = _mapping(binding)
    source = _mapping(rows)
    items = [row for row in source.get("items") or [] if isinstance(row, Mapping)]
    variants = [row for row in source.get("variants") or [] if isinstance(row, Mapping)]
    options = [row for row in source.get("options") or [] if isinstance(row, Mapping)]
    problems: list[dict[str, str]] = []

    if not _text(active_binding.get("manifestRevision")):
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

    mapped_item_ids: set[str] = set()
    seen_item_ids: set[str] = set()
    for index, row in enumerate(items):
        item_id = _text(_row_value(row, "itemId", "id"))
        slot = _text(_row_value(row, "slot"))
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
            problems.append(_problem(
                "CATALOG_ITEM_SLOT_MISSING",
                f"rows.items[{index}].slot",
                "ItemDefinition mapping requires a canonical slot.",
            ))
        if item_id and slot and item_id not in seen_item_ids:
            mapped_item_ids.add(item_id)
        if item_id:
            seen_item_ids.add(item_id)

    variant_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for index, row in enumerate(variants):
        item_id = _text(_row_value(row, "itemId"))
        track_key = _text(_row_value(row, "trackKey"))
        rank = _positive_int(_row_value(row, "rank", "trackRank", "upgradeRank"))
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
        if not track_key:
            row_problems.append(_problem(
                "CATALOG_VARIANT_TRACK_MISSING",
                f"rows.variants[{index}].trackKey",
                "BrowseVariant mapping requires a canonical track.",
            ))
        if not rank:
            row_problems.append(_problem(
                "CATALOG_VARIANT_RANK_MISSING",
                f"rows.variants[{index}].rank",
                "BrowseVariant mapping requires a positive rank.",
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
        problems.extend(row_problems)
        if item_id and track_key and rank:
            variant_candidates.setdefault((item_id, track_key), []).append({
                "index": index,
                "rank": rank,
                "valid": not row_problems,
            })

    mapped_variant_count = 0
    excluded_lower_rank_count = 0
    for (item_id, track_key), candidates in sorted(variant_candidates.items()):
        highest_rank = max(candidate["rank"] for candidate in candidates)
        highest = [candidate for candidate in candidates if candidate["rank"] == highest_rank]
        excluded_lower_rank_count += sum(
            1 for candidate in candidates if candidate["rank"] < highest_rank
        )
        if len(highest) != 1:
            problems.append(_problem(
                "CATALOG_VARIANT_HIGHEST_RANK_AMBIGUOUS",
                f"rows.variants[{item_id}:{track_key}]",
                "One item and track has more than one highest-rank candidate.",
            ))
            continue
        if highest[0]["valid"]:
            mapped_variant_count += 1

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
    return {
        "schemaRevision": "gear-catalog-mapping-audit-v1",
        "status": status,
        "manifestRevision": _text(active_binding.get("manifestRevision")),
        "gearReleaseId": _text(active_binding.get("gearReleaseId")),
        "itemTotal": len(items),
        "mappedItemCount": len(mapped_item_ids),
        "variantTotal": len(variants),
        "mappedVariantCount": mapped_variant_count,
        "excludedLowerRankCount": excluded_lower_rank_count,
        "optionTotal": len(options),
        "mappedOptionCount": mapped_option_count,
        "problemCodes": _problem_codes(problems),
        "problems": _canonical(problems),
    }


def _template_item_state(item: Any, path: str) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(item, Mapping):
        return "blocked", [_problem(
            "TEMPLATE_EXACT_ITEM_MALFORMED",
            path,
            "Exact item input must be an object.",
        )]
    problems: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
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
        "problems": _canonical(problems),
    }


def audit_template_exactness(community_rows: Any, personal_rows: Any) -> dict[str, Any]:
    """Classify community and account gear templates without data substitution."""

    community = _template_category(community_rows, "community")
    personal = _template_category(personal_rows, "personal")
    problems = [
        *(community.get("problems") or []),
        *(personal.get("problems") or []),
    ]
    return {
        "schemaRevision": "gear-template-exactness-audit-v1",
        "status": _status((community["status"], personal["status"])),
        "community": community,
        "personal": personal,
        "problemCodes": _problem_codes(problems),
        "problems": _canonical(problems),
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
        "problems": _canonical(problems),
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
        "problemCodes": _problem_codes(problems),
        "problems": _canonical(problems),
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
