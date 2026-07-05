#!/usr/bin/env python3
import os
import json
import sqlite3
import time

try:
    from .db import connect_postgres, database_config_from_env
    from .postgres_cache_store import PostgresCacheStore, utc_now
    from .raiderio_payload import sync_raiderio_cache
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
        blizzard_get,
        blizzard_namespace,
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
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        slugify,
        spec_label,
        unique_text_list,
    )
except ImportError:
    from db import connect_postgres, database_config_from_env
    from postgres_cache_store import PostgresCacheStore, utc_now
    from raiderio_payload import sync_raiderio_cache
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
        blizzard_get,
        blizzard_namespace,
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
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        slugify,
        spec_label,
        unique_text_list,
    )


CRAFTED_GEAR_BACKFILL_SYNC_KEY = "crafted_gear_backfill"
COMMUNITY_TALENT_COVERAGE_MATRIX_REVISION = "community-talent-coverage-matrix-v1"
COMMUNITY_GEAR_TEMPLATE_PREFLIGHT_REVISION = "community-gear-template-preflight-v1"
COMMUNITY_TEMPLATE_STAGE_TIMING_REVISION = "community-template-stage-timings-v1"
BASELINE_GEAR_TEMPLATE_SOURCE_KEYS = {DEFAULT_GEAR_TEMPLATE_SOURCE_KEY, "baseline_template", "simc_preset"}
BAD_REAL_GEAR_TEMPLATE_SOURCE_KEYS = {
    "",
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
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
    raid_refs = raid_pool_status.get("refs") or official_current_season_raid_refs()
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
            continue
        encounter_refs, _skipped = limited_sync_items(
            encounter_refs,
            remaining_encounter_capacity if encounter_limit >= 0 else len(encounter_refs),
        )
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
                if not item_id or (item_limit >= 0 and len(fetched_items) >= item_limit and item_id not in fetched_items):
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
    return {"season": season, "instances": instances, "counts": counts}


def sync_raiderio_cache_postgres(force=False, stage_callback=None, store=None):
    store = store or cache_store_from_env()
    _emit(stage_callback, "raiderio", "start", force=bool(force))
    try:
        conn = sqlite3.connect(":memory:")
        try:
            payload = sync_raiderio_cache(conn, force=force, stage_callback=stage_callback)
        finally:
            conn.close()
    except Exception as error:
        cached = dict(store.get_raiderio_payload() or {})
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
    if payload.get("sourceStatus") != "stale":
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


def sync_websim_cache_postgres(include_blizzard=True, stage_callback=None, store=None):
    store = store or cache_store_from_env()
    _emit(stage_callback, "websim", "start", includeBlizzard=bool(include_blizzard))
    checked_at = utc_now()
    simc_counts = {
        "talents": 0,
        "profiles": 0,
        "spellDetails": 0,
        "build": "",
        "source": "",
        "traitEdgeSource": "",
        "errors": [],
    }
    try:
        _emit(stage_callback, "simc", "start", runner="postgres")
        simc_counts = store.replace_simc_generated_data(extract_simc_generated_data())
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
        simc_counts["errors"] = [str(error)]
        _emit(stage_callback, "simc", "blocked", runner="postgres", errors=1)
    blizzard_counts = {"runner": "postgres", "skipped": not include_blizzard}
    gear_catalog = store.get_sync_state("gearCatalog") or {}
    if include_blizzard:
        try:
            _emit(stage_callback, "blizzard", "start", runner="postgres")
            journal_data = fetch_websim_journal_data_postgres()
            blizzard_counts = store.replace_websim_journal_data(journal_data)
            blizzard_counts["runner"] = "postgres"
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
    talent_state = store.get_sync_state("websim_sync") or {}
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
        "talentHealth": talent_state.get("talentHealth") if isinstance(talent_state.get("talentHealth"), dict) else {},
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


def _gear_display_row(spec_id, class_key, spec_key, template_slot, template, status):
    template = template if isinstance(template, dict) else {}
    missing_slots = _gear_template_missing_slots(template, class_key, spec_key) if template else list(CANONICAL_GEAR_SLOTS)
    ready_slots = _gear_template_ready_slots(template, class_key, spec_key)
    ready_count = _gear_template_ready_count(template, class_key, spec_key) if template else 0
    target_key = f"gear-template:{class_key}:{spec_key}:{template_slot}:{DEFAULT_GEAR_TEMPLATE_SCENARIO_KEY}"
    if template_slot == "baseline" and status == "available":
        next_action = "keep_baseline_available"
    elif template_slot == "baseline":
        next_action = "build_baseline_template"
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
        "status": row["status"],
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
        best_community = _best_gear_template(grouped.get(spec_id, {}).get("community"))
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
    matrix_status = "verified" if complete_specs and len(complete_specs) == len(expected_specs) else "partial"
    if blocked_specs and not complete_specs and not partial_specs and not pending_specs:
        matrix_status = "blocked"
    incomplete_specs = [*partial_specs, *pending_specs, *blocked_specs]
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
            "countingPolicy": "real community gear only; baseline/default templates do not fill this coverage",
        },
        "baseline": {
            "templateSlot": "baseline",
            "totalSpecCount": len(expected_specs),
            "availableSpecCount": len(baseline_available_specs),
            "blockedSpecCount": len(baseline_blocked_specs),
            "availableSpecs": baseline_available_specs,
            "blockedSpecs": baseline_blocked_specs,
            "countingPolicy": "baseline is a separate display slot and is excluded from real community coverage",
        },
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
        if row.get("slotId") and row.get("status") != "verified"
    ]


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
    missing_slots_mode = _community_template_missing_slots_mode_enabled(mode)
    existing_talent_rows = []
    target_slot_ids = None
    target_spec_ids = []
    if missing_slots_mode:
        existing_talent_rows = _community_talent_coverage_rows(store, [])
        target_slot_ids = _community_talent_missing_slot_ids(existing_talent_rows)
        target_spec_ids = _community_talent_specs_for_slots(target_slot_ids)
        if not target_slot_ids:
            refresh_raiderio = False
    source_started_at = time.monotonic()
    if refresh_raiderio:
        raiderio_env = {}
        if gear_template_sync_mode:
            raiderio_env = _community_gear_first_sync_raiderio_env(gear_target_spec_ids, gear_first_sync_budget)
        elif missing_slots_mode:
            raiderio_env = {
                "WOW_RAIDERIO_RUN_PAGES": "0",
                "WOW_RAIDERIO_SPEC_RANKING_ENABLED": "1",
                "WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS": ",".join(target_spec_ids),
            }
        _with_temporary_env(
            raiderio_env,
            lambda: sync_raiderio_cache_postgres(force=True, store=store, stage_callback=record_stage),
        )
    source_results = load_community_talent_sources_postgres(store)
    stage_timings.append(
        _timing_stage(
            "source_collection",
            source_started_at,
            refreshRaiderio=bool(refresh_raiderio),
            sourceCount=len(source_results),
            targetMode="gear_template_first_sync" if gear_template_sync_mode else ("missing_slots" if missing_slots_mode else "all_slots"),
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
        if missing_slots_mode:
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
    if gear_template_sync_mode:
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
        if (gear_observed_backfill.get("sourceStatus") or gear_observed_backfill.get("status")) == "blocked":
            gear_errors.extend(gear_observed_backfill.get("errors") or [])
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
    gear_templates = []
    gear_started_at = time.monotonic()
    if hasattr(store, "build_community_gear_templates"):
        try:
            gear_templates = store.build_community_gear_templates(scan_run_id=scan_run_id)
        except Exception as error:
            gear_errors.append(f"community gear templates failed: {error}")
            gear_templates = []
    if gear_templates:
        gear_counts = store.replace_community_gear_templates(gear_templates, scan_run_id=scan_run_id)
    else:
        gear_counts = store.community_gear_template_counts()
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
        )
    )
    verified = talent_counts.get("verified", 0) + gear_counts.get("verified", 0)
    partial = talent_counts.get("partial", 0) + gear_counts.get("partial", 0)
    blocked = talent_counts.get("blocked", 0) + gear_counts.get("blocked", 0)
    coverage_started_at = time.monotonic()
    if gear_template_sync_mode:
        coverage_templates = _community_talent_coverage_rows(store, [])
    elif missing_slots_mode:
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
        "gear": {
            "templates": gear_counts,
            "preflight": gear_preflight,
            "observedBackfill": gear_observed_backfill,
            "realCommunityTemplates": gear_preflight.get("realCommunityTemplates") or {},
            "baselineTemplates": gear_preflight.get("baseline") or {},
        },
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


def load_crafted_gear_seed_postgres():
    raw = os.environ.get("WOW_CRAFTED_GEAR_SEED_JSON", "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("items") or parsed.get("gear") or []
    return parsed if isinstance(parsed, list) else []


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
