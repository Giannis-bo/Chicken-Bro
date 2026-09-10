"""Server-configured Warcraft Logs evidence reader for the v2 Chickenbro app.

This module owns the small, read-only WCL report query used by the native
Chickenbro Codex path. Credentials are read only in the API process and the
returned packet contains bounded report/fight/event facts, never credentials
or the OAuth token.
"""

import json
import os
import re
import threading
from contextvars import ContextVar
from copy import deepcopy
from collections.abc import Mapping
from math import isfinite
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from server.app.simulation.sources import parse_character_source_url, InvalidSourceLink

from server.app.integrations.warcraftlogs import (
    warcraftlogs_credentials_state as configured_warcraftlogs_credentials_state,
    chat_warcraftlogs_oauth_token,
    invalidate_chat_warcraftlogs_oauth_token,
    WarcraftLogsProviderError,
    warcraftlogs_timeout_seconds,
)


WCL_REPORT_EVIDENCE_QUERY = """
query WowMiniProgramReportEvidence($code: String!, $fightIds: [Int], $sourceId: Int,
  $dataType: EventDataType, $startTime: Float, $endTime: Float, $limit: Int) {
  reportData {
    report(code: $code) {
      title
      startTime
      endTime
      fights {
        id
        name
        difficulty
        kill
        startTime
        endTime
      }
      masterData { gameVersion logVersion actors { id name type subType } }
      playerDetails(fightIDs: $fightIds, includeCombatantInfo: true)
      casts: table(fightIDs: $fightIds, sourceID: $sourceId, dataType: Casts)
      damage: table(fightIDs: $fightIds, sourceID: $sourceId, dataType: DamageDone)
      events(fightIDs: $fightIds, sourceID: $sourceId, dataType: $dataType,
        startTime: $startTime, endTime: $endTime, limit: $limit, includeResources: true) {
        data
        nextPageTimestamp
      }
    }
  }
}
"""

WCL_EVENTS_QUERY = """
query WowMiniProgramEvents($code: String!, $fightIds: [Int], $sourceId: Int,
  $dataType: EventDataType, $startTime: Float, $endTime: Float, $limit: Int) {
  reportData { report(code: $code) {
    events(fightIDs: $fightIds, sourceID: $sourceId, dataType: $dataType,
      startTime: $startTime, endTime: $endTime, limit: $limit, includeResources: true) {
      data nextPageTimestamp
    }
  }}
}
"""
WCL_EVENT_VIEW_QUERY = """
query ChickenbroEventView($code: String!, $fightIds: [Int], $sourceId: Int,
  $dataType: EventDataType, $startTime: Float, $endTime: Float, $limit: Int) {
  reportData { report(code: $code) {
    title startTime endTime
    fights { id name difficulty kill startTime endTime }
    masterData { gameVersion logVersion }
    events(fightIDs: $fightIds, sourceID: $sourceId, dataType: $dataType,
      startTime: $startTime, endTime: $endTime, limit: $limit, includeResources: true) {
      data nextPageTimestamp
    }
  }}
}
"""
WCL_OVERVIEW_QUERY = """
query ChickenbroOverview($code: String!, $fightIds: [Int], $sourceId: Int) {
  reportData { report(code: $code) {
    title startTime endTime
    fights { id name difficulty kill startTime endTime }
    masterData { gameVersion logVersion actors { id name type subType } }
    playerDetails(fightIDs: $fightIds, includeCombatantInfo: true)
    casts: table(fightIDs: $fightIds, sourceID: $sourceId, dataType: Casts)
    damage: table(fightIDs: $fightIds, sourceID: $sourceId, dataType: DamageDone)
  }}
}
"""
_RUN_READER = ContextVar('wcl_run_reader', default=None)
_STATISTICS_DEADLINE = ContextVar('wcl_statistics_deadline', default=None)


class WclRunReader:
    """Reuse verified identical requests and fight context within one run.

    No global/user-crossing cache. Context expires after 60s for live logs and
    is capped at 16 scopes / 4 MiB. Upstream partial/error responses are not cached.
    """
    def __init__(self):
        self.contexts = {}
        self.results = {}
        self.pending = {}
        self.lock = threading.RLock()
        self.started = monotonic()

    def __call__(self, request):
        if monotonic()-self.started >= 360:
            return {'sourceStatus':'partial','blockers':['Research time budget exhausted. Finish with verified evidence and explicit gaps; do not request more pages.'],
                'nextActions':['Write the answer now using only evidence already obtained.']}
        from concurrent.futures import Future
        key = json.dumps({'url': normalize_wcl_report_url(request.get('wclUrl', '')),
                          'options': validate_wcl_options(request.get('options'))}, sort_keys=True)
        with self.lock:
            self.results = {k:v for k,v in self.results.items() if monotonic()-v[0] < 60}
            if key in self.results:
                return deepcopy(self.results[key][1])
            pending = self.pending.get(key)
            owner = pending is None
            if owner:
                pending = self.pending[key] = Future()
        if not owner:
            return deepcopy(pending.result(timeout=max(0.01, 360-(monotonic()-self.started))))
        token = _RUN_READER.set(self)
        try:
            result = build_wcl_log_evidence(request)
            if result.get('sourceStatus') == 'verified':
                size = len(json.dumps(result, ensure_ascii=False).encode())
                with self.lock:
                    if len(self.results) < 16 and sum(v[2] for v in self.results.values())+size <= 4194304:
                        self.results[key] = (monotonic(), deepcopy(result), size)
            pending.set_result(deepcopy(result))
            return deepcopy(result)
        except BaseException as error:
            pending.set_exception(error)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
            _RUN_READER.reset(token)

    def query(self, query, variables):
        if query != WCL_REPORT_EVIDENCE_QUERY:
            return _graphql(query,variables)
        key = json.dumps({k:variables[k] for k in ('code','fightIds','sourceId')},sort_keys=True)
        with self.lock:
            self.contexts = {k:v for k,v in self.contexts.items() if monotonic()-v[0]<60}
            cached = self.contexts.get(key)
        data = _graphql(WCL_EVENTS_QUERY if cached else query,variables)
        report = (data.get('reportData') or {}).get('report')
        if cached and isinstance(report,Mapping):
            data = deepcopy(data)
            data['reportData']['report'] = {**deepcopy(cached[1]),**report}
        elif isinstance(report,Mapping) and not data.get('_fieldErrors'):
            context = {k:v for k,v in report.items() if k!='events'}
            size = len(json.dumps(context,ensure_ascii=False).encode())
            with self.lock:
                if len(self.contexts)<16 and sum(v[2] for v in self.contexts.values())+size<=4194304:
                    self.contexts[key] = (monotonic(),deepcopy(context),size)
        return data


def _text(value: Any) -> str:
    return str(value or "").strip()


def warcraftlogs_credentials_state() -> dict[str, Any]:
    return configured_warcraftlogs_credentials_state(os.environ)


def _redact_secret(text: Any) -> str:
    value = _text(text)
    for name in (
        "WOW_WARCRAFTLOGS_CLIENT_ID",
        "WOW_WARCRAFTLOGS_CLIENT_SECRET",
        "WOW_WARCRAFTLOGS_API_KEY",
    ):
        secret = os.environ.get(name, "").strip()
        if secret:
            value = value.replace(secret, "[redacted]")
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", value)
    value = re.sub(r"(?i)(client_secret=)[^&\s]+", r"\1[redacted]", value)
    return value[:360]


def _timeout_seconds(timeout_seconds: Any = None) -> int:
    return warcraftlogs_timeout_seconds(timeout_seconds, env=os.environ)


def _oauth_token(timeout_seconds: Any = None) -> str:
    return chat_warcraftlogs_oauth_token(
        timeout_seconds,
        env=os.environ,
        opener=urlopen,
    )


def _graphql(
    query: str,
    variables: Mapping[str, Any] | None = None,
    *,
    token: str | None = None,
    timeout_seconds: Any = None,
) -> Mapping[str, Any]:
    request_timeout = _timeout_seconds(timeout_seconds)
    statistics_deadline = _STATISTICS_DEADLINE.get()
    if statistics_deadline is not None:
        request_timeout = min(request_timeout, statistics_deadline - monotonic())
    started_at = monotonic()
    if timeout_seconds is not None:
        try:
            request_timeout = min(request_timeout, float(timeout_seconds))
        except (TypeError, ValueError):
            pass
    reader = _RUN_READER.get()
    if reader is not None:
        request_timeout = min(request_timeout, 360 - (started_at-reader.started))
    if not isfinite(request_timeout) or request_timeout <= 0:
        raise WarcraftLogsProviderError('Warcraft Logs request deadline exhausted')
    graphql_url = os.environ.get(
        "WOW_WARCRAFTLOGS_GRAPHQL_URL",
        "https://www.warcraftlogs.com/api/v2/client",
    ).strip()
    access_token = token or _oauth_token(request_timeout)
    request = Request(
        graphql_url,
        data=json.dumps({"query": query, "variables": dict(variables or {})}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "wow-mini-program-wcl-sync",
        },
        method="POST",
    )
    remaining_timeout = request_timeout - (monotonic() - started_at)
    if remaining_timeout <= 0:
        raise WarcraftLogsProviderError('Warcraft Logs request deadline exhausted')
    try:
        with urlopen(request, timeout=remaining_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403) and token is None:
            invalidate_chat_warcraftlogs_oauth_token(access_token, env=os.environ, opener=urlopen)
        raise
    if monotonic() - started_at >= request_timeout:
        raise WarcraftLogsProviderError('Warcraft Logs request deadline exhausted')
    if not isinstance(payload, Mapping):
        raise RuntimeError("Warcraft Logs GraphQL response was invalid")
    errors = payload.get("errors")
    if errors:
        message = "; ".join(
            _text(item.get("message") if isinstance(item, Mapping) else item)
            for item in errors
        )
        data = payload.get("data")
        report = (data.get("reportData") or {}).get("report") if isinstance(data, Mapping) else None
        if isinstance(report, Mapping) and report.get("fights"):
            return {**data, "_fieldErrors": [_redact_secret(message)[:1000]]}
        raise RuntimeError(_redact_secret(message or "Warcraft Logs GraphQL returned errors"))
    data = payload.get("data")
    return data if isinstance(data, Mapping) else {}


def _summarize_events(events: Any) -> dict[str, int]:
    summary = {
        "total": 0,
        "casts": 0,
        "buffEvents": 0,
        "deaths": 0,
        "damageEvents": 0,
        "healingEvents": 0,
        "mechanicEvents": 0,
    }
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, Mapping):
            continue
        summary["total"] += 1
        event_type = _text(event.get("type")).lower()
        if event_type == "cast":
            summary["casts"] += 1
        elif "buff" in event_type:
            summary["buffEvents"] += 1
        elif event_type == "death":
            summary["deaths"] += 1
        elif event_type == "damage":
            summary["damageEvents"] += 1
        elif event_type in {"heal", "healing"}:
            summary["healingEvents"] += 1
        elif event_type:
            summary["mechanicEvents"] += 1
    return summary


def _normalize_fight(fight: Any) -> dict[str, Any]:
    if not isinstance(fight, Mapping):
        return {}
    return {
        "id": _text(fight.get("id")),
        "name": _text(fight.get("name")),
        "difficulty": fight.get("difficulty") or "",
        "kill": bool(fight.get("kill")),
        "startTime": fight.get("startTime") or 0,
        "endTime": fight.get("endTime") or 0,
    }


def normalize_wcl_report_url(url: str) -> str:
    """Drop WCL display-only parameters; retain strict host/identity validation."""
    parts = urlsplit(url)
    def clean(value: str) -> str:
        return urlencode([(k, v) for k, v in parse_qsl(value, keep_blank_values=True)
                          if k not in {"type", "view"}])
    candidate = urlunsplit((parts.scheme, parts.netloc, parts.path,
                           clean(parts.query), clean(parts.fragment)))
    parsed = parse_character_source_url(candidate)
    if not parsed.report_code:
        raise InvalidSourceLink()
    return parsed.url


def _extract_reference(request_data: Any) -> dict[str, str]:
    source = request_data if isinstance(request_data, Mapping) else {}
    text = "\n".join(
        _text(source.get(key))
        for key in ("wclUrl", "prompt", "question")
        if _text(source.get(key))
    )
    url_match = re.search(
        r"https://(?:(?:www|cn)\.)?warcraftlogs\.com/reports/([A-Za-z0-9]+)[^\s<>\"]*",
        text,
    )
    code = url_match.group(1) if url_match else ""
    source_url = url_match.group(0).rstrip(".,)") if url_match else ""
    if source_url:
        try:
            parsed = parse_character_source_url(normalize_wcl_report_url(source_url))
            return {"reportCode": parsed.report_code, "sourceUrl": parsed.url,
                    "fightId": str(parsed.fight_id or ""), "sourceId": str(parsed.actor_id or "")}
        except InvalidSourceLink:
            return {"reportCode": "", "sourceUrl": "", "fightId": "", "sourceId": ""}
    if not code:
        code_match = re.search(
            r"\b(?:wcl|report)\s*[:#= ]\s*([A-Za-z0-9]{6,})\b",
            text,
            re.IGNORECASE,
        )
        code = code_match.group(1) if code_match else ""
    fight_id = ""
    if source_url:
        fight_match = re.search(r"(?:[?#&]|&amp;)fight=([A-Za-z0-9_-]+)", source_url)
        fight_id = fight_match.group(1) if fight_match else ""
    return {"reportCode": code, "sourceUrl": source_url, "fightId": fight_id}


def _bounded_table(table: Any) -> dict[str, Any]:
    data = table.get("data", {}) if isinstance(table, Mapping) else {}
    if not isinstance(data, Mapping):
        return {}
    keys = ("id", "guid", "name", "type", "total", "totalUses", "hitCount", "tickCount",
            "totalTime", "activeTime", "count", "uses", "uptime", "uptimePercentage")
    rows = data.get("entries", [])
    return {
        "entries": [{key: (value[:240] if isinstance(value, str) else value)
                     for key, value in row.items() if key in keys and isinstance(value, (str, int, float, bool))}
                    for row in rows[:100] if isinstance(row, Mapping)] if isinstance(rows, list) else [],
        "rowsTruncated": isinstance(rows, list) and len(rows) > 100,
        "totalTime": data.get("totalTime") if isinstance(data.get("totalTime"), (int, float)) else None,
    }


WCL_EVENT_TYPES = {"All", "Buffs", "Casts", "CombatantInfo", "DamageDone", "DamageTaken",
                   "Deaths", "Debuffs", "Dispels", "Healing", "Interrupts", "Resources", "Summons", "Threat"}


def validate_wcl_options(options: Any) -> dict[str, Any]:
    if options is None:
        return {}
    if not isinstance(options, Mapping) or set(options) - {"dataType", "startTime", "endTime", "limit", "view", "maxPages"}:
        raise InvalidSourceLink("invalid WCL event options")
    result = dict(options)
    if result.get('view', 'full') not in ('full', 'overview', 'events', 'statistics'):
        raise InvalidSourceLink('invalid WCL view')
    if 'maxPages' in result and (result.get('view') != 'statistics' or type(result['maxPages']) is not int or not 1 <= result['maxPages'] <= 5):
        raise InvalidSourceLink('maxPages requires statistics view and must be 1-5')
    if result.get('view') == 'statistics' and not {'startTime','endTime'} <= result.keys():
        raise InvalidSourceLink('statistics require an explicit startTime/endTime window')
    if result.get('view') == 'overview' and {'startTime','endTime','dataType'} & result.keys():
        raise InvalidSourceLink('overview is whole-fight only; use events/statistics for window filters')
    if "dataType" in result and (not isinstance(result["dataType"], str) or result["dataType"] not in WCL_EVENT_TYPES):
        raise InvalidSourceLink("invalid WCL event type")
    for key in ("startTime", "endTime", "limit"):
        if key not in result:
            continue
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0 or value > 1e12:
            raise InvalidSourceLink("invalid WCL event range")
    if "limit" in result and (not isinstance(result["limit"], int) or not 1 <= result["limit"] <= 1000):
        raise InvalidSourceLink("WCL event limit must be 1-1000")
    if "endTime" in result and result["endTime"] <= result.get("startTime", 0):
        raise InvalidSourceLink("WCL endTime must be after startTime")
    return result


def _bounded_json(value: Any, *, depth: int = 0, truncated: list[bool]) -> Any:
    if depth > 10:
        truncated[0] = True
        return None
    if isinstance(value, Mapping):
        if len(value) > 200:
            truncated[0] = True
        return {str(k)[:120]: _bounded_json(v, depth=depth + 1, truncated=truncated)
                for k, v in list(value.items())[:200]}
    if isinstance(value, list):
        if len(value) > 200:
            truncated[0] = True
        return [_bounded_json(v, depth=depth + 1, truncated=truncated) for v in value[:200]]
    if isinstance(value, str):
        if len(value) > 2000:
            truncated[0] = True
        return value[:2000]
    return value if value is None or isinstance(value, (int, float, bool)) else None


def _fetch_v2_evidence(reference: Mapping[str, str], credential_state: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, Any]:
    fight_id = _text(reference.get("fightId"))
    fight_ids = [int(fight_id)] if fight_id.isdigit() else []
    options = dict(options)
    # WCL may return an empty page when startTime is provided but endTime is
    # null, even though nextPageTimestamp indicated remaining fight events.
    # Resolve an explicit report-relative boundary for such continuation calls.
    if "startTime" in options and "endTime" not in options:
        bounds = _graphql("query($code:String!){reportData{report(code:$code){fights{id endTime}}}}",
                          {"code": reference["reportCode"]})
        report_bounds = (bounds.get("reportData") or {}).get("report") or {}
        ends = [f.get("endTime", 0) for f in report_bounds.get("fights", [])
                if isinstance(f, Mapping) and (not fight_id or str(f.get("id")) == fight_id)]
        end = max(ends, default=0)
        if not end or end <= options["startTime"]:
            raise InvalidSourceLink("event startTime is outside the report/fight range")
        options["endTime"] = end
    discovery = not fight_ids and not ("startTime" in options and "endTime" in options)
    query = ("query($code:String!){reportData{report(code:$code){title startTime endTime "
             "fights{id name difficulty kill startTime endTime} "
             "masterData{gameVersion logVersion actors{id name type subType}}}}}"
             if discovery else WCL_REPORT_EVIDENCE_QUERY)
    variables = {"code": reference["reportCode"]} if discovery else {
        "code": reference["reportCode"], "fightIds": fight_ids or None,
        "sourceId": int(reference["sourceId"]) if reference.get("sourceId", "").isdigit() else None,
        "dataType": options.get("dataType", "All"), "startTime": options.get("startTime"),
        "endTime": options.get("endTime"), "limit": options.get("limit", 300)}
    view = options.get('view', 'full')
    if not discovery and view == 'events':
        query = WCL_EVENT_VIEW_QUERY
    elif not discovery and view == 'overview':
        query = WCL_OVERVIEW_QUERY
        variables = {k:variables[k] for k in ('code', 'fightIds', 'sourceId')}
    reader = _RUN_READER.get()
    data = reader.query(query, variables) if reader else _graphql(query, variables)
    field_errors = data.get("_fieldErrors", [])
    # The discovery query never requests tables without a valid scope.
    # Preserve useful metadata when independent statistics fail.
    report_data = data.get("reportData") if isinstance(data, Mapping) else {}
    report = report_data.get("report") if isinstance(report_data, Mapping) else {}
    if not isinstance(report, Mapping) or not report:
        raise RuntimeError("Warcraft Logs GraphQL response did not include report data")
    fights = [_normalize_fight(item) for item in report.get("fights") or []]
    selected_fight = next((item for item in fights if item.get("id") == fight_id), {}) if fight_id else {}
    if fight_id and not selected_fight:
        raise RuntimeError("The requested fight was not found in this report")
    events_payload = report.get("events")
    events = events_payload.get("data") if isinstance(events_payload, Mapping) else []
    master = report.get("masterData") or {}
    actors = master.get("actors", []) if isinstance(master, Mapping) else []
    next_page = events_payload.get("nextPageTimestamp") if isinstance(events_payload, Mapping) else None
    details = report.get("playerDetails") or {}
    detail_data = details.get("data") or {} if isinstance(details, Mapping) else {}
    groups = detail_data.get("playerDetails", {}) if isinstance(detail_data, Mapping) else {}
    players = [p for group in groups.values() if isinstance(group, list) for p in group
               if isinstance(p, Mapping) and (not reference.get("sourceId") or str(p.get("id")) == reference["sourceId"])] if isinstance(groups, Mapping) else []
    context_truncated = [len(players) > 40]
    player_keys = {"id", "name", "type", "server", "region", "specs", "minItemLevel", "maxItemLevel", "combatantInfo"}
    if not reference.get("sourceId"):
        player_keys.remove("combatantInfo")
    players = [_bounded_json({k: v for k, v in p.items() if k in player_keys}, truncated=context_truncated) for p in players[:40]]
    event_truncated = [False]
    event_rows = [_bounded_json(e, truncated=event_truncated) for e in events if isinstance(e, Mapping)] if isinstance(events, list) else []
    result = {
        "schemaRevision": "wcl-log-evidence-v1",
        "status": "ready",
        "sourceStatus": "partial" if field_errors else "verified",
        "queryScope": "report_discovery" if discovery else "scoped_analysis",
        "credentialMode": credential_state["mode"],
        "api": credential_state["api"],
        "reportCode": reference["reportCode"],
        "sourceUrl": reference["sourceUrl"],
        "fightId": selected_fight.get("id") or fight_id,
        "reportTitle": _text(report.get("title")),
        "reportWindow": {
            "startTime": report.get("startTime") or 0,
            "endTime": report.get("endTime") or 0,
        },
        "fight": selected_fight,
        "fights": fights[:100],
        "fightsTruncated": len(fights) > 100,
        "eventSummary": _summarize_events(events),
        "sourceId": reference.get("sourceId") or None,
        "players": players,
        "playersTruncated": context_truncated[0],
        "gameVersion": master.get("gameVersion"),
        "logVersion": master.get("logVersion"),
        "versionScope": "WCL gameVersion/logVersion are format/product identifiers, not a verified patch number.",
        "events": event_rows,
        "actors": [{key: (value[:160] if isinstance(value, str) else value)
                    for key, value in item.items() if key in {"id", "name", "type", "subType"}
                    and isinstance(value, (str, int))}
                   for item in actors if isinstance(item, Mapping) and item.get("type") == "Player"][:100],
        "actorsTruncated": sum(isinstance(item, Mapping) and item.get("type") == "Player" for item in actors) > 100,
        "casts": _bounded_table(report.get("casts")),
        "damage": _bounded_table(report.get("damage")),
        "eventPage": {"limit": options.get("limit", 300), "count": len(event_rows),
                      "dataType": options.get("dataType", "All"), "startTime": options.get("startTime"),
                      "endTime": options.get("endTime", selected_fight.get("endTime") or max((f.get("endTime", 0) for f in fights), default=0)),
                      "fieldsTruncated": event_truncated[0],
                      "nextPageTimestamp": next_page,
                      "complete": isinstance(events_payload, Mapping) and "nextPageTimestamp" in events_payload and next_page is None,
                      "scope": "event sample only; tables are aggregated independently over the selected filters"},
        "missingInputs": [],
        "blockers": field_errors,
        "evidenceRefs": ["wcl.report", "wcl.fight"] if discovery else ["wcl.report", "wcl.fight", "wcl.events"],
        "nextActions": (["Report metadata only: no casts, damage or events were queried. Select a fight id from fights and query again with fight= and source= as needed. If the user has not identified a fight, ask them to select one or explicitly explain which fights you will analyze."] if discovery else []) + (["Some fields failed; use only returned data, report the missing scope and retry the affected query. Do not treat missing fields as zero."] if field_errors else []) + [
            "Choose follow-up queries as needed. Filter an actor with source= in the URL; options.dataType selects events. Set options.startTime to nextPageTimestamp to continue, preserving other filters. Times are report-relative milliseconds. Tables and player details cover the fight independently of event pagination.",
        ],
    }
    if view == 'events' and not discovery:
        for key in ('actors', 'actorsTruncated', 'fights', 'fightsTruncated', 'players', 'playersTruncated', 'casts', 'damage'):
            result.pop(key, None)
        result['nextActions'] = ['Event-only response. Continue from nextPageTimestamp with the same endTime/dataType/source. '
                                 'Use overview for whole-fight tables/gear; omitted tables are unknown, not zero.']
    if view == 'overview':
        for key in ('events', 'eventPage', 'eventSummary'):
            result.pop(key, None)
        result['evidenceRefs'] = ['wcl.report', 'wcl.fight']
        if not discovery:
            result['nextActions'] = ['Whole-fight tables/gear only; no events were requested. '
                                     'Use events for a sequence or statistics for an explicit actor/time window.']
    result['view'] = view
    return result


def build_wcl_log_evidence(request_data: Mapping[str, Any] | None) -> dict[str, Any]:
    options = validate_wcl_options((request_data or {}).get("options"))
    reference = _extract_reference(request_data)
    if options.get('view') == 'statistics' and (not reference.get('sourceId','').isdigit() or not reference.get('fightId','').isdigit()):
        raise InvalidSourceLink('statistics require explicit fight and source IDs')
    credential_state = warcraftlogs_credentials_state()
    if not reference["reportCode"]:
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "missing_input",
            "sourceStatus": "missing_report",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": "",
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": ["wcl.report"],
            "evidenceRefs": ["wcl.report"],
            "nextActions": [
                "Paste a Warcraft Logs report URL or report code before requesting log analysis.",
                "Include fight id, boss, difficulty, class, spec, and the question you want answered.",
            ],
        }
    if not credential_state["configured"]:
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "blocked",
            "sourceStatus": "missing_credentials",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": reference["reportCode"],
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": ["wcl.credentials"],
            "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
            "nextActions": [
                "Configure Warcraft Logs API credentials before fetching report events.",
                "Do not infer rankings, parses, DPS, HPS, or cooldown mistakes until log evidence is fetched.",
            ],
        }
    if credential_state["mode"] != "v2_oauth":
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "blocked",
            "sourceStatus": "unsupported_credentials",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": reference["reportCode"],
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": ["wcl.v2_credentials"],
            "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
            "nextActions": ["Configure WCL v2 OAuth client credentials for report event queries."],
        }
    try:
        if options.get('view') == 'statistics':
            from server.app.chickenbro.wcl_statistics import summarize_window
            token = _STATISTICS_DEADLINE.set(monotonic() + 20)
            try:
                return summarize_window(reference, options, credential_state, _fetch_v2_evidence)
            finally:
                _STATISTICS_DEADLINE.reset(token)
        return _fetch_v2_evidence(reference, credential_state, options)
    except Exception as error:
        return {
            "schemaRevision": "wcl-log-evidence-v1",
            "status": "blocked",
            "sourceStatus": "blocked",
            "credentialMode": credential_state["mode"],
            "api": credential_state["api"],
            "reportCode": reference["reportCode"],
            "sourceUrl": reference["sourceUrl"],
            "fightId": reference["fightId"],
            "missingInputs": ["wcl.graphql_fetch"],
            "blockers": [_redact_secret(error)],
            "evidenceRefs": ["wcl.reportCode", "wcl.credentials"],
            "nextActions": [
                "Retry the Warcraft Logs GraphQL fetch after checking report visibility, fight id and API credentials.",
                "Do not infer rankings, parses, DPS, HPS, casts, deaths or cooldown mistakes until log evidence is fetched.",
            ],
        }


__all__ = ["WCL_REPORT_EVIDENCE_QUERY", "build_wcl_log_evidence", "warcraftlogs_credentials_state"]
