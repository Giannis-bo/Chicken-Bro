"""Pure final evidence assembly for the dormant Catalog v3 / builder v5 candidate."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .catalog_candidate_gate_metrics import (
    REQUIRED_CANDIDATE_GATE_FIELDS,
    build_candidate_gate_metrics,
)


CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION = "gear-catalog-candidate-evidence-v1"

_REPORT_ID_PREFIX = "gear-catalog-candidate-evidence:sha256:"
_PRESERVED_STATUSES = ("partial", "blocked", "UNVERIFIED", "pending")
_IDENTITY_FIELDS = (
    "manifestRevision",
    "pointerGeneration",
    "gearCatalogRevision",
    "gearExactRegistryRevision",
    "simcRuntimeRevision",
)
_IDENTITY_ALIASES = {
    "manifestRevision": ("manifestRevision",),
    "pointerGeneration": ("pointerGeneration",),
    "gearCatalogRevision": ("gearCatalogRevision", "catalogRevision"),
    "gearExactRegistryRevision": (
        "gearExactRegistryRevision",
        "registryRevision",
        "exactRegistryRevision",
    ),
    "simcRuntimeRevision": ("simcRuntimeRevision",),
}
_EXPLICIT_GATE_COUNT_FIELDS = (
    "catalog_non_simulatable_count",
    "silent_default_fill_count",
    "type_unknown_nonportable_visible_count",
    "progression_conflict_count",
    "mixed_revision_count",
    "missing_provenance_count",
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _status(value: Any) -> str:
    raw = _mapping(value).get("status")
    return str(raw).strip() if raw is not None else ""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


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


def _problem(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _identity_candidate_mappings(
    report_name: str,
    value: Any,
) -> list[tuple[str, Mapping[str, Any]]]:
    report = _mapping(value)
    return [
        (report_name, report),
        (f"{report_name}.expectedIdentity", _mapping(report.get("expectedIdentity"))),
        (f"{report_name}.identity", _mapping(report.get("identity"))),
        (f"{report_name}.releaseContext", _mapping(report.get("releaseContext"))),
        (f"{report_name}.sourceIdentity", _mapping(report.get("sourceIdentity"))),
        (f"{report_name}.authoredAgainst", _mapping(report.get("authoredAgainst"))),
    ]


def _identity_normalized(field: str, value: Any) -> Any:
    if field == "pointerGeneration":
        return _int_or_none(value)
    return _text(value)


def _collect_identity_problems(
    report_name: str,
    value: Any,
    expected_identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for field in _IDENTITY_FIELDS:
        expected = _identity_normalized(field, expected_identity.get(field))
        if expected in (None, ""):
            continue
        for source_name, mapping in _identity_candidate_mappings(report_name, value):
            for alias in _IDENTITY_ALIASES[field]:
                if alias not in mapping:
                    continue
                actual = _identity_normalized(field, mapping.get(alias))
                if actual in (None, ""):
                    continue
                if actual != expected:
                    problems.append(
                        _problem(
                            "CANDIDATE_EVIDENCE_IDENTITY_MISMATCH",
                            f"{source_name}.{alias} does not match expected identity",
                            component=report_name,
                            field=field,
                            expected=expected,
                            actual=actual,
                        )
                    )
    return problems


def _normalized_http_status(report: Mapping[str, Any]) -> str:
    status = _text(report.get("status"))
    if status == "verified":
        return "verified"
    if status == "pass" and _int_or_none(report.get("failureCount")) == 0:
        return "verified"
    return status


def _normalized_http_gate_report(
    catalog_http_report: Any,
    catalog_gate_counts: Any,
) -> dict[str, Any]:
    source = _mapping(catalog_http_report)
    counts = _mapping(catalog_gate_counts)
    normalized: dict[str, Any] = {
        "status": _normalized_http_status(source),
        "problemCodes": _normalized_problem_codes(source),
    }
    for field in _EXPLICIT_GATE_COUNT_FIELDS:
        if field in counts:
            normalized[field] = counts[field]
    return normalized


def _normalized_problem_codes(report: Mapping[str, Any]) -> list[str]:
    codes: set[str] = set()
    raw_problem_codes = report.get("problemCodes")
    if isinstance(raw_problem_codes, list):
        codes.update(
            code
            for code in (_text(value) for value in raw_problem_codes)
            if code
        )

    raw_failure_codes = report.get("failureCodes")
    if isinstance(raw_failure_codes, Mapping):
        codes.update(
            code
            for code in (_text(value) for value in raw_failure_codes.keys())
            if code
        )
    elif isinstance(raw_failure_codes, list):
        codes.update(
            code
            for code in (_text(value) for value in raw_failure_codes)
            if code
        )
    return sorted(codes)


def _validate_expected_identity(value: Any) -> list[dict[str, Any]]:
    identity = _mapping(value)
    problems: list[dict[str, Any]] = []
    if not identity:
        return [
            _problem(
                "CANDIDATE_EVIDENCE_EXPECTED_IDENTITY_MALFORMED",
                "expected_identity must be a mapping",
            )
        ]
    for field in _IDENTITY_FIELDS:
        normalized = _identity_normalized(field, identity.get(field))
        if normalized in (None, ""):
            problems.append(
                _problem(
                    "CANDIDATE_EVIDENCE_EXPECTED_IDENTITY_FIELD_MISSING",
                    f"expected_identity.{field} is required",
                    field=field,
                )
            )
    return problems


def _validate_simc_execution_matrix_report(report: Any) -> list[dict[str, Any]]:
    source = _mapping(report)
    problems: list[dict[str, Any]] = []
    if _status(source) != "pass":
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_STATUS_NOT_PASS",
                "simc_execution_matrix_report.status must stay pass",
                status=_status(source) or "missing",
            )
        )
    failure_count = _int_or_none(source.get("failureCount"))
    if failure_count is None:
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_FAILURE_COUNT_INVALID",
                "simc_execution_matrix_report.failureCount must be an explicit non-negative integer",
            )
        )
    elif failure_count != 0:
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_FAILURE_COUNT_NONZERO",
                "simc_execution_matrix_report.failureCount must be zero",
                value=failure_count,
            )
        )

    supported = _mapping(source.get("supported"))
    unsupported = _mapping(source.get("unsupported"))

    supported_values = {
        field: _int_or_none(supported.get(field))
        for field in (
            "expectedSpecCount",
            "profileReadySpecCount",
            "executedSpecCount",
            "dpsMetricSpecCount",
        )
    }
    unsupported_values = {
        field: _int_or_none(unsupported.get(field))
        for field in (
            "expectedSpecCount",
            "deterministicallyBlockedSpecCount",
        )
    }

    if any(value is None for value in supported_values.values()):
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_SUPPORTED_COUNTS_INVALID",
                "simc_execution_matrix_report.supported must expose explicit 26/14 counts",
            )
        )
    elif set(supported_values.values()) != {26}:
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_SUPPORTED_COUNT_MISMATCH",
                "simc_execution_matrix_report.supported counts must all equal 26",
                supported=supported_values,
            )
        )

    if any(value is None for value in unsupported_values.values()):
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_UNSUPPORTED_COUNTS_INVALID",
                "simc_execution_matrix_report.unsupported must expose explicit 26/14 counts",
            )
        )
    elif set(unsupported_values.values()) != {14}:
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_SIMC_26_14_UNSUPPORTED_COUNT_MISMATCH",
                "simc_execution_matrix_report.unsupported counts must all equal 14",
                unsupported=unsupported_values,
            )
        )
    return problems


def _report_id_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": report.get("schemaRevision"),
        "status": report.get("status"),
        "problems": list(report.get("problems") or []),
        "machineFields": {
            field: report.get(field) for field in REQUIRED_CANDIDATE_GATE_FIELDS
        },
        "expectedIdentity": dict(report.get("expectedIdentity") or {}),
        "pointerStable": report.get("pointerStable"),
        "pointerBefore": dict(report.get("pointerBefore") or {}),
        "pointerAfter": dict(report.get("pointerAfter") or {}),
        "componentStatuses": dict(report.get("componentStatuses") or {}),
        "componentEvidence": dict(report.get("componentEvidence") or {}),
    }


def _report_id(report: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            _report_id_payload(report),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{_REPORT_ID_PREFIX}{digest}"


def _final_status(
    *,
    problems: list[dict[str, Any]],
    exact_registry_status: str,
) -> str:
    if not problems:
        return "verified"
    if exact_registry_status in _PRESERVED_STATUSES:
        return exact_registry_status
    return "blocked"


def assemble_catalog_candidate_evidence(
    *,
    catalog: Any,
    catalog_http_report: Any,
    catalog_gate_counts: Any,
    materialization_report: Any,
    variant_simc_report: Any,
    simc_execution_matrix_report: Any,
    exact_registry_report: Any,
    expected_identity: Any,
    pointer_before: Any,
    pointer_after: Any,
) -> dict[str, Any]:
    raw_component_evidence = {
        "catalog": _canonical(catalog),
        "catalog_http_report": _canonical(catalog_http_report),
        "catalog_gate_counts": _canonical(catalog_gate_counts),
        "materialization_report": _canonical(materialization_report),
        "variant_simc_report": _canonical(variant_simc_report),
        "simc_execution_matrix_report": _canonical(simc_execution_matrix_report),
        "exact_registry_report": _canonical(exact_registry_report),
    }
    component_statuses = {
        "catalog": _status(catalog),
        "catalog_http_report": _status(catalog_http_report),
        "materialization_report": _status(materialization_report),
        "variant_simc_report": _status(variant_simc_report),
        "simc_execution_matrix_report": _status(simc_execution_matrix_report),
        "exact_registry_report": _status(exact_registry_report),
    }

    normalized_http_report = _normalized_http_gate_report(
        catalog_http_report,
        catalog_gate_counts,
    )
    gate_metrics = build_candidate_gate_metrics(
        catalog,
        normalized_http_report,
        materialization_report,
        variant_simc_report,
        exact_registry_report=exact_registry_report,
    )

    problems: list[dict[str, Any]] = list(gate_metrics.get("problems") or [])
    problems.extend(_validate_expected_identity(expected_identity))
    problems.extend(_validate_simc_execution_matrix_report(simc_execution_matrix_report))

    expected_identity_mapping = _mapping(expected_identity)
    for component_name, value in (
        ("catalog", catalog),
        ("catalog_http_report", catalog_http_report),
        ("catalog_gate_counts", catalog_gate_counts),
        ("materialization_report", materialization_report),
        ("variant_simc_report", variant_simc_report),
        ("simc_execution_matrix_report", simc_execution_matrix_report),
        ("exact_registry_report", exact_registry_report),
    ):
        problems.extend(
            _collect_identity_problems(
                component_name,
                value,
                expected_identity_mapping,
            )
        )

    stable_before = _canonical(pointer_before)
    stable_after = _canonical(pointer_after)
    pointer_stable = stable_before == stable_after
    if not pointer_stable:
        problems.append(
            _problem(
                "CANDIDATE_EVIDENCE_POINTER_DRIFT",
                "pointer_before and pointer_after must remain exactly equal",
                pointerBefore=stable_before,
                pointerAfter=stable_after,
            )
        )

    report = {
        "schemaRevision": CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION,
        "status": _final_status(
            problems=problems,
            exact_registry_status=component_statuses["exact_registry_report"],
        ),
        "problems": _canonical(problems),
        "expectedIdentity": _canonical(expected_identity_mapping),
        "pointerStable": pointer_stable,
        "pointerBefore": stable_before,
        "pointerAfter": stable_after,
        "componentStatuses": _canonical(component_statuses),
        "componentEvidence": raw_component_evidence,
    }

    metrics = gate_metrics.get("metrics") if isinstance(gate_metrics, Mapping) else {}
    safe_metrics = _mapping(metrics)
    for field in REQUIRED_CANDIDATE_GATE_FIELDS:
        report[field] = safe_metrics.get(field)

    report["reportId"] = _report_id(report)
    return report


__all__ = (
    "CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION",
    "assemble_catalog_candidate_evidence",
)
