"""Pure contracts for bounded, Codex-planned Chickenbro research."""

import copy
import json
import re

try:
    from .chickenbro_registry import validate_chickenbro_registry_release
except ImportError:  # pragma: no cover - direct server module execution
    from chickenbro_registry import validate_chickenbro_registry_release


RESEARCH_PLAN_SCHEMA_REVISION = "chickenbro-research-plan-v1"
MAX_RESEARCH_TURNS = 2
MAX_TOOL_CALLS_PER_TURN = 3
MAX_GOAL_CHARS = 480
MAX_LIST_ITEMS = 6
MAX_LIST_ITEM_CHARS = 240
MAX_ARGUMENT_CHARS = 160

_PLAN_KEYS = {
    "schemaRevision",
    "goal",
    "hypotheses",
    "informationGaps",
    "toolCalls",
    "decision",
}
_TOOL_CALL_KEYS = {"toolId", "arguments"}
_ARGUMENT_ENTRY_KEYS = {"name", "value"}
_SAFE_TOOL_ID = re.compile(r"^[a-z][a-z0-9_-]{0,47}(?::[a-z][a-z0-9_-]{0,47}){1,3}$")
_SAFE_ARGUMENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")
_UNSAFE_ARGUMENT_NAME = re.compile(r"^(?:url|uri|path|file|shell|command|sql|token|secret|credential|password|apiKey)$", re.IGNORECASE)
_UNSAFE_ARGUMENT_VALUE = re.compile(r"(?:^\s*(?:https?|file|data|ssh)://|(?:^|[\\/])\.\.(?:[\\/]|$)|\x00)", re.IGNORECASE)
_SAFE_WCL_REPORT = re.compile(
    r"^https://www\.warcraftlogs\.com/reports/[A-Za-z0-9]+(?:\?fight=[0-9]+)?$",
    re.IGNORECASE,
)
_OBSERVATION_FACT_KEYS = {"summary", "classKey", "specKey", "scenarioKey", "productPhase", "metric", "sampleCount"}
_OBSERVATION_SCOPE_KEYS = {"productPhase", "scenarioKey", "region", "seasonSlug", "partition", "encounterId"}


def _bounded_text(value, limit):
    if not isinstance(value, str):
        raise ValueError("research field must be text")
    text = value.strip()
    if not text or len(text) > limit:
        raise ValueError("research field is empty or too long")
    return text


def _bounded_text_list(value, name):
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        raise ValueError(f"invalid research {name}")
    output = []
    for item in value:
        text = _bounded_text(item, MAX_LIST_ITEM_CHARS)
        if text not in output:
            output.append(text)
    return output


def _required_arguments(tool):
    schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
    required = schema.get("required") or []
    if not isinstance(required, list) or any(
        not isinstance(item, str) or not _SAFE_ARGUMENT_NAME.fullmatch(item)
        for item in required
    ):
        raise ValueError("invalid published tool input schema")
    return set(required)


def _catalog_entry(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("invalid published tool")
    tool_id = str(manifest.get("toolId") or "").strip()
    if not _SAFE_TOOL_ID.fullmatch(tool_id):
        raise ValueError("invalid published tool id")
    if manifest.get("riskClass") != "read_only" or manifest.get("status", "active") != "active":
        raise ValueError("invalid published tool safety")
    required = _required_arguments(manifest)
    purpose = _bounded_text(manifest.get("purpose"), MAX_LIST_ITEM_CHARS)
    timeout = manifest.get("timeoutBudgetMs")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("invalid published tool timeout")
    for key in ("outputSchema", "sourcePolicy", "freshnessPolicy", "costBudget"):
        if not isinstance(manifest.get(key), dict):
            raise ValueError("invalid published tool contract")
    return {
        "toolId": tool_id,
        "purpose": purpose,
        "inputSchema": {"required": sorted(required)},
        "outputSchema": copy.deepcopy(manifest["outputSchema"]),
        "riskClass": "read_only",
        "ownerPolicy": str(manifest.get("ownerPolicy") or ""),
        "sourcePolicy": copy.deepcopy(manifest["sourcePolicy"]),
        "freshnessPolicy": copy.deepcopy(manifest["freshnessPolicy"]),
        "costBudget": copy.deepcopy(manifest["costBudget"]),
        "timeoutBudgetMs": timeout,
    }


def build_research_catalog(release):
    """Expose only safe, published read-only tool descriptions to the planner."""
    validated = validate_chickenbro_registry_release(release)
    return [
        _catalog_entry(manifest)
        for manifest in sorted(validated["manifests"], key=lambda item: item["toolId"])
        if manifest.get("status") == "active" and manifest.get("riskClass") == "read_only"
    ]


def research_plan_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_PLAN_KEYS),
        "properties": {
            "schemaRevision": {"type": "string", "enum": [RESEARCH_PLAN_SCHEMA_REVISION]},
            "goal": {"type": "string"},
            "hypotheses": {"type": "array", "items": {"type": "string"}},
            "informationGaps": {"type": "array", "items": {"type": "string"}},
            "toolCalls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["toolId", "arguments"],
                    "properties": {
                        "toolId": {"type": "string"},
                        "arguments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["name", "value"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "decision": {"type": "string", "enum": ["continue", "answer"]},
        },
    }


def research_plan_prompt(message, history, catalog, observations, turn):
    """Describe a bounded planning task without asking for hidden reasoning."""
    if not isinstance(turn, int) or turn < 0 or turn >= MAX_RESEARCH_TURNS:
        raise ValueError("invalid research turn")
    safe_history = []
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            safe_history.append({"role": role, "content": content[:600]})
    return json.dumps(
        {
            "instructions": [
                "Plan a bounded research step for a World of Warcraft player question.",
                "Select only tools in toolCatalog. Do not request URLs, files, shell commands, SQL, secrets, or unlisted tools.",
                "Represent every tool argument as an arguments array of {name, value}; include exactly the names required by that tool and use an empty array when none are required.",
                "Use returned observations to decide whether one more tool call will materially change the answer.",
                "Return only JSON that matches the supplied schema. Do not expose tool ids to the player.",
            ],
            "turn": turn,
            "playerMessage": _bounded_text(str(message or ""), 1000),
            "history": safe_history[-6:],
            "toolCatalog": copy.deepcopy(catalog),
            "observations": copy.deepcopy(observations),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def parse_research_plan(model_result):
    if isinstance(model_result, dict) and model_result.get("schemaRevision"):
        return copy.deepcopy(model_result)
    content = ""
    if isinstance(model_result, dict):
        content = model_result.get("content") or model_result.get("lastMessage") or ""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty research plan")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("invalid research plan json") from error
    if not isinstance(payload, dict):
        raise ValueError("invalid research plan")
    return payload


def _argument_mapping(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        raise ValueError("invalid research arguments")
    output = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != _ARGUMENT_ENTRY_KEYS:
            raise ValueError("invalid research argument")
        key = item.get("name")
        if not isinstance(key, str) or key in output:
            raise ValueError("invalid research argument")
        output[key] = item.get("value")
    return output


def _validate_arguments(value, required):
    value = _argument_mapping(value)
    if set(value) - required:
        for key in value:
            if _UNSAFE_ARGUMENT_NAME.search(str(key)):
                raise ValueError("unsafe research argument")
        raise ValueError("unsupported research argument")
    output = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not _SAFE_ARGUMENT_NAME.fullmatch(key):
            raise ValueError("unsafe research argument")
        if _UNSAFE_ARGUMENT_NAME.search(key):
            raise ValueError("unsafe research argument")
        if not isinstance(raw, (str, int, float, bool)) or isinstance(raw, bool):
            raise ValueError("invalid research argument")
        text = str(raw).strip()
        is_owner_report = key == "wclReport" and bool(_SAFE_WCL_REPORT.fullmatch(text))
        if not text or len(text) > MAX_ARGUMENT_CHARS or (
            _UNSAFE_ARGUMENT_VALUE.search(text) and not is_owner_report
        ):
            raise ValueError("unsafe research argument")
        output[key] = text
    return output


def validate_research_plan(payload, catalog):
    """Validate a model plan against the catalog, never inferred player labels."""
    if not isinstance(payload, dict) or set(payload) != _PLAN_KEYS:
        raise ValueError("invalid research plan keys")
    if payload.get("schemaRevision") != RESEARCH_PLAN_SCHEMA_REVISION:
        raise ValueError("invalid research plan revision")
    catalog_by_id = {}
    for item in catalog if isinstance(catalog, list) else []:
        entry = _catalog_entry(item)
        if entry["toolId"] in catalog_by_id:
            raise ValueError("duplicate published tool")
        catalog_by_id[entry["toolId"]] = entry
    if not catalog_by_id:
        raise ValueError("published tool catalog is empty")
    tool_calls = payload.get("toolCalls")
    if not isinstance(tool_calls, list) or len(tool_calls) > MAX_TOOL_CALLS_PER_TURN:
        raise ValueError("research tool call budget exceeded")
    calls = []
    seen = set()
    for raw_call in tool_calls:
        if not isinstance(raw_call, dict) or set(raw_call) != _TOOL_CALL_KEYS:
            raise ValueError("invalid research tool call")
        tool_id = str(raw_call.get("toolId") or "").strip()
        if tool_id not in catalog_by_id:
            raise ValueError("research plan requests an unpublished tool")
        if tool_id in seen:
            raise ValueError("duplicate research tool call")
        seen.add(tool_id)
        calls.append(
            {
                "toolId": tool_id,
                "arguments": _validate_arguments(
                    raw_call.get("arguments"),
                    set(catalog_by_id[tool_id]["inputSchema"]["required"]),
                ),
            }
        )
    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"continue", "answer"}:
        raise ValueError("invalid research decision")
    if not calls and decision != "answer":
        raise ValueError("empty tool calls require answer decision")
    return {
        "schemaRevision": RESEARCH_PLAN_SCHEMA_REVISION,
        "goal": _bounded_text(payload.get("goal"), MAX_GOAL_CHARS),
        "hypotheses": _bounded_text_list(payload.get("hypotheses"), "hypotheses"),
        "informationGaps": _bounded_text_list(payload.get("informationGaps"), "information gaps"),
        "toolCalls": calls,
        "decision": decision,
    }


def _observation_scope(result):
    scope = {}
    for evidence in result.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        for key in _OBSERVATION_SCOPE_KEYS:
            value = evidence.get(key)
            if value not in (None, "") and key not in scope:
                scope[key] = str(value)[:160]
    for fact in result.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        for key in _OBSERVATION_SCOPE_KEYS:
            value = fact.get(key)
            if value not in (None, "") and key not in scope:
                scope[key] = str(value)[:160]
    return scope


def _observation_facts(result):
    output = []
    for fact in result.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        projection = {}
        for key in _OBSERVATION_FACT_KEYS:
            value = fact.get(key)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                projection[key] = str(value)[:240]
        if projection:
            output.append(projection)
        if len(output) >= 3:
            break
    return output


def observations_from_tool_results(tool_calls, results):
    """Keep only short, source-returned facts and execution status for re-planning."""
    calls = tool_calls if isinstance(tool_calls, list) else []
    tool_results = results if isinstance(results, list) else []
    output = []
    for index, result in enumerate(tool_results):
        if not isinstance(result, dict):
            continue
        call = calls[index] if index < len(calls) and isinstance(calls[index], dict) else {}
        tool_id = str(call.get("toolId") or "").strip()
        source_key = str(result.get("sourceKey") or "").strip()
        status = str(result.get("status") or "unknown").strip().lower()
        if not tool_id or not source_key:
            continue
        evidence_refs = []
        for value in result.get("evidenceRefs") or []:
            ref = str(value or "").strip()
            if ref and len(ref) <= 160 and ref not in evidence_refs:
                evidence_refs.append(ref)
        limitations = []
        for value in result.get("limitations") or []:
            text = str(value or "").strip()
            if text and len(text) <= 240 and text not in limitations:
                limitations.append(text)
        output.append(
            {
                "toolId": tool_id,
                "sourceKey": source_key[:80],
                "status": status[:32],
                "evidenceRefs": evidence_refs[:6],
                "scope": _observation_scope(result),
                "facts": _observation_facts(result),
                "limitations": limitations[:4],
            }
        )
    return output
