#!/usr/bin/env python3
"""Pure reference evaluator for non-combat gear attributes.

The evaluator has no persistence, Resolver, HTTP, or SimulationCraft dependency.
It receives only a released rule context plus server-owned static input facts.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


ATTRIBUTE_CALCULATION_CONTRACT_REVISION = "gear-attribute-calculation-v1"

_MAX_IDENTIFIER_LENGTH = 256
_STATIC_ATTRIBUTE_ALIASES = {
    "int": "intellect",
    "intellect": "intellect",
    "stam": "stamina",
    "stamina": "stamina",
    "crit": "crit_rating",
    "critical_strike": "crit_rating",
    "critical_strike_rating": "crit_rating",
    "crit_rating": "crit_rating",
    "haste": "haste_rating",
    "haste_rating": "haste_rating",
    "mastery": "mastery_rating",
    "mastery_rating": "mastery_rating",
    "versatility": "versatility_rating",
    "versatility_rating": "versatility_rating",
    "avoidance": "avoidance_rating",
    "avoidance_rating": "avoidance_rating",
    "leech": "leech_rating",
    "leech_rating": "leech_rating",
    "speed": "speed_rating",
    "speed_rating": "speed_rating",
}


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"kind": "ATTRIBUTE_RULE_UNAVAILABLE", "code": code, "path": path, "message": message}


def _bounded_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_IDENTIFIER_LENGTH or normalized != normalized.lower():
        return None
    return normalized


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def format_attribute_value(value: float | int) -> str:
    """Format an absolute attribute value without turning it into a percentage."""
    numeric = float(value)
    if numeric.is_integer():
        return f"{round(numeric):,}"
    return f"{numeric:,.1f}".rstrip("0").rstrip(".")


def _format_converted_value(value: float, precision: int, display_unit: str) -> str:
    rendered = f"{value:.{precision}f}"
    return f"{rendered}%" if display_unit == "percent" else rendered


def _unavailable(attribute_rule_revision: str, code: str, path: str, message: str) -> dict:
    return {
        "contractRevision": ATTRIBUTE_CALCULATION_CONTRACT_REVISION,
        "status": "rule_unavailable",
        "attributeRuleRevision": attribute_rule_revision,
        "primary": None,
        "stamina": None,
        "resources": {},
        "secondary": [],
        "conditionals": [],
        "problems": [_issue(code, path, message)],
        "inputSignature": "",
    }


def _normalize_static_attributes(raw: Any) -> tuple[dict[str, float] | None, dict | None]:
    if not isinstance(raw, dict):
        return None, _issue("INVALID_STATIC_ATTRIBUTES", "staticAttributes", "staticAttributes must be an object")
    normalized: dict[str, float] = {}
    for key, raw_value in raw.items():
        normalized_key = _bounded_key(key)
        value = _number(raw_value)
        if normalized_key is None or value is None:
            return None, _issue("INVALID_STATIC_ATTRIBUTE", f"staticAttributes.{key}", "static attributes require lower-case keys and finite numeric values")
        canonical_key = _STATIC_ATTRIBUTE_ALIASES.get(normalized_key, normalized_key)
        normalized[canonical_key] = normalized.get(canonical_key, 0.0) + value
    return normalized, None


def _normalize_stable_effects(raw: Any) -> tuple[list[str] | None, dict | None]:
    if not isinstance(raw, list):
        return None, _issue("INVALID_STABLE_EFFECTS", "stableEffects", "stableEffects must be a list")
    effect_ids: set[str] = set()
    for index, effect in enumerate(raw):
        if not isinstance(effect, dict):
            return None, _issue("INVALID_STABLE_EFFECT", f"stableEffects[{index}]", "stable effects must be objects")
        effect_id = _bounded_key(effect.get("effectId"))
        if effect_id is None:
            return None, _issue("INVALID_STABLE_EFFECT", f"stableEffects[{index}].effectId", "stable effects require a bounded lower-case effectId")
        effect_ids.add(effect_id)
    return sorted(effect_ids), None


def _normalized_rule_revision(rule: Any) -> str:
    if not isinstance(rule, dict):
        return ""
    revision = rule.get("attributeRuleRevision")
    return revision if isinstance(revision, str) else ""


def _validate_rule_and_character(rule: Any, character_context: Any) -> tuple[dict | None, str, dict | None]:
    revision = _normalized_rule_revision(rule)
    if not isinstance(rule, dict):
        return None, revision, _issue("ATTRIBUTE_RULE_UNAVAILABLE", "rule", "attribute rule is unavailable")
    required_keys = {
        "attributeRuleRevision",
        "contextKey",
        "raceKey",
        "status",
        "primaryKey",
        "baseAttributes",
        "stableModifiers",
        "resources",
        "secondaryRules",
    }
    missing_keys = sorted(required_keys - set(rule))
    if missing_keys:
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", f"rule.{missing_keys[0]}", "attribute rule is incomplete")
    if _bounded_key(rule["attributeRuleRevision"]) is None:
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", "rule.attributeRuleRevision", "attribute rule revision is invalid")
    if rule["status"] not in {"verified", "fixture_only"}:
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", "rule.status", "attribute rule is not usable")
    race_key = _bounded_key(rule["raceKey"])
    primary_key = _bounded_key(rule["primaryKey"])
    if race_key is None or primary_key is None:
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", "rule", "rule identifiers must be bounded lower-case values")
    if not isinstance(character_context, dict) or _bounded_key(character_context.get("raceKey")) != race_key:
        return None, revision, _issue("ATTRIBUTE_RULE_UNAVAILABLE", "characterContext.raceKey", "no attribute rule is available for this race")
    if not isinstance(rule["baseAttributes"], dict) or not isinstance(rule["stableModifiers"], list):
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", "rule", "rule base attributes or modifiers are invalid")
    if not isinstance(rule["resources"], dict) or not isinstance(rule["secondaryRules"], list):
        return None, revision, _issue("INVALID_ATTRIBUTE_RULE", "rule", "rule resources or secondary rules are invalid")
    return rule, revision, None


def _apply_stable_modifiers(
    attributes: dict[str, float], modifiers: list[Any], effect_ids: list[str]
) -> tuple[dict[str, float] | None, list[dict], dict | None]:
    active_effects = set(effect_ids)
    allowed_effects: set[str] = set()
    for index, modifier in enumerate(modifiers):
        path = f"rule.stableModifiers[{index}]"
        if not isinstance(modifier, dict):
            return None, [], _issue("INVALID_STABLE_MODIFIER", path, "stable modifiers must be objects")
        effect_id = _bounded_key(modifier.get("effectId"))
        target_key = _bounded_key(modifier.get("targetKey"))
        operation = modifier.get("operation")
        value = _number(modifier.get("value"))
        if effect_id is None or target_key is None or operation not in {"add", "multiply"} or value is None:
            return None, [], _issue("INVALID_STABLE_MODIFIER", path, "stable modifier requires effectId, targetKey, operation and finite value")
        allowed_effects.add(effect_id)
        if effect_id not in active_effects:
            continue
        current = attributes.get(target_key, 0.0)
        attributes[target_key] = current + value if operation == "add" else current * value

    conditionals = [
        {"effectId": effect_id, "included": False, "reason": "UNSUPPORTED_STABLE_EFFECT"}
        for effect_id in effect_ids
        if effect_id not in allowed_effects
    ]
    return attributes, conditionals, None


def _resource_rows(resources: dict[str, Any], attributes: dict[str, float]) -> tuple[dict | None, dict | None]:
    rows: dict[str, dict] = {}
    for resource_key, definition in resources.items():
        normalized_key = _bounded_key(resource_key)
        path = f"rule.resources.{resource_key}"
        if normalized_key is None or not isinstance(definition, dict):
            return None, _issue("INVALID_RESOURCE_RULE", path, "resource definitions must be keyed objects")
        base = _number(definition.get("base"))
        per_stamina = _number(definition.get("perStamina", 0))
        per_intellect = _number(definition.get("perIntellect", 0))
        rounding = definition.get("round")
        if base is None or per_stamina is None or per_intellect is None or rounding not in {"floor", "ceil", "round"}:
            return None, _issue("INVALID_RESOURCE_RULE", path, "resource definitions require finite base/per-attribute values and a round mode")
        raw_value = base + attributes.get("stamina", 0.0) * per_stamina + attributes.get("intellect", 0.0) * per_intellect
        if rounding == "floor":
            raw_value = float(math.floor(raw_value))
        elif rounding == "ceil":
            raw_value = float(math.ceil(raw_value))
        else:
            raw_value = float(round(raw_value))
        clean_value = _clean_number(raw_value)
        rows[normalized_key] = {"key": normalized_key, "rawValue": clean_value, "value": format_attribute_value(raw_value)}
    return rows, None


def _secondary_rows(secondary_rules: list[Any], attributes: dict[str, float]) -> tuple[list[dict] | None, dict | None]:
    rows: list[dict] = []
    output_keys: set[str] = set()
    for index, definition in enumerate(secondary_rules):
        path = f"rule.secondaryRules[{index}]"
        if not isinstance(definition, dict):
            return None, _issue("INVALID_SECONDARY_RULE", path, "secondary rules must be objects")
        input_key = _bounded_key(definition.get("inputKey"))
        output_key = _bounded_key(definition.get("outputKey"))
        label = definition.get("label")
        base_percent = _number(definition.get("basePercent"))
        rating_per_percent = _number(definition.get("ratingPerPercent"))
        precision = definition.get("precision")
        display_unit = definition.get("displayUnit")
        if input_key is None or output_key is None or not isinstance(label, str) or not label.strip():
            return None, _issue("INVALID_SECONDARY_RULE", path, "secondary rules require input, output and label")
        if output_key in output_keys:
            return None, _issue("DUPLICATE_OUTPUT_KEY", f"{path}.outputKey", "secondary output keys must be unique")
        output_keys.add(output_key)
        if base_percent is None or rating_per_percent is None or rating_per_percent <= 0:
            return None, _issue("INVALID_RATING_CONVERSION", f"{path}.ratingPerPercent", "ratingPerPercent must be a finite number greater than zero")
        if isinstance(precision, bool) or not isinstance(precision, int) or precision < 0 or precision > 6:
            return None, _issue("INVALID_PRECISION", f"{path}.precision", "precision must be an integer from 0 to 6")
        if display_unit not in {"percent", "effect"}:
            return None, _issue("INVALID_DISPLAY_UNIT", f"{path}.displayUnit", "displayUnit must be percent or effect")
        canonical_input_key = _STATIC_ATTRIBUTE_ALIASES.get(input_key, input_key)
        raw_value = attributes.get(canonical_input_key, 0.0)
        converted_value = base_percent + raw_value / rating_per_percent
        rows.append(
            {
                "key": output_key,
                "label": label,
                "rawValue": _clean_number(raw_value),
                "value": format_attribute_value(raw_value),
                "convertedValue": _format_converted_value(converted_value, precision, display_unit),
                "displayUnit": display_unit,
            }
        )
    return rows, None


def _input_signature(rule: dict, race_key: str, static_attributes: dict[str, float], effect_ids: list[str]) -> str:
    payload = {
        "attributeRuleRevision": rule["attributeRuleRevision"],
        "contextKey": rule["contextKey"],
        "raceKey": race_key,
        "staticAttributes": {key: _clean_number(value) for key, value in sorted(static_attributes.items())},
        "stableModifiers": rule["stableModifiers"],
        "stableEffects": effect_ids,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def calculate_noncombat_attributes(
    rule: dict,
    character_context: dict,
    static_attributes: dict,
    stable_effects: list[dict],
) -> dict:
    """Calculate a complete non-combat panel or return no numeric panel at all.

    The caller owns where ``rule``, ``static_attributes`` and ``stable_effects``
    came from.  This function never makes that data more authoritative than it is.
    """
    validated_rule, revision, rule_issue = _validate_rule_and_character(rule, character_context)
    if rule_issue:
        return _unavailable(revision, rule_issue["code"], rule_issue["path"], rule_issue["message"])
    normalized_static, static_issue = _normalize_static_attributes(static_attributes)
    if static_issue:
        return _unavailable(revision, static_issue["code"], static_issue["path"], static_issue["message"])
    effect_ids, effect_issue = _normalize_stable_effects(stable_effects)
    if effect_issue:
        return _unavailable(revision, effect_issue["code"], effect_issue["path"], effect_issue["message"])

    attributes: dict[str, float] = {}
    for key, value in validated_rule["baseAttributes"].items():
        normalized_key = _bounded_key(key)
        numeric_value = _number(value)
        if normalized_key is None or numeric_value is None:
            return _unavailable(revision, "INVALID_BASE_ATTRIBUTE", f"rule.baseAttributes.{key}", "base attributes require lower-case keys and finite numeric values")
        canonical_key = _STATIC_ATTRIBUTE_ALIASES.get(normalized_key, normalized_key)
        attributes[canonical_key] = attributes.get(canonical_key, 0.0) + numeric_value
    for key, value in normalized_static.items():
        attributes[key] = attributes.get(key, 0.0) + value

    attributes, conditionals, modifier_issue = _apply_stable_modifiers(attributes, validated_rule["stableModifiers"], effect_ids)
    if modifier_issue:
        return _unavailable(revision, modifier_issue["code"], modifier_issue["path"], modifier_issue["message"])
    resources, resource_issue = _resource_rows(validated_rule["resources"], attributes)
    if resource_issue:
        return _unavailable(revision, resource_issue["code"], resource_issue["path"], resource_issue["message"])
    secondary, secondary_issue = _secondary_rows(validated_rule["secondaryRules"], attributes)
    if secondary_issue:
        return _unavailable(revision, secondary_issue["code"], secondary_issue["path"], secondary_issue["message"])

    primary_key = _STATIC_ATTRIBUTE_ALIASES.get(validated_rule["primaryKey"], validated_rule["primaryKey"])
    primary_value = attributes.get(primary_key, 0.0)
    stamina_value = attributes.get("stamina", 0.0)
    return {
        "contractRevision": ATTRIBUTE_CALCULATION_CONTRACT_REVISION,
        "status": "calculated",
        "attributeRuleRevision": revision,
        "primary": {"key": primary_key, "rawValue": _clean_number(primary_value), "value": format_attribute_value(primary_value)},
        "stamina": {"key": "stamina", "rawValue": _clean_number(stamina_value), "value": format_attribute_value(stamina_value)},
        "resources": resources,
        "secondary": secondary,
        "conditionals": conditionals,
        "problems": [],
        "inputSignature": _input_signature(validated_rule, validated_rule["raceKey"], normalized_static, effect_ids),
    }
