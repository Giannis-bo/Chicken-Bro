#!/usr/bin/env python3
import json
import os
import sqlite3
from pathlib import Path

try:
    from .db import postgres_only_runtime_enabled, require_sqlite_runtime_enabled
    from .postgres_cache_sync import (
        _community_gear_first_sync_budget,
        _community_gear_template_coverage_rows,
        _gear_first_sync_target_specs,
        build_community_gear_template_preflight,
        cache_store_from_env,
        sync_community_template_cache_postgres,
    )
    from .raiderio_payload import sync_raiderio_cache
    from .websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ensure_websim_tables,
        get_active_season_payload,
        get_sync_state,
        set_sync_state,
        sync_community_gear_templates,
        sync_community_talent_templates,
        sync_websim_gear_catalog,
        utc_now,
    )
except ImportError:
    from db import postgres_only_runtime_enabled, require_sqlite_runtime_enabled
    from postgres_cache_sync import (
        _community_gear_first_sync_budget,
        _community_gear_template_coverage_rows,
        _gear_first_sync_target_specs,
        build_community_gear_template_preflight,
        cache_store_from_env,
        sync_community_template_cache_postgres,
    )
    from raiderio_payload import sync_raiderio_cache
    from websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ensure_websim_tables,
        get_active_season_payload,
        get_sync_state,
        set_sync_state,
        sync_community_gear_templates,
        sync_community_talent_templates,
        sync_websim_gear_catalog,
        utc_now,
    )


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
DAILY_INCREMENTAL_MODES = {
    "daily_incremental",
    "daily-incremental",
    "daily_light",
    "daily-light",
    "daily_targeted",
    "daily-targeted",
    "weekly_deep",
    "weekly-deep",
    "season_reset_full",
    "season-reset-full",
}
DAILY_INCREMENTAL_TIERS = {"daily_light", "daily_targeted", "weekly_deep", "season_reset_full"}
AVAILABILITY_RESTORE_MODES = {
    "restore_availability",
    "availability_restore",
    "availability_repair",
    "restore-availability",
    "availability-repair",
}
CHANGE_REPORT_CATEGORIES = (
    "unchanged",
    "metadata_refreshed",
    "promoted",
    "candidate_only",
    "needs_review",
    "rejected_regression",
    "blocked",
    "stale_winner",
)


def connect_db():
    require_sqlite_runtime_enabled("community_template_sync")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def source_status_from_parts(parts):
    statuses = [str(item.get("sourceStatus") or item.get("status") or "") for item in parts if isinstance(item, dict)]
    if any(status == "blocked" for status in statuses):
        return "partial" if any(status in {"synced", "verified", "partial"} for status in statuses) else "blocked"
    if any(status == "missing_credentials" for status in statuses):
        return "partial" if any(status in {"synced", "verified", "partial"} for status in statuses) else "missing_credentials"
    if any(status == "partial" for status in statuses):
        return "partial"
    if statuses and all(status in {"synced", "verified"} for status in statuses):
        return "synced"
    return "blocked"


def daily_incremental_mode_enabled(mode):
    return str(mode or "").strip().lower() in DAILY_INCREMENTAL_MODES


def availability_restore_mode_enabled(mode):
    return str(mode or "").strip().lower() in AVAILABILITY_RESTORE_MODES


def _normalized_daily_tier(mode):
    requested = str(mode or "").strip().lower().replace("-", "_")
    if requested in DAILY_INCREMENTAL_TIERS:
        return requested
    configured = os.environ.get("WOW_COMMUNITY_DAILY_TIER", "").strip().lower().replace("-", "_")
    if configured in DAILY_INCREMENTAL_TIERS:
        return configured
    return "daily_targeted"


def _env_bool(names, default=False):
    for name in names:
        raw = os.environ.get(name)
        if raw in (None, ""):
            continue
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return bool(default)


def _stage_value(payload, stage_name, key, default=0):
    stage_timings = (payload or {}).get("stageTimings") if isinstance(payload, dict) else {}
    stages = stage_timings.get("stages") if isinstance(stage_timings, dict) else []
    for stage in stages or []:
        if isinstance(stage, dict) and stage.get("stage") == stage_name:
            return stage.get(key, default)
    return default


def _new_change_report(scan_run_id, checked_at, tier):
    return {
        "schemaRevision": "community-template-daily-change-report-v1",
        "scanRunId": scan_run_id,
        "tier": tier,
        "checkedAt": checked_at,
        "categories": {
            category: {"count": 0, "items": []}
            for category in CHANGE_REPORT_CATEGORIES
        },
        "summary": {category: 0 for category in CHANGE_REPORT_CATEGORIES},
    }


def _add_change_report_item(report, category, count=1, item=None):
    if category not in CHANGE_REPORT_CATEGORIES:
        category = "needs_review"
    try:
        count = max(0, int(count or 0))
    except (TypeError, ValueError):
        count = 0
    bucket = report["categories"][category]
    bucket["count"] += count
    report["summary"][category] += count
    if isinstance(item, dict):
        bucket["items"].append(item)


def _finalize_change_report(report):
    for category in CHANGE_REPORT_CATEGORIES:
        bucket = report["categories"][category]
        bucket["count"] = report["summary"][category]
    return report


def _daily_talent_mode(tier):
    default = "scheduled" if tier in {"weekly_deep", "season_reset_full"} else "missing_slots"
    return os.environ.get("WOW_COMMUNITY_DAILY_TALENT_MODE", default).strip() or default


def _daily_gear_mode(tier):
    default = "gear_template_first_sync" if tier == "season_reset_full" else "gear_template_targeted_refresh"
    return os.environ.get("WOW_COMMUNITY_DAILY_GEAR_MODE", default).strip() or default


def _daily_gear_skip_when_no_targets(tier):
    return _env_bool(
        ["WOW_COMMUNITY_DAILY_GEAR_SKIP_WHEN_NO_TARGETS"],
        default=tier in {"daily_light", "daily_targeted"},
    )


def _daily_gear_refresh_raiderio(tier):
    return _env_bool(
        ["WOW_COMMUNITY_DAILY_GEAR_REFRESH_RAIDERIO"],
        default=tier in {"daily_targeted", "weekly_deep", "season_reset_full"},
    )


def _gear_preflight_from_store(store, scan_run_id, checked_at):
    return build_community_gear_template_preflight(
        _community_gear_template_coverage_rows(store, []),
        scan_run_id=scan_run_id,
        checked_at=checked_at,
    )


def _gear_templates_counts_from_store(store):
    if hasattr(store, "community_gear_template_counts"):
        try:
            return store.community_gear_template_counts()
        except Exception:
            return {}
    return {}


def _gear_skip_payload(mode, preflight, store, checked_at):
    return {
        "runner": "postgres",
        "mode": mode,
        "status": "completed",
        "sourceStatus": "verified",
        "startedAt": checked_at,
        "finishedAt": checked_at,
        "skipped": True,
        "skipReason": "no_gear_template_targets",
        "gear": {
            "templates": _gear_templates_counts_from_store(store),
            "preflight": preflight,
            "observedBackfill": {
                "status": "skipped",
                "sourceStatus": "verified",
                "skipReason": "no_gear_template_targets",
            },
            "realCommunityTemplates": preflight.get("realCommunityTemplates") or {},
            "baselineTemplates": preflight.get("baseline") or {},
        },
        "errors": [],
    }


def _restore_community_template_availability_for_incremental(store, checked_at):
    if not hasattr(store, "restore_community_template_availability"):
        return {"status": "skipped", "skipReason": "store_missing_availability_restore"}
    result = store.restore_community_template_availability(checked_at=checked_at)
    return result if isinstance(result, dict) else {"status": "completed"}


def _record_talent_changes(report, talent_payload):
    target_count = _stage_value(talent_payload, "source_collection", "targetSlotCount", 0)
    if not target_count:
        coverage = (talent_payload or {}).get("scanCoverage") if isinstance(talent_payload, dict) else {}
        coverage = coverage if isinstance(coverage, dict) else {}
        total_slots = int(coverage.get("totalHeroSlotCount") or coverage.get("targetHeroSlotCount") or 80)
        _add_change_report_item(
            report,
            "unchanged",
            total_slots,
            {
                "domain": "talents",
                "targetType": "hero_slot",
                "reason": "no_missing_talent_slots",
            },
        )
        return
    promoted = ((talent_payload or {}).get("talents") or {}).get("templates") or {}
    _add_change_report_item(
        report,
        "promoted",
        promoted.get("verified") or target_count,
        {
            "domain": "talents",
            "targetType": "hero_slot",
            "targetCount": target_count,
            "scanRunId": (talent_payload or {}).get("scanRunId") or "",
        },
    )


def _record_gear_changes(report, gear_payload, preflight, target_spec_ids):
    community_best = (preflight or {}).get("communityBest") or {}
    baseline = (preflight or {}).get("baseline") or {}
    slot_matrix = (preflight or {}).get("canonicalSlotMatrix") or {}
    if (gear_payload or {}).get("skipped"):
        unchanged_count = int(community_best.get("totalSpecCount") or community_best.get("completeSpecCount") or 40)
        unchanged_count += int(baseline.get("totalSpecCount") or baseline.get("availableSpecCount") or 40)
        _add_change_report_item(
            report,
            "unchanged",
            unchanged_count,
            {
                "domain": "gear",
                "targetType": "community_best_and_baseline",
                "reason": "no_gear_template_targets",
            },
        )
        return

    observed = ((gear_payload or {}).get("gear") or {}).get("observedBackfill") or {}
    variant_count = int(observed.get("variantCount") or 0)
    verified_count = int(observed.get("verifiedCount") or observed.get("simcItemProbeResolvedCount") or 0)
    partial_count = int(observed.get("partialCount") or 0)
    if variant_count:
        _add_change_report_item(
            report,
            "candidate_only",
            variant_count,
            {
                "domain": "gear",
                "targetType": "gear_variant",
                "targetSpecIds": target_spec_ids,
                "scanRunId": (gear_payload or {}).get("scanRunId") or "",
            },
        )
    if verified_count:
        _add_change_report_item(
            report,
            "metadata_refreshed",
            verified_count,
            {
                "domain": "gear",
                "targetType": "gear_variant",
                "reason": "trusted_item_metadata_or_simc_stats_resolved",
            },
        )
    if partial_count:
        _add_change_report_item(
            report,
            "needs_review",
            partial_count,
            {
                "domain": "gear",
                "targetType": "gear_variant",
                "reason": "variant_remains_partial_after_targeted_refresh",
            },
        )
    missing_slots = int(slot_matrix.get("missingSlotCount") or 0)
    incomplete_specs = int(community_best.get("partialSpecCount") or 0) + int(community_best.get("pendingSpecCount") or 0)
    incomplete_specs += int(community_best.get("blockedSpecCount") or 0)
    if missing_slots or incomplete_specs:
        _add_change_report_item(
            report,
            "needs_review",
            max(missing_slots, incomplete_specs),
            {
                "domain": "gear",
                "targetType": "gear_template",
                "targetSpecIds": target_spec_ids,
                "missingSlotCount": missing_slots,
                "incompleteSpecCount": incomplete_specs,
            },
        )
    if (gear_payload or {}).get("errors"):
        _add_change_report_item(
            report,
            "blocked",
            len((gear_payload or {}).get("errors") or []),
            {
                "domain": "gear",
                "targetType": "gear_template",
                "errors": (gear_payload or {}).get("errors") or [],
            },
        )


def sync_community_template_daily_incremental_postgres(mode="daily_incremental"):
    store = cache_store_from_env()
    checked_at = utc_now()
    scan_run_id = f"pg-community-template-daily-incremental-{checked_at.replace(':', '').replace('+', 'z')}"
    tier = _normalized_daily_tier(mode)
    talent_mode = _daily_talent_mode(tier)
    gear_mode = _daily_gear_mode(tier)
    change_report = _new_change_report(scan_run_id, checked_at, tier)
    availability_repair = _restore_community_template_availability_for_incremental(store, checked_at)

    talent_payload = sync_community_template_cache_postgres(mode=talent_mode, store=store, refresh_raiderio=True)
    _record_talent_changes(change_report, talent_payload)

    gear_preflight = _gear_preflight_from_store(store, scan_run_id, checked_at)
    budget = _community_gear_first_sync_budget()
    gear_target_spec_ids = _gear_first_sync_target_specs(
        gear_preflight,
        limit=budget.get("targetSpecLimit") or 0,
    )
    if not gear_target_spec_ids and _daily_gear_skip_when_no_targets(tier):
        gear_payload = _gear_skip_payload(gear_mode, gear_preflight, store, checked_at)
    else:
        gear_payload = sync_community_template_cache_postgres(
            mode=gear_mode,
            store=store,
            refresh_raiderio=_daily_gear_refresh_raiderio(tier),
        )
        gear_payload.setdefault("skipped", False)
        gear_preflight = ((gear_payload.get("gear") or {}).get("preflight") or gear_preflight)
    _record_gear_changes(change_report, gear_payload, gear_preflight, gear_target_spec_ids)
    change_report = _finalize_change_report(change_report)

    source_status = source_status_from_parts([talent_payload, gear_payload])
    finished_at = utc_now()
    gear_summary = dict((gear_payload or {}).get("gear") or {})
    gear_summary["skipped"] = bool((gear_payload or {}).get("skipped"))
    if (gear_payload or {}).get("skipReason"):
        gear_summary["skipReason"] = gear_payload.get("skipReason")
    gear_summary["targetSpecIds"] = gear_target_spec_ids
    payload = {
        "schemaRevision": "community-template-daily-incremental-v1",
        "scanRunId": scan_run_id,
        "runner": "postgres-daily-incremental",
        "mode": mode,
        "tier": tier,
        "status": "blocked" if source_status == "blocked" else "completed",
        "sourceStatus": source_status,
        "startedAt": checked_at,
        "finishedAt": finished_at,
        "availabilityRepair": availability_repair,
        "talents": {
            "mode": talent_mode,
            "scanRunId": talent_payload.get("scanRunId") or "",
            "status": talent_payload.get("status") or "",
            "sourceStatus": talent_payload.get("sourceStatus") or "",
            "templates": ((talent_payload.get("talents") or {}).get("templates") or {}),
            "scanCoverage": talent_payload.get("scanCoverage") or {},
        },
        "gear": gear_summary,
        "runs": {
            "talents": talent_payload,
            "gear": gear_payload,
        },
        "changeReport": change_report,
        "sourceRefs": [
            *list((talent_payload.get("sourceRefs") or [])[:10]),
            *list((gear_payload.get("sourceRefs") or [])[:10]),
        ],
        "errors": [
            *list(talent_payload.get("errors") or []),
            *list(gear_payload.get("errors") or []),
        ][:20],
    }
    if hasattr(store, "save_sync_state"):
        store.save_sync_state(COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload, finished_at)
    return payload


def restore_community_template_availability_postgres(mode="restore_availability"):
    store = cache_store_from_env()
    started_at = utc_now()
    scan_run_id = f"pg-community-template-availability-repair-{started_at.replace(':', '').replace('+', 'z')}"
    result = store.restore_community_template_availability(checked_at=started_at)
    finished_at = utc_now()
    payload = {
        "schemaRevision": "community-template-availability-repair-v1",
        "scanRunId": scan_run_id,
        "runner": "postgres-availability-repair",
        "mode": mode,
        "status": result.get("status") or "completed",
        "sourceStatus": "verified",
        "startedAt": started_at,
        "finishedAt": finished_at,
        "availabilityExpiresAt": result.get("availabilityExpiresAt") or "",
        "talentRestored": int(result.get("talentRestored") or 0),
        "gearRestored": int(result.get("gearRestored") or 0),
        "repair": result,
        "errors": [],
    }
    if hasattr(store, "save_sync_state"):
        store.save_sync_state(COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload, finished_at)
    return payload


def record_sync_run(conn, payload):
    conn.execute(
        """
        INSERT INTO community_template_sync_runs (
            id, mode, status, source_status, started_at, finished_at,
            scan_coverage_json, talent_counts_json, gear_counts_json,
            source_refs_json, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            mode=excluded.mode,
            status=excluded.status,
            source_status=excluded.source_status,
            started_at=excluded.started_at,
            finished_at=excluded.finished_at,
            scan_coverage_json=excluded.scan_coverage_json,
            talent_counts_json=excluded.talent_counts_json,
            gear_counts_json=excluded.gear_counts_json,
            source_refs_json=excluded.source_refs_json,
            payload_json=excluded.payload_json
        """,
        (
            payload["scanRunId"],
            payload["mode"],
            payload["status"],
            payload["sourceStatus"],
            payload["startedAt"],
            payload["finishedAt"],
            json.dumps(payload.get("scanCoverage") or {}, ensure_ascii=False),
            json.dumps((payload.get("talents") or {}).get("templates") or {}, ensure_ascii=False),
            json.dumps((payload.get("gear") or {}).get("templates") or {}, ensure_ascii=False),
            json.dumps(payload.get("sourceRefs") or [], ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    set_sync_state(conn, COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload)


def sync_community_template_cache(conn, mode="scheduled"):
    ensure_websim_tables(conn)
    started_at = utc_now()
    scan_run_id = f"community-template-{started_at.replace(':', '').replace('+', 'z')}"
    errors = []

    try:
        raiderio = sync_raiderio_cache(conn)
    except Exception as error:
        raiderio = {"sourceStatus": "blocked", "errors": [str(error)]}
        errors.append(f"Raider.IO cache failed: {error}")

    try:
        talents = sync_community_talent_templates(conn)
    except Exception as error:
        talents = {
            "sourceStatus": "blocked",
            "sources": {},
            "templates": {"total": 0, "verified": 0, "blocked": 0},
            "errors": [str(error)],
        }
        set_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY, talents)
        errors.append(f"community talent templates failed: {error}")

    try:
        gear_catalog = sync_websim_gear_catalog(conn, get_active_season_payload(conn))
    except Exception as error:
        gear_catalog = {"status": "blocked", "errors": [str(error)]}
        errors.append(f"gear catalog observed variants failed: {error}")

    try:
        gear = sync_community_gear_templates(conn, scan_run_id=scan_run_id)
    except Exception as error:
        gear = {
            "sourceStatus": "blocked",
            "templates": {"total": 0, "verified": 0, "partial": 0, "blocked": 0},
            "errors": [str(error)],
        }
        errors.append(f"community gear templates failed: {error}")

    source_status = source_status_from_parts([
        raiderio,
        talents,
        gear_catalog,
        gear,
    ])
    scan_coverage = talents.get("scanCoverage") or {}
    raiderio_coverage = raiderio.get("specCoverage") if isinstance(raiderio.get("specCoverage"), dict) else {}
    if raiderio_coverage:
        scan_coverage = {**scan_coverage, "raiderio": raiderio_coverage}
    payload = {
        "scanRunId": scan_run_id,
        "mode": mode,
        "status": "blocked" if source_status == "blocked" else "completed",
        "sourceStatus": source_status,
        "startedAt": started_at,
        "finishedAt": utc_now(),
        "scanCoverage": scan_coverage,
        "raiderio": {
            "sourceStatus": raiderio.get("sourceStatus") or raiderio.get("status") or "",
            "runCount": raiderio.get("runCount") or 0,
            "profileCount": raiderio.get("profileCount") or 0,
            "specCoverage": raiderio_coverage,
            "checkedAt": raiderio.get("checkedAt") or "",
        },
        "talents": talents,
        "gearCatalog": gear_catalog,
        "gear": gear,
        "sourceRefs": [
            {"sourceKey": "raiderio", "sourceName": "Raider.IO", "sourceStatus": raiderio.get("sourceStatus") or ""},
            {"sourceKey": "warcraftlogs", "sourceName": "Warcraft Logs", "sourceStatus": ((talents.get("sources") or {}).get("warcraftlogs") or {}).get("status") or ""},
            {"sourceKey": "simc", "sourceName": "SimulationCraft", "sourceStatus": "source_reference"},
        ],
        "errors": errors,
    }
    record_sync_run(conn, payload)
    return payload


def main():
    mode = os.environ.get("WOW_COMMUNITY_TEMPLATE_SYNC_MODE", "scheduled").strip() or "scheduled"
    if postgres_only_runtime_enabled():
        if availability_restore_mode_enabled(mode):
            payload = restore_community_template_availability_postgres(mode=mode)
        elif daily_incremental_mode_enabled(mode):
            payload = sync_community_template_daily_incremental_postgres(mode=mode)
        else:
            payload = sync_community_template_cache_postgres(mode=mode)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    with connect_db() as conn:
        payload = sync_community_template_cache(conn, mode=mode)
        conn.commit()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
