"""Offline deterministic evaluation for Chickenbro observability traces."""

import copy
import json
import re
from pathlib import Path

from server.chickenbro_observability import (
    CAPABILITY_IDS,
    SAFE_SCOPE_VALUE,
    SIGNAL_CODES,
    SOURCE_CAPABILITY_IDS,
    TOOL_STATUSES,
    _safe_evidence_ref,
    build_chickenbro_agent_trace,
    deidentify_chickenbro_agent_trace,
)


EVAL_CASE_SCHEMA_REVISION = "chickenbro-trace-eval-case-v1"
EVAL_SUMMARY_SCHEMA_REVISION = "chickenbro-trace-eval-summary-v1"
EVAL_CASE_KEYS = {"schemaRevision", "caseId", "input", "expect"}
EVAL_INPUT_KEYS = {"boundedContext", "agentResult", "errorCode", "latencyMs"}
EVAL_EXPECT_KEYS = {
    "answerStatus",
    "requiredSignals",
    "forbiddenSignals",
    "selectedCapabilityIds",
}
BOUNDED_CONTEXT_KEYS = {"topic", "requestContext", "sourceEvidence"}
REQUEST_CONTEXT_KEYS = {
    "productPhase",
    "region",
    "classKey",
    "specKey",
    "scenarioKey",
}
SOURCE_EVIDENCE_KEYS = {"sourceKey", "status", "evidenceRefs"}
EVAL_ERROR_CODES = {
    "",
    "source_blocked",
    "model_output_invalid",
    "model_output_invalid: unknown evidence ref",
}
CASE_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,80}$")


def _validate_string_list(values, *, name, allowed):
    if not isinstance(values, list) or any(
        not isinstance(value, str) or value not in allowed for value in values
    ):
        raise ValueError(f"invalid chickenbro eval {name}")
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate chickenbro eval {name}")


def _validate_bounded_context(bounded_context):
    if not isinstance(bounded_context, dict) or set(bounded_context) != BOUNDED_CONTEXT_KEYS:
        raise ValueError("invalid chickenbro eval bounded context keys")
    topic = bounded_context["topic"]
    if not isinstance(topic, dict) or set(topic) != {"status"}:
        raise ValueError("invalid chickenbro eval topic keys")
    if not isinstance(topic["status"], str) or not SAFE_SCOPE_VALUE.fullmatch(topic["status"]):
        raise ValueError("invalid chickenbro eval topic status")

    request_context = bounded_context["requestContext"]
    if not isinstance(request_context, dict) or set(request_context) != REQUEST_CONTEXT_KEYS:
        raise ValueError("invalid chickenbro eval request context keys")
    if any(
        not isinstance(value, str) or not SAFE_SCOPE_VALUE.fullmatch(value)
        for value in request_context.values()
    ):
        raise ValueError("invalid chickenbro eval request context value")

    source_evidence = bounded_context["sourceEvidence"]
    if not isinstance(source_evidence, list):
        raise ValueError("invalid chickenbro eval source evidence")
    for row in source_evidence:
        if not isinstance(row, dict) or set(row) != SOURCE_EVIDENCE_KEYS:
            raise ValueError("invalid chickenbro eval source evidence keys")
        if row["sourceKey"] not in SOURCE_CAPABILITY_IDS:
            raise ValueError("invalid chickenbro eval source key")
        if row["status"] not in TOOL_STATUSES:
            raise ValueError("invalid chickenbro eval source status")
        refs = row["evidenceRefs"]
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or _safe_evidence_ref(ref) != ref for ref in refs
        ):
            raise ValueError("invalid chickenbro eval evidence refs")


def _validate_agent_result(agent_result):
    if not isinstance(agent_result, dict) or set(agent_result) != {"validation", "model"}:
        raise ValueError("invalid chickenbro eval agent result keys")
    validation = agent_result["validation"]
    model = agent_result["model"]
    if (
        not isinstance(validation, dict)
        or set(validation) != {"status"}
        or validation["status"] not in {"passed", "failed"}
    ):
        raise ValueError("invalid chickenbro eval validation status")
    if (
        not isinstance(model, dict)
        or set(model) != {"status"}
        or model["status"] not in {"succeeded", "failed", "timed_out", "skipped"}
    ):
        raise ValueError("invalid chickenbro eval model status")


def validate_eval_case(case):
    if not isinstance(case, dict) or set(case) != EVAL_CASE_KEYS:
        raise ValueError("invalid chickenbro eval case keys")
    if case["schemaRevision"] != EVAL_CASE_SCHEMA_REVISION:
        raise ValueError("invalid chickenbro eval case schema revision")
    if not isinstance(case["caseId"], str) or not CASE_ID_PATTERN.fullmatch(case["caseId"]):
        raise ValueError("invalid chickenbro eval case id")

    case_input = case["input"]
    if not isinstance(case_input, dict) or set(case_input) != EVAL_INPUT_KEYS:
        raise ValueError("invalid chickenbro eval input keys")
    _validate_bounded_context(case_input["boundedContext"])
    _validate_agent_result(case_input["agentResult"])
    if case_input["errorCode"] not in EVAL_ERROR_CODES:
        raise ValueError("invalid chickenbro eval error code")
    latency_ms = case_input["latencyMs"]
    if not isinstance(latency_ms, int) or isinstance(latency_ms, bool) or latency_ms < 0:
        raise ValueError("invalid chickenbro eval latency")

    expected = case["expect"]
    if not isinstance(expected, dict) or set(expected) != EVAL_EXPECT_KEYS:
        raise ValueError("invalid chickenbro eval expectation keys")
    if expected["answerStatus"] not in {"succeeded", "failed", "timed_out", "skipped"}:
        raise ValueError("invalid chickenbro eval expected answer status")
    _validate_string_list(
        expected["requiredSignals"],
        name="required signals",
        allowed=SIGNAL_CODES,
    )
    _validate_string_list(
        expected["forbiddenSignals"],
        name="forbidden signals",
        allowed=SIGNAL_CODES,
    )
    _validate_string_list(
        expected["selectedCapabilityIds"],
        name="selected capability ids",
        allowed=CAPABILITY_IDS,
    )
    return copy.deepcopy(case)


def load_chickenbro_eval_cases(path):
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid chickenbro eval corpus: {source.name}") from error
    if not isinstance(payload, list):
        raise ValueError("invalid chickenbro eval corpus shape")
    cases = [validate_eval_case(case) for case in payload]
    case_ids = [case["caseId"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate chickenbro eval case id")
    return cases


def evaluate_chickenbro_trace_case(case):
    validated_case = validate_eval_case(case)
    case_input = validated_case["input"]
    trace = build_chickenbro_agent_trace(
        bounded_context=case_input["boundedContext"],
        agent_result=case_input["agentResult"],
        error=case_input["errorCode"],
        latency_ms=case_input["latencyMs"],
        created_at="2026-08-02T00:00:00+00:00",
    )
    projection = deidentify_chickenbro_agent_trace(trace)
    expected = validated_case["expect"]
    failures = []
    signal_codes = {item["code"] for item in projection["outcomeSignals"]}
    if projection["answerStatus"] != expected["answerStatus"]:
        failures.append("answer_status")
    if not set(expected["requiredSignals"]).issubset(signal_codes):
        failures.append("required_signals")
    if set(expected["forbiddenSignals"]) & signal_codes:
        failures.append("forbidden_signals")
    if sorted(projection["selectedCapabilityIds"]) != sorted(
        expected["selectedCapabilityIds"]
    ):
        failures.append("selected_capability_ids")
    return {
        "caseId": validated_case["caseId"],
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def evaluate_chickenbro_trace_cases(cases):
    if not isinstance(cases, list):
        raise ValueError("invalid chickenbro eval cases")
    results = [evaluate_chickenbro_trace_case(case) for case in cases]
    passed_count = sum(result["status"] == "passed" for result in results)
    failed_count = len(results) - passed_count
    return {
        "schemaRevision": EVAL_SUMMARY_SCHEMA_REVISION,
        "status": "passed" if failed_count == 0 else "failed",
        "caseCount": len(results),
        "passedCount": passed_count,
        "failedCount": failed_count,
        "cases": results,
    }
