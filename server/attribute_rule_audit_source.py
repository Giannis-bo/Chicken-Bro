#!/usr/bin/env python3
"""Read-only official-profile adapter for winner attribute rule audits."""

from __future__ import annotations

import math
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
        enchantments = item.get("enchantments") if isinstance(item.get("enchantments"), list) else []
        if not enchantments and isinstance(item.get("enchantment"), dict):
            enchantments = [item["enchantment"]]
        enchant_ids = sorted({
            _text(enchantment.get("enchantment_id") or enchantment.get("id"))
            for enchantment in enchantments
            if isinstance(enchantment, dict) and _text(enchantment.get("enchantment_id") or enchantment.get("id"))
        })
        rows.append({
            "slot": slot_key,
            "itemId": item_id,
            "itemLevel": item_level,
            "bonusIds": sorted({_text(value) for value in item.get("bonus_list") or [] if _text(value)}),
            "gemIds": gem_ids,
            "enchantIds": enchant_ids,
        })
    return rows


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _stat_number(value: Any, *keys: str) -> int | float | None:
    direct = _number(value)
    if direct is not None:
        return direct
    if not isinstance(value, dict):
        return None
    for key in keys:
        numeric = _number(value.get(key))
        if numeric is not None:
            return numeric
    return None


def _observed_panel(statistics: dict[str, Any]) -> dict[str, Any]:
    """Normalize only documented public statistics fields into the audit comparator shape."""
    if not isinstance(statistics, dict):
        return {}
    panel: dict[str, Any] = {"resources": {}, "secondary": []}
    primary = _stat_number(statistics.get("intellect"), "effective", "value")
    stamina = _stat_number(statistics.get("stamina"), "effective", "value")
    if primary is not None:
        panel["primary"] = {"rawValue": primary}
    if stamina is not None:
        panel["stamina"] = {"rawValue": stamina}
    for output_key, field_names, percent_fields in (
        ("crit", ("spell_crit", "critical_strike", "crit"), ("value", "final_percent", "rating_bonus")),
        ("haste", ("spell_haste", "haste"), ("value", "final_percent", "rating_bonus")),
        ("mastery", ("mastery",), ("value", "final_percent", "rating_bonus")),
        ("versatility", ("versatility",), ("damage_done_bonus", "value", "rating_bonus")),
        ("avoidance", ("avoidance",), ("value", "rating_bonus")),
        ("leech", ("lifesteal", "leech"), ("value", "rating_bonus")),
        ("speed", ("speed",), ("value", "rating_bonus")),
    ):
        stat = next((statistics.get(field) for field in field_names if statistics.get(field) is not None), None)
        rating = _stat_number(stat, "rating", "rating_normalized")
        percent = _stat_number(stat, *percent_fields)
        if rating is not None and percent is not None:
            panel["secondary"].append({
                "key": output_key,
                "rawValue": rating,
                "convertedValue": f"{percent}%",
                "displayUnit": "percent",
            })
    for output_key, field_names in (("health", ("health",)), ("mana", ("mana", "power"))):
        value = next((_stat_number(statistics.get(field), "effective", "value") for field in field_names if statistics.get(field) is not None), None)
        if value is not None:
            panel["resources"][output_key] = {"rawValue": value}
    if not panel["resources"]:
        panel.pop("resources")
    if not panel["secondary"]:
        panel.pop("secondary")
    return panel


def fetch_official_profile(identity: dict[str, str]) -> dict[str, Any]:
    """Fetch profile/equipment/statistics read-only and reduce any failure to a safe code."""
    normalized = _identity(identity)
    try:
        token = get_blizzard_access_token(normalized["region"])
        namespace = blizzard_namespace(normalized["region"], "profile")
        base = f"/profile/wow/character/{normalized['realmSlug']}/{normalized['characterName'].lower()}"
        # Character class/spec/race labels are locale-dependent, while the audit
        # contract requires stable canonical keys. The official profile endpoint
        # supports en_US in every supported region, so normalize at the source.
        audit_locale = "en_US"
        profile = blizzard_get(base, token, region=normalized["region"], locale=audit_locale, namespace=namespace)
        equipment = blizzard_get(f"{base}/equipment", token, region=normalized["region"], locale=audit_locale, namespace=namespace)
        statistics = blizzard_get(f"{base}/statistics", token, region=normalized["region"], locale=audit_locale, namespace=namespace)
    except AttributeAuditSourceUnavailable:
        raise
    except Exception as exc:
        code = "OFFICIAL_PROFILE_AUTH_UNAVAILABLE" if "token" in _text(exc).lower() or "credential" in _text(exc).lower() else "OFFICIAL_PROFILE_UNAVAILABLE"
        raise AttributeAuditSourceUnavailable(code) from None
    if not isinstance(profile, dict) or not isinstance(equipment, dict) or not isinstance(statistics, dict):
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_PAYLOAD_INVALID")
    normalized_profile = {"character": _profile_character(profile), "equipment": _normalized_equipment(equipment)}
    if not normalized_profile["equipment"]:
        raise AttributeAuditSourceUnavailable("OFFICIAL_PROFILE_EQUIPMENT_UNAVAILABLE")
    return {"profile": normalized_profile, "panel": _observed_panel(statistics)}


__all__ = ("AttributeAuditSourceUnavailable", "fetch_official_profile")
