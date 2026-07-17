#!/usr/bin/env python3
"""Released non-combat attribute rules backed by Armory golden samples.

The module intentionally exposes only contexts whose race, source loadout,
static inputs and Armory output have a verified evidence chain.  It does not
invent a fallback for another race or an incomplete community template.
"""

from __future__ import annotations

from typing import Any

try:  # Supports both package imports and the repository's script entrypoints.
    from .gear_attribute_rules import ATTRIBUTE_RULEBOOK_SCHEMA_REVISION
except ImportError:  # pragma: no cover - exercised by the script smoke check
    from gear_attribute_rules import ATTRIBUTE_RULEBOOK_SCHEMA_REVISION


ATTRIBUTE_RULE_REVISION = "midnight-mage-attributes-r1"
SIMC_DBC_REVISION = "simc-dbc-12.0.7.68453"

_SECONDARY_CURVE = (
    (0, 0),
    (30, 30),
    (40, 39),
    (50, 47),
    (60, 54),
    (80, 66),
    (100, 76),
    (200, 126),
)
_TERTIARY_CURVE = (
    (0, 0),
    (0.5, 0.5),
    (10, 10),
    (15, 14),
    (20, 17),
    (25, 19),
    (100, 49),
)


def _curve(rating_per_percent: float, points: tuple[tuple[float, float], ...]) -> dict[str, Any]:
    return {
        "kind": "piecewise_linear",
        "ratingPerPercent": rating_per_percent,
        "points": [{"input": value, "output": output} for value, output in points],
        "outOfRange": "clamp",
    }


def _secondary_rule(
    input_key: str,
    output_key: str,
    label: str,
    base_percent: float,
    rating_per_percent: float,
    source_ref: str,
    *,
    tertiary: bool = False,
    post_conversion_modifiers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rule = {
        "inputKey": input_key,
        "outputKey": output_key,
        "label": label,
        "basePercent": base_percent,
        "ratingTransform": _curve(
            rating_per_percent,
            _TERTIARY_CURVE if tertiary else _SECONDARY_CURVE,
        ),
        "precision": 6,
        "sourceRefs": [source_ref],
        "displayUnit": "percent",
    }
    if post_conversion_modifiers:
        rule["postConversionModifiers"] = post_conversion_modifiers
    return rule


def _mage_secondary_rules(spec_key: str) -> list[dict[str, Any]]:
    haste_modifiers = [
        {"effectId": "mage:tome_of_antonidas", "operation": "multiply_total", "value": 1.02},
        {
            "effectId": "mage:frost_winters_blessing" if spec_key == "frost" else "mage:arcane_tempo",
            "operation": "multiply_total",
            "value": 1.03 if spec_key == "frost" else 1.02,
        },
    ]
    mastery_modifiers = [
        {"effectId": "mage:charm_of_medivh", "operation": "add", "value": 3},
        {
            "effectId": "mage:frost_mastery" if spec_key == "frost" else "mage:arcane_mastery",
            "operation": "multiply",
            "value": 1.6 if spec_key == "frost" else 1.32,
        },
    ]
    secondary_source = f"{SIMC_DBC_REVISION}:combat-rating-21024"
    tertiary_source = f"{SIMC_DBC_REVISION}:combat-rating-21025"
    mastery_source = f"{SIMC_DBC_REVISION}:spell-1246752" if spec_key == "frost" else f"{SIMC_DBC_REVISION}:spell-190740"
    return [
        _secondary_rule(
            "crit_rating", "crit", "暴击", 5, 46, secondary_source,
            post_conversion_modifiers=[{"effectId": "mage:tome_of_rhonin", "operation": "add", "value": 2}],
        ),
        _secondary_rule("haste_rating", "haste", "急速", 0, 44, secondary_source, post_conversion_modifiers=haste_modifiers),
        _secondary_rule("mastery_rating", "mastery", "精通", 8, 46, mastery_source, post_conversion_modifiers=mastery_modifiers),
        _secondary_rule("versatility_rating", "versatility", "全能", 0, 54, secondary_source),
        _secondary_rule("avoidance_rating", "avoidance", "闪避", 0, 36.80052531, tertiary_source, tertiary=True),
        _secondary_rule("leech_rating", "leech", "吸血", 0, 69.00098495, tertiary_source, tertiary=True),
        _secondary_rule("speed_rating", "speed", "速度", 0, 11.50016416, tertiary_source, tertiary=True),
    ]


def _mage_context(
    spec_key: str,
    race_key: str,
    base_attributes: dict[str, int],
    golden_sample_id: str,
) -> dict[str, Any]:
    stable_modifiers: list[dict[str, Any]] = [
        {"effectId": "mage:arcane_intellect", "targetKey": "intellect", "operation": "add_percent_of_base", "value": 0.03},
        {"effectId": "mage:inspired_intellect", "targetKey": "intellect", "operation": "add_percent_of_base", "value": 0.02},
        {"effectId": "mage:arcane_intellect", "targetKey": "intellect", "operation": "round_nearest", "value": 0},
    ]
    if spec_key == "frost":
        stable_modifiers.extend((
            {"effectId": "mage:frost_winters_blessing", "targetKey": "haste_rating", "operation": "multiply", "value": 1.05},
            {"effectId": "mage:frost_winters_blessing", "targetKey": "haste_rating", "operation": "round_nearest", "value": 0},
        ))
    resources: dict[str, dict[str, Any]] = {
        "health": {"base": 0, "perStamina": 20, "round": "floor"},
        "mana": {"base": 250000, "round": "floor"},
    }
    if spec_key == "arcane":
        resources["mana"] = {
            "base": 250000,
            "percentFromSecondary": "mastery",
            "round": "floor",
        }
    return {
        "contextKey": f"mage:{spec_key}:90:{race_key}",
        "classKey": "mage",
        "specKey": spec_key,
        "level": 90,
        "raceKey": race_key,
        "status": "verified",
        "primaryKey": "intellect",
        "baseAttributes": dict(base_attributes),
        "stableModifiers": stable_modifiers,
        "resources": resources,
        "secondaryRules": _mage_secondary_rules(spec_key),
        "sourceRefs": [
            f"official-armory:{golden_sample_id}",
            f"{SIMC_DBC_REVISION}:mage-{spec_key}-noncombat-rules",
        ],
        "goldenSampleIds": [golden_sample_id],
    }


ACTIVE_ATTRIBUTE_RULEBOOK = {
    "schemaRevision": ATTRIBUTE_RULEBOOK_SCHEMA_REVISION,
    "attributeRuleRevision": ATTRIBUTE_RULE_REVISION,
    "contexts": [
        _mage_context(
            "frost",
            "dwarf",
            {"intellect": 619, "stamina": 4601},
            "mage-frost-armory-2026-07-17t091243z",
        ),
        _mage_context(
            "arcane",
            "night_elf",
            {"intellect": 620, "stamina": 4600},
            "mage-arcane-armory-2026-07-17t041853z",
        ),
    ],
}


__all__ = ("ACTIVE_ATTRIBUTE_RULEBOOK", "ATTRIBUTE_RULE_REVISION", "SIMC_DBC_REVISION")
