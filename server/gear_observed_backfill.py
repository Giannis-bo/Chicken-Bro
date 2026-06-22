#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
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


def matched_target_item_ids(profiles, target_item_ids):
    targets = set(websim_payload.gear_observed_backfill_target_ids(target_item_ids))
    matched = []
    for profile in profiles or []:
        for item in profile.get("gear") or []:
            item_id = profile_item_id(item)
            if item_id in targets and item_id not in matched:
                matched.append(item_id)
    return matched


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

    with sqlite3.connect(db_path) as conn:
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
                    "officialVariantsPromoted": 0,
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
            filtered_profiles = filter_profiles_to_target_items(fetched_profiles, window["targetItemIds"])
            matched_ids = matched_target_item_ids(filtered_profiles, window["targetItemIds"])
            emit_stage(
                stage_callback,
                provider.name,
                "complete",
                fetch_started,
                fetchedProfileCount=len(fetched_profiles),
                matchedTargetItemCount=len(matched_ids),
                errors=len(fetch_errors),
            )

            season = websim_payload.get_active_season_payload(conn)
            observed_counts = websim_payload.sync_observed_gear_variants(
                conn,
                observed_payload(provider, filtered_profiles, utc_now_iso(), fetch_errors),
                season,
                replace=False,
            )
            promotion_counts = websim_payload.promote_official_gear_variants_from_observed(conn)
            gear_state = websim_payload.build_gear_catalog_sync_state(conn, season)
            gear_state["observedBackfill"] = {
                "provider": provider.name,
                "lastRunStatus": "partial" if fetch_errors else "ok",
                "processedTargetItemIds": window["targetItemIds"],
                "processedProfileCount": len(window["profiles"]),
                "matchedTargetItemIds": matched_ids,
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
                    "matchedTargetItemIds": merged_matched,
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
                "officialVariantsPromoted": promotion_counts.get("promotedVariants") or 0,
                "cursor": state.get("cursor") or {},
                "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
                "errors": fetch_errors[:12],
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
                "officialVariantsPromoted": 0,
                "cursor": state.get("cursor") or {},
                "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
                "errors": [str(error)],
            }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run bounded observed gear variant backfill.")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--target-limit", type=int, default=DEFAULT_TARGET_LIMIT)
    parser.add_argument("--profile-limit", type=int, default=DEFAULT_PROFILE_LIMIT)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="Emit compact JSON summary.")
    args = parser.parse_args(argv)
    summary = run_gear_observed_backfill(
        args.db,
        target_limit=args.target_limit,
        profile_limit=args.profile_limit,
        timeout_seconds=args.timeout_seconds,
        stage_callback=print_stage,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if summary.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
