#!/usr/bin/env python3
"""Pure canonical equipment resolver.

The resolver consumes only a client Selection Intent and a server-owned
Authority Context.  It performs no I/O and deliberately stops at structured
serializer input; profile serialization and simulation execution belong to
later phases.
"""

from __future__ import annotations

from collections import Counter
import json
from typing import Any, Iterable, Mapping

try:
    from . import gear_loadout_effect_authority, gear_socket_authority
    from .gear_enhancement_management import (
        ENHANCEMENT_SIMC_FIELDS,
        GEM_SIMC_SEQUENCE_FIELDS,
        validated_enhancement_management_fields,
    )
    from .gear_contracts import (
        parse_selection_intent,
        resolved_gear_signature,
        selection_signature,
        validate_authority_context,
    )
    from .gear_evidence_ledger import build_evidence_ledger, evidence_claim
    from .gear_result_envelope import gear_problem
    from .gear_rule_matrix import (
        embellishment_usage,
        evaluate_rule_matrix,
        loadout_effect_subjects,
        ordered_rule_matrix,
    )
except ImportError:
    import gear_loadout_effect_authority
    import gear_socket_authority
    from gear_enhancement_management import (
        ENHANCEMENT_SIMC_FIELDS,
        GEM_SIMC_SEQUENCE_FIELDS,
        validated_enhancement_management_fields,
    )
    from gear_contracts import (
        parse_selection_intent,
        resolved_gear_signature,
        selection_signature,
        validate_authority_context,
    )
    from gear_evidence_ledger import build_evidence_ledger, evidence_claim
    from gear_result_envelope import gear_problem
    from gear_rule_matrix import embellishment_usage, evaluate_rule_matrix, ordered_rule_matrix
    from gear_rule_matrix import loadout_effect_subjects


RESOLVED_SNAPSHOT_CONTRACT_REVISION = "gear-resolved-snapshot-v1"
V2_EFFECT_BOUNDARY_SCHEMA_REVISION = "gear-resolver-v2-effect-boundary-v1"
_OPTION_FIELDS = (
    ("gemOptionIds", "gem"),
    ("enchantOptionId", "enchant"),
    ("embellishmentOptionId", "embellishment"),
    ("craftedOptionId", "crafted"),
    ("catalystOptionId", "catalyst"),
)
_GEM_SIMC_SEQUENCE_FIELDS = GEM_SIMC_SEQUENCE_FIELDS
_ENHANCEMENT_SIMC_FIELDS = ENHANCEMENT_SIMC_FIELDS
_CAPABILITY_FIELDS = (
    "socketCount",
    "canEnchant",
    "canEmbellish",
    "allowedGemOptionIds",
    "allowedEnchantOptionIds",
    "allowedEmbellishmentOptionIds",
    "allowedCraftedOptionIds",
    "allowedCatalystOptionIds",
    "requiresCraftedOption",
)


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _ids(values: Iterable[Any]) -> list[str]:
    normalized = {str(value or "").strip() for value in values or []}
    normalized.discard("")
    return sorted(normalized)


def _contract_problem(issue: dict[str, Any]) -> dict[str, Any]:
    return gear_problem(
        issue.get("kind", "AUTHORITY_UNAVAILABLE"),
        issue.get("code", "AUTHORITY_UNAVAILABLE"),
        issue.get("message", "Required resolver input is unavailable."),
        path=issue.get("path", ""),
    )


def _problem(
    kind: str,
    code: str,
    title: str,
    *,
    path: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return gear_problem(kind, code, title, path=path, meta=meta)


def _dedupe_problems(problems: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_value: dict[str, dict[str, Any]] = {}
    for problem in problems:
        key = json.dumps(problem, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        by_value[key] = problem
    return [_canonical(by_value[key]) for key in sorted(by_value)]


def _empty_ledger() -> dict[str, Any]:
    return build_evidence_ledger([], {})


def _empty_snapshot(status: str, problems: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {
        "contractRevision": RESOLVED_SNAPSHOT_CONTRACT_REVISION,
        "status": status,
        "dependencyVector": {},
        "selectionSignature": "",
        "resolvedGearSignature": "",
        "eligibilityContext": {},
        "resolvedSlots": {},
        "ruleResults": [],
        "aggregateLegality": {"status": "blocked", "problemCodes": []},
        "staticAttributes": {},
        "attributeStaticFacts": {"status": "unavailable", "problems": []},
        "setState": {"itemSetCounts": {}, "activeDynamicEffects": []},
        "profileReadiness": {
            "status": "blocked",
            "simcReady": False,
            "requiredSlots": [],
            "readySlots": [],
            "serializerRevision": "",
            "simcRuntimeRevision": "",
            "problems": [],
        },
        "constraints": {"slots": {}},
        "serializerInput": {"gearItems": []},
        "evidenceLedger": _empty_ledger(),
        "problems": _dedupe_problems(problems),
    }


def _stat_map(
    raw: Any,
    *,
    path: str,
    allow_negative: bool = False,
) -> tuple[dict[str, int | float], list[dict[str, Any]]]:
    if raw in (None, {}):
        return {}, []
    if not isinstance(raw, dict):
        return {}, [
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_STATIC_ATTRIBUTES_UNAVAILABLE",
                "Static attribute authority must be an object.",
                path=path,
            )
        ]
    result: dict[str, int | float] = {}
    problems: list[dict[str, Any]] = []
    for key in sorted(raw):
        value = raw[key]
        if (
            not isinstance(key, str)
            or not key
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (not allow_negative and value < 0)
        ):
            problems.append(
                _problem(
                    "AUTHORITY_UNAVAILABLE",
                    "GEAR_STATIC_ATTRIBUTE_INVALID",
                    "Static attribute authority contains an invalid value.",
                    path=f"{path}.{key}",
                )
            )
            continue
        result[key] = value
    return result, problems


def _apply_deltas(
    stats: dict[str, int | float],
    raw_deltas: Any,
    *,
    path: str,
) -> tuple[dict[str, int | float], list[dict[str, Any]]]:
    deltas, problems = _stat_map(raw_deltas, path=path, allow_negative=True)
    updated = dict(stats)
    for key, delta in deltas.items():
        value = updated.get(key, 0) + delta
        if value < 0:
            problems.append(
                _problem(
                    "AUTHORITY_UNAVAILABLE",
                    "GEAR_STATIC_ATTRIBUTE_NEGATIVE",
                    "Static attribute deltas produced a negative final value.",
                    path=f"{path}.{key}",
                )
            )
            continue
        updated[key] = value
    return updated, problems


def resolve_base_item(
    slot: str,
    selection: dict[str, Any],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    """Resolve the catalog base item for one canonical slot."""

    item = authority_context["itemsById"].get(selection["itemId"])
    if not isinstance(item, dict):
        return {
            "item": {},
            "stats": {},
            "sourceRefIds": [],
            "problems": [
                _problem(
                    "ILLEGAL_SELECTION",
                    "GEAR_RELEASE_ITEM_UNKNOWN",
                    "Item is absent from the current authority release.",
                    path=f"slots.{slot}.itemId",
                )
            ],
        }
    stats, problems = _stat_map(
        item.get("baseStats", {}),
        path=f"itemsById.{selection['itemId']}.baseStats",
    )
    return {
        "item": _canonical(item),
        "stats": stats,
        "sourceRefIds": _ids(item.get("sourceRefIds", [])),
        "problems": problems,
    }


def resolve_variant(
    slot: str,
    selection: dict[str, Any],
    base_state: dict[str, Any],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    """Apply only a verified, item-matching catalog variant."""

    state = _canonical(base_state)
    state["variant"] = {}
    variant_key = selection.get("variantKey", "")
    if not variant_key:
        return state
    variant = authority_context["variantsByKey"].get(variant_key)
    if not isinstance(variant, dict):
        state["problems"].append(
            _problem(
                "ILLEGAL_SELECTION",
                "GEAR_RELEASE_VARIANT_UNKNOWN",
                "Variant is absent from the current authority release.",
                path=f"slots.{slot}.variantKey",
            )
        )
        return state
    if variant.get("itemId") != selection["itemId"]:
        state["problems"].append(
            _problem(
                "ILLEGAL_SELECTION",
                "GEAR_RELEASE_VARIANT_ITEM_MISMATCH",
                "Variant does not belong to the selected item.",
                path=f"slots.{slot}.variantKey",
            )
        )
        return state
    if variant.get("status") != "verified":
        state["problems"].append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_VARIANT_UNVERIFIED",
                "Variant authority is not verified.",
                path=f"variantsByKey.{variant_key}.status",
            )
        )
        return state
    state["sourceRefIds"] = _ids(
        state["sourceRefIds"] + list(variant.get("sourceRefIds", []))
    )
    state["variant"] = _canonical(variant)
    if "resolvedStats" not in variant:
        state["problems"].append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_VARIANT_STATS_UNAVAILABLE",
                "Verified variant is missing authoritative resolved static attributes.",
                path=f"variantsByKey.{variant_key}.resolvedStats",
            )
        )
        return state
    variant_stats, problems = _stat_map(
        variant.get("resolvedStats"),
        path=f"variantsByKey.{variant_key}.resolvedStats",
    )
    variant_stats, delta_problems = _apply_deltas(
        variant_stats,
        variant.get("statDeltas", {}),
        path=f"variantsByKey.{variant_key}.statDeltas",
    )
    state["stats"] = variant_stats
    state["problems"].extend(problems + delta_problems)
    return state


def apply_verified_overlay(
    slot: str,
    selection: dict[str, Any],
    variant_state: dict[str, Any],
) -> dict[str, Any]:
    """Apply a present overlay only when its status is explicitly verified."""

    state = _canonical(variant_state)
    state["overlay"] = {}
    overlay = state.get("variant", {}).get("overlay")
    if not isinstance(overlay, dict):
        return state
    if overlay.get("status") != "verified":
        state["problems"].append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_OVERLAY_UNVERIFIED",
                "Variant overlay authority is not verified.",
                path=f"variantsByKey.{selection.get('variantKey', '')}.overlay.status",
            )
        )
        return state
    if not _ids(overlay.get("sourceRefIds", [])):
        state["problems"].append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_OVERLAY_SOURCE_UNAVAILABLE",
                "Verified overlay authority requires immutable source references.",
                path=f"variantsByKey.{selection.get('variantKey', '')}.overlay.sourceRefIds",
            )
        )
        return state
    base_set_id = state.get("item", {}).get("itemSetId") or ""
    overlay_set_id = overlay.get("itemSetId") or ""
    if base_set_id and overlay_set_id and base_set_id != overlay_set_id:
        state["problems"].append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_OVERLAY_SET_IDENTITY_CONFLICT",
                "Base item and verified overlay disagree on canonical item-set identity.",
                path=f"variantsByKey.{selection.get('variantKey', '')}.overlay.itemSetId",
                meta={"baseItemSetId": base_set_id, "overlayItemSetId": overlay_set_id},
            )
        )
        return state
    state["stats"], problems = _apply_deltas(
        state["stats"],
        overlay.get("statDeltas", {}),
        path=f"variantsByKey.{selection.get('variantKey', '')}.overlay.statDeltas",
    )
    state["problems"].extend(problems)
    state["sourceRefIds"] = _ids(
        state["sourceRefIds"] + list(overlay.get("sourceRefIds", []))
    )
    state["overlay"] = _canonical(overlay)
    return state


def derive_effective_capabilities(
    selection: dict[str, Any],
    overlay_state: dict[str, Any],
) -> dict[str, Any]:
    """Derive effective option capabilities after verified overlays."""

    state = _canonical(overlay_state)
    item = state.get("item", {})
    capabilities = dict(item.get("baseCapabilities") or {})
    for field in _CAPABILITY_FIELDS:
        if field in item and field not in capabilities:
            capabilities[field] = item[field]
    variant_overrides = state.get("variant", {}).get("capabilityOverrides")
    if isinstance(variant_overrides, dict):
        capabilities.update(variant_overrides)
    overlay_overrides = state.get("overlay", {}).get("capabilityOverrides")
    if isinstance(overlay_overrides, dict):
        capabilities.update(overlay_overrides)
    capabilities.setdefault("socketCount", 0)
    capabilities.setdefault("canEnchant", False)
    capabilities.setdefault("canEmbellish", False)
    state["effectiveCapabilities"] = _canonical(capabilities)
    return state


def apply_selected_enhancements(
    slot: str,
    selection: dict[str, Any],
    capability_state: dict[str, Any],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    """Apply selected, present enhancement facts in deterministic field order."""

    state = _canonical(capability_state)
    selected_options = {
        "gemOptionIds": list(selection.get("gemOptionIds", [])),
        "enchantOptionId": selection.get("enchantOptionId", ""),
        "embellishmentOptionId": selection.get("embellishmentOptionId", ""),
        "craftedOptionId": selection.get("craftedOptionId", ""),
        "catalystOptionId": selection.get("catalystOptionId", ""),
    }
    simc_options = dict(state.get("variant", {}).get("simcOptions") or {})
    capabilities = state.get("effectiveCapabilities", {})
    capability_revision = authority_context.get("dependencyVector", {}).get("capabilityRevision")
    v2_management = capability_revision == gear_socket_authority.CAPABILITY_REVISION
    management = state.get("variant", {}).get("enhancementManagement")
    classifications = validated_enhancement_management_fields(
        simc_options,
        management,
        capability_revision,
    )
    if v2_management:
        for simc_field in _ENHANCEMENT_SIMC_FIELDS:
            if classifications.get(simc_field) != "source_only":
                simc_options.pop(simc_field, None)
    replaces_variant_gem_sequences = bool(selected_options["gemOptionIds"])
    selected_gem_sequences: dict[str, list[str]] = {
        field: [] for field in _GEM_SIMC_SEQUENCE_FIELDS
    }
    applied_gem_count = 0
    if replaces_variant_gem_sequences:
        for field in _GEM_SIMC_SEQUENCE_FIELDS:
            simc_options.pop(field, None)
    applied: list[dict[str, Any]] = []
    for field, expected_type in _OPTION_FIELDS:
        raw_ids = selected_options[field]
        option_ids = raw_ids if isinstance(raw_ids, list) else [raw_ids]
        for index, option_id in enumerate(option_ids):
            if not option_id:
                continue
            option = authority_context["optionsById"].get(option_id)
            path = f"slots.{slot}.{field}" + (f".{index}" if isinstance(raw_ids, list) else "")
            if not isinstance(option, dict):
                continue
            option_type = option.get("optionType")
            if expected_type == "enchant":
                type_matches = option_type in {"enchant", "runeforge"}
            else:
                type_matches = option_type == expected_type
            if not type_matches:
                continue
            if expected_type == "gem":
                allowed = option_id in capabilities.get("allowedGemOptionIds", [])
                capacity = capabilities.get("socketCount")
                allowed = allowed and isinstance(capacity, int) and index < capacity
            elif expected_type == "enchant":
                allowed = (
                    capabilities.get("canEnchant") is True
                    and option_id in capabilities.get("allowedEnchantOptionIds", [])
                )
            elif expected_type == "embellishment":
                allowed = (
                    capabilities.get("canEmbellish") is True
                    and option_id in capabilities.get("allowedEmbellishmentOptionIds", [])
                )
            elif expected_type == "crafted":
                allowed = option_id in capabilities.get("allowedCraftedOptionIds", [])
            else:
                catalyst = authority_context.get("capabilities", {}).get("catalyst", {})
                allowed = (
                    catalyst.get("enabled") is True
                    and option_id in capabilities.get("allowedCatalystOptionIds", [])
                )
            if not allowed:
                continue
            state["stats"], problems = _apply_deltas(
                state["stats"], option.get("statDeltas", {}), path=f"optionsById.{option_id}.statDeltas"
            )
            state["problems"].extend(problems)
            state["sourceRefIds"] = _ids(
                state["sourceRefIds"] + list(option.get("sourceRefIds", []))
            )
            option_simc_options = option.get("simcOptions") or {}
            if expected_type == "gem" and replaces_variant_gem_sequences:
                applied_gem_count += 1
                for simc_field in _GEM_SIMC_SEQUENCE_FIELDS:
                    value = str(option_simc_options.get(simc_field) or "").strip()
                    if value:
                        selected_gem_sequences[simc_field].append(value)
                simc_options.update(
                    {
                        key: value
                        for key, value in option_simc_options.items()
                        if key not in _GEM_SIMC_SEQUENCE_FIELDS
                    }
                )
            else:
                simc_options.update(option_simc_options)
            applied.append(
                {
                    "field": field,
                    "optionId": option_id,
                    "path": path,
                    "statDeltas": _canonical(option.get("statDeltas", {})),
                }
            )
    if replaces_variant_gem_sequences:
        simc_options.update(
            {
                field: "/".join(values)
                for field, values in selected_gem_sequences.items()
                if applied_gem_count and len(values) == applied_gem_count
            }
        )
    state["selectedOptions"] = selected_options
    state["appliedEnhancements"] = applied
    state["simcOptions"] = _canonical(simc_options)
    return state


def resolve_slot(
    slot: str,
    selection: dict[str, Any],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    """Run the fixed five-stage canonical slot pipeline."""

    state = resolve_base_item(slot, selection, authority_context)
    state = resolve_variant(slot, selection, state, authority_context)
    state = apply_verified_overlay(slot, selection, state)
    state = derive_effective_capabilities(selection, state)
    item_static_stats = _canonical(state["stats"])
    state = apply_selected_enhancements(slot, selection, state, authority_context)
    item = state.get("item", {})
    variant = state.get("variant", {})
    overlay = state.get("overlay", {})
    item_set_id = overlay.get("itemSetId") or item.get("itemSetId") or ""
    dynamic_effects = []
    for owner in (item, variant, overlay):
        if isinstance(owner.get("dynamicEffects"), list):
            dynamic_effects.extend(owner["dynamicEffects"])
    return {
        "slot": slot,
        "itemId": selection["itemId"],
        "variantKey": selection.get("variantKey", ""),
        "itemLevel": variant.get("itemLevel"),
        "displayName": item.get("displayName", ""),
        "inventoryType": item.get("inventoryType", ""),
        "handedness": item.get("handedness", ""),
        "itemSetId": item_set_id,
        "overlayId": overlay.get("overlayId", ""),
        "resolutionStages": ["base", "variant", "overlay", "capabilities", "enhancements"],
        "itemStaticStats": item_static_stats,
        "resolvedStats": _canonical(state["stats"]),
        "statDeltas": {
            "variant": _canonical(variant.get("statDeltas", {})),
            "overlay": _canonical(overlay.get("statDeltas", {})),
            "enhancements": [
                {
                    "optionId": enhancement["optionId"],
                    "statDeltas": enhancement["statDeltas"],
                }
                for enhancement in state["appliedEnhancements"]
            ],
        },
        "effectiveCapabilities": _canonical(state["effectiveCapabilities"]),
        "selectedOptions": _canonical(state["selectedOptions"]),
        "simcOptions": _canonical(state["simcOptions"]),
        "dynamicEffects": _canonical(dynamic_effects),
        "sourceRefIds": _ids(state["sourceRefIds"]),
        "legality": {
            "status": "blocked" if state["problems"] else "verified",
            "problemCodes": sorted({problem["code"] for problem in state["problems"]}),
        },
        "evidenceClaimIds": [],
        "problems": _dedupe_problems(state["problems"]),
    }


def _set_state(
    resolved_slots: dict[str, dict[str, Any]],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    counts = Counter(
        slot["itemSetId"] for slot in resolved_slots.values() if slot.get("itemSetId")
    )
    effects: list[dict[str, Any]] = []
    inputs = authority_context["ruleParameters"].get("setAggregationInputs", [])
    for aggregate in inputs:
        if not isinstance(aggregate, dict):
            continue
        set_id = aggregate.get("itemSetId")
        if not set_id:
            continue
        for threshold in aggregate.get("thresholds", []):
            pieces = threshold.get("pieces") if isinstance(threshold, dict) else None
            effect_id = threshold.get("effectId") if isinstance(threshold, dict) else None
            if isinstance(pieces, int) and pieces > 0 and effect_id and counts[set_id] >= pieces:
                effect = {
                    "effectId": effect_id,
                    "itemSetId": set_id,
                    "pieces": pieces,
                    "sourceRefIds": _ids(threshold.get("sourceRefIds", [])),
                }
                if "subjectKind" in threshold:
                    effect["subjectKind"] = threshold["subjectKind"]
                effects.append(effect)
    return {
        "itemSetCounts": {key: counts[key] for key in sorted(counts)},
        "activeDynamicEffects": sorted(
            effects, key=lambda effect: (effect["itemSetId"], effect["pieces"], effect["effectId"])
        ),
    }


def _static_attributes(resolved_slots: dict[str, dict[str, Any]]) -> dict[str, int | float]:
    totals: dict[str, int | float] = {}
    for slot in sorted(resolved_slots):
        for key, value in resolved_slots[slot]["resolvedStats"].items():
            totals[key] = totals.get(key, 0) + value
    return {key: totals[key] for key in sorted(totals)}


def _attribute_static_facts(
    resolved_slots: dict[str, dict[str, Any]],
    authority_context: dict[str, Any],
) -> dict[str, Any]:
    """Report whether selected enhancements have explicit attribute facts.

    Resolver legality and SimC serialization remain usable when a selected
    option has no numeric stat delta.  The real-time character panel needs the
    stricter answer: an absent fact is not equivalent to a zero stat delta.
    """

    options = authority_context.get("optionsById", {})
    problems: list[dict[str, Any]] = []
    for slot in sorted(resolved_slots):
        stat_deltas = resolved_slots[slot].get("statDeltas", {})
        enhancements = stat_deltas.get("enhancements", []) if isinstance(stat_deltas, dict) else []
        for enhancement in enhancements:
            if not isinstance(enhancement, dict):
                continue
            option_id = enhancement.get("optionId")
            option = options.get(option_id) if isinstance(options, dict) else None
            if not isinstance(option, dict):
                continue
            status = option.get("attributeStaticFactsStatus")
            if not isinstance(status, str):
                status = "verified" if "statDeltas" in option else "unavailable"
            if status in {"verified", "not_applicable"}:
                continue
            problems.append(
                _problem(
                    "AUTHORITY_UNAVAILABLE",
                    "ATTRIBUTE_STATIC_FACTS_UNAVAILABLE",
                    "Selected enhancement is missing canonical static attribute facts.",
                    path=f"optionsById.{option_id}.attributeStaticFactsStatus",
                    meta={"slot": slot, "optionId": option_id},
                )
            )
    return {
        "status": "verified" if not problems else "unavailable",
        "problems": _dedupe_problems(problems),
    }


def _constraints(
    resolved_slots: dict[str, dict[str, Any]],
    authority_context: dict[str, Any],
    selection_intent: dict[str, Any],
) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    for slot in sorted(resolved_slots):
        resolved = resolved_slots[slot]
        capabilities = resolved["effectiveCapabilities"]
        socket_count = capabilities.get("socketCount", 0)
        gem_count = len(resolved["selectedOptions"]["gemOptionIds"])
        slots[slot] = {
            "socketCount": socket_count,
            "socketRemaining": max(0, socket_count - gem_count) if isinstance(socket_count, int) else 0,
            "canEnchant": capabilities.get("canEnchant") is True,
            "hasSelectedEnchant": bool(resolved["selectedOptions"]["enchantOptionId"]),
            "canEmbellish": capabilities.get("canEmbellish") is True,
            "hasSelectedEmbellishment": bool(resolved["selectedOptions"]["embellishmentOptionId"]),
        }
    usage = embellishment_usage(selection_intent, authority_context)
    constraints = {
        "slots": slots,
        "embellishmentBuiltInUsed": usage["builtIn"],
        "embellishmentSelectedUsed": usage["selected"],
        "embellishmentUsed": usage["used"],
    }
    embellishment_limit = authority_context["ruleParameters"].get("embellishmentLimit")
    if (
        isinstance(embellishment_limit, int)
        and not isinstance(embellishment_limit, bool)
        and embellishment_limit >= 0
    ):
        constraints["embellishmentMax"] = embellishment_limit
    return constraints


def _profile_readiness(
    resolved_slots: dict[str, dict[str, Any]],
    authority_context: dict[str, Any],
    selection_intent: dict[str, Any],
    problems: list[dict[str, Any]],
) -> dict[str, Any]:
    vector = authority_context["dependencyVector"]
    parameters = authority_context["ruleParameters"]
    required = list(parameters.get("requiredSlots", []))
    main_hand = resolved_slots.get("main_hand", {})
    eligibility = selection_intent["eligibilityContext"]
    requested_spec = f"{eligibility['classKey']}:{eligibility['specKey']}"
    weapon_mode = parameters.get("weaponModesByClassSpec", {}).get(requested_spec)
    if main_hand.get("handedness") == "ranged" or (
        main_hand.get("handedness") == "two_hand" and weapon_mode != "dual_wield_2h"
    ):
        required = [slot for slot in required if slot != "off_hand"]
    required = sorted(set(required))
    ready = sorted(slot for slot in required if slot in resolved_slots and not resolved_slots[slot]["problems"])
    serializer = authority_context["capabilities"].get("serializer", {})
    serializer_revision = vector.get("serializerRevision", "")
    simc_revision = vector.get("simcRuntimeRevision", "")
    readiness_problems = list(problems)
    if serializer.get("enabled") is not True or serializer.get("revision") != serializer_revision:
        readiness_problems.append(
            _problem(
                "AUTHORITY_UNAVAILABLE",
                "GEAR_SERIALIZER_CAPABILITY_BLOCKED",
                "Structured gear cannot be serialized by the current capability.",
                path="capabilities.serializer",
            )
        )
    if not simc_revision:
        readiness_problems.append(
            _problem(
                "SIMC_UNAVAILABLE",
                "GEAR_SIMC_RUNTIME_UNAVAILABLE",
                "SimulationCraft runtime revision is unavailable.",
                path="dependencyVector.simcRuntimeRevision",
            )
        )
    if ready != required:
        readiness_problems.append(
            _problem(
                "ILLEGAL_SELECTION",
                "GEAR_REQUIRED_SLOTS_INCOMPLETE",
                "Required legal equipment slots are incomplete.",
                meta={"requiredSlots": required, "readySlots": ready},
            )
        )
    readiness_problems = _dedupe_problems(readiness_problems)
    simc_ready = not readiness_problems
    return {
        "status": "verified" if simc_ready else "blocked",
        "simcReady": simc_ready,
        "requiredSlots": required,
        "readySlots": ready,
        "serializerRevision": serializer_revision,
        "simcRuntimeRevision": simc_revision,
        "problems": readiness_problems,
    }


def _missing_evidence_problems(
    source_ref_ids: Iterable[str],
    evidence_records_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    problems = []
    for source_id in _ids(source_ref_ids):
        record = evidence_records_by_id.get(source_id)
        if not isinstance(record, dict) or record.get("id") not in (None, "", source_id):
            problems.append(
                _problem(
                    "AUTHORITY_UNAVAILABLE",
                    "EVIDENCE_RECORD_MISSING",
                    "Required evidence record is unavailable.",
                    path=f"evidenceRecordsById.{source_id}",
                    meta={"sourceRefId": source_id},
                )
            )
    return problems


def _claims(
    resolved_slots: dict[str, dict[str, Any]],
    rule_results: list[dict[str, Any]],
    static_attributes: dict[str, Any],
    set_state: dict[str, Any],
    readiness: dict[str, Any],
    authority_context: dict[str, Any],
    resolved_signature: str,
) -> list[dict[str, Any]]:
    vector = authority_context["dependencyVector"]
    rule_revision = vector["gearRuleRevision"]
    records = authority_context["evidenceRecordsById"]
    claims: list[dict[str, Any]] = []
    identity_ids: list[str] = []
    provenance_ids: list[str] = []
    static_ids: list[str] = []
    for slot in sorted(resolved_slots):
        resolved = resolved_slots[slot]
        sources = resolved["sourceRefIds"]
        missing = _missing_evidence_problems(sources, records)
        status = "blocked" if resolved["problems"] or missing else "verified"
        identity = evidence_claim(
            "identity_options",
            f"slot:{slot}:identity_options",
            {
                "itemId": resolved["itemId"],
                "variantKey": resolved["variantKey"],
                "selectedOptions": resolved["selectedOptions"],
            },
            status=status,
            source_ref_ids=sources,
            rule_revision=rule_revision,
            resolved_signature=resolved_signature,
            dependency_vector=vector,
            problems=resolved["problems"] + missing,
        )
        provenance = evidence_claim(
            "provenance",
            f"slot:{slot}:provenance",
            {"resolutionStages": resolved["resolutionStages"], "sourceRefIds": sources},
            status=status,
            source_ref_ids=sources,
            rule_revision=rule_revision,
            resolved_signature=resolved_signature,
            dependency_vector=vector,
            problems=resolved["problems"] + missing,
        )
        static = evidence_claim(
            "static_attributes",
            f"slot:{slot}:static_attributes",
            resolved["resolvedStats"],
            status=status,
            source_ref_ids=sources,
            rule_revision=rule_revision,
            resolved_signature=resolved_signature,
            dependency_vector=vector,
            problems=resolved["problems"] + missing,
        )
        claims.extend((identity, provenance, static))
        identity_ids.append(identity["claimId"])
        provenance_ids.append(provenance["claimId"])
        static_ids.append(static["claimId"])

    rule_sources = _ids(authority_context["ruleParameters"].get("sourceRefIds", []))
    rule_claim_ids: list[str] = []
    for result in rule_results:
        missing = _missing_evidence_problems(rule_sources, records)
        status = "blocked" if result["problems"] or missing else "verified"
        claim = evidence_claim(
            "legality",
            f"rule:{result['ruleId']}",
            {"order": result["order"], "status": result["status"]},
            status=status,
            source_ref_ids=rule_sources,
            rule_revision=rule_revision,
            resolved_signature=resolved_signature,
            dependency_vector=vector,
            problems=result["problems"] + missing,
        )
        claims.append(claim)
        rule_claim_ids.append(claim["claimId"])

    legal = all(result["status"] == "verified" for result in rule_results)
    aggregate_legality = evidence_claim(
        "legality",
        "aggregate:legality",
        {"legal": legal},
        status="verified" if legal else "blocked",
        source_ref_ids=rule_sources,
        rule_revision=rule_revision,
        resolved_signature=resolved_signature,
        dependency_vector=vector,
        depends_on=rule_claim_ids,
    )
    claims.append(aggregate_legality)

    set_sources = _ids(
        source
        for effect in set_state["activeDynamicEffects"]
        for source in effect.get("sourceRefIds", [])
    )
    set_missing = _missing_evidence_problems(set_sources, records)
    aggregate_set = evidence_claim(
        "provenance",
        "aggregate:set_state",
        set_state,
        status="blocked" if set_missing else "verified",
        source_ref_ids=set_sources,
        rule_revision=rule_revision,
        resolved_signature=resolved_signature,
        dependency_vector=vector,
        depends_on=provenance_ids,
        problems=set_missing,
    )
    claims.append(aggregate_set)

    aggregate_static = evidence_claim(
        "static_attributes",
        "aggregate:static_attributes",
        static_attributes,
        status="verified" if all(claim["status"] == "verified" for claim in claims if claim["claimId"] in static_ids) else "blocked",
        source_ref_ids=[],
        rule_revision=rule_revision,
        resolved_signature=resolved_signature,
        dependency_vector=vector,
        depends_on=static_ids,
    )
    claims.append(aggregate_static)

    profile_sources = _ids(rule_sources + set_sources)
    aggregate_profile = evidence_claim(
        "profile_executability",
        "aggregate:profile_readiness",
        readiness,
        status="verified" if readiness["simcReady"] else "blocked",
        source_ref_ids=profile_sources,
        rule_revision=rule_revision,
        resolved_signature=resolved_signature,
        dependency_vector=vector,
        depends_on=[aggregate_legality["claimId"], aggregate_static["claimId"]],
        problems=readiness["problems"],
    )
    claims.append(aggregate_profile)
    return claims


def _serializer_input(resolved_slots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "gearItems": [
            {
                "slot": slot,
                "itemId": resolved_slots[slot]["itemId"],
                "variantKey": resolved_slots[slot]["variantKey"],
                "simcOptions": resolved_slots[slot]["simcOptions"],
            }
            for slot in sorted(resolved_slots)
        ]
    }


def resolve(selection_intent: Any, authority_context: Any) -> dict[str, Any]:
    """Resolve a Selection Intent into a deterministic, current-fact snapshot."""

    intent, intent_issues = parse_selection_intent(selection_intent)
    if intent_issues:
        return _empty_snapshot("blocked", [_contract_problem(issue) for issue in intent_issues])

    authority_issues = validate_authority_context(intent, authority_context)
    if authority_issues:
        problems = [_contract_problem(issue) for issue in authority_issues]
        status = "unavailable" if any(problem["kind"] == "AUTHORITY_UNAVAILABLE" for problem in problems) else "blocked"
        return _empty_snapshot(status, problems)

    selection_sig = selection_signature(intent, intent["eligibilityContext"])
    resolved_sig = resolved_gear_signature(selection_sig, authority_context["dependencyVector"])
    resolved_slots = {
        slot: resolve_slot(slot, intent["slots"][slot], authority_context)
        for slot in sorted(intent["slots"])
    }

    matrix = evaluate_rule_matrix(intent, authority_context)
    order_by_id = {rule.rule_id: rule.order for rule in ordered_rule_matrix()}
    rule_results = [
        {**_canonical(result), "order": order_by_id[result["ruleId"]]}
        for result in matrix["results"]
    ]
    resolution_problems = [
        problem for resolved in resolved_slots.values() for problem in resolved["problems"]
    ]
    problems = _dedupe_problems(list(matrix["problems"]) + resolution_problems)
    for slot, resolved in resolved_slots.items():
        slot_prefix = f"slots.{slot}"
        slot_rule_problems = [
            problem
            for problem in matrix["problems"]
            if problem.get("path", "").startswith(slot_prefix)
        ]
        slot_problems = _dedupe_problems(resolved["problems"] + slot_rule_problems)
        resolved["legality"] = {
            "status": "blocked" if slot_problems else "verified",
            "problemCodes": sorted({problem["code"] for problem in slot_problems}),
        }

    static_attributes = _static_attributes(resolved_slots)
    attribute_static_facts = _attribute_static_facts(resolved_slots, authority_context)
    set_state = _set_state(resolved_slots, authority_context)
    all_sources = [
        source for resolved in resolved_slots.values() for source in resolved["sourceRefIds"]
    ] + [
        source
        for effect in set_state["activeDynamicEffects"]
        for source in effect.get("sourceRefIds", [])
    ] + list(authority_context["ruleParameters"].get("sourceRefIds", []))
    evidence_problems = _missing_evidence_problems(
        all_sources, authority_context["evidenceRecordsById"]
    )
    problems = _dedupe_problems(problems + evidence_problems)
    readiness = _profile_readiness(resolved_slots, authority_context, intent, problems)
    claims = _claims(
        resolved_slots,
        rule_results,
        static_attributes,
        set_state,
        readiness,
        authority_context,
        resolved_sig,
    )
    ledger = build_evidence_ledger(claims, authority_context["evidenceRecordsById"])
    for slot, resolved in resolved_slots.items():
        prefix = f"slot:{slot}:"
        resolved["evidenceClaimIds"] = sorted(
            claim["claimId"]
            for claim in ledger["claims"]
            if claim["claimKey"].startswith(prefix)
        )
    problems = _dedupe_problems(problems + ledger["problems"] + readiness["problems"])
    if problems and readiness["simcReady"]:
        readiness = _profile_readiness(resolved_slots, authority_context, intent, problems)

    aggregate_legality = {
        "status": "verified" if not matrix["problems"] else "blocked",
        "problemCodes": sorted({problem["code"] for problem in matrix["problems"]}),
    }
    return {
        "contractRevision": RESOLVED_SNAPSHOT_CONTRACT_REVISION,
        "status": "verified" if not problems and readiness["simcReady"] else "blocked",
        "dependencyVector": _canonical(authority_context["dependencyVector"]),
        "selectionSignature": selection_sig,
        "resolvedGearSignature": resolved_sig,
        "eligibilityContext": _canonical(intent["eligibilityContext"]),
        "resolvedSlots": _canonical(resolved_slots),
        "ruleResults": _canonical(rule_results),
        "aggregateLegality": aggregate_legality,
        "staticAttributes": static_attributes,
        "attributeStaticFacts": attribute_static_facts,
        "setState": set_state,
        "profileReadiness": readiness,
        "constraints": _constraints(resolved_slots, authority_context, intent),
        "serializerInput": _serializer_input(resolved_slots),
        "evidenceLedger": ledger,
        "problems": problems,
    }


def resolve_v2(
    selection_intent: Any,
    authority_context: Any,
    *,
    loadout_effect_authority: Any = None,
) -> dict[str, Any]:
    """Apply the existing complete rule matrix, then fail closed on Task 4L work.

    V2 cannot manufacture a loadout-scoped effect aggregate from slot records.
    It therefore exposes the same legality result while retaining the literal
    blocking reason until a separately reviewed authority owner exists.
    """
    result = resolve(selection_intent, authority_context)
    subjects = loadout_effect_subjects(
        selection_intent,
        authority_context,
        effective_set_state=result.get("setState"),
    )
    set_state = result.get("setState")
    active_effects = (
        set_state.get("activeDynamicEffects")
        if isinstance(set_state, Mapping)
        else None
    )
    if not subjects and active_effects == []:
        return {
            **result,
            "loadoutEffectSubjects": [],
            "v2EffectBoundary": _v2_effect_boundary(result, []),
        }
    required_problem = gear_problem(
        "AUTHORITY_UNAVAILABLE",
        "LOADOUT_EFFECT_AUTHORITY_REQUIRED",
        "Loadout-scoped effects require the Task 4L authority aggregate.",
        path="ruleMatrix.loadoutEffectSubjects",
        meta={"subjects": subjects},
    )
    blocked = _v2_blocked_for_effect(
        result,
        subjects,
        required_problem,
    )
    if not subjects:
        return blocked
    authority_payload = _verified_loadout_effect_authority(
        loadout_effect_authority,
        resolver_snapshot=blocked,
    )
    if authority_payload is None:
        return blocked
    payload, authority_key = authority_payload
    if payload.get("status") == "unsupported":
        unsupported_problem = gear_problem(
            "SIMC_UNAVAILABLE",
            "LOADOUT_EFFECT_UNSUPPORTED",
            "Loadout-scoped effects are unsupported by the governed SimC runtime.",
            path="ruleMatrix.loadoutEffectSubjects",
            meta={"subjects": subjects},
        )
        return _v2_blocked_for_effect(
            result,
            subjects,
            unsupported_problem,
        )
    ready = {
        **result,
        "loadoutEffectSubjects": subjects,
    }
    return {
        **ready,
        "v2EffectBoundary": _v2_effect_boundary(
            ready,
            subjects,
            loadout_effect_authority_verified=True,
            loadout_effect_authority_key=authority_key,
        ),
    }


def _v2_blocked_for_effect(
    result: Mapping[str, Any],
    subjects: list[dict[str, str]],
    problem: Mapping[str, Any],
) -> dict[str, Any]:
    problems = _dedupe_problems(list(result.get("problems", [])) + [problem])
    readiness = _canonical(result.get("profileReadiness") or {})
    readiness.update({"status": "blocked", "simcReady": False, "problems": _dedupe_problems(list(readiness.get("problems", [])) + [problem])})
    blocked = {
        **result,
        "status": "blocked",
        "profileReadiness": readiness,
        "problems": problems,
        "problemCodes": sorted({problem["code"] for problem in problems if problem.get("code")}),
        "loadoutEffectSubjects": subjects,
    }
    return {**blocked, "v2EffectBoundary": _v2_effect_boundary(blocked, subjects)}


def _verified_loadout_effect_authority(
    value: Any,
    *,
    resolver_snapshot: Mapping[str, Any],
) -> tuple[dict[str, Any], str] | None:
    """Reload one owner-sealed aggregate; Resolver never builds or guesses it."""
    try:
        if not gear_loadout_effect_authority.verify_loadout_effect_authority(
            value,
            resolver_snapshot=resolver_snapshot,
        ):
            return None
        reloaded = gear_loadout_effect_authority.reload_loadout_effect_authority(
            value.canonical_bytes,
            value.content_key,
            resolver_snapshot=resolver_snapshot,
        )
        payload = json.loads(reloaded.canonical_bytes)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("status") not in {
        "verified", "unsupported",
    }:
        return None
    return payload, reloaded.content_key


def _v2_effect_boundary(
    result: Mapping[str, Any],
    subjects: list[dict[str, str]],
    *,
    loadout_effect_authority_verified: bool = False,
    loadout_effect_authority_key: str = "",
) -> dict[str, Any]:
    """Bind v2 promotion to the Resolver's effective loadout effect state."""
    dependency = (
        result.get("dependencyVector")
        if isinstance(result.get("dependencyVector"), Mapping)
        else {}
    )
    set_state = result.get("setState") if isinstance(result.get("setState"), Mapping) else {}
    active_effects = set_state.get("activeDynamicEffects") if isinstance(set_state, Mapping) else None
    clean = (
        result.get("status") == "verified"
        and (
            (not subjects and active_effects == [])
            or (
                bool(subjects)
                and loadout_effect_authority_verified
                and bool(loadout_effect_authority_key)
            )
        )
    )
    boundary = {
        "schemaRevision": V2_EFFECT_BOUNDARY_SCHEMA_REVISION,
        "status": "verified" if clean else "blocked",
        "resolvedGearSignature": result.get("resolvedGearSignature"),
        "setState": _canonical(set_state),
        "subjects": _canonical(subjects),
        "gearRuleRevision": dependency.get("gearRuleRevision"),
        "resolverRevision": dependency.get("resolverContractRevision"),
        "simcRuntimeRevision": dependency.get("simcRuntimeRevision"),
    }
    if clean and subjects:
        boundary["loadoutEffectAuthorityKey"] = loadout_effect_authority_key
    return boundary


__all__ = (
    "resolve",
    "resolve_v2",
    "V2_EFFECT_BOUNDARY_SCHEMA_REVISION",
    "resolve_base_item",
    "resolve_variant",
    "apply_verified_overlay",
    "derive_effective_capabilities",
    "apply_selected_enhancements",
    "resolve_slot",
)
