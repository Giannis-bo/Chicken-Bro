#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from .db import (
        connect_postgres,
        database_config_from_env,
        postgres_only_runtime_enabled,
        require_sqlite_runtime_enabled,
        sqlite_migration_source_enabled,
    )
    from .postgres_cache_sync import run_gear_observed_backfill_postgres
    from . import raiderio_payload
    from . import websim_payload
except ImportError:
    from db import (
        connect_postgres,
        database_config_from_env,
        postgres_only_runtime_enabled,
        require_sqlite_runtime_enabled,
        sqlite_migration_source_enabled,
    )
    from postgres_cache_sync import run_gear_observed_backfill_postgres
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
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_SQLITE_BUSY_TIMEOUT_MS", "30000"))
DEFAULT_SQLITE_LOCK_RETRY_ATTEMPTS = int(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_SQLITE_LOCK_RETRY_ATTEMPTS", "3"))
DEFAULT_SQLITE_LOCK_RETRY_DELAY_SECONDS = float(os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_SQLITE_LOCK_RETRY_DELAY_SECONDS", "1"))
DEFAULT_RETRY_FAILED_SIMC_STATS = os.environ.get("WOW_GEAR_OBSERVED_BACKFILL_RETRY_FAILED_SIMC_STATS", "0").strip().lower() in {"1", "true", "yes", "on"}
SIMC_FALLBACK_MAIN_HAND_LINE = "main_hand=worn_shortsword,id=25"
SIMC_FALLBACK_DEMONHUNTER_OFF_HAND_LINE = "off_hand=worn_shortsword,id=25"
SIMC_DEMONHUNTER_DUAL_WIELD_SPECS = {"havoc", "vengeance"}


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


def connect_backfill_db(db_path=DB_PATH):
    if postgres_only_runtime_enabled() and not sqlite_migration_source_enabled():
        config = database_config_from_env()
        return connect_postgres(config.database_url)
    require_sqlite_runtime_enabled("gear_observed_backfill")
    timeout_ms = max(1000, int(DEFAULT_SQLITE_BUSY_TIMEOUT_MS or 30000))
    conn = sqlite3.connect(db_path, timeout=max(1, timeout_ms // 1000))
    conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    return conn


def connect_readonly_backfill_db(db_path=DB_PATH):
    if postgres_only_runtime_enabled() and not sqlite_migration_source_enabled():
        config = database_config_from_env()
        return connect_postgres(config.database_url)
    require_sqlite_runtime_enabled("gear_observed_backfill read-only source")
    timeout_ms = max(1000, int(DEFAULT_SQLITE_BUSY_TIMEOUT_MS or 30000))
    db_uri = Path(db_path).resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(db_uri, timeout=max(1, timeout_ms // 1000), uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def is_sqlite_lock_error(error):
    return isinstance(error, sqlite3.OperationalError) and "database is locked" in str(error).lower()


def run_sqlite_lock_retry(
    operation,
    *,
    attempts=DEFAULT_SQLITE_LOCK_RETRY_ATTEMPTS,
    delay_seconds=DEFAULT_SQLITE_LOCK_RETRY_DELAY_SECONDS,
):
    attempts = max(1, int(attempts or 1))
    for attempt in range(attempts):
        try:
            return operation()
        except sqlite3.OperationalError as error:
            if not is_sqlite_lock_error(error) or attempt >= attempts - 1:
                raise
            time.sleep(max(0.0, float(delay_seconds or 0.0)))
    return operation()


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
    return observed_profile_simc_gear_lines(normalized)


def observed_profile_simc_gear_lines(items):
    lines = []
    for item in items or []:
        if not isinstance(item, dict) or not item.get("simcReady"):
            continue
        parts = [f'{item["slot"]}=', f'id={item["id"]}']
        for key in ["ilevel", "bonus_id", "gem_id", "gem_bonus_id", "gem_ilevel", "enchant_id", "crafted_stats"]:
            if item.get(key):
                parts.append(f"{key}={item[key]}")
        lines.append(",".join(parts))
    return lines


def simc_lines_include_slot(lines, slot):
    expected = f"{slot}="
    return any(str(line or "").strip().startswith(expected) for line in lines or [])


def observed_profile_simc_init_fallback_lines(class_key, spec_key, lines):
    if not lines:
        return []
    fallback_lines = []
    if not simc_lines_include_slot(lines, "main_hand"):
        fallback_lines.append(SIMC_FALLBACK_MAIN_HAND_LINE)
    if (
        class_key == "demonhunter"
        and spec_key in SIMC_DEMONHUNTER_DUAL_WIELD_SPECS
        and not simc_lines_include_slot(lines, "off_hand")
    ):
        fallback_lines.append(SIMC_FALLBACK_DEMONHUNTER_OFF_HAND_LINE)
    return fallback_lines


def observed_profile_simc_text(profile):
    class_key = websim_payload.slugify(profile.get("classKey") or profile.get("classSlug") or profile.get("className"), "mage")
    spec_key = websim_payload.slugify(profile.get("specKey") or profile.get("specSlug") or profile.get("specName"), "")
    character_name = str(profile.get("characterName") or profile.get("name") or "observed_profile").strip() or "observed_profile"
    race = websim_payload.DEFAULT_RACE_BY_CLASS.get(class_key, "troll")
    lines = observed_profile_simc_lines(profile)
    if not lines:
        return "", ["observed profile has no SimC-ready gear lines"]
    lines = [*observed_profile_simc_init_fallback_lines(class_key, spec_key, lines), *lines]
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

    def _blizzard_api_credentials(self):
        client_id = str(os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID") or "").strip()
        client_secret = str(
            os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET") or ""
        ).strip()
        if not client_id or not client_secret:
            return None
        return client_id, client_secret

    def run(self, profile, timeout_seconds=DEFAULT_SIMC_TIMEOUT_SECONDS):
        profile_text, errors = observed_profile_simc_text(profile)
        if errors:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": errors}
        try:
            args = [self.simc_bin, "/dev/stdin", "output=/dev/null", "json2=/dev/stdout", "html=/dev/null"]
            run_kwargs = {
                "input": profile_text,
                "text": True,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "timeout": max(1, int(timeout_seconds or DEFAULT_SIMC_TIMEOUT_SECONDS)),
            }
            credentials = self._blizzard_api_credentials()
            if credentials:
                with tempfile.TemporaryDirectory() as simc_home:
                    key_path = Path(simc_home) / ".simc_apikey"
                    key_path.write_text(f"{credentials[0]}:{credentials[1]}\n", encoding="utf-8")
                    key_path.chmod(0o600)
                    proc = subprocess.run(args, env={**os.environ, "HOME": simc_home}, **run_kwargs)
            else:
                proc = subprocess.run(args, **run_kwargs)
        except Exception as error:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [str(error)]}
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [detail or f"SimulationCraft exited {proc.returncode}"]}
        start = (proc.stdout or "").find("{")
        if start < 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return {
                "ok": False,
                "simcJson": None,
                "resolvedSlotCount": 0,
                "errors": [detail or "SimulationCraft did not emit JSON gear output"],
            }
        try:
            payload, _ = json.JSONDecoder().raw_decode(proc.stdout[start:])
        except Exception as error:
            return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": [f"SimulationCraft JSON parse failed: {error}"]}
        resolved = websim_payload.simc_json_gear_stats_by_slot(payload)
        if not resolved:
            detail = (proc.stderr or "").strip()
            return {
                "ok": False,
                "simcJson": None,
                "resolvedSlotCount": 0,
                "errors": [detail or "SimulationCraft JSON did not contain resolved gear stats"],
            }
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


def observed_variant_profile_refs(payload, class_key="", spec_key="", slot="", item_id="", item_level=0):
    payload = payload if isinstance(payload, dict) else {}
    refs = [ref for ref in payload.get("observedProfileRefs") or [] if isinstance(ref, dict)]
    if refs:
        return refs
    class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
    spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
    return [
        {
            "sourceName": "local observed variant",
            "classKey": class_keys[0] if class_keys else class_key,
            "specKey": spec_keys[0] if spec_keys else spec_key,
            "slot": slot,
            "itemId": item_id,
            "itemLevel": item_level,
            "characterName": payload.get("characterName") or "",
            "realmSlug": payload.get("realmSlug") or "",
            "profileUrl": payload.get("profileUrl") or "",
        }
    ]


def observed_profile_group_key(ref, fallback_class="", fallback_spec=""):
    class_key = websim_payload.slugify(ref.get("classKey") or fallback_class, "")
    spec_key = websim_payload.slugify(ref.get("specKey") or fallback_spec, "")
    profile_url = str(ref.get("profileUrl") or "").strip()
    if profile_url:
        return ("url", profile_url, class_key, spec_key)
    return (
        "identity",
        class_key,
        spec_key,
        str(ref.get("realmSlug") or "").strip().lower(),
        str(ref.get("characterName") or "").strip().lower(),
    )


def failed_simc_stats_filter_sql():
    if DEFAULT_RETRY_FAILED_SIMC_STATS:
        return ""
    return "AND COALESCE(json_extract(payload_json, '$.simcStatStatus'), '') != 'failed'"


def existing_observed_variant_profiles(conn, variant_limit=DEFAULT_TARGET_LIMIT, profile_limit=DEFAULT_PROFILE_LIMIT):
    failed_filter = failed_simc_stats_filter_sql()
    rows = conn.execute(
        f"""
        SELECT id, item_id, slot, item_level, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
          AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
          AND COALESCE(simc_options_json, '{{}}') NOT IN ('{{}}', '')
          {failed_filter}
        ORDER BY updated_at ASC, id ASC
        LIMIT ?
        """,
        (max(1, int(variant_limit or DEFAULT_TARGET_LIMIT)),),
    ).fetchall()
    selected_keys = []
    selected_key_set = set()
    row_entries = []
    for row_id, item_id, slot, item_level, simc_options_json, payload_json in rows:
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
        spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
        refs = observed_variant_profile_refs(
            payload,
            class_key=class_keys[0] if class_keys else "",
            spec_key=spec_keys[0] if spec_keys else "",
            slot=slot,
            item_id=item_id,
            item_level=item_level,
        )
        if not refs:
            continue
        ref = refs[0]
        key = observed_profile_group_key(ref, class_keys[0] if class_keys else "", spec_keys[0] if spec_keys else "")
        if key not in selected_key_set:
            if len(selected_keys) >= max(1, int(profile_limit or DEFAULT_PROFILE_LIMIT)):
                continue
            selected_key_set.add(key)
            selected_keys.append(key)
        row_entries.append((key, row_id, item_id, slot, item_level, simc_options_json, payload, ref))
    if not selected_key_set:
        return []
    all_rows = conn.execute(
        f"""
        SELECT id, item_id, slot, item_level, simc_options_json, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
          AND COALESCE(simc_options_json, '{{}}') NOT IN ('{{}}', '')
          {failed_filter}
        ORDER BY id ASC
        """
    ).fetchall()
    grouped = {}
    seen_items_by_group = {}
    for row_id, item_id, slot, item_level, simc_options_json, payload_json in all_rows:
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
        spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
        refs = observed_variant_profile_refs(
            payload,
            class_key=class_keys[0] if class_keys else "",
            spec_key=spec_keys[0] if spec_keys else "",
            slot=slot,
            item_id=item_id,
            item_level=item_level,
        )
        for ref in refs:
            key = observed_profile_group_key(ref, class_keys[0] if class_keys else "", spec_keys[0] if spec_keys else "")
            if key not in selected_key_set:
                continue
            profile = grouped.setdefault(
                key,
                {
                    "name": ref.get("characterName") or "local_observed_profile",
                    "characterName": ref.get("characterName") or "",
                    "realmSlug": ref.get("realmSlug") or "",
                    "region": "cn",
                    "classKey": websim_payload.slugify(ref.get("classKey") or (class_keys[0] if class_keys else ""), "mage"),
                    "specKey": websim_payload.slugify(ref.get("specKey") or (spec_keys[0] if spec_keys else ""), ""),
                    "profileUrl": ref.get("profileUrl") or "",
                    "gear": [],
                },
            )
            item_key = (slot, str(item_id or ""))
            seen = seen_items_by_group.setdefault(key, set())
            if item_key in seen:
                continue
            seen.add(item_key)
            simc_options = websim_payload.safe_json_loads(simc_options_json, {})
            simc_options = simc_options if isinstance(simc_options, dict) else {}
            gear_item = {
                "slot": slot,
                "itemId": str(item_id or ""),
                "itemLevel": int(item_level or 0),
                "name": payload.get("displayName") or f"Item {item_id}",
                "characterName": ref.get("characterName") or "",
                "realmSlug": ref.get("realmSlug") or "",
                "profileUrl": ref.get("profileUrl") or "",
            }
            gear_item.update({key: value for key, value in simc_options.items() if value})
            profile["gear"].append(gear_item)
    return [profile for profile in grouped.values() if profile.get("gear")]


def observed_variant_profile_candidates(conn):
    failed_filter = failed_simc_stats_filter_sql()
    rows = conn.execute(
        f"""
        SELECT item_id, slot, item_level, payload_json
        FROM websim_gear_variants
        WHERE source_type = 'observed_profile'
          AND status = 'verified'
          AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
          {failed_filter}
        ORDER BY updated_at ASC, id ASC
        """
    ).fetchall()
    candidates = []
    seen = set()
    for item_id, slot, item_level, payload_json in rows:
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
        spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
        refs = observed_variant_profile_refs(
            payload,
            class_key=class_keys[0] if class_keys else "",
            spec_key=spec_keys[0] if spec_keys else "",
            slot=slot,
            item_id=item_id,
            item_level=item_level,
        )
        for ref in refs:
            candidate = {
                "name": ref.get("characterName") or ref.get("name") or "",
                "realmSlug": ref.get("realmSlug") or "",
                "region": ref.get("region") or "cn",
                "classKey": websim_payload.slugify(ref.get("classKey") or (class_keys[0] if class_keys else ""), ""),
                "specKey": websim_payload.slugify(ref.get("specKey") or (spec_keys[0] if spec_keys else ""), ""),
                "profileUrl": ref.get("profileUrl") or "",
            }
            if not raiderio_payload.is_profile_candidate(candidate):
                continue
            key = raiderio_payload.character_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def simc_error_item_ids(errors):
    item_ids = []
    for error in errors or []:
        text = str(error or "")
        for match in re.finditer(r"Item ['\"](?:item_)?(\d+)['\"]", text):
            item_id = match.group(1)
            if item_id not in item_ids:
                item_ids.append(item_id)
        for match in re.finditer(r"\bitem id=(\d+)\b", text, flags=re.IGNORECASE):
            item_id = match.group(1)
            if item_id not in item_ids:
                item_ids.append(item_id)
    return item_ids


def simc_error_failed_profile_names(errors):
    names = []
    for error in errors or []:
        text = str(error or "")
        if "not currently supported" not in text and "No active players in sim" not in text:
            continue
        for match in re.finditer(r"Player ['\"]([^'\"]+)['\"]", text):
            name = match.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def simc_error_for_item(errors, item_id):
    needle = f"item_{item_id}"
    for error in errors or []:
        text = str(error or "")
        if needle in text or f"Item '{item_id}'" in text or f'Item "{item_id}"' in text or f"item id={item_id}" in text:
            return text
    return str((errors or [""])[0] or "")


def simc_error_for_profile(errors, character_name):
    needle = f"Player '{character_name}'"
    quoted = f'Player "{character_name}"'
    for error in errors or []:
        text = str(error or "")
        if needle in text or quoted in text:
            return text
    return str((errors or [""])[0] or "")


def observed_payload_matches_character_name(payload, character_name):
    for ref in observed_variant_profile_refs(payload):
        if str(ref.get("characterName") or "").strip() == character_name:
            return True
    return False


def mark_existing_observed_variant_simc_failures(conn, errors):
    item_ids = simc_error_item_ids(errors)
    profile_names = simc_error_failed_profile_names(errors)
    if not item_ids and not profile_names:
        return 0
    marked = 0
    now = utc_now_iso()
    for item_id in item_ids:
        rows = conn.execute(
            """
            SELECT id, payload_json
            FROM websim_gear_variants
            WHERE source_type = 'observed_profile'
              AND status = 'verified'
              AND item_id = ?
              AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
            """,
            (item_id,),
        ).fetchall()
        error_text = simc_error_for_item(errors, item_id)
        for row_id, payload_json in rows:
            payload = websim_payload.safe_json_loads(payload_json, {})
            payload = payload if isinstance(payload, dict) else {}
            payload["simcStatStatus"] = "failed"
            payload["simcStatFailureKind"] = "item_resolution"
            payload["simcStatError"] = error_text[:500]
            payload["simcStatCheckedAt"] = now
            conn.execute(
                """
                UPDATE websim_gear_variants
                SET payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(payload, ensure_ascii=False), now, row_id),
            )
            marked += 1
    if profile_names:
        rows = conn.execute(
            """
            SELECT id, payload_json
            FROM websim_gear_variants
            WHERE source_type = 'observed_profile'
              AND status = 'verified'
              AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
              AND COALESCE(json_extract(payload_json, '$.simcStatStatus'), '') != 'failed'
            """
        ).fetchall()
        for row_id, payload_json in rows:
            payload = websim_payload.safe_json_loads(payload_json, {})
            payload = payload if isinstance(payload, dict) else {}
            matched_name = next((name for name in profile_names if observed_payload_matches_character_name(payload, name)), "")
            if not matched_name:
                continue
            payload["simcStatStatus"] = "failed"
            payload["simcStatFailureKind"] = "unsupported_profile"
            payload["simcStatError"] = simc_error_for_profile(errors, matched_name)[:500]
            payload["simcStatCheckedAt"] = now
            conn.execute(
                """
                UPDATE websim_gear_variants
                SET payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(payload, ensure_ascii=False), now, row_id),
            )
            marked += 1
    return marked


def run_existing_observed_variant_simc_stats_backfill(
    db_path=DB_PATH,
    *,
    simc_runner=None,
    variant_limit=DEFAULT_TARGET_LIMIT,
    profile_limit=DEFAULT_PROFILE_LIMIT,
    simc_timeout_seconds=DEFAULT_SIMC_TIMEOUT_SECONDS,
    stage_callback=None,
):
    db_path = Path(db_path)
    started_monotonic = time.monotonic()
    emit_stage(stage_callback, "existing_observed_variant_simc_stats", "start")
    conn = connect_backfill_db(db_path)
    try:
        websim_payload.ensure_websim_tables(conn)
        profiles = existing_observed_variant_profiles(conn, variant_limit=variant_limit, profile_limit=profile_limit)
        simc_stats = {
            "simcProfileCount": 0,
            "simcResolvedProfileCount": 0,
            "simcResolvedSlotCount": 0,
            "simcErrors": [],
        }
        if profiles:
            profiles, simc_stats = enrich_profiles_with_simc_json_stats(
                profiles,
                simc_runner or SimulationCraftGearStatsRunner(),
                timeout_seconds=simc_timeout_seconds,
            )
        simc_failure_rows_marked = run_sqlite_lock_retry(
            lambda: mark_existing_observed_variant_simc_failures(conn, simc_stats["simcErrors"])
        )
        resolved_profiles = [profile for profile in profiles if isinstance(profile.get("simcJson"), dict)]
        season = websim_payload.get_active_season_payload(conn)
        observed_counts = websim_payload.sync_observed_gear_variants(
            conn,
            observed_payload(RaiderIOObservedBackfillProvider(), resolved_profiles, utc_now_iso(), simc_stats["simcErrors"]),
            season,
            replace=False,
        )
        promotion_counts = run_sqlite_lock_retry(lambda: websim_payload.promote_official_gear_variants_from_observed(conn))
        refresh_counts = run_sqlite_lock_retry(lambda: websim_payload.refresh_official_observed_variant_payloads_from_observed(conn))
        gear_state = websim_payload.build_gear_catalog_sync_state(conn, season)
        gear_state["existingObservedVariantSimcStats"] = {
            "lastRunStatus": "partial" if simc_stats["simcErrors"] else "ok",
            "localProfileCount": len(profiles),
            "resolvedProfileCount": simc_stats["simcResolvedProfileCount"],
            "resolvedSlotCount": simc_stats["simcResolvedSlotCount"],
            "simcFailureRowsMarked": simc_failure_rows_marked,
            "observedVariantRowsUpserted": observed_counts.get("observedVariants") or 0,
            "refreshedOfficialObservedVariants": refresh_counts.get("refreshedOfficialObservedVariants") or 0,
        }
        websim_payload.set_sync_state(conn, "gearCatalog", gear_state)
        conn.commit()
        status = "partial" if simc_stats["simcErrors"] else "ok"
        summary = {
            "status": status,
            "localProfileCount": len(profiles),
            "observedVariantRowsUpserted": observed_counts.get("observedVariants") or 0,
            "verifiedObservedVariants": observed_counts.get("verifiedObservedVariants") or 0,
            "officialVariantsPromoted": promotion_counts.get("promotedVariants") or 0,
            "officialObservedVariantsRefreshed": refresh_counts.get("refreshedOfficialObservedVariants") or 0,
            "simcFailureRowsMarked": simc_failure_rows_marked,
            **simc_stats,
            "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
            "errors": simc_stats["simcErrors"][:12],
        }
        emit_stage(
            stage_callback,
            "existing_observed_variant_simc_stats",
            "complete",
            started_monotonic,
            runStatus=status,
            resolvedSlotCount=simc_stats["simcResolvedSlotCount"],
        )
        return summary
    finally:
        conn.close()


class RaiderIOObservedBackfillProvider:
    name = "raiderio"

    def target_item_ids(self, conn):
        return raiderio_payload.raiderio_target_item_ids(conn)

    def candidate_profiles(self, conn):
        cached = raiderio_payload.read_cache(conn)
        candidates = [
            *observed_variant_profile_candidates(conn),
            *raiderio_payload.unique_profile_candidates_for_runs(cached.get("runs") or []),
        ]
        unique = []
        seen = set()
        for candidate in candidates:
            if not raiderio_payload.is_profile_candidate(candidate):
                continue
            key = raiderio_payload.character_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

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


def append_unique(values, value):
    value = str(value or "").strip()
    if value and value not in values:
        values.append(value)


def item_id_sort_key(item_id):
    text = str(item_id or "").strip()
    try:
        return (0, int(text), text)
    except ValueError:
        return (1, 0, text)


def observed_missing_stat_gap_summary(conn, target_item_ids=None, planned_target_item_ids=None, limit=20):
    target_ids = set(websim_payload.gear_observed_backfill_target_ids(target_item_ids))
    planned_ids = websim_payload.gear_observed_backfill_target_ids(planned_target_item_ids)
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='websim_gear_variants'"
        ).fetchone()
        if not table_exists:
            return {
                "totalMissingObservedVariantCount": 0,
                "targetMissingObservedVariantCount": 0,
                "topMissingObservedItems": [],
                "plannedTargetItems": [],
            }
        rows = conn.execute(
            """
            SELECT item_id, slot, item_level, payload_json
            FROM websim_gear_variants
            WHERE source_type = 'observed_profile'
              AND status = 'verified'
              AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
            ORDER BY item_id, slot, item_level, id
            """
        ).fetchall()
    except Exception:
        return {
            "totalMissingObservedVariantCount": 0,
            "targetMissingObservedVariantCount": 0,
            "topMissingObservedItems": [],
            "plannedTargetItems": [],
        }

    by_item = {}
    total_missing = 0
    target_missing = 0
    for item_id, slot, item_level, payload_json in rows:
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        total_missing += 1
        if item_id in target_ids:
            target_missing += 1
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        entry = by_item.setdefault(
            item_id,
            {
                "itemId": item_id,
                "displayName": "",
                "missingObservedVariantCount": 0,
                "slots": [],
                "itemLevels": [],
                "specs": [],
                "profileRefCount": 0,
                "_profileKeys": set(),
            },
        )
        entry["missingObservedVariantCount"] += 1
        if not entry["displayName"]:
            entry["displayName"] = str(payload.get("displayName") or payload.get("name") or "").strip()
        append_unique(entry["slots"], slot)
        append_unique(entry["itemLevels"], item_level)
        refs = observed_variant_profile_refs(payload, slot=slot, item_id=item_id, item_level=item_level)
        for ref in refs:
            spec_label = ":".join(
                part
                for part in [
                    websim_payload.slugify(ref.get("classKey"), ""),
                    websim_payload.slugify(ref.get("specKey"), ""),
                ]
                if part
            )
            append_unique(entry["specs"], spec_label)
            key = observed_profile_group_key(ref)
            if key not in entry["_profileKeys"]:
                entry["_profileKeys"].add(key)
                entry["profileRefCount"] += 1
        if not refs:
            class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
            spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
            for index, class_key in enumerate(class_keys):
                spec_key = spec_keys[index] if index < len(spec_keys) else (spec_keys[0] if spec_keys else "")
                spec_label = ":".join(
                    part
                    for part in [
                        websim_payload.slugify(class_key, ""),
                        websim_payload.slugify(spec_key, ""),
                    ]
                    if part
                )
                append_unique(entry["specs"], spec_label)

    def clean(entry):
        result = {key: value for key, value in entry.items() if key != "_profileKeys"}
        result["itemLevels"] = [int(value) if str(value).isdigit() else value for value in result.get("itemLevels") or []]
        return result

    all_items = [clean(entry) for entry in by_item.values()]
    all_items.sort(
        key=lambda entry: (
            -int(entry.get("missingObservedVariantCount") or 0),
            item_id_sort_key(entry.get("itemId")),
        )
    )
    planned = [clean(by_item[item_id]) for item_id in planned_ids if item_id in by_item]
    return {
        "totalMissingObservedVariantCount": total_missing,
        "targetMissingObservedVariantCount": target_missing,
        "topMissingObservedItems": all_items[: max(0, int(limit or 20))],
        "plannedTargetItems": planned,
    }


SOURCE_GAP_UNTRUSTED_SOURCE_TYPES = {"observed_profile", "simcpreset", "simc_preset"}
SOURCE_GAP_TRUSTED_SOURCE_TYPES = {
    *getattr(websim_payload, "OFFICIAL_REPLACEMENT_SOURCE_TYPES", {"dungeon", "mythic_plus", "mythicplus", "raid", "tier_set"}),
    "crafted",
    "loot",
    "verifiedloot",
    "verified_loot",
}
SOURCE_GAP_GENERIC_LABELS = {
    "catalog",
    "gear catalog",
    "websim catalog",
    "source reference",
    "unknown",
    "来源待补充",
    "来源未知",
}


def source_gap_source_type(value):
    return websim_payload.raw_source_type(value, "").strip().lower()


def source_gap_label(value):
    return str(value or "").strip()


def source_gap_source_label(source):
    if not isinstance(source, dict):
        return ""
    return source_gap_label(source.get("label") or source.get("sourceLabel") or source.get("source"))


def source_gap_label_is_generic(label):
    normalized = re.sub(r"\s+", " ", source_gap_label(label)).strip().lower()
    return not normalized or normalized in SOURCE_GAP_GENERIC_LABELS


def source_gap_source_is_trusted(source):
    if not isinstance(source, dict):
        return False
    source_type = source_gap_source_type(source.get("sourceType") or source.get("type"))
    label = source_gap_source_label(source)
    if source_type in SOURCE_GAP_UNTRUSTED_SOURCE_TYPES:
        return False
    if websim_payload.gear_observed_source_label(label) or websim_payload.gear_simc_preset_source_label(label):
        return False
    if source_gap_label_is_generic(label):
        return False
    if source_type in SOURCE_GAP_TRUSTED_SOURCE_TYPES:
        return True
    return bool(source.get("instanceId") or source.get("instance_id") or source.get("encounterId") or source.get("encounter_id"))


def source_gap_payload_sources(payload):
    if not isinstance(payload, dict):
        return []
    sources = []
    for key in ("sources", "sourceRefs"):
        for source in payload.get(key) or []:
            if isinstance(source, dict):
                sources.append(source)
    source_type = payload.get("sourceType") or payload.get("type")
    label = first_non_empty(payload, "source", "sourceName", "sourceLabel", "label", "encounterName", "instanceName")
    if source_type or label:
        sources.append(
            {
                "sourceType": source_type,
                "sourceLabel": label,
                "instanceId": payload.get("instanceId") or payload.get("instance_id"),
                "encounterId": payload.get("encounterId") or payload.get("encounter_id"),
            }
        )
    return sources


def first_non_empty(source, *keys):
    if not isinstance(source, dict):
        return ""
    for key in keys:
        value = str(source.get(key) or "").strip()
        if value:
            return value
    return ""


def append_source_gap_specs(entry, payload):
    refs = payload.get("observedProfileRefs") if isinstance(payload.get("observedProfileRefs"), list) else []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        spec_label = ":".join(
            part
            for part in [
                websim_payload.slugify(ref.get("classKey"), ""),
                websim_payload.slugify(ref.get("specKey"), ""),
            ]
            if part
        )
        append_unique(entry["specs"], spec_label)
    if refs:
        return
    class_keys = payload.get("classKeys") if isinstance(payload.get("classKeys"), list) else []
    spec_keys = payload.get("specKeys") if isinstance(payload.get("specKeys"), list) else []
    for index, class_key in enumerate(class_keys):
        spec_key = spec_keys[index] if index < len(spec_keys) else (spec_keys[0] if spec_keys else "")
        spec_label = ":".join(
            part
            for part in [
                websim_payload.slugify(class_key, ""),
                websim_payload.slugify(spec_key, ""),
            ]
            if part
        )
        append_unique(entry["specs"], spec_label)


def observed_source_gap_summary(conn, target_item_ids=None, planned_target_item_ids=None, limit=20):
    target_ids = set(websim_payload.gear_observed_backfill_target_ids(target_item_ids))
    planned_ids = websim_payload.gear_observed_backfill_target_ids(planned_target_item_ids)
    empty = {
        "totalSourcePendingItemCount": 0,
        "targetSourcePendingItemCount": 0,
        "topSourcePendingItems": [],
        "plannedTargetItems": [],
    }
    try:
        variant_table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='websim_gear_variants'"
        ).fetchone()
        if not variant_table_exists:
            return empty
        source_table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='websim_gear_sources'"
        ).fetchone()
        source_rows = []
        if source_table_exists:
            source_rows = conn.execute(
                """
                SELECT item_id, source_type, source_label, instance_id, encounter_id, payload_json
                FROM websim_gear_sources
                ORDER BY item_id, source_type, source_label, id
                """
            ).fetchall()
        variant_rows = conn.execute(
            """
            SELECT item_id, slot, item_level, source_type, payload_json
            FROM websim_gear_variants
            WHERE status IN ('verified', 'partial')
            ORDER BY item_id, slot, item_level, id
            """
        ).fetchall()
    except Exception:
        return empty

    sources_by_item = {}
    for item_id, source_type, source_label, instance_id, encounter_id, payload_json in source_rows:
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        source = {
            "sourceType": source_type,
            "sourceLabel": source_label,
            "label": source_label,
            "instanceId": instance_id,
            "encounterId": encounter_id,
        }
        source.update({key: value for key, value in payload.items() if key not in source or source.get(key) in (None, "")})
        sources_by_item.setdefault(item_id, []).append(source)

    by_item = {}
    for item_id, slot, item_level, source_type, payload_json in variant_rows:
        item_id = str(item_id or "").strip()
        if not item_id:
            continue
        payload = websim_payload.safe_json_loads(payload_json, {})
        payload = payload if isinstance(payload, dict) else {}
        sources = [
            *sources_by_item.get(item_id, []),
            *source_gap_payload_sources(payload),
            {"sourceType": source_type, "sourceLabel": first_non_empty(payload, "source", "sourceName", "sourceLabel", "label")},
        ]
        source_types = []
        for source in sources:
            append_unique(source_types, source_gap_source_type((source or {}).get("sourceType") or (source or {}).get("type")))
        if any(source_gap_source_is_trusted(source) for source in sources):
            continue
        entry = by_item.setdefault(
            item_id,
            {
                "itemId": item_id,
                "displayName": "",
                "sourcePendingVariantCount": 0,
                "slots": [],
                "itemLevels": [],
                "specs": [],
                "sourceTypes": [],
            },
        )
        entry["sourcePendingVariantCount"] += 1
        if not entry["displayName"]:
            entry["displayName"] = first_non_empty(payload, "displayName", "localizedName", "name", "englishName")
        append_unique(entry["slots"], slot)
        append_unique(entry["itemLevels"], item_level)
        for source_type_value in source_types:
            append_unique(entry["sourceTypes"], source_type_value)
        append_source_gap_specs(entry, payload)

    def clean(entry):
        result = dict(entry)
        result["itemLevels"] = [int(value) if str(value).isdigit() else value for value in result.get("itemLevels") or []]
        result["sourceTypes"] = [value for value in result.get("sourceTypes") or [] if value]
        return result

    all_items = [clean(entry) for entry in by_item.values()]
    all_items.sort(
        key=lambda entry: (
            -int(entry.get("sourcePendingVariantCount") or 0),
            item_id_sort_key(entry.get("itemId")),
        )
    )
    planned = [clean(by_item[item_id]) for item_id in planned_ids if item_id in by_item]
    target_pending_items = sum(1 for item_id in by_item if item_id in target_ids)
    return {
        "totalSourcePendingItemCount": len(by_item),
        "targetSourcePendingItemCount": target_pending_items,
        "topSourcePendingItems": all_items[: max(0, int(limit or 20))],
        "plannedTargetItems": planned,
    }


def plan_gear_observed_backfill(
    db_path=DB_PATH,
    *,
    provider=None,
    target_limit=DEFAULT_TARGET_LIMIT,
    profile_limit=DEFAULT_PROFILE_LIMIT,
):
    provider = provider or RaiderIOObservedBackfillProvider()
    db_path = Path(db_path)
    started_monotonic = time.monotonic()
    conn = connect_readonly_backfill_db(db_path)
    try:
        target_item_ids = websim_payload.gear_observed_backfill_target_ids(provider.target_item_ids(conn))
        raw_state = websim_payload.get_sync_state(conn, websim_payload.GEAR_OBSERVED_BACKFILL_SYNC_KEY)
        state = websim_payload.normalize_gear_observed_backfill_state(
            raw_state,
            target_item_ids=target_item_ids,
            provider=provider.name,
        )
        candidates = [] if not target_item_ids else list(provider.candidate_profiles(conn))
        window = websim_payload.build_gear_observed_backfill_window(
            target_item_ids,
            candidates,
            state,
            target_limit=target_limit,
            profile_limit=profile_limit,
        )
        return {
            "status": "ok",
            "provider": provider.name,
            "planOnly": True,
            "targetItemCount": len(target_item_ids),
            "candidateProfileCount": len(candidates),
            "processedTargetItemIds": window["targetItemIds"],
            "processedProfileCount": len(window["profiles"]),
            "plannedProfiles": window["profiles"],
            "missingStatSummary": observed_missing_stat_gap_summary(
                conn,
                target_item_ids=target_item_ids,
                planned_target_item_ids=window["targetItemIds"],
            ),
            "sourceGapSummary": observed_source_gap_summary(
                conn,
                target_item_ids=target_item_ids,
                planned_target_item_ids=window["targetItemIds"],
            ),
            "cursor": window["cursor"],
            "wrapped": window["wrapped"],
            "durationSeconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
            "errors": [],
        }
    finally:
        conn.close()


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

    conn = connect_backfill_db(db_path)
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
                    "officialObservedVariantRowsPrunedMissingStats": 0,
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
            promotion_counts = run_sqlite_lock_retry(lambda: websim_payload.promote_official_gear_variants_from_observed(conn))
            refresh_counts = run_sqlite_lock_retry(lambda: websim_payload.refresh_official_observed_variant_payloads_from_observed(conn))
            official_prune_counts = {"officialObservedVariantRowsPrunedMissingStats": 0}
            if enable_simc_stats:
                official_prune_counts = run_sqlite_lock_retry(lambda: websim_payload.prune_official_observed_variants_missing_simc_stats(conn))
            gear_state = websim_payload.build_gear_catalog_sync_state(conn, season)
            gear_state["observedBackfill"] = {
                "provider": provider.name,
                "lastRunStatus": "partial" if fetch_errors else "ok",
                "processedTargetItemIds": window["targetItemIds"],
                "processedProfileCount": len(window["profiles"]),
                "matchedTargetItemIds": matched_ids,
                "refreshedOfficialObservedVariants": refresh_counts.get("refreshedOfficialObservedVariants") or 0,
                **prune_counts,
                **official_prune_counts,
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
                    **official_prune_counts,
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
                **official_prune_counts,
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
                "officialObservedVariantRowsPrunedMissingStats": 0,
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
    parser.add_argument("--existing-observed-simc-stats-only", action="store_true", help="Use existing observed variants in the local DB to generate SimC stat payloads; does not fetch external profiles.")
    parser.add_argument("--plan-only", action="store_true", help="Print the next target/profile window without fetching profiles, running SimC, or writing DB state.")
    parser.add_argument("--simc-timeout-seconds", type=int, default=DEFAULT_SIMC_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="Emit compact JSON summary.")
    args = parser.parse_args(argv)
    if postgres_only_runtime_enabled() and not sqlite_migration_source_enabled():
        summary = run_gear_observed_backfill_postgres()
    elif args.plan_only:
        summary = plan_gear_observed_backfill(
            args.db,
            target_limit=args.target_limit,
            profile_limit=args.profile_limit,
        )
    elif args.existing_observed_simc_stats_only:
        summary = run_existing_observed_variant_simc_stats_backfill(
            args.db,
            variant_limit=args.target_limit,
            profile_limit=args.profile_limit,
            simc_timeout_seconds=args.simc_timeout_seconds,
            stage_callback=print_stage,
        )
    else:
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
    return 0 if summary.get("runner") == "postgres" or summary.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
