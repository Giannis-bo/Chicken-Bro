"""Exact, read-only Blizzard profile enrichment for source snapshots.

Raider.IO and Warcraft Logs remain the user-selected primary source.  This
adapter is only allowed to fill fields that the primary source omitted after
the public identity (region, realm and character name) matches exactly.  A
failed or mismatched official lookup is deliberately indistinguishable from
an unavailable enrichment so callers keep the honest incomplete snapshot.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from server.app.simulation.snapshots import sha256_json


_REGIONS: dict[str, tuple[str, str, str, str]] = {
    "us": ("us.api.blizzard.com", "profile-us", "en_US", "oauth.battle.net"),
    "eu": ("eu.api.blizzard.com", "profile-eu", "en_GB", "oauth.battle.net"),
    "kr": ("kr.api.blizzard.com", "profile-kr", "ko_KR", "oauth.battle.net"),
    "tw": ("tw.api.blizzard.com", "profile-tw", "zh_TW", "oauth.battle.net"),
    "cn": (
        "gateway.battlenet.com.cn",
        "profile-cn",
        "zh_CN",
        "oauth.battlenet.com.cn",
    ),
}
_SAFE_REGION = re.compile(r"^[a-z]{2}$")


@dataclass(frozen=True)
class BlizzardProfileEnrichment:
    """The verified facts and hashes returned by one official profile read."""

    character: Mapping[str, object]
    raw: Mapping[str, object]
    raw_sha256: str
    endpoint: str
    source_revision: str


def _text(value: object) -> str:
    return str(value or "").strip()


def _key(value: object) -> str:
    text = _text(value).lower().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "", text)


def _realm_slug(value: object) -> str:
    text = _text(value).lower().replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _nested_mapping(value: object, *keys: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    for key in keys:
        nested = value.get(key)
        if isinstance(nested, Mapping):
            return nested
    return {}


def _official_character(payload: Mapping[str, object]) -> dict[str, object]:
    realm = _nested_mapping(payload, "realm")
    race = _nested_mapping(payload, "race")
    character_class = _nested_mapping(payload, "character_class", "class")
    active_spec = _nested_mapping(payload, "active_spec", "activeSpec")
    level = _positive_int(payload.get("level"))
    return {
        "name": _text(payload.get("name")),
        "realm": _text(realm.get("slug") or realm.get("name")),
        "classKey": _key(character_class.get("slug") or character_class.get("name")),
        "specKey": _key(active_spec.get("slug") or active_spec.get("name")),
        "raceKey": _key(race.get("slug") or race.get("name")),
        "level": level,
    }


def _same_identity(source: Mapping[str, object], official: Mapping[str, object]) -> bool:
    source_name = _text(source.get("name"))
    source_realm = _realm_slug(source.get("realm"))
    official_name = _text(official.get("name"))
    official_realm = _realm_slug(official.get("realm"))
    if not source_name or not source_realm or not official_name or not official_realm:
        return False
    if source_name.casefold() != official_name.casefold() or source_realm != official_realm:
        return False
    for field in ("classKey", "specKey", "raceKey"):
        source_value = _key(source.get(field))
        official_value = _key(official.get(field))
        if source_value and (not official_value or source_value != official_value):
            return False
    return True


def _region_for(parsed_url: object, character: Mapping[str, object]) -> str:
    value = _text(getattr(parsed_url, "region", "")) or _text(character.get("region"))
    return value.lower()


def _profile_endpoint(region: str, realm: str, name: str) -> str | None:
    config = _REGIONS.get(region)
    if config is None or not _SAFE_REGION.fullmatch(region):
        return None
    host, namespace, locale, _oauth_host = config
    return (
        f"https://{host}/profile/wow/character/"
        f"{quote(realm, safe='-_.~')}/{quote(name, safe='-_.~')}?"
        + urlencode({"namespace": namespace, "locale": locale})
    )


def blizzard_oauth_token(region: str = "") -> str:
    """Return one short-lived token without leaking credentials or errors."""

    client_id = _text(os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID"))
    client_secret = _text(
        os.environ.get("WOW_BLIZZARD_CLIENT_SECRET")
        or os.environ.get("WOW_BNET_CLIENT_SECRET")
    )
    if not client_id or not client_secret:
        return ""
    config = _REGIONS.get(_text(region).lower(), _REGIONS["us"])
    oauth_host = config[3]
    token_url = f"https://{oauth_host}/token"
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        token_url,
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "chickenbro-simc/1",
        },
    )
    try:
        timeout = int(os.environ.get("WOW_BLIZZARD_TIMEOUT_SECONDS", "15"))
    except (TypeError, ValueError):
        timeout = 15
    timeout = max(1, min(timeout, 30))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(1_000_001).decode("utf-8"))
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, UnicodeError, json.JSONDecodeError):
        return ""
    token = _text(payload.get("access_token")) if isinstance(payload, Mapping) else ""
    return token if 1 <= len(token) <= 4096 and not any(char.isspace() for char in token) else ""


class BlizzardProfileEnricher:
    """Fetch and verify the exact official profile for a source character."""

    def __init__(
        self,
        http_client: object,
        *,
        token_provider: Callable[..., str] | None = None,
    ):
        self._http_client = http_client
        self._token_provider = token_provider or blizzard_oauth_token

    def enrich(
        self,
        parsed_url: object,
        character: Mapping[str, object],
    ) -> BlizzardProfileEnrichment | None:
        region = _region_for(parsed_url, character)
        realm = _realm_slug(character.get("realm"))
        name = _text(character.get("name"))
        endpoint = _profile_endpoint(region, realm, name)
        if endpoint is None or not realm or not name:
            return None
        try:
            try:
                token = _text(self._token_provider(region))
            except TypeError:
                token = _text(self._token_provider())
        except Exception:
            return None
        if not token:
            return None
        try:
            fetch = getattr(self._http_client, "fetch_json")
            try:
                raw = fetch(endpoint, headers={"Authorization": f"Bearer {token}"})
            except TypeError:
                raw = fetch(endpoint)
        except Exception:
            return None
        if not isinstance(raw, Mapping):
            return None
        official = _official_character(raw)
        if not _same_identity(character, official):
            return None
        if any(
            not official.get(field)
            for field in ("name", "realm", "classKey", "specKey", "raceKey", "level")
        ):
            return None
        raw_sha = sha256_json(raw)
        return BlizzardProfileEnrichment(
            character=official,
            raw=raw,
            raw_sha256=raw_sha,
            endpoint=endpoint,
            source_revision=f"blizzard-profile:{raw_sha}",
        )


__all__ = (
    "BlizzardProfileEnricher",
    "BlizzardProfileEnrichment",
    "blizzard_oauth_token",
)
