#!/usr/bin/env python3
"""Pure projection of one sealed observed community template into canonical gear input."""

from __future__ import annotations

import json
from typing import Any


COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION = "websim-community-template-import-v1"
PUBLIC_OBSERVED_SOURCE_KEY = "raiderio_observed_profile"

_OPTION_FIELDS = (
    ("gemOptionIds", "gem", "gemCount"),
    ("enchantOptionId", "enchant", "enchantCount"),
    ("embellishmentOptionId", "embellishment", "embellishmentCount"),
    ("craftedOptionId", "crafted", "craftedCount"),
    ("catalystOptionId", "catalyst", "catalystCount"),
)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _problem(code: str, title: str, *, retryable: bool = False) -> dict[str, Any]:
    return {"code": code, "title": title, "retryable": retryable}


def community_template_import_problem(code: str, title: str, *, retryable: bool = False) -> dict[str, Any]:
    """Return a bounded public problem without source payload details."""

    return _problem(_text(code), _text(title), retryable=retryable)


def _blocked(problem: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "blocked",
        "template": {},
        "selectedGearBySlot": {},
        "visibleOptionsBySlot": {},
        "selectionIntent": None,
        "unresolvedBySlot": {},
        "warnings": [],
        "problems": [problem],
    }


def _option_is_usable(option: Any, slot: str, expected_type: str) -> bool:
    value = option if isinstance(option, dict) else {}
    applicable_slots = value.get("applicableSlots")
    return (
        bool(_text(value.get("optionKey")))
        and _text(value.get("optionType")) == expected_type
        and _text(value.get("status")) == "verified"
        and value.get("isVisible") is True
        and isinstance(applicable_slots, list)
        and (slot in applicable_slots or "*" in applicable_slots)
    )


def build_community_template_import_source(
    winner: Any,
    variants: Any,
    options: Any,
) -> dict[str, Any]:
    """Build canonical import facts from immutable, already-bound Release rows only."""

    row = winner if isinstance(winner, dict) else {}
    if row.get("role") != "winner" or row.get("sourceKey") != PUBLIC_OBSERVED_SOURCE_KEY:
        return _blocked(_problem("template_not_active", "The requested observed template is not active."))

    class_key = _text(row.get("classKey"))
    spec_key = _text(row.get("specKey"))
    intent = row.get("selectionIntent") if isinstance(row.get("selectionIntent"), dict) else {}
    eligibility = intent.get("eligibilityContext") if isinstance(intent.get("eligibilityContext"), dict) else {}
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    authored = intent.get("authoredAgainst") if isinstance(intent.get("authoredAgainst"), dict) else {}
    if (
        not _text(row.get("templateId"))
        or not class_key
        or not spec_key
        or intent.get("schemaRevision") != "selection-intent-v1"
        or eligibility.get("classKey") != class_key
        or eligibility.get("specKey") != spec_key
        or not isinstance(eligibility.get("level"), int)
        or isinstance(eligibility.get("level"), bool)
        or eligibility.get("level") <= 0
        or not _text(authored.get("seasonRevision"))
        or not _text(authored.get("gearCatalogRevision"))
        or not slots
    ):
        return _blocked(_problem("template_inapplicable", "The active template cannot be imported."))

    variants_by_identity = {
        (_text(value.get("itemId")), _text(value.get("variantKey"))): value
        for value in variants if isinstance(variants, list) and isinstance(value, dict)
        if _text(value.get("itemId")) and _text(value.get("variantKey"))
    }
    options_by_key = {
        _text(value.get("optionKey")): value
        for value in options if isinstance(options, list) and isinstance(value, dict)
        if _text(value.get("optionKey"))
    }

    canonical_slots: dict[str, dict[str, Any]] = {}
    selected_gear_by_slot: dict[str, dict[str, Any]] = {}
    visible_options_by_slot: dict[str, dict[str, dict[str, str]]] = {}
    unresolved_by_slot: dict[str, dict[str, int]] = {}
    warnings: list[dict[str, Any]] = []
    for slot in sorted(slots):
        selection = slots.get(slot)
        if not isinstance(selection, dict) or not _text(slot):
            return _blocked(_problem("template_inapplicable", "The active template contains an invalid slot."))
        item_id = _text(selection.get("itemId"))
        variant_key = _text(selection.get("variantKey"))
        variant = variants_by_identity.get((item_id, variant_key))
        if (
            not isinstance(variant, dict)
            or _text(variant.get("slot")) != slot
            or _text(variant.get("status")) != "verified"
        ):
            return _blocked(_problem("template_inapplicable", "The active template references unavailable gear."))

        canonical_slot = {
            "itemId": item_id,
            "variantKey": variant_key,
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        selected_gear_by_slot[slot] = {
            "variantId": _text(variant.get("id") or variant.get("variantId")),
            "itemId": item_id,
            "variantKey": variant_key,
            "slot": slot,
            "label": _text(variant.get("label")),
            "itemLevel": variant.get("itemLevel") if isinstance(variant.get("itemLevel"), int) else 0,
        }
        slot_visible_options: dict[str, dict[str, str]] = {}
        slot_unresolved: dict[str, int] = {}
        for field, expected_type, count_field in _OPTION_FIELDS:
            raw_values = selection.get(field, [] if field == "gemOptionIds" else "")
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            accepted: list[str] = []
            rejected = 0
            for value in values:
                option_key = _text(value)
                if not option_key:
                    continue
                option = options_by_key.get(option_key)
                if not _option_is_usable(option, slot, expected_type):
                    rejected += 1
                    continue
                accepted.append(option_key)
                slot_visible_options[option_key] = {
                    "optionKey": option_key,
                    "optionType": expected_type,
                    "name": _text(option.get("name")),
                }
            if field == "gemOptionIds":
                canonical_slot[field] = accepted
            elif accepted:
                canonical_slot[field] = accepted[0]
            if rejected:
                slot_unresolved[count_field] = rejected
        canonical_slots[slot] = canonical_slot
        if slot_visible_options:
            visible_options_by_slot[slot] = slot_visible_options
        if slot_unresolved:
            unresolved_by_slot[slot] = slot_unresolved
            warnings.append({"code": "template_import_unresolved", "slot": slot, "counts": slot_unresolved})

    source = {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": "partial" if unresolved_by_slot else "verified",
        "template": {
            "id": _text(row.get("templateId")),
            "classKey": class_key,
            "specKey": spec_key,
            "sourceKey": PUBLIC_OBSERVED_SOURCE_KEY,
            "name": _text((row.get("payload") or {}).get("name")) if isinstance(row.get("payload"), dict) else "",
        },
        "selectedGearBySlot": selected_gear_by_slot,
        "visibleOptionsBySlot": visible_options_by_slot,
        "selectionIntent": {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": _text(authored.get("seasonRevision")),
                "gearCatalogRevision": _text(authored.get("gearCatalogRevision")),
            },
            "eligibilityContext": {
                "classKey": class_key,
                "specKey": spec_key,
                "level": eligibility.get("level"),
            },
            "slots": canonical_slots,
        },
        "unresolvedBySlot": unresolved_by_slot,
        "warnings": warnings,
        "problems": [],
    }
    return _copy(source)


def build_community_template_selection_intent(source: Any) -> dict[str, Any] | None:
    """Return only the projector-built canonical Intent for Resolver consumption."""

    value = source if isinstance(source, dict) else {}
    if value.get("status") not in {"verified", "partial"}:
        return None
    intent = value.get("selectionIntent")
    return _copy(intent) if isinstance(intent, dict) else None


def community_template_import_public_data(
    source: Any,
    resolved_snapshot: Any,
    release_context: Any,
) -> dict[str, Any]:
    """Expose bounded import facts; never serialize the sealed source Intent or rows."""

    value = source if isinstance(source, dict) else {}
    status = value.get("status") if value.get("status") in {"verified", "partial"} else "blocked"
    context = release_context if isinstance(release_context, dict) else {}
    return _copy({
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        "status": status,
        "template": value.get("template") if isinstance(value.get("template"), dict) else {},
        "manifest": {
            "manifestRevision": _text(context.get("manifestRevision")),
            "pointerGeneration": context.get("pointerGeneration") if isinstance(context.get("pointerGeneration"), int) else 0,
        },
        "selectedGearBySlot": value.get("selectedGearBySlot") if isinstance(value.get("selectedGearBySlot"), dict) else {},
        "resolvedSnapshot": resolved_snapshot if isinstance(resolved_snapshot, dict) else {},
        "unresolvedBySlot": value.get("unresolvedBySlot") if isinstance(value.get("unresolvedBySlot"), dict) else {},
        "warnings": value.get("warnings") if isinstance(value.get("warnings"), list) else [],
    })


__all__ = [
    "COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION",
    "PUBLIC_OBSERVED_SOURCE_KEY",
    "build_community_template_import_source",
    "build_community_template_selection_intent",
    "community_template_import_problem",
    "community_template_import_public_data",
]
