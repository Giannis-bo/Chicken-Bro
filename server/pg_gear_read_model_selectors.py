#!/usr/bin/env python3
import json

try:
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        SIMC_GEAR_OPTION_KEYS,
        active_catalog_sources_for_replacement,
        apply_gear_candidate_legality,
        apply_gear_mod_option_display_fields,
        blocked_stat_snapshot,
        candidate_legality_audit_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        enrich_catalog_item,
        fallback_text_for,
        game_asset_from_icon_url,
        gear_mod_option_display_fields,
        gear_mod_option_is_supported_config_option,
        gear_mod_option_payload_with_config_policy,
        gear_slot_payload,
        gear_candidate_for_slot,
        gear_candidate_incompatible,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_readiness,
        limit_replacement_candidates,
        localized_difficulty_label,
        normalize_gear_item,
        normalize_option_value,
        normalize_slot,
        sanitize_gear_candidate_mod_options,
        unique_gear_candidates,
        utc_now,
        websim_max_level,
        weapon_equipment_rule_payload,
    )
except ImportError:
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        GEAR_CATALOG_REVISION,
        GEAR_SCHEMA_REVISION,
        GEAR_SLOT_LABELS,
        SIMC_GEAR_OPTION_KEYS,
        active_catalog_sources_for_replacement,
        apply_gear_candidate_legality,
        apply_gear_mod_option_display_fields,
        blocked_stat_snapshot,
        candidate_legality_audit_payload,
        compact_catalog_health_summary,
        compact_gear_candidates,
        compact_gear_mod_options,
        enrich_catalog_item,
        fallback_text_for,
        game_asset_from_icon_url,
        gear_mod_option_display_fields,
        gear_mod_option_is_supported_config_option,
        gear_mod_option_payload_with_config_policy,
        gear_slot_payload,
        gear_candidate_for_slot,
        gear_candidate_incompatible,
        gear_candidate_quality_score,
        gear_candidate_slots,
        gear_readiness,
        gear_slot_readiness,
        limit_replacement_candidates,
        localized_difficulty_label,
        normalize_gear_item,
        normalize_option_value,
        normalize_slot,
        sanitize_gear_candidate_mod_options,
        unique_gear_candidates,
        utc_now,
        websim_max_level,
        weapon_equipment_rule_payload,
    )


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _int_value(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def build_gear_sources_by_item_read_model(rows):
    result = {}
    for row in rows or []:
        payload = _json_value(row[9], {})
        payload = payload if isinstance(payload, dict) else {}
        label = str(row[4] or row[3] or row[2] or "").strip()
        source = {
            "id": str(row[0]),
            "itemId": str(row[1]),
            "sourceType": row[2],
            "sourceKey": row[3],
            "label": label,
            "sourceLabel": label,
            "instanceId": row[5],
            "encounterId": row[6],
            "difficultyKey": row[7],
            "difficultyLabel": localized_difficulty_label(row[7], label, row[2]),
            "seasonRevision": row[8],
            "payload": payload,
            "updatedAt": str(row[10] or ""),
        }
        if payload.get("recommendationScore") is not None:
            source["recommendationScore"] = payload.get("recommendationScore")
        result.setdefault(str(row[1]), []).append(source)
    return result


def build_gear_variants_by_item_read_model(rows):
    result = {}
    for row in rows or []:
        simc_options = _json_value(row[8], {})
        if not isinstance(simc_options, dict):
            simc_options = {}
        blockers = _json_value(row[10], [])
        if not isinstance(blockers, list):
            blockers = [str(blockers)]
        payload = _json_value(row[11], {})
        payload = payload if isinstance(payload, dict) else {}
        item_level = _int_value(row[7])
        variant = {
            "id": str(row[0]),
            "itemId": str(row[1]),
            "slot": normalize_slot(row[2]),
            "key": row[3],
            "variantKey": row[3],
            "label": row[4],
            "difficultyLabel": localized_difficulty_label(row[6], row[4], row[5]),
            "sourceType": row[5],
            "difficultyKey": row[6],
            "itemLevel": item_level,
            "ilevel": item_level,
            "simcOptions": simc_options,
            "status": row[9] or "blocked",
            "blockers": [str(item) for item in blockers if str(item or "").strip()],
            "payload": payload,
            "updatedAt": str(row[12] or ""),
        }
        if payload.get("simcIlevelOnly"):
            variant["simcIlevelOnly"] = True
        result.setdefault(str(row[1]), []).append(variant)
    return result


def build_admin_gear_variant_records_read_model(rows):
    return [
        {
            "id": str(row[0] or ""),
            "itemId": str(row[1] or ""),
            "itemName": str(row[2] or ""),
            "slot": row[3] or "",
            "label": row[4] or "",
            "sourceType": row[5] or "",
            "difficultyKey": row[6] or "",
            "itemLevel": _int_value(row[7]),
            "simcOptions": _json_value(row[8], {}),
            "status": row[9] or "",
            "blockers": _json_value(row[10], []),
            "payload": _json_value(row[11], {}),
            "itemPayload": _json_value(row[12], {}),
            "sourceLabel": str(row[13] or ""),
            "sourceInstanceId": str(row[14] or ""),
            "updatedAt": str(row[15] or ""),
        }
        for row in rows or []
    ]


def build_websim_instances_read_model(instance_rows, encounter_rows):
    encounters = {}
    for row in encounter_rows or []:
        encounters.setdefault(row[1], []).append({"id": row[0], "instanceId": row[1], "name": row[2]})
    return [
        {"id": row[0], "name": row[1], "category": row[2], "encounters": encounters.get(row[0], [])}
        for row in instance_rows or []
    ]


def build_websim_loot_items_read_model(
    rows,
    filters=None,
    *,
    limit=120,
    normalize_item=None,
    game_asset_factory=None,
    fallback_text=None,
):
    filters = filters or {}
    normalize_item = normalize_item or normalize_gear_item
    game_asset_factory = game_asset_factory or game_asset_from_icon_url
    fallback_text = fallback_text or fallback_text_for
    items = []
    for row in rows or []:
        item_payload = _json_value(row[10], {})
        item = normalize_item(
            {
                "id": row[5],
                "itemId": row[5],
                "name": row[6],
                "displayName": row[6],
                "slot": row[7],
                "quality": row[8],
                "iconUrl": row[9],
                "sourceType": "verifiedLoot",
                "source": f"{row[4] or 'Unknown Encounter'} - {row[2] or 'Unknown Instance'}",
                "payload": item_payload,
            },
            default_source_type="verifiedLoot",
        )
        if not item:
            continue
        loot_asset = game_asset_factory(
            "item",
            row[5],
            "websim-loot",
            row[9],
            source="blizzard",
            status="verified",
            semantic_tags=["game", "gear", "item", "loot", row[7]],
            usage=["websim_loot", "builds_detail"],
            fallback_text=fallback_text(row[6]),
        )
        item.update(
            {
                "id": row[0],
                "instanceId": row[1],
                "instanceName": row[2] or "Unknown Instance",
                "encounterId": row[3],
                "encounterName": row[4] or "Unknown Encounter",
                "itemId": row[5],
                "quality": row[8],
                "iconUrl": row[9],
                "gameAsset": loot_asset,
                "sourceType": "verifiedLoot",
            }
        )
        items.append(item)
    instance_id = str(filters.get("instanceId") or "")
    encounter_id = str(filters.get("encounterId") or "")
    slot = str(filters.get("slot") or "")
    query = str(filters.get("q") or "").strip().lower()
    if instance_id:
        items = [item for item in items if str(item.get("instanceId")) == instance_id]
    if encounter_id:
        items = [item for item in items if str(item.get("encounterId")) == encounter_id]
    if slot:
        items = [item for item in items if item.get("slot") == slot]
    if query:
        items = [
            item for item in items
            if query in str(item.get("name", "")).lower()
            or query in str(item.get("encounterName", "")).lower()
            or query in str(item.get("instanceName", "")).lower()
        ]
    return items[:limit]


def build_gear_mod_options_by_slot_read_model(rows):
    result = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for row in rows or []:
        option_type = str(row[1] or "").strip().lower()
        slots = _json_value(row[4], [])
        if isinstance(slots, str):
            slots = [slots]
        if not isinstance(slots, list):
            slots = []
        normalized_slots = [normalize_slot(slot) for slot in slots]
        normalized_slots = [slot for slot in normalized_slots if slot]
        if not normalized_slots or "*" in slots:
            normalized_slots = list(CANONICAL_GEAR_SLOTS)
        simc_options = _json_value(row[5], {})
        if not isinstance(simc_options, dict):
            simc_options = {}
        simc_options = {
            key: normalize_option_value(value)
            for key, value in simc_options.items()
            if key in SIMC_GEAR_OPTION_KEYS
        }
        payload = _json_value(row[7], {})
        payload = payload if isinstance(payload, dict) else {}
        payload = gear_mod_option_payload_with_config_policy(
            option_type,
            row[3],
            simc_options,
            payload,
            normalized_slots,
        )
        if not gear_mod_option_is_supported_config_option(option_type, simc_options, payload, row[3]):
            continue
        display_fields = gear_mod_option_display_fields(option_type, row[3], simc_options, payload)
        label = str(
            display_fields.get("displayLabel")
            or payload.get("displayLabel")
            or payload.get("displayName")
            or row[3]
            or row[2]
            or ""
        ).strip()
        option = {
            "id": str(row[0]),
            "type": option_type,
            "optionType": option_type,
            "name": label,
            "label": label,
            "rawName": row[3],
            "simcOptions": simc_options,
            "status": row[6] or "blocked",
            "payload": payload,
            "updatedAt": str(row[8] or ""),
        }
        option = apply_gear_mod_option_display_fields(option, display_fields)
        for key in (
            "displayName",
            "displayLabel",
            "displayKind",
            "displayStatus",
            "evidenceSource",
            "evidenceRef",
            "iconUrl",
            "quality",
            "gameAsset",
            "metadataStatus",
            "metadataSource",
            "metadataLocale",
            "itemStats",
            "statSummary",
            "slotGroup",
            "slot_group",
            "uniqueEquipped",
            "unique_equipped",
            "uniqueGroup",
            "unique_group",
            "uniqueLimit",
            "unique_limit",
            "uniqueScope",
            "unique_scope",
            "configCategory",
            "config_category",
            "exclusionReason",
            "exclusion_reason",
            "itemTypeRule",
            "item_type_rule",
        ):
            if payload.get(key) not in (None, "", [], {}):
                if key in {"displayName", "displayLabel", "displayKind", "displayStatus", "evidenceSource", "evidenceRef"} and option.get(key) not in (None, "", [], {}):
                    continue
                option[key] = payload.get(key)
        for slot in normalized_slots:
            if slot in result:
                result[slot].append(option)
    return result


def build_gear_mod_options_by_type_read_model(rows):
    rows_by_type = {
        "socket": [],
        "enchant": [],
        "embellishment": [],
    }
    for row in rows or []:
        option_type = str(row[1] or "").strip().lower()
        if option_type in rows_by_type:
            rows_by_type[option_type].append(row)
    return {
        option_type: build_gear_mod_options_by_slot_read_model(option_rows)
        for option_type, option_rows in rows_by_type.items()
    }


def build_gear_catalog_items_read_model(
    item_rows,
    sources_by_item,
    variants_by_item,
    mod_options_by_slot,
    class_key,
    spec_key,
    season,
):
    catalog_items = []
    sources_by_item = sources_by_item if isinstance(sources_by_item, dict) else {}
    variants_by_item = variants_by_item if isinstance(variants_by_item, dict) else {}
    mod_options_by_slot = mod_options_by_slot if isinstance(mod_options_by_slot, dict) else {}
    season = season if isinstance(season, dict) else {}
    for row in item_rows or []:
        payload = _json_value(row[4], {})
        payload = payload if isinstance(payload, dict) else {}
        item_id = str(row[0])
        item_sources = active_catalog_sources_for_replacement(sources_by_item.get(item_id, []), season)
        item_variants = variants_by_item.get(item_id, [])
        if not item_sources:
            continue
        raw_item = {
            "id": item_id,
            "itemId": item_id,
            "name": row[1],
            "displayName": payload.get("displayName") or payload.get("name") or row[1],
            "slot": row[2],
            "itemLevel": row[3],
            "ilevel": row[3],
            "quality": payload.get("quality") or "",
            "iconUrl": payload.get("iconUrl") or "",
            "source": (sources_by_item.get(item_id) or [{}])[0].get("label") or "gear catalog",
            "sourceType": "catalog",
            "payload": payload,
        }
        item = normalize_gear_item(raw_item, class_key, spec_key, "catalog")
        if not item:
            continue
        item = enrich_catalog_item(
            item,
            item_sources,
            item_variants,
            mod_options_by_slot.get("socket", {}).get(item["slot"], []),
            mod_options_by_slot.get("enchant", {}).get(item["slot"], []),
            mod_options_by_slot.get("embellishment", {}).get(item["slot"], []),
            class_key,
            spec_key,
        )
        if item:
            catalog_items.append(sanitize_gear_candidate_mod_options(item))
    return catalog_items


def build_season_recommended_catalog_candidates_by_slot_read_model(
    catalog_items,
    class_key,
    spec_key,
    *,
    candidate_limit=24,
):
    catalog_items = sorted(catalog_items or [], key=gear_candidate_quality_score, reverse=True)
    grouped = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for item in catalog_items:
        candidate_slots = gear_candidate_slots(item, class_key, spec_key)
        if not candidate_slots:
            checked = apply_gear_candidate_legality(item, class_key, spec_key, item.get("slot"))
            if gear_candidate_incompatible(checked):
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
            if gear_candidate_incompatible(candidate):
                continue
            grouped[candidate_slot].append(candidate)
    return {
        slot: limit_replacement_candidates(
            sorted(unique_gear_candidates(items), key=gear_candidate_quality_score, reverse=True),
            candidate_limit,
        )
        for slot, items in grouped.items()
    }


def build_common_gear_read_model_fragment(class_key, spec_key, readiness, *, checked_at=None):
    return {
        "weaponRule": weapon_equipment_rule_payload(class_key, spec_key),
        "slots": gear_slot_payload(),
        "readiness": readiness,
        "statSnapshot": blocked_stat_snapshot(
            ["Select complete SimC-ready gear and talents to calculate a verified stat snapshot."],
            class_key=class_key,
            spec_key=spec_key,
            gear_readiness_payload=readiness,
        ),
        "maxLevel": websim_max_level(),
        "checkedAt": checked_at or utc_now(),
    }


def build_catalog_output_read_model_fragment(catalog_read_model, *, compact=False):
    catalog_read_model = catalog_read_model if isinstance(catalog_read_model, dict) else {}
    output = {
        "catalogItems": (catalog_read_model.get("catalogItems") or [])[:120],
    }
    if not compact:
        output.update(
            {
                "slotGroups": catalog_read_model.get("replacementCandidates") or [],
                "presets": [],
                "candidateItems": [],
                "candidateLegalityAudit": catalog_read_model.get("candidateLegalityAudit") or {},
            }
        )
    return output


def _compact_initial_gear_item(item, compact=False):
    items = compact_gear_candidates([item], include_mod_options=False) if compact else [dict(item)]
    if not items:
        return {}
    output = dict(items[0])
    output["detailMode"] = "summary"
    output["slotDetailAvailable"] = True
    return output


def _template_gear_by_slot(template, compact=False):
    result = {}
    for item in (template or {}).get("gearItems") or []:
        if not isinstance(item, dict):
            continue
        slot = normalize_slot(item.get("simcSlot") or item.get("slot"))
        if slot in CANONICAL_GEAR_SLOTS and slot not in result:
            initial_item = _compact_initial_gear_item(item, compact=compact)
            if initial_item:
                result[slot] = initial_item
    return result


def build_initial_gear_read_model_fragment(baseline_template, class_key, spec_key, *, compact=False):
    baseline_template = baseline_template if isinstance(baseline_template, dict) else {}
    baseline_items = baseline_template.get("gearItems") or []
    equipped_set = _template_gear_by_slot(baseline_template, compact=compact)
    slot_groups = []
    for slot in CANONICAL_GEAR_SLOTS:
        item = equipped_set.get(slot)
        slot_groups.append(
            {
                "slot": slot,
                "simcSlot": slot,
                "label": GEAR_SLOT_LABELS.get(slot, slot),
                "items": [item] if item else [],
                "detailMode": "partial",
                "fullItemCount": 1 if item else 0,
            }
        )
    output_baseline_set = compact_gear_candidates(baseline_items, include_mod_options=False) if compact else baseline_items
    return {
        "replacementCandidates": slot_groups,
        "equippedSet": equipped_set,
        "slotReadiness": gear_slot_readiness(baseline_items, class_key, spec_key),
        "baselineSet": output_baseline_set,
        "readiness": gear_readiness(baseline_items),
        "catalogItems": output_baseline_set[:120],
    }


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
