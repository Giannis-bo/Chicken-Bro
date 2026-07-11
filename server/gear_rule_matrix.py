#!/usr/bin/env python3
"""Fixed, ordered, pure legality rules for equipment selection intents."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable

try:
    from .gear_contracts import parse_selection_intent, validate_authority_context
    from .gear_result_envelope import gear_problem
except ImportError:
    from gear_contracts import parse_selection_intent, validate_authority_context
    from gear_result_envelope import gear_problem


RULE_MATRIX_REVISION = "gear-rule-matrix-v1"

Evaluator = Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]]


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    rule_revision: str
    order: int
    scope: str
    parameters: tuple[str, ...]
    authority_source_refs: tuple[str, ...]
    blocker_code: str
    evaluator: Evaluator


def _problem(
    prefix: str,
    suffix: str,
    title: str,
    *,
    kind: str = "ILLEGAL_SELECTION",
    detail: str = "",
    path: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return gear_problem(
        kind,
        f"{prefix}{suffix}",
        title,
        detail=detail,
        path=path,
        meta=meta,
    )


def _selected_items(intent: dict[str, Any], authority: dict[str, Any]):
    items = authority["itemsById"]
    for slot, selection in intent["slots"].items():
        yield slot, selection, items.get(selection["itemId"])


def _effective_item_for_selection(
    selection: dict[str, Any],
    item: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    """Project verified variant/overlay capability overrides for option rules."""

    effective = dict(item)
    capabilities = dict(item.get("baseCapabilities") or {})
    for field in (
        "socketCount",
        "canEnchant",
        "canEmbellish",
        "allowedGemOptionIds",
        "allowedEnchantOptionIds",
        "allowedEmbellishmentOptionIds",
        "allowedCraftedOptionIds",
        "allowedCatalystOptionIds",
    ):
        if field in item and field not in capabilities:
            capabilities[field] = item[field]

    variant = authority.get("variantsByKey", {}).get(selection.get("variantKey"))
    if (
        isinstance(variant, dict)
        and variant.get("itemId") == selection.get("itemId")
        and variant.get("status") == "verified"
    ):
        overrides = variant.get("capabilityOverrides")
        if isinstance(overrides, dict):
            capabilities.update(overrides)
        overlay = variant.get("overlay")
        if isinstance(overlay, dict) and overlay.get("status") == "verified":
            overrides = overlay.get("capabilityOverrides")
            if isinstance(overrides, dict):
                capabilities.update(overrides)

    effective["effectiveCapabilities"] = capabilities
    effective.update(capabilities)
    return effective


def _season_release_identity(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    authored = intent["authoredAgainst"]
    manifest = authority["manifest"]
    vector = authority["dependencyVector"]
    for field, suffix in (
        ("seasonRevision", "SEASON_REVISION_CONFLICT"),
        ("gearCatalogRevision", "CATALOG_REVISION_CONFLICT"),
    ):
        if authored.get(field) != manifest.get(field):
            problems.append(
                _problem(
                    "GEAR_RELEASE_",
                    suffix,
                    "Selection was authored against a different release.",
                    kind="REVISION_CONFLICT",
                    path=f"authoredAgainst.{field}",
                    meta={"authored": authored.get(field), "current": manifest.get(field)},
                )
            )
    for field in ("seasonRevision", "gearCatalogReleaseId", "gearCatalogRevision"):
        if manifest.get(field) != vector.get(field):
            problems.append(
                _problem(
                    "GEAR_RELEASE_",
                    "AUTHORITY_REVISION_CONFLICT",
                    "Authority release facts disagree.",
                    kind="AUTHORITY_UNAVAILABLE",
                    path=f"dependencyVector.{field}",
                    meta={"manifest": manifest.get(field), "dependency": vector.get(field)},
                )
            )

    items = authority["itemsById"]
    variants = authority["variantsByKey"]
    for slot, selection in intent["slots"].items():
        item_id = selection["itemId"]
        variant_key = selection["variantKey"]
        if item_id not in items:
            problems.append(
                _problem("GEAR_RELEASE_", "ITEM_UNKNOWN", "Item is absent from the current authority release.", path=f"slots.{slot}.itemId")
            )
            continue
        if variant_key:
            variant = variants.get(variant_key)
            if not isinstance(variant, dict):
                problems.append(
                    _problem("GEAR_RELEASE_", "VARIANT_UNKNOWN", "Variant is absent from the current authority release.", path=f"slots.{slot}.variantKey")
                )
            elif variant.get("itemId") != item_id:
                problems.append(
                    _problem("GEAR_RELEASE_", "VARIANT_ITEM_MISMATCH", "Variant does not belong to the selected item.", path=f"slots.{slot}.variantKey")
                )
    return problems


def _slot_inventory_type(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    inventory_by_slot = authority["ruleParameters"].get("inventoryTypesBySlot")
    if not isinstance(inventory_by_slot, dict):
        return [_problem("GEAR_SLOT_", "AUTHORITY_UNAVAILABLE", "Slot inventory parameters are unavailable.", kind="AUTHORITY_UNAVAILABLE", path="ruleParameters.inventoryTypesBySlot")]
    for slot, _selection, item in _selected_items(intent, authority):
        if not isinstance(item, dict):
            continue
        allowed_slots = item.get("allowedSlots")
        if not isinstance(allowed_slots, list):
            problems.append(_problem("GEAR_SLOT_", "AUTHORITY_UNAVAILABLE", "Allowed-slot authority is unavailable.", kind="AUTHORITY_UNAVAILABLE", path=f"itemsById.{item.get('itemId', '')}.allowedSlots"))
        elif slot not in allowed_slots:
            problems.append(_problem("GEAR_SLOT_", "NOT_ALLOWED", "Item cannot be equipped in this slot.", path=f"slots.{slot}.itemId"))
        allowed_inventory = inventory_by_slot.get(slot)
        if not isinstance(allowed_inventory, list):
            problems.append(_problem("GEAR_SLOT_", "AUTHORITY_UNAVAILABLE", "Slot inventory-type authority is unavailable.", kind="AUTHORITY_UNAVAILABLE", path=f"ruleParameters.inventoryTypesBySlot.{slot}"))
        elif item.get("inventoryType") not in allowed_inventory:
            problems.append(_problem("GEAR_SLOT_", "INVENTORY_TYPE_MISMATCH", "Item inventory type is not valid for this slot.", path=f"slots.{slot}.itemId"))
    return problems


def _class_spec_armor_weapon(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    eligibility = intent["eligibilityContext"]
    class_key = eligibility["classKey"]
    spec_key = eligibility["specKey"]
    params = authority["ruleParameters"]
    armor_by_class = params.get("allowedArmorTypesByClass", {})
    weapon_by_spec = params.get("allowedWeaponTypesByClassSpec", {})
    for slot, _selection, item in _selected_items(intent, authority):
        if not isinstance(item, dict):
            continue
        if class_key not in item.get("allowedClassKeys", []):
            problems.append(_problem("GEAR_ELIGIBILITY_", "CLASS_MISMATCH", "Item is not allowed for this class.", path=f"slots.{slot}.itemId"))
        if spec_key not in item.get("allowedSpecKeys", []):
            problems.append(_problem("GEAR_ELIGIBILITY_", "SPEC_MISMATCH", "Item is not allowed for this specialization.", path=f"slots.{slot}.itemId"))
        armor_type = item.get("armorType")
        if armor_type and armor_type not in armor_by_class.get(class_key, []):
            problems.append(_problem("GEAR_ELIGIBILITY_", "ARMOR_TYPE_MISMATCH", "Armor type is not allowed for this class.", path=f"slots.{slot}.itemId"))
        weapon_type = item.get("weaponType")
        if weapon_type and weapon_type not in weapon_by_spec.get(f"{class_key}:{spec_key}", []):
            problems.append(_problem("GEAR_ELIGIBILITY_", "WEAPON_TYPE_MISMATCH", "Weapon type is not allowed for this class and specialization.", path=f"slots.{slot}.itemId"))
    return problems


def _weapon_hand_configuration(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    slots = intent["slots"]
    main_selection = slots.get("main_hand")
    off_selection = slots.get("off_hand")
    items = authority["itemsById"]
    main_item = items.get(main_selection["itemId"]) if main_selection else None
    off_item = items.get(off_selection["itemId"]) if off_selection else None
    if off_selection and not main_selection:
        problems.append(_problem("GEAR_HAND_", "OFFHAND_REQUIRES_MAIN_HAND", "Off-hand selection requires a main-hand item.", path="slots.off_hand"))
    if isinstance(main_item, dict) and main_item.get("handedness") == "two_hand" and off_selection:
        problems.append(_problem("GEAR_HAND_", "TWO_HAND_OFFHAND_CONFLICT", "A two-hand weapon cannot be combined with an off-hand item.", path="slots.off_hand"))
    if isinstance(off_item, dict) and off_item.get("inventoryType") == "weapon":
        eligibility = intent["eligibilityContext"]
        spec = f"{eligibility['classKey']}:{eligibility['specKey']}"
        dual_wield = authority["ruleParameters"].get("dualWieldByClassSpec", {}).get(spec)
        if dual_wield is not True:
            problems.append(_problem("GEAR_HAND_", "DUAL_WIELD_NOT_ALLOWED", "This class and specialization cannot dual-wield weapons.", path="slots.off_hand"))
    return problems


def _unique_equipped(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    item_counts = Counter(selection["itemId"] for selection in intent["slots"].values())
    group_counts: Counter[str] = Counter()
    items = authority["itemsById"]
    for item_id, count in item_counts.items():
        item = items.get(item_id)
        if not isinstance(item, dict):
            continue
        limit = item.get("uniqueLimit", 0)
        if isinstance(limit, int) and limit > 0 and count > limit:
            problems.append(_problem("GEAR_UNIQUE_", "LIMIT_EXCEEDED", "Unique-equipped item limit was exceeded.", meta={"itemId": item_id, "count": count, "limit": limit}))
        group = item.get("uniqueGroupId")
        if group:
            group_counts[group] += count
    limits = authority["ruleParameters"].get("uniqueLimits", {})
    for group in sorted(group_counts):
        limit = limits.get(group)
        if isinstance(limit, int) and group_counts[group] > limit:
            problems.append(_problem("GEAR_UNIQUE_", "GROUP_LIMIT_EXCEEDED", "Unique-equipped group limit was exceeded.", meta={"uniqueGroupId": group, "count": group_counts[group], "limit": limit}))
    return problems


def _socket_and_gem(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    options = authority["optionsById"]
    unique_counts: Counter[str] = Counter()
    option_limits: dict[str, int] = {}
    for slot, selection, item in _selected_items(intent, authority):
        if not isinstance(item, dict):
            continue
        item = _effective_item_for_selection(selection, item, authority)
        gem_ids = selection["gemOptionIds"]
        capacity = item.get("socketCount")
        if not isinstance(capacity, int):
            problems.append(_problem("GEAR_GEM_", "AUTHORITY_UNAVAILABLE", "Socket capacity authority is unavailable.", kind="AUTHORITY_UNAVAILABLE", path=f"itemsById.{item.get('itemId', '')}.socketCount"))
            continue
        if len(gem_ids) > capacity:
            problems.append(_problem("GEAR_GEM_", "SOCKET_CAPACITY_EXCEEDED", "Selected gems exceed authoritative socket capacity.", path=f"slots.{slot}.gemOptionIds"))
        allowed = item.get("allowedGemOptionIds", [])
        for index, option_id in enumerate(gem_ids):
            option = options.get(option_id)
            path = f"slots.{slot}.gemOptionIds.{index}"
            if not isinstance(option, dict):
                problems.append(_problem("GEAR_GEM_", "OPTION_UNKNOWN", "Gem option is absent from authority.", path=path))
                continue
            if option.get("optionType") != "gem":
                problems.append(_problem("GEAR_GEM_", "OPTION_TYPE_MISMATCH", "Selected option is not a gem.", path=path))
            if option_id not in allowed:
                problems.append(_problem("GEAR_GEM_", "OPTION_NOT_ALLOWED", "Gem option is not allowed for this item.", path=path))
            group = option.get("uniqueGroupId")
            if group:
                unique_counts[group] += 1
                if isinstance(option.get("uniqueLimit"), int) and option["uniqueLimit"] > 0:
                    option_limits[group] = option["uniqueLimit"]
    configured_limits = authority["ruleParameters"].get("uniqueGemLimits", {})
    for group in sorted(unique_counts):
        limit = configured_limits.get(group, option_limits.get(group))
        if isinstance(limit, int) and unique_counts[group] > limit:
            problems.append(_problem("GEAR_GEM_", "UNIQUE_LIMIT_EXCEEDED", "Unique gem limit was exceeded.", meta={"uniqueGroupId": group, "count": unique_counts[group], "limit": limit}))
    return problems


def _enchant_and_runeforge(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    options = authority["optionsById"]
    eligibility = intent["eligibilityContext"]
    spec = f"{eligibility['classKey']}:{eligibility['specKey']}"
    runeforge_allowed = authority["ruleParameters"].get("runeforgeAllowedClassSpecs", [])
    for slot, selection, item in _selected_items(intent, authority):
        option_id = selection["enchantOptionId"]
        if not option_id or not isinstance(item, dict):
            continue
        item = _effective_item_for_selection(selection, item, authority)
        option = options.get(option_id)
        path = f"slots.{slot}.enchantOptionId"
        if not isinstance(option, dict):
            problems.append(_problem("GEAR_ENCHANT_", "OPTION_UNKNOWN", "Enchant option is absent from authority.", path=path))
            continue
        option_type = option.get("optionType")
        if option_type not in {"enchant", "runeforge"}:
            problems.append(_problem("GEAR_ENCHANT_", "OPTION_TYPE_MISMATCH", "Selected option is not an enchant or runeforge.", path=path))
        if option_id not in item.get("allowedEnchantOptionIds", []):
            problems.append(_problem("GEAR_ENCHANT_", "OPTION_NOT_ALLOWED", "Enchant option is not allowed for this item.", path=path))
        if option_type == "runeforge" and spec not in runeforge_allowed:
            problems.append(_problem("GEAR_ENCHANT_", "RUNEFORGE_NOT_ALLOWED", "Runeforge is not allowed for this class and specialization.", path=path))
    return problems


def _embellishment_and_crafted(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    options = authority["optionsById"]
    embellishment_count = 0
    for slot, selection, item in _selected_items(intent, authority):
        if not isinstance(item, dict):
            continue
        item = _effective_item_for_selection(selection, item, authority)
        for field, option_type, allowed_field, unknown_suffix in (
            ("embellishmentOptionId", "embellishment", "allowedEmbellishmentOptionIds", "EMBELLISHMENT_UNKNOWN"),
            ("craftedOptionId", "crafted", "allowedCraftedOptionIds", "OPTION_UNKNOWN"),
        ):
            option_id = selection[field]
            if not option_id:
                continue
            if field == "embellishmentOptionId":
                embellishment_count += 1
            path = f"slots.{slot}.{field}"
            option = options.get(option_id)
            if not isinstance(option, dict):
                problems.append(_problem("GEAR_CRAFT_", unknown_suffix, "Crafting option is absent from authority.", path=path))
                continue
            if option.get("optionType") != option_type:
                problems.append(_problem("GEAR_CRAFT_", "OPTION_TYPE_MISMATCH", "Crafting option type does not match the selection field.", path=path))
            if option_id not in item.get(allowed_field, []):
                problems.append(_problem("GEAR_CRAFT_", "OPTION_NOT_ALLOWED", "Crafting option is not allowed for this item.", path=path))
    limit = authority["ruleParameters"].get("embellishmentLimit")
    if not isinstance(limit, int):
        problems.append(_problem("GEAR_CRAFT_", "AUTHORITY_UNAVAILABLE", "Embellishment limit authority is unavailable.", kind="AUTHORITY_UNAVAILABLE", path="ruleParameters.embellishmentLimit"))
    elif embellishment_count > limit:
        problems.append(_problem("GEAR_CRAFT_", "EMBELLISHMENT_LIMIT_EXCEEDED", "Whole-character embellishment limit was exceeded.", meta={"count": embellishment_count, "limit": limit}))
    return problems


def _catalyst_tier_overlay(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    selected = [
        (slot, selection, item)
        for slot, selection, item in _selected_items(intent, authority)
        if selection["catalystOptionId"]
    ]
    if not selected:
        return []
    problems: list[dict[str, Any]] = []
    capability = authority["capabilities"].get("catalyst")
    expected_revision = authority["ruleParameters"].get("catalystRevision")
    if not isinstance(capability, dict) or capability.get("enabled") is not True:
        problems.append(_problem("GEAR_CATALYST_", "CAPABILITY_BLOCKED", "Catalyst remains fail-closed without a verified capability.", path="capabilities.catalyst.enabled"))
    elif not expected_revision or capability.get("revision") != expected_revision:
        problems.append(_problem("GEAR_CATALYST_", "REVISION_MISMATCH", "Catalyst capability revision does not match rule authority.", kind="REVISION_CONFLICT", path="capabilities.catalyst.revision"))
    options = authority["optionsById"]
    for slot, selection, item in selected:
        option_id = selection["catalystOptionId"]
        path = f"slots.{slot}.catalystOptionId"
        option = options.get(option_id)
        if not isinstance(option, dict):
            problems.append(_problem("GEAR_CATALYST_", "OPTION_UNKNOWN", "Catalyst option is absent from authority.", path=path))
            continue
        if option.get("optionType") != "catalyst":
            problems.append(_problem("GEAR_CATALYST_", "OPTION_TYPE_MISMATCH", "Selected option is not a Catalyst overlay.", path=path))
        if isinstance(item, dict):
            item = _effective_item_for_selection(selection, item, authority)
        if not isinstance(item, dict) or option_id not in item.get("allowedCatalystOptionIds", []):
            problems.append(_problem("GEAR_CATALYST_", "OPTION_NOT_ALLOWED", "Catalyst option is not allowed for this item.", path=path))
        if expected_revision and option.get("capabilityRevision") != expected_revision:
            problems.append(_problem("GEAR_CATALYST_", "OPTION_REVISION_MISMATCH", "Catalyst option revision does not match rule authority.", kind="REVISION_CONFLICT", path=path))
    return problems


def _cross_slot_set_aggregate(intent: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    parameters = authority["ruleParameters"]
    selected_ids = {selection["itemId"] for selection in intent["slots"].values()}
    for blocker in parameters.get("crossSlotBlockers", []):
        if not isinstance(blocker, dict):
            continue
        required = set(blocker.get("requiredItemIds", []))
        if required and required.issubset(selected_ids):
            code = blocker.get("code", "GEAR_AGGREGATE_FORBIDDEN_COMBINATION")
            if not isinstance(code, str) or not code.startswith("GEAR_AGGREGATE_"):
                code = "GEAR_AGGREGATE_FORBIDDEN_COMBINATION"
            problems.append(gear_problem("ILLEGAL_SELECTION", code, "Authoritative cross-slot combination is blocked.", detail=str(blocker.get("detail", "")), meta={"requiredItemIds": sorted(required)}))
    for aggregate in parameters.get("setAggregationInputs", []):
        if not isinstance(aggregate, dict):
            continue
        members = set(aggregate.get("memberItemIds", []))
        count = len(selected_ids.intersection(members))
        maximum = aggregate.get("maxSelected")
        if isinstance(maximum, int) and count > maximum:
            code = aggregate.get("blockerCode", "GEAR_AGGREGATE_SET_LIMIT_EXCEEDED")
            if not isinstance(code, str) or not code.startswith("GEAR_AGGREGATE_"):
                code = "GEAR_AGGREGATE_SET_LIMIT_EXCEEDED"
            problems.append(gear_problem("ILLEGAL_SELECTION", code, "Authoritative set aggregate limit was exceeded.", meta={"count": count, "maxSelected": maximum}))
    return problems


_RULES = (
    RuleDefinition("season_release_identity", RULE_MATRIX_REVISION, 10, "release,item,variant", ("seasonRevision", "gearCatalogRevision"), ("manifest", "dependencyVector", "itemsById", "variantsByKey"), "GEAR_RELEASE_", _season_release_identity),
    RuleDefinition("slot_inventory_type", RULE_MATRIX_REVISION, 20, "slot,item", ("inventoryTypesBySlot",), ("itemsById", "ruleParameters"), "GEAR_SLOT_", _slot_inventory_type),
    RuleDefinition("class_spec_armor_weapon", RULE_MATRIX_REVISION, 30, "character,item", ("allowedArmorTypesByClass", "allowedWeaponTypesByClassSpec"), ("itemsById", "ruleParameters"), "GEAR_ELIGIBILITY_", _class_spec_armor_weapon),
    RuleDefinition("weapon_hand_configuration", RULE_MATRIX_REVISION, 40, "main_hand,off_hand", ("dualWieldByClassSpec",), ("itemsById", "ruleParameters"), "GEAR_HAND_", _weapon_hand_configuration),
    RuleDefinition("unique_equipped", RULE_MATRIX_REVISION, 50, "whole_character", ("uniqueLimits",), ("itemsById", "ruleParameters"), "GEAR_UNIQUE_", _unique_equipped),
    RuleDefinition("socket_and_gem", RULE_MATRIX_REVISION, 60, "slot,sockets,whole_character", ("uniqueGemLimits",), ("itemsById", "optionsById", "ruleParameters"), "GEAR_GEM_", _socket_and_gem),
    RuleDefinition("enchant_and_runeforge", RULE_MATRIX_REVISION, 70, "slot,character", ("runeforgeAllowedClassSpecs",), ("itemsById", "optionsById", "ruleParameters"), "GEAR_ENCHANT_", _enchant_and_runeforge),
    RuleDefinition("embellishment_and_crafted", RULE_MATRIX_REVISION, 80, "slot,whole_character", ("embellishmentLimit",), ("itemsById", "optionsById", "ruleParameters"), "GEAR_CRAFT_", _embellishment_and_crafted),
    RuleDefinition("catalyst_tier_overlay", RULE_MATRIX_REVISION, 90, "slot,capability", ("catalystRevision",), ("itemsById", "optionsById", "capabilities", "ruleParameters"), "GEAR_CATALYST_", _catalyst_tier_overlay),
    RuleDefinition("cross_slot_set_aggregate", RULE_MATRIX_REVISION, 100, "whole_character,set", ("crossSlotBlockers", "setAggregationInputs"), ("itemsById", "ruleParameters"), "GEAR_AGGREGATE_", _cross_slot_set_aggregate),
)


def ordered_rule_matrix() -> tuple[RuleDefinition, ...]:
    return _RULES


def _result(rule: RuleDefinition, problems: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ruleId": rule.rule_id,
        "ruleRevision": rule.rule_revision,
        "status": "blocked" if problems else "verified",
        "problems": problems,
    }


def _contract_problem(issue: dict[str, Any]) -> dict[str, Any]:
    return gear_problem(
        issue.get("kind", "AUTHORITY_UNAVAILABLE"),
        issue.get("code", "AUTHORITY_UNAVAILABLE"),
        issue.get("message", "Required authority is unavailable."),
        path=issue.get("path", ""),
    )


def evaluate_rule_matrix(selection_intent: Any, authority_context: Any) -> dict[str, Any]:
    """Evaluate all explicit rules, short-circuiting only unavailable authority or invalid input."""

    authority_issues = validate_authority_context(
        selection_intent if isinstance(selection_intent, dict) else {},
        authority_context,
    )
    unavailable = [_contract_problem(issue) for issue in authority_issues if issue.get("kind") == "AUTHORITY_UNAVAILABLE"]
    if unavailable:
        first = _result(_RULES[0], unavailable)
        return {"ruleMatrixRevision": RULE_MATRIX_REVISION, "status": "blocked", "results": [first], "problems": unavailable}

    parsed_intent, intent_issues = parse_selection_intent(selection_intent)
    if intent_issues:
        problems = [_contract_problem(issue) for issue in intent_issues]
        first = _result(_RULES[0], problems)
        return {"ruleMatrixRevision": RULE_MATRIX_REVISION, "status": "blocked", "results": [first], "problems": problems}

    results = []
    all_problems: list[dict[str, Any]] = []
    for rule in _RULES:
        problems = rule.evaluator(parsed_intent, authority_context)
        results.append(_result(rule, problems))
        all_problems.extend(problems)
    return {
        "ruleMatrixRevision": RULE_MATRIX_REVISION,
        "status": "blocked" if all_problems else "verified",
        "results": results,
        "problems": all_problems,
    }


__all__ = (
    "RULE_MATRIX_REVISION",
    "RuleDefinition",
    "ordered_rule_matrix",
    "evaluate_rule_matrix",
)
