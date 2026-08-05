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


def _partial_tool_result(limitation):
    return {
        "sourceKey": "public_web_research",
        "status": "partial",
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": [],
    }


def _safe_observation(result):
    packet = result if isinstance(result, dict) else {}
    return {
        "tool": TOOL_NAME,
        "sourceKey": str(packet.get("sourceKey") or "public_web_research"),
        "status": str(packet.get("status") or "partial"),
        "evidenceRefs": [str(value) for value in packet.get("evidenceRefs") or [] if str(value)],
        "evidence": [item for item in packet.get("evidence") or [] if isinstance(item, dict)],
        "limitations": [str(value) for value in packet.get("limitations") or [] if str(value)],
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
                    "Only one read-only public-web research tool is exposed. "
                    "Choose concrete queries yourself and state the returned source scope and limitations."
                ),
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": [TOOL_DEFINITION]})
    if method == "tools/call":
        params = packet.get("params") if isinstance(packet.get("params"), dict) else {}
        if params.get("name") != TOOL_NAME:
            return _response(
                request_id,
                {"content": [{"type": "text", "text": "Unknown read-only tool."}], "isError": True},
            )
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        target = str(arguments.get("target") or "").strip()
        if not target:
            result = _partial_tool_result("Public web research requires a bounded non-empty query or safe public HTTPS URL.")
        else:
            try:
                result = build_public_web_research_tool_result({"target": target})
            except Exception:
                result = _partial_tool_result("Public web research failed before a safe observation was returned.")
        observation = _safe_observation(result)
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
