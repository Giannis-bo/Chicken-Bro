"""Server-owned source queries exposed to the native Chickenbro Codex.

The Codex subprocess receives only a short-lived capability for this gateway.
WCL/Raider.IO credentials stay in the API process and are never forwarded to
the model or the MCP subprocess.
"""

import secrets
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from server.app.simulation.domain import SourceProvider
from server.app.simulation.sources import (
    CharacterSourceRouter,
    HttpxSourceGateway,
    InvalidSourceLink,
    parse_character_source_url,
)
from server.app.chickenbro.wcl_source import build_wcl_log_evidence, validate_wcl_options


SOURCE_GATEWAY_PATH = "/api/v2/internal/chickenbro/source-query"
DEFAULT_SOURCE_GATEWAY_URL = "http://127.0.0.1:8790" + SOURCE_GATEWAY_PATH


class SourceGatewayUnauthorized(ValueError):
    code = "SOURCE_GATEWAY_UNAUTHORIZED"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def _source_status(candidate: Any) -> str:
    readiness = getattr(candidate, "readiness", "")
    return _text(getattr(readiness, "value", readiness), 80).lower()


def _safe_mapping(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value[key]
        for key in keys
        if key in value and value[key] not in (None, "")
    }


def _safe_gear(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    allowed = ("itemId", "name", "itemLevel", "bonusIds", "gems", "enchant")
    result: dict[str, dict[str, Any]] = {}
    for slot, raw_item in value.items():
        if not isinstance(raw_item, Mapping):
            continue
        item = _safe_mapping(raw_item, allowed)
        if item:
            result[_text(slot, 80)] = item
    return result


def _safe_talents(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    if isinstance(value.get("loadout"), list):
        result["loadout"] = value["loadout"][:120]
    talent_string = _text(value.get("string"), 1000)
    if talent_string:
        result["string"] = talent_string
    return result


class ServerConfiguredSourceQuery:
    """Query only the allowlisted source APIs from the API process."""

    def __init__(
        self,
        *,
        character_router: CharacterSourceRouter | None = None,
        wcl_reader: Callable[[Mapping[str, str]], Mapping[str, Any]] | None = None,
    ):
        self._character_router = character_router or CharacterSourceRouter(
            HttpxSourceGateway(timeout_seconds=15)
        )
        self._wcl_reader = wcl_reader or build_wcl_log_evidence

    def query(self, provider: str, target: str, options: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized_provider = _text(provider, 40).lower()
        parsed = parse_character_source_url(target)
        if normalized_provider == "warcraftlogs" and parsed.provider is SourceProvider.WARCRAFTLOGS:
            return self._query_warcraftlogs(parsed.url, validate_wcl_options(options))
        if normalized_provider == "raiderio" and parsed.provider is SourceProvider.RAIDERIO:
            return self._query_raiderio(target)
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
        ] if verified else []
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
        if verified:
            limitations.append(
                "Tables are scoped by fight/source filters. Event samples have their own coverage metadata; select relevant data and follow-up queries for the user's question."
            )
        elif not limitations:
            limitations.append("The configured Warcraft Logs API did not return verifiable report evidence.")

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
        if verified:
            result["facts"] = [{
                "queryMode": "server_configured_warcraftlogs_api",
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
                "summary": "Warcraft Logs report evidence was fetched through the server-configured API.",
            }]
        return result

    def _query_raiderio(self, target: str) -> dict[str, Any]:
        candidate = self._character_router.resolve(target)
        snapshot = candidate.snapshot if isinstance(candidate.snapshot, Mapping) else {}
        character = _safe_mapping(
            snapshot.get("character"),
            ("name", "realm", "region", "classKey", "specKey", "raceKey", "level", "levelSource", "sourceLevel"),
        )
        provenance = candidate.provenance if isinstance(candidate.provenance, Mapping) else {}
        source_url = _text(provenance.get("sourceUrl"), 2048) or _text(candidate.source_url, 2048) or _text(target, 2048)
        raw_sha256 = _text(candidate.raw_sha256, 64)
        source_evidence = {
            "id": "raiderio:character:" + ":".join(
                _text(character.get(key), 120) for key in ("region", "realm", "name")
            ),
            "sourceName": "Raider.IO",
            "sourceUrl": source_url,
            "sourceStatus": "fetched" if character else _source_status(candidate),
            "sourceRevision": _text(provenance.get("sourceRevision"), 160),
            "fetchedAt": _text(provenance.get("fetchedAt"), 80),
            "rawSha256": raw_sha256,
        }
        if not character:
            return {
                "sourceKey": "raiderio",
                "status": _source_status(candidate) or "blocked",
                "facts": [],
                "evidence": [source_evidence],
                "evidenceRefs": [],
                "limitations": ["The configured Raider.IO API did not return a usable character profile."],
                "nextActions": ["Check the character region, realm slug and name, then retry the Raider.IO profile query."],
            }
        facts = {
            "queryMode": "server_configured_raiderio_api",
            "character": character,
            "gear": _safe_gear(snapshot.get("gear")),
            "talents": _safe_talents(snapshot.get("talents")),
            "profileSource": _text(snapshot.get("profileSource"), 80),
            "summary": "Raider.IO character profile was fetched through the server-configured API.",
        }
        return {
            "sourceKey": "raiderio",
            "status": "source_reference",
            "facts": [facts],
            "evidence": [source_evidence],
            "evidenceRefs": [source_evidence["id"]],
            "limitations": [
                "This is a Raider.IO character snapshot, not a Warcraft Logs combat record or a personal DPS verdict.",
                "The SimC application applies its max-level policy when the profile is used for simulation.",
            ],
            "nextActions": [],
        }


class ChickenbroSourceGateway:
    def __init__(
        self,
        *,
        query_service: ServerConfiguredSourceQuery | Callable[[str, str], Mapping[str, Any]] | None = None,
        now: Callable[[], datetime] | None = None,
        capability_ttl_seconds: int = 600,
    ):
        self._query_service = query_service or ServerConfiguredSourceQuery()
        self._now = now or _utc_now
        self._ttl = timedelta(seconds=max(60, min(900, int(capability_ttl_seconds))))
        self._capabilities: dict[str, datetime] = {}

    def issue_capability(self) -> str:
        now = self._aware_now()
        self._prune(now)
        token = secrets.token_urlsafe(32)
        self._capabilities[token] = now + self._ttl
        return token

    def revoke(self, token: str) -> None:
        self._capabilities.pop(str(token or ""), None)

    def query(self, token: str, provider: str, target: str, options: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        now = self._aware_now()
        if not self._valid(token, now):
            raise SourceGatewayUnauthorized("source gateway capability is invalid or expired")
        if hasattr(self._query_service, "query"):
            result = self._query_service.query(provider, target, options=options) if options else self._query_service.query(provider, target)
        else:
            result = self._query_service(provider, target)
        return result if isinstance(result, Mapping) else {
            "sourceKey": str(provider or "source"),
            "status": "partial",
            "facts": [],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["The configured source API returned no bounded result."],
            "nextActions": [],
        }

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


__all__ = (
    "ChickenbroSourceGateway",
    "DEFAULT_SOURCE_GATEWAY_URL",
    "SOURCE_GATEWAY_PATH",
    "ServerConfiguredSourceQuery",
    "SourceGatewayUnauthorized",
)
