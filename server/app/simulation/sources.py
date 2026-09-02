import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

from server.app.simulation.domain import SourceProvider, SourceReadiness
from server.app.simulation.snapshots import (
    CharacterSnapshotCandidate,
    missing_snapshot_fields,
    sha256_json,
)


class InvalidSourceLink(ValueError):
    def __init__(self, message: str = "source link is not allowed"):
        self.code = "INVALID_LINK"
        super().__init__(message)


class SourceHttpError(RuntimeError):
    def __init__(self, status_code: int = 502):
        self.status_code = int(status_code)
        super().__init__("source request failed")


class SourceHttpGateway(Protocol):
    def fetch_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
        json_body: Mapping[str, object] | None = None,
    ) -> object:
        raise NotImplementedError


class HttpxSourceGateway:
    """Read-only HTTP gateway with redirects disabled at the source boundary."""

    def __init__(self, *, timeout_seconds: int = 15):
        self._timeout_seconds = max(1, int(timeout_seconds))

    def fetch_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
        json_body: Mapping[str, object] | None = None,
    ) -> object:
        try:
            import httpx
        except ImportError as error:
            raise SourceHttpError(503) from error
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
                headers={"User-Agent": "chickenbro-web-prototype/1", **dict(headers or {})},
            ) as client:
                response = client.request(method, url, json=json_body)
                if 300 <= response.status_code < 400:
                    raise SourceHttpError(502)
                if response.status_code == 404:
                    raise SourceHttpError(404)
                if response.status_code in {401, 403}:
                    raise SourceHttpError(403)
                if response.status_code >= 400:
                    raise SourceHttpError(502)
                response_host = str(getattr(getattr(response, "url", None), "host", "") or "").lower()
                if response_host and response_host not in {
                    "raider.io",
                    "www.raider.io",
                    "warcraftlogs.com",
                    "www.warcraftlogs.com",
                }:
                    raise SourceHttpError(502)
                return response.json()
        except SourceHttpError:
            raise
        except Exception as error:
            raise SourceHttpError(502) from error


@dataclass(frozen=True)
class ParsedSourceUrl:
    provider: SourceProvider
    url: str
    region: str = ""
    realm: str = ""
    character_name: str = ""
    report_code: str = ""
    fight_id: int | None = None
    actor_id: int | None = None

    @property
    def source_key(self) -> str:
        if self.provider is SourceProvider.RAIDERIO:
            return "|".join((self.region, self.realm, self.character_name))
        return "|".join((self.report_code, str(self.fight_id or ""), str(self.actor_id or "")))


def parse_character_source_url(source_url: str) -> ParsedSourceUrl:
    if not isinstance(source_url, str) or len(source_url) > 2048:
        raise InvalidSourceLink()
    parsed = urlparse(source_url.strip())
    if parsed.scheme.lower() != "https" or parsed.username or parsed.password:
        raise InvalidSourceLink()
    if parsed.port not in {None, 443}:
        raise InvalidSourceLink()
    host = (parsed.hostname or "").lower()
    path = [unquote(part) for part in parsed.path.split("/") if part]
    if host in {"raider.io", "www.raider.io"}:
        if (
            len(path) == 5
            and path[1].lower() == "characters"
            and re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", path[0], re.IGNORECASE)
        ):
            path = path[1:]
        if len(path) != 4 or path[0].lower() != "characters" or parsed.query or parsed.fragment:
            raise InvalidSourceLink()
        region, realm, character_name = (part.strip() for part in path[1:])
        if not region or not realm or not character_name or any("\x00" in part for part in (region, realm, character_name)):
            raise InvalidSourceLink()
        canonical = f"https://raider.io/characters/{quote(region, safe='-_.~')}/{quote(realm, safe='-_.~')}/{quote(character_name, safe='-_.~')}"
        return ParsedSourceUrl(
            provider=SourceProvider.RAIDERIO,
            url=canonical,
            region=region.lower(),
            realm=realm.lower(),
            character_name=character_name,
        )
    if host in {"warcraftlogs.com", "www.warcraftlogs.com"}:
        if len(path) < 2 or path[0].lower() != "reports" or len(path) > 3:
            raise InvalidSourceLink()
        report_code = path[1].strip()
        if not re.fullmatch(r"[A-Za-z0-9]{4,128}", report_code):
            raise InvalidSourceLink()
        values = parse_qs(parsed.query, keep_blank_values=False)
        fragment_values = parse_qs(parsed.fragment, keep_blank_values=False)
        for key, value in fragment_values.items():
            if key not in values:
                values[key] = value
        if any(key not in {"fight", "source"} for key in values):
            raise InvalidSourceLink()

        def integer_query(name: str) -> int | None:
            raw = values.get(name, [])
            if not raw:
                return None
            if len(raw) != 1 or not re.fullmatch(r"[1-9][0-9]{0,8}", raw[0]):
                raise InvalidSourceLink()
            return int(raw[0])

        fight_id = integer_query("fight")
        actor_id = integer_query("source")
        canonical = f"https://www.warcraftlogs.com/reports/{quote(report_code, safe='')}"
        suffix = []
        if fight_id is not None:
            suffix.append(f"fight={fight_id}")
        if actor_id is not None:
            suffix.append(f"source={actor_id}")
        if suffix:
            canonical += "#" + "&".join(suffix)
        return ParsedSourceUrl(
            provider=SourceProvider.WARCRAFTLOGS,
            url=canonical,
            report_code=report_code,
            fight_id=fight_id,
            actor_id=actor_id,
        )
    raise InvalidSourceLink()


def _fetch_json(
    client: object,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    method: str = "GET",
    json_body: Mapping[str, object] | None = None,
) -> object:
    if hasattr(client, "fetch_json"):
        fetch = getattr(client, "fetch_json")
        try:
            return fetch(url, headers=headers, method=method, json_body=json_body)
        except TypeError:
            return fetch(url, headers=headers)
    if callable(client):
        return client(url)
    raise SourceHttpError(503)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object) -> str:
    return str(value or "").strip()


def _key(value: object) -> str:
    if isinstance(value, Mapping):
        return ""
    text = _text(value).lower().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "", text)


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _character_fields(**values: object) -> dict[str, object]:
    result: dict[str, object] = {}
    for field, value in values.items():
        if field == "level":
            level = _positive_int(value)
            if level is not None:
                result[field] = level
            continue
        text = _text(value)
        if text:
            result[field] = text
    return result


def _gear_state(raw_gear: object, normalized_gear: Mapping[str, object]) -> dict[str, object]:
    raw_items = raw_gear.get("items") if isinstance(raw_gear, Mapping) else raw_gear
    if (
        isinstance(raw_items, (Mapping, list))
        and "main_hand" in normalized_gear
        and "off_hand" not in normalized_gear
    ):
        return {"unequippedSlots": ["off_hand"]}
    return {"unequippedSlots": []}


def _source_error_code(error: object) -> SourceReadiness:
    status = int(getattr(error, "status_code", 502) or 502)
    if status == 404:
        return SourceReadiness.CHARACTER_NOT_FOUND
    if status in {401, 403}:
        return SourceReadiness.ACCESS_RESTRICTED
    return SourceReadiness.SNAPSHOT_UNAVAILABLE


def _failure_candidate(parsed: ParsedSourceUrl, readiness: SourceReadiness, *, fetched_at: datetime) -> CharacterSnapshotCandidate:
    return CharacterSnapshotCandidate(
        provider=parsed.provider,
        source_url=parsed.url,
        source_key=parsed.source_key,
        snapshot={},
        provenance={
            "provider": parsed.provider.value,
            "sourceUrl": parsed.url,
            "fetchedAt": fetched_at.isoformat(),
        },
        raw_sha256=sha256_json({}),
        fetched_at=fetched_at,
        readiness=readiness,
    )


def _normalize_item(item: object, slot: str) -> dict[str, object] | None:
    if not isinstance(item, Mapping):
        return None
    item_id = _positive_int(item.get("itemId") or item.get("item_id") or item.get("id"))
    if item_id is None:
        return None
    result: dict[str, object] = {"itemId": item_id}
    for target, names in {
        "name": ("name", "itemName"),
        "itemLevel": ("itemLevel", "item_level", "ilevel"),
        "bonusIds": ("bonusIds", "bonuses", "bonus_id", "bonus_ids"),
        "gems": ("gems", "gemIds", "gem_ids"),
        "enchant": ("enchant", "enchantId", "enchant_id"),
    }.items():
        for name in names:
            if name in item:
                value = item[name]
                if target in {"bonusIds", "gems"} and isinstance(value, tuple):
                    value = list(value)
                result[target] = value
                break
        if target == "enchant" and target not in result and "enchants" in item:
            raw_enchants = item.get("enchants")
            if isinstance(raw_enchants, (list, tuple)):
                result[target] = next(
                    (enchant for enchant in (_positive_int(value) for value in raw_enchants) if enchant is not None),
                    None,
                )
            else:
                result[target] = _positive_int(raw_enchants)
    return result


def _normalize_slot(raw_slot: object) -> str:
    slot = _key(raw_slot)
    return {
        "shoulders": "shoulder",
        "finger_1": "finger1",
        "finger_2": "finger2",
        "ring1": "finger1",
        "ring2": "finger2",
        "trinket_1": "trinket1",
        "trinket_2": "trinket2",
        "mainhand": "main_hand",
        "offhand": "off_hand",
    }.get(slot, slot)


def _normalize_gear(raw_gear: object) -> dict[str, object]:
    items = raw_gear.get("items") if isinstance(raw_gear, Mapping) else raw_gear
    result: dict[str, object] = {}
    if isinstance(items, Mapping):
        for raw_slot, item in items.items():
            normalized_slot = _normalize_slot(raw_slot)
            normalized = _normalize_item(item, normalized_slot)
            if normalized is not None:
                result[normalized_slot] = normalized
    elif isinstance(items, list):
        for item in items:
            if not isinstance(item, Mapping):
                continue
            slot = _normalize_slot(item.get("slot") or item.get("slotName"))
            normalized = _normalize_item(item, slot)
            if slot and normalized is not None:
                result[slot] = normalized
    return result


def _normalize_talents(raw: object) -> dict[str, object]:
    if isinstance(raw, list):
        return {"loadout": raw}
    if isinstance(raw, Mapping):
        result: dict[str, object] = {}
        if isinstance(raw.get("loadout"), list):
            result["loadout"] = raw["loadout"]
        talent_string = raw.get("string") or raw.get("loadoutString") or raw.get("loadout_text")
        if _text(talent_string):
            result["string"] = _text(talent_string)
        return result
    if _text(raw):
        return {"string": _text(raw)}
    return {}


class RaiderIOCharacterAdapter:
    def __init__(self, http_client: object):
        self._http_client = http_client

    def resolve(self, parsed_url: ParsedSourceUrl) -> CharacterSnapshotCandidate:
        fetched_at = _now()
        endpoint = "https://raider.io/api/v1/characters/profile?" + urlencode({
            "region": parsed_url.region,
            "realm": parsed_url.realm,
            "name": parsed_url.character_name,
            "fields": "gear,talents",
            **(
                {"access_key": os.environ.get("WOW_RAIDERIO_API_KEY", "").strip()}
                if os.environ.get("WOW_RAIDERIO_API_KEY", "").strip()
                else {}
            ),
        })
        try:
            raw = _fetch_json(self._http_client, endpoint)
        except Exception as error:
            return _failure_candidate(parsed_url, _source_error_code(error), fetched_at=fetched_at)
        if not isinstance(raw, Mapping) or raw.get("error") or not _text(raw.get("name")):
            return _failure_candidate(parsed_url, SourceReadiness.CHARACTER_NOT_FOUND, fetched_at=fetched_at)

        raw_class = raw.get("class") if isinstance(raw.get("class"), Mapping) else {}
        raw_race = raw.get("race") if isinstance(raw.get("race"), Mapping) else {}
        character = _character_fields(
            name=raw.get("name"),
            realm=raw.get("realm"),
            region=_key(raw.get("region")),
            classKey=_key(
                raw.get("classSlug")
                or raw_class.get("slug")
                or raw_class.get("name")
                or raw.get("class")
            ),
            specKey=_key(raw.get("activeSpecSlug") or raw.get("active_spec_name") or raw.get("spec")),
            raceKey=_key(
                raw.get("raceSlug")
                or raw_race.get("slug")
                or raw_race.get("name")
                or raw.get("race")
            ),
            level=raw.get("level"),
        )
        normalized_gear = _normalize_gear(raw.get("gear"))
        snapshot = {
            "character": character,
            "gear": normalized_gear,
            "gearState": _gear_state(raw.get("gear"), normalized_gear),
            "talents": _normalize_talents(raw.get("talents") or raw.get("talentLoadout")),
            "profileSource": "raiderio",
        }
        source_revision = _text(
            raw.get("profileRevision")
            or raw.get("profile_revision")
            or raw.get("lastUpdated")
            or raw.get("last_updated")
        )
        provenance = {
            "provider": SourceProvider.RAIDERIO.value,
            "sourceUrl": parsed_url.url,
            "fetchedAt": fetched_at.isoformat(),
            "endpoint": "raiderio-character-profile",
        }
        if source_revision:
            provenance["sourceRevision"] = source_revision
        return CharacterSnapshotCandidate(
            provider=SourceProvider.RAIDERIO,
            source_url=parsed_url.url,
            source_key=parsed_url.source_key,
            snapshot=snapshot,
            provenance=provenance,
            raw_sha256=sha256_json(raw),
            fetched_at=fetched_at,
            missing_fields=missing_snapshot_fields(snapshot),
        )


WCL_CHARACTER_QUERY = """
query ChickenbroCharacterSnapshot($code: String!, $fightIds: [Int]) {
  reportData {
    report(code: $code) {
      code
      revision
      fights { id name }
      playerDetails(fightIDs: $fightIds)
    }
  }
}
"""


class WclCharacterAdapter:
    def __init__(
        self,
        http_client: object,
        *,
        access_token: str | None = None,
        endpoint: str | None = None,
        token_provider: Callable[[], str] | None = None,
    ):
        self._http_client = http_client
        self._access_token = _text(access_token or os.environ.get("WOW_WARCRAFTLOGS_API_TOKEN"))
        self._endpoint = _text(endpoint or os.environ.get("WOW_WARCRAFTLOGS_GRAPHQL_URL")) or "https://www.warcraftlogs.com/api/v2/client"
        self._token_provider = token_provider

    def resolve(self, parsed_url: ParsedSourceUrl) -> CharacterSnapshotCandidate:
        fetched_at = _now()
        token = self._access_token
        if not token and self._token_provider is not None:
            try:
                token = _text(self._token_provider())
            except Exception:
                token = ""
        if not token:
            return _failure_candidate(parsed_url, SourceReadiness.ACCESS_RESTRICTED, fetched_at=fetched_at)
        try:
            raw = _fetch_json(
                self._http_client,
                self._endpoint,
                headers={"Authorization": f"Bearer {token}"},
                method="POST",
                json_body={
                    "query": WCL_CHARACTER_QUERY,
                    "variables": {
                        "code": parsed_url.report_code,
                        "fightIds": [parsed_url.fight_id] if parsed_url.fight_id else None,
                    },
                },
            )
        except Exception as error:
            return _failure_candidate(parsed_url, _source_error_code(error), fetched_at=fetched_at)
        report = self._report_from_response(raw)
        if not isinstance(report, Mapping):
            return _failure_candidate(parsed_url, SourceReadiness.CHARACTER_NOT_FOUND, fetched_at=fetched_at)
        player = self._player_from_report(report, parsed_url.actor_id)
        if not isinstance(player, Mapping):
            return _failure_candidate(parsed_url, SourceReadiness.CHARACTER_NOT_FOUND, fetched_at=fetched_at)

        spec_entries = player.get("specs") if isinstance(player.get("specs"), list) else []
        first_spec = spec_entries[0] if spec_entries and isinstance(spec_entries[0], Mapping) else {}
        character = _character_fields(
            name=player.get("name"),
            realm=player.get("realm") or player.get("server"),
            region=_key(player.get("region")),
            classKey=_key(player.get("classKey") or player.get("class") or player.get("type")),
            specKey=_key(player.get("specKey") or player.get("spec") or first_spec.get("spec")),
            raceKey=_key(player.get("raceKey") or player.get("race")),
            level=player.get("level"),
        )
        fight_id = parsed_url.fight_id
        if fight_id is None:
            fights = report.get("fights") if isinstance(report.get("fights"), list) else []
            first_fight = fights[0] if fights and isinstance(fights[0], Mapping) else {}
            fight_id = _positive_int(first_fight.get("id"))
        actor_id = parsed_url.actor_id or _positive_int(player.get("id") or player.get("actorId"))
        guid = _positive_int(player.get("guid") or player.get("gameGuid"))
        normalized_gear = _normalize_gear(player.get("gear"))
        snapshot = {
            "character": character,
            "gear": normalized_gear,
            "gearState": _gear_state(player.get("gear"), normalized_gear),
            "talents": _normalize_talents(player.get("talents") or player.get("talentLoadout")),
            "combat": {
                "reportCode": parsed_url.report_code,
                "fightId": fight_id,
                "actorId": actor_id,
                "guid": guid,
            },
            "profileSource": "warcraftlogs",
        }
        source_revision = _text(report.get("revision"))
        provenance = {
            "provider": SourceProvider.WARCRAFTLOGS.value,
            "sourceUrl": parsed_url.url,
            "reportCode": parsed_url.report_code,
            "fightId": fight_id,
            "actorId": actor_id,
            "guid": guid,
            "fetchedAt": fetched_at.isoformat(),
            "endpoint": "warcraftlogs-report-player-details",
        }
        if source_revision:
            provenance["sourceRevision"] = source_revision
        return CharacterSnapshotCandidate(
            provider=SourceProvider.WARCRAFTLOGS,
            source_url=parsed_url.url,
            source_key=parsed_url.source_key,
            snapshot=snapshot,
            provenance=provenance,
            raw_sha256=sha256_json(raw),
            fetched_at=fetched_at,
            missing_fields=missing_snapshot_fields(snapshot),
        )

    @staticmethod
    def _report_from_response(raw: object) -> Mapping[str, object] | None:
        if not isinstance(raw, Mapping):
            return None
        data = raw.get("data") if isinstance(raw.get("data"), Mapping) else raw
        report_data = data.get("reportData") if isinstance(data, Mapping) else None
        if not isinstance(report_data, Mapping):
            report_data = data
        report = report_data.get("report") if isinstance(report_data, Mapping) else None
        return report if isinstance(report, Mapping) else None

    @staticmethod
    def _player_from_report(report: Mapping[str, object], actor_id: int | None) -> Mapping[str, object] | None:
        details: object = report.get("playerDetails")
        if isinstance(details, Mapping) and isinstance(details.get("data"), Mapping):
            details = details["data"]
        if isinstance(details, Mapping):
            details = details.get("playerDetails") or details.get("players") or details.get("data")
        players = details if isinstance(details, list) else report.get("players")
        if not isinstance(players, list):
            return None
        normalized_actor = actor_id
        if normalized_actor is not None:
            for player in players:
                if isinstance(player, Mapping) and _positive_int(player.get("id") or player.get("actorId")) == normalized_actor:
                    return player
            return None
        mapped = [player for player in players if isinstance(player, Mapping)]
        return mapped[0] if len(mapped) == 1 else None


class CharacterSourceRouter:
    def __init__(
        self,
        http_client: object,
        *,
        raiderio_adapter: RaiderIOCharacterAdapter | None = None,
        wcl_adapter: WclCharacterAdapter | None = None,
    ):
        self._http_client = http_client
        self._raiderio = raiderio_adapter or RaiderIOCharacterAdapter(http_client)
        self._wcl = wcl_adapter or WclCharacterAdapter(http_client)

    def resolve(self, source_url: str, http_client: object | None = None) -> CharacterSnapshotCandidate:
        parsed = parse_character_source_url(source_url)
        if parsed.provider is SourceProvider.RAIDERIO:
            adapter = self._raiderio if http_client is None else RaiderIOCharacterAdapter(http_client)
        else:
            adapter = self._wcl if http_client is None else WclCharacterAdapter(http_client)
        return adapter.resolve(parsed)


__all__ = (
    "CharacterSourceRouter",
    "HttpxSourceGateway",
    "InvalidSourceLink",
    "ParsedSourceUrl",
    "RaiderIOCharacterAdapter",
    "SourceHttpError",
    "WclCharacterAdapter",
    "parse_character_source_url",
)
