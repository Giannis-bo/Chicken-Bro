"""Server-owned source queries exposed to the native Chickenbro Codex.

The Codex subprocess receives only a short-lived capability for this gateway.
WCL/Raider.IO credentials stay in the API process and are never forwarded to
the model or the MCP subprocess.
"""

import secrets
import copy
import json
from threading import RLock
from server.app.chickenbro.answer_grounding import collect_evidence
from server.app.chickenbro.research_budget import ResearchBudget
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from server.app.simulation.domain import SourceProvider
from server.app.simulation.sources import (
    InvalidSourceLink,
    parse_character_source_url,
)
from server.app.chickenbro.wcl_source import build_wcl_log_evidence, validate_wcl_options


SOURCE_GATEWAY_PATH = "/api/v2/internal/chickenbro/source-query"
DEFAULT_SOURCE_GATEWAY_URL = "http://127.0.0.1:8790" + SOURCE_GATEWAY_PATH
MAX_SOURCE_RESULT_BYTES = 180000  # Match ToolRecorder's UTF-8 serialization limit.


def _bounded_result(result: Mapping[str, Any]) -> Mapping[str, Any]:
    """Keep whole batch members; index exactly the receipt delivered to the model.

    First-fit preserves input order and every retained member's original coverage.
    An omitted member was queried, but supplies no evidence to this response.
    """
    def fits(value):
        return len(json.dumps(value, ensure_ascii=False).encode()) <= MAX_SOURCE_RESULT_BYTES

    if fits(result):
        return result
    omitted = {
        'sourceKey': _text(result.get('sourceKey'), 40) or 'source',
        'status': 'partial', 'facts': [], 'transportOmitted': True,
        'limitations': ['The query ran, but its result did not fit the bounded response. '
                        'No evidence from this member is delivered. Narrow the query to retrieve it.'],
    }
    members = result.get('results')
    if not isinstance(members, list) or not 1 <= len(members) <= 3:
        return omitted
    bounded = {**result, 'status': 'partial',
        'results': [dict(omitted) for _ in members],
        'transportProjection': {'originalMembers': len(members), 'retainedMembers': 0,
                                'omittedMembers': len(members)},
        'limitations': list(result.get('limitations') or []) + [
            'Some whole batch members were omitted to fit the response size limit. '
            'Retained members preserve their independent source coverage; input order is unchanged.'],
    }
    if not fits(bounded):
        return omitted
    retained = 0
    for index, member in enumerate(members):
        placeholder = bounded['results'][index]
        bounded['results'][index] = member
        if fits(bounded):
            retained += 1
        else:
            bounded['results'][index] = placeholder
    bounded['transportProjection'].update(retainedMembers=retained, omittedMembers=len(members)-retained)
    return bounded if fits(bounded) else omitted


class SourceGatewayUnauthorized(ValueError):
    code = "SOURCE_GATEWAY_UNAUTHORIZED"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def _safe_mapping(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {key: value[key] for key in keys if key in value and value[key] not in (None, "")}


class ServerConfiguredSourceQuery:
    """Query only the allowlisted source APIs from the API process."""

    def __init__(
        self,
        *,
        raiderio_research: Any | None = None,
        wcl_reader: Callable[[Mapping[str, str]], Mapping[str, Any]] | None = None,
    ):
        from server.app.chickenbro.raiderio_research import RaiderIOResearch
        self._raiderio = raiderio_research if raiderio_research is not None else RaiderIOResearch()
        self._wcl_reader = wcl_reader or build_wcl_log_evidence

    def query(self, provider: str, target: str, options: Mapping[str, Any] | None = None, *, web_state=None) -> dict[str, Any]:
        normalized_provider = _text(provider, 40).lower()
        options = options or {}
        if normalized_provider == 'public_web':
            if set(options) - {'start', 'match'}:
                raise InvalidSourceLink()
            from server.chickenbro_public_web_research import build_public_web_research_tool_result
            return build_public_web_research_tool_result({'target': target, **options}, state=web_state)
        if normalized_provider == 'warcraftlogs_batch':
            from server.app.chickenbro.wcl_source import normalize_wcl_report_url
            queries = options.get('queries')
            if target != 'reports' or set(options) != {'queries'} or not isinstance(queries,list) or not 1<=len(queries)<=3:
                raise InvalidSourceLink('bounded WCL batch required')
            validated = []
            for item in queries:
                if not isinstance(item,Mapping) or set(item)-{'target','options'}:
                    raise InvalidSourceLink('invalid batch item')
                url = normalize_wcl_report_url(item.get('target',''))
                parsed = parse_character_source_url(url)
                if parsed.provider is not SourceProvider.WARCRAFTLOGS:
                    raise InvalidSourceLink()
                event_options = validate_wcl_options(item.get('options'))
                event_options['limit'] = min(event_options.get('limit',200),200)
                validated.append((parsed.url,event_options))
            def fetch(item):
                try:
                    return self._query_warcraftlogs(*item)
                except Exception:
                    return {'sourceKey':'warcraftlogs','status':'partial','facts':[],
                        'limitations':['This batch member could not be queried; other members remain usable.']}
            with ThreadPoolExecutor(max_workers=3,thread_name_prefix='wcl-batch') as pool:
                results = list(pool.map(fetch,validated))
            return {'sourceKey':'warcraftlogs','status':'verified' if all(r.get('status')=='verified' for r in results) else 'partial',
                'results':results,'limitations':['Results retain input order and independent coverage; do not combine overlapping events as distinct events.']}
        if normalized_provider == "warcraftlogs_rankings":
            from server.app.chickenbro.wcl_rankings import query_wcl_rankings
            if target != "rankings":
                raise InvalidSourceLink()
            return query_wcl_rankings(options)
        if normalized_provider == "warcraftlogs_character":
            from server.app.chickenbro.character_discovery import discover_wcl_character
            if target != "character":
                raise InvalidSourceLink()
            return discover_wcl_character(options)
        if normalized_provider == "raiderio_rankings":
            if target != "rankings":
                raise InvalidSourceLink()
            return self._raiderio.rankings(options)
        if normalized_provider == "raiderio_batch":
            if target != "characters" or set(options) != {"targets"}:
                raise InvalidSourceLink()
            return self._raiderio.characters(options["targets"])
        if normalized_provider == "warcraftlogs":
            from server.app.chickenbro.wcl_source import normalize_wcl_report_url
            target = normalize_wcl_report_url(target)
        parsed = parse_character_source_url(target)
        if normalized_provider == "warcraftlogs" and parsed.provider is SourceProvider.WARCRAFTLOGS:
            return self._query_warcraftlogs(parsed.url, validate_wcl_options(options))
        if normalized_provider == "raiderio" and parsed.provider is SourceProvider.RAIDERIO:
            if options:
                raise InvalidSourceLink()
            return self._raiderio.character(parsed.url)
        raise InvalidSourceLink()

    def _query_warcraftlogs(self, target: str, options: Mapping[str, Any]) -> dict[str, Any]:
        evidence = self._wcl_reader({"wclUrl": target, "prompt": target, "options": options})
        evidence = evidence if isinstance(evidence, Mapping) else {}
        source_status = _text(evidence.get("sourceStatus"), 80).lower() or "blocked"
        report_code = _text(evidence.get("reportCode"), 128)
        fight_id = _text(evidence.get("fightId"), 40)
        verified = source_status == "verified"
        evidence_refs = [
            _text(value, 160)
            for value in (evidence.get("evidenceRefs") or [])
            if _text(value, 160)
        ] if verified or (source_status == 'partial' and evidence.get('statistics', {}).get('observedThrough', 0) > evidence.get('statistics', {}).get('startTime', 0)) else []
        reference_id = ":".join(("wcl", report_code or "unknown", fight_id or "selected"))
        source_evidence = {
            "id": reference_id,
            "sourceName": "Warcraft Logs",
            "sourceUrl": _text(evidence.get("sourceUrl"), 2048) or _text(target, 2048),
            "reportCode": report_code,
            "fightId": fight_id,
            "api": _text(evidence.get("api"), 80),
            "sourceStatus": source_status,
            "checkedAt": _utc_now().isoformat(),
        }
        limitations = [
            _text(value, 360)
            for value in (evidence.get("nextActions") or [])
            if _text(value, 360)
        ][:3]
        for value in (evidence.get("blockers") or []):
            clean = _text(value, 360)
            if clean and clean not in limitations:
                limitations.append(clean)
        if verified and evidence.get('view', 'full') == 'full':
            limitations.append(
                "Tables are scoped by fight/source filters. Event samples have their own coverage metadata; select relevant data and follow-up queries for the user's question."
            )
        elif not verified and not limitations:
            limitations.append("The configured Warcraft Logs API did not return verifiable report evidence.")

        if verified or source_status == 'partial':
            limitations.insert(0,
                "Casts count logged events, not manual button presses or GCD usage. "
                "Triggers and secondary effects can produce casts. Equal timestamps do not prove "
                "manual or triggered origin. Preserve counts; verify origin before recommending fewer casts.")

        result: dict[str, Any] = {
            "sourceKey": "warcraftlogs",
            "status": "verified" if verified else source_status,
            "facts": [],
            "evidence": [source_evidence],
            "evidenceRefs": evidence_refs,
            "limitations": limitations[:6],
            "nextActions": [
                _text(value, 360)
                for value in (evidence.get("nextActions") or [])
                if _text(value, 360)
            ][:4],
        }
        statistics = evidence.get('statistics') or {}
        observed_statistics = statistics.get('observedThrough', 0) > statistics.get('startTime', 0)
        if verified or (source_status == "partial" and (evidence.get("fights") or observed_statistics)):
            result["facts"] = [{
                "queryMode": "server_configured_warcraftlogs_api",
                "queryScope": evidence.get("queryScope", "scoped_analysis"),
                "reportCode": report_code,
                "fightId": fight_id,
                "reportTitle": _text(evidence.get("reportTitle"), 240),
                "reportWindow": _safe_mapping(evidence.get("reportWindow"), ("startTime", "endTime")),
                "fight": _safe_mapping(
                    evidence.get("fight"),
                    ("id", "name", "difficulty", "kill", "startTime", "endTime"),
                ),
                "eventSummary": _safe_mapping(
                    evidence.get("eventSummary"),
                    ("total", "casts", "buffEvents", "deaths", "damageEvents", "healingEvents", "mechanicEvents"),
                ),
                "actors": evidence.get("actors", []),
                "actorsTruncated": bool(evidence.get("actorsTruncated")),
                "fights": evidence.get("fights", []),
                "fightsTruncated": bool(evidence.get("fightsTruncated")),
                "casts": evidence.get("casts", {}),
                "damage": evidence.get("damage", {}),
                "eventPage": evidence.get("eventPage", {}),
                "sourceId": evidence.get("sourceId"),
                "players": evidence.get("players", []),
                "playersTruncated": bool(evidence.get("playersTruncated")),
                "gameVersion": evidence.get("gameVersion"),
                "logVersion": evidence.get("logVersion"),
                "versionScope": evidence.get("versionScope", ""),
                "events": evidence.get("events", []),
                "summary": "Returned fields only; consult queryScope, eventPage and limitations before drawing conclusions.",
            }]
            view = evidence.get('view', 'full')
            fact = result['facts'][0]
            if view != 'full':
                fact['view'] = view
            if view in ('events', 'statistics') and evidence.get('queryScope') != 'report_discovery':
                for key in ('actors','actorsTruncated','fights','fightsTruncated','players','playersTruncated','casts','damage'):
                    fact.pop(key, None)
            if view in ('overview', 'statistics'):
                for key in ('events','eventPage','eventSummary'):
                    fact.pop(key, None)
            if view == 'statistics':
                fact['statistics'] = statistics
        return result



class ChickenbroSourceGateway:
    def __init__(
        self,
        *,
        query_service: ServerConfiguredSourceQuery | Callable[[str, str], Mapping[str, Any]] | None = None,
        now: Callable[[], datetime] | None = None,
        capability_ttl_seconds: int = 600,
        research_budget=None,
        research_budget_factory=None,
    ):
        self._query_service = query_service or ServerConfiguredSourceQuery()
        self._now = now or _utc_now
        self._ttl = timedelta(seconds=max(60, min(900, int(capability_ttl_seconds))))
        self._capabilities: dict[str, datetime] = {}
        self._answer_evidence: dict[str, dict] = {}
        self._budgets = {}
        self._research_budget = research_budget
        self._research_budget_factory = research_budget_factory
        self._web_states = {}
        self._lock = RLock()

    def issue_capability(self, context=None) -> str:
        with self._lock:
            now = self._aware_now()
            self._prune(now)
            if len(self._capabilities) >= 256:
                raise SourceGatewayUnauthorized("source gateway capacity reached")
            budget = (self._research_budget_factory(context) if self._research_budget_factory
                      else self._research_budget or ResearchBudget())
            token = secrets.token_urlsafe(32)
            self._capabilities[token] = now + self._ttl
            self._budgets[token] = budget
            from server.chickenbro_public_web_research import PublicWebState
            self._web_states[token] = PublicWebState()
            return token

    def revoke(self, token: str) -> None:
        with self._lock:
            self._capabilities.pop(str(token or ""), None)
            self._answer_evidence.pop(str(token or ""), None)
            self._budgets.pop(str(token or ""), None)
            self._web_states.pop(str(token or ""), None)

    def query(self, token: str, provider: str, target: str, options: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        with self._lock:
            now = self._aware_now()
            self._prune(now)
            if not self._valid(token, now):
                raise SourceGatewayUnauthorized("source gateway capability is invalid or expired")
            if str(provider).lower().startswith('warcraftlogs'):
                index = self._answer_evidence.setdefault(token, {"reports": [], "groups": [], "truncated": False})
                index['attemptedWcl'] = True
            error, receipt = self._budgets[token].reserve(str(provider).strip().lower(), target, options)
            if error:
                return error
            web_state = self._web_states[token]
        if str(provider).strip().lower() == 'public_web' and isinstance(self._query_service, ServerConfiguredSourceQuery):
            result = self._query_service.query(provider, target, options, web_state=web_state)
        elif hasattr(self._query_service, "query"):
            result = self._query_service.query(provider, target, options=options) if options else self._query_service.query(provider, target)
        else:
            result = self._query_service(provider, target)
        if isinstance(result, Mapping):
            result = _bounded_result(result)
        with self._lock:
            self._prune(self._aware_now())
            if self._valid(token, self._aware_now()) and isinstance(result, Mapping):
                self._budgets[token].observe(receipt, result)
                self._answer_evidence[token] = collect_evidence(self._answer_evidence.get(token), result)
        return result if isinstance(result, Mapping) else {
            "sourceKey": str(provider or "source"),
            "status": "partial",
            "facts": [],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["The configured source API returned no bounded result."],
            "nextActions": [],
        }

    def research_status(self, token):
        with self._lock:
            if not self._valid(token, self._aware_now()):
                raise SourceGatewayUnauthorized('source gateway capability is invalid or expired')
            budget = self._budgets[token]
            return budget.status() if hasattr(budget, 'status') else {'state': 'active'}

    def answer_evidence(self, token: str) -> dict:
        with self._lock:
            now = self._aware_now()
            self._prune(now)
            if not self._valid(token, now):
                raise SourceGatewayUnauthorized("source gateway capability is invalid or expired")
            return copy.deepcopy(self._answer_evidence.get(token, {"reports": [], "groups": [], "truncated": False}))

    def _aware_now(self) -> datetime:
        value = self._now()
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def _valid(self, token: str, now: datetime) -> bool:
        value = str(token or "")
        expires_at = self._capabilities.get(value)
        return bool(expires_at and expires_at > now)

    def _prune(self, now: datetime) -> None:
        for token, expires_at in list(self._capabilities.items()):
            if expires_at <= now:
                self._capabilities.pop(token, None)
                self._answer_evidence.pop(token, None)
                self._budgets.pop(token, None)
                self._web_states.pop(token, None)


__all__ = (
    "ChickenbroSourceGateway",
    "DEFAULT_SOURCE_GATEWAY_URL",
    "SOURCE_GATEWAY_PATH",
    "ServerConfiguredSourceQuery",
    "SourceGatewayUnauthorized",
)
