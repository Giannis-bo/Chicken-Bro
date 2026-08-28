#!/usr/bin/env python3
import hashlib
import os
import json
import re
import sqlite3
import time
from datetime import datetime, timezone

try:
    from .crafted_pve_membership import crafted_pve_membership_items
    from .db import connect_postgres, database_config_from_env
    from .postgres_cache_store import (
        PostgresCacheStore,
        simc_talent_persisted_content_identity,
        utc_now,
    )
    from .raiderio_payload import capture_gear_projection_profiles, sync_raiderio_cache
    from .websim_journal_contract import journal_discovery_state
    from .stat_weights_payload import (
        MPLUS_SCENARIOS,
        aggregate_by_spec,
        build_scenario_payload_with_previous,
        ready_profile_candidate,
        representative_profile_candidates,
        scenario_blocked_payload,
        specialization_registry,
    )
    from .websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_PENDING_STATUS,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        DEFAULT_LOCALE,
        DEFAULT_REGION,
        GEAR_CATALOG_REVISION,
        GEAR_OBSERVED_BACKFILL_SYNC_KEY,
        TALENT_CATALOG_REVISION,
        TALENT_SCHEMA_REVISION,
        SIMC_PROFILE_RETIREMENT_SCHEMA_REVISION,
        apply_gear_template_legality_gate,
        blizzard_get,
        blizzard_namespace,
        community_gear_import_coverage_summary,
        class_label,
        community_talent_loadout_spec_blockers,
        disabled_community_talent_template_source_keys,
        include_websim_baseline_talent_sources,
        current_season_raid_pool_status,
        expected_spec_pairs,
        expected_hero_tree_triplets,
        extract_simc_generated_data,
        extract_id_from_ref,
        fetch_blizzard_item_metadata,
        get_blizzard_access_token,
        gear_template_slot_coverage,
        hero_tree_for,
        hero_tree_label,
        icon_url_from_media,
        is_active_community_observed_template,
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        recommended_bis_role_for_spec_id,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        slugify,
        spec_label,
        unique_text_list,
        websim_gear_template_chain_state,
    )
except ImportError:
    from crafted_pve_membership import crafted_pve_membership_items
    from db import connect_postgres, database_config_from_env
    from postgres_cache_store import (
        PostgresCacheStore,
        simc_talent_persisted_content_identity,
        utc_now,
    )
    from raiderio_payload import capture_gear_projection_profiles, sync_raiderio_cache
    from websim_journal_contract import journal_discovery_state
    from stat_weights_payload import (
        MPLUS_SCENARIOS,
        aggregate_by_spec,
        build_scenario_payload_with_previous,
        ready_profile_candidate,
        representative_profile_candidates,
        scenario_blocked_payload,
        specialization_registry,
    )
    from websim_payload import (
        CANONICAL_GEAR_SLOTS,
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_PENDING_STATUS,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
        DEFAULT_LOCALE,
        DEFAULT_REGION,
        GEAR_CATALOG_REVISION,
        GEAR_OBSERVED_BACKFILL_SYNC_KEY,
        TALENT_CATALOG_REVISION,
        TALENT_SCHEMA_REVISION,
        SIMC_PROFILE_RETIREMENT_SCHEMA_REVISION,
        apply_gear_template_legality_gate,
        blizzard_get,
        blizzard_namespace,
        community_gear_import_coverage_summary,
        class_label,
        community_talent_loadout_spec_blockers,
        disabled_community_talent_template_source_keys,
        include_websim_baseline_talent_sources,
        current_season_raid_pool_status,
        expected_spec_pairs,
        expected_hero_tree_triplets,
        extract_simc_generated_data,
        extract_id_from_ref,
        fetch_blizzard_item_metadata,
        get_blizzard_access_token,
        gear_template_slot_coverage,
        hero_tree_for,
        hero_tree_label,
        icon_url_from_media,
        is_active_community_observed_template,
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        recommended_bis_role_for_spec_id,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        slugify,
        spec_label,
        unique_text_list,
        websim_gear_template_chain_state,
    )


CRAFTED_GEAR_BACKFILL_SYNC_KEY = "crafted_gear_backfill"
CRAFTED_DOUBLE_SECONDARY_VALUES = (
    "32/36",
    "32/40",
    "32/49",
    "36/40",
    "36/49",
    "40/49",
)
CRAFTED_SINGLE_SECONDARY_VALUES = ("32", "36", "40", "49")
COMMUNITY_TALENT_COVERAGE_MATRIX_REVISION = "community-talent-coverage-matrix-v1"
COMMUNITY_GEAR_TEMPLATE_PREFLIGHT_REVISION = "community-gear-template-preflight-v1"
COMMUNITY_TEMPLATE_STAGE_TIMING_REVISION = "community-template-stage-timings-v1"
ITEM_METADATA_REFRESH_SYNC_KEY = "item_metadata_refresh"
SEASON_RECOMMENDED_GEAR_SYNC_KEY = "season_recommended_gear_sync"
COMMUNITY_BEST_GUARD_SYNC_KEY = "community_best_v2_guard"
RECOMMENDED_BIS_GUARD_SYNC_KEY = "recommended_bis_v1_guard"
RECOMMENDED_BIS_PROTOTYPE_SYNC_KEY = "recommended_bis_v1_prototype_sync"
BASELINE_GEAR_TEMPLATE_SOURCE_KEYS = {
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "recommended_bis",
    "season_recommendation",
    "baseline_template",
    "simc_preset",
}
BAD_REAL_GEAR_TEMPLATE_SOURCE_KEYS = {
    "",
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "recommended_bis",
    "season_recommendation",
    "baseline_template",
    "simc_preset",
    "manual_fixture",
    "fallback",
    "source_reference",
}


def cache_store_from_env():
    config = database_config_from_env()
    if config.backend != "postgres" or not config.database_url:
        raise RuntimeError("PostgreSQL cache sync requires WOW_DATABASE_URL")
    return PostgresCacheStore(lambda: connect_postgres(config.database_url))


def _emit(stage_callback, stage, status, **details):
    if stage_callback:
        stage_callback({"stage": stage, "status": status, **details})


def _timing_stage(stage, started_at, **details):
    event = {
        "stage": stage,
        "durationSeconds": round(max(0.0, time.monotonic() - started_at), 3),
    }
    event.update({key: value for key, value in details.items() if value is not None})
    return event


def _sync_timing_summary(started_at, stages, coverage_matrix=None, talent_counts=None):
    coverage_matrix = coverage_matrix if isinstance(coverage_matrix, dict) else {}
    talent_counts = talent_counts if isinstance(talent_counts, dict) else {}
    return {
        "schemaRevision": COMMUNITY_TEMPLATE_STAGE_TIMING_REVISION,
        "totalDurationSeconds": round(max(0.0, time.monotonic() - started_at), 3),
        "candidateCount": int(talent_counts.get("candidateTotal") or talent_counts.get("total") or 0),
        "verifiedCount": int(coverage_matrix.get("verifiedHeroSlotCount") or talent_counts.get("verified") or 0),
        "blockedCount": int(coverage_matrix.get("blockedHeroSlotCount") or talent_counts.get("blocked") or 0),
        "pendingDelta": int(coverage_matrix.get("pendingCollectionHeroSlotCount") or 0),
        "stages": list(stages or []),
    }


def _status_from_counts(verified=0, partial=0, blocked=0):
    verified = int(verified or 0)
    partial = int(partial or 0)
    blocked = int(blocked or 0)
    if verified and not partial and not blocked:
        return "verified"
    if verified or partial:
        return "partial"
    return "blocked"


def _source_status_bucket(status):
    normalized = str(status or "").strip()
    if normalized in {"verified", "synced", "complete", "ok"}:
        return "verified"
    if normalized in {"partial", "stale", "missing_credentials", "skipped"}:
        return "partial"
    return "blocked"


def _status_from_counts_and_sources(verified=0, partial=0, blocked=0, sources=None, errors=None):
    row_status = _status_from_counts(verified, partial, blocked)
    if row_status == "blocked":
        return "blocked"
    source_buckets = [
        _source_status_bucket(source.get("status") or source.get("sourceStatus"))
        for source in (sources or {}).values()
        if isinstance(source, dict)
    ]
    if errors or any(bucket in {"partial", "blocked"} for bucket in source_buckets):
        return "partial"
    return row_status


def fetch_websim_journal_data_postgres(region=DEFAULT_REGION, locale=DEFAULT_LOCALE):
    token = get_blizzard_access_token(region)
    instance_limit = int(os.environ.get("WOW_WEBSIM_SYNC_INSTANCE_LIMIT", "20"))
    raid_instance_limit = int(os.environ.get("WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT", "8"))
    encounter_limit = int(os.environ.get("WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT", "200"))
    item_limit = int(os.environ.get("WOW_WEBSIM_SYNC_ITEM_LIMIT", "1000"))
    season = resolve_current_mythic_season(token, region, locale)
    dungeons, truncated_dungeons = limited_sync_items(
        [
            {**dungeon, "instanceId": str(dungeon.get("instanceId") or dungeon.get("id") or ""), "category": "Dungeon"}
            for dungeon in (season.get("dungeons") or [])
            if str(dungeon.get("instanceId") or dungeon.get("id") or "").strip()
        ],
        instance_limit,
    )
    raid_refs = []
    journal_expansion_name = ""
    errors = []
    try:
        selected_refs = selected_journal_instance_refs(token, region, season.get("locale") or locale)
        if isinstance(selected_refs, tuple) and selected_refs and isinstance(selected_refs[0], list):
            journal_expansion_name = str(selected_refs[1] or "") if len(selected_refs) > 1 else ""
            selected_refs = selected_refs[0]
        for raw_ref in selected_refs or []:
            ref = normalize_journal_instance_ref(raw_ref)
            if str(ref.get("category") or "").lower() == "raid":
                raid_refs.append({**ref, "instanceId": str(ref.get("instanceId") or ref.get("id") or ""), "category": "Raid"})
    except Exception as error:
        errors.append(str(error))
    raid_pool_status = current_season_raid_pool_status({"raids": raid_refs})
    discovered_raid_refs = raid_pool_status.get("refs") or []
    fallback_raid_refs = (
        official_current_season_raid_refs()
        if not discovered_raid_refs
        else []
    )
    raid_fallback_gap = None
    if fallback_raid_refs:
        raid_fallback_gap = {
            "kind": "fallback",
            "boundary": "raidInstances",
            "identity": "journal:raid-instances",
            "omittedCount": 0,
            "evidenceRef": "blizzard:game-data:journal",
            "message": "; ".join(raid_pool_status.get("blockers") or []),
        }
    raid_membership_gap = None
    if raid_pool_status.get("blockers"):
        raid_membership_gap = {
            "kind": "membership",
            "boundary": "raidInstances",
            "identity": "journal:raid-instances",
            "omittedCount": len(raid_pool_status.get("missingNames") or []),
            "evidenceRef": "blizzard:game-data:journal",
            "message": "; ".join(raid_pool_status.get("blockers") or []),
        }
    raid_refs = discovered_raid_refs or fallback_raid_refs
    season = {
        **season,
        "raids": raid_refs,
        "raidPoolStatus": raid_pool_status,
    }
    if journal_expansion_name:
        season["journalExpansionName"] = journal_expansion_name
    limited_raid_refs, truncated_raids = limited_sync_items(raid_refs, raid_instance_limit)
    instance_refs = []
    seen_instances = set()
    for ref in [*dungeons, *limited_raid_refs]:
        instance_id = str(ref.get("instanceId") or ref.get("id") or "").strip()
        if not instance_id or instance_id in seen_instances:
            continue
        seen_instances.add(instance_id)
        instance_refs.append({**ref, "instanceId": instance_id})
    counts = {
        "truncatedDungeons": truncated_dungeons,
        "truncatedRaids": truncated_raids,
        "limits": {
            "dungeonInstances": instance_limit,
            "raidInstances": raid_instance_limit,
            "encounters": encounter_limit,
            "items": item_limit,
        },
        "truncation": {
            "dungeonInstances": truncated_dungeons,
            "raidInstances": truncated_raids,
            "encounters": 0,
            "items": 0,
        },
        "errors": errors,
        "fetchFailures": [],
        "skippedNonGearLoot": 0,
        "skippedNonGearLootExamples": [],
    }
    fetched_items = set()
    instances = []
    for instance_ref in instance_refs:
        instance_id = str(instance_ref.get("instanceId") or "")
        if not instance_id:
            continue
        try:
            instance_payload = blizzard_get(
                f"/data/wow/journal-instance/{instance_id}",
                token,
                region,
                season.get("locale") or locale,
                namespace=blizzard_namespace(region, "static"),
            )
        except Exception as error:
            counts["fetchFailures"].append(
                {"type": "instance", "id": instance_id, "name": instance_ref.get("name") or "", "message": str(error)}
            )
            instance_payload = {
                "id": instance_id,
                "name": instance_ref.get("name") or f"Instance {instance_id}",
                "category": {"name": instance_ref.get("category") or "Dungeon"},
                "encounters": [],
                "_syncError": str(error),
            }
        instance_name = instance_payload.get("name") or instance_ref.get("name") or f"Instance {instance_id}"
        category = (instance_payload.get("category") or {}).get("name") or instance_ref.get("category") or "Dungeon"
        instance = {
            "id": instance_id,
            "name": instance_name,
            "category": category,
            "payload": instance_payload,
            "encounters": [],
        }
        encounter_refs = list_keyed_values(instance_payload, "encounters")
        remaining_encounter_capacity = encounter_limit - sum(len(item.get("encounters") or []) for item in instances)
        if encounter_limit >= 0 and remaining_encounter_capacity <= 0:
            counts["truncation"]["encounters"] += len(encounter_refs)
            continue
        encounter_refs, skipped_encounters = limited_sync_items(
            encounter_refs,
            remaining_encounter_capacity if encounter_limit >= 0 else len(encounter_refs),
        )
        counts["truncation"]["encounters"] += skipped_encounters
        for encounter_ref in encounter_refs:
            encounter_id = extract_id_from_ref(encounter_ref)
            if not encounter_id:
                continue
            try:
                encounter_payload = blizzard_get(
                    f"/data/wow/journal-encounter/{encounter_id}",
                    token,
                    region,
                    season.get("locale") or locale,
                    namespace=blizzard_namespace(region, "static"),
                )
            except Exception as error:
                counts["fetchFailures"].append(
                    {"type": "encounter", "id": str(encounter_id), "name": (encounter_ref or {}).get("name") or "", "message": str(error)}
                )
                continue
            encounter = {
                "id": str(encounter_id),
                "name": encounter_payload.get("name") or f"Encounter {encounter_id}",
                "payload": encounter_payload,
                "items": [],
            }
            for loot_ref in list_keyed_values(encounter_payload, "items", "loot"):
                item_ref = loot_ref.get("item") if isinstance(loot_ref, dict) else loot_ref
                item_id = extract_id_from_ref(item_ref)
                if not item_id:
                    continue
                if item_limit >= 0 and len(fetched_items) >= item_limit and item_id not in fetched_items:
                    counts["truncation"]["items"] += 1
                    continue
                fallback_name = (item_ref or {}).get("name") if isinstance(item_ref, dict) else ""
                try:
                    item_metadata = fetch_blizzard_item_metadata(
                        token,
                        item_id,
                        region,
                        season.get("locale") or locale,
                        fallback_name=fallback_name,
                    )
                except Exception as error:
                    counts["fetchFailures"].append(
                        {"type": "item", "id": str(item_id), "name": fallback_name or "", "message": str(error)}
                    )
                    continue
                item_payload = item_metadata.get("payload") or {}
                slot = item_slot_from_payload(item_payload) or item_metadata.get("fallbackSlot") or ""
                if not item_payload_is_equipment_loot(item_payload, slot):
                    counts["skippedNonGearLoot"] += 1
                    if len(counts["skippedNonGearLootExamples"]) < 5:
                        counts["skippedNonGearLootExamples"].append({"itemId": str(item_id), "name": fallback_name or f"Item {item_id}"})
                    continue
                media_payload = item_metadata.get("media") or {}
                item_name = item_payload.get("name") or fallback_name or f"Item {item_id}"
                encounter["items"].append(
                    {
                        "id": f"{instance_id}:{encounter_id}:{item_id}",
                        "itemId": str(item_id),
                        "name": item_name,
                        "slot": slot,
                        "quality": (item_payload.get("quality") or {}).get("name") or "",
                        "iconUrl": icon_url_from_media(media_payload),
                        "payload": item_payload,
                        "sourceStatus": "verified",
                    }
                )
                fetched_items.add(item_id)
            instance["encounters"].append(encounter)
        instances.append(instance)
    gaps = []
    if raid_membership_gap:
        gaps.append(raid_membership_gap)
    if raid_fallback_gap:
        gaps.append(raid_fallback_gap)
    for boundary, omitted_count in counts["truncation"].items():
        if omitted_count:
            gaps.append(
                {
                    "kind": "cap",
                    "boundary": boundary,
                    "identity": f"journal:{boundary}",
                    "omittedCount": omitted_count,
                    "evidenceRef": "blizzard:game-data:journal",
                }
            )
    for error in counts["errors"]:
        gaps.append(
            {
                "kind": "fetch_failure",
                "boundary": "raidSelection",
                "identity": "journal:raid-selection",
                "omittedCount": 0,
                "evidenceRef": "blizzard:game-data:journal",
                "message": str(error),
            }
        )
    for failure in counts["fetchFailures"]:
        gaps.append(
            {
                "kind": "fetch_failure",
                "boundary": str(failure.get("type") or "resource"),
                "identity": str(failure.get("id") or "unknown"),
                "omittedCount": 0,
                "evidenceRef": "blizzard:game-data:journal",
                "message": str(failure.get("message") or ""),
            }
        )
    counts["fetchFailureCount"] = len(counts["fetchFailures"]) + len(counts["errors"])
    counts["gaps"] = gaps
    blocker_code_by_gap_kind = {
        "cap": "SOURCE_CAP_TRUNCATED",
        "fallback": "SOURCE_FALLBACK_USED",
        "fetch_failure": "SOURCE_FETCH_FAILED",
        "membership": "SOURCE_MEMBERSHIP_INCOMPLETE",
    }
    gap_count_by_blocker_code = {}
    for gap in gaps:
        blocker_code = blocker_code_by_gap_kind.get(
            gap["kind"],
            "SOURCE_DISCOVERY_GAP",
        )
        gap_count_by_blocker_code[blocker_code] = (
            gap_count_by_blocker_code.get(blocker_code, 0) + 1
        )
    counts["blockerCodes"] = sorted(gap_count_by_blocker_code)
    counts["blockers"] = [
        (
            f"{blocker_code}: "
            f"{gap_count_by_blocker_code[blocker_code]} "
            "Journal discovery gap(s)"
        )
        for blocker_code in counts["blockerCodes"]
    ]
    counts["membershipComplete"] = not gaps
    counts["truncated"] = any(counts["truncation"].values())
    counts["sourceStatus"] = "blocked" if gaps else "verified"
    return {"season": season, "instances": instances, "counts": counts}


def _normalise_item_metadata_refs(item_refs):
    refs_by_id = {}
    for ref in item_refs or []:
        if isinstance(ref, str):
            ref = {"itemId": ref}
        if not isinstance(ref, dict):
            continue
        item_id = str(ref.get("itemId") or ref.get("item_id") or ref.get("id") or "").strip()
        if not item_id:
            continue
        entry = refs_by_id.setdefault(
            item_id,
            {
                "itemId": item_id,
                "name": "",
                "slot": "",
                "reasons": [],
                "templates": [],
            },
        )
        if not entry["name"]:
            entry["name"] = str(ref.get("name") or ref.get("displayName") or ref.get("localizedName") or "").strip()
        if not entry["slot"]:
            entry["slot"] = str(ref.get("slot") or ref.get("simcSlot") or "").strip()
        entry["reasons"] = unique_text_list([*entry.get("reasons", []), *(ref.get("reasons") or [])])
        entry["templates"].extend(ref.get("templates") or [])
    return list(refs_by_id.values())


def refresh_websim_item_metadata_postgres(
    item_refs,
    *,
    region=DEFAULT_REGION,
    locale=DEFAULT_LOCALE,
    token=None,
    store=None,
    stage_callback=None,
):
    store = store or cache_store_from_env()
    refs = _normalise_item_metadata_refs(item_refs)
    checked_at = utc_now()
    payload = {
        "runner": "postgres",
        "region": region,
        "locale": locale,
        "checkedAt": checked_at,
        "requested": len(refs),
        "items": 0,
        "missingIcon": 0,
        "savedItems": [],
        "errors": [],
    }
    if not refs:
        payload["status"] = "blocked"
        payload["sourceStatus"] = "blocked"
        payload["errors"].append("no item metadata refs provided")
        store.save_sync_state(ITEM_METADATA_REFRESH_SYNC_KEY, payload, checked_at)
        return payload
    token = token or get_blizzard_access_token(region)
    _emit(stage_callback, "item_metadata", "start", requested=len(refs))
    for ref in refs:
        item_id = ref["itemId"]
        try:
            item_metadata = fetch_blizzard_item_metadata(
                token,
                item_id,
                region,
                locale,
                fallback_name=ref.get("name") or "",
                fallback_slot=ref.get("slot") or "",
            )
            saved = store.save_websim_item_metadata(
                item_id,
                item_metadata.get("payload") or {},
                item_metadata.get("media") or {},
                fallback_slot=item_metadata.get("fallbackSlot") or ref.get("slot") or "",
                fallback_name=item_metadata.get("fallbackName") or ref.get("name") or "",
                english_payload=item_metadata.get("englishPayload") or {},
                locale=item_metadata.get("locale") or locale,
            )
            if not saved:
                payload["errors"].append(f"{item_id}: metadata save returned empty result")
                continue
            payload["items"] += 1
            if not saved.get("iconUrl"):
                payload["missingIcon"] += 1
            payload["savedItems"].append(
                {
                    "itemId": item_id,
                    "displayName": saved.get("displayName") or "",
                    "slot": saved.get("slot") or "",
                    "iconUrl": saved.get("iconUrl") or "",
                    "reasons": ref.get("reasons") or [],
                }
            )
        except Exception as error:
            payload["errors"].append(f"{item_id}: {error}")
    payload["status"] = "verified" if payload["items"] == payload["requested"] and not payload["errors"] else (
        "partial" if payload["items"] else "blocked"
    )
    payload["sourceStatus"] = payload["status"]
    store.save_sync_state(ITEM_METADATA_REFRESH_SYNC_KEY, payload, checked_at)
    _emit(
        stage_callback,
        "item_metadata",
        "complete",
        sourceStatus=payload["status"],
        items=payload["items"],
        errors=len(payload["errors"]),
    )
    return payload


def refresh_websim_item_metadata_gaps_postgres(
    *,
    limit=200,
    region=DEFAULT_REGION,
    locale=DEFAULT_LOCALE,
    token=None,
    store=None,
    stage_callback=None,
):
    store = store or cache_store_from_env()
    gaps = store.community_gear_template_item_metadata_gaps(limit=limit)
    payload = refresh_websim_item_metadata_postgres(
        gaps,
        region=region,
        locale=locale,
        token=token,
        store=store,
        stage_callback=stage_callback,
    )
    payload["gapCount"] = len(gaps)
    payload["gaps"] = gaps[:20]
    store.save_sync_state(ITEM_METADATA_REFRESH_SYNC_KEY, payload, payload.get("checkedAt") or utc_now())
    return payload


def refresh_websim_item_metadata_item_gaps_postgres(
    *,
    limit=200,
    region=DEFAULT_REGION,
    locale=DEFAULT_LOCALE,
    token=None,
    store=None,
    stage_callback=None,
):
    store = store or cache_store_from_env()
    gaps = store.websim_item_metadata_gaps(limit=limit)
    payload = refresh_websim_item_metadata_postgres(
        gaps,
        region=region,
        locale=locale,
        token=token,
        store=store,
        stage_callback=stage_callback,
    )
    payload["gapCount"] = len(gaps)
    payload["gaps"] = gaps[:20]
    store.save_sync_state(ITEM_METADATA_REFRESH_SYNC_KEY, payload, payload.get("checkedAt") or utc_now())
    return payload


def _raiderio_target_spec_ids():
    raw = str(
        os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS")
        or ""
    ).strip()
    if not raw:
        return []
    expected = set(expected_spec_pairs())
    targets = []
    for token in (
        raw.replace("/", ":")
        .replace(";", " ")
        .replace(",", " ")
        .split()
    ):
        parts = token.split(":")
        if len(parts) != 2:
            continue
        spec_id = (
            f"{slugify(parts[0], '')}:{slugify(parts[1], '')}"
        )
        if spec_id in expected and spec_id not in targets:
            targets.append(spec_id)
    return targets


def _raiderio_row_spec_id(row):
    row = row if isinstance(row, dict) else {}
    class_key = slugify(
        row.get("classKey")
        or row.get("classSlug"),
        "",
    )
    spec_key = slugify(
        row.get("specKey")
        or row.get("specSlug"),
        "",
    )
    return f"{class_key}:{spec_key}" if class_key and spec_key else ""


def _raiderio_profile_merge_key(profile):
    profile = profile if isinstance(profile, dict) else {}
    identity = str(
        profile.get("sourceIdentity") or ""
    ).strip().lower()
    if identity:
        return f"identity:{identity}"
    return "|".join(
        [
            str(profile.get("region") or "").strip().lower(),
            str(
                profile.get("realmSlug")
                or profile.get("realm")
                or ""
            ).strip().lower(),
            str(
                profile.get("name")
                or profile.get("characterName")
                or ""
            ).strip().lower(),
            _raiderio_row_spec_id(profile),
        ]
    )


def _merge_raiderio_rows(cached_rows, refreshed_rows, key_builder):
    merged = {}
    for row in [*(cached_rows or []), *(refreshed_rows or [])]:
        if not isinstance(row, dict):
            continue
        key = str(key_builder(row) or "").strip()
        if key:
            merged[key] = row
    return list(merged.values())


def _merge_targeted_raiderio_payload(
    cached,
    refreshed,
    target_specs,
):
    cached = dict(cached or {})
    refreshed = dict(refreshed or {})
    targets = [
        str(spec_id or "").strip()
        for spec_id in target_specs or []
        if str(spec_id or "").strip()
    ]
    if (
        not cached
        or not targets
        or str(cached.get("seasonSlug") or "").strip()
        != str(refreshed.get("seasonSlug") or "").strip()
    ):
        return refreshed

    profiles = _merge_raiderio_rows(
        cached.get("profiles"),
        refreshed.get("profiles"),
        _raiderio_profile_merge_key,
    )
    templates = _merge_raiderio_rows(
        cached.get("communityTemplates"),
        refreshed.get("communityTemplates"),
        lambda row: row.get("id"),
    )
    aggregates = _merge_raiderio_rows(
        cached.get("specAggregates"),
        refreshed.get("specAggregates"),
        lambda row: (
            f"{_raiderio_row_spec_id(row)}:"
            f"{slugify(row.get('role'), '')}"
        ),
    )
    runs = _merge_raiderio_rows(
        cached.get("runs"),
        refreshed.get("runs"),
        lambda row: (
            f"{str(row.get('region') or '').strip().lower()}:"
            f"{row.get('runId') or row.get('id') or ''}"
        ),
    )
    merged_status = (
        "synced"
        if str(
            cached.get("sourceStatus")
            or cached.get("status")
        )
        == "synced"
        and str(
            refreshed.get("sourceStatus")
            or refreshed.get("status")
        )
        == "synced"
        else "partial"
    )
    payload = {
        **cached,
        **refreshed,
        "sourceStatus": merged_status,
        "status": merged_status,
        "errors": unique_text_list(
            [
                *(cached.get("errors") or []),
                *(refreshed.get("errors") or []),
            ]
        )[:12],
        "runCount": max(
            int(cached.get("runCount") or 0),
            int(refreshed.get("runCount") or 0),
            len(runs),
        ),
        "profileCount": len(profiles),
        "profiles": profiles,
        "communityTemplates": templates,
        "specAggregates": aggregates,
        "runs": runs[:400],
        "targetedMerge": {
            "schemaRevision":
                "raiderio-targeted-cache-merge-v1",
            "targetSpecs": targets,
            "cachedProfileCount": len(
                cached.get("profiles") or []
            ),
            "refreshedProfileCount": len(
                refreshed.get("profiles") or []
            ),
            "mergedProfileCount": len(profiles),
            "cachedTemplateCount": len(
                cached.get("communityTemplates") or []
            ),
            "refreshedTemplateCount": len(
                refreshed.get("communityTemplates") or []
            ),
            "mergedTemplateCount": len(templates),
        },
    }
    for key in (
        "regionCoverage",
        "specCoverage",
        "targetItemCoverage",
        "targetMatrix",
    ):
        if cached.get(key) not in (None, {}, []):
            payload[key] = cached[key]
    return payload


def sync_raiderio_cache_postgres(force=False, stage_callback=None, store=None):
    store = store or cache_store_from_env()
    _emit(stage_callback, "raiderio", "start", force=bool(force))
    cached = dict(store.get_raiderio_payload() or {})
    try:
        conn = sqlite3.connect(":memory:")
        try:
            payload = sync_raiderio_cache(conn, force=force, stage_callback=stage_callback)
        finally:
            conn.close()
    except Exception as error:
        if not cached:
            raise
        cached_errors = list(cached.get("errors") or [])
        cached_errors.append(f"PostgreSQL Raider.IO refresh failed: {error}")
        cached["errors"] = cached_errors[:12]
        cached["sourceStatus"] = "stale"
        cached["status"] = "stale"
        payload = cached
    payload = dict(payload or {})
    payload["runner"] = "postgres"
    payload.setdefault("sourceStatus", payload.get("status") or "blocked")
    payload.setdefault("status", payload.get("sourceStatus") or "blocked")
    payload.setdefault("checkedAt", utc_now())
    source_status = str(payload.get("sourceStatus") or payload.get("status") or "blocked").strip().lower()
    if source_status in {"blocked", "failed", "stale"} and cached:
        cached_errors = list(cached.get("errors") or [])
        cached_errors.extend(payload.get("errors") or [])
        cached["errors"] = unique_text_list(cached_errors)[:12]
        cached["sourceStatus"] = "stale"
        cached["status"] = "stale"
        cached["runner"] = "postgres"
        payload = cached
        source_status = "stale"
    if source_status not in {"blocked", "failed", "stale"}:
        payload = _merge_targeted_raiderio_payload(
            cached,
            payload,
            _raiderio_target_spec_ids(),
        )
        source_status = str(
            payload.get("sourceStatus")
            or payload.get("status")
            or source_status
        ).strip().lower()
        store.save_raiderio_payload(payload)
    _emit(
        stage_callback,
        "raiderio",
        "complete",
        sourceStatus=payload.get("sourceStatus") or "",
        runCount=payload.get("runCount") or 0,
        profileCount=payload.get("profileCount") or 0,
    )
    return payload


def _percent_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = int(default)
    return max(1, min(100, value))


def _simc_talent_context(talent):
    payload = talent.get("payload") if isinstance(talent.get("payload"), dict) else {}
    tree_type = str(payload.get("treeType") or talent.get("treeType") or "").strip()
    hero_key = str(payload.get("heroKey") or "").strip() if tree_type == "hero" else ""
    return (
        str(talent.get("classKey") or "").strip(),
        str(talent.get("specKey") or "").strip(),
        tree_type,
        hero_key,
    )


def _canonical_simc_rank_entries(raw_entries):
    if not isinstance(raw_entries, list) or not raw_entries or any(
        not isinstance(entry, dict) for entry in raw_entries
    ):
        return ()
    canonical = []
    seen = set()
    integer_fields = (
        "traitId",
        "traitDefinitionId",
        "spellId",
        "selectionIndex",
        "rank",
        "points",
        "pointStart",
        "pointEnd",
    )
    for entry in raw_entries:
        if any(
            field not in entry
            or not isinstance(entry.get(field), int)
            or isinstance(entry.get(field), bool)
            for field in integer_fields
        ):
            return ()
        item = tuple(int(entry[field]) for field in integer_fields)
        trait_id, trait_definition_id, spell_id, selection_index, rank, points, point_start, point_end = item
        identity = (trait_id, spell_id, selection_index)
        if (
            trait_id <= 0
            or trait_definition_id <= 0
            or spell_id <= 0
            or selection_index < 0
            or rank <= 0
            or points <= 0
            or point_start <= 0
            or point_end < point_start
            or identity in seen
        ):
            return ()
        seen.add(identity)
        canonical.append(item)
    canonical.sort(key=lambda item: (item[3], item[0], item[2]))
    total_points = 0
    for index, item in enumerate(canonical, start=1):
        _trait_id, _definition_id, _spell_id, _selection_index, rank, points, point_start, point_end = item
        if rank != index or point_start != total_points + 1 or point_end != total_points + points:
            return ()
        total_points += points
    return tuple(canonical)


def _legacy_visual_slot_deduplication_is_safe(previous_row, candidate_node_ids, candidate_visual_slots):
    if not isinstance(previous_row, dict):
        return False
    raw_slots = previous_row.get("visualSlots")
    if not isinstance(raw_slots, list):
        return False
    previous_node_ids = {
        str(node_id or "").strip()
        for node_id in (previous_row.get("nodeIds") or [])
        if str(node_id or "").strip()
    }
    candidate_node_ids = {
        str(node_id or "").strip()
        for node_id in (candidate_node_ids or set())
        if str(node_id or "").strip()
    }
    if not previous_node_ids or not candidate_node_ids:
        return False
    duplicate_node_ids = set()
    for raw_slot in raw_slots:
        if not isinstance(raw_slot, dict):
            continue
        try:
            slot_key = (int(raw_slot.get("row") or 0), int(raw_slot.get("col") or 0))
        except (TypeError, ValueError):
            continue
        if slot_key[0] <= 0 or slot_key[1] <= 0:
            continue
        baseline_slot_nodes = {
            str(node_id or "").strip()
            for node_id in (raw_slot.get("nodeIds") or [])
            if str(node_id or "").strip()
        }
        if len(baseline_slot_nodes) < 2:
            continue
        retained_slot_nodes = baseline_slot_nodes & candidate_node_ids
        if len(retained_slot_nodes) != 1:
            return False
        if set(candidate_visual_slots.get(slot_key) or set()) != retained_slot_nodes:
            return False
        duplicate_node_ids.update(baseline_slot_nodes)
    removed_node_ids = previous_node_ids - candidate_node_ids
    return bool(
        removed_node_ids
        and duplicate_node_ids
        and removed_node_ids <= duplicate_node_ids
        and candidate_node_ids == previous_node_ids - removed_node_ids
    )


def _legacy_foreign_hero_spec_cleanup_is_safe(previous_row, candidate_node_ids):
    if not isinstance(previous_row, dict):
        return False
    previous_node_ids = {
        str(node_id or "").strip()
        for node_id in (previous_row.get("nodeIds") or [])
        if str(node_id or "").strip()
    }
    candidate_node_ids = {
        str(node_id or "").strip()
        for node_id in (candidate_node_ids or set())
        if str(node_id or "").strip()
    }
    foreign_spec_node_ids = {
        str(node_id or "").strip()
        for node_id in (previous_row.get("foreignSpecNodeIds") or [])
        if str(node_id or "").strip()
    }
    removed_node_ids = previous_node_ids - candidate_node_ids
    return bool(
        foreign_spec_node_ids
        and removed_node_ids
        and removed_node_ids == foreign_spec_node_ids
        and candidate_node_ids == previous_node_ids - removed_node_ids
    )


def _same_source_self_override_node_recovery_is_safe(
    previous_row,
    candidate_node_ids,
    candidate_parent_map,
    self_override_node_ids,
):
    if not isinstance(previous_row, dict):
        return False
    previous_node_ids = {
        str(node_id or "").strip()
        for node_id in (previous_row.get("nodeIds") or [])
        if str(node_id or "").strip()
    }
    candidate_node_ids = {
        str(node_id or "").strip()
        for node_id in (candidate_node_ids or set())
        if str(node_id or "").strip()
    }
    added_node_ids = candidate_node_ids - previous_node_ids
    self_override_node_ids = {
        str(node_id or "").strip()
        for node_id in (self_override_node_ids or set())
        if str(node_id or "").strip()
    }
    if not previous_node_ids or not added_node_ids or not previous_node_ids <= candidate_node_ids:
        return False
    if not added_node_ids <= self_override_node_ids:
        return False
    raw_parent_map = previous_row.get("parentIdsByNode") or []
    if not isinstance(raw_parent_map, list):
        return False
    previous_parent_map = {}
    for raw_entry in raw_parent_map:
        if not isinstance(raw_entry, (list, tuple)) or len(raw_entry) != 2:
            return False
        node_id = str(raw_entry[0] or "").strip()
        raw_parent_ids = raw_entry[1]
        if not node_id or not isinstance(raw_parent_ids, list):
            return False
        previous_parent_map[node_id] = {
            str(parent_id or "").strip()
            for parent_id in raw_parent_ids
            if str(parent_id or "").strip()
        }
    if set(previous_parent_map) != previous_node_ids:
        return False
    normalized_candidate_parent_map = {
        str(node_id or "").strip(): {
            str(parent_id or "").strip()
            for parent_id in (parent_ids or [])
            if str(parent_id or "").strip()
        }
        for node_id, parent_ids in (candidate_parent_map or {}).items()
        if str(node_id or "").strip()
    }
    if set(normalized_candidate_parent_map) != candidate_node_ids:
        return False
    return all(
        previous_parent_ids <= normalized_candidate_parent_map.get(node_id, set())
        for node_id, previous_parent_ids in previous_parent_map.items()
    )


def validate_simc_generated_data_candidate(simc_data, previous_state=None):
    simc_data = simc_data if isinstance(simc_data, dict) else {}
    previous_state = previous_state if isinstance(previous_state, dict) else {}
    raw_talents = simc_data.get("talents") or []
    talents = list(raw_talents) if isinstance(raw_talents, list) else []
    if not talents:
        detail = str(simc_data.get("extractionError") or simc_data.get("traitEdgeError") or "").strip()
        raise RuntimeError(
            "SimulationCraft talent catalog is empty; preserving the current PostgreSQL talent tree"
            + (f": {detail}" if detail else "")
        )
    if any(not isinstance(talent, dict) for talent in talents):
        raise RuntimeError(
            "SimulationCraft talent payload is invalid; preserving the current PostgreSQL talent tree"
        )
    raw_source = simc_data.get("source")
    candidate_source = str(raw_source or "").strip()
    if not candidate_source:
        raise RuntimeError(
            "SimulationCraft source identity is missing; preserving the current PostgreSQL talent tree"
        )
    if not isinstance(raw_source, str) or raw_source != candidate_source:
        raise RuntimeError(
            "SimulationCraft source identity is not canonical; preserving the current PostgreSQL talent tree"
        )
    if not str(simc_data.get("build") or "").strip():
        raise RuntimeError(
            "SimulationCraft talent build identity is missing; preserving the current PostgreSQL talent tree"
        )

    required_specs = set(expected_spec_pairs())
    required_heroes = set(expected_hero_tree_triplets())
    ids_by_context = {}
    nodes_by_context = {}
    talent_ids = set()
    parent_ids_by_talent_id = {}
    signature_identity_by_talent_id = {}
    content_identity_by_talent_id = {}
    visual_slots_by_context = {}
    self_override_node_ids_by_context = {}
    for talent in talents:
        payload = talent.get("payload") if isinstance(talent.get("payload"), dict) else {}
        raw_talent_id = talent.get("id")
        talent_id = str(raw_talent_id or "").strip()
        if not talent_id or talent_id in talent_ids:
            raise RuntimeError(
                "SimulationCraft talent identifiers are invalid or duplicated; "
                "preserving the current PostgreSQL talent tree"
            )
        talent_ids.add(talent_id)

        raw_class_key = talent.get("classKey")
        raw_spec_key = talent.get("specKey")
        raw_top_tree_type = talent.get("treeType")
        raw_payload_tree_type = payload.get("treeType")
        raw_tree_id = talent.get("treeId")
        class_key = str(raw_class_key or "").strip()
        spec_key = str(raw_spec_key or "").strip()
        top_tree_type = str(raw_top_tree_type or "").strip()
        payload_tree_type = str(raw_payload_tree_type or "").strip()
        tree_type = payload_tree_type or top_tree_type
        raw_payload_hero_key = payload.get("heroKey")
        raw_top_hero_key = talent.get("heroKey")
        payload_hero_key = str(raw_payload_hero_key or "").strip()
        top_hero_key = str(raw_top_hero_key or "").strip()
        hero_key = payload_hero_key if tree_type == "hero" else ""
        tree_id = str(raw_tree_id or "").strip()
        raw_payload_tree_id = payload.get("treeId")
        payload_tree_id = str(raw_payload_tree_id or "").strip()
        required_identity_values = (
            (raw_talent_id, talent_id),
            (raw_class_key, class_key),
            (raw_spec_key, spec_key),
            (raw_top_tree_type, top_tree_type),
            (raw_payload_tree_type, payload_tree_type),
            (raw_tree_id, tree_id),
            (raw_payload_hero_key, payload_hero_key),
        )
        optional_identity_values = (
            (raw_top_hero_key, top_hero_key),
            (raw_payload_tree_id, payload_tree_id),
        )
        if any(not isinstance(raw, str) or raw != normalized for raw, normalized in required_identity_values) or any(
            raw is not None and (not isinstance(raw, str) or raw != normalized)
            for raw, normalized in optional_identity_values
        ):
            raise RuntimeError(
                "SimulationCraft talent identity is not canonical; "
                f"talent {talent_id}; preserving the current PostgreSQL talent tree"
            )
        expected_tree_id = {
            "class": f"class:{class_key}",
            "spec": f"spec:{class_key}:{spec_key}",
            "hero": f"hero:{hero_key}",
        }.get(tree_type, "")
        inconsistent_identity = (
            not class_key
            or not spec_key
            or not top_tree_type
            or not payload_tree_type
            or top_tree_type != payload_tree_type
            or tree_type not in {"class", "spec", "hero"}
            or (tree_type == "hero" and not hero_key)
            or (tree_type != "hero" and bool(payload_hero_key or top_hero_key))
            or (top_hero_key and top_hero_key != hero_key)
            or not tree_id
            or tree_id != expected_tree_id
            or (payload_tree_id and payload_tree_id != tree_id)
        )
        if inconsistent_identity:
            raise RuntimeError(
                "SimulationCraft talent tree identity is inconsistent; "
                f"talent {talent_id}; preserving the current PostgreSQL talent tree"
            )

        try:
            row_index = int(talent.get("row") or 0)
            col_index = int(talent.get("col") or 0)
            spell_id = int(talent.get("spellId") or 0)
            node_id = int(payload.get("nodeId") or 0)
            trait_id = int(payload.get("traitId") or 0)
        except (TypeError, ValueError):
            row_index = col_index = spell_id = node_id = trait_id = 0
        if (
            row_index <= 0
            or col_index <= 0
            or spell_id <= 0
            or node_id <= 0
            or trait_id <= 0
            or not str(talent.get("name") or "").strip()
        ):
            raise RuntimeError(
                "SimulationCraft talent read-model shape is invalid; "
                f"talent {talent_id}; preserving the current PostgreSQL talent tree"
            )
        canonical_rank_entries = _canonical_simc_rank_entries(payload.get("rankEntries"))
        signature_integer_fields = (
            "selectionIndex",
            "nodeType",
            "rank",
            "maxRank",
            "selectedRank",
            "grantedRank",
            "pointRequirement",
        )
        if any(
            field not in payload
            or not isinstance(payload.get(field), int)
            or isinstance(payload.get(field), bool)
            for field in signature_integer_fields
        ):
            canonical_rank_entries = ()
        signature_integer_values = {
            field: (
                payload.get(field)
                if isinstance(payload.get(field), int) and not isinstance(payload.get(field), bool)
                else 0
            )
            for field in signature_integer_fields
        }
        selection_index = signature_integer_values["selectionIndex"]
        node_type = signature_integer_values["nodeType"]
        rank = signature_integer_values["rank"]
        max_rank = signature_integer_values["maxRank"]
        selected_rank = signature_integer_values["selectedRank"]
        granted_rank = signature_integer_values["grantedRank"]
        point_requirement = signature_integer_values["pointRequirement"]
        raw_granted = payload.get("granted")
        raw_choice_group = payload.get("choiceGroup")
        choice_group = str(raw_choice_group or "").strip()
        raw_parent_mode = payload.get("parentMode")
        parent_mode = str(raw_parent_mode or "any").strip().lower()
        raw_shape = payload.get("shape")
        shape = str(raw_shape or "").strip().lower()
        total_rank_points = sum(entry[5] for entry in canonical_rank_entries)
        first_rank_entry = canonical_rank_entries[0] if canonical_rank_entries else ()
        invalid_rank_shape = (
            not canonical_rank_entries
            or selection_index < 0
            or node_type < 0
            or rank <= 0
            or max_rank != rank
            or rank != total_rank_points
            or selected_rank < 0
            or selected_rank > max_rank
            or granted_rank < 0
            or granted_rank > max_rank
            or not isinstance(raw_granted, bool)
            or raw_granted != (granted_rank > 0)
            or not isinstance(raw_choice_group, str)
            or raw_choice_group != choice_group
            or point_requirement < 0
            or (raw_parent_mode is not None and (not isinstance(raw_parent_mode, str) or raw_parent_mode != parent_mode))
            or parent_mode not in {"any", "all"}
            or not isinstance(raw_shape, str)
            or raw_shape != shape
            or shape not in {"circle", "square", "choice", "apex"}
            or not first_rank_entry
            or trait_id != first_rank_entry[0]
            or spell_id != first_rank_entry[2]
            or selection_index != first_rank_entry[3]
        )
        if invalid_rank_shape:
            raise RuntimeError(
                "SimulationCraft talent rankEntries payload is invalid; "
                f"talent {talent_id}; preserving the current PostgreSQL talent tree"
            )
        raw_parent_ids = payload.get("parentIds")
        if not isinstance(raw_parent_ids, list) or any(
            not isinstance(parent_id, str)
            or not parent_id.strip()
            or parent_id != parent_id.strip()
            for parent_id in raw_parent_ids
        ):
            raise RuntimeError(
                "SimulationCraft talent parentIds payload is invalid; "
                f"talent {talent_id}; preserving the current PostgreSQL talent tree"
            )
        parent_ids_by_talent_id[talent_id] = list(raw_parent_ids)
        signature_identity_by_talent_id[talent_id] = (
            row_index,
            col_index,
            spell_id,
            node_id,
            trait_id,
            canonical_rank_entries,
            selection_index,
            node_type,
            rank,
            max_rank,
            selected_rank,
            granted_rank,
            raw_granted,
            choice_group,
            point_requirement,
            parent_mode,
            shape,
        )
        content_identity_by_talent_id[talent_id] = simc_talent_persisted_content_identity(
            talent_id,
            class_key,
            spec_key,
            tree_id,
            row_index,
            col_index,
            spell_id,
            talent.get("name"),
            payload,
        )

        context = (class_key, spec_key, tree_type, hero_key)
        ids_by_context.setdefault(context, set()).add(talent_id)
        nodes_by_context[context] = nodes_by_context.get(context, 0) + 1
        if not choice_group and shape != "choice":
            visual_slots_by_context.setdefault(context, {}).setdefault(
                (row_index, col_index), set()
            ).add(talent_id)
        try:
            override_spell_id = int(payload.get("overrideSpellId") or 0)
        except (TypeError, ValueError):
            override_spell_id = 0
        if override_spell_id > 0 and override_spell_id == spell_id:
            self_override_node_ids_by_context.setdefault(context, set()).add(talent_id)

    try:
        declared_dependencies = int(simc_data.get("dependencies") or 0)
    except (TypeError, ValueError):
        declared_dependencies = 0
    dependency_node_count = 0
    has_parent_ids = any(parent_ids_by_talent_id.values())
    if (
        declared_dependencies <= 0
        or not has_parent_ids
        or not str(simc_data.get("traitEdgeSource") or "").strip()
    ):
        detail = str(simc_data.get("traitEdgeError") or "").strip()
        raise RuntimeError(
            "SimulationCraft talent dependency edges are unavailable; "
            "preserving the current PostgreSQL talent tree"
            + (f": {detail}" if detail else "")
        )

    actual_specs = {
        f"{talent.get('classKey')}:{talent.get('specKey')}"
        for talent in talents
        if talent.get("classKey") and talent.get("specKey")
    }
    missing_specs = sorted(required_specs - actual_specs)
    if missing_specs:
        raise RuntimeError(
            "SimulationCraft specialization coverage is incomplete; "
            f"missing {', '.join(missing_specs[:8])}; preserving the current PostgreSQL talent tree"
        )

    actual_heroes = {
        f"{class_key}:{spec_key}:{hero_key}"
        for class_key, spec_key, tree_type, hero_key in (_simc_talent_context(talent) for talent in talents)
        if tree_type == "hero" and class_key and spec_key and hero_key
    }
    missing_heroes = sorted(required_heroes - actual_heroes)
    if missing_heroes:
        raise RuntimeError(
            "SimulationCraft hero-tree coverage is incomplete; "
            f"missing {', '.join(missing_heroes[:8])}; preserving the current PostgreSQL talent tree"
        )

    dependency_refs = 0
    dependent_contexts = set()
    parent_nodes_by_context = {}
    dependency_refs_by_context = {}
    parents_by_context = {}
    invalid_parent_refs = []
    malformed_parent_refs = []
    for talent in talents:
        context = _simc_talent_context(talent)
        talent_id = str(talent.get("id") or "").strip()
        parent_ids = parent_ids_by_talent_id[talent_id]
        parents_by_context.setdefault(context, {})[talent_id] = parent_ids
        if talent_id in parent_ids or len(parent_ids) != len(set(parent_ids)):
            malformed_parent_refs.append(talent_id)
        dependency_refs += len(parent_ids)
        dependency_refs_by_context[context] = dependency_refs_by_context.get(context, 0) + len(parent_ids)
        if parent_ids:
            dependency_node_count += 1
            dependent_contexts.add(context)
            parent_nodes_by_context[context] = parent_nodes_by_context.get(context, 0) + 1
        for parent_id in parent_ids:
            if parent_id not in ids_by_context.get(context, set()):
                invalid_parent_refs.append(f"{talent.get('id')}->{parent_id}")
                if len(invalid_parent_refs) >= 4:
                    break
        if len(invalid_parent_refs) >= 4:
            break
    if malformed_parent_refs:
        raise RuntimeError(
            "SimulationCraft talent dependency references are invalid or duplicated; "
            f"examples {', '.join(malformed_parent_refs[:4])}; preserving the current PostgreSQL talent tree"
        )
    if invalid_parent_refs:
        raise RuntimeError(
            "SimulationCraft talent dependency references leave their tree context; "
            f"examples {', '.join(invalid_parent_refs)}; preserving the current PostgreSQL talent tree"
        )
    for context, parent_map in parents_by_context.items():
        visit_state = {}

        def visit(node_id):
            state = visit_state.get(node_id, 0)
            if state == 1:
                context_label = ":".join(filter(None, context))
                raise RuntimeError(
                    "SimulationCraft talent dependency cycle detected for "
                    f"{context_label} at {node_id}; preserving the current PostgreSQL talent tree"
                )
            if state == 2:
                return
            visit_state[node_id] = 1
            for parent_id in parent_map.get(node_id, []):
                visit(parent_id)
            visit_state[node_id] = 2

        for talent_id in parent_map:
            visit(talent_id)
    if dependency_refs != declared_dependencies:
        raise RuntimeError(
            "SimulationCraft talent dependency count does not match parent references; "
            f"declared {declared_dependencies}, actual {dependency_refs}; "
            "preserving the current PostgreSQL talent tree"
        )
    if dependency_node_count <= 0:
        raise RuntimeError(
            "SimulationCraft talent dependency edges are unavailable; "
            "preserving the current PostgreSQL talent tree"
        )

    required_contexts = set()
    for spec_pair in required_specs:
        class_key, spec_key = spec_pair.split(":", 1)
        required_contexts.add((class_key, spec_key, "class", ""))
        required_contexts.add((class_key, spec_key, "spec", ""))
    for triplet in required_heroes:
        class_key, spec_key, hero_key = triplet.split(":", 2)
        required_contexts.add((class_key, spec_key, "hero", hero_key))
    missing_dependency_contexts = sorted(required_contexts - dependent_contexts)
    if missing_dependency_contexts:
        labels = [":".join(filter(None, context)) for context in missing_dependency_contexts[:8]]
        raise RuntimeError(
            "SimulationCraft tree dependency coverage is incomplete; "
            f"missing {', '.join(labels)}; preserving the current PostgreSQL talent tree"
        )

    min_parent_coverage = _percent_env("WOW_WEBSIM_SIMC_MIN_PARENT_COVERAGE_PERCENT", 80)
    for context in sorted(required_contexts):
        node_count = int(nodes_by_context.get(context) or 0)
        parent_count = int(parent_nodes_by_context.get(context) or 0)
        if node_count <= 0 or parent_count * 100 < node_count * min_parent_coverage:
            context_label = ":".join(filter(None, context))
            raise RuntimeError(
                "SimulationCraft talent dependency coverage is incomplete for "
                f"{context_label}: {parent_count}/{node_count} parent-bearing nodes is below "
                f"{min_parent_coverage}%; preserving the current PostgreSQL talent tree"
            )

    raw_presets = simc_data.get("presets") or []
    presets = list(raw_presets) if isinstance(raw_presets, list) else []
    preset_ids = set()
    profile_specs = set()
    profile_content_signatures = set()
    for preset in presets:
        if not isinstance(preset, dict):
            raise RuntimeError(
                "SimulationCraft profile preset payload is invalid; preserving the current PostgreSQL talent tree"
            )
        raw_preset_id = preset.get("id")
        raw_class_key = preset.get("classKey")
        raw_spec_key = preset.get("specKey")
        raw_profile = preset.get("profile")
        preset_id = str(raw_preset_id or "").strip()
        preset_class_key = str(raw_class_key or "").strip()
        preset_spec_key = str(raw_spec_key or "").strip()
        spec_pair = f"{preset_class_key}:{preset_spec_key}"
        profile = str(raw_profile or "").strip()
        if (
            not isinstance(raw_preset_id, str)
            or raw_preset_id != preset_id
            or not isinstance(raw_class_key, str)
            or raw_class_key != preset_class_key
            or not isinstance(raw_spec_key, str)
            or raw_spec_key != preset_spec_key
            or not isinstance(raw_profile, str)
            or not preset_id
            or preset_id in preset_ids
            or spec_pair not in required_specs
            or not profile
        ):
            raise RuntimeError(
                "SimulationCraft profile preset payload is invalid; preserving the current PostgreSQL talent tree"
            )
        preset_ids.add(preset_id)
        profile_specs.add(spec_pair)
        profile_content_signatures.add(
            (
                preset_class_key,
                preset_spec_key,
                hashlib.sha256(profile.encode("utf-8")).hexdigest(),
            )
        )

    profile_retirement = simc_data.get("profileRetirement")
    retired_profile_batches = set()
    if profile_retirement is not None:
        if not isinstance(profile_retirement, dict):
            raise RuntimeError(
                "SimulationCraft profile retirement policy is invalid; preserving the current PostgreSQL talent tree"
            )
        retirement_revision = str(profile_retirement.get("schemaRevision") or "").strip()
        retired_profile_batches = {
            str(batch or "").strip().upper()
            for batch in profile_retirement.get("retiredBatches") or []
            if str(batch or "").strip()
        }
        retirement_reason = str(profile_retirement.get("reason") or "").strip().lower()
        if (
            retirement_revision != SIMC_PROFILE_RETIREMENT_SCHEMA_REVISION
            or retired_profile_batches != {"MID1"}
            or "talent hashes changed" not in retirement_reason
        ):
            raise RuntimeError(
                "SimulationCraft profile retirement policy is not canonical; preserving the current PostgreSQL talent tree"
            )

    retired_batch_name = re.compile(r"(?:^|[\"'_ /-])MID1(?:$|[\"'_ /-])", re.IGNORECASE)
    retired_batch_actor = re.compile(
        r"^[A-Za-z][A-Za-z0-9_]*\s*=\s*[\"']?MID1(?:$|[\"'_ /-])",
        re.IGNORECASE,
    )

    def profile_contains_retired_batch(preset):
        if retired_batch_name.search(str(preset.get("name") or "")):
            return True
        for line in str(preset.get("profile") or "").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", ";")):
                continue
            if retired_batch_actor.search(stripped):
                return True
        return False

    if retired_profile_batches and any(profile_contains_retired_batch(preset) for preset in presets):
        raise RuntimeError(
            "SimulationCraft candidate still contains a retired profile batch; preserving the current PostgreSQL talent tree"
        )

    min_profile_coverage = _percent_env("WOW_WEBSIM_SIMC_MIN_PROFILE_COVERAGE_PERCENT", 80)
    min_profile_count = (len(required_specs) * min_profile_coverage + 99) // 100
    if len(profile_specs) < min_profile_count:
        raise RuntimeError(
            "SimulationCraft profile preset coverage is incomplete; "
            f"found {len(profile_specs)}, require at least {min_profile_count} of {len(required_specs)} specializations; "
            "preserving the current PostgreSQL talent tree"
        )

    graph_baseline = previous_state.get("graphBaseline")
    graph_baseline = graph_baseline if isinstance(graph_baseline, dict) else {}
    previous_simc = previous_state.get("simc") if isinstance(previous_state.get("simc"), dict) else {}
    candidate_counts = {
        "talents": len(talents),
        "profileSpecCoverage": len(profile_specs),
        "dependencies": dependency_refs,
        "dependencyNodes": dependency_node_count,
    }
    previous_source = str(previous_simc.get("source") or "").strip()
    same_source = bool(previous_source and previous_source == candidate_source)
    min_retention = _percent_env("WOW_WEBSIM_SIMC_MIN_BASELINE_RETENTION_PERCENT", 80)

    try:
        baseline_profile_count = int(graph_baseline.get("profiles") or 0)
    except (TypeError, ValueError):
        baseline_profile_count = 0
    if baseline_profile_count > 0 and not retired_profile_batches:
        candidate_profile_count = len(presets)
        if same_source and candidate_profile_count < baseline_profile_count:
            raise RuntimeError(
                "SimulationCraft candidate fell below the last-known-good same-source baseline; "
                f"profiles declined from {baseline_profile_count} to {candidate_profile_count}; "
                "preserving the current PostgreSQL talent tree"
            )
        if not same_source and candidate_profile_count * 100 < baseline_profile_count * min_retention:
            raise RuntimeError(
                "SimulationCraft candidate fell below the last-known-good baseline; "
                f"profiles retained {candidate_profile_count}/{baseline_profile_count}, "
                f"below {min_retention}%; preserving the current PostgreSQL talent tree"
            )

    for key, candidate_count in candidate_counts.items():
        baseline_value = graph_baseline.get(key) if key in graph_baseline else previous_simc.get(key)
        try:
            previous_count = int(baseline_value or 0)
        except (TypeError, ValueError):
            previous_count = 0
        if previous_count <= 0:
            continue
        if same_source and candidate_count < previous_count:
            raise RuntimeError(
                "SimulationCraft candidate fell below the last-known-good same-source baseline; "
                f"{key} declined from {previous_count} to {candidate_count}; "
                "preserving the current PostgreSQL talent tree"
            )
        if not same_source and candidate_count * 100 < previous_count * min_retention:
            raise RuntimeError(
                "SimulationCraft candidate fell below the last-known-good baseline; "
                f"{key} retained {candidate_count}/{previous_count}, below {min_retention}%; "
                "preserving the current PostgreSQL talent tree"
            )

    previous_profile_specs = {
        str(spec_pair or "").strip()
        for spec_pair in (graph_baseline.get("profileSpecs") or [])
        if str(spec_pair or "").strip()
    }
    missing_previous_profile_specs = sorted(previous_profile_specs - profile_specs)
    if same_source and missing_previous_profile_specs:
        raise RuntimeError(
            "SimulationCraft same-source profile specialization set declined; "
            f"missing {', '.join(missing_previous_profile_specs[:8])}; "
            "preserving the current PostgreSQL talent tree"
        )
    if not same_source and previous_profile_specs:
        retained_profile_specs = len(previous_profile_specs & profile_specs)
        if retained_profile_specs * 100 < len(previous_profile_specs) * min_retention:
            raise RuntimeError(
                "SimulationCraft profile specialization identities fell below the last-known-good baseline; "
                f"retained {retained_profile_specs}/{len(previous_profile_specs)}, below {min_retention}%; "
                "preserving the current PostgreSQL talent tree"
            )

    previous_profile_content_signatures = set()
    for raw_signature in graph_baseline.get("profileContentSignatures") or []:
        if not isinstance(raw_signature, (list, tuple)) or len(raw_signature) != 3:
            continue
        class_key, spec_key, profile_hash = (
            str(value or "").strip() for value in raw_signature
        )
        if class_key and spec_key and profile_hash:
            previous_profile_content_signatures.add((class_key, spec_key, profile_hash))
    missing_profile_content_signatures = (
        previous_profile_content_signatures - profile_content_signatures
    )
    if same_source and missing_profile_content_signatures and not retired_profile_batches:
        raise RuntimeError(
            "SimulationCraft same-source profile content identities declined; "
            f"missing {len(missing_profile_content_signatures)} of "
            f"{len(previous_profile_content_signatures)}; preserving the current PostgreSQL talent tree"
        )

    candidate_graphs = {}
    for context, parent_map in parents_by_context.items():
        graph_entries = sorted(
            (
                talent_id,
                *signature_identity_by_talent_id[talent_id],
                sorted(parent_ids),
            )
            for talent_id, parent_ids in parent_map.items()
        )
        content_entries = sorted(
            content_identity_by_talent_id[talent_id]
            for talent_id in parent_map
        )
        candidate_graphs[context] = {
            "nodeIds": [entry[0] for entry in graph_entries],
            "structureSignature": hashlib.sha256(
                json.dumps(
                    content_entries,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "parentIdsByNode": {
                entry[0]: set(entry[-1])
                for entry in graph_entries
            },
            "graphSignature": hashlib.sha256(
                json.dumps(graph_entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }

    baseline_rows = graph_baseline.get("contexts") or []
    for row in baseline_rows or []:
        if not isinstance(row, dict):
            continue
        context = (
            str(row.get("classKey") or "").strip(),
            str(row.get("specKey") or "").strip(),
            str(row.get("treeType") or "").strip(),
            str(row.get("heroKey") or "").strip(),
        )
        if context not in required_contexts:
            continue
        candidate_context_counts = {
            "nodes": int(nodes_by_context.get(context) or 0),
            "dependencyNodes": int(parent_nodes_by_context.get(context) or 0),
            "dependencies": int(dependency_refs_by_context.get(context) or 0),
        }
        legacy_visual_slot_deduplication = _legacy_visual_slot_deduplication_is_safe(
            row,
            ids_by_context.get(context) or set(),
            visual_slots_by_context.get(context) or {},
        )
        legacy_foreign_hero_spec_cleanup = _legacy_foreign_hero_spec_cleanup_is_safe(
            row,
            ids_by_context.get(context) or set(),
        )
        safe_legacy_normalization = (
            legacy_visual_slot_deduplication or legacy_foreign_hero_spec_cleanup
        )
        for key, candidate_count in candidate_context_counts.items():
            try:
                previous_count = int(row.get(key) or 0)
            except (TypeError, ValueError):
                previous_count = 0
            if previous_count <= 0:
                continue
            context_label = ":".join(filter(None, context))
            if same_source and candidate_count < previous_count:
                if safe_legacy_normalization:
                    continue
                raise RuntimeError(
                    "SimulationCraft tree context fell below the same-source baseline; "
                    f"{context_label} {key} declined from {previous_count} to {candidate_count}; "
                    "preserving the current PostgreSQL talent tree"
                )
            if not same_source and candidate_count * 100 < previous_count * min_retention:
                if safe_legacy_normalization:
                    continue
                raise RuntimeError(
                    "SimulationCraft tree context fell below the last-known-good baseline; "
                    f"{context_label} {key} retained {candidate_count}/{previous_count}, "
                    f"below {min_retention}%; preserving the current PostgreSQL talent tree"
                )

        candidate_graph = candidate_graphs.get(context) or {}
        previous_signature = str(row.get("graphSignature") or "").strip()
        candidate_signature = str(candidate_graph.get("graphSignature") or "").strip()
        previous_node_ids = {
            str(node_id or "").strip()
            for node_id in (row.get("nodeIds") or [])
            if str(node_id or "").strip()
        }
        candidate_node_ids = set(candidate_graph.get("nodeIds") or [])
        context_label = ":".join(filter(None, context))
        source_unknown_same_node_set = bool(
            not previous_source
            and previous_node_ids
            and candidate_node_ids == previous_node_ids
        )
        guarded_same_graph = same_source or source_unknown_same_node_set
        self_override_node_recovery = _same_source_self_override_node_recovery_is_safe(
            row,
            candidate_node_ids,
            candidate_graph.get("parentIdsByNode") or {},
            self_override_node_ids_by_context.get(context) or set(),
        )
        if same_source and self_override_node_recovery:
            continue
        previous_structure_signature = str(row.get("structureSignature") or "").strip()
        candidate_structure_signature = str(candidate_graph.get("structureSignature") or "").strip()
        if (
            guarded_same_graph
            and previous_structure_signature
            and candidate_structure_signature != previous_structure_signature
        ):
            source_scope = "same-source" if same_source else "source-unknown"
            raise RuntimeError(
                f"SimulationCraft {source_scope} graph structure changed for "
                f"{context_label}; preserving the current PostgreSQL talent tree"
            )
        if (
            guarded_same_graph
            and previous_signature
            and candidate_signature != previous_signature
        ):
            source_scope = "same-source" if same_source else "source-unknown"
            previous_nodes = int(row.get("nodes") or 0)
            previous_dependency_nodes = int(row.get("dependencyNodes") or 0)
            incomplete_previous_graph = bool(
                previous_nodes > 0
                and previous_dependency_nodes * 100 < previous_nodes * min_parent_coverage
            )
            if incomplete_previous_graph and previous_structure_signature:
                previous_parent_map = {}
                raw_parent_map = row.get("parentIdsByNode") or []
                if isinstance(raw_parent_map, list):
                    for raw_entry in raw_parent_map:
                        if not isinstance(raw_entry, (list, tuple)) or len(raw_entry) != 2:
                            continue
                        node_id = str(raw_entry[0] or "").strip()
                        raw_parent_ids = raw_entry[1]
                        if not node_id or not isinstance(raw_parent_ids, list):
                            continue
                        previous_parent_map[node_id] = {
                            str(parent_id or "").strip()
                            for parent_id in raw_parent_ids
                            if str(parent_id or "").strip()
                        }
                candidate_parent_map = candidate_graph.get("parentIdsByNode") or {}
                monotonic_recovery = bool(
                    previous_parent_map
                    and set(previous_parent_map) == set(candidate_parent_map)
                    and all(
                        previous_parents <= set(candidate_parent_map.get(node_id) or set())
                        for node_id, previous_parents in previous_parent_map.items()
                    )
                    and any(
                        previous_parents < set(candidate_parent_map.get(node_id) or set())
                        for node_id, previous_parents in previous_parent_map.items()
                    )
                )
                if monotonic_recovery:
                    continue
                raise RuntimeError(
                    f"SimulationCraft {source_scope} dependency recovery is not monotonic for "
                    f"{context_label}; preserving the current PostgreSQL talent tree"
                )
            raise RuntimeError(
                f"SimulationCraft {source_scope} graph signature changed for "
                f"{context_label}; preserving the current PostgreSQL talent tree"
            )
        if not same_source and previous_node_ids:
            retained_node_ids = len(previous_node_ids & candidate_node_ids)
            if retained_node_ids * 100 < len(previous_node_ids) * min_retention:
                raise RuntimeError(
                    "SimulationCraft tree context node identities fell below the last-known-good baseline; "
                    f"{context_label} retained {retained_node_ids}/{len(previous_node_ids)}, "
                    f"below {min_retention}%; preserving the current PostgreSQL talent tree"
                )

    return {
        "dependencies": dependency_refs,
        "dependencyNodes": dependency_node_count,
        "specCoverage": len(required_specs),
        "heroCoverage": len(required_heroes),
        "profiles": len(presets),
        "profileSpecCoverage": len(profile_specs),
        "profileRetiredBatches": sorted(retired_profile_batches),
        "profileFallbackCount": int(simc_data.get("profileFallbackCount") or 0),
        "profileFallbackSpecs": sorted(
            str(spec_pair or "").strip()
            for spec_pair in (simc_data.get("profileFallbackSpecs") or [])
            if str(spec_pair or "").strip()
        ),
    }


def postgres_talent_catalog_revision(simc_data, simc_counts):
    """Return a content identity for a successfully persisted PG SimC catalog."""

    simc_data = simc_data if isinstance(simc_data, dict) else {}
    simc_counts = simc_counts if isinstance(simc_counts, dict) else {}
    if not int(simc_counts.get("talents") or len(simc_data.get("talents") or [])):
        return ""
    identity = {
        "source": simc_data.get("source") or simc_counts.get("source") or "",
        "build": simc_data.get("build") or simc_counts.get("build") or "",
        "talents": simc_data.get("talents") or [],
        "presets": simc_data.get("presets") or [],
        "spellDetails": simc_data.get("spellDetails") or [],
        "dependencies": int(simc_counts.get("dependencies") or simc_data.get("dependencies") or 0),
        "dependencyNodes": int(
            simc_counts.get("dependencyNodes") or simc_data.get("dependencyNodes") or 0
        ),
        "profileFallbackCount": int(simc_counts.get("profileFallbackCount") or 0),
        "profileFallbackSpecs": sorted(
            str(spec_pair or "").strip()
            for spec_pair in (simc_counts.get("profileFallbackSpecs") or [])
            if str(spec_pair or "").strip()
        ),
        "profileRetiredBatches": sorted(
            str(batch or "").strip().upper()
            for batch in (simc_counts.get("profileRetiredBatches") or [])
            if str(batch or "").strip()
        ),
        "traitEdgeSource": simc_data.get("traitEdgeSource") or simc_counts.get("traitEdgeSource") or "",
    }
    digest = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{TALENT_CATALOG_REVISION}-{digest}"


def sync_websim_cache_postgres(include_blizzard=True, stage_callback=None, store=None):
    store = store or cache_store_from_env()
    _emit(stage_callback, "websim", "start", includeBlizzard=bool(include_blizzard))
    checked_at = utc_now()
    talent_state = store.get_sync_state("websim_sync") or {}
    simc_data = {}
    simc_sync_ok = False
    simc_counts = {
        "talents": 0,
        "profiles": 0,
        "spellDetails": 0,
        "build": "",
        "source": "",
        "traitEdgeSource": "",
        "errors": [],
    }
    graph_baseline = {}
    try:
        _emit(stage_callback, "simc", "start", runner="postgres")
        validation_state = dict(talent_state)
        graph_baseline = store.simc_talent_graph_baseline()
        validation_state["graphBaseline"] = graph_baseline
        simc_data = extract_simc_generated_data()
        simc_data.update(validate_simc_generated_data_candidate(simc_data, validation_state))
        simc_counts = store.replace_simc_generated_data(simc_data)
        simc_counts = {
            **(simc_counts if isinstance(simc_counts, dict) else {}),
            # Keep these quality signals in the sync state even when the cloud
            # store is one revision behind the extractor contract.
            "profileFallbackCount": int(simc_data.get("profileFallbackCount") or 0),
            "profileFallbackSpecs": sorted(
                str(spec_pair or "").strip()
                for spec_pair in (simc_data.get("profileFallbackSpecs") or [])
                if str(spec_pair or "").strip()
            ),
            "profileRetiredBatches": sorted(
                str(batch or "").strip().upper()
                for batch in (
                    simc_data.get("profileRetiredBatches")
                    or (
                        (simc_data.get("profileRetirement") or {}).get(
                            "retiredBatches"
                        )
                        if isinstance(simc_data.get("profileRetirement"), dict)
                        else []
                    )
                )
                if str(batch or "").strip()
            ),
        }
        simc_sync_ok = True
        _emit(
            stage_callback,
            "simc",
            "complete",
            runner="postgres",
            talents=simc_counts.get("talents") or 0,
            profiles=simc_counts.get("profiles") or 0,
            spellDetails=simc_counts.get("spellDetails") or 0,
        )
    except Exception as error:
        previous_simc = talent_state.get("simc") if isinstance(talent_state.get("simc"), dict) else {}
        if previous_simc:
            simc_counts = dict(previous_simc)
        if isinstance(graph_baseline, dict):
            for key in ("talents", "profiles", "profileSpecCoverage", "dependencies", "dependencyNodes"):
                if key in graph_baseline:
                    simc_counts[key] = int(graph_baseline.get(key) or 0)
        simc_counts["errors"] = [str(error)]
        simc_counts["lastAttempt"] = {
            "status": "blocked",
            "checkedAt": checked_at,
            "error": str(error),
        }
        _emit(stage_callback, "simc", "blocked", runner="postgres", errors=1)
    blizzard_counts = {"runner": "postgres", "skipped": not include_blizzard}
    gear_catalog = store.get_sync_state("gearCatalog") or {}
    if include_blizzard:
        try:
            _emit(stage_callback, "blizzard", "start", runner="postgres")
            journal_data = fetch_websim_journal_data_postgres()
            discovery_state = journal_discovery_state(journal_data)
            if discovery_state["sourceStatus"] != "verified":
                blizzard_counts = {
                    **discovery_state,
                    "runner": "postgres",
                }
                _emit(
                    stage_callback,
                    "blizzard",
                    "blocked",
                    runner="postgres",
                    errors=len(blizzard_counts.get("errors") or []),
                )
            else:
                blizzard_counts = store.replace_websim_journal_data(journal_data)
                blizzard_counts.update(
                    {
                        "runner": "postgres",
                        "sourceStatus": "verified",
                        "membershipComplete": True,
                        "gaps": [],
                        "blockerCodes": [],
                        "blockers": [],
                        "errors": [],
                    }
                )
                gear_catalog = store.rebuild_websim_gear_catalog_from_loot(journal_data.get("season") or {})
                _emit(
                    stage_callback,
                    "blizzard",
                    "complete",
                    runner="postgres",
                    instances=blizzard_counts.get("instances") or 0,
                    encounters=blizzard_counts.get("encounters") or 0,
                    loot=blizzard_counts.get("loot") or 0,
                    items=blizzard_counts.get("items") or 0,
                )
        except Exception as error:
            blizzard_counts = {"runner": "postgres", "sourceStatus": "blocked", "errors": [str(error)]}
            _emit(stage_callback, "blizzard", "blocked", runner="postgres", errors=1)
    season = store.get_active_season_payload()
    blockers = []
    data_status = season.get("dataStatus") or "blocked"
    if simc_counts.get("errors"):
        blockers.extend(simc_counts.get("errors") or [])
    if blizzard_counts.get("errors"):
        blockers.extend(blizzard_counts.get("errors") or [])
    if data_status != "verified":
        blockers.extend(season.get("errors") or [f"active season is {data_status}"])
    gear_status = gear_catalog.get("status") or gear_catalog.get("dataStatus") or ""
    if gear_status in {"partial", "blocked", "stale"}:
        blockers.extend(gear_catalog.get("blockers") or [f"gear catalog is {gear_status}"])
    blockers = unique_text_list(blockers)
    if simc_sync_ok:
        talent_health = {
            "schemaRevision": TALENT_SCHEMA_REVISION,
            "simcBuild": simc_counts.get("build") or "",
            "traitEdgeSource": simc_counts.get("traitEdgeSource") or "",
            "officialRevision": season.get("seasonRevision") or season.get("revision") or "",
            "diffStatus": "pending_official_audit" if simc_counts.get("talents") else "blocked",
            "checkedAt": checked_at,
        }
        talent_revision = postgres_talent_catalog_revision(simc_data, simc_counts)
    else:
        talent_health = (
            talent_state.get("talentHealth")
            if isinstance(talent_state.get("talentHealth"), dict)
            else {}
        )
        talent_revision = str(talent_state.get("talentRevision") or "").strip()
    payload = {
        "ok": not blockers and data_status == "verified",
        "runner": "postgres",
        "checkedAt": checked_at,
        "region": talent_state.get("region") or "cn",
        "locale": talent_state.get("locale") or "zh_CN",
        "simc": simc_counts,
        "blizzard": blizzard_counts,
        "currentSeason": season,
        "dataStatus": data_status,
        "seasonRevision": season.get("seasonRevision") or season.get("revision") or "",
        "gearCatalog": gear_catalog or {
            "status": "blocked",
            "schemaRevision": GEAR_CATALOG_REVISION,
            "blockers": ["PostgreSQL gear catalog sync state is missing"],
        },
        "talentSchemaRevision": TALENT_SCHEMA_REVISION,
        "talentRevision": talent_revision,
        "talentHealth": talent_health,
        "errors": blockers,
        "stages": [
            {
                "stage": "postgres_read_model",
                "status": "complete" if not blockers else "partial",
                "checkedAt": checked_at,
            }
        ],
    }
    store.save_sync_state("websim_sync", payload, checked_at)
    _emit(stage_callback, "websim", "complete", ok=payload["ok"], errors=len(blockers), dataStatus=data_status)
    return payload


def sync_stat_weight_cache_postgres(raiderio_payload=None, refresh_mode="scheduled", store=None):
    store = store or cache_store_from_env()
    raiderio_payload = raiderio_payload or store.get_raiderio_payload()
    _emit(None, "stat_weights", "start")
    accepted = 0
    verified = 0
    partial = 0
    blocked = 0
    errors = []
    aggregates = aggregate_by_spec(raiderio_payload or {})
    registry = specialization_registry()
    spec_limit = 0
    try:
        spec_limit = int(os.environ.get("WOW_STAT_WEIGHTS_SPEC_LIMIT", "0"))
    except ValueError:
        spec_limit = 0
    if spec_limit > 0:
        registry = registry[:spec_limit]
    for spec_meta in registry:
        spec_key = f"{spec_meta['classKey']}:{spec_meta['specKey']}"
        aggregate = aggregates.get(spec_key) or {}
        ready_profiles = []
        blocked_profile_notes = []
        try:
            raw_profiles = representative_profile_candidates(raiderio_payload or {}, aggregate, spec_meta)
        except Exception as error:
            raw_profiles = []
            blocked_profile_notes.append(f"representative profile selection failed: {error}")
        for raw_profile in raw_profiles:
            try:
                candidate = ready_profile_candidate(raw_profile, spec_meta)
            except Exception as error:
                blocked_profile_notes.append(f"profile readiness check failed: {error}")
                continue
            if candidate.get("ready"):
                ready_profiles.append(candidate)
            else:
                blocked_profile_notes.extend(candidate.get("blockers") or [])
        for scenario in MPLUS_SCENARIOS:
            previous = store.get_stat_weight_payload(spec_meta["classKey"], spec_meta["specKey"], scenario["key"])
            try:
                payload = build_scenario_payload_with_previous(
                    spec_meta,
                    scenario,
                    raiderio_payload or {},
                    aggregate,
                    ready_profiles,
                    blocked_profile_notes,
                    previous=previous,
                )
            except Exception as error:
                reason = f"PostgreSQL-native stat weight generation failed: {error}"
                payload = scenario_blocked_payload(spec_meta["classKey"], spec_meta["specKey"], scenario, reason)
                errors.append(f"{spec_key}:{scenario['key']}: {error}")
            payload["refreshMode"] = refresh_mode
            payload["raiderioStatus"] = (raiderio_payload or {}).get("sourceStatus") or "blocked"
            store.save_stat_weight_payload(payload)
            status = payload.get("sourceStatus") or payload.get("status") or "blocked"
            if status == "verified":
                verified += 1
                accepted += 1
            elif status in {"partial", "stale"}:
                partial += 1
                accepted += 1
            else:
                blocked += 1
    status = _status_from_counts(verified, partial, blocked)
    refreshed_at = utc_now()
    result = {
        "runner": "postgres",
        "refreshMode": refresh_mode,
        "refreshedAt": refreshed_at,
        "status": status,
        "sourceStatus": status,
        "specCount": len(registry),
        "scenarioCount": len(MPLUS_SCENARIOS),
        "acceptedCount": accepted,
        "blockedCount": blocked,
        "raiderioStatus": (raiderio_payload or {}).get("sourceStatus") or "blocked",
        "raiderioCheckedAt": (raiderio_payload or {}).get("checkedAt") or "",
        "errors": errors,
    }
    store.save_sync_state("stat_weights_sync", result, refreshed_at)
    return result


def include_manual_fixture_sources():
    return os.environ.get("WOW_INCLUDE_MANUAL_FIXTURES", "").strip().lower() in {"1", "true", "yes", "on"}


def _source_error_stage(error):
    text = str(error or "").lower()
    if any(token in text for token in ("combatantinfo", "template seed", "report extraction", "raw talent", "loadout")):
        return "template_extraction"
    if any(token in text for token in ("credential", "api key", "oauth", "configured")):
        return "source_collection"
    return "source_collection"


def _text_list(value):
    if isinstance(value, list):
        return unique_text_list([str(item) for item in value if str(item or "").strip()])
    if isinstance(value, dict):
        values = []
        for key in ("warnings", "errors", "blockers"):
            items = value.get(key)
            if isinstance(items, list):
                values.extend(str(item) for item in items if str(item or "").strip())
        return unique_text_list(values)
    if str(value or "").strip():
        return [str(value)]
    return []


def _template_blocker_stage(reason):
    text = str(reason or "").lower()
    if "loadout spec id" in text or "matched multiple hero" in text or "did not identify a hero" in text:
        return "class_spec_hero_validation"
    if "unknown talent node" in text or "talentencoding" in text or "encode" in text:
        return "authority_encoding"
    if "unknown structured talent entry" in text:
        return "authority_validation"
    if any(token in text for token in ("structured talent loadout", "raw talent import", "missing websim talent state", "external talents import")):
        return "template_extraction"
    return "authority_validation"


def _source_gap_records(source_key, source_name, errors, status=""):
    gaps = []
    for error in errors or []:
        reason = str(error or "").strip()
        if not reason:
            continue
        gaps.append(
            {
                "sourceKey": source_key,
                "sourceName": source_name or source_key,
                "status": "blocked" if status == "blocked" else "partial",
                "stage": _source_error_stage(reason),
                "reason": reason,
            }
        )
    return gaps


def _new_source_summary(source_key, source_name, status, errors=None, warnings=None, candidate_count=0):
    errors = _text_list(errors)
    warnings = _text_list(warnings)
    return {
        "status": status or "blocked",
        "sourceName": source_name or source_key,
        "candidateCount": int(candidate_count or 0),
        "verifiedCount": 0,
        "blockedCount": 0,
        "skippedCount": 0,
        "warningCount": len(warnings),
        "errorCount": len(errors),
        "warnings": warnings,
        "errors": errors,
        "gaps": _source_gap_records(source_key, source_name or source_key, errors, status or "blocked"),
        "blocked": [],
        "skipped": [],
        "wclEvidenceCount": 0,
        "targetMatrix": {},
    }


def _template_payload(template):
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    return payload if isinstance(payload, dict) else {}


def _template_wcl_evidence_tier(template):
    payload = _template_payload(template)
    evidence = payload.get("wclEvidence") if isinstance(payload.get("wclEvidence"), dict) else {}
    warcraftlogs = payload.get("warcraftlogs") if isinstance(payload.get("warcraftlogs"), dict) else {}
    tier = str(evidence.get("tier") or payload.get("evidenceTier") or warcraftlogs.get("evidenceTier") or warcraftlogs.get("tier") or "").strip()
    return tier or "wcl_missing"


def _template_has_wcl_backing(template):
    return _template_wcl_evidence_tier(template) in {"wcl_exact_template", "wcl_character_supported"}


def _template_slot_id(template):
    class_key = slugify(template.get("classKey"), "")
    spec_key = slugify(template.get("specKey"), "")
    hero_key = hero_tree_for(class_key, spec_key, slugify(template.get("heroKey"), "")) if class_key and spec_key else slugify(template.get("heroKey"), "")
    if not class_key or not spec_key or not hero_key:
        return ""
    return f"{class_key}:{spec_key}:{hero_key}"


def _template_blocker_records(template, default_reason="community talent template blocked without explicit reason"):
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    records = []

    def append_reasons(stage, reasons):
        for reason in reasons or []:
            reason = str(reason or "").strip()
            if not reason:
                continue
            records.append(
                {
                    "status": "blocked",
                    "stage": stage or _template_blocker_stage(reason),
                    "reason": reason,
                    "sourceKey": template.get("sourceKey") or payload.get("sourceKey") or "",
                    "sourceName": template.get("sourceName") or "",
                    "templateId": str(template.get("id") or ""),
                    "classKey": slugify(template.get("classKey"), ""),
                    "specKey": slugify(template.get("specKey"), ""),
                    "heroKey": slugify(template.get("heroKey"), ""),
                }
            )

    for section_key, stage in (("talentLoadoutParse", ""), ("talentEncoding", "authority_encoding")):
        section = payload.get(section_key) if isinstance(payload.get(section_key), dict) else {}
        section_errors = section.get("errors")
        if isinstance(section_errors, list):
            append_reasons(stage, section_errors)
        elif str(section_errors or "").strip():
            append_reasons(stage, [section_errors])
    generic = []
    for key in ("blockers", "errors"):
        value = payload.get(key)
        if isinstance(value, list):
            generic.extend(value)
        elif str(value or "").strip():
            generic.append(value)
    seen = {item["reason"] for item in records}
    append_reasons("", [item for item in generic if str(item or "").strip() not in seen])
    if not records:
        append_reasons(_template_blocker_stage(default_reason), [default_reason])
    return records


def _pending_coverage_blocker(class_key, spec_key, hero_key):
    return {
        "status": COMMUNITY_TALENT_PENDING_STATUS,
        "stage": "source_collection",
        "reason": f"missing verified community talent template for {class_key}/{spec_key}/{hero_key}",
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
    }


def _coverage_summary_from_rows(rows):
    reason_counts = {}
    for row in rows:
        if row.get("status") == "verified":
            continue
        for blocker in row.get("blockers") or []:
            reason = blocker.get("reason") or ""
            stage = blocker.get("stage") or ""
            if not reason:
                continue
            key = (stage, reason)
            reason_counts[key] = reason_counts.get(key, 0) + 1
    return [
        {"stage": stage, "reason": reason, "count": count}
        for (stage, reason), count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))[:12]
    ]


def _int_value(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _slot_target_collection(row, sources):
    spec_id = row.get("specId") or ""
    source_attempts = {}
    total_attempted = 0
    for source_key, source in (sources or {}).items():
        source = source if isinstance(source, dict) else {}
        spec_coverage = source.get("specCoverage") if isinstance(source.get("specCoverage"), dict) else {}
        sample_counts = spec_coverage.get("sampleCounts") if isinstance(spec_coverage.get("sampleCounts"), dict) else {}
        attempted = _int_value(sample_counts.get(spec_id), 0)
        region_samples = []
        region_coverage = source.get("regionCoverage") if isinstance(source.get("regionCoverage"), dict) else {}
        for region, region_summary in sorted(region_coverage.items()):
            region_summary = region_summary if isinstance(region_summary, dict) else {}
            region_spec_coverage = region_summary.get("specCoverage") if isinstance(region_summary.get("specCoverage"), dict) else {}
            region_counts = region_spec_coverage.get("sampleCounts") if isinstance(region_spec_coverage.get("sampleCounts"), dict) else {}
            sample_count = _int_value(region_counts.get(spec_id), 0)
            if sample_count:
                region_samples.append({"region": region, "sampleCount": sample_count})
        if attempted or region_samples or source.get("regions"):
            source_attempts[source_key] = {
                "attemptedRunCount": attempted,
                "regions": region_samples,
                "runCount": _int_value(source.get("runCount"), 0),
                "profileCount": _int_value(source.get("profileCount"), 0),
                "runDetailCoverage": source.get("runDetailCoverage") or {},
            }
        total_attempted += attempted
    return {
        "attemptedRunCount": total_attempted,
        "sources": source_attempts,
    }


def _slot_next_action(row):
    status = row.get("status") or ""
    collection = row.get("targetCollection") if isinstance(row.get("targetCollection"), dict) else {}
    attempted = _int_value(collection.get("attemptedRunCount"), 0)
    candidate_count = _int_value(row.get("candidateCount"), 0)
    if status == "verified":
        return "promoted active template; keep monitoring drift and duplicate signatures"
    if status == "blocked":
        stage = row.get("stage") or "authority_validation"
        reason = row.get("reason") or "blocked community talent template"
        return f"fix {stage}: {reason}"
    if attempted <= 0:
        return "expand Raider.IO target-matrix scan across more regions/pages, then fall back to WCL combatantinfo extraction"
    if candidate_count <= 0:
        return "fetch run-detail/profile talent snapshots for observed high-score runs in this spec"
    return "increase same-slot candidate count and require authority validation before promotion"


def _source_target_matrix_summary(source_key, rows):
    attempted_by_spec = {}
    verified = 0
    pending = 0
    blocked = 0
    candidate_count = 0
    attempted_pending = False
    unattempted_pending = False
    for row in rows or []:
        status = row.get("status") or ""
        if status == "verified":
            verified += 1
        elif status == COMMUNITY_TALENT_PENDING_STATUS:
            pending += 1
        elif status == "blocked":
            blocked += 1
        source_counts = (row.get("sources") or {}).get(source_key) or {}
        candidate_count += _int_value(source_counts.get("candidateCount"), 0)
        source_collection = ((row.get("targetCollection") or {}).get("sources") or {}).get(source_key) or {}
        attempted = _int_value(source_collection.get("attemptedRunCount"), 0)
        spec_id = row.get("specId") or row.get("slotId") or ""
        if attempted:
            attempted_by_spec[spec_id] = max(attempted_by_spec.get(spec_id, 0), attempted)
        if status != "verified":
            if attempted:
                attempted_pending = True
            else:
                unattempted_pending = True
    if attempted_pending:
        next_action = "fetch run-detail/profile talent snapshots for observed high-score runs in attempted specs"
    elif unattempted_pending:
        next_action = "expand Raider.IO target-matrix scan across more regions/pages, then fall back to WCL combatantinfo extraction"
    else:
        next_action = "promoted active templates; keep monitoring drift and WCL evidence freshness"
    return {
        "totalHeroSlotCount": len(rows or []),
        "verifiedHeroSlotCount": verified,
        "pendingCollectionHeroSlotCount": pending,
        "blockedHeroSlotCount": blocked,
        "candidateCount": candidate_count,
        "attemptedRunCount": sum(attempted_by_spec.values()),
        "nextAction": next_action,
    }


def build_community_talent_coverage_matrix(templates, sources=None, scan_run_id="", checked_at=""):
    sources = {key: dict(value) for key, value in (sources or {}).items()}
    expected_slots = []
    for triplet in expected_hero_tree_triplets():
        parts = str(triplet or "").split(":")
        if len(parts) != 3:
            continue
        class_key, spec_key, hero_key = parts
        expected_slots.append((class_key, spec_key, hero_key))
    rows_by_slot = {}
    for class_key, spec_key, hero_key in expected_slots:
        slot_id = f"{class_key}:{spec_key}:{hero_key}"
        rows_by_slot[slot_id] = {
            "slotId": slot_id,
            "specId": f"{class_key}:{spec_key}",
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "classLabel": class_label(class_key),
            "specLabel": spec_label(spec_key),
            "heroLabel": hero_tree_label(hero_key),
            "status": COMMUNITY_TALENT_PENDING_STATUS,
            "stage": "source_collection",
            "reason": "missing verified community sample",
            "candidateCount": 0,
            "verifiedCount": 0,
            "blockedCount": 0,
            "skippedCount": 0,
            "sources": {},
            "verifiedTemplateIds": [],
            "blockedTemplateIds": [],
            "blockers": [_pending_coverage_blocker(class_key, spec_key, hero_key)],
            "warnings": [],
            "skipped": [],
        }
    for source_key, source in sources.items():
        for skipped in source.get("skipped") or []:
            slot_id = _template_slot_id(skipped)
            row = rows_by_slot.get(slot_id)
            if not row:
                continue
            row["candidateCount"] += 1
            row["skippedCount"] += 1
            row["sources"].setdefault(source_key, {"candidateCount": 0, "verifiedCount": 0, "blockedCount": 0, "skippedCount": 0})
            row["sources"][source_key]["candidateCount"] += 1
            row["sources"][source_key]["skippedCount"] += 1
            row["skipped"].append(skipped)
            reason = skipped.get("reason") or ""
            if reason:
                row["warnings"] = unique_text_list([*(row.get("warnings") or []), reason])
    for template in templates or []:
        if not isinstance(template, dict):
            continue
        slot_id = _template_slot_id(template)
        row = rows_by_slot.get(slot_id)
        if not row:
            continue
        source_key = template.get("sourceKey") or "unknown"
        source = sources.setdefault(
            source_key,
            _new_source_summary(source_key, template.get("sourceName") or source_key, template.get("sourceStatus") or "partial"),
        )
        row["candidateCount"] += 1
        row["sources"].setdefault(source_key, {"candidateCount": 0, "verifiedCount": 0, "blockedCount": 0, "skippedCount": 0})
        row["sources"][source_key]["candidateCount"] += 1
        status = template.get("status") or "blocked"
        if status == "verified":
            source["verifiedCount"] = int(source.get("verifiedCount") or 0) + 1
            if _template_has_wcl_backing(template):
                source["wclEvidenceCount"] = int(source.get("wclEvidenceCount") or 0) + 1
            row["verifiedCount"] += 1
            row["sources"][source_key]["verifiedCount"] += 1
            if row["status"] != "verified":
                row["status"] = "verified"
                row["stage"] = "promotion_dedupe"
                row["reason"] = ""
                row["blockers"] = []
            row["verifiedTemplateIds"].append(str(template.get("id") or ""))
        elif status == COMMUNITY_TALENT_PENDING_STATUS:
            continue
        else:
            blockers = _template_blocker_records(template)
            source["blockedCount"] = int(source.get("blockedCount") or 0) + 1
            source["blocked"] = [*(source.get("blocked") or []), *blockers]
            row["blockedCount"] += 1
            row["sources"][source_key]["blockedCount"] += 1
            row["blockedTemplateIds"].append(str(template.get("id") or ""))
            if row["status"] != "verified":
                row["status"] = "blocked"
                row["stage"] = blockers[0].get("stage") or "authority_validation"
                row["reason"] = blockers[0].get("reason") or ""
                row["blockers"] = blockers
            else:
                row["warnings"] = unique_text_list([*(row.get("warnings") or []), *[item.get("reason") for item in blockers]])
    rows = [rows_by_slot[f"{class_key}:{spec_key}:{hero_key}"] for class_key, spec_key, hero_key in expected_slots]
    for row in rows:
        row["targetCollection"] = _slot_target_collection(row, sources)
        row["attemptedRunCount"] = row["targetCollection"]["attemptedRunCount"]
        row["nextAction"] = _slot_next_action(row)
    verified_slots = [row for row in rows if row.get("status") == "verified"]
    pending_slots = [row for row in rows if row.get("status") == COMMUNITY_TALENT_PENDING_STATUS]
    blocked_slots = [row for row in rows if row.get("status") == "blocked"]
    spec_ids = sorted({row["specId"] for row in rows})
    complete_specs = [
        spec_id
        for spec_id in spec_ids
        if all(row.get("status") == "verified" for row in rows if row.get("specId") == spec_id)
    ]
    partial_specs = [
        spec_id
        for spec_id in spec_ids
        if spec_id not in complete_specs and any(row.get("status") == "verified" for row in rows if row.get("specId") == spec_id)
    ]
    matrix_status = "verified" if len(verified_slots) == len(rows) and rows else "partial"
    if blocked_slots and not verified_slots and not pending_slots:
        matrix_status = "blocked"
    for source in sources.values():
        source["candidateCount"] = int(source.get("candidateCount") or 0)
        source["verifiedCount"] = int(source.get("verifiedCount") or 0)
        source["blockedCount"] = int(source.get("blockedCount") or 0)
        source["skippedCount"] = int(source.get("skippedCount") or 0)
        source["warnings"] = _text_list(source.get("warnings") or [])
        source["errors"] = _text_list(source.get("errors") or [])
        source["warningCount"] = len(source["warnings"])
        source["errorCount"] = len(source["errors"])
        source["gaps"] = source.get("gaps") or _source_gap_records("", source.get("sourceName") or "", source["errors"], source.get("status") or "")
        source["wclEvidenceCount"] = int(source.get("wclEvidenceCount") or 0)
        source["targetMatrix"] = _source_target_matrix_summary(
            next((key for key, value in sources.items() if value is source), ""),
            rows,
        )
    return {
        "schemaRevision": COMMUNITY_TALENT_COVERAGE_MATRIX_REVISION,
        "scanRunId": scan_run_id,
        "checkedAt": checked_at,
        "status": matrix_status,
        "totalSpecCount": len(spec_ids),
        "totalHeroSlotCount": len(rows),
        "verifiedHeroSlotCount": len(verified_slots),
        "pendingCollectionHeroSlotCount": len(pending_slots),
        "blockedHeroSlotCount": len(blocked_slots),
        "skippedCandidateCount": sum(int(row.get("skippedCount") or 0) for row in rows),
        "completeSpecCount": len(complete_specs),
        "partialSpecCount": len(partial_specs),
        "pendingSpecCount": len(spec_ids) - len(complete_specs) - len(partial_specs),
        "completeSpecs": complete_specs,
        "partialSpecs": partial_specs,
        "pendingHeroSlots": [row["slotId"] for row in pending_slots],
        "blockedHeroSlots": [row["slotId"] for row in blocked_slots],
        "topBlockers": _coverage_summary_from_rows(rows),
        "sourceSummary": sources,
        "rows": rows,
    }


def scan_coverage_from_community_talent_matrix(matrix):
    matrix = matrix if isinstance(matrix, dict) else {}
    rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    spec_ids = sorted({row.get("specId") for row in rows if row.get("specId")})
    return {
        "totalClassCount": len({row.get("classKey") for row in rows if row.get("classKey")}),
        "totalSpecCount": int(matrix.get("totalSpecCount") or len(spec_ids)),
        "totalHeroSlotCount": int(matrix.get("totalHeroSlotCount") or len(rows)),
        "coveredSpecCount": int(matrix.get("completeSpecCount") or 0),
        "partiallyCoveredSpecCount": int(matrix.get("partialSpecCount") or 0),
        "coveredHeroSlotCount": int(matrix.get("verifiedHeroSlotCount") or 0),
        "pendingCollectionHeroSlotCount": int(matrix.get("pendingCollectionHeroSlotCount") or 0),
        "blockedHeroSlotCount": int(matrix.get("blockedHeroSlotCount") or 0),
        "missingSpecs": [spec_id for spec_id in spec_ids if spec_id not in set(matrix.get("completeSpecs") or [])],
        "missingHeroSlots": list(matrix.get("pendingHeroSlots") or []),
        "blockedHeroSlots": list(matrix.get("blockedHeroSlots") or []),
    }


def _gear_spec_parts(spec_id):
    parts = str(spec_id or "").split(":")
    if len(parts) != 2:
        return "", ""
    return slugify(parts[0], ""), slugify(parts[1], "")


def _gear_template_source_key(template):
    return str((template or {}).get("sourceKey") or "").strip()


def _gear_template_is_baseline(template):
    return _gear_template_source_key(template) in BASELINE_GEAR_TEMPLATE_SOURCE_KEYS


def _gear_template_is_real_community(template):
    return _gear_template_source_key(template) not in BAD_REAL_GEAR_TEMPLATE_SOURCE_KEYS


def _gear_template_slot_sets(template, class_key="", spec_key=""):
    gear_items = [
        item
        for item in (template or {}).get("gearItems") or []
        if isinstance(item, dict)
    ]
    if not gear_items:
        return set(), set(), None
    ready_by_slot, occupied_slots, _missing_slots = gear_template_slot_coverage(
        gear_items,
        slugify(class_key or (template or {}).get("classKey"), ""),
        slugify(spec_key or (template or {}).get("specKey"), ""),
    )
    ready_slots = {
        slot for slot in ready_by_slot
        if slot in CANONICAL_GEAR_SLOTS
    }
    occupied = {
        slot for slot in (occupied_slots or {})
        if slot in CANONICAL_GEAR_SLOTS
    }
    covered = ready_slots | occupied
    missing = [slot for slot in CANONICAL_GEAR_SLOTS if slot not in covered]
    return ready_slots, occupied, missing


def _gear_template_ready_slots(template, class_key="", spec_key=""):
    ready_slots, occupied_slots, missing_slots = _gear_template_slot_sets(template, class_key, spec_key)
    if missing_slots is not None:
        return ready_slots | occupied_slots
    ready = set()
    for item in (template or {}).get("gearItems") or []:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot") or "").strip()
        if slot in CANONICAL_GEAR_SLOTS:
            ready.add(slot)
    return ready


def _gear_template_missing_slots(template, class_key="", spec_key=""):
    _ready_slots, _occupied_slots, missing_slots = _gear_template_slot_sets(template, class_key, spec_key)
    if missing_slots is not None:
        return missing_slots
    declared = (template or {}).get("missingSlots")
    if isinstance(declared, list):
        normalized = [str(slot) for slot in declared if str(slot or "") in CANONICAL_GEAR_SLOTS]
        if normalized:
            return normalized
    ready = _gear_template_ready_slots(template, class_key, spec_key)
    return [slot for slot in CANONICAL_GEAR_SLOTS if slot not in ready]


def _gear_template_ready_count(template, class_key="", spec_key=""):
    _ready_slots, _occupied_slots, missing_slots = _gear_template_slot_sets(template, class_key, spec_key)
    if missing_slots is not None:
        return len(CANONICAL_GEAR_SLOTS) - len(missing_slots)
    ready_count = _int_value((template or {}).get("readySlotCount"), -1)
    if ready_count >= 0:
        return ready_count
    return len(_gear_template_ready_slots(template, class_key, spec_key))


def _gear_template_rank(template):
    status = str((template or {}).get("status") or "").strip()
    class_key = slugify((template or {}).get("classKey"), "")
    spec_key = slugify((template or {}).get("specKey"), "")
    return (
        1 if status in {"complete", "verified"} else 0,
        _gear_template_ready_count(template, class_key, spec_key),
        str((template or {}).get("updatedAt") or ""),
        str((template or {}).get("id") or ""),
    )


def _best_gear_template(templates):
    candidates = [template for template in templates or [] if isinstance(template, dict)]
    if not candidates:
        return None
    return sorted(candidates, key=_gear_template_rank, reverse=True)[0]


def _active_observed_gear_template(template, class_key, spec_key):
    if not isinstance(template, dict) or not _gear_template_is_real_community(template):
        return None
    try:
        gated = apply_gear_template_legality_gate(template, class_key, spec_key)
    except Exception:
        gated = template
    if is_active_community_observed_template(gated):
        return gated
    return None


def _gear_display_row(spec_id, class_key, spec_key, template_slot, template, status):
    template = template if isinstance(template, dict) else {}
    missing_slots = _gear_template_missing_slots(template, class_key, spec_key) if template else list(CANONICAL_GEAR_SLOTS)
    ready_slots = _gear_template_ready_slots(template, class_key, spec_key)
    ready_count = _gear_template_ready_count(template, class_key, spec_key) if template else 0
    target_key = f"gear-template:{class_key}:{spec_key}:{template_slot}:{DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY}"
    freshness_status = "unknown"
    if template:
        freshness_status = "stale" if _community_template_freshness_expired(template) else "fresh"
    if template_slot == "baseline" and status == "available":
        next_action = "keep_baseline_available"
    elif template_slot == "baseline":
        next_action = "build_baseline_template"
    elif status == "complete" and freshness_status == "stale":
        next_action = "refresh_stale_winner"
    elif status == "complete":
        next_action = "monitor_freshness"
    elif status == "partial":
        next_action = "probe_missing_variants" if ready_slots else "collect_real_community_gear_samples"
    elif status == "blocked":
        next_action = "review_gear_template_blocker"
    else:
        next_action = "collect_real_community_gear_samples"
    return {
        "specId": spec_id,
        "classKey": class_key,
        "specKey": spec_key,
        "templateSlot": template_slot,
        "targetKey": target_key,
        "status": status,
        "freshnessStatus": freshness_status,
        "sourceKey": _gear_template_source_key(template),
        "sourceName": str(template.get("sourceName") or ""),
        "currentWinnerId": str(template.get("id") or ""),
        "currentWinnerSignature": str(template.get("signature") or ""),
        "readySlotCount": ready_count,
        "totalSlotCount": len(CANONICAL_GEAR_SLOTS),
        "missingSlots": missing_slots,
        "pendingVariantCount": _int_value(template.get("pendingVariantCount"), 0),
        "nextAction": next_action,
    }


def _gear_template_target(row, priority=50):
    return {
        "targetType": "gear_template",
        "targetKey": row["targetKey"],
        "status": "stale" if row.get("freshnessStatus") == "stale" and row.get("status") == "complete" else row["status"],
        "priority": priority,
        "specId": row["specId"],
        "templateSlot": row["templateSlot"],
        "missingSlots": list(row.get("missingSlots") or []),
        "pendingVariantCount": _int_value(row.get("pendingVariantCount"), 0),
        "nextAction": row.get("nextAction") or "",
    }


def _gear_slot_target(spec_id, class_key, spec_key, slot, status, current_winner_id=""):
    return {
        "targetType": "gear_slot",
        "targetKey": f"gear-slot:{class_key}:{spec_key}:{slot}",
        "status": status,
        "priority": 20 if status == "missing" else 40,
        "specId": spec_id,
        "slot": slot,
        "currentWinnerId": current_winner_id,
        "nextAction": "collect_slot_sample" if status == "missing" else "verify_slot_variant",
    }


def _community_gear_template_coverage_rows(store, fallback_templates):
    if hasattr(store, "community_gear_template_coverage_rows"):
        try:
            rows = store.community_gear_template_coverage_rows()
            if isinstance(rows, list):
                return rows
        except Exception:
            return list(fallback_templates or [])
    if hasattr(store, "admin_gate_gear_template_records"):
        try:
            payload = store.admin_gate_gear_template_records()
            rows = payload.get("communityGearTemplates") if isinstance(payload, dict) else []
            if isinstance(rows, list):
                return rows
        except Exception:
            return list(fallback_templates or [])
    return list(fallback_templates or [])


def build_community_gear_template_preflight(templates, scan_run_id="", checked_at=""):
    expected_specs = []
    for spec_id in expected_spec_pairs():
        class_key, spec_key = _gear_spec_parts(spec_id)
        if class_key and spec_key:
            expected_specs.append((spec_id, class_key, spec_key))
    if not expected_specs:
        for template in templates or []:
            class_key = slugify((template or {}).get("classKey"), "")
            spec_key = slugify((template or {}).get("specKey"), "")
            if class_key and spec_key:
                expected_specs.append((f"{class_key}:{spec_key}", class_key, spec_key))
        expected_specs = sorted(set(expected_specs))

    grouped = {spec_id: {"community": [], "baseline": []} for spec_id, _, _ in expected_specs}
    for template in templates or []:
        if not isinstance(template, dict):
            continue
        class_key = slugify(template.get("classKey"), "")
        spec_key = slugify(template.get("specKey"), "")
        spec_id = f"{class_key}:{spec_key}" if class_key and spec_key else ""
        if spec_id not in grouped:
            continue
        if _gear_template_is_baseline(template):
            grouped[spec_id]["baseline"].append(template)
        elif _gear_template_is_real_community(template):
            grouped[spec_id]["community"].append(template)

    display_slots = []
    slot_rows = []
    target_queue = []
    complete_specs = []
    partial_specs = []
    pending_specs = []
    blocked_specs = []
    baseline_available_specs = []
    baseline_blocked_specs = []

    for spec_id, class_key, spec_key in expected_specs:
        raw_community_templates = grouped.get(spec_id, {}).get("community") or []
        active_community_templates = [
            template
            for template in (
                _active_observed_gear_template(template, class_key, spec_key)
                for template in raw_community_templates
            )
            if template
        ]
        best_community = _best_gear_template(active_community_templates)
        if best_community:
            raw_status = str(best_community.get("status") or "").strip()
            missing_slots = _gear_template_missing_slots(best_community, class_key, spec_key)
            if raw_status != "blocked" and not missing_slots:
                community_status = "complete"
                complete_specs.append(spec_id)
            elif raw_status == "blocked":
                community_status = "blocked"
                blocked_specs.append(spec_id)
            else:
                community_status = "partial"
                partial_specs.append(spec_id)
        else:
            blocked_candidate = _best_gear_template(raw_community_templates)
            if blocked_candidate:
                best_community = blocked_candidate
                raw_status = str(blocked_candidate.get("status") or "").strip()
                missing_slots = _gear_template_missing_slots(blocked_candidate, class_key, spec_key)
                if raw_status == "blocked":
                    community_status = "blocked"
                    blocked_specs.append(spec_id)
                elif raw_status == "partial" or missing_slots:
                    community_status = "partial"
                    partial_specs.append(spec_id)
                else:
                    community_status = "blocked"
                    blocked_specs.append(spec_id)
            else:
                community_status = COMMUNITY_TALENT_PENDING_STATUS
                pending_specs.append(spec_id)
        community_row = _gear_display_row(
            spec_id,
            class_key,
            spec_key,
            "community_best",
            best_community,
            community_status,
        )
        display_slots.append(community_row)
        if community_status != "complete":
            target_queue.append(_gear_template_target(community_row, priority=10 if community_status == "partial" else 30))
        elif community_row.get("freshnessStatus") == "stale":
            target_queue.append(_gear_template_target(community_row, priority=15))

        ready_slots = _gear_template_ready_slots(best_community, class_key, spec_key) if best_community else set()
        for slot in CANONICAL_GEAR_SLOTS:
            slot_status = "ready" if slot in ready_slots else "missing"
            slot_row = {
                "specId": spec_id,
                "classKey": class_key,
                "specKey": spec_key,
                "slot": slot,
                "targetKey": f"gear-slot:{class_key}:{spec_key}:{slot}",
                "status": slot_status,
                "templateSlot": "community_best",
                "currentWinnerId": community_row["currentWinnerId"],
                "nextAction": "monitor_slot_variant" if slot_status == "ready" else "collect_slot_sample",
            }
            slot_rows.append(slot_row)
            if slot_status != "ready":
                target_queue.append(_gear_slot_target(spec_id, class_key, spec_key, slot, slot_status, community_row["currentWinnerId"]))

        best_baseline = _best_gear_template(grouped.get(spec_id, {}).get("baseline"))
        baseline_status = "available" if best_baseline and _gear_template_ready_count(best_baseline, class_key, spec_key) > 0 else "blocked"
        if baseline_status == "available":
            baseline_available_specs.append(spec_id)
        else:
            baseline_blocked_specs.append(spec_id)
        baseline_row = _gear_display_row(spec_id, class_key, spec_key, "baseline", best_baseline, baseline_status)
        display_slots.append(baseline_row)
        if baseline_status != "available":
            target_queue.append(_gear_template_target(baseline_row, priority=60))

    ready_slot_count = sum(1 for row in slot_rows if row.get("status") == "ready")
    target_queue_by_key = {}
    for target in target_queue:
        key = target.get("targetKey")
        if key and key not in target_queue_by_key:
            target_queue_by_key[key] = target
    target_queue = sorted(target_queue_by_key.values(), key=lambda row: (int(row.get("priority") or 0), row.get("targetKey") or ""))
    incomplete_specs = [*partial_specs, *pending_specs, *blocked_specs]
    community_import = community_gear_import_coverage_summary(
        len(expected_specs),
        community_complete_specs=complete_specs,
        community_partial_specs=partial_specs,
        community_pending_specs=pending_specs,
        community_blocked_specs=blocked_specs,
        baseline_available_specs=baseline_available_specs,
        baseline_blocked_specs=baseline_blocked_specs,
    )
    matrix_status = community_import.get("status") or "partial"
    return {
        "schemaRevision": COMMUNITY_GEAR_TEMPLATE_PREFLIGHT_REVISION,
        "scanRunId": scan_run_id,
        "checkedAt": checked_at,
        "status": matrix_status,
        "scenarioKey": DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY,
        "totalSpecCount": len(expected_specs),
        "totalDisplaySlotCount": len(display_slots),
        "communityBest": {
            "templateSlot": "community_best",
            "totalSpecCount": len(expected_specs),
            "completeSpecCount": len(complete_specs),
            "partialSpecCount": len(partial_specs),
            "pendingSpecCount": len(pending_specs),
            "blockedSpecCount": len(blocked_specs),
            "completeSpecs": complete_specs,
            "partialSpecs": partial_specs,
            "pendingSpecs": pending_specs,
            "blockedSpecs": blocked_specs,
            "countingPolicy": "real community gear subtype under community import; must reach 40/40 specs",
        },
        "baseline": {
            "templateSlot": "baseline",
            "totalSpecCount": len(expected_specs),
            "availableSpecCount": len(baseline_available_specs),
            "blockedSpecCount": len(baseline_blocked_specs),
            "availableSpecs": baseline_available_specs,
            "blockedSpecs": baseline_blocked_specs,
            "countingPolicy": "fallback baseline gear subtype under community import; must reach 40/40 specs",
        },
        "communityImport": community_import,
        "canonicalSlotMatrix": {
            "totalSlotCount": len(slot_rows),
            "readySlotCount": ready_slot_count,
            "missingSlotCount": len(slot_rows) - ready_slot_count,
            "rows": slot_rows,
        },
        "displaySlots": display_slots,
        "targetQueue": target_queue,
        "realCommunityTemplates": {
            "templateRevision": COMMUNITY_GEAR_TEMPLATE_PREFLIGHT_REVISION,
            "totalSpecCount": len(expected_specs),
            "coveredSpecCount": len(complete_specs),
            "missingSpecCount": len(incomplete_specs),
            "partialSpecCount": len(partial_specs),
            "pendingSpecCount": len(pending_specs),
            "blockedSpecCount": len(blocked_specs),
            "coveredSpecs": complete_specs,
            "partialSpecs": partial_specs,
            "missingSpecs": incomplete_specs,
            "topBlockers": [
                {
                    "stage": "gear_template_preflight",
                    "reason": "missing complete real community gear template",
                    "count": len(incomplete_specs),
                }
            ] if incomplete_specs else [],
            "lastSyncRun": scan_run_id,
            "countingPolicy": "real samples only; baseline/default templates are excluded",
        },
    }


def load_community_talent_sources_postgres(store):
    try:
        from .community_talent_sources import warcraftlogs
    except ImportError:
        from community_talent_sources import warcraftlogs
    sources = {}
    try:
        raiderio = store.get_raiderio_payload()
        sources["raiderio"] = {
            "status": (raiderio or {}).get("sourceStatus") or (raiderio or {}).get("status") or "blocked",
            "sourceName": "Raider.IO",
            "templates": (raiderio or {}).get("communityTemplates") or [],
            "errors": (raiderio or {}).get("errors") or [],
            "regions": (raiderio or {}).get("regions") or ([((raiderio or {}).get("region") or "")] if (raiderio or {}).get("region") else []),
            "regionCoverage": (raiderio or {}).get("regionCoverage") or {},
            "runDetailCoverage": (raiderio or {}).get("runDetailCoverage") or {},
            "specCoverage": (raiderio or {}).get("specCoverage") or {},
            "targetMatrix": (raiderio or {}).get("targetMatrix") or {},
            "runCount": (raiderio or {}).get("runCount") or 0,
            "profileCount": (raiderio or {}).get("profileCount") or 0,
        }
    except Exception as error:
        sources["raiderio"] = {"status": "blocked", "sourceName": "Raider.IO", "templates": [], "errors": [str(error)]}

    loaders = [
        ("warcraftlogs", "Warcraft Logs", warcraftlogs.load_templates),
    ]
    if include_websim_baseline_talent_sources():
        try:
            from .websim_payload import load_websim_baseline_talent_templates
        except ImportError:
            from websim_payload import load_websim_baseline_talent_templates
        loaders.append(("websim_baseline", "WebSim 基线模板", load_websim_baseline_talent_templates))
    if include_manual_fixture_sources():
        try:
            from .community_talent_sources import manual_fixture
        except ImportError:
            from community_talent_sources import manual_fixture
        loaders.insert(0, ("manual_fixture", "Manual Fixture", manual_fixture.load_templates))

    for source_key, source_name, loader in loaders:
        try:
            try:
                result = loader(store)
            except TypeError:
                result = loader()
            result = result if isinstance(result, dict) else {}
        except Exception as error:
            result = {"status": "blocked", "sourceName": source_name, "templates": [], "errors": [str(error)]}
        sources[source_key] = {
            "status": result.get("status") or "blocked",
            "sourceName": result.get("sourceName") or source_name,
            "templates": result.get("templates") or [],
            "warnings": result.get("warnings") or [],
            "errors": result.get("errors") or [],
        }
    return sources


def _community_templates_from_sources(source_results, scan_run_id):
    templates = []
    sources = {}
    errors = []
    for source_key, result in (source_results or {}).items():
        result = result if isinstance(result, dict) else {}
        status = result.get("status") or "blocked"
        source_name = result.get("sourceName") or source_key
        source_errors = result.get("errors") or []
        source_warnings = _text_list(result.get("warnings") or [])
        raw_templates = [item for item in result.get("templates") or [] if isinstance(item, dict)]
        sources[source_key] = _new_source_summary(
            source_key,
            source_name,
            status,
            errors=source_errors,
            warnings=source_warnings,
            candidate_count=len(raw_templates),
        )
        for meta_key in (
            "regions",
            "regionCoverage",
            "runDetailCoverage",
            "specCoverage",
            "targetMatrix",
            "runCount",
            "profileCount",
        ):
            if meta_key in result:
                sources[source_key][meta_key] = result.get(meta_key)
        errors.extend(f"{source_key}: {error}" for error in source_errors)
        for raw_template in raw_templates:
            template = {
                **raw_template,
                "sourceKey": source_key,
                "sourceName": raw_template.get("sourceName") or source_name,
                "sourceStatus": raw_template.get("sourceStatus") or status,
                "scanRunId": raw_template.get("scanRunId") or scan_run_id,
            }
            inventory_blockers = community_talent_loadout_spec_blockers(template)
            if source_key == "raiderio" and inventory_blockers:
                source_warnings = unique_text_list([*source_warnings, *inventory_blockers])
                sources[source_key]["warnings"] = source_warnings
                sources[source_key]["warningCount"] = len(source_warnings)
                sources[source_key]["skippedCount"] = int(sources[source_key].get("skippedCount") or 0) + 1
                for blocker in inventory_blockers:
                    sources[source_key]["skipped"].append(
                        {
                            "status": "skipped",
                            "stage": "class_spec_hero_validation",
                            "reason": blocker,
                            "sourceKey": source_key,
                            "sourceName": source_name,
                            "templateId": str(template.get("id") or ""),
                            "classKey": slugify(template.get("classKey"), ""),
                            "specKey": slugify(template.get("specKey"), ""),
                            "heroKey": slugify(template.get("heroKey"), ""),
                        }
                    )
                continue
            templates.append(template)
    return templates, sources, errors


def _community_template_missing_slots_mode_enabled(mode):
    configured = os.environ.get("WOW_COMMUNITY_TEMPLATE_SYNC_TARGET_MODE", "").strip().lower()
    requested = str(mode or "").strip().lower()
    return configured in {"missing_slots", "missing-slots", "pending_only", "pending-only"} or requested in {
        "missing_slots",
        "missing-slots",
        "pending_only",
        "pending-only",
    }


def _community_template_targeted_slots_mode_enabled(mode):
    configured = os.environ.get("WOW_COMMUNITY_TEMPLATE_SYNC_TARGET_MODE", "").strip().lower()
    requested = str(mode or "").strip().lower()
    enabled_modes = {"targeted_slots", "targeted-slots", "explicit_slots", "explicit-slots"}
    return configured in enabled_modes or requested in enabled_modes


def _community_template_explicit_target_slot_ids():
    raw_values = os.environ.get("WOW_COMMUNITY_TEMPLATE_TARGET_SLOTS", "").split(",")
    expected_slot_ids = {str(slot_id or "").strip() for slot_id in expected_hero_tree_triplets() if str(slot_id or "").strip()}
    target_slot_ids = []
    for raw_value in raw_values:
        parts = [slugify(part, "") for part in str(raw_value or "").strip().split(":")]
        if len(parts) != 3 or not all(parts):
            continue
        slot_id = ":".join(parts)
        if slot_id in expected_slot_ids and slot_id not in target_slot_ids:
            target_slot_ids.append(slot_id)
    return target_slot_ids


def _community_gear_template_sync_mode_enabled(mode):
    configured = os.environ.get("WOW_COMMUNITY_TEMPLATE_SYNC_GEAR_MODE", "").strip().lower()
    requested = str(mode or "").strip().lower()
    enabled_modes = {
        "gear_template_first_sync",
        "gear-template-first-sync",
        "gear_first_sync",
        "gear-first-sync",
        "gear_template_targeted_refresh",
        "gear-template-targeted-refresh",
    }
    return configured in enabled_modes or requested in enabled_modes


def _int_env_value(names, default=0, minimum=0):
    for name in names:
        raw = os.environ.get(name)
        if raw in (None, ""):
            continue
        try:
            return max(minimum, int(str(raw).strip()))
        except (TypeError, ValueError):
            continue
    return max(minimum, int(default or 0))


def _bool_env_value(names, default=False):
    for name in names:
        raw = os.environ.get(name)
        if raw in (None, ""):
            continue
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return bool(default)


def _community_gear_first_sync_budget():
    return {
        "targetLimit": _int_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_TARGET_LIMIT", "WOW_GEAR_OBSERVED_BACKFILL_TARGET_LIMIT"],
            80,
            minimum=0,
        ),
        "profileLimit": _int_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_PROFILE_LIMIT", "WOW_GEAR_OBSERVED_BACKFILL_PROFILE_LIMIT"],
            40,
            minimum=0,
        ),
        "timeoutSeconds": _int_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_TIMEOUT_SECONDS", "WOW_GEAR_OBSERVED_BACKFILL_TIMEOUT_SECONDS"],
            600,
            minimum=1,
        ),
        "targetSpecLimit": _int_env_value(["WOW_COMMUNITY_GEAR_FIRST_SYNC_SPEC_LIMIT"], 8, minimum=0),
        "enableSimcStats": _bool_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_SIMC_STATS", "WOW_GEAR_OBSERVED_BACKFILL_SIMC_STATS"],
            False,
        ),
        "fullProfileGear": _bool_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_FULL_PROFILE_GEAR", "WOW_GEAR_OBSERVED_BACKFILL_FULL_PROFILE_GEAR"],
            True,
        ),
        "itemProbeLimit": _int_env_value(
            ["WOW_COMMUNITY_GEAR_FIRST_SYNC_ITEM_PROBE_LIMIT", "WOW_GEAR_OBSERVED_BACKFILL_ITEM_PROBE_LIMIT"],
            0,
            minimum=0,
        ),
    }


def _community_gear_projection_capture_budget():
    """Return hard-bounded exact profile and observed-item budgets."""

    return {
        "requestLimit": min(
            80,
            _int_env_value(["WOW_COMMUNITY_GEAR_PROJECTION_PROFILE_REQUEST_LIMIT"], 80, minimum=0),
        ),
        "captureTimeoutSeconds": min(
            300,
            _int_env_value(["WOW_COMMUNITY_GEAR_PROJECTION_CAPTURE_TIMEOUT_SECONDS"], 300, minimum=1),
        ),
        "backfillProfileLimit": min(
            80,
            _int_env_value(["WOW_COMMUNITY_GEAR_PROJECTION_BACKFILL_PROFILE_LIMIT"], 80, minimum=0),
        ),
        "backfillItemLimit": min(
            1280,
            _int_env_value(["WOW_COMMUNITY_GEAR_PROJECTION_BACKFILL_ITEM_LIMIT"], 1280, minimum=0),
        ),
        "backfillTimeoutSeconds": min(
            600,
            _int_env_value(["WOW_COMMUNITY_GEAR_PROJECTION_BACKFILL_TIMEOUT_SECONDS"], 600, minimum=1),
        ),
    }


def _gear_first_sync_target_specs(preflight, limit=0):
    specs = []
    for target in (preflight or {}).get("targetQueue") or []:
        if target.get("targetType") != "gear_template":
            continue
        if target.get("templateSlot") != "community_best":
            continue
        spec_id = str(target.get("specId") or "").strip()
        if spec_id and spec_id not in specs:
            specs.append(spec_id)
        if limit and len(specs) >= limit:
            break
    return specs


def _community_gear_first_sync_raiderio_env(target_spec_ids, budget):
    profile_limit = int((budget or {}).get("profileLimit") or 0)
    target_spec_ids = [str(spec_id or "").strip() for spec_id in target_spec_ids or [] if str(spec_id or "").strip()]
    per_spec_default = max(1, min(8, profile_limit // max(1, len(target_spec_ids) or 1))) if profile_limit else 1
    return {
        "WOW_RAIDERIO_RUN_PAGES": os.environ.get("WOW_COMMUNITY_GEAR_FIRST_SYNC_RUN_PAGES", "0"),
        "WOW_RAIDERIO_SPEC_RANKING_ENABLED": "1",
        "WOW_RAIDERIO_SPEC_RANKING_PAGES": os.environ.get("WOW_COMMUNITY_GEAR_FIRST_SYNC_SPEC_RANKING_PAGES", "1"),
        "WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE": os.environ.get("WOW_COMMUNITY_GEAR_FIRST_SYNC_SPEC_RANKING_PAGE_SIZE", "50"),
        "WOW_RAIDERIO_SPEC_RANKING_RUNS_PER_CHARACTER": "1",
        "WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS": ",".join(target_spec_ids),
        "WOW_RAIDERIO_PROFILE_LIMIT": str(profile_limit or 0),
        "WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC": os.environ.get(
            "WOW_COMMUNITY_GEAR_FIRST_SYNC_PROFILE_LIMIT_PER_SPEC",
            str(per_spec_default),
        ),
        "WOW_RAIDERIO_PROFILE_WORKERS": os.environ.get("WOW_COMMUNITY_GEAR_FIRST_SYNC_PROFILE_WORKERS", "2"),
        "WOW_RAIDERIO_RUN_DETAIL_LIMIT": "0",
        "WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC": "0",
        "WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT": "0",
        "WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_LIMIT_PER_SPEC": "0",
        "WOW_RAIDERIO_GAP_FILL_RUN_DETAIL_FRONTLOAD_PER_SPEC": "0",
        "WOW_RAIDERIO_RUN_DETAIL_WORKERS": "1",
        "WOW_RAIDERIO_COMMUNITY_TEMPLATE_LIMIT": "0",
    }


def _community_talent_missing_slot_ids(rows):
    matrix = build_community_talent_coverage_matrix(rows or {}, sources={})
    return [
        str(row.get("slotId") or "")
        for row in matrix.get("rows") or []
        if row.get("slotId") and (
            row.get("status") != "verified"
            or _community_talent_slot_freshness_expired(row, rows)
        )
    ]


def _parse_iso_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _community_template_freshness_expired(template, now=None):
    template = template if isinstance(template, dict) else {}
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    freshness = payload.get("communityTemplateFreshness") if isinstance(payload.get("communityTemplateFreshness"), dict) else {}
    if str(freshness.get("status") or "").strip() in {"stale", "refresh_failed", "needs_refresh"}:
        return True
    fresh_until = _parse_iso_datetime(freshness.get("freshUntil") or template.get("freshUntil"))
    if not fresh_until:
        return False
    now = now or datetime.now(timezone.utc)
    return fresh_until <= now


def _community_talent_slot_freshness_expired(row, templates):
    slot_id = str((row or {}).get("slotId") or "")
    if not slot_id:
        return False
    for template in templates or []:
        if not isinstance(template, dict):
            continue
        if _template_slot_id(template) != slot_id:
            continue
        if template.get("status") == "verified" and _community_template_freshness_expired(template):
            return True
    return False


def _community_talent_specs_for_slots(slot_ids):
    specs = []
    for slot_id in slot_ids or []:
        parts = str(slot_id or "").split(":")
        if len(parts) != 3:
            continue
        spec_id = f"{parts[0]}:{parts[1]}"
        if spec_id not in specs:
            specs.append(spec_id)
    return specs


def _community_talent_targeted_raiderio_env(target_spec_ids):
    target_spec_ids = [str(spec_id or "").strip() for spec_id in target_spec_ids or [] if str(spec_id or "").strip()]
    detail_limit = _int_env_value(
        ["WOW_COMMUNITY_TEMPLATE_TARGETED_RUN_DETAIL_LIMIT"],
        240,
        minimum=1,
    )
    per_spec_default = max(1, min(24, detail_limit // max(1, len(target_spec_ids))))
    detail_limit_per_spec = _int_env_value(
        ["WOW_COMMUNITY_TEMPLATE_TARGETED_RUN_DETAIL_LIMIT_PER_SPEC"],
        per_spec_default,
        minimum=1,
    )
    return {
        "WOW_RAIDERIO_RUN_PAGES": "0",
        "WOW_RAIDERIO_SPEC_RANKING_ENABLED": "1",
        "WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS": ",".join(target_spec_ids),
        "WOW_RAIDERIO_RUN_DETAIL_LIMIT": str(detail_limit),
        "WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC": str(detail_limit_per_spec),
    }


def _community_talent_templates_for_slots(templates, target_slot_ids):
    if target_slot_ids is None:
        return list(templates or [])
    allowed = {str(slot_id or "") for slot_id in target_slot_ids if str(slot_id or "").strip()}
    if not allowed:
        return []
    return [template for template in templates or [] if _template_slot_id(template) in allowed]


def _merge_community_talent_coverage_templates(existing_rows, validated_templates, target_slot_ids=None):
    by_slot = {}
    for template in existing_rows or []:
        slot_id = _template_slot_id(template)
        if slot_id:
            by_slot[slot_id] = template
    for template in validated_templates or []:
        slot_id = _template_slot_id(template)
        if slot_id:
            by_slot[slot_id] = template
    return list(by_slot.values())


def _with_temporary_env(overrides, callback):
    previous = {}
    for key, value in (overrides or {}).items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
    try:
        return callback()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _replace_community_talent_templates_with_details(store, templates, scan_run_id, target_slot_ids=None):
    try:
        result = store.replace_community_talent_templates(
            templates,
            scan_run_id=scan_run_id,
            include_details=True,
            target_slot_ids=target_slot_ids,
        )
    except TypeError:
        try:
            result = store.replace_community_talent_templates(
                templates,
                scan_run_id=scan_run_id,
                include_details=True,
            )
        except TypeError:
            result = store.replace_community_talent_templates(templates, scan_run_id=scan_run_id)
    result = result if isinstance(result, dict) else {}
    promoted = result.get("promotedTemplates") if isinstance(result.get("promotedTemplates"), list) else []
    validated = promoted or (result.get("validatedTemplates") if isinstance(result.get("validatedTemplates"), list) else [])
    counts = {
        "total": int(result.get("total") or 0),
        "verified": int(result.get("verified") or 0),
        "partial": int(result.get("partial") or 0),
        "blocked": int(result.get("blocked") or 0),
    }
    return counts, validated


def _community_talent_coverage_rows(store, fallback_templates):
    if fallback_templates:
        return fallback_templates
    if hasattr(store, "community_talent_template_coverage_rows"):
        try:
            rows = store.community_talent_template_coverage_rows()
            if isinstance(rows, list):
                return rows
        except Exception:
            return []
    return []


def _community_talent_source_freshness_maintenance(
    store,
    sources,
    checked_at,
    *,
    collection_attempted=True,
    source_attempts=None,
):
    results = {}
    successful_statuses = {"synced", "verified", "complete"}
    source_attempts = source_attempts if isinstance(source_attempts, dict) else {}
    for source_key, source in (sources or {}).items():
        source = source if isinstance(source, dict) else {}
        status = str(source.get("status") or "blocked").strip()
        region_coverage = source.get("regionCoverage") if isinstance(source.get("regionCoverage"), dict) else {}
        attempted = bool(source_attempts.get(source_key, collection_attempted))
        if not attempted:
            results[source_key] = {
                "status": "not_attempted",
                "sourceStatus": status,
                "regionCoverage": region_coverage,
            }
            continue
        successful_regions = sorted(
            str(region).strip().lower()
            for region, detail in region_coverage.items()
            if isinstance(detail, dict) and str(detail.get("status") or "").strip().lower() in successful_statuses
        )
        failed_regions = sorted(
            str(region).strip().lower()
            for region, detail in region_coverage.items()
            if isinstance(detail, dict) and str(detail.get("status") or "").strip().lower() in {"blocked", "failed"}
        )
        result = {
            "status": "success_observed" if status in successful_statuses else "not_recorded",
            "sourceStatus": status,
            "regionCoverage": region_coverage,
        }
        if (status in successful_statuses or successful_regions) and hasattr(store, "record_community_talent_source_sync_success"):
            try:
                recorded = store.record_community_talent_source_sync_success(
                    source_key,
                    checked_at=checked_at,
                    regions=successful_regions,
                )
                result["successUpdated"] = int((recorded or {}).get("updated") or 0) if isinstance(recorded, dict) else 0
            except Exception as error:
                result["successStatus"] = "record_failed"
                result["successError"] = str(error)
        should_record_failure = status not in successful_statuses and (not successful_regions or failed_regions)
        if should_record_failure and hasattr(store, "record_community_talent_source_sync_failure"):
            try:
                recorded = store.record_community_talent_source_sync_failure(
                    source_key,
                    checked_at=checked_at,
                    errors=source.get("errors") or [],
                    regions=failed_regions,
                )
                result["status"] = "failure_recorded"
                result["updated"] = int((recorded or {}).get("updated") or 0) if isinstance(recorded, dict) else 0
            except Exception as error:
                result["status"] = "record_failed"
                result["error"] = str(error)
        results[source_key] = result
    return results


def sync_community_template_cache_postgres(mode="scheduled", store=None, refresh_raiderio=True):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    timing_started_at = time.monotonic()
    stage_timings = []

    def record_stage(event):
        if isinstance(event, dict):
            stage_timings.append(dict(event))

    scan_run_id = f"pg-community-template-{checked_at.replace(':', '').replace('+', 'z')}"
    gear_template_sync_mode = _community_gear_template_sync_mode_enabled(mode)
    gear_first_sync_budget = _community_gear_first_sync_budget() if gear_template_sync_mode else {}
    gear_projection_capture_budget = _community_gear_projection_capture_budget()
    gear_target_spec_ids = []
    if gear_template_sync_mode:
        gear_seed_preflight = build_community_gear_template_preflight(
            _community_gear_template_coverage_rows(store, []),
            scan_run_id=scan_run_id,
            checked_at=checked_at,
        )
        gear_target_spec_ids = _gear_first_sync_target_specs(
            gear_seed_preflight,
            limit=gear_first_sync_budget.get("targetSpecLimit") or 0,
        )
    targeted_slots_mode = _community_template_targeted_slots_mode_enabled(mode)
    missing_slots_mode = _community_template_missing_slots_mode_enabled(mode)
    existing_talent_rows = []
    target_slot_ids = None
    target_spec_ids = []
    if targeted_slots_mode:
        target_slot_ids = _community_template_explicit_target_slot_ids()
        target_spec_ids = _community_talent_specs_for_slots(target_slot_ids)
        if not target_slot_ids:
            refresh_raiderio = False
    elif missing_slots_mode:
        existing_talent_rows = _community_talent_coverage_rows(store, [])
        target_slot_ids = _community_talent_missing_slot_ids(existing_talent_rows)
        target_spec_ids = _community_talent_specs_for_slots(target_slot_ids)
        if not target_slot_ids:
            refresh_raiderio = False
    source_started_at = time.monotonic()
    raiderio_collection_attempted = bool(refresh_raiderio)
    raiderio_refresh = {}
    if refresh_raiderio:
        raiderio_env = {}
        if gear_template_sync_mode:
            raiderio_env = _community_gear_first_sync_raiderio_env(gear_target_spec_ids, gear_first_sync_budget)
        elif targeted_slots_mode or missing_slots_mode:
            raiderio_env = _community_talent_targeted_raiderio_env(target_spec_ids)
        try:
            raiderio_refresh = _with_temporary_env(
                raiderio_env,
                lambda: sync_raiderio_cache_postgres(force=True, store=store, stage_callback=record_stage),
            ) or {}
        except Exception:
            raiderio_refresh = {
                "sourceStatus": "failed",
                "status": "failed",
                "errors": ["Raider.IO collection failed"],
            }
    source_results = load_community_talent_sources_postgres(store)
    raiderio_refresh_status = str(
        raiderio_refresh.get("sourceStatus") or raiderio_refresh.get("status") or ""
    ).strip().lower()
    if raiderio_collection_attempted and raiderio_refresh_status in {"failed", "blocked", "stale"}:
        previous = source_results.get("raiderio") if isinstance(source_results.get("raiderio"), dict) else {}
        source_results["raiderio"] = {
            **previous,
            "status": "failed",
            "templates": [],
            "errors": list(raiderio_refresh.get("errors") or ["Raider.IO collection failed"]),
            "regionCoverage": {},
        }
    stage_timings.append(
        _timing_stage(
            "source_collection",
            source_started_at,
            refreshRaiderio=bool(refresh_raiderio),
            sourceCount=len(source_results),
            targetMode="gear_template_first_sync" if gear_template_sync_mode else (
                "targeted_slots" if targeted_slots_mode else ("missing_slots" if missing_slots_mode else "all_slots")
            ),
            targetSlotCount=len(target_slot_ids or []),
            targetSpecCount=len(target_spec_ids or []),
            gearTargetSpecCount=len(gear_target_spec_ids or []),
        )
    )
    candidate_started_at = time.monotonic()
    if gear_template_sync_mode:
        talent_templates = []
        talent_errors = []
        talent_sources = {
            source_key: {
                "status": (source or {}).get("status") or (source or {}).get("sourceStatus") or "blocked",
                "sourceName": (source or {}).get("sourceName") or source_key,
                "candidateCount": len((source or {}).get("templates") or []),
                "verifiedCount": 0,
                "blockedCount": 0,
                "skippedCount": 0,
                "errors": (source or {}).get("errors") or [],
            }
            for source_key, source in source_results.items()
        }
    else:
        talent_templates, talent_sources, talent_errors = _community_templates_from_sources(source_results, scan_run_id)
        if targeted_slots_mode or missing_slots_mode:
            talent_templates = _community_talent_templates_for_slots(talent_templates, target_slot_ids)
    stage_timings.append(
        _timing_stage(
            "candidate_extraction",
            candidate_started_at,
            candidateCount=len(talent_templates),
            sourceCount=len(source_results),
        )
    )
    disabled_talent_sources = disabled_community_talent_template_source_keys()
    if not gear_template_sync_mode and disabled_talent_sources and hasattr(store, "expire_community_talent_template_sources"):
        store.expire_community_talent_template_sources(disabled_talent_sources, expired_at=checked_at)
    validated_talent_templates = []
    validation_started_at = time.monotonic()
    if gear_template_sync_mode:
        talent_counts = store.community_talent_template_counts()
    elif talent_templates:
        talent_counts, validated_talent_templates = _replace_community_talent_templates_with_details(
            store,
            talent_templates,
            scan_run_id,
            target_slot_ids=target_slot_ids,
        )
    else:
        talent_counts = store.community_talent_template_counts()
    stage_timings.append(
        _timing_stage(
            "validation_promotion_db_write",
            validation_started_at,
            candidateCount=len(talent_templates),
            promotedCount=talent_counts.get("promotedTotal") or talent_counts.get("total") or 0,
            verifiedCount=talent_counts.get("verified") or 0,
            blockedCount=talent_counts.get("blocked") or 0,
        )
    )
    gear_errors = []
    gear_observed_backfill = {}
    gear_profile_capture = {
        "schemaRevision": "raiderio-gear-projection-profile-capture-v1",
        "requestedIdentityCount": 0,
        "requestLimit": gear_projection_capture_budget["requestLimit"],
        "attemptedRequestCount": 0,
        "freshCachedProfileCount": 0,
        "capturedProfileCount": 0,
        "availableProfileCount": 0,
        "fetchFailureCount": 0,
        "deferredIdentityCount": 0,
        "deferredIdentityRefs": [],
        "deadlineReached": False,
        "requestBudgetExhausted": False,
        "missingCaptureCount": 0,
        "failures": [],
        "missingIdentityRefs": [],
        "diagnosticLimit": 12,
    }
    if not targeted_slots_mode:
        capture_started_at = time.monotonic()
        persisted_talent_rows = _community_talent_coverage_rows(store, [])
        merged_raiderio_payload = capture_gear_projection_profiles(
            persisted_talent_rows,
            store.get_raiderio_payload(),
            stage_callback=record_stage,
            request_limit=gear_projection_capture_budget["requestLimit"],
            deadline_at=time.monotonic() + gear_projection_capture_budget["captureTimeoutSeconds"],
        )
        gear_profile_capture = dict(merged_raiderio_payload.get("gearProjectionProfileCapture") or gear_profile_capture)
        if gear_profile_capture.get("requestedIdentityCount"):
            store.save_raiderio_payload(merged_raiderio_payload)
        if gear_profile_capture.get("availableProfileCount"):
            gear_observed_backfill = run_gear_observed_backfill_postgres(
                mode=mode,
                store=store,
                target_limit=gear_projection_capture_budget["backfillItemLimit"],
                profile_limit=min(
                    int(gear_profile_capture["availableProfileCount"]),
                    gear_projection_capture_budget["backfillProfileLimit"],
                ),
                timeout_seconds=gear_projection_capture_budget["backfillTimeoutSeconds"],
                enable_simc_stats=False,
                full_profile_gear=True,
                item_probe_limit=0,
            )
        if gear_profile_capture.get("fetchFailureCount") or gear_profile_capture.get("missingCaptureCount"):
            gear_errors.append(
                "exact Raider.IO gear profile capture incomplete: "
                f"fetchFailures={int(gear_profile_capture.get('fetchFailureCount') or 0)} "
                f"missing={int(gear_profile_capture.get('missingCaptureCount') or 0)}"
            )
        stage_timings.append(
            _timing_stage(
                "gear_projection_profile_capture",
                capture_started_at,
                requestedIdentityCount=gear_profile_capture.get("requestedIdentityCount") or 0,
                capturedProfileCount=gear_profile_capture.get("capturedProfileCount") or 0,
                availableProfileCount=gear_profile_capture.get("availableProfileCount") or 0,
                fetchFailureCount=gear_profile_capture.get("fetchFailureCount") or 0,
                missingCaptureCount=gear_profile_capture.get("missingCaptureCount") or 0,
            )
        )
    if gear_template_sync_mode and not gear_observed_backfill:
        backfill_started_at = time.monotonic()
        gear_observed_backfill = run_gear_observed_backfill_postgres(
            mode=mode,
            store=store,
            target_limit=gear_first_sync_budget.get("targetLimit"),
            profile_limit=gear_first_sync_budget.get("profileLimit"),
            timeout_seconds=gear_first_sync_budget.get("timeoutSeconds"),
            enable_simc_stats=gear_first_sync_budget.get("enableSimcStats"),
            full_profile_gear=gear_first_sync_budget.get("fullProfileGear"),
            item_probe_limit=gear_first_sync_budget.get("itemProbeLimit"),
        )
        stage_timings.append(
            _timing_stage(
                "gear_observed_backfill",
                backfill_started_at,
                status=gear_observed_backfill.get("status") or "",
                sourceStatus=gear_observed_backfill.get("sourceStatus") or "",
                targetLimit=gear_observed_backfill.get("targetLimit"),
                profileLimit=gear_observed_backfill.get("profileLimit"),
                processedProfileCount=gear_observed_backfill.get("processedProfileCount"),
                variantCount=gear_observed_backfill.get("variantCount"),
                itemProbeLimit=gear_observed_backfill.get("itemProbeLimit"),
                simcItemProbeCount=gear_observed_backfill.get("simcItemProbeCount"),
                simcItemProbeResolvedCount=gear_observed_backfill.get("simcItemProbeResolvedCount"),
                stopReason=gear_observed_backfill.get("stopReason") or "",
            )
        )
    if (gear_observed_backfill.get("sourceStatus") or gear_observed_backfill.get("status")) == "blocked":
        gear_errors.extend(gear_observed_backfill.get("errors") or [])
    gear_templates = []
    gear_started_at = time.monotonic()
    if not targeted_slots_mode and hasattr(store, "build_community_gear_templates"):
        try:
            gear_templates = store.build_community_gear_templates(scan_run_id=scan_run_id)
        except Exception as error:
            gear_errors.append(f"community gear templates failed: {error}")
            gear_templates = []
    if gear_templates and not targeted_slots_mode:
        gear_counts = store.replace_community_gear_templates(gear_templates, scan_run_id=scan_run_id)
    else:
        gear_counts = store.community_gear_template_counts()
    if targeted_slots_mode:
        real_player_cleanup = {"status": "skipped", "reason": "targeted_talent_slots"}
    else:
        real_player_cleanup = _cleanup_real_player_gear_template_pilot_residue(
            store,
            scan_run_id=scan_run_id,
            checked_at=checked_at,
        )
    if real_player_cleanup.get("errors"):
        gear_errors.extend(real_player_cleanup.get("errors") or [])
    gear_preflight = build_community_gear_template_preflight(
        _community_gear_template_coverage_rows(store, gear_templates),
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )
    stage_timings.append(
        _timing_stage(
            "gear_template_sync",
            gear_started_at,
            templateCount=gear_counts.get("total") or 0,
            verifiedCount=gear_counts.get("verified") or 0,
            blockedCount=gear_counts.get("blocked") or 0,
            totalSpecCount=gear_preflight.get("totalSpecCount") or 0,
            communityBestCompleteSpecCount=(gear_preflight.get("communityBest") or {}).get("completeSpecCount") or 0,
            baselineAvailableSpecCount=(gear_preflight.get("baseline") or {}).get("availableSpecCount") or 0,
            missingSlotCount=(gear_preflight.get("canonicalSlotMatrix") or {}).get("missingSlotCount") or 0,
            skipped=targeted_slots_mode,
        )
    )
    verified = talent_counts.get("verified", 0) + gear_counts.get("verified", 0)
    partial = talent_counts.get("partial", 0) + gear_counts.get("partial", 0)
    blocked = talent_counts.get("blocked", 0) + gear_counts.get("blocked", 0)
    coverage_started_at = time.monotonic()
    if gear_template_sync_mode:
        coverage_templates = _community_talent_coverage_rows(store, [])
    elif targeted_slots_mode or missing_slots_mode:
        coverage_templates = _merge_community_talent_coverage_templates(
            _community_talent_coverage_rows(store, []),
            validated_talent_templates,
            target_slot_ids=target_slot_ids,
        )
    else:
        coverage_templates = _community_talent_coverage_rows(store, validated_talent_templates)
    coverage_matrix = build_community_talent_coverage_matrix(
        coverage_templates,
        sources=talent_sources,
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )
    talent_sources = coverage_matrix.get("sourceSummary") if isinstance(coverage_matrix.get("sourceSummary"), dict) else talent_sources
    scan_coverage = scan_coverage_from_community_talent_matrix(coverage_matrix)
    coverage_status = coverage_matrix.get("status") or "partial"
    stage_timings.append(
        _timing_stage(
            "coverage_report",
            coverage_started_at,
            totalHeroSlotCount=coverage_matrix.get("totalHeroSlotCount") or 0,
            verifiedHeroSlotCount=coverage_matrix.get("verifiedHeroSlotCount") or 0,
            pendingCollectionHeroSlotCount=coverage_matrix.get("pendingCollectionHeroSlotCount") or 0,
            blockedHeroSlotCount=coverage_matrix.get("blockedHeroSlotCount") or 0,
        )
    )
    source_status = _status_from_counts_and_sources(
        verified,
        partial,
        blocked,
        sources=talent_sources,
        errors=[*talent_errors, *gear_errors],
    )
    if coverage_status != "verified" and source_status == "verified":
        source_status = "partial"
    talent_source_status = _status_from_counts_and_sources(
        talent_counts.get("verified", 0),
        talent_counts.get("partial", 0),
        talent_counts.get("blocked", 0),
        sources=talent_sources,
        errors=talent_errors,
    )
    if coverage_status != "verified" and talent_source_status == "verified":
        talent_source_status = "partial"
    talent_freshness = _community_talent_source_freshness_maintenance(
        store,
        talent_sources,
        checked_at,
        source_attempts={"raiderio": raiderio_collection_attempted},
    )
    payload = {
        "scanRunId": scan_run_id,
        "runner": "postgres",
        "mode": mode,
        "status": "completed" if source_status != "blocked" else "blocked",
        "sourceStatus": source_status,
        "startedAt": checked_at,
        "finishedAt": checked_at,
        "scanCoverage": scan_coverage,
        "talents": {"templates": talent_counts},
        "talentFreshness": talent_freshness,
        "gear": {
            "templates": gear_counts,
            "preflight": gear_preflight,
            "observedBackfill": gear_observed_backfill,
            "realPlayerTemplateCleanup": real_player_cleanup,
            "realCommunityTemplates": gear_preflight.get("realCommunityTemplates") or {},
            "baselineTemplates": gear_preflight.get("baseline") or {},
            "communityImportTemplates": gear_preflight.get("communityImport") or {},
        },
        "gearProfileCapture": gear_profile_capture,
        "sourceRefs": [
            {
                "sourceKey": source_key,
                "sourceName": source.get("sourceName") or source_key,
                "sourceStatus": source.get("status") or "blocked",
                "candidateCount": source.get("candidateCount") or 0,
                "verifiedCount": source.get("verifiedCount") or 0,
                "blockedCount": source.get("blockedCount") or 0,
                "skippedCount": source.get("skippedCount") or 0,
            }
            for source_key, source in talent_sources.items()
        ],
        "errors": [*talent_errors, *gear_errors][:20],
    }
    payload["stageTimings"] = _sync_timing_summary(
        timing_started_at,
        stage_timings,
        coverage_matrix=coverage_matrix,
        talent_counts=talent_counts,
    )
    talent_state = {
        "runner": "postgres",
        "mode": mode,
        "status": payload["status"],
        "sourceStatus": talent_source_status,
        "templates": talent_counts,
        "scanCoverage": payload["scanCoverage"],
        "coverageMatrix": coverage_matrix,
        "sources": talent_sources,
        "checkedAt": checked_at,
        "scanRunId": payload["scanRunId"],
        "errors": talent_errors[:20],
        "stageTimings": payload["stageTimings"],
        "freshness": talent_freshness,
    }
    sync_state_started_at = time.monotonic()
    store.save_sync_state(COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload, checked_at)
    store.save_sync_state(COMMUNITY_TALENT_SYNC_KEY, talent_state, checked_at)
    stage_timings.append(_timing_stage("sync_state_write", sync_state_started_at, stateCount=2))
    payload["stageTimings"] = _sync_timing_summary(
        timing_started_at,
        stage_timings,
        coverage_matrix=coverage_matrix,
        talent_counts=talent_counts,
    )
    talent_state["stageTimings"] = payload["stageTimings"]
    store.save_sync_state(COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload, checked_at)
    store.save_sync_state(COMMUNITY_TALENT_SYNC_KEY, talent_state, checked_at)
    return payload


def _season_recommended_template_confidence(template):
    payload = (template or {}).get("payload") if isinstance((template or {}).get("payload"), dict) else {}
    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
    return str(evidence.get("recommendationConfidence") or "").strip()


def _cleanup_real_player_gear_template_pilot_residue(store, scan_run_id="", checked_at=""):
    if not hasattr(store, "cleanup_real_player_gear_template_pilot_residue"):
        return {}
    try:
        return store.cleanup_real_player_gear_template_pilot_residue(
            scan_run_id=scan_run_id,
            checked_at=checked_at,
        )
    except Exception as error:
        return {"status": "blocked", "errors": [str(error)]}


def sync_season_recommended_gear_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    scan_run_id = f"season-recommended-gear-{checked_at.replace('+00:00', 'Z').replace(':', '').replace('-', '')}"
    errors = []
    try:
        templates = store.build_season_recommended_gear_templates(scan_run_id=scan_run_id)
    except Exception as error:
        templates = []
        errors.append(str(error))
    if templates:
        counts = store.replace_community_gear_templates(templates, scan_run_id=scan_run_id)
    else:
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
    real_player_cleanup = _cleanup_real_player_gear_template_pilot_residue(
        store,
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )
    if real_player_cleanup.get("errors"):
        errors.extend(real_player_cleanup.get("errors") or [])

    complete_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if template.get("status") == "complete" and template.get("sourceKey") == "season_recommendation"
    )
    verified_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if _season_recommended_template_confidence(template) == "verified"
    )
    provisional_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if _season_recommended_template_confidence(template) == "provisional"
    )
    expected_specs = unique_text_list(expected_spec_pairs())
    blocked_specs = [spec_id for spec_id in expected_specs if spec_id not in set(complete_specs)]
    total_spec_count = len(expected_specs) or len(complete_specs)
    status = "verified" if total_spec_count and len(complete_specs) >= total_spec_count and not errors else "partial"
    if not complete_specs and errors:
        status = "blocked"
    preflight = build_community_gear_template_preflight(
        _community_gear_template_coverage_rows(store, templates) or templates,
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )
    payload = {
        "runner": "postgres",
        "mode": mode,
        "sourceKey": "season_recommendation",
        "sourceName": "当前赛季大秘境 AOE 推荐模板",
        "status": status,
        "sourceStatus": "synced" if status == "verified" else status,
        "scanRunId": scan_run_id,
        "checkedAt": checked_at,
        "totalSpecCount": total_spec_count,
        "completeSpecCount": len(complete_specs),
        "verifiedSpecCount": len(verified_specs),
        "provisionalSpecCount": len(provisional_specs),
        "blockedSpecCount": len(blocked_specs),
        "completeSpecs": complete_specs,
        "verifiedSpecs": verified_specs,
        "provisionalSpecs": provisional_specs,
        "blockedSpecs": blocked_specs,
        "templates": counts,
        "communityImportTemplates": preflight.get("communityImport") or {},
        "realPlayerTemplateCleanup": real_player_cleanup,
        "errors": errors[:20],
    }
    store.save_sync_state(SEASON_RECOMMENDED_GEAR_SYNC_KEY, payload, checked_at)
    return payload


def _recommended_bis_template_evidence_status(template):
    payload = (template or {}).get("payload") if isinstance((template or {}).get("payload"), dict) else {}
    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
    return str(evidence.get("status") or evidence.get("confidence") or "").strip()


def sync_recommended_bis_prototype_postgres(mode="manual", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    scan_run_id = f"recommended-bis-prototype-{checked_at.replace('+00:00', 'Z').replace(':', '').replace('-', '')}"
    errors = []
    try:
        templates = store.build_recommended_bis_prototype_templates(scan_run_id=scan_run_id)
    except Exception as error:
        templates = []
        errors.append(str(error))
    if templates:
        counts = store.replace_community_gear_templates(templates, scan_run_id=scan_run_id)
    else:
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
    real_player_cleanup = _cleanup_real_player_gear_template_pilot_residue(
        store,
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )
    if real_player_cleanup.get("errors"):
        errors.extend(real_player_cleanup.get("errors") or [])

    projected_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if _recommended_bis_template_evidence_status(template) == "projected_bis"
    )
    candidate_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if _recommended_bis_template_evidence_status(template) == "candidate_bis"
    )
    verified_specs = unique_text_list(
        f"{template.get('classKey')}:{template.get('specKey')}"
        for template in templates
        if _recommended_bis_template_evidence_status(template) == "verified_bis"
    )
    expected_specs = unique_text_list(expected_spec_pairs())
    dps_expected_specs = [
        spec_id for spec_id in expected_specs
        if recommended_bis_role_for_spec_id(spec_id) == "dps"
    ]
    covered_specs = set(projected_specs) | set(candidate_specs) | set(verified_specs)
    missing_dps_specs = [spec_id for spec_id in dps_expected_specs if spec_id not in covered_specs]
    full_optimizer_specs = unique_text_list([*projected_specs, *candidate_specs, *missing_dps_specs])
    status = "blocked"
    if templates and not errors:
        status = "partial"
    if verified_specs and len(verified_specs) >= len(dps_expected_specs) and not errors:
        status = "verified"
    payload = {
        "runner": "postgres",
        "schemaRevision": "recommended-bis-v1-prototype-sync-state-v1",
        "mode": mode,
        "sourceKey": "recommended_bis",
        "sourceName": "SimC optimizer 毕业模板",
        "status": status,
        "sourceStatus": status,
        "scanRunId": scan_run_id,
        "checkedAt": checked_at,
        "totalSpecCount": len(covered_specs),
        "expectedSpecCount": len(expected_specs),
        "dpsExpectedSpecCount": len(dps_expected_specs),
        "projectedSpecCount": len(projected_specs),
        "candidateSpecCount": len(candidate_specs),
        "verifiedSpecCount": len(verified_specs),
        "missingDpsSpecCount": len(missing_dps_specs),
        "fullOptimizerRunRequiredSpecCount": len(full_optimizer_specs),
        "projectedSpecs": projected_specs,
        "candidateSpecs": candidate_specs,
        "verifiedSpecs": verified_specs,
        "missingDpsSpecs": missing_dps_specs,
        "fullOptimizerRunRequiredSpecs": full_optimizer_specs,
        "templates": counts,
        "realPlayerTemplateCleanup": real_player_cleanup,
        "errors": errors[:20],
    }
    store.save_sync_state(RECOMMENDED_BIS_PROTOTYPE_SYNC_KEY, payload, checked_at)
    return payload


def _recommended_bis_guard_status(recommended, errors=None):
    errors = errors or []
    if errors:
        return "blocked"
    expected = int(recommended.get("expectedSpecCount") or 0)
    total = int(recommended.get("totalSpecCount") or 0)
    verified = int(recommended.get("verifiedSpecCount") or 0)
    missing = int(recommended.get("missingSpecCount") or 0)
    blocked = int(recommended.get("blockedSpecCount") or 0)
    if expected and verified >= expected:
        return "verified"
    if expected and not total and (missing >= expected or blocked >= expected):
        return "blocked"
    if expected and (missing or blocked):
        return "partial"
    if not expected:
        return "blocked"
    return "partial"


def _community_best_guard_status(observed, errors=None):
    errors = errors or []
    if errors:
        return "blocked"
    expected = int(observed.get("expectedSpecCount") or 0)
    covered = int(observed.get("coveredSpecCount") or 0)
    verified = int(observed.get("verifiedSpecCount") or 0)
    missing = int(observed.get("missingSpecCount") or 0)
    blocked = int(observed.get("blockedSpecCount") or 0)
    replay_required = int(observed.get("simcReplayRequiredSpecCount") or 0)
    if expected and verified >= expected and not (missing or blocked or replay_required):
        return "verified"
    if expected and not covered and (missing or blocked):
        return "blocked"
    if not expected:
        return "blocked"
    return "partial"


def sync_community_best_guard_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    errors = []
    summary = {}
    try:
        summary = store.community_gear_template_live_health_summary()
    except Exception as error:
        errors.append(str(error))
    chains = (summary or {}).get("templateChains") if isinstance(summary, dict) else {}
    observed = chains.get("communityObserved") if isinstance(chains, dict) else {}
    if not isinstance(observed, dict) or not observed:
        observed = websim_gear_template_chain_state(
            [],
            [],
            expected_spec_ids=expected_spec_pairs(),
            checked_at=checked_at,
        ).get("communityObserved") or {}
    status = _community_best_guard_status(observed, errors=errors)
    payload = {
        "runner": "postgres",
        "schemaRevision": "community-best-v2-guard-state-v1",
        "mode": mode,
        "status": status,
        "sourceStatus": status,
        "guardMode": observed.get("guardMode") or "readiness_only",
        "guardPolicy": observed.get("guardPolicy") or (
            "reports missing community_best_v2 observed specs, blocked observed candidates, "
            "and observed templates requiring SimC replay; does not fetch profiles, run SimC, or replace winners"
        ),
        "checkedAt": checked_at,
        "lastGuardCheckAt": checked_at,
        "dailyCheckedAt": checked_at,
        "sourceScanRunId": (summary or {}).get("scanRunId") if isinstance(summary, dict) else "",
        "expectedSpecCount": int(observed.get("expectedSpecCount") or 0),
        "coveredSpecCount": int(observed.get("coveredSpecCount") or 0),
        "verifiedSpecCount": int(observed.get("verifiedSpecCount") or 0),
        "provisionalSpecCount": int(observed.get("provisionalSpecCount") or 0),
        "partialSpecCount": int(observed.get("partialSpecCount") or 0),
        "blockedSpecCount": int(observed.get("blockedSpecCount") or 0),
        "missingSpecCount": int(observed.get("missingSpecCount") or 0),
        "simcReplayRequiredSpecCount": int(observed.get("simcReplayRequiredSpecCount") or 0),
        "changedWinnerCount": int(observed.get("changedWinnerCount") or 0),
        "simcReplayQueuedCount": int(observed.get("simcReplayQueuedCount") or 0),
        "missingSpecs": observed.get("missingSpecs") or [],
        "simcReplayRequiredSpecs": observed.get("simcReplayRequiredSpecs") or [],
        "examples": observed.get("examples") or [],
        "blockedExamples": observed.get("blockedExamples") or [],
        "errors": errors[:20],
    }
    store.save_sync_state(COMMUNITY_BEST_GUARD_SYNC_KEY, payload, checked_at)
    return payload


def sync_recommended_bis_guard_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    errors = []
    summary = {}
    try:
        summary = store.community_gear_template_live_health_summary()
    except Exception as error:
        errors.append(str(error))
    chains = (summary or {}).get("templateChains") if isinstance(summary, dict) else {}
    recommended = chains.get("recommendedBis") if isinstance(chains, dict) else {}
    if not isinstance(recommended, dict) or not recommended:
        recommended = websim_gear_template_chain_state(
            [],
            [],
            expected_spec_ids=expected_spec_pairs(),
            checked_at=checked_at,
        ).get("recommendedBis") or {}
    status = _recommended_bis_guard_status(recommended, errors=errors)
    payload = {
        "runner": "postgres",
        "schemaRevision": "recommended-bis-v1-guard-state-v1",
        "mode": mode,
        "status": status,
        "sourceStatus": status,
        "guardMode": recommended.get("guardMode") or "readiness_only",
        "guardPolicy": recommended.get("guardPolicy") or (
            "reports missing recommended_bis_v1 specs as optimizer_required; "
            "does not execute or queue the full SimC optimizer"
        ),
        "checkedAt": checked_at,
        "lastGuardCheckAt": checked_at,
        "sourceScanRunId": (summary or {}).get("scanRunId") if isinstance(summary, dict) else "",
        "totalSpecCount": int(recommended.get("totalSpecCount") or 0),
        "expectedSpecCount": int(recommended.get("expectedSpecCount") or 0),
        "missingSpecCount": int(recommended.get("missingSpecCount") or 0),
        "projectedSpecCount": int(recommended.get("projectedSpecCount") or 0),
        "candidateSpecCount": int(recommended.get("candidateSpecCount") or 0),
        "verifiedSpecCount": int(recommended.get("verifiedSpecCount") or 0),
        "blockedSpecCount": int(recommended.get("blockedSpecCount") or 0),
        "anchorFailedSpecCount": int(recommended.get("anchorFailedSpecCount") or 0),
        "optimizerFailedSpecCount": int(recommended.get("optimizerFailedSpecCount") or 0),
        "optimizerRequiredSpecCount": int(recommended.get("optimizerRequiredSpecCount") or 0),
        "revisionStaleSpecCount": int(recommended.get("revisionStaleSpecCount") or 0),
        "optimizerQueuedSpecCount": int(recommended.get("optimizerQueuedSpecCount") or 0),
        "fullOptimizerRunRequiredSpecCount": int(recommended.get("fullOptimizerRunRequiredSpecCount") or 0),
        "missingSpecs": recommended.get("missingSpecs") or [],
        "examples": recommended.get("examples") or [],
        "blockedExamples": recommended.get("blockedExamples") or [],
        "errors": errors[:20],
    }
    store.save_sync_state(RECOMMENDED_BIS_GUARD_SYNC_KEY, payload, checked_at)
    return payload


def load_crafted_gear_seed_postgres():
    raw = os.environ.get("WOW_CRAFTED_GEAR_SEED_JSON", "").strip()
    if raw:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = parsed.get("items") or parsed.get("gear") or []
        return parsed if isinstance(parsed, list) else []
    rows = []
    for item in crafted_pve_membership_items():
        mode = str(item.get("secondaryStatMode") or "").strip()
        if mode == "customize_two_secondary":
            stat_values = CRAFTED_DOUBLE_SECONDARY_VALUES
        elif mode == "amplify_one_secondary":
            stat_values = CRAFTED_SINGLE_SECONDARY_VALUES
        elif mode == "fixed_or_recipe_defined_stats":
            stat_values = ("",)
        else:
            continue
        slot = str(item.get("slot") or "").strip()
        levels = [("crafted_myth", 285)]
        if (
            item.get("supportsVoidUpgrade") is True
            and str(
                item.get("voidUpgradeEligibilityStatus") or ""
            ).strip()
            == "verified"
        ):
            levels.append(("crafted_void_upgrade", 295))
        for difficulty_key, item_level in levels:
            for crafted_stats in stat_values:
                variant_suffix = crafted_stats.replace("/", "-") or "fixed"
                rows.append(
                    {
                        **item,
                        "itemLevel": item_level,
                        "crafted_stats": crafted_stats,
                        "difficultyKey": difficulty_key,
                        "variantKey": (
                            f"crafted-{difficulty_key}-{item_level}-"
                            f"{variant_suffix}"
                        ),
                        "sourceLabel": "制造装备",
                        "sourceRefs": [
                            {
                                "sourceType": "current_client_crafting_relation",
                                "status": item.get("membershipStatus"),
                                "recipeId": item.get("recipeId"),
                                "clientBuild": item.get("clientBuild"),
                                "evidenceRef": item.get("evidenceRef"),
                            },
                            {
                                "sourceType": "battle_net_item_search",
                                "status": "verified",
                                "sourceUrl": item.get("officialItemRef"),
                            },
                        ],
                        "status": "partial",
                        "blockers": [
                            "current-season membership verified; exact "
                            "SimulationCraft stat payload pending",
                            "OFFICIAL_PROGRESSION_STATE_UNAVAILABLE",
                        ],
                    }
                )
    return rows


def run_gear_observed_backfill_postgres(
    mode="scheduled",
    store=None,
    target_limit=None,
    profile_limit=None,
    timeout_seconds=None,
    enable_simc_stats=None,
    full_profile_gear=None,
    item_probe_limit=None,
):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    target_limit = (
        _int_env_value(["WOW_GEAR_OBSERVED_BACKFILL_TARGET_LIMIT"], 80, minimum=0)
        if target_limit is None
        else max(0, int(target_limit or 0))
    )
    profile_limit = (
        _int_env_value(["WOW_GEAR_OBSERVED_BACKFILL_PROFILE_LIMIT"], 40, minimum=0)
        if profile_limit is None
        else max(0, int(profile_limit or 0))
    )
    timeout_seconds = (
        _int_env_value(["WOW_GEAR_OBSERVED_BACKFILL_TIMEOUT_SECONDS"], 600, minimum=1)
        if timeout_seconds is None
        else max(1, int(timeout_seconds or 1))
    )
    if enable_simc_stats is None:
        enable_simc_stats = _bool_env_value(["WOW_GEAR_OBSERVED_BACKFILL_SIMC_STATS"], False)
    if full_profile_gear is None:
        full_profile_gear = _bool_env_value(["WOW_GEAR_OBSERVED_BACKFILL_FULL_PROFILE_GEAR"], True)
    item_probe_limit = (
        _int_env_value(["WOW_GEAR_OBSERVED_BACKFILL_ITEM_PROBE_LIMIT"], 0, minimum=0)
        if item_probe_limit is None
        else max(0, int(item_probe_limit or 0))
    )
    get_sync_state = getattr(store, "get_sync_state", None)
    prior_state = (
        get_sync_state(GEAR_OBSERVED_BACKFILL_SYNC_KEY)
        if callable(get_sync_state)
        else {}
    )
    prior_state = prior_state if isinstance(prior_state, dict) else {}
    profile_cursor = (
        prior_state.get("profileCursor")
        if isinstance(prior_state.get("profileCursor"), dict)
        else {}
    )
    try:
        try:
            result = store.backfill_observed_gear_from_raiderio(
                store.get_raiderio_payload(),
                mode=mode,
                target_limit=target_limit,
                profile_limit=profile_limit,
                timeout_seconds=timeout_seconds,
                enable_simc_stats=enable_simc_stats,
                full_profile_gear=full_profile_gear,
                item_probe_limit=item_probe_limit,
                profile_cursor=profile_cursor,
            )
        except TypeError:
            result = store.backfill_observed_gear_from_raiderio(store.get_raiderio_payload(), mode=mode)
    except Exception as error:
        result = {
            "status": "blocked",
            "sourceStatus": "blocked",
            "errors": [f"Observed gear PG-native backfill failed: {error}"],
        }
    payload = {
        "runner": "postgres",
        "mode": mode,
        "checkedAt": checked_at,
        "targetLimit": target_limit,
        "profileLimit": profile_limit,
        "timeoutSeconds": timeout_seconds,
        "enableSimcStats": bool(enable_simc_stats),
        "fullProfileGear": bool(full_profile_gear),
        "itemProbeLimit": item_probe_limit,
        **(result if isinstance(result, dict) else {}),
    }
    payload.setdefault("status", payload.get("sourceStatus") or "blocked")
    payload.setdefault("sourceStatus", payload.get("status") or "blocked")
    payload.setdefault("profileCursor", profile_cursor)
    payload.setdefault("errors", [])
    store.save_sync_state(GEAR_OBSERVED_BACKFILL_SYNC_KEY, payload, checked_at)
    return payload


def run_crafted_gear_backfill_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    seed_items = load_crafted_gear_seed_postgres()
    try:
        result = store.backfill_crafted_gear_from_seed(seed_items, mode=mode)
    except Exception as error:
        result = {
            "status": "blocked",
            "sourceStatus": "blocked",
            "errors": [f"Crafted gear PG-native backfill failed: {error}"],
        }
    payload = {
        "runner": "postgres",
        "mode": mode,
        "checkedAt": checked_at,
        "seedItemCount": len(seed_items),
        **(result if isinstance(result, dict) else {}),
    }
    payload.setdefault("status", payload.get("sourceStatus") or "blocked")
    payload.setdefault("sourceStatus", payload.get("status") or "blocked")
    payload.setdefault("errors", [])
    store.save_sync_state(CRAFTED_GEAR_BACKFILL_SYNC_KEY, payload, checked_at)
    return payload
