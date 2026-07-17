#!/usr/bin/env python3
"""Non-blocking server reference audit for the gear attribute calculator."""

from __future__ import annotations

from typing import Any

try:
    from .gear_attribute_engine import calculate_noncombat_attributes
    from .gear_attribute_rules import (
        applicable_attribute_rule,
        parse_attribute_character_context,
    )
    from .gear_contracts import parse_selection_intent
    from .gear_result_envelope import gear_problem, result_envelope
    from .gear_runtime import resolve_selection_intent
except ImportError:
    from gear_attribute_engine import calculate_noncombat_attributes
    from gear_attribute_rules import applicable_attribute_rule, parse_attribute_character_context
    from gear_contracts import parse_selection_intent
    from gear_result_envelope import gear_problem, result_envelope
    from gear_runtime import resolve_selection_intent


_REQUEST_KEYS = {"selectionIntent", "characterContext"}
_EMPTY_RULEBOOK = {
    "schemaRevision": "gear-attribute-rulebook-v1",
    "attributeRuleRevision": "",
    "contexts": [],
}


def _invalid_attribute_request(
    request_id: str,
    *,
    code: str,
    title: str,
    path: str,
) -> tuple[int, dict[str, Any]]:
    calculation = calculate_noncombat_attributes(None, {}, {}, [])
    envelope = result_envelope(
        "blocked",
        request_id,
        {},
        data={"attributeCalculation": calculation},
        problems=[
            gear_problem(
                "INVALID_INTENT",
                code,
                title,
                path=path,
            )
        ],
    )
    return 400, envelope


def _sealed_stable_effects(snapshot: Any) -> list[dict[str, str]] | None:
    """Pass only resolver-owned stable effect IDs to the pure calculator."""
    source = snapshot.get("stableEffects") if isinstance(snapshot, dict) else None
    if source is None:
        return []
    if not isinstance(source, list):
        return None
    effects = []
    for value in source:
        if not isinstance(value, dict) or set(value) != {"effectId"}:
            return None
        effect_id = value.get("effectId")
        if not isinstance(effect_id, str):
            return None
        effects.append({"effectId": effect_id})
    return effects


def calculate_attributes_for_selection(
    raw_request: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
    rulebook: dict | None = None,
) -> tuple[int, dict[str, Any]]:
    """Resolve gear, then audit the canonical static facts without SimC.

    The optional ``rulebook`` is an in-process injection point for deterministic
    tests and candidate verification. Runtime callers use the empty, fail-closed
    rulebook until a source-ledger-backed production context is published.
    """
    if not isinstance(raw_request, dict) or set(raw_request).difference(_REQUEST_KEYS):
        return _invalid_attribute_request(
            request_id,
            code="ATTRIBUTE_REQUEST_INVALID",
            title="Attribute audit accepts only selectionIntent and characterContext.",
            path="attributeRequest",
        )
    character, character_issues = parse_attribute_character_context(raw_request.get("characterContext"))
    if character_issues:
        return _invalid_attribute_request(
            request_id,
            code="ATTRIBUTE_CHARACTER_CONTEXT_INVALID",
            title="Attribute audit requires an explicit valid character context.",
            path="characterContext",
        )
    intent, intent_issues = parse_selection_intent(raw_request.get("selectionIntent"))
    if intent_issues:
        return _invalid_attribute_request(
            request_id,
            code="ATTRIBUTE_SELECTION_INTENT_INVALID",
            title="Attribute audit requires a valid sealed selection intent.",
            path="selectionIntent",
        )

    status, resolved = resolve_selection_intent(
        intent,
        store=store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
    )
    if status != 200 or not isinstance(resolved, dict) or resolved.get("status") != "resolved":
        return status, resolved

    snapshot = resolved.get("data") if isinstance(resolved.get("data"), dict) else {}
    eligibility = intent["eligibilityContext"]
    active_rule, _ = applicable_attribute_rule(
        rulebook if isinstance(rulebook, dict) else _EMPTY_RULEBOOK,
        class_key=eligibility["classKey"],
        spec_key=eligibility["specKey"],
        level=eligibility["level"],
        race_key=character["raceKey"],
    )
    calculation = calculate_noncombat_attributes(
        active_rule,
        character,
        snapshot.get("staticAttributes"),
        _sealed_stable_effects(snapshot),
    )
    release_context = resolved.get("releaseContext") if isinstance(resolved.get("releaseContext"), dict) else {}
    envelope = result_envelope(
        "resolved",
        request_id,
        release_context,
        data={
            "resolvedGearSignature": str(snapshot.get("resolvedGearSignature") or ""),
            "attributeCalculation": calculation,
        },
        problems=[],
    )
    return 200, envelope
