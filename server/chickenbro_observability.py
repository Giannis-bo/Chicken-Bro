"""Bounded, text-free observability contracts for the Chickenbro agent.

This module is deliberately pure: callers own identity and persistence, while
the trace payload contains only allowlisted execution facts.
"""

import copy
import re
from datetime import datetime


TRACE_SCHEMA_REVISION = "chickenbro-agent-trace-v1"
PROJECTION_SCHEMA_REVISION = "chickenbro-trace-projection-v1"
RUNTIME_VERSION = "chickenbro-fixed-allowlist-v1"

CAPABILITY_IDS = {
    "source:raiderio:v1",
    "source:warcraftlogs:v1",
}
SOURCE_CAPABILITY_IDS = {
    "raiderio": "source:raiderio:v1",
    "warcraftlogs": "source:warcraftlogs:v1",
}
TRACE_KEYS = {
    "schemaRevision",
    "runtimeVersion",
    "selectionMode",
    "requestScope",
    "discoveredCapabilityIds",
    "selectedCapabilityIds",
    "toolStatuses",
    "evidenceRefs",
    "answerStatus",
    "validationStatus",
    "outcomeSignals",
    "latencyMs",
    "boundedCost",
    "createdAt",
}
REQUEST_SCOPE_KEYS = {
    "topicStatus",
    "productPhase",
    "region",
    "classKey",
    "specKey",
    "scenarioKey",
}
TOOL_STATUS_KEYS = {
    "capabilityId",
    "status",
    "freshnessState",
    "evidenceCount",
}
TOOL_STATUSES = {
    "blocked",
    "failed",
    "missing_credentials",
    "partial",
    "source_reference",
    "stale",
    "unknown",
    "verified",
}
SIGNAL_CODES = {
    "answer_succeeded",
    "model_failed",
    "tool_failed",
    "evidence_missing",
    "schema_invalid",
    "verification_conflict",
    "explicit_correction",
}
SIGNAL_SEVERITIES = {"info", "warning", "error"}
SAFE_SCOPE_VALUE = re.compile(r"^[a-z0-9_-]{0,48}$")
SAFE_EVIDENCE_REF_PATTERNS = (
    re.compile(r"^profile\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^simc\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^wcl\.[a-z0-9_.-]{1,96}$"),
    re.compile(
        r"^raiderio:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}$"
    ),
)


def _text(value, limit=160):
    return str(value or "").strip()[:limit]


def _scope_value(value):
    normalized = _text(value, 48).lower()
    return normalized if SAFE_SCOPE_VALUE.fullmatch(normalized) else ""


def _capability_id(source_key):
    return SOURCE_CAPABILITY_IDS.get(_text(source_key, 48).lower(), "")


def _safe_evidence_ref(value):
    ref = _text(value, 160).lower()
    return ref if any(pattern.fullmatch(ref) for pattern in SAFE_EVIDENCE_REF_PATTERNS) else ""


def _request_scope(bounded_context):
    context = bounded_context if isinstance(bounded_context, dict) else {}
    request = (
        context.get("requestContext")
        if isinstance(context.get("requestContext"), dict)
        else {}
    )
    topic = context.get("topic") if isinstance(context.get("topic"), dict) else {}
    return {
        "topicStatus": _scope_value(topic.get("status")),
        "productPhase": _scope_value(request.get("productPhase")),
        "region": _scope_value(request.get("region")),
        "classKey": _scope_value(request.get("classKey")),
        "specKey": _scope_value(request.get("specKey")),
        "scenarioKey": _scope_value(request.get("scenarioKey")),
    }


def _freshness_state(status):
    if status in {"verified", "source_reference"}:
        return "fresh"
    if status == "stale":
        return "stale"
    if status in {"blocked", "failed", "missing_credentials"}:
        return "unavailable"
    return "unknown"


def build_chickenbro_agent_trace(
    *, bounded_context, agent_result, error, latency_ms, created_at
):
    """Build a terminal trace from allowlisted execution facts only."""

    context = bounded_context if isinstance(bounded_context, dict) else {}
    result = agent_result if isinstance(agent_result, dict) else {}
    validation = (
        result.get("validation") if isinstance(result.get("validation"), dict) else {}
    )
    model = result.get("model") if isinstance(result.get("model"), dict) else {}
    validation_status = _text(validation.get("status"), 32).lower()
    validation_status = validation_status if validation_status in {"passed", "failed"} else "failed"
    model_status = _text(model.get("status"), 32).lower()
    if validation_status == "passed":
        answer_status = "succeeded"
    elif model_status in {"failed", "timed_out", "skipped"}:
        answer_status = model_status
    else:
        answer_status = "failed"

    source_rows = [
        row for row in context.get("sourceEvidence") or [] if isinstance(row, dict)
    ][:8]
    tool_statuses = []
    evidence_refs = []
    for row in source_rows:
        capability_id = _capability_id(row.get("sourceKey"))
        if not capability_id:
            continue
        raw_status = _text(row.get("status"), 32).lower()
        status = raw_status if raw_status in TOOL_STATUSES else "unknown"
        safe_refs = [
            ref
            for ref in (
                _safe_evidence_ref(value) for value in row.get("evidenceRefs") or []
            )
            if ref
        ]
        for ref in safe_refs:
            if ref not in evidence_refs:
                evidence_refs.append(ref)
        tool_statuses.append(
            {
                "capabilityId": capability_id,
                "status": status,
                "freshnessState": _freshness_state(status),
                "evidenceCount": len(safe_refs),
            }
        )

    signal_codes = []
    if answer_status == "succeeded":
        signal_codes.append(("answer_succeeded", "info"))
    else:
        signal_codes.append(("model_failed", "error"))
    if any(row["status"] in {"blocked", "failed"} for row in tool_statuses):
        signal_codes.append(("tool_failed", "error"))
    if any(
        row["status"] in {"stale", "blocked", "failed", "missing_credentials"}
        or row["evidenceCount"] == 0
        for row in tool_statuses
    ):
        signal_codes.append(("evidence_missing", "warning"))
    normalized_error = _text(error, 240).lower()
    if any(
        token in normalized_error
        for token in ("invalid model json", "schema", "model_output_invalid")
    ):
        signal_codes.append(("schema_invalid", "error"))
    if any(
        token in normalized_error
        for token in ("unknown evidence ref", "unapproved number")
    ):
        signal_codes.append(("verification_conflict", "error"))

    seen_signals = set()
    outcome_signals = []
    for code, severity in signal_codes:
        if code in seen_signals:
            continue
        outcome_signals.append({"code": code, "severity": severity})
        seen_signals.add(code)

    capability_ids = sorted({row["capabilityId"] for row in tool_statuses})
    return validate_chickenbro_agent_trace(
        {
            "schemaRevision": TRACE_SCHEMA_REVISION,
            "runtimeVersion": RUNTIME_VERSION,
            "selectionMode": "fixed_allowlist",
            "requestScope": _request_scope(context),
            "discoveredCapabilityIds": capability_ids,
            "selectedCapabilityIds": capability_ids,
            "toolStatuses": tool_statuses,
            "evidenceRefs": evidence_refs,
            "answerStatus": answer_status,
            "validationStatus": validation_status,
            "outcomeSignals": outcome_signals,
            "latencyMs": max(0, int(latency_ms or 0)),
            "boundedCost": {"status": "not_available"},
            "createdAt": _text(created_at, 80),
        }
    )


def _validate_capability_ids(values, field_name):
    if not isinstance(values, list) or any(value not in CAPABILITY_IDS for value in values):
        raise ValueError(f"invalid chickenbro trace {field_name} capability")
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate chickenbro trace {field_name} capability")


def validate_chickenbro_agent_trace(trace):
    """Reject payload drift and return a defensive copy of a valid trace."""

    if not isinstance(trace, dict) or set(trace) != TRACE_KEYS:
        raise ValueError("invalid chickenbro trace keys")
    if trace["schemaRevision"] != TRACE_SCHEMA_REVISION:
        raise ValueError("invalid chickenbro trace schema revision")
    if (
        trace["runtimeVersion"] != RUNTIME_VERSION
        or trace["selectionMode"] != "fixed_allowlist"
    ):
        raise ValueError("invalid chickenbro trace runtime identity")
    request_scope = trace["requestScope"]
    if not isinstance(request_scope, dict) or set(request_scope) != REQUEST_SCOPE_KEYS:
        raise ValueError("invalid chickenbro trace request scope")
    if any(
        not isinstance(value, str) or not SAFE_SCOPE_VALUE.fullmatch(value)
        for value in request_scope.values()
    ):
        raise ValueError("invalid chickenbro trace request scope value")
    if trace["answerStatus"] not in {"succeeded", "failed", "timed_out", "skipped"}:
        raise ValueError("invalid chickenbro trace answer status")
    if trace["validationStatus"] not in {"passed", "failed"}:
        raise ValueError("invalid chickenbro trace validation status")
    if (
        not isinstance(trace["latencyMs"], int)
        or isinstance(trace["latencyMs"], bool)
        or trace["latencyMs"] < 0
    ):
        raise ValueError("invalid chickenbro trace latency")
    try:
        created_at = datetime.fromisoformat(str(trace["createdAt"]).replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid chickenbro trace createdAt") from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("invalid chickenbro trace createdAt timezone")

    _validate_capability_ids(trace["discoveredCapabilityIds"], "discovered")
    _validate_capability_ids(trace["selectedCapabilityIds"], "selected")
    if not set(trace["selectedCapabilityIds"]).issubset(trace["discoveredCapabilityIds"]):
        raise ValueError("undiscovered chickenbro trace capability")

    evidence_refs = trace["evidenceRefs"]
    if not isinstance(evidence_refs, list) or any(
        not isinstance(value, str) or _safe_evidence_ref(value) != value
        for value in evidence_refs
    ):
        raise ValueError("invalid chickenbro trace evidence refs")
    if len(evidence_refs) != len(set(evidence_refs)):
        raise ValueError("duplicate chickenbro trace evidence refs")

    tool_statuses = trace["toolStatuses"]
    if not isinstance(tool_statuses, list):
        raise ValueError("invalid chickenbro trace tool statuses")
    for row in tool_statuses:
        if not isinstance(row, dict) or set(row) != TOOL_STATUS_KEYS:
            raise ValueError("invalid chickenbro trace tool status")
        if row["capabilityId"] not in trace["selectedCapabilityIds"]:
            raise ValueError("unselected chickenbro trace capability")
        if row["status"] not in TOOL_STATUSES:
            raise ValueError("invalid chickenbro trace tool status value")
        if row["freshnessState"] not in {"fresh", "stale", "unavailable", "unknown"}:
            raise ValueError("invalid chickenbro trace freshness state")
        if (
            not isinstance(row["evidenceCount"], int)
            or isinstance(row["evidenceCount"], bool)
            or row["evidenceCount"] < 0
        ):
            raise ValueError("invalid chickenbro trace evidence count")

    outcome_signals = trace["outcomeSignals"]
    if not isinstance(outcome_signals, list):
        raise ValueError("invalid chickenbro trace outcome signals")
    seen_signals = set()
    for signal in outcome_signals:
        if not isinstance(signal, dict) or set(signal) != {"code", "severity"}:
            raise ValueError("invalid chickenbro trace outcome signal")
        if signal["code"] not in SIGNAL_CODES or signal["severity"] not in SIGNAL_SEVERITIES:
            raise ValueError("unknown chickenbro trace outcome signal")
        if signal["code"] in seen_signals:
            raise ValueError("duplicate chickenbro trace outcome signal")
        seen_signals.add(signal["code"])
    if trace["boundedCost"] != {"status": "not_available"}:
        raise ValueError("invalid chickenbro trace cost state")
    return copy.deepcopy(trace)


def deidentify_chickenbro_agent_trace(trace):
    """Produce a text-free, identity-free projection suitable for offline eval."""

    validated = validate_chickenbro_agent_trace(trace)
    latency = validated["latencyMs"]
    if latency <= 1000:
        latency_bucket = "le_1s"
    elif latency <= 5000:
        latency_bucket = "le_5s"
    elif latency <= 15000:
        latency_bucket = "le_15s"
    else:
        latency_bucket = "gt_15s"
    signature_parts = [
        validated["requestScope"]["topicStatus"],
        validated["requestScope"]["productPhase"],
        validated["requestScope"]["region"],
        validated["requestScope"]["classKey"],
        validated["requestScope"]["specKey"],
        validated["requestScope"]["scenarioKey"],
        ",".join(sorted(item["code"] for item in validated["outcomeSignals"])),
    ]
    return {
        "schemaRevision": PROJECTION_SCHEMA_REVISION,
        "problemSignature": ":".join(signature_parts),
        "requestScope": dict(validated["requestScope"]),
        "selectionMode": validated["selectionMode"],
        "selectedCapabilityIds": list(validated["selectedCapabilityIds"]),
        "toolStatuses": [dict(item) for item in validated["toolStatuses"]],
        "answerStatus": validated["answerStatus"],
        "validationStatus": validated["validationStatus"],
        "outcomeSignals": [dict(item) for item in validated["outcomeSignals"]],
        "latencyBucket": latency_bucket,
        "costStatus": validated["boundedCost"]["status"],
    }
