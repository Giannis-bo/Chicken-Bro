import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

from server.app.integrations.blizzard import BlizzardProfileEnricher
from server.app.integrations.warcraftlogs import (
    WarcraftLogsAccessError,
    warcraftlogs_oauth_token,
)
from server.app.simulation.domain import SourceProvider, SourceReadiness
from server.app.simulation.source_details import (
    combatant_input, matching_talent_export, read_character_details,
)
from server.app.simulation.wcl_talents import reconstruct_fight_talents
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
                headers={"User-Agent": "chickenbro-simc/1", **dict(headers or {})},
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
                } and not (
                    response_host.endswith(".api.blizzard.com")
                    or response_host == "gateway.battlenet.com.cn"
                ):
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
    if host in {"warcraftlogs.com", "www.warcraftlogs.com", "cn.warcraftlogs.com"}:
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


def _source_revision(raw: Mapping[str, object]) -> str:
    return _text(
        raw.get("profileRevision")
        or raw.get("profile_revision")
        or raw.get("lastUpdated")
        or raw.get("last_updated")
        or raw.get("lastCrawledAt")
        or raw.get("last_crawled_at")
    )


def _enrich_character(
    parsed_url: ParsedSourceUrl,
    character: Mapping[str, object],
    provenance: dict[str, object],
    raw: Mapping[str, object],
    official_enricher: object | None,
) -> tuple[dict[str, object], str, str]:
    """Fill only missing identity fields from an exact official profile."""

    source_revision = _source_revision(raw)
    merged = dict(character)
    raw_sha256 = sha256_json(raw)
    if official_enricher is None or all(
        _positive_int(merged.get("level")) if field == "level" else _text(merged.get(field))
        for field in ("level", "classKey", "specKey", "raceKey")
    ):
        return merged, raw_sha256, source_revision
    try:
        enrichment = official_enricher.enrich(parsed_url, merged)
    except Exception:
        return merged, raw_sha256, source_revision
    if enrichment is None:
        return merged, raw_sha256, source_revision
    official_character = getattr(enrichment, "character", {})
    if not isinstance(official_character, Mapping):
        return merged, raw_sha256, source_revision
    for field, value in official_character.items():
        existing = merged.get(field)
        if field == "level":
            if not _positive_int(existing):
                level = _positive_int(value)
                if level is not None:
                    merged[field] = level
        elif not _text(existing) and _text(value):
            merged[field] = _text(value)
    official_raw_sha = _text(getattr(enrichment, "raw_sha256", ""))
    official_endpoint = _text(getattr(enrichment, "endpoint", ""))
    official_raw = getattr(enrichment, "raw", {})
    if official_raw_sha and official_endpoint and isinstance(official_raw, Mapping):
        provenance["officialProfile"] = {
            "provider": "blizzard",
            "endpoint": official_endpoint,
            "rawSha256": official_raw_sha,
        }
        if not source_revision:
            source_revision = _text(getattr(enrichment, "source_revision", ""))
        return merged, sha256_json({"primary": raw, "officialProfile": official_raw}), source_revision
    return merged, raw_sha256, source_revision


def _raiderio_ranking_level(
    client: object,
    parsed: ParsedSourceUrl,
    character: Mapping[str, object],
) -> tuple[int, dict[str, object], dict[str, object]] | None:
    """Read an explicit level from one current ranking page, never infer it.

    This deliberately bounded fallback cannot cover unranked characters. The
    primary profile, requested identity, and ranked identity must all agree.
    """
    def realm_key(value: object) -> str:
        return _text(value).casefold().replace("'", "").replace(" ", "-")

    if (
        parsed.region not in {"us", "eu", "kr", "tw"}
        or _text(character.get("region")).casefold() != parsed.region
        or realm_key(character.get("realm")) != realm_key(parsed.realm)
        or _text(character.get("name")).casefold() != parsed.character_name.casefold()
        or not character.get("classKey")
        or not character.get("specKey")
    ):
        return None
    affixes_endpoint = "https://raider.io/api/v1/mythic-plus/affixes?" + urlencode({
        "region": parsed.region, "locale": "en",
    })
    try:
        affixes = _fetch_json(client, affixes_endpoint)
        if not isinstance(affixes, Mapping) or affixes.get("region") != parsed.region:
            return None
        leaderboard = urlparse(_text(affixes.get("leaderboard_url")))
        match = re.fullmatch(
            r"/mythic-plus-affix-rankings/(season-[a-z0-9-]+)/all/([a-z]{2})/[^?#]+",
            leaderboard.path,
        )
        if (
            leaderboard.scheme != "https" or leaderboard.netloc != "raider.io"
            or leaderboard.query or leaderboard.fragment or not match
            or match.group(2) != parsed.region
        ):
            return None
        season = match.group(1)
        rankings_endpoint = "https://raider.io/api/mythic-plus/rankings/specs?" + urlencode({
            "region": "world", "season": season,
            "class": _text(character["classKey"]).replace("_", "-"),
            "spec": _text(character["specKey"]).replace("_", "-"), "page": 0,
        })
        raw_rankings = _fetch_json(client, rankings_endpoint)
    except Exception:
        return None
    rankings = raw_rankings.get("rankings") if isinstance(raw_rankings, Mapping) else None
    rows = rankings.get("rankedCharacters") if isinstance(rankings, Mapping) else None
    if not isinstance(rows, list) or len(rows) > 100:
        return None
    matches = []
    for row in rows:
        ranked = row.get("character") if isinstance(row, Mapping) else None
        if not isinstance(ranked, Mapping):
            continue
        def slug(field: str) -> str:
            nested = ranked.get(field)
            return _text(nested.get("slug")) if isinstance(nested, Mapping) else ""

        if (
            _text(ranked.get("name")).casefold() == parsed.character_name.casefold()
            and slug("region") == parsed.region
            and slug("realm").casefold() == parsed.realm.casefold()
        ):
            matches.append(ranked)
    if len(matches) != 1:
        return None
    ranked = matches[0]
    for source_field, ranking_field in (("classKey", "class"), ("specKey", "spec"), ("raceKey", "race")):
        nested = ranked.get(ranking_field)
        if character.get(source_field) and (
            not isinstance(nested, Mapping) or _key(nested.get("slug")) != character[source_field]
        ):
            return None
    expected_path = f"/characters/{parsed.region}/{parsed.realm}/{parsed.character_name}"
    if unquote(_text(ranked.get("path"))).casefold() != expected_path.casefold():
        return None
    level = ranked.get("level")
    if type(level) is not int or level <= 0:
        return None
    raw_metadata = {"affixes": affixes, "rankings": raw_rankings}
    provenance = {
        "provider": "raiderio", "season": season, "characterPath": ranked["path"],
        "affixesEndpoint": affixes_endpoint, "affixesRawSha256": sha256_json(affixes),
        "rankingsEndpoint": rankings_endpoint, "rankingsRawSha256": sha256_json(raw_rankings),
    }
    return level, provenance, raw_metadata


class RaiderIOCharacterAdapter:
    def __init__(
        self,
        http_client: object,
        *,
        official_enricher: object | None = None,
    ):
        self._http_client = http_client
        self._official_enricher = official_enricher or BlizzardProfileEnricher(http_client)

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
        provenance = {
            "provider": SourceProvider.RAIDERIO.value,
            "sourceUrl": parsed_url.url,
            "fetchedAt": fetched_at.isoformat(),
            "endpoint": "raiderio-character-profile",
        }
        character, raw_sha256, source_revision = _enrich_character(
            parsed_url,
            character,
            provenance,
            raw,
            self._official_enricher,
        )
        if not _positive_int(character.get("level")):
            details = read_character_details(
                lambda url: _fetch_json(self._http_client, url),
                parsed_url.region, parsed_url.realm, parsed_url.character_name, character,
            )
            if details is not None:
                detail_character, metadata = details
                character["level"] = detail_character["level"]
                provenance["raiderioCharacterDetails"] = {**metadata, "fields": ["level"]}
                raw_sha256 = sha256_json({"primarySha256": raw_sha256, "details": metadata})
        if not _positive_int(character.get("level")):
            ranking_level = _raiderio_ranking_level(self._http_client, parsed_url, character)
            if ranking_level is not None:
                level, metadata_provenance, raw_metadata = ranking_level
                character["level"] = level
                provenance["raiderioLevelMetadata"] = metadata_provenance
                raw_sha256 = sha256_json({
                    "primarySha256": raw_sha256, "raiderioLevelMetadata": raw_metadata,
                })
        snapshot["character"] = character
        if source_revision:
            provenance["sourceRevision"] = source_revision
        return CharacterSnapshotCandidate(
            provider=SourceProvider.RAIDERIO,
            source_url=parsed_url.url,
            source_key=parsed_url.source_key,
            snapshot=snapshot,
            provenance=provenance,
            raw_sha256=raw_sha256,
            fetched_at=fetched_at,
            missing_fields=missing_snapshot_fields(snapshot),
        )


WCL_CHARACTER_QUERY = """
query ChickenbroCharacterSnapshot($code: String!, $fightIds: [Int], $sourceId: Int) {
  reportData {
    report(code: $code) {
      code
      revision
      fights { id name }
      playerDetails(fightIDs: $fightIds, includeCombatantInfo: true)
      events(fightIDs: $fightIds, sourceID: $sourceId, dataType: CombatantInfo, limit: 2) {
        data
        nextPageTimestamp
      }
    }
  }
}
"""

WCL_IDENTITY_QUERY = """
query ChickenbroCharacterIdentity($name: String!, $realm: String!, $region: String!) {
  characterData { character(name: $name, serverSlug: $realm, serverRegion: $region) {
    name level server { name slug region { slug } }
  } }
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
        official_enricher: object | None = None,
    ):
        self._http_client = http_client
        self._access_token = _text(access_token or os.environ.get("WOW_WARCRAFTLOGS_API_TOKEN"))
        self._endpoint = _text(endpoint or os.environ.get("WOW_WARCRAFTLOGS_GRAPHQL_URL")) or "https://www.warcraftlogs.com/api/v2/client"
        self._token_provider = token_provider
        self._official_enricher = official_enricher or BlizzardProfileEnricher(http_client)

    def resolve(self, parsed_url: ParsedSourceUrl) -> CharacterSnapshotCandidate:
        fetched_at = _now()
        token = self._access_token
        if not token and self._token_provider is not None:
            try:
                token = _text(self._token_provider())
            except WarcraftLogsAccessError:
                return _failure_candidate(
                    parsed_url,
                    SourceReadiness.ACCESS_RESTRICTED,
                    fetched_at=fetched_at,
                )
            except Exception:
                return _failure_candidate(
                    parsed_url,
                    SourceReadiness.SNAPSHOT_UNAVAILABLE,
                    fetched_at=fetched_at,
                )
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
                        "sourceId": parsed_url.actor_id,
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
        character, raw_sha256, enriched_source_revision = _enrich_character(
            parsed_url,
            character,
            provenance,
            raw,
            self._official_enricher,
        )
        snapshot["character"] = character
        combat = combatant_input(report, fight_id, actor_id)
        if combat is not None:
            fight_input, event = combat
            snapshot.update(fight_input)
            # A WCL entry/rank list is not a SimC talent export hash.
            snapshot["talents"] = {}
            provenance["wclCombatantInfo"] = {
                "fightId": fight_id, "actorId": actor_id,
                "eventSha256": sha256_json(event), "fields": ["gear", "talents"],
            }
            try:
                identity_raw = _fetch_json(
                    self._http_client, self._endpoint,
                    headers={"Authorization": f"Bearer {token}"}, method="POST",
                    json_body={"query": WCL_IDENTITY_QUERY, "variables": {
                        "name": character.get("name"), "realm": character.get("realm"),
                        "region": character.get("region"),
                    }},
                )
                identity = identity_raw["data"]["characterData"]["character"]
                server = identity["server"]
                if (_text(identity["name"]).casefold() != _text(character.get("name")).casefold()
                        or _text(server["name"]).casefold() != _text(character.get("realm")).casefold()
                        or _text(server["region"]["slug"]).casefold() != _text(character.get("region")).casefold()):
                    raise ValueError("character identity mismatch")
                details = read_character_details(
                    lambda url: _fetch_json(self._http_client, url),
                    character["region"], server["slug"], character["name"], character,
                )
                if details is not None:
                    detail_character, metadata = details
                    if type(identity.get("level")) is not int or identity["level"] != detail_character["level"]:
                        raise ValueError("character level mismatch")
                    if not character.get("level"):
                        character["level"] = detail_character["level"]
                    if not character.get("raceKey"):
                        character["raceKey"] = _key(detail_character["race"]["slug"])
                    character["realm"] = server["slug"]
                    code = matching_talent_export(event.get("talentTree"), detail_character, character["specKey"])
                    reconstructed = reconstruct_fight_talents(
                        event.get("talentTree"), event.get("specID"), detail_character, character["specKey"])
                    if reconstructed is not None:
                        reconstructed_code, reconstruction = reconstructed
                        snapshot["talents"] = {"string": reconstructed_code}
                        provenance["wclTalentReconstruction"] = reconstruction
                    elif code and (event.get("specID") is None or (
                        type(event["specID"]) is int and event["specID"] == detail_character["spec"].get("id")
                    )):
                        snapshot["talents"] = {"string": code}
                    provenance["raiderioCharacterDetails"] = {
                        **metadata, "fields": ["level", "raceKey", "realm"],
                        "talentsVerifiedAgainstFight": bool(code),
                    }
                    provenance["wclCharacterIdentity"] = {"rawSha256": sha256_json(identity_raw)}
                    raw_sha256 = sha256_json({"primarySha256": raw_sha256,
                                             "identity": identity_raw, "details": metadata})
            except (KeyError, TypeError, ValueError, SourceHttpError):
                pass
        if not source_revision:
            source_revision = enriched_source_revision
        if source_revision:
            provenance["sourceRevision"] = source_revision
        return CharacterSnapshotCandidate(
            provider=SourceProvider.WARCRAFTLOGS,
            source_url=parsed_url.url,
            source_key=parsed_url.source_key,
            snapshot=snapshot,
            provenance=provenance,
            raw_sha256=raw_sha256,
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
        if isinstance(details, Mapping):
            grouped: list[object] = []
            for group in ("dps", "healers", "tanks"):
                value = details.get(group)
                if isinstance(value, list):
                    grouped.extend(value)
            details = grouped if grouped else details
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
        official_enricher: object | None = None,
    ):
        self._http_client = http_client
        self._official_enricher = official_enricher or BlizzardProfileEnricher(http_client)
        self._raiderio = raiderio_adapter or RaiderIOCharacterAdapter(
            http_client,
            official_enricher=self._official_enricher,
        )
        self._wcl = wcl_adapter or WclCharacterAdapter(
            http_client,
            token_provider=warcraftlogs_oauth_token,
            official_enricher=self._official_enricher,
        )

    def resolve(self, source_url: str, http_client: object | None = None) -> CharacterSnapshotCandidate:
        parsed = parse_character_source_url(source_url)
        if parsed.provider is SourceProvider.RAIDERIO:
            adapter = self._raiderio if http_client is None else RaiderIOCharacterAdapter(http_client)
        else:
            adapter = self._wcl if http_client is None else WclCharacterAdapter(
                http_client,
                token_provider=warcraftlogs_oauth_token,
            )
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
