"""Canonical current-season crafted PVE equipment membership.

The checked-in document is built from the isolated official evidence snapshot.
It owns item identity and crafting capabilities only.  Crafting progression
and resolved stat payloads remain separate, fail-closed authorities.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MEMBERSHIP_PATH = (
    BASE_DIR / "data" / "midnight-season-1-crafted-pve-membership.json"
)
SCHEMA_REVISION = "midnight-season-1-crafted-pve-membership-v1"
SEASON_REVISION = "midnight-season-1"
PROGRESSION_BLOCKER = "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE"
SECONDARY_STAT_MODES = {
    "customize_two_secondary",
    "amplify_one_secondary",
    "fixed_or_recipe_defined_stats",
}
INVENTORY_TYPE_TO_SLOT = {
    "HEAD": "head",
    "NECK": "neck",
    "SHOULDER": "shoulder",
    "CLOAK": "back",
    "CHEST": "chest",
    "ROBE": "chest",
    "WRIST": "wrist",
    "HAND": "hands",
    "WAIST": "waist",
    "LEGS": "legs",
    "FEET": "feet",
    "FINGER": "finger1",
    "TRINKET": "trinket1",
    "WEAPON": "main_hand",
    "WEAPONMAINHAND": "main_hand",
    "TWOHWEAPON": "main_hand",
    "RANGED": "main_hand",
    "RANGEDRIGHT": "main_hand",
    "THROWN": "main_hand",
    "SHIELD": "off_hand",
    "HOLDABLE": "off_hand",
    "WEAPONOFFHAND": "off_hand",
}


class CraftedPveMembershipError(ValueError):
    """Raised when current-season crafted membership evidence is incomplete."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _locale_text(value: Any, *locales: str) -> str:
    if isinstance(value, dict):
        for locale in locales:
            text = _text(value.get(locale))
            if text:
                return text
        for candidate in value.values():
            text = _text(candidate)
            if text:
                return text
        return ""
    return _text(value)


def _profession_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).lower()).strip("_")


def secondary_stat_mode(modified_slot_names: Any) -> str:
    names = {
        _text(name)
        for name in (modified_slot_names or [])
        if _text(name)
    }
    if "Customize Secondary Stats" in names:
        return "customize_two_secondary"
    if "Amplify Secondary Stat" in names:
        return "amplify_one_secondary"
    return "fixed_or_recipe_defined_stats"


def _official_search_records(official_search: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(official_search, dict):
        raise CraftedPveMembershipError(
            "official item search evidence must be an object"
        )
    records: dict[str, dict[str, Any]] = {}
    for raw in official_search.get("results") or []:
        result = raw if isinstance(raw, dict) else {}
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        item_id = _text(data.get("id"))
        if not item_id:
            continue
        if item_id in records:
            raise CraftedPveMembershipError(
                f"duplicate official item search record {item_id}"
            )
        records[item_id] = {
            "data": data,
            "key": result.get("key") if isinstance(result.get("key"), dict) else {},
        }
    return records


def _item_type_fields(data: dict[str, Any]) -> dict[str, Any]:
    item_class = (
        data.get("item_class")
        if isinstance(data.get("item_class"), dict)
        else {}
    )
    item_subclass = (
        data.get("item_subclass")
        if isinstance(data.get("item_subclass"), dict)
        else {}
    )
    class_id = int(item_class.get("id") or 0)
    subclass_name = _locale_text(item_subclass.get("name"), "en_US")
    result = {
        "itemClassId": class_id,
        "itemSubclassId": int(item_subclass.get("id") or 0),
        "itemClassName": _locale_text(item_class.get("name"), "en_US"),
        "itemSubclassName": subclass_name,
    }
    if class_id == 4 and subclass_name.lower() in {
        "cloth",
        "leather",
        "mail",
        "plate",
    }:
        result["armorType"] = subclass_name.lower()
    if class_id == 2 and subclass_name:
        result["weaponType"] = subclass_name.lower()
    return result


def build_crafted_pve_membership(
    crafted_source: Any,
    official_search: Any,
    *,
    season_revision: str,
    as_of: str,
) -> dict[str, Any]:
    """Join verified recipe outputs to official equippable item metadata."""

    if not isinstance(crafted_source, dict) or not isinstance(
        crafted_source.get("rawMembers"),
        list,
    ):
        raise CraftedPveMembershipError(
            "crafted source requires rawMembers"
        )
    official_records = _official_search_records(official_search)
    items = []
    seen_item_ids = set()
    seen_recipe_ids = set()
    for raw_member in crafted_source["rawMembers"]:
        member = raw_member if isinstance(raw_member, dict) else {}
        candidate_ids = sorted(
            {
                _text(item_id)
                for item_id in member.get("candidateItemIds") or []
                if _text(item_id)
            },
            key=int,
        )
        if len(candidate_ids) != 1:
            raise CraftedPveMembershipError(
                "crafted recipe "
                f"{_text(member.get('recipeId')) or 'unknown'} "
                f"requires exactly one candidate item, got {candidate_ids}"
            )
        item_id = candidate_ids[0]
        recipe_id = _text(member.get("recipeId"))
        if item_id in seen_item_ids:
            raise CraftedPveMembershipError(
                f"duplicate itemId {item_id}"
            )
        if not recipe_id:
            raise CraftedPveMembershipError(
                f"crafted item {item_id} is missing recipeId"
            )
        if _text(member.get("membershipStatus")) != "verified_output_item":
            raise CraftedPveMembershipError(
                f"crafted item {item_id} membershipStatus must be "
                "verified_output_item"
            )
        for field in ("clientBuild", "evidenceRef"):
            if not _text(member.get(field)):
                raise CraftedPveMembershipError(
                    f"crafted item {item_id} is missing {field}"
                )
        if recipe_id in seen_recipe_ids:
            raise CraftedPveMembershipError(
                f"duplicate recipeId {recipe_id}"
            )
        official = official_records.get(item_id)
        if not official:
            raise CraftedPveMembershipError(
                f"missing official item search record {item_id}"
            )
        data = official["data"]
        if data.get("is_equippable") is not True:
            raise CraftedPveMembershipError(
                f"official item {item_id} is not equippable"
            )
        if not _text(official["key"].get("href")):
            raise CraftedPveMembershipError(
                f"official item {item_id} is missing officialItemRef"
            )
        inventory = (
            data.get("inventory_type")
            if isinstance(data.get("inventory_type"), dict)
            else {}
        )
        inventory_type = _text(inventory.get("type")).upper()
        slot = INVENTORY_TYPE_TO_SLOT.get(inventory_type, "")
        if not slot:
            raise CraftedPveMembershipError(
                f"official item {item_id} has unsupported inventory type "
                f"{inventory_type or 'missing'}"
            )
        modified_names = sorted(
            {
                _text(name)
                for name in member.get("modifiedCraftingSlotNames") or []
                if _text(name)
            }
        )
        mode = secondary_stat_mode(modified_names)
        profession_name = _text(member.get("profession"))
        item = {
            "itemId": item_id,
            "recipeId": recipe_id,
            "name": (
                _locale_text(data.get("name"), "zh_CN", "en_US")
                or _text(member.get("name"))
                or f"item_{item_id}"
            ),
            "englishName": (
                _locale_text(data.get("name"), "en_US")
                or _text(member.get("name"))
            ),
            "slot": slot,
            "inventoryType": inventory_type,
            "profession": _profession_key(profession_name),
            "professionName": profession_name,
            "category": _text(member.get("category")),
            "membershipStatus": _text(member.get("membershipStatus")),
            "clientBuild": _text(member.get("clientBuild")),
            "secondaryStatMode": mode,
            "modifiedCraftingSlotNames": modified_names,
            "canAddEmbellishment": "Add Embellishment" in modified_names,
            "supportsSocketReagent": "Socket" in modified_names,
            "powerReagentMode": (
                "spark"
                if "Spark" in modified_names
                else "empower"
                if "Empower" in modified_names
                else "recipe_defined"
            ),
            "evidenceRef": _text(member.get("evidenceRef")),
            "officialItemRef": _text(official["key"].get("href")),
            **_item_type_fields(data),
        }
        items.append(item)
        seen_item_ids.add(item_id)
        seen_recipe_ids.add(recipe_id)
    items.sort(key=lambda item: int(item["itemId"]))
    mode_counts = Counter(item["secondaryStatMode"] for item in items)
    profession_counts = Counter(item["professionName"] for item in items)
    result = {
        "schemaVersion": 1,
        "schemaRevision": SCHEMA_REVISION,
        "seasonRevision": _text(season_revision),
        "asOf": _text(as_of),
        "status": "verified",
        "progressionStatus": "blocked",
        "progressionReasonCodes": [
            PROGRESSION_BLOCKER
        ],
        "summary": {
            "itemCount": len(items),
            "recipeCount": len(seen_recipe_ids),
            "bySecondaryStatMode": dict(sorted(mode_counts.items())),
            "byProfession": dict(sorted(profession_counts.items())),
        },
        "items": items,
    }
    return validate_crafted_pve_membership(result)


def validate_crafted_pve_membership(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CraftedPveMembershipError(
            "crafted PVE membership must be an object"
        )
    if payload.get("schemaVersion") != 1:
        raise CraftedPveMembershipError(
            "crafted PVE membership schemaVersion must be 1"
        )
    if _text(payload.get("schemaRevision")) != SCHEMA_REVISION:
        raise CraftedPveMembershipError(
            "crafted PVE membership schemaRevision mismatch"
        )
    if _text(payload.get("seasonRevision")) != SEASON_REVISION:
        raise CraftedPveMembershipError(
            "crafted PVE membership is missing seasonRevision or does not "
            f"match {SEASON_REVISION}"
        )
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _text(payload.get("asOf"))):
        raise CraftedPveMembershipError(
            "crafted PVE membership is missing asOf or it is not an ISO date"
        )
    if payload.get("status") != "verified":
        raise CraftedPveMembershipError(
            "crafted PVE membership status must be verified"
        )
    if payload.get("progressionStatus") != "blocked":
        raise CraftedPveMembershipError(
            "crafted PVE membership progressionStatus must be blocked"
        )
    progression_reason_codes = payload.get("progressionReasonCodes")
    if (
        not isinstance(progression_reason_codes, list)
        or PROGRESSION_BLOCKER not in progression_reason_codes
    ):
        raise CraftedPveMembershipError(
            "crafted PVE membership progressionReasonCodes must contain "
            f"{PROGRESSION_BLOCKER}"
        )
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise CraftedPveMembershipError(
            "crafted PVE membership items must be non-empty"
        )
    seen_item_ids = set()
    seen_recipe_ids = set()
    mode_counts = Counter()
    for raw_item in items:
        item = raw_item if isinstance(raw_item, dict) else {}
        item_id = _text(item.get("itemId"))
        recipe_id = _text(item.get("recipeId"))
        if not re.fullmatch(r"[1-9]\d*", item_id):
            raise CraftedPveMembershipError(
                f"crafted PVE membership item has invalid itemId "
                f"{item_id or 'missing'}"
            )
        if item_id in seen_item_ids:
            raise CraftedPveMembershipError(
                f"duplicate itemId {item_id}"
            )
        if not re.fullmatch(r"[1-9]\d*", recipe_id):
            raise CraftedPveMembershipError(
                f"crafted item {item_id} has invalid recipeId "
                f"{recipe_id or 'missing'}"
            )
        if recipe_id in seen_recipe_ids:
            raise CraftedPveMembershipError(
                f"duplicate recipeId {recipe_id}"
            )
        mode = _text(item.get("secondaryStatMode"))
        if mode not in SECONDARY_STAT_MODES:
            raise CraftedPveMembershipError(
                f"crafted item {item_id} has invalid secondaryStatMode "
                f"{mode or 'missing'}"
            )
        for field in (
            "name",
            "slot",
            "profession",
            "clientBuild",
            "evidenceRef",
            "officialItemRef",
        ):
            if not _text(item.get(field)):
                raise CraftedPveMembershipError(
                    f"crafted item {item_id} is missing {field}"
                )
        if item.get("membershipStatus") != "verified_output_item":
            raise CraftedPveMembershipError(
                f"crafted item {item_id} membershipStatus must be "
                "verified_output_item"
            )
        official_item_ref = _text(item.get("officialItemRef"))
        if not re.fullmatch(
            rf"https://[^/]+/data/wow/item/{re.escape(item_id)}(?:\?.*)?",
            official_item_ref,
        ):
            raise CraftedPveMembershipError(
                f"crafted item {item_id} officialItemRef does not bind the "
                "same official item"
            )
        seen_item_ids.add(item_id)
        seen_recipe_ids.add(recipe_id)
        mode_counts[mode] += 1
    summary = (
        payload.get("summary")
        if isinstance(payload.get("summary"), dict)
        else {}
    )
    expected_count = int(summary.get("itemCount") or 0)
    if expected_count != len(items):
        raise CraftedPveMembershipError(
            "crafted PVE membership item count mismatch: "
            f"summary={expected_count}, actual={len(items)}"
        )
    expected_modes = summary.get("bySecondaryStatMode")
    if expected_modes != dict(sorted(mode_counts.items())):
        raise CraftedPveMembershipError(
            "crafted PVE membership secondary stat mode summary mismatch"
        )
    return payload


def load_crafted_pve_membership(
    path: str | Path = DEFAULT_MEMBERSHIP_PATH,
) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CraftedPveMembershipError(
            f"cannot load crafted PVE membership {source}: {error}"
        ) from error
    return validate_crafted_pve_membership(payload)


def crafted_pve_membership_items(
    path: str | Path = DEFAULT_MEMBERSHIP_PATH,
) -> list[dict[str, Any]]:
    return list(load_crafted_pve_membership(path)["items"])
