"""Server-configured Warcraft Logs evidence reader for the v2 Chickenbro app.

This module owns the small, read-only WCL report query used by the native
Chickenbro Codex path. Credentials are read only in the API process and the
returned packet contains bounded report/fight/event facts, never credentials
or the OAuth token.
"""

import base64
import json
import os
import re
from collections.abc import Mapping
from math import ceil
from time import monotonic
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WCL_REPORT_EVIDENCE_QUERY = """
query WowMiniProgramReportEvidence($code: String!, $fightIds: [Int]) {
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
      events(fightIDs: $fightIds, limit: 300) {
        data
      }
    }
  }
}
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def warcraftlogs_credentials_state() -> dict[str, Any]:
    has_v2_credentials = bool(
        os.environ.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
        and os.environ.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    )
    if has_v2_credentials:
        return {
            "configured": True,
            "mode": "v2_oauth",
            "api": "warcraftlogs-v2-graphql",
        }
    if os.environ.get("WOW_WARCRAFTLOGS_API_KEY", "").strip():
        return {
            "configured": True,
            "mode": "v1_api_key",
            "api": "warcraftlogs-v1-rest",
        }
    return {
        "configured": False,
        "mode": "none",
        "api": "warcraftlogs-v2-graphql",
    }


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
    try:
        configured = int(os.environ.get("WOW_WARCRAFTLOGS_TIMEOUT_SECONDS", "15"))
    except (TypeError, ValueError):
        configured = 15
    configured = max(1, configured)
    if timeout_seconds is None:
        return configured
    try:
        return min(configured, max(1, int(timeout_seconds)))
    except (TypeError, ValueError):
        return configured


def _oauth_token(timeout_seconds: Any = None) -> str:
    client_id = os.environ.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Warcraft Logs v2 credentials are not configured")
    token_url = os.environ.get(
        "WOW_WARCRAFTLOGS_TOKEN_URL",
        "https://www.warcraftlogs.com/oauth/token",
    ).strip()
    request = Request(
        token_url,
        data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
        headers={
            "Authorization": "Basic " + base64.b64encode(
                f"{client_id}:{client_secret}".encode("utf-8")
            ).decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "wow-mini-program-wcl-sync",
        },
        method="POST",
    )
    with urlopen(request, timeout=_timeout_seconds(timeout_seconds)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = _text(payload.get("access_token")) if isinstance(payload, Mapping) else ""
    if not token:
        raise RuntimeError("Warcraft Logs OAuth response did not include an access token")
    return token


def _graphql(
    query: str,
    variables: Mapping[str, Any] | None = None,
    *,
    token: str | None = None,
    timeout_seconds: Any = None,
) -> Mapping[str, Any]:
    request_timeout = _timeout_seconds(timeout_seconds)
    started_at = monotonic()
    graphql_url = os.environ.get(
        "WOW_WARCRAFTLOGS_GRAPHQL_URL",
        "https://www.warcraftlogs.com/api/v2/client",
    ).strip()
    request = Request(
        graphql_url,
        data=json.dumps({"query": query, "variables": dict(variables or {})}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token or _oauth_token(request_timeout)}",
            "Content-Type": "application/json",
            "User-Agent": "wow-mini-program-wcl-sync",
        },
        method="POST",
    )
    remaining_timeout = max(1, ceil(request_timeout - (monotonic() - started_at)))
    with urlopen(request, timeout=remaining_timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("Warcraft Logs GraphQL response was invalid")
    errors = payload.get("errors")
    if errors:
        message = "; ".join(
            _text(item.get("message") if isinstance(item, Mapping) else item)
            for item in errors
        )
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


def _extract_reference(request_data: Any) -> dict[str, str]:
    source = request_data if isinstance(request_data, Mapping) else {}
    text = "\n".join(
        _text(source.get(key))
        for key in ("wclUrl", "prompt", "question")
        if _text(source.get(key))
    )
    url_match = re.search(
        r"https?://(?:www\.)?warcraftlogs\.com/reports/([A-Za-z0-9]+)[^\s<>\"]*",
        text,
    )
    code = url_match.group(1) if url_match else ""
    source_url = url_match.group(0).rstrip(".,)") if url_match else ""
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


def _fetch_v2_evidence(reference: Mapping[str, str], credential_state: Mapping[str, Any]) -> dict[str, Any]:
    fight_id = _text(reference.get("fightId"))
    fight_ids = [int(fight_id)] if fight_id.isdigit() else []
    data = _graphql(
        WCL_REPORT_EVIDENCE_QUERY,
        {"code": reference["reportCode"], "fightIds": fight_ids or None},
    )
    report_data = data.get("reportData") if isinstance(data, Mapping) else {}
    report = report_data.get("report") if isinstance(report_data, Mapping) else {}
    if not isinstance(report, Mapping) or not report:
        raise RuntimeError("Warcraft Logs GraphQL response did not include report data")
    fights = [_normalize_fight(item) for item in report.get("fights") or []]
    selected_fight = next((item for item in fights if item.get("id") == fight_id), {}) if fight_id else {}
    if not selected_fight and fights:
        selected_fight = fights[0]
    events_payload = report.get("events")
    events = events_payload.get("data") if isinstance(events_payload, Mapping) else []
    return {
        "schemaRevision": "wcl-log-evidence-v1",
        "status": "ready",
        "sourceStatus": "verified",
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
        "eventSummary": _summarize_events(events),
        "missingInputs": [],
        "blockers": [],
        "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
        "nextActions": [
            "Use this parsed WCL evidence together with the SimC result before making rotation or performance conclusions.",
            "Compare casts, buff uptime, deaths, damage and healing events against a matched sample window before ranking the player.",
        ],
    }


def build_wcl_log_evidence(request_data: Mapping[str, Any] | None) -> dict[str, Any]:
    reference = _extract_reference(request_data)
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
        return _fetch_v2_evidence(reference, credential_state)
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
