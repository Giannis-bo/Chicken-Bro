"""Pure callback-driven unique BrowseVariant SimC smoke matrix."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from .simc_support_policy import (
    SIMC_SPECIALIZATION_UNKNOWN_CODE,
    SIMC_SPECIALIZATION_UNSUPPORTED_CODE,
    simc_execution_support,
)


GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION = "gear-variant-simc-matrix-v1"

SmokeCallback = Callable[..., Any]

_REPORT_ID_PREFIX = "gear-variant-simc-matrix:sha256:"
_MAX_FAILURE_SAMPLES = 10
_READY_STATUSES = {"verified", "resolved"}
_PRESERVED_STATUSES = ("partial", "blocked", "UNVERIFIED", "pending")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None
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


def _entry_status(preferred_status: str, failures: list[str]) -> str:
    if not failures:
        return "verified"
    if preferred_status in _PRESERVED_STATUSES:
        return preferred_status
    return "blocked"


def _report_id_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaRevision": report.get("schemaRevision"),
        "status": report.get("status"),
        "expected_supported_variant_smoke_count": report.get(
            "expected_supported_variant_smoke_count"
        ),
        "passed_supported_variant_smoke_count": report.get(
            "passed_supported_variant_smoke_count"
        ),
        "supported_variant_simc_smoke_count": report.get(
            "supported_variant_simc_smoke_count"
        ),
        "failureCodes": list(report.get("failureCodes") or []),
        "failureSamples": list(report.get("failureSamples") or []),
        "ledger": dict(report.get("ledger") or {}),
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


def build_gear_variant_simc_matrix(
    materialization_report: Any,
    smoke_callback: SmokeCallback,
) -> dict[str, Any]:
    source = _mapping(materialization_report)
    source_status = _text(source.get("status"))
    ledger_input = _mapping(source.get("ledger"))
    expected_supported_variant_smoke_count = 0
    passed_supported_variant_smoke_count = 0
    ledger: dict[str, dict[str, Any]] = {}
    report_failure_codes: set[str] = set()
    report_failure_samples: list[dict[str, str]] = []

    if not source:
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATRIX_REPORT_MALFORMED")
    if (
        _text(source.get("schemaRevision")) != "gear-variant-materialization-matrix-v1"
    ):
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATRIX_INPUT_SCHEMA_MISMATCH")
    if not isinstance(source.get("ledger"), Mapping):
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATRIX_REPORT_MALFORMED")
    try:
        expected_unique_variant_count = int(source.get("expected_unique_variant_count"))
        materialized_unique_variant_count = int(
            source.get("unique_variant_materialization_count")
        )
        materialized_unique_variant_count_2 = int(
            source.get("materialized_unique_variant_count")
        )
    except (TypeError, ValueError):
        expected_unique_variant_count = -1
        materialized_unique_variant_count = -1
        materialized_unique_variant_count_2 = -1
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATRIX_REPORT_MALFORMED")

    if (
        expected_unique_variant_count != len(ledger_input)
        or materialized_unique_variant_count != len(ledger_input)
        or materialized_unique_variant_count_2 != len(ledger_input)
    ):
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATRIX_LEDGER_COUNT_MISMATCH")

    report_ready = (
        not report_failure_codes and source_status == "verified"
    )
    if source_status != "verified":
        report_failure_codes.add("GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY")
        report_failure_samples.append(
            _failure_sample("GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY")
        )

    for browse_variant_key in sorted(ledger_input):
        entry_source = _mapping(ledger_input.get(browse_variant_key))
        materialization_status = _text(entry_source.get("status"))
        item_id = _text(entry_source.get("itemId"))
        class_key = _text(entry_source.get("classKey"))
        spec_key = _text(entry_source.get("specKey"))
        slot = _text(entry_source.get("slot"))
        materialized_item_id = _text(entry_source.get("materializedItemId"))
        materialized_browse_variant_key = _text(
            entry_source.get("materializedBrowseVariantKey")
        )
        entry = {
            "status": "blocked",
            "materializationStatus": materialization_status,
            "itemId": item_id,
            "classKey": class_key,
            "specKey": spec_key,
            "slot": slot,
            "supportedSpecialization": None,
            "simcSupportStatus": "",
            "supportCode": "",
            "smokeInvoked": False,
            "smokeItemId": "",
            "smokeBrowseVariantKey": "",
            "smokeClassKey": "",
            "smokeSpecKey": "",
            "ran": None,
            "timedOut": None,
            "hasDps": None,
            "executionMode": "",
            "simcRuntimeRevision": "",
            "iterations": None,
            "maxTimeSeconds": None,
            "failureCodes": [],
        }
        support = simc_execution_support(class_key, spec_key)
        entry["supportedSpecialization"] = bool(support.get("supported"))
        entry["simcSupportStatus"] = _text(support.get("status"))
        entry["supportCode"] = _text(support.get("code"))
        entry_failures = _canonical_codes(entry_source.get("failureCodes"))
        preferred_status = materialization_status

        if not report_ready:
            entry["failureCodes"] = entry_failures
            entry["status"] = _entry_status(
                materialization_status or source_status,
                entry_failures or ["GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY"],
            )
            ledger[browse_variant_key] = entry
            continue

        if materialization_status not in _READY_STATUSES:
            entry_failures.append("GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY")
        if (
            not item_id
            or not class_key
            or not spec_key
            or not slot
            or not materialized_item_id
            or not materialized_browse_variant_key
        ):
            entry_failures.append("GEAR_VARIANT_SIMC_MISSING_PROVENANCE")
        if entry_source.get("failureCodes"):
            entry_failures.append("GEAR_VARIANT_SIMC_MISSING_PROVENANCE")
        if (
            materialized_item_id
            and materialized_browse_variant_key
            and (
                materialized_item_id != item_id
                or materialized_browse_variant_key != browse_variant_key
            )
        ):
            entry_failures.append("GEAR_VARIANT_SIMC_MATERIALIZATION_IDENTITY_MISMATCH")

        if support.get("supported") is not True:
            code = _text(support.get("code"))
            if code == SIMC_SPECIALIZATION_UNSUPPORTED_CODE and not entry_failures:
                entry["failureCodes"] = [SIMC_SPECIALIZATION_UNSUPPORTED_CODE]
                entry["status"] = "blocked"
                ledger[browse_variant_key] = entry
                continue
            entry_failures.append(code or SIMC_SPECIALIZATION_UNKNOWN_CODE)

        if entry_failures:
            preferred_status = materialization_status
        else:
            expected_supported_variant_smoke_count += 1
            entry["smokeInvoked"] = True
            try:
                raw_smoke = smoke_callback(
                    item_id=item_id,
                    browse_variant_key=browse_variant_key,
                    class_key=class_key,
                    spec_key=spec_key,
                    slot=slot,
                )
            except Exception:
                raw_smoke = None
                entry_failures.append("GEAR_VARIANT_SIMC_CALLBACK_EXCEPTION")
            if isinstance(raw_smoke, Mapping):
                smoke = dict(raw_smoke)
                preferred_status = _text(smoke.get("status"))
                entry["smokeItemId"] = _text(smoke.get("itemId"))
                entry["smokeBrowseVariantKey"] = _text(smoke.get("browseVariantKey"))
                entry["smokeClassKey"] = _text(smoke.get("classKey"))
                entry["smokeSpecKey"] = _text(smoke.get("specKey"))
                entry["ran"] = _bool_or_none(smoke.get("ran"))
                entry["timedOut"] = _bool_or_none(smoke.get("timedOut"))
                entry["hasDps"] = _bool_or_none(smoke.get("hasDps"))
                entry["executionMode"] = _text(smoke.get("executionMode"))
                entry["simcRuntimeRevision"] = _text(smoke.get("simcRuntimeRevision"))
                entry["iterations"] = _int_or_none(smoke.get("iterations"))
                entry["maxTimeSeconds"] = _number_or_none(smoke.get("maxTimeSeconds"))
                entry_failures.extend(_canonical_codes(smoke.get("failureCodes")))

                if preferred_status not in _READY_STATUSES:
                    entry_failures.append("GEAR_VARIANT_SIMC_STATUS_NOT_READY")
                if entry["ran"] is not True:
                    entry_failures.append("GEAR_VARIANT_SIMC_RAN_NOT_TRUE")
                if entry["timedOut"] is not False:
                    entry_failures.append("GEAR_VARIANT_SIMC_TIMED_OUT")
                if entry["hasDps"] is not True:
                    entry_failures.append("GEAR_VARIANT_SIMC_HAS_DPS_NOT_TRUE")
                if entry["executionMode"] != "real":
                    entry_failures.append("GEAR_VARIANT_SIMC_EXECUTION_MODE_NOT_REAL")
                if not entry["simcRuntimeRevision"]:
                    entry_failures.append(
                        "GEAR_VARIANT_SIMC_RUNTIME_REVISION_MISSING"
                    )
                if entry["iterations"] != 1:
                    entry_failures.append("GEAR_VARIANT_SIMC_ITERATIONS_INVALID")
                if (
                    entry["maxTimeSeconds"] is None
                    or entry["maxTimeSeconds"] <= 0
                    or entry["maxTimeSeconds"] > 5
                ):
                    entry_failures.append("GEAR_VARIANT_SIMC_MAX_TIME_INVALID")
                if (
                    entry["smokeItemId"] != item_id
                    or entry["smokeBrowseVariantKey"] != browse_variant_key
                    or entry["smokeClassKey"] != class_key
                    or entry["smokeSpecKey"] != spec_key
                ):
                    entry_failures.append("GEAR_VARIANT_SIMC_IDENTITY_MISMATCH")
            elif "GEAR_VARIANT_SIMC_CALLBACK_EXCEPTION" not in entry_failures:
                entry_failures.append("GEAR_VARIANT_SIMC_REPORT_MALFORMED")

        entry["failureCodes"] = sorted(set(_text(code) for code in entry_failures if _text(code)))
        entry["status"] = _entry_status(preferred_status, entry["failureCodes"])
        if not entry["failureCodes"] and entry["supportedSpecialization"] is True:
            passed_supported_variant_smoke_count += 1
        else:
            for code in entry["failureCodes"]:
                report_failure_codes.add(code)
                report_failure_samples.append(
                    _failure_sample(
                        code,
                        browse_variant_key=browse_variant_key,
                        item_id=item_id,
                        class_key=class_key,
                        spec_key=spec_key,
                        slot=slot,
                    )
                )
        ledger[browse_variant_key] = entry

    report_status = (
        source_status
        if source_status in {"partial", "pending", "UNVERIFIED"} and source_status != "verified"
        else "blocked"
    )
    if (
        not report_failure_codes
        and passed_supported_variant_smoke_count
        == expected_supported_variant_smoke_count
    ):
        report_status = "verified"
    elif source_status == "blocked":
        report_status = "blocked"

    report = {
        "schemaRevision": GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION,
        "status": report_status,
        "expected_supported_variant_smoke_count": expected_supported_variant_smoke_count,
        "passed_supported_variant_smoke_count": passed_supported_variant_smoke_count,
        "supported_variant_simc_smoke_count": passed_supported_variant_smoke_count,
        "failureCodes": sorted(report_failure_codes),
        "failureSamples": sorted(
            (_canonical(sample) for sample in report_failure_samples),
            key=_sample_sort_key,
        )[:_MAX_FAILURE_SAMPLES],
        "ledger": {key: _canonical(ledger[key]) for key in sorted(ledger)},
    }
    report["reportId"] = _report_id(report)
    return _canonical(report)


__all__ = [
    "GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION",
    "build_gear_variant_simc_matrix",
]
