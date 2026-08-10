"""HTTP callback runner for candidate Resolver/Profile materialization."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping

EXPECTED_RELEASE_CONTEXT_FIELDS = (
    "manifestRevision",
    "pointerGeneration",
    "gearCatalogRevision",
    "gearExactRegistryRevision",
    "simcRuntimeRevision",
)

_READY_STATUSES = {"resolved", "verified"}
_PRESERVED_STATUSES = ("partial", "blocked", "UNVERIFIED", "pending")
_JSON_HEADERS = {"Content-Type": "application/json"}

RequestJson = Callable[..., Any]
ProfileContextFactory = Callable[..., Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _canonical_mapping(value: Any) -> dict[str, Any]:
    return dict(_canonical(value)) if isinstance(value, Mapping) else {}


def _preserved_status(*values: Any) -> str:
    for raw in values:
        if raw in _PRESERVED_STATUSES:
            return str(raw)
    return "blocked"


def _normalize_http_result(raw_result: Any) -> tuple[int, Any]:
    if isinstance(raw_result, tuple):
        if len(raw_result) == 2:
            http_status, payload = raw_result
            return int(http_status), payload
        if len(raw_result) == 3:
            http_status, payload, _latency = raw_result
            return int(http_status), payload
    raise ValueError("request callback must return (http_status, payload[, latency])")


def _normalize_identity_value(field: str, value: Any) -> Any:
    if field == "pointerGeneration":
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None
    return _text(value)


def _validate_release_context(
    stage: str,
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for field in EXPECTED_RELEASE_CONTEXT_FIELDS:
        if field not in expected:
            continue
        expected_value = _normalize_identity_value(field, expected.get(field))
        actual_value = _normalize_identity_value(field, actual.get(field))
        if actual_value != expected_value:
            issues.append(
                {
                    "code": f"MATERIALIZATION_RUNNER_{stage.upper()}_RELEASE_CONTEXT_MISMATCH",
                    "stage": stage,
                    "field": field,
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )
    return issues


def build_gear_variant_materialization_runner(
    *,
    request_json: RequestJson,
    profile_context_factory: ProfileContextFactory,
    expected_release_context: Mapping[str, Any] | None = None,
) -> Callable[..., dict[str, Any]]:
    expected_context = _canonical_mapping(expected_release_context or {})

    def materialize(
        *,
        item_id: Any,
        browse_variant_key: Any,
        class_key: Any,
        spec_key: Any,
        slot: Any,
        selection_intent: Any,
    ) -> dict[str, Any]:
        safe_selection_intent = _canonical_mapping(selection_intent)
        safe_profile_context = _canonical_mapping(
            profile_context_factory(
                item_id=_text(item_id),
                browse_variant_key=_text(browse_variant_key),
                class_key=_text(class_key),
                spec_key=_text(spec_key),
                slot=_text(slot),
                selection_intent=_canonical(safe_selection_intent),
            )
        )
        failure_codes: list[str] = []
        release_context_issues: list[dict[str, Any]] = []
        report = {
            "status": "blocked",
            "selectionIntent": _canonical(safe_selection_intent),
            "profileContext": _canonical(safe_profile_context),
            "usedDefaultVariant": False,
            "materializedItemId": "",
            "materializedBrowseVariantKey": "",
            "resolverStatus": "",
            "profileStatus": "",
            "profileReadinessStatus": "",
            "simcReady": None,
            "resolverHttpStatus": 0,
            "profileHttpStatus": 0,
            "failureCodes": [],
            "releaseContextIssues": [],
        }

        try:
            resolve_http_status, resolve_payload = _normalize_http_result(
                request_json(
                    "POST",
                    "/api/websim/gear/resolve",
                    _canonical(safe_selection_intent),
                    dict(_JSON_HEADERS),
                )
            )
        except Exception:
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVER_REQUEST_FAILED")
            report["failureCodes"] = sorted(set(failure_codes))
            return _canonical(report)

        report["resolverHttpStatus"] = resolve_http_status
        resolve_envelope = _mapping(resolve_payload)
        resolve_data = _mapping(resolve_envelope.get("data"))
        resolve_envelope_status = _text(resolve_envelope.get("status"))
        resolve_snapshot_status = _text(resolve_data.get("status"))
        report["resolverStatus"] = resolve_snapshot_status or resolve_envelope_status

        if resolve_http_status != 200:
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVER_HTTP_STATUS_INVALID")
        if not resolve_envelope or not resolve_data:
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVER_ENVELOPE_MALFORMED")
        if (
            resolve_envelope_status not in _READY_STATUSES
            or resolve_snapshot_status not in _READY_STATUSES
        ):
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVER_STATUS_NOT_READY")

        resolved_slots = _mapping(resolve_data.get("resolvedSlots"))
        resolved_slot = _mapping(resolved_slots.get(_text(slot)))
        actual_item_id = _text(resolved_slot.get("itemId"))
        actual_variant_key = _text(
            resolved_slot.get("browseVariantKey") or resolved_slot.get("variantKey")
        )
        report["materializedItemId"] = actual_item_id
        report["materializedBrowseVariantKey"] = actual_variant_key
        if not resolved_slot:
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVED_SLOT_MISSING")
        elif (
            actual_item_id != _text(item_id)
            or actual_variant_key != _text(browse_variant_key)
        ):
            failure_codes.append("MATERIALIZATION_RUNNER_RESOLVED_PAIR_MISMATCH")

        resolve_release_context = _canonical_mapping(resolve_envelope.get("releaseContext"))

        if failure_codes:
            report["status"] = _preserved_status(
                resolve_snapshot_status,
                resolve_envelope_status,
            )
            report["failureCodes"] = sorted(set(failure_codes))
            return _canonical(report)

        try:
            profile_http_status, profile_payload = _normalize_http_result(
                request_json(
                    "POST",
                    "/api/websim/profile",
                    {
                        "selectionIntent": _canonical(safe_selection_intent),
                        "profileContext": _canonical(safe_profile_context),
                    },
                    dict(_JSON_HEADERS),
                )
            )
        except Exception:
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_REQUEST_FAILED")
            report["failureCodes"] = sorted(set(failure_codes))
            return _canonical(report)

        report["profileHttpStatus"] = profile_http_status
        profile_envelope = _mapping(profile_payload)
        profile_data = _mapping(profile_envelope.get("data"))
        profile_envelope_status = _text(profile_envelope.get("status"))
        profile_status = _text(profile_data.get("status"))
        profile_readiness = _mapping(profile_data.get("profileReadiness"))
        profile_readiness_status = _text(profile_readiness.get("status"))
        report["profileStatus"] = profile_status or profile_envelope_status
        report["profileReadinessStatus"] = profile_readiness_status
        report["simcReady"] = (
            profile_readiness.get("simcReady")
            if isinstance(profile_readiness.get("simcReady"), bool)
            else None
        )

        if profile_http_status != 200:
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_HTTP_STATUS_INVALID")
        if not profile_envelope or not profile_data:
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_ENVELOPE_MALFORMED")
        if (
            profile_envelope_status not in _READY_STATUSES
            or profile_status not in _READY_STATUSES
        ):
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_STATUS_NOT_READY")
        if not _text(profile_data.get("profile")):
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_EMPTY")
        if profile_readiness_status != "verified":
            failure_codes.append(
                "MATERIALIZATION_RUNNER_PROFILE_READINESS_STATUS_NOT_READY"
            )
        if report["simcReady"] is not True:
            failure_codes.append("MATERIALIZATION_RUNNER_PROFILE_SIMC_NOT_READY")

        profile_release_context = _canonical_mapping(profile_envelope.get("releaseContext"))
        release_context_issues.extend(
            _validate_release_context("resolver", resolve_release_context, expected_context)
        )
        release_context_issues.extend(
            _validate_release_context("profile", profile_release_context, expected_context)
        )
        failure_codes.extend(issue["code"] for issue in release_context_issues)

        report["releaseContextIssues"] = _canonical(release_context_issues)
        if failure_codes:
            report["status"] = _preserved_status(
                profile_status,
                profile_envelope_status,
                profile_readiness_status,
                resolve_snapshot_status,
                resolve_envelope_status,
            )
            report["failureCodes"] = sorted(set(failure_codes))
            return _canonical(report)

        report["status"] = "verified"
        report["failureCodes"] = []
        return _canonical(report)

    return materialize


__all__ = [
    "EXPECTED_RELEASE_CONTEXT_FIELDS",
    "build_gear_variant_materialization_runner",
]
