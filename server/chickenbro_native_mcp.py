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
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from pathlib import Path

try:
    from .chickenbro_public_web_research import build_public_web_research_tool_result
except ImportError:
    from chickenbro_public_web_research import build_public_web_research_tool_result


MCP_PROTOCOL_VERSION = "2025-03-26"
TOOL_NAME = "research_public_web"
WARCRAFTLOGS_TOOL_NAME = "query_warcraftlogs_report"
RAIDERIO_TOOL_NAME = "query_raiderio_character"
SOURCE_GATEWAY_URL_ENV = "CHICKENBRO_SOURCE_GATEWAY_URL"
SOURCE_GATEWAY_TOKEN_ENV = "CHICKENBRO_SOURCE_GATEWAY_TOKEN"
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
WARCRAFTLOGS_TOOL_DEFINITION = {
    "name": WARCRAFTLOGS_TOOL_NAME,
    "description": (
        "Query one Warcraft Logs report or fight through the server-configured Warcraft Logs API. "
        "Use this for a WCL report URL; do not open the public report page instead. The result is a bounded "
        "report metadata, actor IDs, player gear/talent/stats, casts and damage tables, and paginated events. "
        "Credentials and OAuth refresh are handled automatically by the server; never ask the user for API keys. "
        "You can add source=<actor ID> to the report URL to query that actor's abilities. "
        "Choose follow-up queries and analysis yourself. options.dataType filters event kinds (Casts, Buffs, Resources etc.); "
        "options.startTime/endTime select report-relative milliseconds. Continue with startTime=eventPage.nextPageTimestamp "
        "and the same other filters. Tables/player details cover the fight independently of event pages. "
        "An unfinished page is queryable data, not an API inability; fetch further relevant pages as needed."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["target"],
        "properties": {
            "target": {
                "type": "string",
                "description": "An HTTPS Warcraft Logs report URL, optionally including fight= and source=.",
                "maxLength": 2048,
            },
            "options": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "dataType": {"type": "string", "enum": ["All", "Buffs", "Casts", "CombatantInfo", "DamageDone", "DamageTaken", "Deaths", "Debuffs", "Dispels", "Healing", "Interrupts", "Resources", "Summons", "Threat"]},
                    "startTime": {"type": "number", "minimum": 0},
                    "endTime": {"type": "number", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
            }
        },
    },
    "annotations": {"readOnlyHint": True},
}
RAIDERIO_TOOL_DEFINITION = {
    "name": RAIDERIO_TOOL_NAME,
    "description": (
        "Query one Raider.IO character profile through the server-configured Raider.IO API. "
        "Use this for a Raider.IO character URL; do not open the public profile page instead. "
        "The result is a bounded character, gear and talent snapshot."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["target"],
        "properties": {
            "target": {
                "type": "string",
                "description": "An HTTPS Raider.IO character profile URL.",
                "maxLength": 2048,
            }
        },
    },
    "annotations": {"readOnlyHint": True},
}
TOOL_DEFINITIONS = [
    TOOL_DEFINITION,
    WARCRAFTLOGS_TOOL_DEFINITION,
    RAIDERIO_TOOL_DEFINITION,
]


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


def _source_gateway_url():
    configured = str(os.environ.get(SOURCE_GATEWAY_URL_ENV) or "").strip()
    return configured or "http://127.0.0.1:8790/api/v2/internal/chickenbro/source-query"


def _source_gateway_target_is_local(url):
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and not parsed.username
        and not parsed.password
        and port in {8790, 8791, 8792}
        and parsed.path == "/api/v2/internal/chickenbro/source-query"
        and not parsed.query
        and not parsed.fragment
    )


def query_source_gateway(provider, target, options=None):
    """Ask the API process to use its configured source credentials."""
    gateway_url = _source_gateway_url()
    capability = str(os.environ.get(SOURCE_GATEWAY_TOKEN_ENV) or "").strip()
    if not capability:
        return _partial_tool_result(
            "The server source gateway capability was not provided to this Codex run.",
            provider,
        )
    if not _source_gateway_target_is_local(gateway_url):
        return _partial_tool_result(
            "The server source gateway is not bound to a local API endpoint.",
            provider,
        )
    request = Request(
        gateway_url,
        data=json.dumps({"provider": provider, "target": target, **({"options": options} if options else {})}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Chickenbro-Source-Gateway": capability,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return _partial_tool_result(
            "The server-configured source API could not return a bounded result.",
            provider,
        )
    return payload if isinstance(payload, dict) else _partial_tool_result(
        "The server-configured source API returned an invalid result.",
        provider,
    )


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
        if tool_name not in {
            TOOL_NAME,
            WARCRAFTLOGS_TOOL_NAME,
            RAIDERIO_TOOL_NAME,
        }:
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
                # Never send a WCL/Raider.IO source URL through the public-page
                # reader. The model has dedicated server-API tools, but this
                # guard also keeps an accidental generic call on the safe path.
                lower_target = target.lower()
                if "warcraftlogs.com/reports/" in lower_target:
                    result = query_source_gateway("warcraftlogs", target)
                elif "raider.io/characters/" in lower_target or "raider.io/cn/characters/" in lower_target:
                    result = query_source_gateway("raiderio", target)
                else:
                    try:
                        result = build_public_web_research_tool_result({"target": target})
                    except Exception:
                        result = _partial_tool_result("Public web research failed before a safe observation was returned.")
        else:
            try:
                result = query_source_gateway(
                    "warcraftlogs" if tool_name == WARCRAFTLOGS_TOOL_NAME else "raiderio",
                    str(arguments.get("target") or "").strip(),
                    **({"options": arguments["options"]} if tool_name == WARCRAFTLOGS_TOOL_NAME and arguments.get("options") else {}),
                )
            except Exception:
                result = _partial_tool_result(
                    "The server-configured source query failed before a safe observation was returned.",
                    "source_gateway",
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
