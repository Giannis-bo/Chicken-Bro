#!/usr/bin/env python3

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        apply_gear_candidate_legality,
        candidate_legality_audit_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        gear_candidate_for_slot,
        gear_candidate_incompatible,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_readiness,
        limit_replacement_candidates,
        unique_gear_candidates,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        apply_gear_candidate_legality,
        candidate_legality_audit_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        gear_candidate_for_slot,
        gear_candidate_incompatible,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_readiness,
        limit_replacement_candidates,
        unique_gear_candidates,
    )


def build_catalog_state_read_model_fragment(catalog_state, catalog_blockers):
    catalog_state = catalog_state if isinstance(catalog_state, dict) else {}
    return {
        "gearSchemaRevision": GEAR_SCHEMA_REVISION,
        "gearCatalogRevision": catalog_state.get("schemaRevision") or GEAR_CATALOG_REVISION,
        "catalogStatus": catalog_state.get("status") or "blocked",
        "catalogHealthSummary": compact_catalog_health_summary(catalog_state),
        "catalogCoverage": {
            "slotCoverage": catalog_state.get("slotCoverage") or {},
            "sourceCoverage": catalog_state.get("sourceCoverage") or {},
            "observedVariantCount": catalog_state.get("observedVariantCount") or 0,
            "verifiedObservedVariantCount": catalog_state.get("verifiedObservedVariantCount") or 0,
            "verifiedVariantCount": catalog_state.get("verifiedCount") or 0,
            "partialVariantCount": catalog_state.get("partialCount") or 0,
            "blockedVariantCount": catalog_state.get("blockedCount") or 0,
        },
        "itemDatabaseRevision": catalog_state.get("itemDatabaseRevision") or "",
        "variantRevision": catalog_state.get("variantRevision") or "",
        "catalogCheckedAt": catalog_state.get("checkedAt") or catalog_state.get("updatedAt") or "",
        "catalogBlockers": catalog_blockers,
    }


def build_catalog_gear_read_model_fragment(
    catalog_items,
    raw_options_by_slot,
    class_key,
    spec_key,
    *,
    compact=False,
    candidate_limit=None,
):
    catalog_items = sorted(catalog_items or [], key=gear_candidate_quality_score, reverse=True)
    raw_options_by_slot = raw_options_by_slot or {}
    socket_options_by_slot = raw_options_by_slot.get("socket") or {}
    enchant_options_by_slot = raw_options_by_slot.get("enchant") or {}
    embellishment_options_by_slot = raw_options_by_slot.get("embellishment") or {}

    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    candidate_legality_excluded = []
    for item in catalog_items:
        if gear_candidate_incompatible(item):
            checked = apply_gear_candidate_legality(item, class_key, spec_key, item.get("slot"))
            if checked.get("legalityStatus") == "blocked":
                candidate_legality_excluded.append(checked)
            continue
        candidate_slots = gear_candidate_slots(item, class_key, spec_key)
        if not candidate_slots:
            checked = apply_gear_candidate_legality(item, class_key, spec_key, item.get("slot"))
            if checked.get("legalityStatus") == "blocked" or gear_candidate_incompatible(checked):
                candidate_legality_excluded.append(checked)
            continue
        for candidate_slot in candidate_slots:
            if candidate_slot not in grouped:
                continue
            candidate = apply_gear_candidate_legality(
                gear_candidate_for_slot(item, candidate_slot),
                class_key,
                spec_key,
                candidate_slot,
            )
            if candidate.get("legalityStatus") == "blocked" or gear_candidate_incompatible(candidate):
                candidate_legality_excluded.append(candidate)
                continue
            grouped[candidate_slot].append(candidate)

    if candidate_limit is None and compact:
        candidate_limit = 12
    slot_groups = []
    baseline_candidates_by_slot = {}
    for slot in CANONICAL_GEAR_SLOTS:
        items = sorted(unique_gear_candidates(grouped.get(slot, [])), key=gear_candidate_quality_score, reverse=True)
        if candidate_limit:
            items = limit_replacement_candidates(items, candidate_limit)
        baseline_candidates_by_slot[slot] = items
        socket_options = socket_options_by_slot.get(slot, []) if items else []
        enchant_options = enchant_options_by_slot.get(slot, []) if items else []
        embellishment_options = embellishment_options_by_slot.get(slot, []) if items else []
        output_items = compact_gear_candidates(items, include_mod_options=False) if compact else items
        slot_group = {
            "slot": slot,
            "simcSlot": slot,
            "label": GEAR_SLOT_LABELS.get(slot, slot),
            "items": output_items,
        }
        if socket_options:
            slot_group["socketOptions"] = compact_gear_mod_options(socket_options) if compact else socket_options
        if enchant_options:
            slot_group["enchantOptions"] = compact_gear_mod_options(enchant_options) if compact else enchant_options
        if embellishment_options:
            slot_group["embellishmentOptions"] = compact_gear_mod_options(embellishment_options) if compact else embellishment_options
        slot_groups.append(slot_group)

    readiness = gear_readiness(catalog_items)
    return {
        "replacementCandidates": slot_groups,
        "baselineCandidatesBySlot": baseline_candidates_by_slot,
        "catalogItems": compact_gear_candidates(catalog_items) if compact else catalog_items,
        "readiness": readiness,
        "slotReadiness": gear_slot_readiness(catalog_items, class_key, spec_key),
        "candidateLegalityAudit": candidate_legality_audit_payload(candidate_legality_excluded),
    }
