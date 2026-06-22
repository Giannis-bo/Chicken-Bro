#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

try:
    from . import raiderio_payload
    from . import websim_payload
except ImportError:
    import raiderio_payload
    import websim_payload


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
DEFAULT_TARGET_LIMIT = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_TARGET_LIMIT", "80"))
DEFAULT_PROFILE_LIMIT = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_PROFILE_LIMIT", "40"))
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_TIMEOUT_SECONDS", "600"))
DEFAULT_SIMC_BIN = os.environ.get("WOW_SIMC_BIN", "/opt/wow-simc/current/simc")
DEFAULT_SIMC_STATS = os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_SIMC_STATS", "0").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_SIMC_TIMEOUT_SECONDS = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_SIMC_TIMEOUT_SECONDS", "90"))


def utc_now_iso():
    return websim_payload.utc_now()


def emit_stage(stage_callback, stage, status, started_at=None, **details):
    event = {
        "event": "gear_observed_backfill_stage",
        "stage": stage,
        "status": status,
    }
    if started_at is not None:
        event["durationSeconds"] = round(max(0.0, time.monotonic() - started_at), 3)
    event.update({key: value for key, value in details.items() if value is not None})
    if stage_callback:
        stage_callback(event)
    return time.monotonic()


def print_stage(event):
    print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True)


def profile_item_id(item):
    return str((item or {}).get("itemId") or (item or {}).get("item_id") or (item or {}).get("id") or "").strip()


def filter_profiles_to_target_items(profiles, target_item_ids):
    targets = set(websim_payload.gear_observed_backfill_target_ids(target_item_ids))
    if not targets:
        return []
    filtered = []
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        gear = [item for item in profile.get("gear") or [] if profile_item_id(item) in targets]
        if not gear:
            continue
        filtered.append({**profile, "gear": gear})
    return filtered


def current_season_source_item_ids(conn, season):
    season_revision = str((season or {}).get("seasonRevision") or (season or {}).get("revision") or "").strip()
    season_verified = str((season or {}).get("dataStatus") or "").strip() == "verified"
    rows = conn.execute(
        """
        SELECT item_id, source_type, source_label, difficulty_key, season_revision, payload_json
        FROM websim_gear_sources
        WHERE source_type IN ('dungeon', 'raid', 'tier_set')
        ORDER BY item_id
        """
    ).fetchall()
    result = []
    for item_id, source_type, source_label, difficulty_key, row_season_revision, payload_json in rows:
        item_id = str(item_id or "").strip()
        if not item_id or item_id in result:
            continue
        row_season_revision = str(row_season_revision or "").strip()
        if season_verified and season_revision and row_season_revision and row_season_revision != season_revision:
            continue
        payload = websim_payload.safe_json_loads(payload_json, {})
        source = {
            "itemId": item_id,
            "sourceType": source_type,
            "sourceLabel": source_label,
            "difficultyKey": difficulty_key,
            "seasonRevision": row_season_revision,
        }
        if isinstance(payload, dict):
            source.update(payload)
        if season_verified and source_type in {"dungeon", "raid"} and season and not websim_payload.gear_source_active_for_replacement(source, season):
            continue
        result.append(item_id)
    return result


def filter_profiles_to_item_ids(profiles, item_ids):
    allowed = set(websim_payload.gear_observed_backfill_target_ids(item_ids))
    if not allowed:
        return []
    filtered = []
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        gear = [item for item in profile.get("gear") or [] if profile_item_id(item) in allowed]
        if not gear:
            continue
        filtered.append({**profile, "gear": gear})
    return filtered


def filter_profiles_to_simc_stat_gear(profiles):
    filtered = []
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        simc_gear = websim_payload.simc_json_gear_stats_by_slot(profile)
        if not simc_gear:
            continue
        gear = [
            item
            for item in profile.get("gear") or []
            if websim_payload.simc_observed_variant_stat_payload(item, simc_gear)
        ]
        if not gear:
            continue
        filtered.append({**profile, "gear": gear})
    return filtered


def prune_observed_profile_gear_to_item_ids(conn, item_ids, *, require_simc_stats=False):
    allowed = websim_payload.gear_observed_backfill_target_ids(item_ids)
    if not allowed:
        return {
            "observedVariantRowsPruned": 0,
            "observedVariantRowsPrunedMissingStats": 0,
            "observedSourceRowsPruned": 0,
        }
    placeholders = ",".join("?" for _ in allowed)
    missing_stat_variant_rows = 0
    if require_simc_stats:
        missing_stat_variant_rows = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM websim_gear_variants
            WHERE source_type = 'observed_profile'
              AND item_id IN ({placeholders})
              AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
            """,
            allowed,
        ).fetchone()[0]
    variant_cursor = conn.execute(
        f"""
        DELETE FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND (
            item_id NOT IN ({placeholders})
            OR (
              ? = 1
              AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
            )
          )
        """,
        [*allowed, int(bool(require_simc_stats))],
    )
    source_cursor = conn.execute(
        f"""
        DELETE FROM websim_gear_sources
        WHERE source_type = 'observed_profile'
          AND (
            item_id NOT IN ({placeholders})
            OR item_id NOT IN (
              SELECT DISTINCT item_id
              FROM websim_gear_variants
              WHERE source_type = 'observed_profile'
            )
          )
        """,
        allowed,
    )
    return {
        "observedVariantRowsPruned": max(0, int(variant_cursor.rowcount or 0)),
        "observedVariantRowsPrunedMissingStats": max(0, int(missing_stat_variant_rows or 0)),
        "observedSourceRowsPruned": max(0, int(source_cursor.rowcount or 0)),
    }


def matched_target_item_ids(profiles, target_item_ids):
    targets = set(websim_payload.gear_observed_backfill_target_ids(target_item_ids))
    matched = []
    for profile in profiles or []:
        for item in profile.get("gear") or []:
            item_id = profile_item_id(item)
            if item_id in targets and item_id not in matched:
                matched.append(item_id)
    return matched


def observed_profile_simc_lines(profile):
    class_key = websim_payload.slugify(profile.get("classKey") or profile.get("classSlug") or profile.get("className"), "")
    spec_key = websim_payload.slugify(profile.get("specKey") or profile.get("specSlug") or profile.get("specName"), "")
    gear_items = []
    for raw_item in profile.get("gear") or []:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        if str(item.get("name") or "").strip().lower() == "unknown":
            continue
        item["sourceType"] = "manual"
        item["ilevel"] = item.get("ilevel") or item.get("itemLevel") or item.get("item_level")
        item.update(websim_payload.observed_gear_simc_options(item))
        gear_items.append(item)
    normalized = websim_payload.normalize_websim_gear_items(gear_items, class_key, spec_key, "manual")
    return websim_payload.build_websim_gear_lines(normalized)


def observed_profile_simc_text(profile):
    class_key = websim_payload.slugify(profile.get("classKey") or profile.get("classSlug") or profile.get("className"), "mage")
    spec_key = websim_payload.slugify(profile.get("specKey") or profile.get("specSlug") or profile.get("specName"), "")
    character_name = str(profile.get("characterName") or profile.get("name") or "observed_profile").strip() or "observed_profile"
    race = websim_payload.DEFAULT_RACE_BY_CLASS.get(class_key, "troll")
    lines = observed_profile_simc_lines(profile)
    if not lines:
        return "", ["observed profile has no SimC-ready gear lines"]
    profile_lines = [
        f'{class_key}="{character_name}"',
        "level=90",
        f"race={race}",
        f"spec={spec_key}" if spec_key else "",
        "iterations=1",
        "default_actions=1",
        *lines,
    ]
    return "\n".join(line for line in profile_lines if line) + "\n", []


class SimulationCraftGearStatsRunner:
    def __init__(self, simc_bin=DEFAULT_SIMC_BIN):
        self.simc_bin = str(simc_bin or DEFAULT_SIMC_BIN)

    def run(self, profile, timeout_seconds=DEFAULT_SIMC_TIMEOUT_SECONDS):
        profile_text, errors = observed_profile_simc_text(profile)
        if errors:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": errors}
        try:
            proc = subprocess.run(
                [self.simc_bin, "/dev/stdin", "output=/dev/null", "json2=/dev/stdout", "html=/dev/null"],
                input=profile_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(1, int(timeout_seconds or DEFAULT_SIMC_TIMEOUT_SECONDS)),
            )
        except Exception as error:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [str(error)]}
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-600:]
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [detail or f"SimulationCraft exited {proc.returncode}"]}
        start = (proc.stdout or "").find("{")
        if start < 0:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": ["SimulationCraft did not emit JSON gear output"]}
        try:
            payload, _ = json.JSONDecoder().raw_decode(proc.stdout[start:])
        except Exception as error:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [f"SimulationCraft JSON parse failed: {error}"]}
        resolved = websim_payload.simc_json_gear_stats_by_slot(payload)
        if not resolved:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": ["SimulationCraft JSON did not contain resolved gear stats"]}
        return {"ok": True, "simcJson": payload, "resolvedSlotCount": len(resolved), "errors": []}


def enrich_profiles_with_simc_json_stats(profiles, simc_runner, timeout_seconds=DEFAULT_SIMC_TIMEOUT_SECONDS):
    enriched = []
    stats = {
        "simcProfileCount": 0,
        "simcResolvedProfileCount": 0,
        "simcResolvedSlotCount": 0,
        "simcErrors": [],
    }
    if not simc_runner:
        return list(profiles or []), stats
    for profile in profiles or []:
        if not isinstance(profile, dict):
            continue
        stats["simcProfileCount"] += 1
        result = simc_runner.run(profile, timeout_seconds=timeout_seconds)
        next_profile = dict(profile)
        if result.get("ok") and isinstance(result.get("simcJson"), dict):
            next_profile["simcJson"] = result.get("simcJson")
            stats["simcResolvedProfileCount"] += 1
            stats["simcResolvedSlotCount"] += int(result.get("resolvedSlotCount") or 0)
        else:
            stats["simcErrors"].extend(str(error) for error in result.get("errors") or [] if str(error).strip())
        enriched.append(next_profile)
    stats["simcErrors"] = stats["simcErrors"][:12]
    return enriched, stats


class RaiderIOObservedBackfillProvider:
    name = "raiderio"

    def target_item_ids(self, conn):
        return raiderio_payload.raiderio_target_item_ids(conn)

    def candidate_profiles(self, conn):
        cached = raiderio_payload.read_cache(conn)
        return raiderio_payload.unique_profile_candidates_for_runs(cached.get("runs") or [])

    def fetch_profiles(self, candidates, target_item_ids, deadline_at=0):
        fields = "gear,talents,mythic_plus_recent_runs,mythic_plus_best_runs,mythic_plus_scores_by_season"
        return raiderio_payload.fetch_profile_batch(candidates, fields)


def observed_payload(provider, profiles, checked_at, errors=None):
    errors = errors or []
    return {
        "sourceName": "Raider.IO observed gear backfill" if provider.name == "raiderio" else f"{provider.name} observed gear backfill",
        "sourceStatus": "synced" if profiles else "partial",
        "status": "synced" if profiles else "partial",
        "checkedAt": checked_at,
        "profiles": profiles,
        "profileCount": len(profiles),
        "errors": errors[:12],
    }


def run_gear_observed_backfill(
    db_path=DB_PATH,
    *,
    provider=None,
    simc_runner=None,
    enable_simc_stats=DEFAULT_SIMC_STATS,
    simc_timeout_seconds=DEFAULT_SIMC_TIMEOUT_SECONDS,
    sync_full_profile_gear=False,
    target_limit=DEFAULT_TARGET_LIMIT,
    profile_limit=DEFAULT_PROFILE_LIMIT,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    stage_callback=None,
):
    provider = provider or RaiderIOObservedBackfillProvider()
    db_path = Path(db_path)
    started_monotonic = time.monotonic()
    started_at = utc_now_iso()
    deadline_at = started_monotonic + max(1, int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS))
    emit_stage(stage_callback, "gear_observed_backfill", "start", provider=provider.name)

    conn = sqlite3.connect(db_path)
    try:
        websim_payload.ensure_websim_tables(conn)
        target_item_ids = websim_payload.gear_observed_backfill_target_ids(provider.target_item_ids(conn))
        state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=target_item_ids, provider=provider.name)
        original_cursor = dict(state.get("cursor") or {})
        try:
            if not target_item_ids:
                finished_at = utc_now_iso()
                window = websim_payload.build_gear_observed_backfill_window(
                    target_item_ids,
                    [],
                    state,
                    target_limit=target_limit,
                    profile_limit=profile_limit,
                )
                state.update(
                    {
                        "lastRunStatus": "ok",
                        "lastRunStartedAt": started_at,
                        "lastRunFinishedAt": finished_at,
                        "processedTargetItemCount": 0,
                        "processedProfileCount": 0,
                        "matchedTargetItemIds": [],
                        "lastError": None,
                        "cursor": window["cursor"],
                    }
                )
                state.setdefault("providers", {})[provider.name] = {"status": "ok"}
                state["providers"].setdefault("wcl", {"status": "not_implemented"})
                websim_payload.write_gear_observed_backfill_state(conn, state)
                conn.commit()
                emit_stage(
                    stage_callback,
                    "gear_observed_backfill",
                    "complete",
                    started_monotonic,
                    runStatus="ok",
                    matchedTargetItemCount=0,
                )
                return {
                    "status": "ok",
                    "provider": provider.name,
                    "targetItemCount": 0,
                    "processedTargetItemIds": [],
                    "processedProfileCount": 0,
                    "matchedTargetItemIds": [],
                    "observedVariantRowsUpserted": 0,
                    "observedVariantRowsPruned": 0,
                    "observedVariantRowsPrunedMissingStats": 0,
                    "observedSourceRowsPruned": 0,
                    "officialVariantsPromoted": 0,
                    "officialObservedVariantsRefreshed": 0,
                    "cursor": state.get("cursor") or {},
                    "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
                    "errors": [],
                }

            candidates = list(provider.candidate_profiles(conn))
            window = websim_payload.build_gear_observed_backfill_window(
                target_item_ids,
                candidates,
                state,
                target_limit=target_limit,
                profile_limit=profile_limit,
            )
            state["lastRunStatus"] = "running"
            state["lastRunStartedAt"] = started_at
            state["lastError"] = None
            websim_payload.write_gear_observed_backfill_state(conn, state)
            conn.commit()

            fetch_started = emit_stage(
                stage_callback,
                provider.name,
                "start",
                targetItemCount=len(window["targetItemIds"]),
                profileCount=len(window["profiles"]),
            )
            fetched_profiles, fetch_errors = provider.fetch_profiles(
                window["profiles"],
                window["targetItemIds"],
                deadline_at=deadline_at,
            )
            simc_stats = {
                "simcProfileCount": 0,
                "simcResolvedProfileCount": 0,
                "simcResolvedSlotCount": 0,
                "simcErrors": [],
            }
            if enable_simc_stats:
                fetched_profiles, simc_stats = enrich_profiles_with_simc_json_stats(
                    fetched_profiles,
                    simc_runner or SimulationCraftGearStatsRunner(),
                    timeout_seconds=simc_timeout_seconds,
                )
            filtered_profiles = filter_profiles_to_target_items(fetched_profiles, window["targetItemIds"])
            observed_profiles = fetched_profiles if sync_full_profile_gear else filtered_profiles
            matched_ids = matched_target_item_ids(filtered_profiles, window["targetItemIds"])
            emit_stage(
                stage_callback,
                provider.name,
                "complete",
                fetch_started,
                fetchedProfileCount=len(fetched_profiles),
                matchedTargetItemCount=len(matched_ids),
                errors=len(fetch_errors),
                simcResolvedProfileCount=simc_stats["simcResolvedProfileCount"],
                simcResolvedSlotCount=simc_stats["simcResolvedSlotCount"],
            )

            season = websim_payload.get_active_season_payload(conn)
            prune_counts = {
                "observedVariantRowsPruned": 0,
                "observedVariantRowsPrunedMissingStats": 0,
                "observedSourceRowsPruned": 0,
            }
            if sync_full_profile_gear:
                current_season_item_ids = current_season_source_item_ids(conn, season)
                observed_profiles = filter_profiles_to_item_ids(
                    fetched_profiles,
                    current_season_item_ids,
                )
                if enable_simc_stats:
                    observed_profiles = filter_profiles_to_simc_stat_gear(observed_profiles)
                prune_counts = prune_observed_profile_gear_to_item_ids(
                    conn,
                    current_season_item_ids,
                    require_simc_stats=enable_simc_stats,
                )
            observed_counts = websim_payload.sync_observed_gear_variants(
                conn,
                observed_payload(provider, observed_profiles, utc_now_iso(), [*fetch_errors, *simc_stats["simcErrors"]]),
                season,
                replace=False,
            )
            promotion_counts = websim_payload.promote_official_gear_variants_from_observed(conn)
            refresh_counts = websim_payload.refresh_official_observed_variant_payloads_from_observed(conn)
            gear_state = websim_payload.build_gear_catalog_sync_state(conn, season)
            gear_state["observedBackfill"] = {
                "provider": provider.name,
                "lastRunStatus": "partial" if fetch_errors else "ok",
                "processedTargetItemIds": window["targetItemIds"],
                "processedProfileCount": len(window["profiles"]),
                "matchedTargetItemIds": matched_ids,
                "refreshedOfficialObservedVariants": refresh_counts.get("refreshedOfficialObservedVariants") or 0,
                **prune_counts,
            }
            websim_payload.set_sync_state(conn, "gearCatalog", gear_state)

            finished_at = utc_now_iso()
            status = "partial" if fetch_errors else "ok"
            prior_matched = websim_payload.gear_observed_backfill_target_ids(state.get("matchedTargetItemIds"))
            merged_matched = websim_payload.gear_observed_backfill_target_ids([*prior_matched, *matched_ids])
            state.update(
                {
                    "lastRunStatus": status,
                    "lastRunFinishedAt": finished_at,
                    "processedTargetItemCount": len(window["targetItemIds"]),
                    "processedProfileCount": len(window["profiles"]),
                    "simcProfileCount": simc_stats["simcProfileCount"],
                    "simcResolvedProfileCount": simc_stats["simcResolvedProfileCount"],
                    "simcResolvedSlotCount": simc_stats["simcResolvedSlotCount"],
                    "matchedTargetItemIds": merged_matched,
                    **prune_counts,
                    "lastError": "; ".join(fetch_errors[:3]) if fetch_errors else None,
                    "cursor": window["cursor"],
                }
            )
            state["providers"][provider.name] = {"status": status}
            state["providers"].setdefault("wcl", {"status": "not_implemented"})
            if window["wrapped"]:
                state["wrappedAt"] = finished_at
            websim_payload.write_gear_observed_backfill_state(conn, state)
            conn.commit()

            summary = {
                "status": status,
                "provider": provider.name,
                "targetItemCount": len(target_item_ids),
                "processedTargetItemIds": window["targetItemIds"],
                "processedProfileCount": len(window["profiles"]),
                "matchedTargetItemIds": matched_ids,
                "observedVariantRowsUpserted": observed_counts.get("observedVariants") or 0,
                **prune_counts,
                "officialVariantsPromoted": promotion_counts.get("promotedVariants") or 0,
                "officialObservedVariantsRefreshed": refresh_counts.get("refreshedOfficialObservedVariants") or 0,
                **simc_stats,
                "cursor": state.get("cursor") or {},
                "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
                "errors": [*fetch_errors, *simc_stats["simcErrors"]][:12],
            }
            emit_stage(
                stage_callback,
                "gear_observed_backfill",
                "complete",
                started_monotonic,
                runStatus=status,
                matchedTargetItemCount=len(matched_ids),
            )
            return summary
        except Exception as error:
            finished_at = utc_now_iso()
            state.update(
                {
                    "lastRunStatus": "error",
                    "lastRunFinishedAt": finished_at,
                    "lastError": str(error),
                    "cursor": original_cursor or state.get("cursor") or {},
                }
            )
            state["providers"][provider.name] = {"status": "error"}
            state["providers"].setdefault("wcl", {"status": "not_implemented"})
            websim_payload.write_gear_observed_backfill_state(conn, state)
            conn.commit()
            emit_stage(stage_callback, "gear_observed_backfill", "error", started_monotonic, error=str(error))
            return {
                "status": "error",
                "provider": provider.name,
                "targetItemCount": len(target_item_ids),
                "processedTargetItemIds": [],
                "processedProfileCount": 0,
                "matchedTargetItemIds": [],
                "observedVariantRowsUpserted": 0,
                "observedVariantRowsPruned": 0,
                "observedVariantRowsPrunedMissingStats": 0,
                "observedSourceRowsPruned": 0,
                "officialVariantsPromoted": 0,
                "officialObservedVariantsRefreshed": 0,
                "cursor": state.get("cursor") or {},
                "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
                "errors": [str(error)],
            }
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run bounded observed gear variant backfill.")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--target-limit", type=int, default=DEFAULT_TARGET_LIMIT)
    parser.add_argument("--profile-limit", type=int, default=DEFAULT_PROFILE_LIMIT)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--simc-stats", action="store_true", default=DEFAULT_SIMC_STATS)
    parser.add_argument("--full-profile-gear", action="store_true", help="Upsert every fetched profile gear item instead of only matched target items.")
    parser.add_argument("--simc-timeout-seconds", type=int, default=DEFAULT_SIMC_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="Emit compact JSON summary.")
    args = parser.parse_args(argv)
    summary = run_gear_observed_backfill(
        args.db,
        target_limit=args.target_limit,
        profile_limit=args.profile_limit,
        timeout_seconds=args.timeout_seconds,
        enable_simc_stats=args.simc_stats,
        sync_full_profile_gear=args.full_profile_gear,
        simc_timeout_seconds=args.simc_timeout_seconds,
        stage_callback=print_stage,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if summary.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
