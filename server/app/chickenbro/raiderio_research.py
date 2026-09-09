"""Bounded, read-only Raider.IO evidence for Chickenbro research."""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode, urlparse

from server.app.simulation.domain import SourceProvider
from server.app.simulation.sources import (
    HttpxSourceGateway,
    InvalidSourceLink,
    _fetch_json,
    parse_character_source_url,
)


_SOURCE_KEY = "raiderio"
_PROFILE_API = "https://raider.io/api/v1/characters/profile"
_AFFIX_API = "https://raider.io/api/v1/mythic-plus/affixes"
_RANKINGS_API = "https://raider.io/api/mythic-plus/rankings/specs"
_RANKING_KEYS = {"className", "spec", "region", "season", "page", "offset", "limit"}
_SPECS_BY_CLASS = {
    "death-knight": {"blood", "frost", "unholy"},
    "demon-hunter": {"havoc", "vengeance", "devourer"},
    "druid": {"balance", "feral", "guardian", "restoration"},
    "evoker": {"augmentation", "devastation", "preservation"},
    "hunter": {"beast-mastery", "marksmanship", "survival"},
    "mage": {"arcane", "fire", "frost"},
    "monk": {"brewmaster", "mistweaver", "windwalker"},
    "paladin": {"holy", "protection", "retribution"},
    "priest": {"discipline", "holy", "shadow"},
    "rogue": {"assassination", "outlaw", "subtlety"},
    "shaman": {"elemental", "enhancement", "restoration"},
    "warlock": {"affliction", "demonology", "destruction"},
    "warrior": {"arms", "fury", "protection"},
}
_REGIONS = {"world", "us", "eu", "kr", "tw", "cn"}
_SEASON_RE = re.compile(r"season-[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _strict_int(value: object, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InvalidSourceLink("invalid Raider.IO research options")
    return value


def _slug(value: object) -> str:
    return _text(value, 80).lower().replace(" ", "-")


def _identity(value: object) -> str:
    return re.sub(r"[-_ ]+", "-", _text(value, 160).casefold())


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _source_error_status(error: Exception) -> str:
    return "not_found" if int(getattr(error, "status_code", 502) or 502) == 404 else "blocked"


def _packet(
    *,
    status: str,
    facts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    limitations: list[str] | None = None,
    next_actions: list[str] | None = None,
    **extra: object,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sourceKey": _SOURCE_KEY,
        "status": status,
        "facts": facts,
        "evidence": evidence,
        "evidenceRefs": [item["id"] for item in evidence if item.get("sourceStatus") == "fetched"],
        "limitations": (limitations or [])[:10],
        "nextActions": (next_actions or [])[:5],
    }
    result.update(extra)
    return result


def _safe_named_detail(
    value: object, *, id_names: tuple[str, ...], limit: int = 8
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value[:limit]:
        item = _mapping(raw)
        safe: dict[str, Any] = {}
        for name in id_names:
            parsed = _positive_int(item.get(name))
            if parsed is not None:
                safe["id"] = parsed
                break
        name = _text(item.get("name"), 160)
        if name:
            safe["name"] = name
        if safe:
            result.append(safe)
    return result


def _safe_gear(value: object) -> dict[str, Any]:
    gear = _mapping(value)
    result: dict[str, Any] = {}
    equipped = _number(gear.get("item_level_equipped"))
    if equipped is not None:
        result["itemLevelEquipped"] = equipped
    raw_items = _mapping(gear.get("items"))
    items: dict[str, dict[str, Any]] = {}
    for raw_slot, raw_item in list(raw_items.items())[:24]:
        slot = re.sub(r"[^a-z0-9_]+", "", _text(raw_slot, 40).lower())
        item = _mapping(raw_item)
        item_id = _positive_int(item.get("id") or item.get("item_id") or item.get("itemId"))
        if not slot or item_id is None:
            continue
        safe: dict[str, Any] = {"itemId": item_id}
        name = _text(item.get("name"), 160)
        level = _positive_int(item.get("item_level") or item.get("itemLevel"))
        tier = item.get("tier")
        if name:
            safe["name"] = name
        if level is not None:
            safe["itemLevel"] = level
        if isinstance(tier, (str, int, bool)):
            safe["tier"] = tier if isinstance(tier, bool) else _text(tier, 40)
        tier36 = item.get("tier36")
        if isinstance(tier36, (str, int, bool)):
            safe["tier36"] = tier36 if isinstance(tier36, bool) else _text(tier36, 40)
        bonuses = item.get("bonuses") or item.get("bonus_ids") or item.get("bonusIds")
        if isinstance(bonuses, list):
            safe["bonusIds"] = [
                parsed for raw in bonuses[:32] if (parsed := _positive_int(raw)) is not None
            ]
        gems = _safe_named_detail(item.get("gems_detail"), id_names=("item_id", "id"))
        enchants = _safe_named_detail(item.get("enchants_detail"), id_names=("enchant_id", "id"))
        if gems:
            safe["gemsDetail"] = gems
        if enchants:
            safe["enchantsDetail"] = enchants
        items[slot] = safe
    result["items"] = items
    return result


def _selected_talents(value: object) -> dict[str, Any]:
    loadout = _mapping(value)
    raw_selections = loadout.get("loadout")
    if isinstance(raw_selections, list) and any(
        isinstance(item, Mapping) and isinstance(item.get("node"), Mapping)
        for item in raw_selections
    ):
        selected: list[dict[str, Any]] = []
        hero_names: list[str] = []
        for raw_selection in raw_selections[:160]:
            selection = _mapping(raw_selection)
            entries = _mapping(selection.get("node")).get("entries")
            entry_index = _positive_int(selection.get("entryIndex"))
            if (
                not isinstance(entries, list)
                or entry_index is None
                or entry_index >= min(len(entries), 40)
            ):
                continue
            entry = _mapping(entries[entry_index])
            spell = _mapping(entry.get("spell"))
            spell_id = _positive_int(spell.get("id"))
            spell_name = _text(spell.get("name"), 160)
            rank = _positive_int(selection.get("rank"))
            if spell_id is not None and spell_name:
                talent: dict[str, Any] = {"spellId": spell_id, "name": spell_name}
                if rank is not None:
                    talent["rank"] = rank
                selected.append(talent)
            elif entry.get("traitSubTreeId") is not None:
                explicit_name = _text(
                    entry.get("name") or _mapping(selection.get("node")).get("name"), 160
                )
                if explicit_name and explicit_name not in hero_names:
                    hero_names.append(explicit_name)
        result: dict[str, Any] = {
            "selected": selected[:80],
            "heroNames": hero_names[:40],
        }
        spec_id = _positive_int(loadout.get("loadout_spec_id"))
        loadout_text = _text(loadout.get("loadout_text"), 2000)
        if spec_id is not None:
            result["loadoutSpecId"] = spec_id
        if loadout_text:
            result["loadoutText"] = loadout_text
        return result

    selected: list[dict[str, Any]] = []
    hero_names: list[str] = []

    def visit(node: object, path: str = "") -> None:
        if len(selected) + len(hero_names) >= 120:
            return
        if isinstance(node, list):
            for item in node[:160]:
                visit(item, path)
            return
        if not isinstance(node, Mapping):
            return
        implicit_selected = path.rsplit(".", 1)[-1].endswith("talent_points")
        is_selected = node.get("selected") is True or (
            "selected" not in node and implicit_selected
        )
        talent_node = _mapping(node.get("talent"))
        spell = _mapping(node.get("spell") or talent_node.get("spell"))
        if is_selected:
            spell_id = _positive_int(
                spell.get("id") or node.get("spell_id") or node.get("spellId")
            )
            name = _text(
                spell.get("name") or node.get("name") or talent_node.get("name"), 160
            )
            rank = _positive_int(node.get("rank"))
            is_hero = "hero" in path
            if spell_id is not None and name and not is_hero:
                talent: dict[str, Any] = {"spellId": spell_id, "name": name}
                if rank is not None:
                    talent["rank"] = rank
                selected.append(talent)
            if is_hero and name and name not in hero_names:
                hero_names.append(name)
        for key, child in list(node.items())[:160]:
            if isinstance(child, (Mapping, list)):
                visit(child, f"{path}.{str(key).lower()}")

    visit(value)
    return {"selected": selected[:80], "heroNames": hero_names[:40]}


def _safe_scores(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value[:8]:
        row = _mapping(raw)
        season = _text(row.get("season"), 80)
        scores = _mapping(row.get("scores"))
        safe_scores = {
            str(key)[:40]: number
            for key, raw_value in list(scores.items())[:12]
            if (number := _number(raw_value)) is not None
        }
        if season or safe_scores:
            result.append({"season": season, "scores": safe_scores})
    return result


class RaiderIOResearch:
    def __init__(self, http_client: object | None = None, *, realm_resolver=None):
        from server.app.chickenbro.character_discovery import resolve_wcl_realm
        self._realm_resolver = realm_resolver or resolve_wcl_realm
        self._http_client = http_client or HttpxSourceGateway(timeout_seconds=15)

    def rankings(self, options: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(options, Mapping) or any(
            not isinstance(key, str) or key not in _RANKING_KEYS for key in options
        ):
            raise InvalidSourceLink("invalid Raider.IO research options")
        class_name = options.get("className")
        spec = options.get("spec")
        if not isinstance(class_name, str) or class_name not in _SPECS_BY_CLASS:
            raise InvalidSourceLink("invalid Raider.IO class slug")
        if not isinstance(spec, str) or spec not in _SPECS_BY_CLASS[class_name]:
            raise InvalidSourceLink("invalid Raider.IO class/spec pair")
        region = options.get("region", "world")
        if not isinstance(region, str) or region not in _REGIONS:
            raise InvalidSourceLink("invalid Raider.IO ranking region")
        page = _strict_int(options.get("page", 0), minimum=0, maximum=20)
        offset = _strict_int(options.get("offset", 0), minimum=0, maximum=99)
        limit = _strict_int(options.get("limit", 10), minimum=1, maximum=10)
        season = options.get("season", "current")
        if not isinstance(season, str) or (
            season != "current" and not _SEASON_RE.fullmatch(season)
        ):
            raise InvalidSourceLink("invalid Raider.IO season")
        evidence: list[dict[str, Any]] = []
        if season == "current":
            affix_url = _AFFIX_API + "?" + urlencode({"region": "us" if region == "world" else region, "locale": "en"})
            try:
                season_raw = _mapping(_fetch_json(self._http_client, affix_url))
                season = self._season_from_leaderboard(season_raw.get("leaderboard_url"))
            except Exception as error:
                return _packet(
                    status=_source_error_status(error),
                    facts=[],
                    evidence=[],
                    limitations=["Raider.IO current-season discovery failed."],
                    next_actions=["Retry the current-season ranking query."],
                )
            evidence.append(
                {
                    "id": f"raiderio:season:{season}",
                    "sourceName": "Raider.IO",
                    "sourceUrl": affix_url,
                    "sourceStatus": "fetched",
                    "fetchedAt": _now(),
                }
            )
        endpoint = _RANKINGS_API + "?" + urlencode(
            {
                "region": region,
                "season": season,
                "class": class_name,
                "spec": spec,
                "page": page,
            }
        )
        try:
            raw = _mapping(_fetch_json(self._http_client, endpoint))
        except Exception as error:
            return _packet(
                status=_source_error_status(error),
                facts=[],
                evidence=evidence,
                limitations=["Raider.IO ranking data could not be fetched."],
                next_actions=["Retry this ranking page."],
            )
        raw_rows = _mapping(raw.get("rankings")).get("rankedCharacters")
        rows = raw_rows[:100] if isinstance(raw_rows, list) else []
        projected = []
        discarded = 0
        for row in rows[offset : offset + limit]:
            safe = self._ranking_row(row, class_name, spec)
            if safe:
                projected.append(safe)
            else:
                discarded += 1
        next_page: int | None = None
        next_offset: int | None = None
        if offset + limit < len(rows):
            next_page, next_offset = page, offset + limit
        elif len(rows) == 100 and page < 20:
            next_page, next_offset = page + 1, 0
        ranking_ref = f"raiderio:rankings:{season}:{region}:{class_name}:{spec}:{page}"
        evidence.append(
            {
                "id": ranking_ref,
                "sourceName": "Raider.IO",
                "sourceUrl": endpoint,
                "sourceStatus": "fetched",
                "fetchedAt": _now(),
                "season": season,
            }
        )
        limitations = (
            [
                f"Discarded {discarded} upstream rows whose class/spec identity did not match the query."
            ]
            if discarded
            else []
        )
        status = "source_reference"
        next_actions = []
        if not projected:
            status = "partial" if next_page is not None else "not_found"
            limitations.append("No valid ranking rows were available in the requested class/spec slice.")
            if next_page is not None:
                next_actions.append("Continue with pagination.nextPage and pagination.nextOffset to find valid samples.")
        return _packet(
            status=status,
            facts=projected,
            evidence=evidence,
            limitations=limitations,
            next_actions=next_actions,
            pagination={
                "page": page,
                "offset": offset,
                "limit": limit,
                "returned": len(projected),
                "upstreamCount": len(rows),
                "nextPage": next_page,
                "nextOffset": next_offset,
            },
        )

    def character(self, target: str) -> dict[str, Any]:
        parsed = parse_character_source_url(target)
        if parsed.provider is not SourceProvider.RAIDERIO:
            raise InvalidSourceLink()
        endpoint_values = {
            "region": parsed.region,
            "realm": parsed.realm,
            "name": parsed.character_name,
            "fields": "gear,talents,mythic_plus_scores_by_season:current",
        }
        access_key = os.environ.get("WOW_RAIDERIO_API_KEY", "").strip()
        if access_key:
            endpoint_values["access_key"] = access_key
        endpoint = _PROFILE_API + "?" + urlencode(endpoint_values)
        evidence = {
            "id": f"raiderio:character:{parsed.region}:{parsed.realm}:{parsed.character_name}",
            "sourceName": "Raider.IO",
            "sourceUrl": parsed.url,
            "sourceStatus": "blocked",
            "fetchedAt": _now(),
        }
        try:
            raw = _mapping(_fetch_json(self._http_client, endpoint))
        except Exception as error:
            status = _source_error_status(error)
            evidence["sourceStatus"] = status
            return _packet(
                status=status,
                facts=[],
                evidence=[evidence],
                limitations=["Raider.IO did not return a usable character profile."],
                next_actions=["Check the character region, realm and name, then retry."],
            )
        try:
            identity_matches = self._verified_identity(parsed.region, parsed.realm, parsed.character_name, raw)
        except Exception:
            evidence['sourceStatus'] = 'identity_unverified'
            return _packet(status='unavailable', facts=[], evidence=[evidence],
                           limitations=['The realm alias could not be verified because its source was unavailable.'],
                           next_actions=['Retry the same character after the source recovers.'])
        if not identity_matches:
            evidence["sourceStatus"] = "identity_mismatch"
            return _packet(
                status="blocked",
                facts=[],
                evidence=[evidence],
                limitations=[
                    "The Raider.IO profile identity did not exactly match the requested character."
                ],
                next_actions=["Check the character URL before retrying."],
            )
        evidence["sourceStatus"] = "fetched"
        updated = _text(
            raw.get("last_crawled_at") or raw.get("profile_updated_at"), 80
        )
        if updated:
            evidence["sourceRevision"] = updated
        fact = {
            "character": {
                "name": _text(raw.get("name"), 160),
                "realm": _text(raw.get("realm"), 160),
                "region": _slug(raw.get("region")),
                "className": _slug(raw.get("class")),
                "spec": _slug(raw.get("active_spec_name")),
                "level": _positive_int(raw.get("level")),
            },
            "gear": _safe_gear(raw.get("gear")),
            "talents": _selected_talents(
                raw.get("talentLoadout") or raw.get("talents")
            ),
            "mythicPlusScores": _safe_scores(
                raw.get("mythic_plus_scores_by_season")
            ),
            "profileUpdatedAt": updated,
            "statPercentagesStatus": "not_provided",
        }
        return _packet(
            status="source_reference",
            facts=[fact],
            evidence=[evidence],
            limitations=["Raider.IO did not provide percentages; none were estimated."],
        )

    def characters(self, targets: list[str]) -> dict[str, Any]:
        if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
            raise InvalidSourceLink(
                "Raider.IO character batch must contain 1 to 10 URLs"
            )
        unique: list[str] = []
        seen: set[str] = set()
        for target in targets:
            parsed = parse_character_source_url(target)
            if parsed.provider is not SourceProvider.RAIDERIO:
                raise InvalidSourceLink()
            key = parsed.url.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(parsed.url)
        with ThreadPoolExecutor(max_workers=3) as executor:
            packets = list(executor.map(self.character, unique))
        facts = [
            fact
            for packet in packets
            for fact in packet.get("facts", [])
            if isinstance(fact, dict)
        ]
        evidence = [
            item
            for packet in packets
            for item in packet.get("evidence", [])
            if isinstance(item, dict)
        ]
        succeeded = sum(
            packet.get("status") == "source_reference" for packet in packets
        )
        failed = len(packets) - succeeded
        status = (
            "source_reference"
            if succeeded == len(packets)
            else "partial"
            if succeeded
            else "blocked"
        )
        limitations = [
            text
            for packet in packets
            for text in packet.get("limitations", [])
            if isinstance(text, str)
        ]
        if failed:
            limitations.insert(
                0,
                f"{failed} of {len(packets)} unique Raider.IO profiles could not be verified.",
            )
        result = _packet(
            status=status,
            facts=facts[:10],
            evidence=evidence[:10],
            limitations=limitations,
        )
        result["counts"] = {
            "requested": len(targets),
            "unique": len(unique),
            "succeeded": succeeded,
            "failed": failed,
        }
        return result

    @staticmethod
    def _season_from_leaderboard(value: object) -> str:
        parsed = urlparse(_text(value, 2048))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {
            "raider.io",
            "www.raider.io",
        }:
            raise InvalidSourceLink(
                "Raider.IO returned an invalid current-season URL"
            )
        parts = [part for part in parsed.path.split("/") if part]
        try:
            marker = next(part for part in parts if part in {
                "mythic-plus-rankings", "mythic-plus-affix-rankings"})
            season = parts[parts.index(marker) + 1]
        except (ValueError, IndexError, StopIteration) as error:
            raise InvalidSourceLink("Raider.IO returned no current season") from error
        if not _SEASON_RE.fullmatch(season):
            raise InvalidSourceLink("Raider.IO returned an invalid current season")
        return season

    @staticmethod
    def _ranking_row(
        value: object, class_name: str, spec: str
    ) -> dict[str, Any] | None:
        row = _mapping(value)
        character = _mapping(row.get("character"))
        raw_class = _slug(_mapping(character.get("class")).get("slug"))
        raw_spec = _mapping(character.get("spec"))
        if raw_class != class_name or _slug(raw_spec.get("slug")) != spec:
            return None
        name = _text(character.get("name"), 160)
        region = _slug(_mapping(character.get("region")).get("slug"))
        realm = _slug(_mapping(character.get("realm")).get("slug"))
        if not name or not region or not realm:
            return None
        canonical_url = (
            "https://raider.io/characters/"
            + "/".join(
                quote(part, safe="-_.~") for part in (region, realm, name)
            )
        )
        parse_character_source_url(canonical_url)
        return {
            "rank": _positive_int(row.get("rank")),
            "score": _number(row.get("score")),
            "character": {
                "name": name,
                "path": _text(character.get("path"), 512),
                "url": canonical_url,
                "region": region,
                "realm": realm,
                "className": raw_class,
                "spec": spec,
                "specId": _positive_int(raw_spec.get("id")),
                "level": _positive_int(character.get("level")),
            },
        }

    @staticmethod
    def _identity_matches(
        region: str, realm: str, name: str, raw: Mapping[str, Any]
    ) -> bool:
        return (
            _identity(region) == _identity(raw.get("region"))
            and _identity(realm) == _identity(raw.get("realm"))
            and _identity(name) == _identity(raw.get("name"))
        )

    def _verified_identity(self, region, realm, name, raw):
        if _identity(region) != _identity(raw.get('region')) or _identity(name) != _identity(raw.get('name')):
            return False
        try:
            canonical = parse_character_source_url(raw.get('profile_url') or '')
        except InvalidSourceLink:
            return False
        if (canonical.provider is not SourceProvider.RAIDERIO or canonical.region != region
                    or _identity(canonical.character_name) != _identity(name)):
            return False
        # A display name may contain punctuation omitted by the provider's URL slug.
        display_slug = _identity(raw.get('realm')).replace("'", '').replace('’', '')
        if _identity(realm) == _identity(canonical.realm) and display_slug == _identity(canonical.realm):
            return True
        server = self._realm_resolver(region, realm)
        return bool(server and str((server.get('region') or {}).get('slug', '')).lower() == region
                    and _identity(server.get('slug')) == _identity(canonical.realm))


__all__ = ("RaiderIOResearch",)
