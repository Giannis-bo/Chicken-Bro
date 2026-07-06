#!/usr/bin/env python3
import copy

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        SEASON_RECOMMENDED_GEAR_SCENARIO_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        build_websim_gear_lines,
        gear_template_signature,
        gear_template_slot_coverage,
        normalize_source_refs,
        gear_template_source_ref,
        season_expires_at,
        slugify,
        stable_digest,
        utc_now,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_REVISION,
        SEASON_RECOMMENDED_GEAR_SCENARIO_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        build_websim_gear_lines,
        gear_template_signature,
        gear_template_slot_coverage,
        normalize_source_refs,
        gear_template_source_ref,
        season_expires_at,
        slugify,
        stable_digest,
        utc_now,
    )


def season_recommended_role_policy(class_key, spec_key, role=""):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    normalized_role = str(role or "").strip().lower()
    if normalized_role in {"tank", "healer", "support"} or (class_key, spec_key) == ("evoker", "augmentation"):
        return {
            "role": normalized_role or "support",
            "objectiveKey": "community_consensus_plus_simc_sanity",
            "recommendationConfidence": "provisional",
            "reason": "non-DPS specs need role-specific scoring before verified recommendation claims",
        }
    if normalized_role in {"damage", "dps"}:
        return {
            "role": "damage",
            "objectiveKey": "dps_mplus_aoe",
            "recommendationConfidence": "verified",
            "reason": "DPS recommendation is ranked by M+ AOE SimC score",
        }
    return {
        "role": normalized_role or "damage",
        "objectiveKey": "community_consensus_seed",
        "recommendationConfidence": "provisional",
        "reason": "first version uses verified community gear winners as recommendation seeds before SimC optimizer verification",
    }


def _template_id(class_key, spec_key, gear_items, evidence):
    seed = {
        "classKey": class_key,
        "specKey": spec_key,
        "gearItems": [
            {
                "slot": item.get("slot"),
                "itemId": item.get("itemId") or item.get("id"),
                "ilevel": item.get("ilevel") or item.get("itemLevel"),
                "bonus_id": item.get("bonus_id"),
                "gem_id": item.get("gem_id"),
                "enchant_id": item.get("enchant_id"),
                "crafted_stats": item.get("crafted_stats"),
                "embellishment": item.get("embellishment"),
            }
            for item in gear_items or []
            if isinstance(item, dict)
        ],
        "seedTemplateId": (evidence or {}).get("seedTemplateId") or "",
    }
    return f"season_recommendation_{class_key}_{spec_key}_{stable_digest(seed)}"


def build_season_recommended_gear_template(class_key, spec_key, gear_items, evidence=None):
    class_key = slugify(class_key, "mage")
    spec_key = slugify(spec_key, "arcane")
    evidence = copy.deepcopy(evidence if isinstance(evidence, dict) else {})
    ready_by_slot, occupied_slots, missing_slots = gear_template_slot_coverage(gear_items or [], class_key, spec_key)
    if missing_slots:
        raise ValueError(f"missing canonical gear slots: {', '.join(missing_slots)}")
    ordered_items = [ready_by_slot[slot] for slot in CANONICAL_GEAR_SLOTS if slot in ready_by_slot]
    raw_lines = build_websim_gear_lines(ordered_items)
    if not raw_lines:
        raise ValueError("season recommended gear template has no SimC-ready gear lines")

    role_policy = season_recommended_role_policy(class_key, spec_key, evidence.get("role"))
    evidence.setdefault("scenarioKey", SEASON_RECOMMENDED_GEAR_SCENARIO_KEY)
    evidence.setdefault("optimizerRunId", "")
    evidence.setdefault("candidateCount", 1)
    evidence.setdefault("simcRunCount", 0)
    evidence.setdefault("blockers", [])
    evidence.setdefault("warnings", [])
    evidence["rolePolicy"] = role_policy
    evidence["recommendationConfidence"] = role_policy["recommendationConfidence"]
    evidence.setdefault("sourceKey", SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY)
    evidence.setdefault("sourceName", SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME)

    template = {
        "id": _template_id(class_key, spec_key, ordered_items, evidence),
        "name": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        "classKey": class_key,
        "specKey": spec_key,
        "sourceKey": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
        "sourceName": SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME,
        "sourceUrl": "",
        "sourceStatus": "synced",
        "status": "complete",
        "updatedAt": evidence.get("checkedAt") or utc_now(),
        "expiresAt": season_expires_at(),
        "analysisWindow": "Current-season M+ AOE recommendation generated from verified complete gear evidence.",
        "gearItems": ordered_items,
        "rawString": "\n".join(raw_lines),
        "readySlotCount": len(CANONICAL_GEAR_SLOTS),
        "missingSlots": [],
        "canApplyGear": True,
        "scenarioKey": evidence["scenarioKey"],
        "payload": {
            "templateSlot": "baseline",
            "baselineDisplaySlot": True,
            "scenarioKey": evidence["scenarioKey"],
            "templateEvidence": evidence,
            "occupiedSlots": occupied_slots,
            "countingPolicy": "current-season recommendation baseline subtype under community import; does not count as real community gear",
        },
    }
    if occupied_slots:
        template["occupiedSlots"] = occupied_slots
    template["templateEvidence"] = evidence
    gear_signature = gear_template_signature(template)
    evidence.setdefault("gearSignature", gear_signature)
    template["signature"] = f"{SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY}:{gear_signature}"
    template["sourceRefs"] = normalize_source_refs(evidence.get("sourceRefs") or [gear_template_source_ref(template)])
    template["templateRevision"] = COMMUNITY_TEMPLATE_REVISION
    return template
