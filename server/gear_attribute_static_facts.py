#!/usr/bin/env python3
"""Versioned, structured-only static facts for gear enhancement options.

These facts are a narrow bridge for existing catalog rows that contain a
structured SimulationCraft option identifier but predate persisted
``statDeltas``.  Display strings are deliberately not an input: an unknown or
ambiguous identifier remains unavailable for the Resolver downgrade path.
"""

from __future__ import annotations

import copy
from typing import Any


STATIC_FACT_RULE_REVISION = "midnight-option-static-facts-r1"

_OPTION_STATIC_FACTS = {
    ("gem", "240892"): {
        "status": "verified",
        "statDeltas": {"haste_rating": 16, "mastery_rating": 7},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-gem-240892",
    },
    ("gem", "240908"): {
        "status": "verified",
        "statDeltas": {"crit_rating": 16, "mastery_rating": 7},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-gem-240908",
    },
    ("gem", "240914"): {
        "status": "verified",
        "statDeltas": {"crit_rating": 7, "versatility_rating": 16},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-gem-240914",
    },
    ("gem", "240983"): {
        "status": "verified",
        "statDeltas": {},
        "primaryStatDelta": 32,
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-gem-240983",
    },
    ("enchant", "4223"): {
        "status": "not_applicable",
        "statDeltas": {},
        "effectClassification": "conditional",
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-4223",
    },
    ("enchant", "4897"): {
        "status": "not_applicable",
        "statDeltas": {},
        "effectClassification": "conditional",
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-4897",
    },
    ("enchant", "8017"): {
        "status": "verified",
        "statDeltas": {"avoidance_rating": 37},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-8017",
    },
    ("enchant", "7935"): {
        "status": "verified",
        "statDeltas": {"stamina": 115},
        "primaryStatDelta": 41,
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-7935",
    },
    ("enchant", "7963"): {
        "status": "verified",
        "statDeltas": {"avoidance_rating": 19, "stamina": 232},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-7963",
    },
    ("enchant", "7967"): {
        "status": "not_applicable",
        "statDeltas": {},
        "effectClassification": "non_panel",
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-7967",
    },
    ("enchant", "7987"): {
        "status": "verified",
        "statDeltas": {},
        "primaryStatDelta": 50,
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-7987",
    },
    ("enchant", "8001"): {
        "status": "verified",
        "statDeltas": {"avoidance_rating": 111},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-8001",
    },
    ("enchant", "8031"): {
        "status": "verified",
        "statDeltas": {"leech_rating": 166},
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-8031",
    },
    ("enchant", "8039"): {
        "status": "not_applicable",
        "statDeltas": {},
        "effectClassification": "conditional",
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-8039",
    },
    ("enchant", "8041"): {
        "status": "not_applicable",
        "statDeltas": {},
        "effectClassification": "conditional",
        "sourceRef": "simc-dbc-12.0.7.68453:midnight-enchant-8041",
    },
}


def option_static_facts(
    option_type: Any,
    simc_options: Any,
    eligibility_context: Any = None,
) -> dict[str, Any] | None:
    """Return canonical static facts for one exact option identity, if known."""

    if not isinstance(option_type, str) or not isinstance(simc_options, dict):
        return None
    identifier_field = {"gem": "gem_id", "enchant": "enchant_id"}.get(option_type)
    identifier = simc_options.get(identifier_field) if identifier_field else None
    if not isinstance(identifier, str) or not identifier.strip():
        return None
    facts = _OPTION_STATIC_FACTS.get((option_type, identifier.strip()))
    if not isinstance(facts, dict):
        return None
    projected = copy.deepcopy(facts)
    primary_delta = projected.pop("primaryStatDelta", None)
    if primary_delta is not None:
        class_key = (
            eligibility_context.get("classKey")
            if isinstance(eligibility_context, dict)
            else None
        )
        primary_key = {"mage": "intellect"}.get(class_key)
        if primary_key is None:
            return None
        projected["statDeltas"][primary_key] = primary_delta
    return projected


__all__ = ("STATIC_FACT_RULE_REVISION", "option_static_facts")
