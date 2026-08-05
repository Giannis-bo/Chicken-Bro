#!/usr/bin/env python3
"""Read-only MCP ToolBox used by the native Chickenbro Codex Agent.

The server deliberately exposes generic operations rather than game, site or
question-specific routes.  Codex decides whether to use them and how to
interpret the returned observation; this process only enforces the bounded
public-web reader already owned by the backend.
"""

import json
import os
import sys
from pathlib import Path

try:
    from .chickenbro_public_web_research import build_public_web_research_tool_result
except ImportError:
    from chickenbro_public_web_research import build_public_web_research_tool_result


MCP_PROTOCOL_VERSION = "2025-03-26"
TOOL_NAME = "research_public_web"
CURRENT_MPLUS_SNAPSHOT_TOOL_NAME = "inspect_current_mythic_plus_snapshot"
TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": (
        "Read a small, safe snapshot from a Codex-selected public HTTPS page or search query. "
        "Use a concrete target. The result includes source URLs, checked time, scope and limitations."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["target"],
        "properties": {
            "target": {
                "type": "string",
                "description": "A concrete public-web research query or safe HTTPS URL.",
                "maxLength": 360,
            }
        },
    },
    "annotations": {"readOnlyHint": True},
}
CURRENT_MPLUS_SNAPSHOT_TOOL_DEFINITION = {
    "name": CURRENT_MPLUS_SNAPSHOT_TOOL_NAME,
    "description": (
        "Inspect the current, read-only Mythic+ community snapshot already available to this service. "
        "Use it when a current high-key comparison by role would help. It reports its source, season, "
        "region, checked time and limits; it is not a universal tier list or a personal-performance result."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["role"],
        "properties": {
            "role": {
                "type": "string",
                "description": "One comparable Mythic+ role, for example tank, healer, or dps.",
                "maxLength": 32,
            },
            "classKey": {
                "type": "string",
                "description": "Optional class filter when inspecting one specialization.",
                "maxLength": 64,
            },
            "specKey": {
                "type": "string",
                "description": "Optional specialization filter when inspecting one specialization.",
                "maxLength": 64,
            },
        },
    },
    "annotations": {"readOnlyHint": True},
}
TOOL_DEFINITIONS = [TOOL_DEFINITION, CURRENT_MPLUS_SNAPSHOT_TOOL_DEFINITION]


def _response(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _tool_text(result):
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _partial_tool_result(limitation, source_key="public_web_research"):
    return {
        "sourceKey": source_key,
        "status": "partial",
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": [],
    }


def _safe_observation(result, tool_name=TOOL_NAME):
    packet = result if isinstance(result, dict) else {}
    return {
        "tool": tool_name,
        "sourceKey": str(packet.get("sourceKey") or "public_web_research"),
        "status": str(packet.get("status") or "partial"),
        "evidenceRefs": [str(value) for value in packet.get("evidenceRefs") or [] if str(value)],
        "evidence": [item for item in packet.get("evidence") or [] if isinstance(item, dict)],
        "limitations": [str(value) for value in packet.get("limitations") or [] if str(value)],
    }


def _normalized_key(value):
    return "".join(character for character in str(value or "").strip().lower() if character.isalnum() or character == "_")[:64]


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _compact_number(value):
    number = _positive_number(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def _current_mythic_plus_payload():
    """Load the service-owned cache lazily so MCP startup stays lightweight."""
    try:
        from .news_backend import chickenbro_cached_raiderio_payload
    except ImportError:  # pragma: no cover - direct candidate script execution
        from news_backend import chickenbro_cached_raiderio_payload
    return chickenbro_cached_raiderio_payload()


def build_current_mythic_plus_snapshot_tool_result(arguments, *, payload_loader=_current_mythic_plus_payload):
    """Project one comparable role from the current service-owned M+ snapshot."""
    request = arguments if isinstance(arguments, dict) else {}
    role = _normalized_key(request.get("role"))
    class_key = _normalized_key(request.get("classKey"))
    spec_key = _normalized_key(request.get("specKey"))
    if not role:
        return _partial_tool_result(
            "A comparable Mythic+ role is required for a current community snapshot.",
            "current_mythic_plus_snapshot",
        )
    try:
        payload = payload_loader() if callable(payload_loader) else {}
    except Exception:
        payload = {}
    payload = payload if isinstance(payload, dict) else {}
    source_status = str(payload.get("sourceStatus") or payload.get("status") or "blocked").strip().lower()
    source_name = str(payload.get("sourceName") or "Community Mythic+ snapshot").strip()
    source_url = str(payload.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings").strip()
    evidence = {
        "id": f"community-mythic-plus:{role}",
        "sourceName": source_name,
        "sourceUrl": source_url,
        "checkedAt": str(payload.get("checkedAt") or "").strip(),
        "seasonSlug": str(payload.get("seasonSlug") or "").strip(),
        "region": str(payload.get("region") or "").strip(),
        "sourceScope": "current_mythic_plus_community_snapshot",
        "sourceStatus": source_status,
    }
    if source_status != "synced":
        return {
            **_partial_tool_result(
                "The current Mythic+ community snapshot is unavailable, stale, or incomplete.",
                "current_mythic_plus_snapshot",
            ),
            "evidence": [evidence],
        }
    ranked = []
    for aggregate in payload.get("specAggregates") or []:
        item = aggregate if isinstance(aggregate, dict) else {}
        if _normalized_key(item.get("role")) != role:
            continue
        if class_key and _normalized_key(item.get("classKey")) != class_key:
            continue
        if spec_key and _normalized_key(item.get("specKey")) != spec_key:
            continue
        score = _positive_number(item.get("bestScore"))
        if score is None:
            continue
        ranked.append({
            "classKey": _normalized_key(item.get("classKey")),
            "specKey": _normalized_key(item.get("specKey")),
            "fullName": str(item.get("fullName") or "").strip(),
            "bestObservedScore": score,
            "maxKeyLevel": int(_positive_number(item.get("maxKeyLevel")) or 0),
            "sampleCount": int(_positive_number(item.get("sampleCount")) or 0),
        })
    ranked.sort(key=lambda item: item["bestObservedScore"], reverse=True)
    for placement, item in enumerate(ranked, start=1):
        item["placement"] = placement
    if not ranked:
        return {
            **_partial_tool_result(
                "The current Mythic+ community snapshot has no comparable positive-score sample for that request.",
                "current_mythic_plus_snapshot",
            ),
            "evidence": [evidence],
        }
    ranked = ranked[:40]
    allowed_numbers = []
    for item in ranked:
        for value in (item["bestObservedScore"], item["maxKeyLevel"], item["sampleCount"], item["placement"]):
            compact = _compact_number(value)
            if compact and compact not in allowed_numbers:
                allowed_numbers.append(compact)
    return {
        "sourceKey": "current_mythic_plus_snapshot",
        "status": "source_reference",
        "facts": [{
            "scenarioKey": "mythic_plus",
            "role": role,
            "rankedSpecs": ranked,
            "summary": f"Current comparable Mythic+ high-key community snapshot is available for {role}.",
        }],
        "evidence": [evidence],
        "evidenceRefs": [evidence["id"]],
        "allowedNumbers": allowed_numbers[:80],
        "limitations": [
            "This snapshot compares best observed high-key samples within one role. It is not representation, success rate, DPS, a universal tier list, or a personal-performance verdict.",
        ],
        "nextActions": [],
    }


def handle_rpc_request(request, *, observation_writer=None):
    """Handle one stdio JSON-RPC request without exposing any host capability."""
    packet = request if isinstance(request, dict) else {}
    request_id = packet.get("id")
    method = str(packet.get("method") or "")
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "chickenbro-native-toolbox", "version": "1.0.0"},
                "instructions": (
                    "Read-only research tools are exposed. Choose the relevant tool and state the returned "
                    "source scope and limitations."
                ),
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        params = packet.get("params") if isinstance(packet.get("params"), dict) else {}
        tool_name = str(params.get("name") or "")
        if tool_name not in {TOOL_NAME, CURRENT_MPLUS_SNAPSHOT_TOOL_NAME}:
            return _response(
                request_id,
                {"content": [{"type": "text", "text": "Unknown read-only tool."}], "isError": True},
            )
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if tool_name == TOOL_NAME:
            target = str(arguments.get("target") or "").strip()
            if not target:
                result = _partial_tool_result("Public web research requires a bounded non-empty query or safe public HTTPS URL.")
            else:
                try:
                    result = build_public_web_research_tool_result({"target": target})
                except Exception:
                    result = _partial_tool_result("Public web research failed before a safe observation was returned.")
        else:
            try:
                result = build_current_mythic_plus_snapshot_tool_result(arguments)
            except Exception:
                result = _partial_tool_result(
                    "The current Mythic+ community snapshot failed before a safe observation was returned.",
                    "current_mythic_plus_snapshot",
                )
        observation = _safe_observation(result, tool_name=tool_name)
        if observation_writer:
            try:
                observation_writer(observation)
            except OSError:
                pass
        return _response(
            request_id,
            {"content": [{"type": "text", "text": _tool_text(result)}], "isError": False},
        )
    if request_id is None:
        return None
    return _error(request_id, -32601, "Method not found")


def _observation_writer_from_environment():
    target = str(os.environ.get("CHICKENBRO_NATIVE_OBSERVATIONS_PATH") or "").strip()
    if not target:
        return lambda _observation: None
    path = Path(target)

    def write(observation):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(observation, ensure_ascii=False, separators=(",", ":")) + "\n")

    return write


def main(input_stream=None, output_stream=None):
    source = input_stream or sys.stdin
    destination = output_stream or sys.stdout
    observation_writer = _observation_writer_from_environment()
    for raw_line in source:
        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        response = handle_rpc_request(request, observation_writer=observation_writer)
        if response is None:
            continue
        destination.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        destination.flush()


if __name__ == "__main__":
    main()
