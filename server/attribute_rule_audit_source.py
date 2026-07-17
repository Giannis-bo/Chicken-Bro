#!/usr/bin/env python3
"""Read-only official-profile adapter for winner attribute rule audits."""

from __future__ import annotations

import re
from typing import Any

try:
    from .websim_payload import blizzard_get, blizzard_namespace, get_blizzard_access_token
except ImportError:
    from websim_payload import blizzard_get, blizzard_namespace, get_blizzard_access_token


class AttributeAuditSourceUnavailable(RuntimeError):
    """A stable, secret-free reason why an official profile could not be audited."""

    def __init__(self, code: str):
        self.code = str(code or "OFFICIAL_PROFILE_UNAVAILABLE")[:120]
        super().__init__(self.code)


_SLOT_KEYS = {
    "HEAD": "head", "NECK": "neck", "SHOULDER": "shoulder", "BACK": "back", "CHEST": "chest",
    "WRIST": "wrist", "HANDS": "hands", "WAIST": "waist", "LEGS": "legs", "FEET": "feet",
    "FINGER_1": "finger1", "FINGER_2": "finger2", "TRINKET_1": "trinket1", "TRINKET_2": "trinket2",
    "MAIN_HAND": "main_hand", "OFF_HAND": "off_hand",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).lower()).strip("_")


def _identity(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_IDENTITY_INVALID")
    identity = {
        "region": _slug(value.get("region")),
        "realmSlug": _slug(value.get("realmSlug")),
        "characterName": _text(value.get("characterName")),
        "locale": _text(value.get("locale")) or "en_US",
    }
    if not identity["region"] or not identity["realmSlug"] or not identity["characterName"]:
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_IDENTITY_INVALID")
    return identity


def _profile_character(profile: dict[str, Any]) -> dict[str, Any]:
    character_class = profile.get("character_class") if isinstance(profile.get("character_class"), dict) else {}
    active_spec = profile.get("active_spec") if isinstance(profile.get("active_spec"), dict) else {}
    race = profile.get("race") if isinstance(profile.get("race"), dict) else {}
    character = {
        "classKey": _slug(character_class.get("name")),
        "specKey": _slug(active_spec.get("name")),
        "raceKey": _slug(race.get("name")),
        "level": profile.get("level"),
    }
    if not all((character["classKey"], character["specKey"], character["raceKey"])) or not isinstance(character["level"], int):
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_CHARACTER_INCOMPLETE")
    return character


def _normalized_equipment(payload: dict[str, Any]) -> list[dict[str, Any]]:
    equipment_rows = payload.get("equipped_items") if isinstance(payload.get("equipped_items"), list) else []
    rows: list[dict[str, Any]] = []
    for item in equipment_rows:
        if not isinstance(item, dict):
            continue
        slot = item.get("slot") if isinstance(item.get("slot"), dict) else {}
        item_ref = item.get("item") if isinstance(item.get("item"), dict) else {}
        level = item.get("level") if isinstance(item.get("level"), dict) else {}
        slot_key = _SLOT_KEYS.get(_text(slot.get("type")))
        item_id = _text(item_ref.get("id"))
        item_level = level.get("value")
        if not slot_key or not item_id or isinstance(item_level, bool) or not isinstance(item_level, int):
            continue
        sockets = item.get("sockets") if isinstance(item.get("sockets"), list) else []
        gem_ids = sorted([
            _text((socket.get("item") or {}).get("id"))
            for socket in sockets if isinstance(socket, dict) and _text((socket.get("item") or {}).get("id"))
        ])
        enchantment = item.get("enchantment") if isinstance(item.get("enchantment"), dict) else {}
        enchant_id = _text(enchantment.get("enchantment_id") or enchantment.get("id"))
        rows.append({
            "slot": slot_key,
            "itemId": item_id,
            "itemLevel": item_level,
            "bonusIds": sorted({_text(value) for value in item.get("bonus_list") or [] if _text(value)}),
            "gemIds": gem_ids,
            "enchantIds": [enchant_id] if enchant_id else [],
        })
    return rows


def _observed_panel(profile: dict[str, Any]) -> dict[str, Any]:
    """Accept only an already structured panel; unknown upstream shapes stay absent."""
    return profile.get("attributeAuditPanel") if isinstance(profile.get("attributeAuditPanel"), dict) else {}


def fetch_official_profile(identity: dict[str, str]) -> dict[str, Any]:
    """Fetch profile/equipment read-only and reduce any failure to a safe code."""
    normalized = _identity(identity)
    try:
        token = get_blizzard_access_token(normalized["region"])
        namespace = blizzard_namespace(normalized["region"], "profile")
        base = f"/profile/wow/character/{normalized['realmSlug']}/{normalized['characterName'].lower()}"
        profile = blizzard_get(base, token, region=normalized["region"], locale=normalized["locale"], namespace=namespace)
        equipment = blizzard_get(f"{base}/equipment", token, region=normalized["region"], locale=normalized["locale"], namespace=namespace)
    except AttributeAuditSourceUnavailable:
        raise
    except Exception as exc:
        code = "OFFICIAL_PROFILE_AUTH_UNAVAILABLE" if "token" in _text(exc).lower() or "credential" in _text(exc).lower() else "OFFICIAL_PROFILE_UNAVAILABLE"
        raise AttributeAuditSourceUnavailable(code) from None
    if not isinstance(profile, dict) or not isinstance(equipment, dict):
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_PAYLOAD_INVALID")
    normalized_profile = {"character": _profile_character(profile), "equipment": _normalized_equipment(equipment)}
    if not normalized_profile["equipment"]:
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_EQUIPMENT_UNAVAILABLE")
    return {"profile": normalized_profile, "panel": _observed_panel(profile)}


__all__ = ("AttributeAuditSourceUnavailable", "fetch_official_profile")
