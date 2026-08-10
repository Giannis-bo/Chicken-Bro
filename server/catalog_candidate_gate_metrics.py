"""Pure machine-gate aggregation for the dormant Catalog v3 / builder v5 candidate."""

from __future__ import annotations

from typing import Any, Mapping

REQUIRED_CANDIDATE_GATE_FIELDS = (
    "exact_derived_browse_count",
    "catalog_non_simulatable_count",
    "silent_default_fill_count",
    "type_unknown_nonportable_visible_count",
    "progression_conflict_count",
    "mixed_revision_count",
    "missing_provenance_count",
    "unique_variant_materialization_count",
    "supported_variant_simc_smoke_count",
)

_ZERO_REQUIRED_FIELDS = REQUIRED_CANDIDATE_GATE_FIELDS[:7]


def _problem(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _problem_codes(report: Mapping[str, Any]) -> list[str]:
    raw_codes = report.get("problemCodes")
    if isinstance(raw_codes, list):
        return [str(code) for code in raw_codes if str(code).strip()]
    raw_problems = report.get("problems")
    if not isinstance(raw_problems, list):
        return []
    codes: list[str] = []
    for problem in raw_problems:
        if isinstance(problem, Mapping):
            code = str(problem.get("code") or "").strip()
            if code:
                codes.append(code)
    return codes


def _status(report: Mapping[str, Any]) -> str:
    value = report.get("status")
    return str(value).strip() if value is not None else ""


def _read_nonnegative_int(
    payload: Mapping[str, Any],
    field: str,
    source: str,
    problems: list[dict[str, Any]],
) -> int | None:
    value = payload.get(field)
    if value is None:
        problems.append(
            _problem(
                "CANDIDATE_GATE_FIELD_MISSING",
                f"Missing required field {source}.{field}",
                field=f"{source}.{field}",
            )
        )
        return None
    if isinstance(value, bool):
        parsed = None
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        parsed = None
    if parsed is None or parsed < 0:
        problems.append(
            _problem(
                "CANDIDATE_GATE_FIELD_INVALID",
                f"Invalid integer field {source}.{field}",
                field=f"{source}.{field}",
                value=value,
            )
        )
        return None
    return parsed


def _identity_problem_codes(report_codes: list[str]) -> list[str]:
    return [code for code in report_codes if _is_identity_problem_code(code)]


def _is_identity_problem_code(code: str) -> bool:
    normalized = str(code or "").strip().upper()
    if not normalized:
        return False
    if normalized.startswith("CATALOG_") and (
        normalized.endswith("_MISMATCH")
        or normalized.endswith("_KEY_MISMATCH")
    ):
        return True
    if normalized.startswith("EXACT_") and (
        normalized.endswith("_MISMATCH")
        or normalized.endswith("_KEY_MISMATCH")
        or normalized.endswith("_BINDING_INVALID")
        or normalized.endswith("_REFERENCE_NOT_VERIFIED")
        or normalized.endswith("_AUTHORITY_REQUIRED")
    ):
        return True
    if normalized.startswith("LOADOUT_EXACT_") and normalized.endswith(
        "_REFERENCE_NOT_VERIFIED"
    ):
        return True
    if normalized.startswith("RESOLVED_LOADOUT_") and normalized.endswith(
        "_BINDING_INVALID"
    ):
        return True
    if normalized.startswith("TRACK_AUTHORITY_") and normalized.endswith(
        "_BINDING_INVALID"
    ):
        return True
    return False


def build_candidate_gate_metrics(
    catalog: Any,
    catalog_http_report: Any,
    materialization_report: Any,
    simc_report: Any,
    exact_registry_report: Any = None,
) -> dict[str, Any]:
    catalog_mapping = _mapping(catalog)
    catalog_http_mapping = _mapping(catalog_http_report)
    materialization_mapping = _mapping(materialization_report)
    simc_mapping = _mapping(simc_report)

    statuses = {
        "catalog": _status(catalog_mapping),
        "catalog_http_report": _status(catalog_http_mapping),
        "materialization_report": _status(materialization_mapping),
        "simc_report": _status(simc_mapping),
    }
    problem_codes = {
        "catalog": _problem_codes(catalog_mapping),
        "catalog_http_report": _problem_codes(catalog_http_mapping),
        "materialization_report": _problem_codes(materialization_mapping),
        "simc_report": _problem_codes(simc_mapping),
    }

    exact_registry_mapping = None
    if exact_registry_report is not None:
        exact_registry_mapping = _mapping(exact_registry_report)
        statuses["exact_registry_report"] = _status(exact_registry_mapping)
        problem_codes["exact_registry_report"] = _problem_codes(exact_registry_mapping)

    field_problems: list[dict[str, Any]] = []

    content_summary = _mapping(catalog_mapping.get("contentSummary"))
    metrics = {
        "exact_derived_browse_count": _read_nonnegative_int(
            content_summary,
            "exactDerivedVariantCount",
            "catalog.contentSummary",
            field_problems,
        ),
        "catalog_non_simulatable_count": _read_nonnegative_int(
            catalog_http_mapping,
            "catalog_non_simulatable_count",
            "catalog_http_report",
            field_problems,
        ),
        "silent_default_fill_count": _read_nonnegative_int(
            catalog_http_mapping,
            "silent_default_fill_count",
            "catalog_http_report",
            field_problems,
        ),
        "type_unknown_nonportable_visible_count": _read_nonnegative_int(
            catalog_http_mapping,
            "type_unknown_nonportable_visible_count",
            "catalog_http_report",
            field_problems,
        ),
        "progression_conflict_count": _read_nonnegative_int(
            catalog_http_mapping,
            "progression_conflict_count",
            "catalog_http_report",
            field_problems,
        ),
        "mixed_revision_count": _read_nonnegative_int(
            catalog_http_mapping,
            "mixed_revision_count",
            "catalog_http_report",
            field_problems,
        ),
        "missing_provenance_count": _read_nonnegative_int(
            catalog_http_mapping,
            "missing_provenance_count",
            "catalog_http_report",
            field_problems,
        ),
        "unique_variant_materialization_count": _read_nonnegative_int(
            materialization_mapping,
            "unique_variant_materialization_count",
            "materialization_report",
            field_problems,
        ),
        "supported_variant_simc_smoke_count": _read_nonnegative_int(
            simc_mapping,
            "passed_supported_variant_smoke_count",
            "simc_report",
            field_problems,
        ),
    }
    expected_unique_variant_count = _read_nonnegative_int(
        materialization_mapping,
        "expected_unique_variant_count",
        "materialization_report",
        field_problems,
    )
    expected_supported_variant_smoke_count = _read_nonnegative_int(
        simc_mapping,
        "expected_supported_variant_smoke_count",
        "simc_report",
        field_problems,
    )

    if field_problems:
        return {
            "status": "blocked",
            "metrics": {},
            "problems": field_problems,
            "reportStatuses": dict(statuses),
            "reportProblemCodes": {key: list(value) for key, value in problem_codes.items()},
        }

    safe_metrics = {key: int(value) for key, value in metrics.items()}
    problems: list[dict[str, Any]] = []

    for report_name, status in statuses.items():
        if status != "verified":
            problems.append(
                _problem(
                    "CANDIDATE_GATE_REPORT_STATUS_NOT_VERIFIED",
                    f"{report_name} must stay literal when not verified",
                    report=report_name,
                    status=status or "missing",
                )
            )

    for report_name, report_problem_codes in problem_codes.items():
        for code in _identity_problem_codes(report_problem_codes):
            problems.append(
                _problem(
                    "CANDIDATE_GATE_IDENTITY_PROBLEM",
                    f"{report_name} reports an identity blocker",
                    report=report_name,
                    problemCode=code,
                )
            )

    for field_name in _ZERO_REQUIRED_FIELDS:
        value = safe_metrics[field_name]
        if value != 0:
            problems.append(
                _problem(
                    "CANDIDATE_GATE_METRIC_NONZERO",
                    f"{field_name} must be zero for a verified candidate",
                    field=field_name,
                    value=value,
                )
            )

    if safe_metrics["unique_variant_materialization_count"] != expected_unique_variant_count:
        problems.append(
            _problem(
                "CANDIDATE_GATE_MATERIALIZATION_COVERAGE_MISMATCH",
                "unique_variant_materialization_count must equal expected_unique_variant_count",
                actual=safe_metrics["unique_variant_materialization_count"],
                expected=expected_unique_variant_count,
            )
        )
    if safe_metrics["supported_variant_simc_smoke_count"] != expected_supported_variant_smoke_count:
        problems.append(
            _problem(
                "CANDIDATE_GATE_SIMC_COVERAGE_MISMATCH",
                "supported_variant_simc_smoke_count must equal expected_supported_variant_smoke_count",
                actual=safe_metrics["supported_variant_simc_smoke_count"],
                expected=expected_supported_variant_smoke_count,
            )
        )

    result = {
        "status": "verified" if not problems else "blocked",
        "problems": problems,
        "reportStatuses": dict(statuses),
        "reportProblemCodes": {key: list(value) for key, value in problem_codes.items()},
    }
    result.update(safe_metrics)
    result["metrics"] = dict(safe_metrics)
    return result
