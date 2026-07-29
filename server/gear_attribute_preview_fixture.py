#!/usr/bin/env python3
"""Candidate-only Armory fixture for an end-to-end attribute preview.

This module is deliberately inert unless ``WOW_ATTRIBUTE_RULEBOOK_PREVIEW=1``.
It never changes the normal community-template catalogue or import path.  The
candidate service can use it to exercise the same client import contract with
one complete, auditable Armory sample while historic observed templates are
still correctly downgraded for incomplete source facts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from .gear_attribute_static_facts import option_static_facts
except ImportError:  # pragma: no cover - script entrypoint compatibility
    from gear_attribute_static_facts import option_static_facts


PREVIEW_ENV = "WOW_ATTRIBUTE_RULEBOOK_PREVIEW"
PREVIEW_TEMPLATE_ID = "candidate-official-armory-mage-frost-dwarf-20260717"
_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "gear-attribute-armory-v1.json"
_REQUIRED_SLOTS = (
    "head", "neck", "shoulder", "back", "chest", "wrist", "hands", "waist",
    "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "main_hand",
)
_PLACEHOLDER_ICON_URL = "https://render.worldofwarcraft.com/us/icons/56/inv_misc_questionmark.jpg"
_PREVIEW_STABLE_EFFECT_IDS = (
    "mage:arcane_intellect",
    "mage:charm_of_medivh",
    "mage:frost_mastery",
    "mage:frost_winters_blessing",
    "mage:inspired_intellect",
    "mage:tome_of_antonidas",
    "mage:tome_of_rhonin",
)


def preview_enabled() -> bool:
    return os.environ.get(PREVIEW_ENV) == "1"


def _fixture_sample() -> dict[str, Any] | None:
    if not preview_enabled() or not _FIXTURE_PATH.is_file():
        return None
    try:
        document = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for sample in document.get("samples", []) if isinstance(document, dict) else []:
        identity = sample.get("identity") if isinstance(sample, dict) else {}
        if (
            isinstance(sample, dict)
            and sample.get("id") == "mage-frost-armory-2026-07-17t091243z"
            and sample.get("status") == "verified"
            and identity.get("classKey") == "mage"
            and identity.get("specKey") == "frost"
            and identity.get("raceKey") == "dwarf"
            and identity.get("level") == 90
        ):
            return sample
    return None


def _official_case() -> dict[str, Any] | None:
    path = _FIXTURE_PATH.with_name("gear-attribute-official-cases-v1.json")
    if not preview_enabled() or not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for case in document.get("cases", []) if isinstance(document, dict) else []:
        if isinstance(case, dict) and case.get("id") == "mage-frost-dwarf-armory-2026-07-17":
            return case
    return None


def _add_stats(total: dict[str, int], values: Any) -> None:
    if not isinstance(values, dict):
        return
    for key, raw_value in values.items():
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            continue
        total[str(key)] = total.get(str(key), 0) + int(raw_value)


def _preview_items(sample: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]] | None:
    items: list[dict[str, Any]] = []
    static_attributes: dict[str, int] = {}
    source_items = sample.get("equipment") if isinstance(sample.get("equipment"), list) else []
    for entry in source_items:
        if not isinstance(entry, dict):
            continue
        slot = str(entry.get("slot") or "").strip()
        if slot not in _REQUIRED_SLOTS:
            continue
        item_id = str(entry.get("itemId") or "").strip()
        variant_key = str(entry.get("variantKey") or "").strip()
        item_level = entry.get("itemLevel")
        if not item_id or not variant_key or not isinstance(item_level, int) or item_level <= 0:
            return None
        item_stats: dict[str, int] = {}
        _add_stats(item_stats, entry.get("stats"))
        for option_type, field, option_key in (
            ("gem", "gemId", "gem_id"),
            ("enchant", "enchantId", "enchant_id"),
        ):
            option_id = str(entry.get(field) or "").strip()
            if not option_id:
                continue
            facts = option_static_facts(
                option_type,
                {option_key: option_id},
                {"classKey": "mage", "specKey": "frost", "level": 90},
            )
            if not isinstance(facts, dict) or facts.get("status") not in {"verified", "not_applicable"}:
                return None
            _add_stats(item_stats, facts.get("statDeltas"))
        _add_stats(static_attributes, item_stats)
        display_name = str(entry.get("name") or f"英雄榜冰法样本 · {slot}")
        items.append({
            "slot": slot,
            "simcSlot": slot,
            "itemId": item_id,
            "id": item_id,
            "variantKey": variant_key,
            "itemLevel": item_level,
            "ilevel": item_level,
            "displayName": display_name,
            "name": display_name,
            "iconUrl": _PLACEHOLDER_ICON_URL,
            "gameAsset": {"status": "verified", "iconUrl": _PLACEHOLDER_ICON_URL},
            "itemStats": [
                {"key": key, "value": value}
                for key, value in sorted(item_stats.items())
                if value
            ],
            "attributeStaticFactsStatus": "verified",
            "simcReady": True,
            "sourceType": "official_armory_fixture",
            "source": "官方英雄榜核验样本",
        })
    if {item["slot"] for item in items} != set(_REQUIRED_SLOTS):
        return None
    return items, static_attributes


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def preview_template_for_payload(payload: Any) -> dict[str, Any] | None:
    """Build the only candidate-only template, or fail closed."""

    source = payload if isinstance(payload, dict) else {}
    if (
        not preview_enabled()
        or source.get("classKey") != "mage"
        or source.get("specKey") != "frost"
        or not str(source.get("manifestRevision") or "").strip()
    ):
        return None
    sample = _fixture_sample()
    case = _official_case()
    if sample is None or case is None:
        return None
    built = _preview_items(sample)
    if built is None:
        return None
    gear_items, static_attributes = built
    expected_static = case.get("staticAttributes") if isinstance(case.get("staticAttributes"), dict) else {}
    if static_attributes != expected_static:
        return None
    identity = sample.get("identity") if isinstance(sample.get("identity"), dict) else {}
    source_url = (sample.get("source") or {}).get("url") if isinstance(sample.get("source"), dict) else ""
    fixture_signature = _fingerprint({"sample": sample.get("id"), "items": gear_items})
    stable_effect_context = {
        "schemaRevision": "gear-attribute-stable-effects-v1",
        "status": "verified",
        "origin": "source_profile",
        "effectIds": list(_PREVIEW_STABLE_EFFECT_IDS),
        "loadoutSignature": _fingerprint({"sample": sample.get("id"), "effects": _PREVIEW_STABLE_EFFECT_IDS}),
    }
    return {
        "id": PREVIEW_TEMPLATE_ID,
        "name": "候选预览 · 官方英雄榜冰法样本",
        "classKey": "mage",
        "specKey": "frost",
        "sourceKey": "candidate_official_armory_fixture",
        "sourceName": "官方英雄榜核验样本（候选预览）",
        "sourceUrl": str(source_url or ""),
        "sourceStatus": "synced",
        "status": "complete",
        "analysisWindow": "候选环境专用：用于核验来源事实完整时的本地属性计算。",
        "readySlotCount": len(_REQUIRED_SLOTS),
        "missingSlots": [],
        "canApplyGear": True,
        "gearItems": gear_items,
        "profileHash": _fingerprint({"identity": identity, "sample": sample.get("id")}),
        "gearHash": fixture_signature,
        "sourceFingerprint": _fingerprint({"sample": sample.get("id"), "capturedAt": (sample.get("source") or {}).get("capturedAt")}),
        "attributeCharacterContext": {
            "schemaRevision": "gear-attribute-character-v1",
            "raceKey": "dwarf",
            "origin": "source_profile",
        },
        "attributeStableEffectContext": stable_effect_context,
        "payload": {
            "attributeCharacterContext": {
                "schemaRevision": "gear-attribute-character-v1",
                "raceKey": "dwarf",
                "origin": "source_profile",
            },
            "attributeStableEffectContext": stable_effect_context,
        },
    }


def append_preview_template(payload: Any) -> dict[str, Any]:
    """Keep the internal fixture out of the public Community template catalogue."""

    return payload if isinstance(payload, dict) else {}


def preview_community_import(
    request: Any,
    payload: Any,
    request_id: str,
) -> tuple[int, dict[str, Any], dict[str, Any]] | None:
    """Return a normal import envelope for the opt-in candidate fixture only."""

    template = preview_template_for_payload(payload)
    raw = request if isinstance(request, dict) else {}
    if template is None or raw.get("templateId") != PREVIEW_TEMPLATE_ID:
        return None
    allowed = {"classKey", "specKey", "templateId", "expectedManifestRevision"}
    manifest_revision = str((payload or {}).get("manifestRevision") or "").strip()
    if (
        set(raw).difference(allowed)
        or raw.get("classKey") != "mage"
        or raw.get("specKey") != "frost"
        or raw.get("expectedManifestRevision") != manifest_revision
    ):
        return None
    gear_items = template["gearItems"]
    resolved_slots = {
        item["slot"]: {
            "itemLevel": item["itemLevel"],
            "selectedOptions": {},
            "legality": {"status": "verified", "problemCodes": []},
        }
        for item in gear_items
    }
    static_attributes = {}
    for item in gear_items:
        for stat in item["itemStats"]:
            static_attributes[stat["key"]] = static_attributes.get(stat["key"], 0) + stat["value"]
    release_context = {
        key: copy.deepcopy((payload or {}).get(key))
        for key in (
            "manifestRevision", "pointerGeneration", "seasonRevision", "gearCatalogRevision",
            "gearRuleRevision", "resolverContractRevision", "serializerRevision",
            "simcRuntimeRevision", "statPolicyRevision", "selectionSchemaRevision",
            "capabilityRevision", "formalActiveManifest",
        )
        if (payload or {}).get(key) not in (None, "")
    }
    snapshot = {
        "contractRevision": "gear-resolved-snapshot-v1",
        "status": "verified",
        "resolvedGearSignature": _fingerprint({"template": template["id"], "gear": template["gearHash"], "manifest": manifest_revision}),
        "staticAttributes": static_attributes,
        "attributeStaticFacts": {"status": "verified", "problems": []},
        "aggregateLegality": {"status": "verified", "problemCodes": []},
        "profileReadiness": {
            "status": "verified", "simcReady": True,
            "requiredSlots": list(_REQUIRED_SLOTS), "readySlots": list(_REQUIRED_SLOTS),
        },
        "constraints": {"embellishmentMax": 2, "embellishmentUsed": 0, "slots": {}},
        "setState": {"itemSetCounts": {}, "activeDynamicEffects": []},
        "resolvedSlots": resolved_slots,
        "problems": [],
    }
    data = {
        "contractRevision": "websim-community-template-import-v2",
        "status": "verified",
        "template": copy.deepcopy(template),
        "manifest": {
            "manifestRevision": manifest_revision,
            "pointerGeneration": release_context.get("pointerGeneration", 0),
        },
        "importedGearBySlot": {item["slot"]: copy.deepcopy(item) for item in gear_items},
        "resolvedSnapshot": snapshot,
    }
    envelope = {
        "contractRevision": "community-template-import-envelope-v1",
        "status": "verified",
        "requestId": str(request_id),
        "releaseContext": release_context,
        "problems": [],
        "data": data,
    }
    return 200, envelope, {
        "queueMs": 0.0,
        "releaseReadMs": 0.0,
        "reconcileMs": 0.0,
        "resolveMs": 0.0,
        "serializeMs": 0.0,
        "cache": "miss",
    }


__all__ = (
    "PREVIEW_ENV",
    "PREVIEW_TEMPLATE_ID",
    "append_preview_template",
    "preview_community_import",
    "preview_enabled",
    "preview_template_for_payload",
)
