#!/usr/bin/env python3
"""Research and account-scoped simulation tools for the native Chickenbro agent.

The server deliberately exposes generic operations rather than game, site or
question-specific routes.  Codex decides whether to use them and how to
interpret the returned observation. Research uses the bounded public-web reader;
simulation uses the current Chat run's server-issued, owner-scoped capability.
"""

import json
import hashlib
import os
import sys
import time
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
RAIDERIO_RANKINGS_TOOL_NAME = "query_raiderio_rankings"
RAIDERIO_BATCH_TOOL_NAME = "query_raiderio_characters"
WCL_CHARACTER_TOOL_NAME = "query_warcraftlogs_character"
SOURCE_GATEWAY_URL_ENV = "CHICKENBRO_SOURCE_GATEWAY_URL"
SOURCE_GATEWAY_TOKEN_ENV = "CHICKENBRO_SOURCE_GATEWAY_TOKEN"
SIMULATION_GATEWAY_URL_ENV = "CHICKENBRO_SIMULATION_GATEWAY_URL"
SIMULATION_GATEWAY_TOKEN_ENV = "CHICKENBRO_SIMULATION_GATEWAY_TOKEN"
SIMULATION_OPERATIONS = {"prepare_simulation": "prepare", "submit_simulation": "submit",
                         "get_simulation_job": "get", "list_simulation_jobs": "list",
                         "preview_simulation": "preview", "query_simulation_options": "options", "compare_simulation_jobs": "compare"}
TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": (
        "Search public sources or read a public HTTPS article for game mechanics, patches and guides. "
        "Use target=query for discovery or target=URL to read. Empty JS shells/challenges are not evidence. "
        "Follow returned nextStart with start to continue a truncated article, or match to locate a term. "
        "For ranked character samples use query_raiderio_rankings instead of the website homepage."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["target"],
        "properties": {
            "target": {
                "type": "string",
                "description": "A concrete public-web research query or safe HTTPS URL.",
                "maxLength": 2048,
            },
            "start": {"type": "integer", "minimum": 0, "maximum": 750000},
            "match": {"type": "string", "maxLength": 120},
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
        "An unfinished page is queryable data, not an API inability; fetch further relevant pages as needed. "
        "Choose view=overview for whole-fight tables/gear without events; view=events for focused events without repeated tables. "
        "Use view=statistics for cast counts, resource waste and healing sums in an explicit fight/source/startTime/endTime window. "
        "Statistics follow up to maxPages (default 3, maximum 5) within 20 seconds; check complete and metricsComplete. "
        "Incomplete sums are subtotals, not whole-window totals or causal proof. full preserves the legacy combined response."
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
                    "view": {"type":"string", "enum":["full","overview","events","statistics"]},
                    "maxPages": {"type":"integer", "minimum":1, "maximum":5},
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
        "Returns selected talents and analysis-ready gear including gem/enchant descriptions, tier membership, "
        "scores and snapshot dates. Missing statistics are explicit; not a combat log or simulated stat weight. "
        "Discover unknown character URLs with query_raiderio_rankings, or read multiple with query_raiderio_characters."
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
RAIDERIO_RANKINGS_TOOL_DEFINITION = {
    "name": RAIDERIO_RANKINGS_TOOL_NAME,
    "description": (
        "Discover high-scoring Mythic+ characters by class and specialization through the Raider.IO API. "
        "Use when the user asks about top players or popular builds without providing character links. "
        "season=current resolves the upstream active season. Returns ranks, scores, character URLs and page metadata. "
        "Use nextPage/nextOffset to continue, then query_raiderio_characters for the selected sample. "
        "Ranked samples are observations, not proof of individual stat gains."
    ),
    "inputSchema": {
        "type": "object", "additionalProperties": False, "required": ["className", "spec"],
        "properties": {
            "className": {"type": "string", "description": "Class slug, e.g. shaman, death-knight, demon-hunter.", "maxLength": 24},
            "spec": {"type": "string", "description": "Matching specialization slug, e.g. enhancement.", "maxLength": 24},
            "region": {"type": "string", "enum": ["world", "us", "eu", "kr", "tw", "cn"]},
            "season": {"type": "string", "description": "current (default) or explicit Raider.IO season slug.", "maxLength": 50},
            "page": {"type": "integer", "minimum": 0, "maximum": 20},
            "offset": {"type": "integer", "minimum": 0, "maximum": 99},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    },
    "annotations": {"readOnlyHint": True},
}
RAIDERIO_BATCH_TOOL_DEFINITION = {
    "name": RAIDERIO_BATCH_TOOL_NAME,
    "description": (
        "Read up to 10 public Raider.IO characters concurrently using the server API. "
        "Use URLs discovered by query_raiderio_rankings or supplied by the user. "
        "Returns analysis-ready gear/talents and individual failures; only use successful matching profiles as evidence."
    ),
    "inputSchema": {
        "type": "object", "additionalProperties": False, "required": ["targets"],
        "properties": {"targets": {"type": "array", "minItems": 1, "maxItems": 10,
                                    "items": {"type": "string", "maxLength": 2048}}},
    },
    "annotations": {"readOnlyHint": True},
}
WCL_CHARACTER_TOOL_DEFINITION = {
    "name": WCL_CHARACTER_TOOL_NAME,
    "description": "Find a named character's recent public Warcraft Logs reports by name, realm and region. "
        "Accepts localized realm names or canonical slugs. Use when the user gives a character name instead of a report link. "
        "Continue with pagination.nextPage. Then query_warcraftlogs_report and match both actor name and server to participating fights. "
        "An empty report list is not proof the character never logged; hidden/unavailable records are not accessible.",
    "inputSchema": {"type": "object", "additionalProperties": False,
        "required": ["name", "realm", "region"], "properties": {
            "name": {"type":"string", "minLength":1, "maxLength":100},
            "realm": {"type":"string", "minLength":1, "maxLength":100},
            "region": {"type":"string", "enum":["cn","us","eu","tw","kr"]},
            "page": {"type":"integer", "minimum":1, "maximum":20},
            "limit": {"type":"integer", "minimum":1, "maximum":10}}},
    "annotations": {"readOnlyHint": True},
}
WCL_BATCH_TOOL_NAME = 'query_warcraftlogs_batch'
WCL_BATCH_TOOL_DEFINITION = {
    'name': WCL_BATCH_TOOL_NAME,
    'description': 'Query up to 3 independent WCL event filters or time windows concurrently, at most 200 events per member. Use after identifying report/fight/actor. Preserve each result scope; pagination dependent on an unknown nextPageTimestamp must stay sequential. Results retain input order. Prefer this over separate calls when all query arguments are already known.',
    'inputSchema': {'type':'object','additionalProperties':False,'required':['queries'],
        'properties':{'queries':{'type':'array','minItems':1,'maxItems':3,
            'items':json.loads(json.dumps(WARCRAFTLOGS_TOOL_DEFINITION['inputSchema']))}}},
    'annotations':{'readOnlyHint':True},
}
WCL_BATCH_TOOL_DEFINITION['inputSchema']['properties']['queries']['items']['properties']['options']['properties']['limit']['maximum'] = 200
WCL_RANKINGS_TOOL_NAME = 'query_warcraftlogs_rankings'
WCL_RANKINGS_TOOL_DEFINITION = {
    'name':WCL_RANKINGS_TOOL_NAME,
    'description':'Discover Warcraft Logs raid zones/partitions/encounters with empty arguments or zoneId. Then query an encounter DPS/HPS leaderboard with explicit difficulty, className (Druid), specName (Feral), partition and optional region (world default). Use this API for top raid players, not public ranking webpages. Catalog partitions distinguish live and PTR. At most 10 player samples total per research across pages and providers, and at most 3 groups. Decline Top100/full enumeration; pagination never resets the budget. Ranking entries give report/fight and player identity, not rotation analysis; follow with report/events tools and disclose coverage.',
    'inputSchema':{'type':'object','additionalProperties':False,'properties':{
        'zoneId':{'type':'integer','minimum':1,'maximum':10000},
        'encounterId':{'type':'integer','minimum':1,'maximum':1000000},
        'difficulty':{'type':'integer','minimum':1,'maximum':5},
        'partition':{'type':'integer','minimum':1,'maximum':100},
        'className':{'type':'string','maxLength':31},'specName':{'type':'string','maxLength':31},
        'metric':{'type':'string','enum':['dps','hps','bossdps']},
        'region':{'type':'string','enum':['world','us','eu','kr','tw','cn']},
        'page':{'type':'integer','minimum':1,'maximum':20},'offset':{'type':'integer','minimum':0,'maximum':99},
        'limit':{'type':'integer','minimum':1,'maximum':10}}},
    'annotations':{'readOnlyHint':True},
}
TOOL_DEFINITIONS = [
    TOOL_DEFINITION,
    WCL_CHARACTER_TOOL_DEFINITION,
    WCL_RANKINGS_TOOL_DEFINITION,
    WARCRAFTLOGS_TOOL_DEFINITION,
    WCL_BATCH_TOOL_DEFINITION,
    RAIDERIO_TOOL_DEFINITION,
    RAIDERIO_RANKINGS_TOOL_DEFINITION,
    RAIDERIO_BATCH_TOOL_DEFINITION,
]

_UUID_SCHEMA = {"type": "string", "format": "uuid", "maxLength": 36}
_EQUIPMENT_ITEM_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["itemId", "itemLevel", "bonusIds", "gems", "enchant"], "properties": {
        "itemId": {"type": "integer", "minimum": 1, "maximum": 2147483647},
        "itemLevel": {"type": "integer", "minimum": 1, "maximum": 1000},
        "bonusIds": {"type": "array", "maxItems": 32, "items": {"type": "integer", "minimum": 1, "maximum": 2147483647}},
        "gems": {"type": "array", "maxItems": 32, "items": {"type": "integer", "minimum": 1, "maximum": 2147483647}},
        "enchant": {"type": ["integer", "null"], "minimum": 1, "maximum": 2147483647},
    }}
_SCENARIO_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "fightStyle": {"type": "string", "maxLength": 64},
    "desiredTargets": {"type": "integer", "minimum": 1, "maximum": 20},
    "iterations": {"type": "integer", "minimum": 1, "maximum": 10000},
    "maxTime": {"type": "integer", "minimum": 20, "maximum": 600},
    "varyCombatLength": {"type": "number", "minimum": 0, "maximum": 0.5},
    "targetError": {"type": "number", "minimum": 0, "maximum": 5},
    "raidBuffs": {"type": "boolean"}, "bloodlust": {"type": "boolean"},
    "statBonuses": {"type":"object", "minProperties":1, "additionalProperties":False,
        "properties":{name:{"type":"integer","minimum":0,"maximum":1000} for name in ("strength","agility","intellect","crit","haste","mastery","versatility")},
        "description":"Explicit hypothetical additive primary stats/secondary ratings via existing engine bonus options; replaces this entire map on a base job. Not actual gear, food identity, stat weights, or item-specific mechanics. For pure food-stat comparison set food=disabled in both arms to avoid stacking the default food. Verify buffedAttributes changes; raid/stat multipliers apply. Use identical controls and disclose short burst assumptions."},
    "food": {"type":"string", "pattern":"^[a-z][a-z0-9_]{0,79}$", "description":"Verified current-engine food token, or disabled for no food. Omission preserves defaults or baseJob food. Uses the engine food setting, not a deprecated precombat food action. Compare otherwise identical jobs; inspect effectiveConfig.food before attributing a result to food. Whole-fight DPS does not establish a boss-phase result."},
    "actionLists": {"type":"object", "minProperties":1, "maxProperties":16, "required":["default"],
        "description":"Custom APL, compiler v6. Complete replacement of ALL lists, including default and any precombat/sub-lists; omitted actionLists preserves prior behavior. Map list names to ordered SimC action strings without actions= prefixes. Max 256 actions / 16000 characters total. Use verified current-engine action names and conditions. APL order is priority, not guaranteed chronological order; strict_sequence enforces a sequence when all actions are ready. Preserve the rest of the rotation in both experiment arms. Preview checks syntax only; inspect actual sampled actions after running before claiming an ordering experiment succeeded.",
        "propertyNames":{"pattern":"^[a-z][a-z0-9_]{0,63}$"},
        "additionalProperties":{"type":"array","minItems":1,"maxItems":256,"items":{"type":"string","minLength":1,"maxLength":1024}}},
    "talentOverrides": {"description": "Requires compiler v5 and matching talent catalog. Replace an export OR patch node selections. Query options for verified node/entry IDs and preview before submit. Omitted nodes remain unchanged; rank 0 removes a selection if legal.",
        "oneOf": [{"type":"object","additionalProperties":False,"required":["string"],
                   "properties":{"string":{"type":"string","minLength":26,"maxLength":512,"pattern":"^[A-Za-z0-9+/]+$"}}},
                  {"type":"object","additionalProperties":False,"required":["nodes"],"properties":{
                      "nodes":{"type":"array","minItems":1,"maxItems":128,"items":{"type":"object","additionalProperties":False,
                               "required":["nodeId","entryId","rank"],"properties":{
                                   "nodeId":{"type":"integer","minimum":1,"maximum":2147483647},
                                   "entryId":{"type":"integer","minimum":1,"maximum":2147483647},
                                   "rank":{"type":"integer","minimum":0,"maximum":63}}}}}}]},
    "equipmentOverrides": {"type": "object", "maxProperties": 16,
        "description": "Canonical slot to COMPLETE replacement item. Use verified item ID, exact item level/bonus IDs, gems and enchant; []/null explicitly mean none. Never invent item data. Requires compiler v4.",
        "additionalProperties": _EQUIPMENT_ITEM_SCHEMA},
    "gemOverrides": {"type": "object", "maxProperties": 16,
        "description": "Canonical equipment slot to replacement gem ITEM IDs; preserve exact socket count. Obtain real IDs from sources; never invent them.",
        "additionalProperties": {"type": "array", "minItems": 1, "maxItems": 32,
            "items": {"type": "integer", "minimum": 1, "maximum": 2147483647}}},
}}
for _name, _description, _required, _properties, _read_only in [
    ("query_simulation_options", "Resolve runtime-bound talent node/entry choices (English/Chinese names, ranks, selected state) or item names to IDs for an owned snapshot/base job. kind=items returns item identity and sameUpgradeVariants when a source upgrade bonus is verified. Use the candidate only for the same upgrade progress and disclose its assumption; other variants require source research. An empty talents query returns the spec tree. Use this proactively when the user asks for talent optimization without candidates; guides suggest candidates, simulations establish gains.",
     ["kind"], {"snapshotId":_UUID_SCHEMA,"baseJobId":_UUID_SCHEMA,"kind":{"enum":["talents","items"]},"query":{"type":"string","maxLength":120}}, True),
    ("preview_simulation", "Compile and validate an immutable scenario edit without enqueueing. Exactly one of snapshotId/baseJobId. Returns effective character/talents/gear, actual changes, scenario/profile hashes and runtime identity. Resolve blockers before submission. Compilation is not measured performance; item syntax is not proof of legal upgrade/slot rules.",
     ["scenario"], {"snapshotId":_UUID_SCHEMA,"baseJobId":_UUID_SCHEMA,"scenario":_SCENARIO_SCHEMA}, True),
    ("compare_simulation_jobs", "Compare two owned completed jobs from the SAME snapshot, runtime/compiler and control parameters. Returns DPS difference/percent and conservative reported-error assessment, plus variant changes. Different environments, pending jobs and absent provenance are not comparable. Within error means no clear gain; refine BOTH jobs with identical increased iterations within budget. Never claim global optimum from limited candidates.",
     ["baselineJobId","variantJobId"], {"baselineJobId":_UUID_SCHEMA,"variantJobId":_UUID_SCHEMA}, True),
    ("prepare_simulation", "Prepare and validate an owner-scoped SimC snapshot from a Raider.IO character URL. Does not run SimC. Returns character, original gear/gem IDs, talents, snapshotId and exact readiness blockers. Reuse the same snapshot for comparisons.",
     ["sourceUrl"], {"sourceUrl": {"type": "string", "maxLength": 2048}}, False),
    ("submit_simulation", "Submit an actual cloud SimulationCraft job for the current account. Use when the user asks to run a simulation or requests a quantitative comparison of explicit alternatives for their character, not for explanation-only questions. Provide exactly one of snapshotId or baseJobId. baseJobId reuses an owned job snapshot and preserves its scenario; scenario is a patch, including slot-wise equipmentOverrides/gemOverrides and talentOverrides; actionLists replaces the full custom rotation. Preview edits first with preview_simulation; query_simulation_options resolves names and talent choices. Original job is unchanged. Read get_simulation_job first for gear and scenario; use verified replacement item data. Up to 4 distinct jobs per Chat turn; repeated same snapshot/scenario is idempotent. Compare baseline and gemOverrides with identical target/time/iterations. Queued is not a result; read get_simulation_job. Jobs also appear in the account's SimC list.",
     ["scenario"], {"snapshotId": _UUID_SCHEMA, "baseJobId": _UUID_SCHEMA, "scenario": _SCENARIO_SCHEMA}, False),
    ("get_simulation_job", "Read this account's SimC job, character, original source URL, effective talents and gear, original scenario, snapshotId, status, validated DPS/HPS, uncertainty when available and provenance. waitSeconds up to20 waits for completion. Poll reasonably within the Chat time budget; pending is not success. Never invent DPS or significance when uncertainty is absent.",
     ["jobId"], {"jobId": _UUID_SCHEMA, "waitSeconds": {"type": "integer", "minimum": 0, "maximum": 20}}, True),
    ("list_simulation_jobs", "List the current account's existing SimC jobs and available results. Useful for follow-up questions and jobs still running after a prior Chat turn; no ownership parameter is accepted.",
     [], {"limit": {"type": "integer", "minimum": 1, "maximum": 10}, "cursor": {"type": "string", "maxLength": 1024}}, True),
]:
    TOOL_DEFINITIONS.append({"name": _name, "description": _description,
        "inputSchema": {"type": "object", "additionalProperties": False, "required": _required,
                        "properties": _properties},
        "annotations": {"readOnlyHint": _read_only, "destructiveHint": False, "idempotentHint": True}})


def _response(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _tool_text(result):
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    # App-server wraps this JSON string in its own bounded stdio notification.
    # Fail with a usable partial packet instead of emitting an oversized frame.
    if len(encoded.encode('utf-8')) > 196608:
        return json.dumps(_partial_tool_result(
            'The result exceeds the bounded tool response size. Narrow the time window, actor, event limit or batch size; no facts from this response are usable.',
            result.get('sourceKey','source') if isinstance(result,dict) else 'source'))
    return encoded


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


def _safe_observation(result, tool_name=TOOL_NAME, *, arguments=None, elapsed_ms=0):
    packet = result if isinstance(result, dict) else {}
    return {
        "tool": tool_name,
        "sourceKey": str(packet.get("sourceKey") or "public_web_research"),
        "status": str(packet.get("status") or "partial"),
        "errorCode": str(packet.get("errorCode") or "")[:128],
        "reasonCode": str(packet.get("reasonCode") or "")[:80],
        "elapsedMs": max(0, int(elapsed_ms)),
        "factCount": len(packet.get("facts") or []),
        "argumentsSha256": hashlib.sha256(json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
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
        and port in {8790, 8791, 8792, 28794, 18794}
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
        with urlopen(request, timeout=85 if provider == "raiderio_batch" else 30) as response:
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


def query_simulation_gateway(operation, arguments):
    url = os.environ.get(SIMULATION_GATEWAY_URL_ENV, "")
    token = os.environ.get(SIMULATION_GATEWAY_TOKEN_ENV, "")
    expected_path = "/api/v2/internal/chickenbro/simc-tool"
    parsed = urlparse(url)
    local_source_url = parsed._replace(path="/api/v2/internal/chickenbro/source-query").geturl()
    if not token or parsed.path != expected_path or not _source_gateway_target_is_local(local_source_url):
        return _partial_tool_result("This run has no authenticated account-scoped simulation capability.", "simc")
    request = Request(url, data=json.dumps({"operation": operation, "arguments": arguments}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Chickenbro-Simulation-Gateway": token}, method="POST")
    try:
        with urlopen(request, timeout=85) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("oversized simulation response")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("invalid simulation response")
        return payload
    except (HTTPError, URLError, OSError, ValueError):
        return _partial_tool_result("The simulation gateway did not return a usable response. Check status before retrying a submission.", "simc")


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
                    "Research and account-scoped cloud SimC tools are exposed. Submit simulations only when "
                    "the user asks to run them. Choose the relevant tool and state the returned "
                    "source scope and limitations."
                ),
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        params = packet.get("params") if isinstance(packet.get("params"), dict) else {}
        tool_name = str(params.get("name") or "")
        if tool_name not in {definition["name"] for definition in TOOL_DEFINITIONS}:
            return _response(
                request_id,
                {"content": [{"type": "text", "text": "Unknown read-only tool."}], "isError": True},
            )
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        started = time.monotonic()
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
                        result = query_source_gateway("public_web", target, options={k:v for k,v in arguments.items() if k != "target"})
                    except Exception:
                        result = _partial_tool_result("Public web research failed before a safe observation was returned.")
        elif tool_name in SIMULATION_OPERATIONS:
            result = query_simulation_gateway(SIMULATION_OPERATIONS[tool_name], arguments)
        elif tool_name == WCL_RANKINGS_TOOL_NAME:
            result = query_source_gateway('warcraftlogs_rankings','rankings',options=arguments)
        elif tool_name == WCL_CHARACTER_TOOL_NAME:
            result = query_source_gateway("warcraftlogs_character", "character", options=arguments)
        elif tool_name == WCL_BATCH_TOOL_NAME:
            result = query_source_gateway('warcraftlogs_batch','reports',options=arguments)
        elif tool_name in {RAIDERIO_RANKINGS_TOOL_NAME, RAIDERIO_BATCH_TOOL_NAME}:
            provider, target = (("raiderio_rankings", "rankings") if tool_name == RAIDERIO_RANKINGS_TOOL_NAME
                                else ("raiderio_batch", "characters"))
            result = query_source_gateway(provider, target, options=arguments)
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
        observation = _safe_observation(result, tool_name=tool_name, arguments=arguments,
                                        elapsed_ms=(time.monotonic() - started) * 1000)
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
