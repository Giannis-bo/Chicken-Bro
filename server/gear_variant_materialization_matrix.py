"""Pure callback-driven BrowseVariant materialization matrix."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping


GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION = (
    "gear-variant-materialization-matrix-v1"
)
_REPORT_ID_PREFIX = "gear-variant-materialization-matrix:sha256:"
_MAX_FAILURE_SAMPLES = 10
_READY_STATUSES = {"verified", "resolved"}
_PROVENANCE_CODES = {
    "MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT",
    "MATERIALIZATION_MATRIX_CONTEXT_ITEM_MISMATCH",
    "MATERIALIZATION_MATRIX_MISSING_SELECTION_INTENT",
    "MATERIALIZATION_MATRIX_SELECTION_INTENT_PROOF_MISSING",
    "MATERIALIZATION_MATRIX_SELECTION_INTENT_PROOF_MISMATCH",
    "MATERIALIZATION_MATRIX_MATERIALIZED_PAIR_MISMATCH",
}
_DEFAULT_CODES = {
    "MATERIALIZATION_MATRIX_DEFAULT_FLAG_MISSING",
    "MATERIALIZATION_MATRIX_USED_DEFAULT_VARIANT",
}

Materializer = Callable[..., Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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


def _canonical_codes(value: Any) -> list[str]:
    codes: list[str] = []
    if isinstance(value, list):
        for raw in value:
            code = _text(raw)
            if code:
                codes.append(code)
    return sorted(set(codes))


def _failure_sample(
    code: str,
    *,
    browse_variant_key: str = "",
    item_id: str = "",
    class_key: str = "",
    spec_key: str = "",
    slot: str = "",
) -> dict[str, str]:
    sample = {"code": _text(code)}
    if _text(browse_variant_key):
        sample["browseVariantKey"] = _text(browse_variant_key)
    if _text(item_id):
        sample["itemId"] = _text(item_id)
    if _text(class_key):
        sample["classKey"] = _text(class_key)
    if _text(spec_key):
        sample["specKey"] = _text(spec_key)
    if _text(slot):
        sample["slot"] = _text(slot)
    return sample


def _sample_sort_key(sample: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        _text(sample.get("code")),
        _text(sample.get("browseVariantKey")),
        _text(sample.get("itemId")),
        _text(sample.get("classKey")),
        _text(sample.get("specKey")),
        _text(sample.get("slot")),
    )


def _catalog_index(
    catalog: Mapping[str, Any],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    variants: dict[str, str] = {}
    failures: list[dict[str, str]] = []
    for raw in catalog.get("browseVariants") or []:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        key = _text(row.get("browseVariantKey"))
        item_id = _text(row.get("itemId"))
        if not key or not item_id or key in variants:
            failures.append(
                _failure_sample(
                    "CATALOG_BROWSE_VARIANT_ID_INVALID",
                    browse_variant_key=key,
                    item_id=item_id,
                )
            )
            continue
        variants[key] = item_id
    return variants, failures


def _relation_index(
    relation_contexts: Any,
    *,
    expected_variants: Mapping[str, str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    indexed: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    seen_contexts: set[tuple[str, str, str, str, str]] = set()
    for raw in relation_contexts or []:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        key = _text(row.get("browseVariantKey"))
        item_id = _text(row.get("itemId"))
        class_key = _text(row.get("classKey"))
        spec_key = _text(row.get("specKey"))
        slot = _text(row.get("slot"))
        context_key = (key, item_id, class_key, spec_key, slot)
        if context_key in seen_contexts:
            failures.append(
                _failure_sample(
                    "MATERIALIZATION_MATRIX_DUPLICATE_RELATION_CONTEXT",
                    browse_variant_key=key,
                    item_id=item_id,
                    class_key=class_key,
                    spec_key=spec_key,
                    slot=slot,
                )
            )
            continue
        seen_contexts.add(context_key)
        if key in indexed:
            failures.append(
                _failure_sample(
                    "MATERIALIZATION_MATRIX_DUPLICATE_VARIANT_CONTEXT",
                    browse_variant_key=key,
                    item_id=item_id,
                    class_key=class_key,
                    spec_key=spec_key,
                    slot=slot,
                )
            )
            continue
        if key not in expected_variants:
            failures.append(
                _failure_sample(
                    "MATERIALIZATION_MATRIX_EXTRA_RELATION_CONTEXT",
                    browse_variant_key=key,
                    item_id=item_id,
                    class_key=class_key,
                    spec_key=spec_key,
                    slot=slot,
                )
            )
            continue
        indexed[key] = row
    return indexed, failures


def _read_used_default_variant(report: Mapping[str, Any]) -> bool | None:
    if "usedDefaultVariant" in report:
        return _bool_or_none(report.get("usedDefaultVariant"))
    if "usedExplicitVariant" in report:
        value = _bool_or_none(report.get("usedExplicitVariant"))
        return None if value is None else not value
    return None


def _entry_status(report_status: str, failures: list[str]) -> str:
    if not failures:
        return "verified"
    if report_status in {"blocked", "partial", "UNVERIFIED", "pending"}:
        return report_status
    return "blocked"


def _report_identity_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": report.get("schemaRevision"),
        "status": report.get("status"),
        "expected_unique_variant_count": report.get("expected_unique_variant_count"),
        "materialized_unique_variant_count": report.get("materialized_unique_variant_count"),
        "unique_variant_materialization_count": report.get("unique_variant_materialization_count"),
        "catalog_non_simulatable_count": report.get("catalog_non_simulatable_count"),
        "silent_default_fill_count": report.get("silent_default_fill_count"),
        "missing_provenance_count": report.get("missing_provenance_count"),
        "failureCodes": list(report.get("failureCodes") or []),
        "failureSamples": list(report.get("failureSamples") or []),
        "ledger": dict(report.get("ledger") or {}),
    }


def _report_id(report: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            _report_identity_payload(report),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{_REPORT_ID_PREFIX}{digest}"


def build_gear_variant_materialization_matrix(
    catalog: Any,
    relation_contexts: Any,
    materializer: Materializer,
) -> dict[str, Any]:
    catalog_mapping = _mapping(catalog)
    expected_variants, structural_failures = _catalog_index(catalog_mapping)
    indexed_contexts, relation_failures = _relation_index(
        relation_contexts,
        expected_variants=expected_variants,
    )

    report_failure_samples = [
        dict(sample) for sample in structural_failures + relation_failures
    ]
    report_failure_codes = {
        _text(sample.get("code"))
        for sample in report_failure_samples
        if _text(sample.get("code"))
    }
    ledger: dict[str, dict[str, Any]] = {}
    materialized_unique_variant_count = 0
    catalog_non_simulatable_count = 0
    silent_default_fill_count = 0
    missing_provenance_count = 0

    for browse_variant_key in sorted(expected_variants):
        item_id = expected_variants[browse_variant_key]
        context = indexed_contexts.get(browse_variant_key)
        entry_failures: list[str] = []
        report_status = ""
        entry_missing_provenance = False
        entry_silent_default = False
        entry = {
            "status": "blocked",
            "itemId": item_id,
            "classKey": "",
            "specKey": "",
            "slot": "",
            "resolverStatus": "",
            "profileStatus": "",
            "simcReady": None,
            "selectionIntentPresent": False,
            "usedDefaultVariant": None,
            "materializedItemId": "",
            "materializedBrowseVariantKey": "",
            "failureCodes": [],
        }

        if context is None:
            entry_failures.append("MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT")
            entry_missing_provenance = True
        else:
            class_key = _text(context.get("classKey"))
            spec_key = _text(context.get("specKey"))
            slot = _text(context.get("slot"))
            context_item_id = _text(context.get("itemId"))
            selection_intent = context.get("selectionIntent")
            entry["classKey"] = class_key
            entry["specKey"] = spec_key
            entry["slot"] = slot
            if context_item_id != item_id:
                entry_failures.append("MATERIALIZATION_MATRIX_CONTEXT_ITEM_MISMATCH")
                entry_missing_provenance = True
            if not class_key or not spec_key or not slot:
                entry_failures.append("MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT")
                entry_missing_provenance = True
            safe_selection_intent = (
                _canonical(selection_intent)
                if isinstance(selection_intent, Mapping) and bool(selection_intent)
                else None
            )
            if safe_selection_intent is None:
                entry_failures.append("MATERIALIZATION_MATRIX_MISSING_SELECTION_INTENT")
                entry_missing_provenance = True
            if not entry_failures:
                try:
                    raw_report = materializer(
                        item_id=item_id,
                        browse_variant_key=browse_variant_key,
                        class_key=class_key,
                        spec_key=spec_key,
                        slot=slot,
                        selection_intent=copy_dict(safe_selection_intent),
                    )
                except Exception:
                    raw_report = None
                    entry_failures.append("MATERIALIZATION_MATRIX_CALLBACK_EXCEPTION")
                if isinstance(raw_report, Mapping):
                    report = dict(raw_report)
                    report_status = _text(report.get("status"))
                    proof_selection_intent = report.get("selectionIntent")
                    materialized_item_id = _text(report.get("materializedItemId"))
                    materialized_browse_variant_key = _text(
                        report.get("materializedBrowseVariantKey")
                    )
                    resolver_status = _text(report.get("resolverStatus"))
                    profile_status = _text(report.get("profileStatus"))
                    simc_ready = _bool_or_none(report.get("simcReady"))
                    used_default_variant = _read_used_default_variant(report)
                    callback_failure_codes = _canonical_codes(report.get("failureCodes"))

                    entry["materializedItemId"] = materialized_item_id
                    entry["materializedBrowseVariantKey"] = materialized_browse_variant_key
                    entry["resolverStatus"] = resolver_status
                    entry["profileStatus"] = profile_status
                    entry["simcReady"] = simc_ready
                    entry["usedDefaultVariant"] = used_default_variant

                    if isinstance(proof_selection_intent, Mapping):
                        entry["selectionIntentPresent"] = True
                        if _canonical(proof_selection_intent) != safe_selection_intent:
                            entry_failures.append(
                                "MATERIALIZATION_MATRIX_SELECTION_INTENT_PROOF_MISMATCH"
                            )
                            entry_missing_provenance = True
                    else:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_SELECTION_INTENT_PROOF_MISSING"
                        )
                        entry_missing_provenance = True

                    if used_default_variant is None:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_DEFAULT_FLAG_MISSING"
                        )
                        entry_silent_default = True
                    elif used_default_variant is True:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_USED_DEFAULT_VARIANT"
                        )
                        entry_silent_default = True

                    if (
                        materialized_item_id != item_id
                        or materialized_browse_variant_key != browse_variant_key
                    ):
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_MATERIALIZED_PAIR_MISMATCH"
                        )
                        entry_missing_provenance = True

                    if report_status and report_status not in _READY_STATUSES:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_REPORT_STATUS_NOT_READY"
                        )
                    if resolver_status not in _READY_STATUSES:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_RESOLVER_STATUS_NOT_READY"
                        )
                    if profile_status not in _READY_STATUSES:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_PROFILE_STATUS_NOT_READY"
                        )
                    if simc_ready is not True:
                        entry_failures.append(
                            "MATERIALIZATION_MATRIX_SIMC_READINESS_NOT_TRUE"
                        )
                    entry_failures.extend(callback_failure_codes)
                elif "MATERIALIZATION_MATRIX_CALLBACK_EXCEPTION" not in entry_failures:
                    entry_failures.append(
                        "MATERIALIZATION_MATRIX_MATERIALIZER_REPORT_MALFORMED"
                    )

        entry["failureCodes"] = sorted(set(_text(code) for code in entry_failures if _text(code)))
        entry["status"] = _entry_status(report_status, entry["failureCodes"])
        ledger[browse_variant_key] = entry

        if entry["failureCodes"]:
            catalog_non_simulatable_count += 1
            if entry_missing_provenance:
                missing_provenance_count += 1
            if entry_silent_default:
                silent_default_fill_count += 1
            report_failure_codes.update(entry["failureCodes"])
            for code in entry["failureCodes"]:
                report_failure_samples.append(
                    _failure_sample(
                        code,
                        browse_variant_key=browse_variant_key,
                        item_id=item_id,
                        class_key=entry["classKey"],
                        spec_key=entry["specKey"],
                        slot=entry["slot"],
                    )
                )
        else:
            materialized_unique_variant_count += 1

    report = {
        "schemaRevision": GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION,
        "status": (
            "verified"
            if (
                not report_failure_codes
                and materialized_unique_variant_count == len(expected_variants)
            )
            else "blocked"
        ),
        "expected_unique_variant_count": len(expected_variants),
        "materialized_unique_variant_count": materialized_unique_variant_count,
        "unique_variant_materialization_count": materialized_unique_variant_count,
        "catalog_non_simulatable_count": catalog_non_simulatable_count,
        "silent_default_fill_count": silent_default_fill_count,
        "missing_provenance_count": missing_provenance_count,
        "failureCodes": sorted(report_failure_codes),
        "failureSamples": sorted(
            (_canonical(sample) for sample in report_failure_samples),
            key=_sample_sort_key,
        )[:_MAX_FAILURE_SAMPLES],
        "ledger": {
            key: _canonical(ledger[key])
            for key in sorted(ledger)
        },
    }
    report["reportId"] = _report_id(report)
    return _canonical(report)


def validate_gear_variant_materialization_matrix_report(report: Any) -> list[str]:
    if not isinstance(report, Mapping):
        return ["MATERIALIZATION_MATRIX_REPORT_MALFORMED"]

    issues: list[str] = []
    required_fields = (
        "schemaRevision",
        "reportId",
        "status",
        "expected_unique_variant_count",
        "materialized_unique_variant_count",
        "unique_variant_materialization_count",
        "catalog_non_simulatable_count",
        "silent_default_fill_count",
        "missing_provenance_count",
        "failureCodes",
        "failureSamples",
        "ledger",
    )
    if any(field not in report for field in required_fields):
        return ["MATERIALIZATION_MATRIX_REPORT_MALFORMED"]

    ledger = report.get("ledger")
    if not isinstance(ledger, Mapping):
        return ["MATERIALIZATION_MATRIX_REPORT_MALFORMED"]

    if _text(report.get("schemaRevision")) != GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION:
        issues.append("MATERIALIZATION_MATRIX_IDENTITY_INVALID")

    ledger_keys = list(ledger)
    if ledger_keys != sorted(ledger_keys):
        issues.append("MATERIALIZATION_MATRIX_LEDGER_ORDER_INVALID")

    if _text(report.get("reportId")) != _report_id(report):
        issues.append("MATERIALIZATION_MATRIX_IDENTITY_INVALID")

    try:
        expected_unique_variant_count = int(report.get("expected_unique_variant_count"))
        materialized_unique_variant_count = int(report.get("materialized_unique_variant_count"))
        unique_variant_materialization_count = int(report.get("unique_variant_materialization_count"))
        catalog_non_simulatable_count = int(report.get("catalog_non_simulatable_count"))
        silent_default_fill_count = int(report.get("silent_default_fill_count"))
        missing_provenance_count = int(report.get("missing_provenance_count"))
    except (TypeError, ValueError):
        return ["MATERIALIZATION_MATRIX_REPORT_MALFORMED"]

    if len(ledger_keys) != expected_unique_variant_count:
        issues.append("MATERIALIZATION_MATRIX_COUNT_MISMATCH")

    derived_materialized = 0
    derived_non_simulatable = 0
    derived_silent_default = 0
    derived_missing_provenance = 0
    for raw_entry in ledger.values():
        if not isinstance(raw_entry, Mapping):
            return ["MATERIALIZATION_MATRIX_REPORT_MALFORMED"]
        entry_codes = _canonical_codes(raw_entry.get("failureCodes"))
        if entry_codes:
            derived_non_simulatable += 1
        else:
            derived_materialized += 1
        if any(code in _DEFAULT_CODES for code in entry_codes):
            derived_silent_default += 1
        if any(code in _PROVENANCE_CODES for code in entry_codes):
            derived_missing_provenance += 1

    if (
        materialized_unique_variant_count != derived_materialized
        or unique_variant_materialization_count != derived_materialized
        or catalog_non_simulatable_count != derived_non_simulatable
        or silent_default_fill_count != derived_silent_default
        or missing_provenance_count != derived_missing_provenance
    ):
        issues.append("MATERIALIZATION_MATRIX_COUNT_MISMATCH")

    expected_status = (
        "verified"
        if (
            not list(report.get("failureCodes") or [])
            and derived_non_simulatable == 0
            and derived_materialized == expected_unique_variant_count
        )
        else "blocked"
    )
    if _text(report.get("status")) != expected_status:
        issues.append("MATERIALIZATION_MATRIX_STATUS_INVALID")

    return sorted(set(issues))


def copy_dict(value: Any) -> dict[str, Any]:
    return dict(_canonical(value)) if isinstance(value, Mapping) else {}
