#!/usr/bin/env python3
import os
import json

try:
    from .db import connect_postgres, database_config_from_env
    from .postgres_cache_store import PostgresCacheStore, utc_now
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
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        DEFAULT_REGION,
        GEAR_CATALOG_REVISION,
        GEAR_OBSERVED_BACKFILL_SYNC_KEY,
        blizzard_get,
        blizzard_namespace,
        current_season_raid_pool_status,
        extract_simc_generated_data,
        extract_id_from_ref,
        fetch_blizzard_item_metadata,
        get_blizzard_access_token,
        icon_url_from_media,
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        unique_text_list,
    )
except ImportError:
    from db import connect_postgres, database_config_from_env
    from postgres_cache_store import PostgresCacheStore, utc_now
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
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        DEFAULT_LOCALE,
        DEFAULT_REGION,
        GEAR_CATALOG_REVISION,
        GEAR_OBSERVED_BACKFILL_SYNC_KEY,
        blizzard_get,
        blizzard_namespace,
        current_season_raid_pool_status,
        extract_simc_generated_data,
        extract_id_from_ref,
        fetch_blizzard_item_metadata,
        get_blizzard_access_token,
        icon_url_from_media,
        item_payload_is_equipment_loot,
        item_slot_from_payload,
        limited_sync_items,
        list_keyed_values,
        normalize_journal_instance_ref,
        official_current_season_raid_refs,
        resolve_current_mythic_season,
        selected_journal_instance_refs,
        unique_text_list,
    )


CRAFTED_GEAR_BACKFILL_SYNC_KEY = "crafted_gear_backfill"


def cache_store_from_env():
    config = database_config_from_env()
    if config.backend != "postgres" or not config.database_url:
        raise RuntimeError("PostgreSQL cache sync requires WOW_DATABASE_URL")
    return PostgresCacheStore(lambda: connect_postgres(config.database_url))


def _emit(stage_callback, stage, status, **details):
    if stage_callback:
        stage_callback({"stage": stage, "status": status, **details})


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
    payload = store.get_raiderio_payload()
    payload = dict(payload or {})
    payload["runner"] = "postgres"
    payload.setdefault("sourceStatus", payload.get("status") or "blocked")
    payload.setdefault("status", payload.get("sourceStatus") or "blocked")
    payload.setdefault("checkedAt", utc_now())
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


def load_community_talent_sources_postgres(store):
    try:
        from .community_talent_sources import manual_fixture, warcraftlogs
    except ImportError:
        from community_talent_sources import manual_fixture, warcraftlogs
    try:
        from .websim_payload import load_websim_baseline_talent_templates
    except ImportError:
        from websim_payload import load_websim_baseline_talent_templates

    sources = {}
    try:
        raiderio = store.get_raiderio_payload()
        sources["raiderio"] = {
            "status": (raiderio or {}).get("sourceStatus") or (raiderio or {}).get("status") or "blocked",
            "sourceName": "Raider.IO",
            "templates": (raiderio or {}).get("communityTemplates") or [],
            "errors": (raiderio or {}).get("errors") or [],
        }
    except Exception as error:
        sources["raiderio"] = {"status": "blocked", "sourceName": "Raider.IO", "templates": [], "errors": [str(error)]}

    for source_key, source_name, loader in (
        ("manual_fixture", "Manual Fixture", manual_fixture.load_templates),
        ("warcraftlogs", "Warcraft Logs", warcraftlogs.load_templates),
        ("websim_baseline", "WebSim 基线模板", load_websim_baseline_talent_templates),
    ):
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
        sources[source_key] = {"status": status, "sourceName": source_name, "errors": source_errors}
        errors.extend(f"{source_key}: {error}" for error in source_errors)
        for raw_template in result.get("templates") or []:
            if not isinstance(raw_template, dict):
                continue
            templates.append(
                {
                    **raw_template,
                    "sourceKey": source_key,
                    "sourceName": raw_template.get("sourceName") or source_name,
                    "sourceStatus": raw_template.get("sourceStatus") or status,
                    "scanRunId": raw_template.get("scanRunId") or scan_run_id,
                }
            )
    return templates, sources, errors


def sync_community_template_cache_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    scan_run_id = f"pg-community-template-{checked_at.replace(':', '').replace('+', 'z')}"
    source_results = load_community_talent_sources_postgres(store)
    talent_templates, talent_sources, talent_errors = _community_templates_from_sources(source_results, scan_run_id)
    if talent_templates:
        talent_counts = store.replace_community_talent_templates(talent_templates, scan_run_id=scan_run_id)
    else:
        talent_counts = store.community_talent_template_counts()
    gear_errors = []
    gear_templates = []
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
    verified = talent_counts.get("verified", 0) + gear_counts.get("verified", 0)
    partial = talent_counts.get("partial", 0) + gear_counts.get("partial", 0)
    blocked = talent_counts.get("blocked", 0) + gear_counts.get("blocked", 0)
    source_status = _status_from_counts_and_sources(
        verified,
        partial,
        blocked,
        sources=talent_sources,
        errors=[*talent_errors, *gear_errors],
    )
    payload = {
        "scanRunId": scan_run_id,
        "runner": "postgres",
        "mode": mode,
        "status": "completed" if source_status != "blocked" else "blocked",
        "sourceStatus": source_status,
        "startedAt": checked_at,
        "finishedAt": checked_at,
        "scanCoverage": {},
        "talents": {"templates": talent_counts},
        "gear": {"templates": gear_counts},
        "sourceRefs": [
            {
                "sourceKey": source_key,
                "sourceName": source.get("sourceName") or source_key,
                "sourceStatus": source.get("status") or "blocked",
            }
            for source_key, source in talent_sources.items()
        ],
        "errors": [*talent_errors, *gear_errors][:20],
    }
    talent_state = {
        "runner": "postgres",
        "mode": mode,
        "status": payload["status"],
        "sourceStatus": _status_from_counts_and_sources(
            talent_counts.get("verified", 0),
            talent_counts.get("partial", 0),
            talent_counts.get("blocked", 0),
            sources=talent_sources,
            errors=talent_errors,
        ),
        "templates": talent_counts,
        "scanCoverage": payload["scanCoverage"],
        "sources": talent_sources,
        "checkedAt": checked_at,
        "scanRunId": payload["scanRunId"],
        "errors": talent_errors[:20],
    }
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


def run_gear_observed_backfill_postgres(mode="scheduled", store=None):
    store = store or cache_store_from_env()
    checked_at = utc_now()
    try:
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
