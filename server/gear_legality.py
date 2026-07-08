#!/usr/bin/env python3

try:
    from . import websim_payload as websim
except ImportError:
    import websim_payload as websim


GEAR_LEGALITY_RULE_VERSION = "2026-07-07-live-manual-overrides"
RULE_SOURCE = "manual_override"


def _item_identifier(item):
    if not isinstance(item, dict):
        return ""
    for key in ("itemId", "item_id", "id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _item_type_metadata(item):
    item = item if isinstance(item, dict) else {}
    armor_type = str(item.get("armorType") or "").strip()
    weapon_type = str(item.get("weaponType") or "").strip()
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
    if not armor_type or not weapon_type:
        metadata = websim.item_type_metadata_from_payload(payload)
        armor_type = armor_type or str(metadata.get("armorType") or "").strip()
        weapon_type = weapon_type or str(metadata.get("weaponType") or "").strip()
    return {"armorType": armor_type, "weaponType": weapon_type}


def _base_result(class_key, spec_key, slot, item=None):
    return {
        "status": "legal",
        "classKey": websim.slugify(class_key, ""),
        "specKey": websim.slugify(spec_key, ""),
        "slot": websim.normalize_slot(slot),
        "itemId": _item_identifier(item),
        "ruleVersion": GEAR_LEGALITY_RULE_VERSION,
        "ruleSource": RULE_SOURCE,
        "reasons": [],
        "blockedSlots": [],
        "warningSlots": [],
    }


def _reason(reason, slot, item=None, *, severity="blocker", **extra):
    payload = {
        "reason": reason,
        "severity": severity,
        "slot": websim.normalize_slot(slot),
        "itemId": _item_identifier(item),
        "source": RULE_SOURCE,
        "ruleVersion": GEAR_LEGALITY_RULE_VERSION,
    }
    payload.update({key: value for key, value in extra.items() if value not in (None, "")})
    return payload


def _finish_result(result):
    blocker_slots = [
        reason.get("slot")
        for reason in result.get("reasons") or []
        if reason.get("severity") == "blocker" and reason.get("slot")
    ]
    warning_slots = [
        reason.get("slot")
        for reason in result.get("reasons") or []
        if reason.get("severity") == "warning" and reason.get("slot")
    ]
    slot_order = {slot: index for index, slot in enumerate(websim.CANONICAL_GEAR_SLOTS)}
    result["blockedSlots"] = sorted(set(blocker_slots), key=lambda slot: slot_order.get(slot, len(slot_order)))
    result["warningSlots"] = sorted(set(warning_slots), key=lambda slot: slot_order.get(slot, len(slot_order)))
    if result["blockedSlots"]:
        result["status"] = "blocked"
    elif result["warningSlots"]:
        result["status"] = "warning"
    else:
        result["status"] = "legal"
    return result


def gear_legality_for_item(class_key, spec_key, slot, item):
    result = _base_result(class_key, spec_key, slot, item)
    class_key = result["classKey"]
    spec_key = result["specKey"]
    slot = result["slot"]
    if not class_key or not slot or not isinstance(item, dict):
        return result

    allowed_class_keys = websim.payload_playable_class_keys(item.get("payload") if isinstance(item.get("payload"), dict) else item)
    if allowed_class_keys and class_key not in allowed_class_keys:
        result["reasons"].append(
            _reason(
                "class_requirement_not_allowed",
                slot,
                item,
                allowedClassKeys=allowed_class_keys,
            )
        )

    metadata = _item_type_metadata(item)
    weapon_type = metadata.get("weaponType") or ""
    armor_type = metadata.get("armorType") or ""
    if slot in websim.WEAPON_SLOTS and weapon_type:
        if not websim.weapon_type_allowed_for_slot(class_key, spec_key, slot, weapon_type):
            result["reasons"].append(
                _reason(
                    "weapon_type_not_allowed_for_spec_slot",
                    slot,
                    item,
                    weaponType=weapon_type,
                    mode=(websim.weapon_equipment_rule_for_spec(class_key, spec_key) or {}).get("mode") or "",
                )
            )
    elif slot in websim.ARMOR_SLOTS and armor_type:
        expected_armor = websim.CLASS_ARMOR_TYPES.get(class_key) or ""
        if expected_armor and armor_type not in {"Miscellaneous", "Cosmetic"} and armor_type.lower() != expected_armor.lower():
            result["reasons"].append(
                _reason(
                    "armor_type_not_allowed_for_class",
                    slot,
                    item,
                    armorType=armor_type,
                    expectedArmorType=expected_armor,
                )
            )
    return _finish_result(result)


def gear_legality_for_template(class_key, spec_key, gear_by_slot, enhancement_by_slot=None):
    result = _base_result(class_key, spec_key, "")
    class_key = result["classKey"]
    spec_key = result["specKey"]
    normalized_items = [item for item in gear_by_slot or [] if isinstance(item, dict)]
    by_slot = {}
    for item in normalized_items:
        slot = websim.normalize_slot(item.get("slot") or item.get("simcSlot"))
        if slot:
            by_slot[slot] = item
        item_result = gear_legality_for_item(class_key, spec_key, slot, item)
        result["reasons"].extend(item_result.get("reasons") or [])

    main_hand = by_slot.get("main_hand")
    off_hand = by_slot.get("off_hand")
    main_hand_type = (_item_type_metadata(main_hand).get("weaponType") if main_hand else "") or ""
    rule = websim.weapon_equipment_rule_for_spec(class_key, spec_key)
    already_blocked = {
        reason.get("slot")
        for reason in result.get("reasons") or []
        if reason.get("severity") == "blocker"
    }
    if (
        off_hand
        and "off_hand" not in already_blocked
        and main_hand_type in websim.TWO_HAND_WEAPON_TYPES
        and rule.get("mode") != "dual_wield_2h"
    ):
        result["reasons"].append(
            _reason(
                "two_hand_main_hand_occupies_offhand",
                "off_hand",
                off_hand,
                mainHandWeaponType=main_hand_type,
            )
        )
    return _finish_result(result)
