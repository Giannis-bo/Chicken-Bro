"""Bounded community evidence adapters for Chickenbro current-strength research."""

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import os
from threading import RLock
from time import monotonic

try:
    from .community_talent_sources.warcraftlogs import (
        class_name_for_wcl,
        metric_for_spec,
        spec_name_for_wcl,
    )
    from .simulator_payload import warcraftlogs_credentials_state, warcraftlogs_graphql
except ImportError:  # pragma: no cover - direct server module execution
    from community_talent_sources.warcraftlogs import (
        class_name_for_wcl,
        metric_for_spec,
        spec_name_for_wcl,
    )
    from simulator_payload import warcraftlogs_credentials_state, warcraftlogs_graphql


PUBLIC_WCL_RANKINGS_QUERY = """
query WowMiniProgramChickenbroPublicMplusRankings(
  $encounterId: Int!,
  $className: String!,
  $specName: String!,
  $metric: CharacterRankingMetricType!,
  $partition: Int,
  $page: Int!
) {
  worldData {
    encounter(id: $encounterId) {
      id
      name
      characterRankings(
        page: $page,
        partition: $partition,
        className: $className,
        specName: $specName,
        metric: $metric
      )
    }
  }
}
"""

_PUBLIC_WCL_CACHE_TTL_SECONDS = 60
_PUBLIC_WCL_MAX_REQUESTS_PER_WINDOW = 12
_PUBLIC_WCL_RATE_WINDOW_SECONDS = 60
_PUBLIC_WCL_LOCK = RLock()
_PUBLIC_WCL_CACHE = {}
_PUBLIC_WCL_INFLIGHT = set()
_PUBLIC_WCL_REQUEST_TIMES = deque()


def _text(value):
    return str(value or "").strip()


def _positive_int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def configured_public_wcl_mplus_target(environment=None):
    """Return an explicitly-owned current M+ target, never a heuristic zone."""
    environment = environment if isinstance(environment, dict) else os.environ
    encounter_id = _positive_int(environment.get("WOW_CHICKENBRO_WCL_PUBLIC_MPLUS_ENCOUNTER_ID"))
    partition = _positive_int(environment.get("WOW_CHICKENBRO_WCL_PUBLIC_MPLUS_PARTITION"))
    season_label = _text(environment.get("WOW_CHICKENBRO_WCL_PUBLIC_MPLUS_SEASON_LABEL"))
    if not encounter_id or not partition or not season_label:
        return None
    return {
        "encounterId": encounter_id,
        "partition": partition,
        "seasonLabel": season_label[:120],
    }


def reset_public_wcl_rankings_state():
    """Clear local rate/cache state for deterministic tests only."""
    with _PUBLIC_WCL_LOCK:
        _PUBLIC_WCL_CACHE.clear()
        _PUBLIC_WCL_INFLIGHT.clear()
        _PUBLIC_WCL_REQUEST_TIMES.clear()


def _ranking_rows(payload):
    world_data = payload.get("worldData") if isinstance(payload, dict) else {}
    encounter = world_data.get("encounter") if isinstance(world_data, dict) else {}
    rankings = encounter.get("characterRankings") if isinstance(encounter, dict) else {}
    rows = rankings.get("rankings") if isinstance(rankings, dict) else []
    return encounter if isinstance(encounter, dict) else {}, [row for row in rows if isinstance(row, dict)]


def _partial_result(evidence, limitation):
    return {
        "sourceKey": "warcraftlogs_public_rankings",
        "status": "partial",
        "facts": [],
        "evidence": [evidence],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": [],
    }


def _wcl_cache_key(class_key, spec_key, target):
    return (
        class_key,
        spec_key,
        int(target["encounterId"]),
        int(target["partition"]),
        str(target["seasonLabel"]),
    )


def _cached_or_permitted_wcl_request(cache_key, now):
    with _PUBLIC_WCL_LOCK:
        cached = _PUBLIC_WCL_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return "cached", deepcopy(cached[1])
        if cached:
            _PUBLIC_WCL_CACHE.pop(cache_key, None)
        if cache_key in _PUBLIC_WCL_INFLIGHT:
            return "inflight", None
        while _PUBLIC_WCL_REQUEST_TIMES and _PUBLIC_WCL_REQUEST_TIMES[0] <= now - _PUBLIC_WCL_RATE_WINDOW_SECONDS:
            _PUBLIC_WCL_REQUEST_TIMES.popleft()
        if len(_PUBLIC_WCL_REQUEST_TIMES) >= _PUBLIC_WCL_MAX_REQUESTS_PER_WINDOW:
            return "rate_limited", None
        _PUBLIC_WCL_INFLIGHT.add(cache_key)
        _PUBLIC_WCL_REQUEST_TIMES.append(now)
        return "permitted", None


def _finish_wcl_request(cache_key, now, result):
    with _PUBLIC_WCL_LOCK:
        _PUBLIC_WCL_INFLIGHT.discard(cache_key)
        if result.get("status") == "source_reference":
            _PUBLIC_WCL_CACHE[cache_key] = (now + _PUBLIC_WCL_CACHE_TTL_SECONDS, deepcopy(result))


def build_wcl_public_rankings_tool_result(
    intent,
    *,
    credentials_loader=warcraftlogs_credentials_state,
    target_loader=configured_public_wcl_mplus_target,
    graphql_loader=warcraftlogs_graphql,
    clock=monotonic,
    checked_at_factory=lambda: datetime.now(timezone.utc).isoformat(),
):
    """Read one configured current public M+ ranking page without player data.

    This source is a supplementary activity/coverage signal.  It deliberately
    does not calculate a cross-specialization tier or satisfy the comparative
    strength evidence requirement by itself.
    """
    intent = intent if isinstance(intent, dict) else {}
    class_key = _text(intent.get("classKey")).lower()
    spec_key = _text(intent.get("specKey")).lower()
    evidence_ref = f"wcl.public.{class_key or 'unknown'}.{spec_key or 'unknown'}.mythic_plus"
    evidence = {
        "id": evidence_ref,
        "sourceName": "Warcraft Logs",
        "sourceUrl": "https://www.warcraftlogs.com/zone/rankings/latest",
        "productPhase": _text(intent.get("productPhase")).lower() or "retail",
        "scenarioKey": "mythic_plus",
    }
    credentials = credentials_loader() if callable(credentials_loader) else {}
    if not isinstance(credentials, dict) or not credentials.get("configured"):
        return {
            **_partial_result(evidence, "Warcraft Logs public rankings credentials are unavailable."),
            "status": "missing_credentials",
        }
    if _text(credentials.get("api")) != "warcraftlogs-v2-graphql":
        return {
            **_partial_result(evidence, "Warcraft Logs public rankings require the v2 GraphQL source."),
            "status": "blocked",
        }
    if not class_key or not spec_key:
        return _partial_result(evidence, "A resolved class and specialization are required for public WCL rankings.")
    if _text(intent.get("scenarioKey") or "mythic_plus").lower() != "mythic_plus":
        return _partial_result(evidence, "Warcraft Logs public rankings source is only configured for Mythic+.")
    target = target_loader() if callable(target_loader) else None
    if not isinstance(target, dict):
        return _partial_result(evidence, "Warcraft Logs current Mythic+ target contract is not configured.")
    encounter_id = _positive_int(target.get("encounterId"))
    partition = _positive_int(target.get("partition"))
    season_label = _text(target.get("seasonLabel"))
    if not encounter_id or not partition or not season_label:
        return _partial_result(evidence, "Warcraft Logs current Mythic+ target contract is invalid.")
    evidence.update({
        "encounterId": encounter_id,
        "partition": partition,
        "seasonLabel": season_label[:120],
        "sourceScope": "configured_current_mythic_plus",
    })
    cache_key = _wcl_cache_key(class_key, spec_key, {"encounterId": encounter_id, "partition": partition, "seasonLabel": season_label})
    now = float(clock())
    admission, cached = _cached_or_permitted_wcl_request(cache_key, now)
    if admission == "cached":
        return cached
    if admission == "inflight":
        return _partial_result(evidence, "Warcraft Logs identical public rankings request is already in progress; no duplicate request was sent.")
    if admission == "rate_limited":
        return _partial_result(evidence, "Warcraft Logs public rankings rate budget is exhausted; no external request was sent.")
    try:
        metric = metric_for_spec(spec_key)
        data = graphql_loader(
            PUBLIC_WCL_RANKINGS_QUERY,
            {
                "encounterId": encounter_id,
                "className": class_name_for_wcl(class_key),
                "specName": spec_name_for_wcl(spec_key),
                "metric": metric,
                "partition": partition,
                "page": 1,
            },
            timeout_seconds=8,
        )
        encounter, rankings = _ranking_rows(data)
        if not rankings:
            result = _partial_result(
                evidence,
                "Warcraft Logs returned no configured current Mythic+ public ranking rows for this specialization.",
            )
        else:
            sample_count = len(rankings)
            evidence["checkedAt"] = _text(checked_at_factory())
            result = {
                "sourceKey": "warcraftlogs_public_rankings",
                "status": "source_reference",
                "facts": [{
                    "classKey": class_key,
                    "specKey": spec_key,
                    "scenarioKey": "mythic_plus",
                    "summary": "Warcraft Logs configured current Mythic+ public ranking rows are available for this specialization.",
                    "metric": metric,
                    "sampleCount": sample_count,
                    "analysisWindow": {
                        "encounterId": encounter_id,
                        "encounterName": _text(encounter.get("name")),
                        "partition": partition,
                        "seasonLabel": season_label[:120],
                        "page": 1,
                    },
                }],
                "evidence": [evidence],
                "evidenceRefs": [evidence_ref],
                "allowedNumbers": [str(sample_count)],
                "limitations": [
                    "WCL confirms configured current public Mythic+ rows for this specialization; its per-encounter metric is supplementary coverage evidence, not a cross-spec tier table.",
                ],
                "nextActions": [],
            }
    except Exception as error:
        result = {
            "sourceKey": "warcraftlogs_public_rankings",
            "status": "failed",
            "facts": [],
            "evidence": [evidence],
            "evidenceRefs": [],
            "limitations": [f"Warcraft Logs public rankings query failed: {type(error).__name__}."],
            "nextActions": [],
        }
    _finish_wcl_request(cache_key, now, result)
    return result
