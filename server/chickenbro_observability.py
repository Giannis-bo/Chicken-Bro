"""Bounded, text-free observability contracts for the Chickenbro agent.

This module is deliberately pure: callers own identity and persistence, while
the trace payload contains only allowlisted execution facts.
"""

import copy
import re
from datetime import datetime


TRACE_SCHEMA_REVISION_V1 = "chickenbro-agent-trace-v1"
PROJECTION_SCHEMA_REVISION_V1 = "chickenbro-trace-projection-v1"
RUNTIME_VERSION_V1 = "chickenbro-fixed-allowlist-v1"
TRACE_SCHEMA_REVISION_V2 = "chickenbro-agent-trace-v2"
PROJECTION_SCHEMA_REVISION_V2 = "chickenbro-trace-projection-v2"
RUNTIME_VERSION_V2 = "chickenbro-registry-runtime-v1"
TRACE_SCHEMA_REVISION_V3 = "chickenbro-agent-trace-v3"
PROJECTION_SCHEMA_REVISION_V3 = "chickenbro-trace-projection-v3"
RUNTIME_VERSION_V3 = "chickenbro-question-planner-runtime-v1"
TRACE_SCHEMA_REVISION_V4 = "chickenbro-agent-trace-v4"
PROJECTION_SCHEMA_REVISION_V4 = "chickenbro-trace-projection-v4"
RUNTIME_VERSION_V4 = "chickenbro-evidence-planner-runtime-v1"
TRACE_SCHEMA_REVISION = TRACE_SCHEMA_REVISION_V4
PROJECTION_SCHEMA_REVISION = PROJECTION_SCHEMA_REVISION_V4
RUNTIME_VERSION = RUNTIME_VERSION_V4

CAPABILITY_IDS = {
    "source:raiderio:v1",
    "source:warcraftlogs:v1",
    "source:current-wow-sources:v1",
    "source:raiderio-strength:v1",
    "source:warcraftlogs-public-rankings:v1",
}
SOURCE_CAPABILITY_IDS = {
    "raiderio": "source:raiderio:v1",
    "warcraftlogs": "source:warcraftlogs:v1",
    "current_wow_sources": "source:current-wow-sources:v1",
    "raiderio_strength": "source:raiderio-strength:v1",
    "warcraftlogs_public_rankings": "source:warcraftlogs-public-rankings:v1",
}
TRACE_KEYS_V1 = {
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
TRACE_KEYS_V2 = TRACE_KEYS_V1 | {
    "registryStatus",
    "registryVersion",
    "registryReleaseHash",
    "registrySource",
}
TRACE_KEYS_V3 = TRACE_KEYS_V2 | {
    "questionType",
    "subjectResolution",
    "requestedEvidenceNeeds",
    "unmetEvidenceNeeds",
}
TRACE_KEYS_V4 = TRACE_KEYS_V3 | {
    "comparisonScope",
    "evidenceFacetKeys",
    "evidenceFacetStatuses",
    "evidenceOutcome",
}
TRACE_KEYS = TRACE_KEYS_V4
REGISTRY_CONTEXT_KEYS = {
    "status",
    "registryVersion",
    "registryReleaseHash",
    "registrySource",
    "discoveredCapabilityIds",
    "selectedCapabilityIds",
}
REGISTRY_STATUSES = {"verified", "unavailable", "invalid"}
REGISTRY_SOURCES = {"postgres", "verified_cache"}
CAPABILITY_ID_PATTERN = re.compile(r"^source:[a-z0-9_.-]{1,64}:v[0-9]+$")
REGISTRY_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,95}$")
RELEASE_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
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
REQUEST_SCOPE_ALLOWED_VALUES = {
    "topicStatus": {"", "in_scope", "out_of_scope"},
    "productPhase": {"", "retail", "ptr", "beta"},
    "region": {"", "cn", "global", "us", "eu", "kr", "tw"},
    "classKey": {
        "",
        "deathknight",
        "demonhunter",
        "druid",
        "evoker",
        "hunter",
        "mage",
        "monk",
        "paladin",
        "priest",
        "rogue",
        "shaman",
        "warlock",
        "warrior",
    },
    "specKey": {
        "",
        "affliction",
        "arcane",
        "arms",
        "assassination",
        "augmentation",
        "balance",
        "beast_mastery",
        "blood",
        "brewmaster",
        "demonology",
        "destruction",
        "devastation",
        "devourer",
        "discipline",
        "elemental",
        "enhancement",
        "feral",
        "fire",
        "frost",
        "fury",
        "guardian",
        "havoc",
        "holy",
        "marksmanship",
        "mistweaver",
        "outlaw",
        "preservation",
        "protection",
        "restoration",
        "retribution",
        "shadow",
        "subtlety",
        "survival",
        "unholy",
        "vengeance",
        "windwalker",
    },
    "scenarioKey": {
        "",
        "mythic_plus",
        "mplus_fortified",
        "mplus_tyrannical",
        "raid",
        "raid_single",
        "raid_cleave",
        "raid_multi",
    },
}
SAFE_EVIDENCE_REF_PATTERNS = (
    re.compile(r"^profile\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^simc\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^wcl\.[a-z0-9_.-]{1,96}$"),
    re.compile(
        r"^raiderio:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}$"
    ),
    re.compile(
        r"^raiderio-strength:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}$"
    ),
    re.compile(r"^current\.[a-z0-9-]{1,64}\.[a-z0-9-]{1,96}$"),
)
QUESTION_TYPES = {"general", "community_build", "current_research", "personal_wcl"}
SUBJECT_RESOLUTIONS = {"resolved", "partial", "unresolved"}
EVIDENCE_NEEDS = {
    "community_build_reference",
    "comparative_strength_signal",
    "official_current_changes",
    "personal_log_evidence",
}
COMPARISON_SCOPES = {"subject", "cross_spec"}
EVIDENCE_FACET_KEYS = {
    "official_changes",
    "high_key_trend",
    "subject_performance",
    "cross_spec_performance",
}
EVIDENCE_FACET_STATUSES = {"supported", "partial", "unavailable"}
EVIDENCE_OUTCOMES = {"answered", "partial", "researching", "blocked"}


def _text(value, limit=160):
    return str(value or "").strip()[:limit]


def _scope_value(value, allowed_values):
    normalized = _text(value, 48).lower()
    return normalized if normalized in allowed_values else ""


def _capability_id(source_key):
    return SOURCE_CAPABILITY_IDS.get(_text(source_key, 48).lower(), "")


def _registry_capability_id(source_key, selected_capability_ids):
    source = _text(source_key, 64).lower()
    expected = SOURCE_CAPABILITY_IDS.get(source)
    if expected and expected in selected_capability_ids:
        return expected
    matches = [
        capability_id
        for capability_id in selected_capability_ids
        if isinstance(capability_id, str)
        and CAPABILITY_ID_PATTERN.fullmatch(capability_id)
        and capability_id.split(":")[1] == source
    ]
    return matches[0] if len(matches) == 1 else ""


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
        "topicStatus": _scope_value(
            topic.get("status"), REQUEST_SCOPE_ALLOWED_VALUES["topicStatus"]
        ),
        "productPhase": _scope_value(
            request.get("productPhase"),
            REQUEST_SCOPE_ALLOWED_VALUES["productPhase"],
        ),
        "region": _scope_value(
            request.get("region"), REQUEST_SCOPE_ALLOWED_VALUES["region"]
        ),
        "classKey": _scope_value(
            request.get("classKey"), REQUEST_SCOPE_ALLOWED_VALUES["classKey"]
        ),
        "specKey": _scope_value(
            request.get("specKey"), REQUEST_SCOPE_ALLOWED_VALUES["specKey"]
        ),
        "scenarioKey": _scope_value(
            request.get("scenarioKey"),
            REQUEST_SCOPE_ALLOWED_VALUES["scenarioKey"],
        ),
    }


def _freshness_state(status):
    if status in {"verified", "source_reference"}:
        return "fresh"
    if status == "stale":
        return "stale"
    if status in {"blocked", "failed", "missing_credentials"}:
        return "unavailable"
    return "unknown"


def _trace_question_plan(context):
    frame = context.get("questionFrame") if isinstance(context.get("questionFrame"), dict) else {}
    plan = context.get("capabilityPlan") if isinstance(context.get("capabilityPlan"), dict) else {}
    subject = frame.get("subject") if isinstance(frame.get("subject"), dict) else {}
    question_type = _text(frame.get("questionType"), 48).lower()
    if question_type not in QUESTION_TYPES:
        question_type = "general"
    resolution = _text(subject.get("resolution"), 32).lower()
    if resolution not in SUBJECT_RESOLUTIONS:
        resolution = "unresolved"
    requested = []
    for value in plan.get("requestedEvidenceNeeds") or frame.get("evidenceNeeds") or []:
        value = _text(value, 64)
        if value in EVIDENCE_NEEDS and value not in requested:
            requested.append(value)
    unmet = []
    for value in plan.get("unmetEvidenceNeeds") or []:
        value = _text(value, 64)
        if value in requested and value not in unmet:
            unmet.append(value)
    return {
        "questionType": question_type,
        "subjectResolution": resolution,
        "requestedEvidenceNeeds": requested,
        "unmetEvidenceNeeds": unmet,
    }


def _trace_evidence_plan(context):
    frame = context.get("questionFrame") if isinstance(context.get("questionFrame"), dict) else {}
    plan = context.get("evidencePlan") if isinstance(context.get("evidencePlan"), dict) else {}
    comparison_scope = _text(plan.get("comparisonScope") or frame.get("comparisonScope"), 32).lower()
    if comparison_scope not in COMPARISON_SCOPES:
        comparison_scope = "subject"
    facet_keys = []
    facet_statuses = []
    for facet in plan.get("facets") or []:
        if not isinstance(facet, dict):
            continue
        key = _text(facet.get("key"), 64).lower()
        status = _text(facet.get("status"), 32).lower()
        if (
            key not in EVIDENCE_FACET_KEYS
            or status not in EVIDENCE_FACET_STATUSES
            or key in facet_keys
        ):
            continue
        facet_keys.append(key)
        facet_statuses.append(status)
    outcome = _text(plan.get("outcome"), 32).lower()
    if outcome not in EVIDENCE_OUTCOMES:
        outcome = "partial"
    return {
        "comparisonScope": comparison_scope,
        "evidenceFacetKeys": facet_keys,
        "evidenceFacetStatuses": facet_statuses,
        "evidenceOutcome": outcome,
    }


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

    registry_context = (
        context.get("registryContext")
        if isinstance(context.get("registryContext"), dict)
        else None
    )
    question_plan = _trace_question_plan(context)
    evidence_plan = _trace_evidence_plan(context)
    registry_selected = (
        list(registry_context.get("selectedCapabilityIds") or [])
        if registry_context is not None
        and isinstance(registry_context.get("selectedCapabilityIds"), list)
        else []
    )
    source_rows = [
        row for row in context.get("sourceEvidence") or [] if isinstance(row, dict)
    ][:8]
    tool_statuses = []
    evidence_refs = []
    for row in source_rows:
        capability_id = (
            _registry_capability_id(row.get("sourceKey"), registry_selected)
            if registry_context is not None
            else _capability_id(row.get("sourceKey"))
        )
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
    ) or question_plan["unmetEvidenceNeeds"]:
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
    trace = {
        "schemaRevision": TRACE_SCHEMA_REVISION_V1,
        "runtimeVersion": RUNTIME_VERSION_V1,
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
    if registry_context is not None:
        trace.update(
            {
                "schemaRevision": TRACE_SCHEMA_REVISION,
                "runtimeVersion": RUNTIME_VERSION,
                "selectionMode": "registry",
                "registryStatus": _text(registry_context.get("status"), 32).lower(),
                "registryVersion": _text(
                    registry_context.get("registryVersion"), 96
                ).lower(),
                "registryReleaseHash": _text(
                    registry_context.get("registryReleaseHash"), 80
                ).lower(),
                "registrySource": _text(
                    registry_context.get("registrySource"), 32
                ).lower(),
                "discoveredCapabilityIds": copy.deepcopy(
                    registry_context.get("discoveredCapabilityIds")
                ),
                "selectedCapabilityIds": copy.deepcopy(
                    registry_context.get("selectedCapabilityIds")
                ),
                **question_plan,
                **evidence_plan,
            }
        )
    return validate_chickenbro_agent_trace(trace)


def _validate_v1_capability_ids(values, field_name):
    if not isinstance(values, list) or any(value not in CAPABILITY_IDS for value in values):
        raise ValueError(f"invalid chickenbro trace {field_name} capability")
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate chickenbro trace {field_name} capability")


def _validate_v2_capability_ids(values, field_name):
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not CAPABILITY_ID_PATTERN.fullmatch(value)
        for value in values
    ):
        raise ValueError(f"invalid chickenbro trace {field_name} capability")
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate chickenbro trace {field_name} capability")


def validate_chickenbro_agent_trace(trace):
    """Reject payload drift and return a defensive copy of a valid trace."""

    if not isinstance(trace, dict):
        raise ValueError("invalid chickenbro trace keys")
    schema_revision = trace.get("schemaRevision")
    if schema_revision == TRACE_SCHEMA_REVISION_V1:
        if set(trace) != TRACE_KEYS_V1:
            raise ValueError("invalid chickenbro trace keys")
        if (
            trace["runtimeVersion"] != RUNTIME_VERSION_V1
            or trace["selectionMode"] != "fixed_allowlist"
        ):
            raise ValueError("invalid chickenbro trace runtime identity")
        capability_validator = _validate_v1_capability_ids
    elif schema_revision in {TRACE_SCHEMA_REVISION_V2, TRACE_SCHEMA_REVISION_V3, TRACE_SCHEMA_REVISION_V4}:
        expected_keys = {
            TRACE_SCHEMA_REVISION_V2: TRACE_KEYS_V2,
            TRACE_SCHEMA_REVISION_V3: TRACE_KEYS_V3,
            TRACE_SCHEMA_REVISION_V4: TRACE_KEYS_V4,
        }[schema_revision]
        expected_runtime = {
            TRACE_SCHEMA_REVISION_V2: RUNTIME_VERSION_V2,
            TRACE_SCHEMA_REVISION_V3: RUNTIME_VERSION_V3,
            TRACE_SCHEMA_REVISION_V4: RUNTIME_VERSION_V4,
        }[schema_revision]
        if set(trace) != expected_keys:
            raise ValueError("invalid chickenbro trace keys")
        if (
            trace["runtimeVersion"] != expected_runtime
            or trace["selectionMode"] != "registry"
        ):
            raise ValueError("invalid chickenbro trace runtime identity")
        capability_validator = _validate_v2_capability_ids
        registry_status = trace["registryStatus"]
        if registry_status not in REGISTRY_STATUSES:
            raise ValueError("invalid chickenbro trace registry status")
        if registry_status == "verified":
            if not REGISTRY_VERSION_PATTERN.fullmatch(trace["registryVersion"]):
                raise ValueError("invalid chickenbro trace registry version")
            if not RELEASE_HASH_PATTERN.fullmatch(trace["registryReleaseHash"]):
                raise ValueError("invalid chickenbro trace registry release hash")
            if trace["registrySource"] not in REGISTRY_SOURCES:
                raise ValueError("invalid chickenbro trace registry source")
        elif any(
            (
                trace["registryVersion"],
                trace["registryReleaseHash"],
                trace["registrySource"],
                trace["discoveredCapabilityIds"],
                trace["selectedCapabilityIds"],
            )
        ):
            raise ValueError("invalid chickenbro trace unverified registry identity")
        if schema_revision in {TRACE_SCHEMA_REVISION_V3, TRACE_SCHEMA_REVISION_V4}:
            if trace["questionType"] not in QUESTION_TYPES:
                raise ValueError("invalid chickenbro trace question type")
            if trace["subjectResolution"] not in SUBJECT_RESOLUTIONS:
                raise ValueError("invalid chickenbro trace subject resolution")
            for field_name in ("requestedEvidenceNeeds", "unmetEvidenceNeeds"):
                values = trace[field_name]
                if not isinstance(values, list) or any(
                    not isinstance(value, str) or value not in EVIDENCE_NEEDS
                    for value in values
                ):
                    raise ValueError(f"invalid chickenbro trace {field_name}")
                if len(values) != len(set(values)):
                    raise ValueError(f"duplicate chickenbro trace {field_name}")
            if not set(trace["unmetEvidenceNeeds"]).issubset(trace["requestedEvidenceNeeds"]):
                raise ValueError("unrequested chickenbro trace unmet evidence")
        if schema_revision == TRACE_SCHEMA_REVISION_V4:
            if trace["comparisonScope"] not in COMPARISON_SCOPES:
                raise ValueError("invalid chickenbro trace comparison scope")
            facet_keys = trace["evidenceFacetKeys"]
            facet_statuses = trace["evidenceFacetStatuses"]
            if (
                not isinstance(facet_keys, list)
                or not isinstance(facet_statuses, list)
                or len(facet_keys) != len(facet_statuses)
                or any(not isinstance(value, str) or value not in EVIDENCE_FACET_KEYS for value in facet_keys)
                or any(not isinstance(value, str) or value not in EVIDENCE_FACET_STATUSES for value in facet_statuses)
                or len(facet_keys) != len(set(facet_keys))
            ):
                raise ValueError("invalid chickenbro trace evidence facets")
            if trace["evidenceOutcome"] not in EVIDENCE_OUTCOMES:
                raise ValueError("invalid chickenbro trace evidence outcome")
    else:
        raise ValueError("invalid chickenbro trace schema revision")
    request_scope = trace["requestScope"]
    if not isinstance(request_scope, dict) or set(request_scope) != REQUEST_SCOPE_KEYS:
        raise ValueError("invalid chickenbro trace request scope")
    for key, value in request_scope.items():
        if not isinstance(value, str) or value not in REQUEST_SCOPE_ALLOWED_VALUES[key]:
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

    capability_validator(trace["discoveredCapabilityIds"], "discovered")
    capability_validator(trace["selectedCapabilityIds"], "selected")
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
    tool_capability_ids = []
    for row in tool_statuses:
        if not isinstance(row, dict) or set(row) != TOOL_STATUS_KEYS:
            raise ValueError("invalid chickenbro trace tool status")
        if row["capabilityId"] not in trace["selectedCapabilityIds"]:
            raise ValueError("unselected chickenbro trace capability")
        tool_capability_ids.append(row["capabilityId"])
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
    if len(tool_capability_ids) != len(set(tool_capability_ids)):
        raise ValueError("duplicate chickenbro trace tool status capability")
    if schema_revision in {TRACE_SCHEMA_REVISION_V2, TRACE_SCHEMA_REVISION_V3, TRACE_SCHEMA_REVISION_V4} and set(tool_capability_ids) != set(
        trace["selectedCapabilityIds"]
    ):
        raise ValueError("missing chickenbro trace selected tool status")

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
    projection = {
        "schemaRevision": PROJECTION_SCHEMA_REVISION_V1,
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
    if validated["schemaRevision"] in {TRACE_SCHEMA_REVISION_V2, TRACE_SCHEMA_REVISION_V3, TRACE_SCHEMA_REVISION_V4}:
        projection.update(
            {
                "schemaRevision": (
                    PROJECTION_SCHEMA_REVISION_V2
                    if validated["schemaRevision"] == TRACE_SCHEMA_REVISION_V2
                    else (
                        PROJECTION_SCHEMA_REVISION_V3
                        if validated["schemaRevision"] == TRACE_SCHEMA_REVISION_V3
                        else PROJECTION_SCHEMA_REVISION_V4
                    )
                ),
                "registryStatus": validated["registryStatus"],
                "registryVersion": validated["registryVersion"],
                "registryReleaseHash": validated["registryReleaseHash"],
                "registrySource": validated["registrySource"],
                "discoveredCapabilityIds": list(
                    validated["discoveredCapabilityIds"]
                ),
            }
        )
    if validated["schemaRevision"] in {TRACE_SCHEMA_REVISION_V3, TRACE_SCHEMA_REVISION_V4}:
        projection.update(
            {
                "questionType": validated["questionType"],
                "subjectResolution": validated["subjectResolution"],
                "requestedEvidenceNeeds": list(validated["requestedEvidenceNeeds"]),
                "unmetEvidenceNeeds": list(validated["unmetEvidenceNeeds"]),
            }
        )
    if validated["schemaRevision"] == TRACE_SCHEMA_REVISION_V4:
        projection.update(
            {
                "comparisonScope": validated["comparisonScope"],
                "evidenceFacetKeys": list(validated["evidenceFacetKeys"]),
                "evidenceFacetStatuses": list(validated["evidenceFacetStatuses"]),
                "evidenceOutcome": validated["evidenceOutcome"],
            }
        )
    return projection
