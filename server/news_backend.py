#!/usr/bin/env python3
import copy
import gzip
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, unquote, urlparse
from urllib.request import urlopen

try:
    from .analytics import (
        analytics_events,
        analytics_features,
        analytics_pages,
        analytics_simulator,
        analytics_summary,
        analytics_users,
        ensure_analytics_tables,
        record_events,
        rollup_daily_metrics,
    )
    from .news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from .news_translator import body_blocks_text, localize_article, normalize_body_blocks, source_body_quality_issue, visible_translation_issues
    from .db import (
        connect_postgres,
        database_config_from_env,
        postgres_only_runtime_enabled,
        postgres_runtime_enabled,
        sqlite_connection,
        sqlite_runtime_disabled,
    )
    from .simulator_payload import (
        analyze_simulator_request,
        build_simulator_home_payload,
        clean_simc_gear_items,
        normalize_simc_race,
        normalize_simc_slot,
        simc_version_status,
        warcraftlogs_credentials_state,
    )
    from .simc_preparation import simc_preparation_payload, simc_preparation_report
    try:
        from .codex_worker import run_codex_job
    except ImportError:
        run_codex_job = None
    from .raiderio_payload import (
        enrich_builds_detail_payload as enrich_raiderio_builds_detail_payload,
        enrich_builds_home_payload as enrich_raiderio_builds_home_payload,
        enrich_builds_intel_payload as enrich_raiderio_builds_intel_payload,
        enrich_game_season_payload,
        enrich_pve_home_payload as enrich_raiderio_pve_home_payload,
        enrich_pve_module_payload as enrich_raiderio_pve_module_payload,
        get_raiderio_payload,
        sync_raiderio_cache,
    )
    from .stat_weights_payload import (
        enrich_builds_detail_stat_weights,
        latest_stat_weight_run_payload,
    )
    from .gear_runtime import (
        build_profile_from_selection_intent,
        import_community_template,
        is_canonical_profile_request,
        resolve_selection_intent,
    )
    from .gear_stat_snapshot_api import get_or_start_stat_snapshot
    from .websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ARMOR_SLOTS,
        apply_gear_template_legality_gate,
        build_websim_profile,
        build_websim_gear_stats_response,
        build_websim_profile_response,
        build_websim_profile_response_from_resolved_snapshot,
        build_websim_simulator_request,
        CLASS_ARMOR_TYPES,
        community_talent_sync_state,
        enrich_build_gear_payload,
        ensure_websim_tables,
        gear_catalog_health_payload,
        gear_legality_authority_health_payload,
        gear_resolver_runtime_authority,
        GAME_CLASS_ID_TO_KEY,
        GEAR_SLOT_LABELS,
        talent_catalog_health_payload,
        export_talent_api_payload,
        get_active_season_payload,
        get_sync_state,
        get_websim_assets,
        get_websim_bootstrap,
        get_websim_gear,
        get_websim_loot,
        get_websim_talent_import,
        get_websim_talents,
        get_active_season_payload,
        import_talent_api_payload,
        websim_talent_import_response,
        websim_gear_community_template_sync_state,
        item_type_metadata_from_payload,
        normalized_armor_subclass,
        encode_websim_talents,
        parse_websim_talent_export_code,
        payload_item_class_is_armor,
        payload_playable_class_keys,
        selected_gear_weapon_rule_blockers,
        simcraft_known_compatibility_blockers,
        SIMC_GEAR_OPTION_KEYS,
        template_evidence_audit_payload,
        validate_talent_api_payload,
        WEAPON_SLOTS,
        weapon_type_allowed_for_slot,
    )
except ImportError:
    from analytics import (
        analytics_events,
        analytics_features,
        analytics_pages,
        analytics_simulator,
        analytics_summary,
        analytics_users,
        ensure_analytics_tables,
        record_events,
        rollup_daily_metrics,
    )
    from news_collector import canonical_article_key, collect_feed_articles, merge_articles
    from news_translator import body_blocks_text, localize_article, normalize_body_blocks, source_body_quality_issue, visible_translation_issues
    from db import (
        connect_postgres,
        database_config_from_env,
        postgres_only_runtime_enabled,
        postgres_runtime_enabled,
        sqlite_connection,
        sqlite_runtime_disabled,
    )
    from simulator_payload import (
        analyze_simulator_request,
        build_simulator_home_payload,
        clean_simc_gear_items,
        normalize_simc_race,
        normalize_simc_slot,
        simc_version_status,
        warcraftlogs_credentials_state,
    )
    from simc_preparation import simc_preparation_payload, simc_preparation_report
    try:
        from codex_worker import run_codex_job
    except ImportError:
        run_codex_job = None
    from raiderio_payload import (
        enrich_builds_detail_payload as enrich_raiderio_builds_detail_payload,
        enrich_builds_home_payload as enrich_raiderio_builds_home_payload,
        enrich_builds_intel_payload as enrich_raiderio_builds_intel_payload,
        enrich_game_season_payload,
        enrich_pve_home_payload as enrich_raiderio_pve_home_payload,
        enrich_pve_module_payload as enrich_raiderio_pve_module_payload,
        get_raiderio_payload,
        sync_raiderio_cache,
    )
    from stat_weights_payload import (
        enrich_builds_detail_stat_weights,
        latest_stat_weight_run_payload,
    )
    from gear_runtime import (
        build_profile_from_selection_intent,
        import_community_template,
        is_canonical_profile_request,
        resolve_selection_intent,
    )
    from gear_stat_snapshot_api import get_or_start_stat_snapshot
    from websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ARMOR_SLOTS,
        apply_gear_template_legality_gate,
        build_websim_profile,
        build_websim_gear_stats_response,
        build_websim_profile_response,
        build_websim_profile_response_from_resolved_snapshot,
        build_websim_simulator_request,
        CLASS_ARMOR_TYPES,
        community_talent_sync_state,
        enrich_build_gear_payload,
        ensure_websim_tables,
        gear_catalog_health_payload,
        gear_legality_authority_health_payload,
        gear_resolver_runtime_authority,
        GAME_CLASS_ID_TO_KEY,
        GEAR_SLOT_LABELS,
        talent_catalog_health_payload,
        export_talent_api_payload,
        get_active_season_payload,
        get_sync_state,
        get_websim_assets,
        get_websim_bootstrap,
        get_websim_gear,
        get_websim_loot,
        get_websim_talent_import,
        get_websim_talents,
        get_active_season_payload,
        import_talent_api_payload,
        websim_talent_import_response,
        websim_gear_community_template_sync_state,
        item_type_metadata_from_payload,
        normalized_armor_subclass,
        encode_websim_talents,
        parse_websim_talent_export_code,
        payload_item_class_is_armor,
        payload_playable_class_keys,
        selected_gear_weapon_rule_blockers,
        simcraft_known_compatibility_blockers,
        SIMC_GEAR_OPTION_KEYS,
        template_evidence_audit_payload,
        validate_talent_api_payload,
        WEAPON_SLOTS,
        weapon_type_allowed_for_slot,
    )

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
WEBSIM_DIR = PROJECT_DIR / "websim"
SEED_PATH = BASE_DIR / "news" / "articles.seed.json"
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
DB_CONFIG = database_config_from_env()
DB_PATH = DB_CONFIG.sqlite_path or DB_PATH
HOST = os.environ.get("WOW_NEWS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WOW_NEWS_PORT", "8787"))
ENABLE_COLLECTORS = os.environ.get("WOW_NEWS_ENABLE_COLLECTORS", "0") == "1"
WEB_GEAR_BUILD_DEFAULT_WORKERS = 4
PUBLIC_REFRESH_MODES = {"scheduled"}
AUTH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
GUEST_SIMULATOR_OPENID = "guest-simulator"
BUILD_TEMPLATE_SCHEMA_VERSION = 1
VALID_BUILD_TEMPLATE_TYPES = {"talent", "gear"}
SCHEMA_MIGRATIONS = [
    ("core_schema_v1", "Core news, auth, simulator, WebSim, and analytics tables are initialized."),
    ("user_build_templates_v1", "Authenticated user build template sync table is initialized."),
    ("chickenbro_backend_v1", "Chickenbro sessions, messages, jobs, structured memory, and playstyle profiles are initialized."),
    ("simulator_task_summary_v1", "Simulator tasks persist a compact list summary read model."),
    ("simulator_task_worker_ready_v1", "Simulator tasks reserve worker-ready queue governance fields."),
    ("admin_gate_diagnostics_v1", "Admin gate diagnostics and audit log overlay tables are initialized."),
]
CHICKENBRO_PROFILE_STATUSES = {"published", "partial", "stale", "blocked", "needs_review"}
CHICKENBRO_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "timed_out"}
CHICKENBRO_PRODUCT_PHASES = {"retail", "ptr", "beta"}
CHICKENBRO_SCENARIOS = {
    "raid_single",
    "raid_cleave",
    "raid_multi",
    "mplus_fortified",
    "mplus_tyrannical",
}
_WEB_GEAR_BUILD_LIMITER = None
_WEB_GEAR_BUILD_LIMITER_LIMIT = None
_WEB_GEAR_BUILD_LIMITER_LOCK = threading.Lock()
_GEAR_AUTHORITY_CACHE_KEY = None
_GEAR_AUTHORITY_CACHE = None
_GEAR_AUTHORITY_CACHE_LOCK = threading.Lock()
CHICKENBRO_ALLOWED_TOOL_TOPICS = {
    "wcl",
    "warcraft logs",
    "warcraftlogs",
    "raider.io",
    "raiderio",
    "rio",
    "simc",
    "simulationcraft",
    "weakaura",
    "weak aura",
    "wa",
    "插件",
    "宏",
}

CHANNELS = [
    {"id": "retail", "title": "正式服动态", "desc": "官方公告、热修、活动与正式服版本内容"},
    {"id": "ptr", "title": "测试服前瞻", "desc": "PTR / Beta 改动、前瞻与开发说明"},
    {"id": "class", "title": "职业强度变化", "desc": "职业调优、套装修正与强度趋势"},
]

TRUSTED_SOURCES = {
    "Blizzard News": {"worldofwarcraft.blizzard.com", "news.blizzard.com"},
    "Blizzard Forums": {"us.forums.blizzard.com"},
    "Wowhead": {"www.wowhead.com"},
    "Icy Veins": {"www.icy-veins.com"},
}

NEWS_SOURCE_REGISTRY = [
    {
        "sourceId": "blizzard",
        "sourceName": "Blizzard News",
        "tier": "official",
        "fetchMode": "html_detail",
        "retailOnly": True,
        "licenseStatus": "approved",
        "rateLimit": "polite:15s-timeout",
        "enabled": True,
        "hostnames": ["worldofwarcraft.blizzard.com", "news.blizzard.com"],
        "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news",
    },
    {
        "sourceId": "wowhead",
        "sourceName": "Wowhead",
        "tier": "trusted_media",
        "fetchMode": "rss_reference",
        "retailOnly": True,
        "licenseStatus": "reference_only",
        "rateLimit": "disabled-until-approved",
        "enabled": False,
        "hostnames": ["www.wowhead.com"],
        "sourceUrl": "https://www.wowhead.com/news/rss/retail",
    },
    {
        "sourceId": "blizzard-forums",
        "sourceName": "Blizzard Forums",
        "tier": "official",
        "fetchMode": "forum_topics",
        "retailOnly": True,
        "licenseStatus": "approved",
        "rateLimit": "polite:15s-timeout",
        "enabled": True,
        "hostnames": ["us.forums.blizzard.com"],
        "sourceUrl": "https://us.forums.blizzard.com/en/wow/c/in-development",
    },
    {
        "sourceId": "icy-veins",
        "sourceName": "Icy Veins",
        "tier": "trusted_media",
        "fetchMode": "reference_link",
        "retailOnly": True,
        "licenseStatus": "reference_only",
        "rateLimit": "disabled-until-approved",
        "enabled": False,
        "hostnames": ["www.icy-veins.com"],
        "sourceUrl": "https://www.icy-veins.com/wow/news",
    },
]

NEWS_SOURCES_BY_NAME = {source["sourceName"]: source for source in NEWS_SOURCE_REGISTRY}
NEWS_SOURCES_BY_ID = {source["sourceId"]: source for source in NEWS_SOURCE_REGISTRY}

FEED_SOURCES = [
    {
        "type": "blizzard_html",
        "sourceId": "blizzard",
        "sourceName": "Blizzard News",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news",
        "sourceNote": "Blizzard official World of Warcraft news listing.",
        "baseImportance": 86,
    },
    {
        "type": "blizzard_forum",
        "sourceId": "blizzard-forums",
        "sourceName": "Blizzard Forums",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "sourceUrl": "https://us.forums.blizzard.com/en/wow/c/in-development",
        "sourceNote": "Blizzard official PTR and development forum topic list.",
        "baseImportance": 84,
    },
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def public_row_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def bool_env(name, default=False):
    value = str(os.environ.get(name, "")).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def websim_gear_build_worker_limit():
    return max(1, int_env("WOW_WEB_GEAR_MAX_WORKERS", WEB_GEAR_BUILD_DEFAULT_WORKERS))


def reset_websim_gear_build_limiter_for_tests():
    global _WEB_GEAR_BUILD_LIMITER, _WEB_GEAR_BUILD_LIMITER_LIMIT
    with _WEB_GEAR_BUILD_LIMITER_LOCK:
        _WEB_GEAR_BUILD_LIMITER = None
        _WEB_GEAR_BUILD_LIMITER_LIMIT = None


def websim_gear_build_limiter():
    global _WEB_GEAR_BUILD_LIMITER, _WEB_GEAR_BUILD_LIMITER_LIMIT
    limit = websim_gear_build_worker_limit()
    with _WEB_GEAR_BUILD_LIMITER_LOCK:
        if _WEB_GEAR_BUILD_LIMITER is None or _WEB_GEAR_BUILD_LIMITER_LIMIT != limit:
            _WEB_GEAR_BUILD_LIMITER = threading.BoundedSemaphore(limit)
            _WEB_GEAR_BUILD_LIMITER_LIMIT = limit
        return _WEB_GEAR_BUILD_LIMITER


def run_websim_gear_build(build_payload):
    with websim_gear_build_limiter():
        return build_payload()


def run_websim_gear_build_with_queue(build_payload):
    """Run a bounded gear build and report only its time spent waiting for capacity."""

    queued_at = time.perf_counter()
    with websim_gear_build_limiter():
        queue_ms = (time.perf_counter() - queued_at) * 1000
        return build_payload(), round(max(0.0, queue_ms), 3)


@contextmanager
def db_connection():
    config = database_config_from_env()
    if sqlite_runtime_disabled():
        raise RuntimeError("SQLite runtime is disabled; use PostgreSQL runtime stores or explicit migration tooling")
    if config.backend != "sqlite":
        if not postgres_runtime_enabled(config):
            raise RuntimeError("PostgreSQL runtime is not enabled in this phase")
        sqlite_path = DB_PATH
    else:
        sqlite_path = config.sqlite_path
    with sqlite_connection(sqlite_path) as conn:
        yield conn


def postgres_personal_runtime_enabled(config=None):
    return postgres_runtime_enabled(config)


def personal_data_store():
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        return None
    try:
        from .postgres_personal_store import PostgresPersonalStore
    except ImportError:
        from postgres_personal_store import PostgresPersonalStore
    return PostgresPersonalStore(lambda: connect_postgres(config.database_url))


def analytics_data_store():
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        return None
    try:
        from .postgres_analytics_store import PostgresAnalyticsStore
    except ImportError:
        from postgres_analytics_store import PostgresAnalyticsStore
    return PostgresAnalyticsStore(lambda: connect_postgres(config.database_url))


def content_data_store():
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        return None
    try:
        from .postgres_content_store import PostgresContentStore
    except ImportError:
        from postgres_content_store import PostgresContentStore
    return PostgresContentStore(lambda: connect_postgres(config.database_url))


def cache_data_store():
    global _GEAR_AUTHORITY_CACHE_KEY, _GEAR_AUTHORITY_CACHE
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        with _GEAR_AUTHORITY_CACHE_LOCK:
            _GEAR_AUTHORITY_CACHE_KEY = None
            _GEAR_AUTHORITY_CACHE = None
        return None
    try:
        from .postgres_cache_store import AuthorityContextCache, PostgresCacheStore
    except ImportError:
        from postgres_cache_store import AuthorityContextCache, PostgresCacheStore
    cache_key = hashlib.sha256(config.database_url.encode("utf-8")).hexdigest()
    with _GEAR_AUTHORITY_CACHE_LOCK:
        if _GEAR_AUTHORITY_CACHE_KEY != cache_key or _GEAR_AUTHORITY_CACHE is None:
            _GEAR_AUTHORITY_CACHE_KEY = cache_key
            _GEAR_AUTHORITY_CACHE = AuthorityContextCache(
                max_entries=32,
                max_bytes=4 * 1024 * 1024,
            )
        authority_cache = _GEAR_AUTHORITY_CACHE
    return PostgresCacheStore(
        lambda: connect_postgres(config.database_url),
        gear_authority_context_cache=authority_cache,
    )


def ops_data_store():
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        return None
    try:
        from .postgres_ops_store import PostgresOpsStore
    except ImportError:
        from postgres_ops_store import PostgresOpsStore
    return PostgresOpsStore(lambda: connect_postgres(config.database_url))


def gear_stat_snapshot_data_store():
    config = database_config_from_env()
    if not postgres_personal_runtime_enabled(config):
        return None
    try:
        from .gear_stat_snapshot_store import GearStatSnapshotStore
    except ImportError:
        from gear_stat_snapshot_store import GearStatSnapshotStore
    return GearStatSnapshotStore(lambda: connect_postgres(config.database_url))


def init_db():
    with db_connection() as conn:
        ensure_schema_migrations(conn)
        if all_schema_migrations_recorded(conn):
            return
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                channel TEXT NOT NULL,
                category TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                importance INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                source_note TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        ensure_article_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_sources (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                tier TEXT NOT NULL,
                fetch_mode TEXT NOT NULL,
                retail_only INTEGER NOT NULL,
                license_status TEXT NOT NULL,
                rate_limit TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                hostnames_json TEXT NOT NULL,
                source_url TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_raw_articles (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                original_title TEXT NOT NULL,
                original_summary TEXT NOT NULL,
                original_body TEXT NOT NULL,
                body_blocks_json TEXT NOT NULL,
                published_at TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                fetch_error TEXT NOT NULL,
                license_status TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                canonical_topic_id TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_article_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL,
                canonical_topic_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                evidence_url TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                conflict_reason TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_discovery_queue (
                id TEXT PRIMARY KEY,
                canonical_topic_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                source_url TEXT NOT NULL,
                original_title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                processed_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_news_discovery_queue_status_updated
            ON news_discovery_queue (status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_news_discovery_queue_source_status
            ON news_discovery_queue (source_id, status)
            """
        )
        seed_news_sources(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_refresh_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                refresh_mode TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,
                accepted_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wechat_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT NOT NULL UNIQUE,
                unionid TEXT NOT NULL DEFAULT '',
                nickname TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulator_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}',
                queued_at TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT NOT NULL DEFAULT '',
                attempt INTEGER NOT NULL DEFAULT 0,
                locked_by TEXT NOT NULL DEFAULT '',
                heartbeat_at TEXT NOT NULL DEFAULT '',
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id)
            )
            """
        )
        ensure_simulator_task_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_build_templates (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                client_id TEXT NOT NULL DEFAULT '',
                template_type TEXT NOT NULL,
                title TEXT NOT NULL,
                class_key TEXT NOT NULL DEFAULT '',
                class_name TEXT NOT NULL DEFAULT '',
                spec_key TEXT NOT NULL DEFAULT '',
                spec_name TEXT NOT NULL DEFAULT '',
                hero_key TEXT NOT NULL DEFAULT '',
                hero_label TEXT NOT NULL DEFAULT '',
                scenario_key TEXT NOT NULL DEFAULT '',
                scenario_title TEXT NOT NULL DEFAULT '',
                raw_string TEXT NOT NULL,
                simc_lines_json TEXT NOT NULL,
                status TEXT NOT NULL,
                status_label TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_build_templates_owner_raw
            ON user_build_templates (user_id, template_type, raw_string)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_build_templates_owner_updated
            ON user_build_templates (user_id, updated_at DESC)
            """
        )
        ensure_auth_token_columns(conn)
        ensure_chickenbro_tables(conn)
        ensure_websim_tables(conn)
        ensure_analytics_tables(conn)
        ensure_admin_gate_tables(conn)
        prune_expired_auth_tokens(conn)
        record_schema_migrations(conn)


def ensure_schema_migrations(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def all_schema_migrations_recorded(conn):
    migration_ids = {migration_id for migration_id, _description in SCHEMA_MIGRATIONS}
    if not migration_ids:
        return False
    try:
        recorded_ids = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM schema_migrations"
            ).fetchall()
        }
    except sqlite3.OperationalError:
        return False
    return migration_ids.issubset(recorded_ids)


def record_schema_migrations(conn):
    now = utc_now()
    for migration_id, description in SCHEMA_MIGRATIONS:
        conn.execute(
            """
            INSERT INTO schema_migrations (id, description, applied_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET description = excluded.description
            """,
            (migration_id, description, now),
        )


def ensure_admin_gate_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_gate_diagnoses (
            id TEXT PRIMARY KEY,
            target_domain TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            gap_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT '',
            target_fingerprint TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_admin_gate_diagnoses_target
        ON admin_gate_diagnoses (target_domain, target_type, target_id, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_audit_logs (
            id TEXT PRIMARY KEY,
            actor TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            target_type TEXT NOT NULL DEFAULT '',
            target_id TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ops_audit_logs_target
        ON ops_audit_logs (target_type, target_id, created_at DESC)
        """
    )


def ensure_chickenbro_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chickenbro_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            product_phase TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES wechat_users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chickenbro_sessions_owner_updated
        ON chickenbro_sessions (user_id, updated_at DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chickenbro_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            agent_job_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES chickenbro_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES wechat_users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chickenbro_messages_session_created
        ON chickenbro_messages (session_id, created_at)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_jobs (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            request_json TEXT NOT NULL,
            bounded_context_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '',
            finished_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES wechat_users(id) ON DELETE CASCADE,
            FOREIGN KEY(session_id) REFERENCES chickenbro_sessions(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_jobs_owner_status_updated
        ON agent_jobs (user_id, status, updated_at DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chickenbro_spec_profiles (
            profile_key TEXT PRIMARY KEY,
            product_phase TEXT NOT NULL,
            season_slug TEXT NOT NULL,
            patch_version TEXT NOT NULL,
            region TEXT NOT NULL,
            class_key TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            role TEXT NOT NULL,
            scenario_key TEXT NOT NULL,
            status TEXT NOT NULL,
            source_status TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            published_at TEXT NOT NULL,
            stale_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chickenbro_profiles_lookup
        ON chickenbro_spec_profiles (
            product_phase, class_key, spec_key, scenario_key, region, status, updated_at DESC
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chickenbro_user_profiles (
            user_id INTEGER PRIMARY KEY,
            profile_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES wechat_users(id) ON DELETE CASCADE
        )
        """
    )


def ensure_article_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(news_articles)").fetchall()}
    text_columns = (
        "body_zh",
        "original_title",
        "original_summary",
        "original_body",
        "translation_status",
        "content_status",
        "tag_items_json",
        "blocked_reason",
        "source_id",
        "source_tier",
        "license_status",
        "verification_status",
        "source_badges_json",
        "body_blocks_zh_json",
        "canonical_topic_id",
        "reading_meta_json",
        "translation_fidelity",
    )
    for name in text_columns:
        if name not in columns:
            conn.execute(f"ALTER TABLE news_articles ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")


def ensure_simulator_task_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(simulator_tasks)").fetchall()}
    if "summary_json" not in columns:
        conn.execute("ALTER TABLE simulator_tasks ADD COLUMN summary_json TEXT NOT NULL DEFAULT '{}'")
        backfill_simulator_task_summaries(conn)
        columns.add("summary_json")
    worker_ready_columns = {
        "queued_at": "TEXT NOT NULL DEFAULT ''",
        "started_at": "TEXT NOT NULL DEFAULT ''",
        "finished_at": "TEXT NOT NULL DEFAULT ''",
        "attempt": "INTEGER NOT NULL DEFAULT 0",
        "locked_by": "TEXT NOT NULL DEFAULT ''",
        "heartbeat_at": "TEXT NOT NULL DEFAULT ''",
        "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
        "last_error": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in worker_ready_columns.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE simulator_tasks ADD COLUMN {name} {definition}")
            columns.add(name)
    conn.execute("UPDATE simulator_tasks SET queued_at = created_at WHERE queued_at = ''")


def seed_news_sources(conn):
    updated_at = utc_now()
    for source in NEWS_SOURCE_REGISTRY:
        conn.execute(
            """
            INSERT INTO news_sources (
                source_id, source_name, tier, fetch_mode, retail_only, license_status,
                rate_limit, enabled, hostnames_json, source_url, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                source_name=excluded.source_name,
                tier=excluded.tier,
                fetch_mode=excluded.fetch_mode,
                retail_only=excluded.retail_only,
                license_status=excluded.license_status,
                rate_limit=excluded.rate_limit,
                enabled=excluded.enabled,
                hostnames_json=excluded.hostnames_json,
                source_url=excluded.source_url,
                updated_at=excluded.updated_at
            """,
            (
                source["sourceId"],
                source["sourceName"],
                source["tier"],
                source["fetchMode"],
                1 if source.get("retailOnly") else 0,
                source["licenseStatus"],
                source["rateLimit"],
                1 if source.get("enabled") else 0,
                json.dumps(source.get("hostnames", []), ensure_ascii=False),
                source.get("sourceUrl", ""),
                updated_at,
            ),
        )


def ensure_auth_token_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(auth_tokens)").fetchall()}
    if "expires_at" not in columns:
        conn.execute("ALTER TABLE auth_tokens ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE auth_tokens SET expires_at = ? WHERE expires_at = ''",
        (auth_token_expires_at(),),
    )


def auth_token_expires_at():
    return (datetime.now(timezone.utc) + timedelta(seconds=AUTH_TOKEN_TTL_SECONDS)).isoformat(timespec="seconds")


def auth_expires_at_ms(expires_at):
    try:
        return int(datetime.fromisoformat(expires_at).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def prune_expired_auth_tokens(conn):
    conn.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (utc_now(),))


def load_seed_articles():
    with SEED_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def hostname_for(url):
    parsed = urlparse(url or "")
    return parsed.hostname or ""


def source_config_for_article(article):
    source_id = article.get("sourceId", "")
    if source_id and source_id in NEWS_SOURCES_BY_ID:
        return NEWS_SOURCES_BY_ID[source_id]
    return NEWS_SOURCES_BY_NAME.get(article.get("sourceName", ""), {})


def canonical_topic_id(article):
    url = article.get("sourceUrl", "")
    match = re.search(r"/(?:news|article)/(\d+)", url)
    if match:
        return f"news:{match.group(1)}"
    key = canonical_article_key(article)
    return re.sub(r"[^a-zA-Z0-9:_-]+", "-", key).strip("-")


def translated_body_blocks_for_article(article):
    return normalize_body_blocks(article.get("bodyBlocksZh"), article.get("bodyZh", ""))


def is_source_translation(article):
    return article.get("translationFidelity") == "source_translation"


def reading_meta_for_article(article):
    blocks = translated_body_blocks_for_article(article)
    text = body_blocks_text(blocks) or article.get("bodyZh", "")
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text or ""))
    estimated_minutes = max(1, round(cjk_chars / 450)) if cjk_chars else 1
    return {
        "bodyBlockCount": len(blocks),
        "estimatedReadingMinutes": estimated_minutes,
    }


def publication_block(article, reason, verification_status=None):
    blocked = dict(article)
    blocked.update(
        {
            "contentStatus": "blocked",
            "blockedReason": reason,
            "verificationStatus": verification_status or reason,
        }
    )
    return blocked


def translation_block(article, reason):
    blocked = dict(article)
    blocked.update(
        {
            "contentStatus": "blocked",
            "translationStatus": "blocked",
            "blockedReason": reason,
        }
    )
    return blocked


def apply_publication_gates(article):
    reviewed = dict(article)
    source = source_config_for_article(reviewed)
    source_id = reviewed.get("sourceId") or source.get("sourceId") or reviewed.get("sourceName", "").lower().replace(" ", "-")
    source_tier = reviewed.get("sourceTier") or source.get("tier", "")
    license_status = reviewed.get("licenseStatus") or source.get("licenseStatus", "")
    canonical_id = reviewed.get("canonicalTopicId") or canonical_topic_id(reviewed)
    translation_fidelity = reviewed.get("translationFidelity", "")
    body_blocks_zh = translated_body_blocks_for_article(reviewed)
    if body_blocks_zh and not reviewed.get("bodyZh"):
        reviewed["bodyZh"] = body_blocks_text(body_blocks_zh)
    source_badges = list(reviewed.get("sourceBadges") or [])
    if source_tier == "official" and "官方已核验" not in source_badges:
        source_badges.append("官方已核验")
    if reviewed.get("translationStatus") == "llm" and translation_fidelity == "source_translation" and "全文翻译" not in source_badges:
        source_badges.append("全文翻译")

    reviewed.update(
        {
            "sourceId": source_id,
            "sourceTier": source_tier,
            "licenseStatus": license_status,
            "canonicalTopicId": canonical_id,
            "sourceBadges": source_badges,
            "bodyBlocksZh": body_blocks_zh,
            "readingMeta": reading_meta_for_article({**reviewed, "bodyBlocksZh": body_blocks_zh}),
            "translationFidelity": translation_fidelity,
        }
    )

    if reviewed.get("contentStatus") != "ready":
        if not reviewed.get("verificationStatus"):
            reviewed["verificationStatus"] = reviewed.get("blockedReason") or "translation_blocked"
        return reviewed

    if license_status != "approved":
        return publication_block(reviewed, "license_blocked", "license_blocked")

    conflict_reason = reviewed.get("conflictReason") or reviewed.get("sourceConflictReason")
    if conflict_reason:
        reviewed["conflictReason"] = conflict_reason
        return publication_block(reviewed, "source_conflict", "conflict_blocked")

    if source_tier == "official":
        reviewed["verificationStatus"] = "official_verified"
    elif reviewed.get("verificationStatus") != "official_verified":
        return publication_block(reviewed, "official_not_found", "unverified_blocked")

    if reviewed.get("translationStatus") != "llm":
        return publication_block(reviewed, "invalid_translation", reviewed.get("verificationStatus"))

    if not is_source_translation(reviewed):
        return publication_block(reviewed, "not_source_translation", reviewed.get("verificationStatus"))

    source_issue = source_body_quality_issue(reviewed)
    if source_issue:
        return publication_block(reviewed, source_issue, reviewed.get("verificationStatus"))

    if not body_blocks_zh or not reviewed.get("bodyZh") or reviewed.get("bodyZh") == reviewed.get("summary"):
        return publication_block(reviewed, "summary_only_body", reviewed.get("verificationStatus"))

    reviewed["contentStatus"] = "ready"
    reviewed["blockedReason"] = ""
    return reviewed


def verification_counts(articles):
    counts = {}
    for article in articles:
        key = article.get("verificationStatus") or article.get("blockedReason") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def persist_news_raw_article(conn, article, fetched_at):
    blocks = normalize_body_blocks(article.get("bodyBlocks"))
    conn.execute(
        """
        INSERT INTO news_raw_articles (
            id, source_id, source_name, source_tier, canonical_url,
            original_title, original_summary, original_body, body_blocks_json,
            published_at, fetched_at, fetch_error, license_status,
            verification_status, canonical_topic_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source_id=excluded.source_id,
            source_name=excluded.source_name,
            source_tier=excluded.source_tier,
            canonical_url=excluded.canonical_url,
            original_title=excluded.original_title,
            original_summary=excluded.original_summary,
            original_body=excluded.original_body,
            body_blocks_json=excluded.body_blocks_json,
            published_at=excluded.published_at,
            fetched_at=excluded.fetched_at,
            fetch_error=excluded.fetch_error,
            license_status=excluded.license_status,
            verification_status=excluded.verification_status,
            canonical_topic_id=excluded.canonical_topic_id
        """,
        (
            article.get("id", ""),
            article.get("sourceId", ""),
            article.get("sourceName", ""),
            article.get("sourceTier", ""),
            article.get("sourceUrl", ""),
            article.get("originalTitle", ""),
            article.get("originalSummary", ""),
            article.get("originalBody", ""),
            json.dumps(blocks, ensure_ascii=False),
            article.get("publishedAt", ""),
            fetched_at,
            article.get("detailError", "") or article.get("fetchError", ""),
            article.get("licenseStatus", ""),
            article.get("verificationStatus", ""),
            article.get("canonicalTopicId", ""),
        ),
    )


def persist_news_evidence(conn, article, checked_at):
    conn.execute(
        """
        INSERT INTO news_article_evidence (
            article_id, canonical_topic_id, source_id, source_name, source_tier,
            evidence_url, verification_status, conflict_reason, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article.get("id", ""),
            article.get("canonicalTopicId", ""),
            article.get("sourceId", ""),
            article.get("sourceName", ""),
            article.get("sourceTier", ""),
            article.get("sourceUrl", ""),
            article.get("verificationStatus", ""),
            article.get("conflictReason", ""),
            checked_at,
        ),
    )


def is_valid_article(article):
    if article.get("channel") not in {channel["title"] for channel in CHANNELS}:
        return False
    source_name = article.get("sourceName")
    if hostname_for(article.get("sourceUrl")) not in TRUSTED_SOURCES.get(source_name, set()):
        return False
    if article.get("contentStatus") != "ready":
        return False
    if article.get("licenseStatus") != "approved":
        return False
    if article.get("verificationStatus") != "official_verified":
        return False
    if article.get("translationStatus") != "llm":
        return False
    if not is_source_translation(article):
        return False
    if not article.get("tagItems"):
        return False
    if not article.get("bodyBlocksZh"):
        return False
    if not article.get("bodyZh") or article.get("bodyZh") == article.get("summary"):
        return False
    required = ["id", "title", "summary", "sourceName", "sourceUrl", "publishedAt", "sourceNote", "originalTitle"]
    return all(article.get(key) for key in required)


def normalize_refresh_mode(value):
    return value if value in PUBLIC_REFRESH_MODES else None


RETRYABLE_NEWS_BLOCK_REASONS = {
    "llm_not_configured",
    "invalid_llm_translation",
    "translation_blocked",
    "invalid_translation",
    "not_source_translation",
    "source_body_missing",
    "summary_only_body",
}


def collector_article_limit():
    return collector_discovery_limit()


def collector_discovery_limit():
    legacy_limit = int_env("WOW_NEWS_MAX_COLLECTED_ARTICLES", 10)
    configured_limit = int_env("WOW_NEWS_DISCOVERY_LIMIT", legacy_limit)
    return max(10, configured_limit)


def collector_process_limit():
    return max(1, min(5, int_env("WOW_NEWS_PROCESS_LIMIT", 5)))


def news_retry_max_attempts():
    return max(1, int_env("WOW_NEWS_RETRY_MAX_ATTEMPTS", 3))


def parse_iso_datetime(value):
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def timestamp_expired(value, now=None):
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return False
    current = parse_iso_datetime(now or utc_now()) or datetime.now(timezone.utc)
    return parsed <= current


def queue_payload_for_article(article):
    queued = dict(article)
    queued["canonicalTopicId"] = queued.get("canonicalTopicId") or canonical_topic_id(queued)
    return queued


def enqueue_discovered_articles(conn, articles, discovered_at):
    for article in articles:
        queued = queue_payload_for_article(article)
        conn.execute(
            """
            INSERT INTO news_discovery_queue (
                id, canonical_topic_id, source_id, source_name, source_tier,
                source_url, original_title, published_at, status, attempts,
                last_error, payload_json, discovered_at, updated_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, '', ?, ?, ?, '')
            ON CONFLICT(id) DO UPDATE SET
                canonical_topic_id=excluded.canonical_topic_id,
                source_id=excluded.source_id,
                source_name=excluded.source_name,
                source_tier=excluded.source_tier,
                source_url=excluded.source_url,
                original_title=excluded.original_title,
                published_at=excluded.published_at,
                status=CASE
                    WHEN news_discovery_queue.status = 'published'
                         AND EXISTS (
                             SELECT 1 FROM news_articles
                             WHERE news_articles.id = excluded.id
                               AND news_articles.content_status = 'ready'
                         )
                    THEN news_discovery_queue.status
                    ELSE 'queued'
                END,
                last_error=CASE
                    WHEN news_discovery_queue.status = 'published'
                         AND EXISTS (
                             SELECT 1 FROM news_articles
                             WHERE news_articles.id = excluded.id
                               AND news_articles.content_status = 'ready'
                         )
                    THEN news_discovery_queue.last_error
                    ELSE ''
                END,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                queued.get("id", ""),
                queued.get("canonicalTopicId", ""),
                queued.get("sourceId", ""),
                queued.get("sourceName", ""),
                queued.get("sourceTier", ""),
                queued.get("sourceUrl", ""),
                queued.get("originalTitle") or queued.get("title", ""),
                queued.get("publishedAt", ""),
                json.dumps(queued, ensure_ascii=False),
                discovered_at,
                discovered_at,
            ),
        )


def mark_queue_article(conn, article, status, error="", processed_at=None, increment_attempts=True):
    now = processed_at or utc_now()
    attempts_sql = "attempts + 1" if increment_attempts else "attempts"
    conn.execute(
        f"""
        UPDATE news_discovery_queue
        SET status = ?, last_error = ?, processed_at = ?, updated_at = ?,
            attempts = {attempts_sql}
        WHERE id = ?
        """,
        (status, error or "", now, now, article.get("id", "")),
    )


def load_queued_articles(conn, limit):
    rows = conn.execute(
        """
        SELECT payload_json, attempts, last_error
        FROM news_discovery_queue
        WHERE status IN ('queued', 'retryable')
        ORDER BY published_at DESC, rowid ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    articles = []
    for row in rows:
        article = safe_json_loads(row[0], {}, "news discovery queue payload")
        if article:
            article["_queueAttempts"] = int(row[1] or 0)
            article["_queueLastError"] = row[2] or ""
            articles.append(article)
    return articles


def queue_retry_limit_error(article):
    try:
        attempts = int(article.get("_queueAttempts") or 0)
    except (TypeError, ValueError):
        attempts = 0
    if attempts < news_retry_max_attempts():
        return ""
    reason = (
        str(article.get("_queueLastError") or "").strip()
        or str(article.get("blockedReason") or "").strip()
        or str(article.get("verificationStatus") or "").strip()
        or "retryable"
    )
    return reason if reason.startswith("retry_limit_exceeded:") else f"retry_limit_exceeded:{reason}"


def queue_status_for_reviewed_article(article):
    if is_valid_article(article):
        return "published", ""
    reason = article.get("blockedReason") or article.get("verificationStatus") or "invalid_article"
    if article.get("sourceTier") == "official" and reason in RETRYABLE_NEWS_BLOCK_REASONS:
        try:
            attempts = int(article.get("_queueAttempts") or 0)
        except (TypeError, ValueError):
            attempts = 0
        if attempts + 1 >= news_retry_max_attempts():
            return "blocked", f"retry_limit_exceeded:{reason}"
        return "retryable", reason
    return "blocked", reason


def reference_only_audit_article(article):
    audited = dict(article)
    audited.update(
        {
            "contentStatus": "ready",
            "translationStatus": "reference_only",
            "translationFidelity": "",
            "bodyZh": article.get("summary", ""),
            "bodyBlocksZh": [{"type": "paragraph", "text": article.get("summary", "")}],
        }
    )
    return audited


def should_request_public_translation(article):
    source = source_config_for_article(article)
    license_status = article.get("licenseStatus") or source.get("licenseStatus", "")
    return bool(article.get("requiresLlmTranslation")) and license_status == "approved"


def queue_summary(conn, collector_errors=None):
    status_counts = {
        row[0]: row[1]
        for row in conn.execute(
            """
            SELECT status, COUNT(*)
            FROM news_discovery_queue
            GROUP BY status
            """
        ).fetchall()
    }
    coverage = {}
    rows = conn.execute(
        """
        SELECT source_id, source_name, source_tier, status, COUNT(*)
        FROM news_discovery_queue
        GROUP BY source_id, source_name, source_tier, status
        """
    ).fetchall()
    for source_id, source_name, source_tier, status, count in rows:
        key = source_id or source_name
        item = coverage.setdefault(
            key,
            {
                "sourceName": source_name,
                "sourceTier": source_tier,
                "discovered": 0,
                "queued": 0,
                "processed": 0,
                "published": 0,
                "blocked": 0,
                "retryable": 0,
                "errors": 0,
            },
        )
        item["discovered"] += count
        if status in item:
            item[status] += count
        if status in {"published", "blocked", "retryable"}:
            item["processed"] += count

    for error in collector_errors or []:
        source_name = error.get("sourceName", "")
        source = NEWS_SOURCES_BY_NAME.get(source_name, {})
        key = source.get("sourceId") or source_name or "unknown"
        item = coverage.setdefault(
            key,
            {
                "sourceName": source_name,
                "sourceTier": source.get("tier", ""),
                "discovered": 0,
                "queued": 0,
                "processed": 0,
                "published": 0,
                "blocked": 0,
                "retryable": 0,
                "errors": 0,
            },
        )
        item["errors"] += 1

    oldest = conn.execute(
        """
        SELECT MIN(discovered_at)
        FROM news_discovery_queue
        WHERE status IN ('queued', 'retryable')
        """
    ).fetchone()[0]
    oldest_age = 0
    oldest_dt = parse_iso_datetime(oldest)
    if oldest_dt:
        oldest_age = max(0, int((datetime.now(timezone.utc) - oldest_dt).total_seconds()))

    return {
        "queuedCount": int(status_counts.get("queued", 0) or 0),
        "retryableCount": int(status_counts.get("retryable", 0) or 0),
        "publishedQueueCount": int(status_counts.get("published", 0) or 0),
        "blockedQueueCount": int(status_counts.get("blocked", 0) or 0),
        "oldestBacklogAge": oldest_age,
        "sourceCoverage": coverage,
    }


def blocked_article_entry(reviewed_article):
    return {
        "id": reviewed_article.get("id", ""),
        "title": reviewed_article.get("originalTitle") or reviewed_article.get("title", ""),
        "sourceName": reviewed_article.get("sourceName", ""),
        "reason": reviewed_article.get("blockedReason") or "invalid_article",
        "translationStatus": reviewed_article.get("translationStatus", ""),
        "contentStatus": reviewed_article.get("contentStatus", ""),
        "verificationStatus": reviewed_article.get("verificationStatus", ""),
        "licenseStatus": reviewed_article.get("licenseStatus", ""),
        "sourceTier": reviewed_article.get("sourceTier", ""),
    }


def compact_public_text(value):
    return re.sub(r"[\W_]+", "", re.sub(r"^中文正文\s*[:：]\s*", "", str(value or "").strip()).lower(), flags=re.UNICODE)


def public_body_quality_issue(article):
    original_body = article.get("originalBody", "")
    original_summary = article.get("originalSummary", "") or article.get("summary", "")
    if original_body:
        source_probe = {
            **article,
            "bodyBlocks": [{"type": "paragraph", "text": original_body}],
            "originalSummary": original_summary,
        }
        source_issue = source_body_quality_issue(source_probe)
        if source_issue:
            return source_issue

    body_blocks = translated_body_blocks_for_article(article)
    body_text = body_blocks_text(body_blocks) or article.get("bodyZh", "")
    body_key = compact_public_text(body_text)
    summary_key = compact_public_text(article.get("summary", ""))
    if not body_blocks or not body_key:
        return "summary_only_body"
    if summary_key and body_key == summary_key:
        return "summary_only_body"
    if len(body_blocks) == 1 and re.search(r"(?:…|\.{3}|．．．)$", str(body_text or "").strip()):
        return "summary_only_body"
    return ""


def article_from_public_row(row):
    return {
        "id": row[0],
        "title": row[1],
        "summary": row[2],
        "channel": row[3],
        "category": row[4],
        "tags": safe_json_loads(row[5], [], "news article tags"),
        "importance": row[6],
        "sourceName": row[7],
        "sourceUrl": row[8],
        "publishedAt": row[9],
        "sourceNote": row[10],
        "bodyZh": row[11],
        "originalTitle": row[12],
        "originalSummary": row[13],
        "originalBody": row[14],
        "translationStatus": row[15],
        "contentStatus": row[16],
        "tagItems": safe_json_loads(row[17], [], "news article tag items"),
        "blockedReason": row[18],
        "sourceId": row[19],
        "sourceTier": row[20],
        "licenseStatus": row[21],
        "verificationStatus": row[22],
        "sourceBadges": safe_json_loads(row[23], [], "news article source badges"),
        "bodyBlocksZh": safe_json_loads(row[24], [], "news article translated body blocks"),
        "canonicalTopicId": row[25],
        "readingMeta": safe_json_loads(row[26], {}, "news article reading meta"),
        "translationFidelity": row[27],
    }


def audit_existing_public_articles(conn):
    rows = conn.execute(
        """
        SELECT id, title, summary, channel, category, tags_json, importance,
               source_name, source_url, published_at, source_note,
               body_zh, original_title, original_summary, original_body,
               translation_status, content_status, tag_items_json, blocked_reason,
               source_id, source_tier, license_status, verification_status,
               source_badges_json, body_blocks_zh_json, canonical_topic_id,
               reading_meta_json, translation_fidelity
        FROM news_articles
        WHERE content_status = 'ready'
        """
    ).fetchall()
    blocked = []
    delete_ids = []
    queue_updates = []
    for row in rows:
        article = article_from_public_row(row)
        reason = public_body_quality_issue(article)
        if not reason:
            continue
        delete_ids.append(article["id"])
        queue_updates.append((reason, utc_now(), article["id"]))
        blocked.append(blocked_article_entry(translation_block(article, reason)))
    if delete_ids:
        conn.executemany("DELETE FROM news_articles WHERE id = ?", [(article_id,) for article_id in delete_ids])
    if queue_updates:
        conn.executemany(
            """
            UPDATE news_discovery_queue
            SET status = 'retryable', last_error = ?, updated_at = ?
            WHERE id = ? AND status = 'published'
            """,
            queue_updates,
        )
    return blocked


def _bounded_news_process_limit(value):
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return collector_process_limit()


def refresh_articles(
    refresh_mode,
    collector_enabled=None,
    seed_enabled=True,
    queue_enabled=None,
    process_limit_override=None,
):
    store = content_data_store()
    if not store:
        init_db()
    seed_articles = load_seed_articles() if seed_enabled else []
    collected_articles = []
    discovered_articles = []
    duplicate_seed_articles = []
    discovered_collected_count = 0
    skipped_seed_duplicate_count = 0
    collector_errors = []
    collector_limit = collector_discovery_limit()
    process_limit = _bounded_news_process_limit(process_limit_override) if process_limit_override is not None else collector_process_limit()
    should_collect = ENABLE_COLLECTORS if collector_enabled is None else bool(collector_enabled)
    should_process_queue = should_collect if queue_enabled is None else bool(queue_enabled)
    if should_collect and collector_limit > 0:
        collected_articles, collector_errors = collect_feed_articles(FEED_SOURCES, max_articles_per_source=collector_limit)
        discovered_articles = list(collected_articles)
        discovered_collected_count = len(collected_articles)
        seed_by_key = {canonical_article_key(article): article for article in seed_articles}
        collected_keys = set()
        fresh_collected_articles = []
        for article in collected_articles:
            key = canonical_article_key(article)
            collected_keys.add(key)
            if key in seed_by_key and is_source_translation(seed_by_key[key]):
                skipped_seed_duplicate_count += 1
                duplicate_seed_articles.append(article)
                continue
            fresh_collected_articles.append(article)
        collected_articles = fresh_collected_articles
        seed_articles = [article for article in seed_articles if canonical_article_key(article) not in collected_keys or is_source_translation(article)]

    refreshed_at = utc_now()
    if store:
        store.seed_sources(NEWS_SOURCE_REGISTRY, refreshed_at)
        if should_collect and discovered_collected_count:
            store.enqueue_discovered_articles(discovered_articles, refreshed_at)
            for article in duplicate_seed_articles:
                store.mark_queue_article(article, "blocked", "duplicate_seed_source_translation", refreshed_at, increment_attempts=False)
        queued_articles = store.load_queued_articles(process_limit) if should_process_queue else []
    else:
        with db_connection() as conn:
            if should_collect and discovered_collected_count:
                enqueue_discovered_articles(conn, discovered_articles, refreshed_at)
                for article in duplicate_seed_articles:
                    mark_queue_article(conn, article, "blocked", "duplicate_seed_source_translation", refreshed_at, increment_attempts=False)
            queued_articles = load_queued_articles(conn, process_limit) if should_process_queue else []

    accepted = []
    blocked = []
    processed = []
    rejected = 0
    for article in merge_articles(seed_articles, queued_articles):
        retry_limit_error = queue_retry_limit_error(article) if should_process_queue else ""
        if retry_limit_error:
            localized_article = dict(
                article,
                contentStatus="blocked",
                blockedReason=retry_limit_error,
                verificationStatus=retry_limit_error,
                _queueRetryLimitPreempted=True,
            )
        elif article.get("contentStatus") == "ready":
            localized_article = article
        elif should_request_public_translation(article):
            source_issue = source_body_quality_issue(article)
            if source_issue:
                localized_article = translation_block(article, source_issue)
            else:
                localized_article = localize_article(article, require_llm=True)
        else:
            localized_article = reference_only_audit_article(article)
        reviewed_article = apply_publication_gates(localized_article)
        processed.append(reviewed_article)
        if is_valid_article(reviewed_article):
            accepted.append(reviewed_article)
        else:
            blocked.append(blocked_article_entry(reviewed_article))
            rejected += 1

    accepted_ids = [article["id"] for article in accepted]
    translation_issues = visible_translation_issues(accepted)
    counts = verification_counts(processed)
    conflict_articles = [article for article in blocked if article.get("reason") == "source_conflict"]
    source_fetch_errors = [
        {
            "id": article.get("id", ""),
            "sourceName": article.get("sourceName", ""),
            "sourceUrl": article.get("sourceUrl", ""),
            "error": article.get("detailError") or article.get("fetchError", ""),
        }
        for article in processed
        if article.get("detailError") or article.get("fetchError")
    ]
    if store:
        for article in processed:
            store.persist_news_raw_article(article, refreshed_at)
            store.persist_news_evidence(article, refreshed_at)
            if should_process_queue and article.get("id"):
                queue_status, queue_error = queue_status_for_reviewed_article(article)
                store.mark_queue_article(
                    article,
                    queue_status,
                    queue_error,
                    refreshed_at,
                    increment_attempts=not article.get("_queueRetryLimitPreempted"),
                )
        for article in accepted:
            store.save_public_article(article, refreshed_at)
        if accepted_ids and not should_collect and seed_enabled:
            store.delete_public_articles_not_in(accepted_ids)
        audited_blocked = store.audit_existing_public_articles(public_body_quality_issue) if seed_enabled else []
        if audited_blocked:
            blocked.extend(audited_blocked)
            rejected += len(audited_blocked)
        summary = store.queue_summary(collector_errors)
        store.record_refresh_run(
            refresh_mode,
            refreshed_at,
            len(accepted),
            rejected,
            {
                "seedCount": len(seed_articles),
                "collectorEnabled": should_collect,
                "seedEnabled": bool(seed_enabled),
                "queueEnabled": bool(should_process_queue),
                "collectorLimit": collector_limit,
                "discoveryLimit": collector_limit,
                "processLimit": process_limit,
                "discoveredCount": discovered_collected_count,
                "queuedCount": summary["queuedCount"],
                "processedCount": len(processed),
                "publishedCount": len(accepted),
                "blockedCount": len(blocked),
                "retryableCount": summary["retryableCount"],
                "oldestBacklogAge": summary["oldestBacklogAge"],
                "sourceCoverage": summary["sourceCoverage"],
                "collectedDiscoveredCount": discovered_collected_count,
                "collectedCount": len(collected_articles),
                "collectorDuplicateSeedSkippedCount": skipped_seed_duplicate_count,
                "collectorErrors": collector_errors,
                "sourceFetchErrors": collector_errors + source_fetch_errors,
                "translationIssueCount": len(translation_issues),
                "translationIssues": translation_issues[:20],
                "blockedArticleCount": len(blocked),
                "blockedArticles": blocked[:20],
                "verificationCounts": counts,
                "licenseBlockedCount": counts.get("license_blocked", 0),
                "conflictArticles": conflict_articles[:20],
            },
        )
        return {"refreshMode": refresh_mode, "lastRefreshedAt": refreshed_at}
    with db_connection() as conn:
        for article in processed:
            persist_news_raw_article(conn, article, refreshed_at)
            persist_news_evidence(conn, article, refreshed_at)
            if should_process_queue and article.get("id"):
                queue_status, queue_error = queue_status_for_reviewed_article(article)
                mark_queue_article(
                    conn,
                    article,
                    queue_status,
                    queue_error,
                    refreshed_at,
                    increment_attempts=not article.get("_queueRetryLimitPreempted"),
                )
        for article in accepted:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason,
                    source_id, source_tier, license_status, verification_status,
                    source_badges_json, body_blocks_zh_json, canonical_topic_id,
                    reading_meta_json, translation_fidelity, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    channel=excluded.channel,
                    category=excluded.category,
                    tags_json=excluded.tags_json,
                    importance=excluded.importance,
                    source_name=excluded.source_name,
                    source_url=excluded.source_url,
                    published_at=excluded.published_at,
                    source_note=excluded.source_note,
                    body_zh=excluded.body_zh,
                    original_title=excluded.original_title,
                    original_summary=excluded.original_summary,
                    original_body=excluded.original_body,
                    translation_status=excluded.translation_status,
                    content_status=excluded.content_status,
                    tag_items_json=excluded.tag_items_json,
                    blocked_reason=excluded.blocked_reason,
                    source_id=excluded.source_id,
                    source_tier=excluded.source_tier,
                    license_status=excluded.license_status,
                    verification_status=excluded.verification_status,
                    source_badges_json=excluded.source_badges_json,
                    body_blocks_zh_json=excluded.body_blocks_zh_json,
                    canonical_topic_id=excluded.canonical_topic_id,
                    reading_meta_json=excluded.reading_meta_json,
                    translation_fidelity=excluded.translation_fidelity,
                    updated_at=excluded.updated_at
                """,
                (
                    article["id"],
                    article["title"],
                    article["summary"],
                    article["channel"],
                    article["category"],
                    json.dumps(article.get("tags", []), ensure_ascii=False),
                    int(article.get("importance", 0)),
                    article["sourceName"],
                    article["sourceUrl"],
                    article["publishedAt"],
                    article["sourceNote"],
                    article.get("bodyZh", ""),
                    article.get("originalTitle", ""),
                    article.get("originalSummary", ""),
                    article.get("originalBody", ""),
                    article.get("translationStatus", ""),
                    article.get("contentStatus", ""),
                    json.dumps(article.get("tagItems", []), ensure_ascii=False),
                    article.get("blockedReason", ""),
                    article.get("sourceId", ""),
                    article.get("sourceTier", ""),
                    article.get("licenseStatus", ""),
                    article.get("verificationStatus", ""),
                    json.dumps(article.get("sourceBadges", []), ensure_ascii=False),
                    json.dumps(article.get("bodyBlocksZh", []), ensure_ascii=False),
                    article.get("canonicalTopicId", ""),
                    json.dumps(article.get("readingMeta", {}), ensure_ascii=False),
                    article.get("translationFidelity", ""),
                    refreshed_at,
                ),
            )
        if accepted_ids and not should_collect and seed_enabled:
            placeholders = ",".join("?" for _ in accepted_ids)
            conn.execute(f"DELETE FROM news_articles WHERE id NOT IN ({placeholders})", accepted_ids)
        audited_blocked = audit_existing_public_articles(conn) if seed_enabled else []
        if audited_blocked:
            blocked.extend(audited_blocked)
            rejected += len(audited_blocked)
        summary = queue_summary(conn, collector_errors)
        conn.execute(
            """
            INSERT INTO news_refresh_runs (refresh_mode, refreshed_at, accepted_count, rejected_count, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                refresh_mode,
                refreshed_at,
                len(accepted),
                rejected,
                json.dumps(
                    {
                        "seedCount": len(seed_articles),
                        "collectorEnabled": should_collect,
                        "seedEnabled": bool(seed_enabled),
                        "queueEnabled": bool(should_process_queue),
                        "collectorLimit": collector_limit,
                        "discoveryLimit": collector_limit,
                        "processLimit": process_limit,
                        "discoveredCount": discovered_collected_count,
                        "queuedCount": summary["queuedCount"],
                        "processedCount": len(processed),
                        "publishedCount": len(accepted),
                        "blockedCount": len(blocked),
                        "retryableCount": summary["retryableCount"],
                        "oldestBacklogAge": summary["oldestBacklogAge"],
                        "sourceCoverage": summary["sourceCoverage"],
                        "collectedDiscoveredCount": discovered_collected_count,
                        "collectedCount": len(collected_articles),
                        "collectorDuplicateSeedSkippedCount": skipped_seed_duplicate_count,
                        "collectorErrors": collector_errors,
                        "sourceFetchErrors": collector_errors + source_fetch_errors,
                        "translationIssueCount": len(translation_issues),
                        "translationIssues": translation_issues[:20],
                        "blockedArticleCount": len(blocked),
                        "blockedArticles": blocked[:20],
                        "verificationCounts": counts,
                        "licenseBlockedCount": counts.get("license_blocked", 0),
                        "conflictArticles": conflict_articles[:20],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    return {"refreshMode": refresh_mode, "lastRefreshedAt": refreshed_at}


def latest_refresh_state():
    store = content_data_store()
    if store:
        state = store.latest_refresh_state()
        if state:
            return state
        return refresh_articles("bootstrap", collector_enabled=False)
    if postgres_only_runtime_enabled():
        return {
            "refreshMode": "blocked",
            "lastRefreshedAt": "",
            "dataStatus": "blocked",
            "errors": ["PostgreSQL content store is not available"],
        }
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT refresh_mode, refreshed_at FROM news_refresh_runs
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if not row:
        return refresh_articles("bootstrap", collector_enabled=False)
    return {"refreshMode": row[0], "lastRefreshedAt": row[1]}


def latest_refresh_run_payload():
    store = content_data_store()
    if store:
        payload = store.latest_refresh_run_payload()
        if payload:
            return payload
        latest_refresh_state()
        return latest_refresh_run_payload()
    if postgres_only_runtime_enabled():
        return {
            "refreshMode": "blocked",
            "refreshedAt": "",
            "acceptedCount": 0,
            "rejectedCount": 0,
            "collectorEnabled": False,
            "sourceFetchErrors": [],
            "translationIssueCount": 0,
            "translationIssues": [],
            "blockedArticleCount": 0,
            "blockedArticles": [],
            "dataStatus": "blocked",
            "errors": ["PostgreSQL content store is not available"],
        }
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT refresh_mode, refreshed_at, accepted_count, rejected_count, message
            FROM news_refresh_runs
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if not row:
        latest_refresh_state()
        return latest_refresh_run_payload()

    message = safe_json_loads(row[4], {}, "latest news refresh run message")
    return {
        "refreshMode": row[0],
        "refreshedAt": row[1],
        "acceptedCount": row[2],
        "rejectedCount": row[3],
        "collectorEnabled": bool(message.get("collectorEnabled")),
        "seedEnabled": bool(message.get("seedEnabled", True)),
        "queueEnabled": bool(message.get("queueEnabled", message.get("collectorEnabled"))),
        "collectorLimit": int(message.get("collectorLimit", 0) or 0),
        "discoveryLimit": int(message.get("discoveryLimit", message.get("collectorLimit", 0)) or 0),
        "processLimit": int(message.get("processLimit", 0) or 0),
        "discoveredCount": int(message.get("discoveredCount", message.get("collectedDiscoveredCount", 0)) or 0),
        "queuedCount": int(message.get("queuedCount", 0) or 0),
        "processedCount": int(message.get("processedCount", 0) or 0),
        "publishedCount": int(message.get("publishedCount", message.get("acceptedCount", row[2])) or 0),
        "blockedCount": int(message.get("blockedCount", message.get("blockedArticleCount", 0)) or 0),
        "retryableCount": int(message.get("retryableCount", 0) or 0),
        "oldestBacklogAge": int(message.get("oldestBacklogAge", 0) or 0),
        "sourceCoverage": message.get("sourceCoverage", {}),
        "collectedDiscoveredCount": int(message.get("collectedDiscoveredCount", message.get("collectedCount", 0)) or 0),
        "collectedCount": int(message.get("collectedCount", 0) or 0),
        "collectorDuplicateSeedSkippedCount": int(message.get("collectorDuplicateSeedSkippedCount", 0) or 0),
        "collectorErrors": message.get("collectorErrors", []),
        "sourceFetchErrors": message.get("sourceFetchErrors", message.get("collectorErrors", [])),
        "translationIssueCount": int(message.get("translationIssueCount", 0) or 0),
        "translationIssues": message.get("translationIssues", []),
        "blockedArticleCount": int(message.get("blockedArticleCount", 0) or 0),
        "blockedArticles": message.get("blockedArticles", []),
        "verificationCounts": message.get("verificationCounts", {}),
        "licenseBlockedCount": int(message.get("licenseBlockedCount", 0) or 0),
        "conflictArticles": message.get("conflictArticles", []),
    }


DATA_HEALTH_STATUSES = [
    "verified",
    "partial",
    "stale",
    "blocked",
    "missing_credentials",
    "pending_official_audit",
    "source_reference",
]
ADMIN_GATE_STATUS_LABELS = {
    "verified": "已验证",
    "partial": "部分通过",
    "stale": "已过期",
    "blocked": "已阻断",
    "missing_credentials": "缺少凭据",
    "pending_official_audit": "待官方校验",
    "source_reference": "仅作参考",
    "passed": "已通过",
    "synced": "已同步",
    "ready": "已就绪",
    "complete": "已完成",
    "published": "已发布",
    "open": "未解决",
    "resolved": "已解决",
}
ADMIN_GATE_SEVERITY_LABELS = {
    "ok": "正常",
    "blocks_frontend_publish": "阻断前端发布",
    "blocks_frontend_template": "阻断前端模板展示",
    "blocks_simc_or_strong_claim": "阻断 SimC 或强结论",
    "blocks_diagnostic_or_record": "影响诊断记录",
}
ADMIN_GATE_MODULE_LABELS = {
    "backend": "后端服务",
    "active_manifest": "正式赛季 Manifest",
    "gear_release_refresh": "装备 Release 定时刷新",
    "news": "新闻发布门禁",
    "raiderio": "Raider.IO 缓存",
    "websim_season": "WebSim 当前赛季",
    "websim_sync": "WebSim 同步状态",
    "gear_catalog": "权威装备库",
    "gear_legality_authority": "装备合法性权威层",
    "talent_catalog": "权威天赋库",
    "template_simc_bridge": "模板到 SimC 桥接",
    "community_templates": "社区天赋与装备模板",
    "stat_weights": "Raider.IO + SimC 属性权重",
    "gear_stat_snapshot": "异步装备属性快照",
    "wcl_credentials": "Warcraft Logs API 凭据",
    "blizzard_api": "Battle.net 游戏数据 API",
}
ADMIN_GATE_BLOCKER_LABELS = {
    "formal retail Manifest has not been activated": "正式零售服 Manifest 尚未激活",
    "formal retail Manifest is inactive after transitional rollback": "正式零售服 Manifest 已回滚到过渡态",
    "active Manifest pointer or release binding is invalid": "正式 Manifest 指针或 Release 绑定无效",
    "active Manifest health reader is unavailable": "正式 Manifest 健康读取不可用",
    "missing deterministic SimC variant preset": "缺少确定性 SimC 装备变体预设",
    "SimC JSON did not include target item stats": "SimC JSON 未包含目标物品属性",
    "SimulationCraft update available": "SimulationCraft 有可用更新",
    "websim cache sync did not complete successfully": "WebSim 缓存同步未成功完成",
    "websim cache has not been synced": "WebSim 缓存尚未同步",
    "Battle.net credentials are not configured.": "Battle.net 凭据未配置。",
    "Warcraft Logs API credentials are not configured.": "Warcraft Logs API 凭据未配置。",
    "default gear template blocked": "默认装备模板被阻断",
    "no saved build templates available for template SimC bridge sampling": "没有可用于模板到 SimC 桥接抽样的已保存构筑模板",
}


def admin_gate_status_label(status):
    value = str(status or "").strip().lower()
    return ADMIN_GATE_STATUS_LABELS.get(value, value)


def admin_gate_severity_label(severity):
    value = str(severity or "").strip()
    return ADMIN_GATE_SEVERITY_LABELS.get(value, value)


def admin_gate_module_title(component):
    component = component if isinstance(component, dict) else {}
    key = str(component.get("key") or "").strip()
    title = str(component.get("title") or "").strip()
    return ADMIN_GATE_MODULE_LABELS.get(key) or ADMIN_GATE_MODULE_LABELS.get(title) or title or key


def admin_gate_localized_blocker(blocker):
    text = admin_gate_summarize_text(blocker, 260)
    if not text:
        return ""
    if " / " in text:
        return " / ".join(
            admin_gate_localized_blocker(part.strip())
            for part in text.split(" / ")
            if part.strip()
        )
    if text in ADMIN_GATE_BLOCKER_LABELS:
        return ADMIN_GATE_BLOCKER_LABELS[text]
    if "WOW_WARCRAFTLOGS_CLIENT_ID" in text or "WOW_WARCRAFTLOGS_API_KEY" in text:
        return "Warcraft Logs 凭据未配置（WOW_WARCRAFTLOGS_CLIENT_ID / WOW_WARCRAFTLOGS_CLIENT_SECRET 或 WOW_WARCRAFTLOGS_API_KEY）。"
    observed = re.search(r"(\d+)\s+observed gear variants missing SimulationCraft item stats", text)
    if observed:
        return f"{observed.group(1)} 个已观测装备变体缺少 SimulationCraft 物品属性"
    missing_talents = re.search(r"talent spell descriptions missing for (\d+) talent spells?", text)
    if missing_talents:
        return f"{missing_talents.group(1)} 个天赋法术缺少说明"
    formula_talents = re.search(r"talent spell descriptions contain unresolved formula text for (\d+) talent spells?", text)
    if formula_talents:
        return f"{formula_talents.group(1)} 个天赋法术说明仍包含未解析公式文本"
    stat_weight = re.search(r"stat weight cache is not verified:\s*([a-z_]+)", text, flags=re.I)
    if stat_weight:
        status = stat_weight.group(1).lower()
        return f"属性权重缓存未通过验证：{admin_gate_status_label(status)}"
    return text


def admin_gate_localized_top_blocker(blocker):
    if not isinstance(blocker, dict):
        return {"reason": admin_gate_localized_blocker(blocker)}
    localized = dict(blocker)
    if localized.get("reason"):
        localized["reason"] = admin_gate_localized_blocker(localized.get("reason"))
    if localized.get("code"):
        localized["code"] = admin_gate_localized_blocker(localized.get("code"))
    return localized


def normalize_data_health_status(status):
    value = str(status or "").strip().lower()
    if value in DATA_HEALTH_STATUSES:
        return value
    if value in {"synced", "ok", "ready"}:
        return "verified"
    if value in {"reference_only", "simc", "llm_reused"}:
        return "partial"
    if value in {"not_configured", "missing_credential", "missing_credentials"}:
        return "missing_credentials"
    if value in {"pending_audit", "pending_official_audit", "official_pending"}:
        return "pending_official_audit"
    return "blocked"


def redact_health_text(value):
    text = str(value or "")
    text = re.sub(r"(?i)(access[_-]?key|api[_-]?key|token|secret)=([^&\s]+)", r"\1=<redacted>", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", text)
    return text


def sanitize_health_value(value):
    if isinstance(value, dict):
        return {key: sanitize_health_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_health_value(item) for item in value]
    if isinstance(value, str):
        return redact_health_text(value)
    return value


def data_health_component(key, title, status, *, checked_at="", details=None, blockers=None):
    normalized_status = normalize_data_health_status(status)
    sanitized_blockers = sanitize_health_value(blockers or [])
    if normalized_status == "verified" and sanitized_blockers:
        normalized_status = "blocked"
    return {
        "key": key,
        "title": title,
        "status": normalized_status,
        "checkedAt": checked_at or "",
        "details": sanitize_health_value(details or {}),
        "blockers": sanitized_blockers,
    }


def data_health_followup_health_component(cache_store):
    if cache_store is None or not hasattr(cache_store, "get_sync_state"):
        return data_health_component(
            "data_health_followup",
            "Revision-gated data health follow-up",
            "blocked",
            details={"mode": "revision_gated", "stateKey": "data_health_followup_v1", "actions": {}},
            blockers=["data health follow-up state reader is unavailable"],
        )
    try:
        state = cache_store.get_sync_state("data_health_followup_v1")
    except Exception:
        return data_health_component(
            "data_health_followup",
            "Revision-gated data health follow-up",
            "blocked",
            details={"mode": "revision_gated", "stateKey": "data_health_followup_v1", "actions": {}},
            blockers=["data health follow-up state reader is unavailable"],
        )
    state = state if isinstance(state, dict) else {}
    actions = state.get("actions") if isinstance(state.get("actions"), dict) else {}
    if not state.get("updatedAt") and not actions:
        return data_health_component(
            "data_health_followup",
            "Revision-gated data health follow-up",
            "partial",
            details={
                "mode": "revision_gated",
                "stateKey": "data_health_followup_v1",
                "ledgerState": "not_observed",
                "actions": {},
            },
            blockers=["data health follow-up ledger has not recorded an execution"],
        )
    safe_actions = {
        str(key): {
            field: value
            for field, value in action.items()
            if field in {"lastSeenRevision", "lastAttemptedRevision", "lastDecision", "lastDecisionAt", "lastReportOnlyReason"}
        }
        for key, action in actions.items()
        if isinstance(action, dict) and str(key or "").strip()
    }
    return data_health_component(
        "data_health_followup",
        "Revision-gated data health follow-up",
        "verified",
        checked_at=state.get("updatedAt") or "",
        details={
            "mode": "revision_gated",
            "stateKey": "data_health_followup_v1",
            "actions": safe_actions,
        },
    )


def gear_stat_snapshot_health_component(*, store=None, now="", simc_runtime_revision=""):
    checked_at = str(now or utc_now())
    active_store = store if store is not None else gear_stat_snapshot_data_store()
    if active_store is None:
        return data_health_component(
            "gear_stat_snapshot",
            "Gear stat snapshot worker",
            "blocked",
            checked_at=checked_at,
            blockers=["stat snapshot PostgreSQL store is unavailable"],
        )
    revision = str(simc_runtime_revision or current_gear_simc_runtime_revision()).strip()
    try:
        summary = active_store.health_summary(now=checked_at)
        readiness = active_store.worker_readiness(
            simc_runtime_revision=revision,
            now=checked_at,
            max_age_seconds=30,
        )
    except Exception:
        return data_health_component(
            "gear_stat_snapshot",
            "Gear stat snapshot worker",
            "blocked",
            checked_at=checked_at,
            blockers=["stat snapshot health reader is unavailable"],
        )
    queue = summary.get("queue") if isinstance(summary.get("queue"), dict) else {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    workers = summary.get("workers") if isinstance(summary.get("workers"), list) else []
    bounded_workers = [
        {
            key: worker.get(key)
            for key in (
                "workerId",
                "status",
                "workerRevision",
                "simcRuntimeRevision",
                "currentJobId",
                "heartbeatAt",
            )
        }
        for worker in workers[:4]
        if isinstance(worker, dict)
    ]
    blockers = [] if readiness.get("ready") is True else ["matching stat snapshot worker is not fresh"]
    return data_health_component(
        "gear_stat_snapshot",
        "Gear stat snapshot worker",
        "verified" if not blockers else "blocked",
        checked_at=summary.get("checkedAt") or checked_at,
        details={
            "simcRuntimeRevision": revision,
            "workerReadiness": readiness,
            "queue": queue,
            "snapshotCount": int(summary.get("snapshotCount") or 0),
            "snapshotCountTruncated": summary.get("snapshotCountTruncated") is True,
            "workers": bounded_workers,
            "metrics": metrics,
        },
        blockers=blockers,
    )


def gear_legality_template_records_from_cache_store(cache_store):
    if not cache_store or not hasattr(cache_store, "admin_gate_gear_template_records"):
        return []
    try:
        payload = cache_store.admin_gate_gear_template_records()
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    return [
        template for template in (payload.get("communityGearTemplates") or [])
        if isinstance(template, dict)
    ]


def gear_legality_authority_health_component(*, candidate_legality_audits=None, templates=None):
    payload = gear_legality_authority_health_payload(
        candidate_legality_audits=candidate_legality_audits or [],
        templates=templates or [],
    )
    return data_health_component(
        "gear_legality_authority",
        "Gear legality authority",
        payload.get("status"),
        checked_at=utc_now(),
        details=payload,
        blockers=payload.get("blockers") or [],
    )


def data_health_overall_status(components):
    statuses = [component.get("status") for component in components]
    if statuses and all(status == "verified" for status in statuses):
        return "verified"
    if any(status in {"verified", "partial", "stale", "pending_official_audit", "source_reference"} for status in statuses):
        return "partial"
    if any(status == "missing_credentials" for status in statuses):
        return "missing_credentials"
    return "blocked"


def gear_catalog_health_payload_from_sync_state(state):
    state = state if isinstance(state, dict) else {}
    variant_readiness = {
        "verified": state.get("verifiedCount") or 0,
        "partial": state.get("partialCount") or 0,
        "blocked": state.get("blockedCount") or 0,
        "total": state.get("variantCount") or 0,
    }
    blockers = state.get("blockers") if isinstance(state.get("blockers"), list) else []
    if not blockers and not state.get("itemCount"):
        blockers = ["gear catalog has not been synced"]
    return {
        "status": state.get("status") or "blocked",
        "checkedAt": state.get("checkedAt") or state.get("updatedAt") or "",
        "details": {
            "itemCount": state.get("itemCount") or 0,
            "sourceCount": state.get("sourceCount") or 0,
            "variantCount": state.get("variantCount") or 0,
            "modOptionCount": state.get("modOptionCount") or 0,
            "verifiedCount": state.get("verifiedCount") or 0,
            "partialCount": state.get("partialCount") or 0,
            "blockedCount": state.get("blockedCount") or 0,
            "observedVariantCount": state.get("observedVariantCount") or 0,
            "verifiedObservedVariantCount": state.get("verifiedObservedVariantCount") or 0,
            "partialObservedVariantCount": state.get("partialObservedVariantCount") or 0,
            "blockedObservedVariantCount": state.get("blockedObservedVariantCount") or 0,
            "variantReadiness": variant_readiness,
            "itemDatabaseRevision": state.get("itemDatabaseRevision") or "",
            "variantRevision": state.get("variantRevision") or state.get("itemDatabaseRevision") or "",
            "schemaRevision": state.get("schemaRevision") or "",
            "catalogContract": state.get("catalogContract") or {},
            "observedBackfill": state.get("observedBackfill") or {},
            "slotCoverage": state.get("slotCoverage") or {},
            "sourceCoverage": state.get("sourceCoverage") or {},
            "sourceGapCoverage": state.get("sourceGapCoverage") or {},
            "modOptionCoverage": state.get("modOptionCoverage") or {},
            "weaponRuleCoverage": state.get("weaponRuleCoverage") or {},
            "itemMetadata": state.get("itemMetadata") or {},
            "seasonSourceCoverage": state.get("seasonSourceCoverage") or {},
            "topBlockers": state.get("topBlockers") or [],
            "dataReadiness": state.get("dataReadiness") or {
                "status": state.get("status") or "blocked",
                "blockers": blockers,
            },
            "simulationReadiness": state.get("simulationReadiness") or {
                "status": state.get("status") or "blocked",
                "blockers": blockers,
                **variant_readiness,
            },
        },
        "blockers": blockers[:8],
    }


def first_text_value(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def nested_dict_value(value, *keys):
    current = value if isinstance(value, dict) else {}
    for key in keys:
        current = current.get(key) if isinstance(current, dict) else {}
    return current if isinstance(current, dict) else {}


def compact_cutover_manifest(manifest, *, active=False):
    manifest = manifest if isinstance(manifest, dict) else {}
    channel = first_text_value(manifest.get("channel"), "retail" if active and manifest else "")
    return {
        "seasonRevision": first_text_value(manifest.get("seasonRevision"), manifest.get("revision")),
        "seasonId": first_text_value(manifest.get("seasonId"), manifest.get("id")),
        "seasonLabel": first_text_value(manifest.get("seasonLabel"), manifest.get("label")),
        "patch": first_text_value(manifest.get("patch")),
        "season": first_text_value(manifest.get("season")),
        "channel": channel,
        "active": bool(active),
        "status": first_text_value(manifest.get("status"), manifest.get("dataStatus"), "verified" if active and manifest else ""),
        "dataStatus": first_text_value(manifest.get("dataStatus")),
        "checkedAt": first_text_value(manifest.get("checkedAt"), manifest.get("verifiedAt")),
        "gearCatalogRevision": first_text_value(manifest.get("gearCatalogRevision")),
        "talentCatalogRevision": first_text_value(manifest.get("talentCatalogRevision")),
        "simcRuntimeRevision": first_text_value(manifest.get("simcRuntimeRevision")),
        "terminologyRevision": first_text_value(manifest.get("terminologyRevision")),
        "previousSeasonRevision": first_text_value(manifest.get("previousSeasonRevision")),
        "rollbackSeasonRevision": first_text_value(
            manifest.get("rollbackSeasonRevision"),
            manifest.get("previousSeasonRevision"),
        ),
        "readAuthority": "active_retail_only" if active else "internal_only",
    }


def staging_cutover_manifests(season, websim_state):
    candidates = []
    for source in (season, websim_state):
        source = source if isinstance(source, dict) else {}
        for key in ("stagingManifests", "stagingSeasonManifests", "ptrSeasonManifests"):
            raw = source.get(key)
            if isinstance(raw, list):
                candidates.extend(item for item in raw if isinstance(item, dict))
        for key in ("stagingSeasonManifest", "stagingSeason", "ptrSeasonManifest", "ptrSeason"):
            raw = source.get(key)
            if isinstance(raw, dict):
                candidates.append(raw)
    output = []
    seen = set()
    for item in candidates:
        compact = compact_cutover_manifest(item, active=False)
        revision = compact.get("seasonRevision")
        if not revision or revision in seen:
            continue
        compact["active"] = False
        output.append(compact)
        seen.add(revision)
    return output[:8]


def catalog_revision_from_health(payload, *keys):
    payload = payload if isinstance(payload, dict) else {}
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    contract = details.get("catalogContract") if isinstance(details.get("catalogContract"), dict) else {}
    for key in keys:
        value = first_text_value(details.get(key), contract.get(key), payload.get(key))
        if value:
            return value
    return first_text_value(contract.get("revision"))


def terminology_cutover_gate(season):
    revision = first_text_value(season.get("terminologyRevision"), "term-seed-2026-07-06")
    return {
        "status": "verified",
        "terminologyRevision": revision,
        "locale": "zh_CN",
        "minimumTerms": [
            {
                "entityType": "hero_talent_tree",
                "entityKey": "spellslinger",
                "canonicalName": "疾咒师",
                "englishName": "Spellslinger",
                "aliases": ["Spellslinger", "法术投射者", "射咒师"],
                "rejectedAliases": ["急咒师"],
                "sourceType": "official_cn_article",
                "sourceRef": "https://wow.blizzard.cn/news/24125213/index.html",
                "status": "verified",
            }
        ],
        "highImpactMissingTerms": [],
        "blockers": [],
    }


def catalyst_overlay_cutover_gate():
    option_parse_supported = "redirected_base_stats" in SIMC_GEAR_OPTION_KEYS
    blocker = (
        "12.1 Catalyst retained-secondary-stat capability proof matrix is incomplete; "
        "catalog policy, Resolver claims, Serializer output, active SimC runtime, real fixture, "
        "frontend explanation, and Manifest capability binding must all be verified"
    )
    return {
        "status": "blocked",
        "simcOption": "redirected_base_stats",
        "optionParseSupported": option_parse_supported,
        "capabilityEnabled": False,
        "serializerAuthority": "backend",
        "frontendMaySynthesize": False,
        "failClosed": True,
        "supportedSimcOptions": sorted(SIMC_GEAR_OPTION_KEYS),
        "blockers": [blocker],
    }


def simc_runtime_cutover_payload(season, websim_state):
    simc_status = simc_version_status()
    websim_simc = websim_state.get("simc") if isinstance(websim_state.get("simc"), dict) else {}
    revision = first_text_value(
        season.get("simcRuntimeRevision"),
        simc_status.get("simcRuntimeRevision"),
        simc_status.get("localTag"),
        websim_simc.get("build"),
        websim_simc.get("version"),
    )
    return {
        "status": first_text_value(simc_status.get("status"), "verified" if revision and not simc_status.get("updateAvailable") else "partial"),
        "simcRuntimeRevision": revision,
        "localTag": simc_status.get("localTag") or "",
        "latestTag": simc_status.get("latestTag") or "",
        "sourceCommit": simc_status.get("sourceCommit") or "",
        "artifactHash": simc_status.get("artifactHash") or "",
        "binaryPath": simc_status.get("binaryPath") or os.environ.get("WOW_SIMC_BIN", ""),
        "channel": first_text_value(simc_status.get("channel"), "retail" if revision else ""),
        "checkedAt": simc_status.get("checkedAt") or "",
        "updateAvailable": bool(simc_status.get("updateAvailable")),
        "source": simc_status.get("source") or "",
        "image": simc_status.get("image") or "",
        "websimState": websim_simc,
    }


def season_cutover_readiness_component(
    season,
    websim_state,
    gear_catalog,
    talent_catalog,
    community_state=None,
    community_sync_run=None,
    stat_weights=None,
):
    season = season if isinstance(season, dict) else {}
    websim_state = websim_state if isinstance(websim_state, dict) else {}
    community_state = community_state if isinstance(community_state, dict) else {}
    community_sync_run = community_sync_run if isinstance(community_sync_run, dict) else {}
    stat_weights = stat_weights if isinstance(stat_weights, dict) else {}
    active_manifest = compact_cutover_manifest(season, active=True)
    staging_manifests = staging_cutover_manifests(season, websim_state)
    terminology = terminology_cutover_gate(season)
    catalyst = catalyst_overlay_cutover_gate()
    simc_runtime = simc_runtime_cutover_payload(season, websim_state)

    gear_revision = first_text_value(
        season.get("gearCatalogRevision"),
        catalog_revision_from_health(gear_catalog, "variantRevision", "itemDatabaseRevision", "revision"),
        nested_dict_value(websim_state, "gearCatalog").get("variantRevision"),
    )
    talent_revision = first_text_value(
        season.get("talentCatalogRevision"),
        catalog_revision_from_health(talent_catalog, "revision", "talentCatalogRevision"),
        websim_state.get("talentRevision"),
    )
    simc_revision = simc_runtime.get("simcRuntimeRevision") or ""
    community_revision = first_text_value(
        season.get("communityTemplateRevision"),
        community_state.get("templateRevision"),
        community_sync_run.get("templateRevision"),
    )
    stat_weight_revision = first_text_value(
        season.get("statWeightRevision"),
        stat_weights.get("revision"),
        stat_weights.get("refreshedAt"),
        stat_weights.get("checkedAt"),
    )
    chickenbro_revision = first_text_value(
        season.get("chickenbroEvidenceRevision"),
        "chickenbro-evidence-v0.2",
    )
    revision_bindings = {
        "seasonRevision": active_manifest.get("seasonRevision") or "",
        "gearCatalogRevision": gear_revision,
        "talentCatalogRevision": talent_revision,
        "simcRuntimeRevision": simc_revision,
        "communityTemplateRevision": community_revision,
        "statWeightRevision": stat_weight_revision,
        "chickenbroEvidenceRevision": chickenbro_revision,
        "terminologyRevision": terminology.get("terminologyRevision") or "",
    }

    blockers = []
    if not active_manifest.get("seasonRevision"):
        blockers.append("active season manifest is missing seasonRevision")
    if active_manifest.get("channel") and active_manifest.get("channel") != "retail":
        blockers.append("active season manifest must use retail channel")
    if season.get("dataStatus") and season.get("dataStatus") != "verified":
        blockers.append(f"active season dataStatus is {season.get('dataStatus')}")
    for key in ("gearCatalogRevision", "talentCatalogRevision", "simcRuntimeRevision", "terminologyRevision"):
        if not revision_bindings.get(key):
            blockers.append(f"{key} is missing")
    if catalyst.get("status") != "verified":
        blockers.extend(catalyst.get("blockers") or [])
    if any(manifest.get("active") for manifest in staging_manifests):
        blockers.append("staging/PTR manifest cannot be active for formal reads")

    gates = {
        "activeRetailPointer": {
            "status": "verified" if active_manifest.get("seasonRevision") and active_manifest.get("channel") == "retail" else "blocked",
            "seasonRevision": active_manifest.get("seasonRevision") or "",
        },
        "revisionBindings": {
            "status": "verified" if all(revision_bindings.get(key) for key in ("seasonRevision", "gearCatalogRevision", "talentCatalogRevision", "simcRuntimeRevision", "terminologyRevision")) else "blocked",
            "missing": [key for key in ("seasonRevision", "gearCatalogRevision", "talentCatalogRevision", "simcRuntimeRevision", "terminologyRevision") if not revision_bindings.get(key)],
        },
        "simcRuntime": {
            "status": simc_runtime.get("status") or "blocked",
            "updateAvailable": bool(simc_runtime.get("updateAvailable")),
        },
        "catalystOverlay": {
            "status": catalyst.get("status"),
            "simcOption": catalyst.get("simcOption"),
        },
        "terminology": {
            "status": terminology.get("status"),
            "terminologyRevision": terminology.get("terminologyRevision"),
        },
        "stagingIsolation": {
            "status": "verified" if not any(manifest.get("active") for manifest in staging_manifests) else "blocked",
            "stagingCount": len(staging_manifests),
        },
    }
    status = "blocked" if blockers else "partial"
    return data_health_component(
        "season_cutover_readiness",
        "12.1 season cutover readiness",
        status,
        checked_at=first_text_value(season.get("checkedAt"), season.get("verifiedAt"), websim_state.get("checkedAt")),
        details={
            "schemaRevision": "season-cutover-readiness-v1",
            "cutoverReadiness": "blocked" if blockers else ("staging_only" if staging_manifests else "partial"),
            "activeManifest": active_manifest,
            "stagingManifests": staging_manifests,
            "revisionBindings": revision_bindings,
            "gates": gates,
            "simcRuntime": simc_runtime,
            "catalystOverlay": catalyst,
            "terminologyCatalog": terminology,
            "officialReadPolicy": {
                "allowClientSeasonOverride": False,
                "formalApiAuthority": "active_retail_manifest",
                "ptrAccess": "internal_only",
            },
            "historicalAssetPolicy": {
                "bindSavedTemplatesToRevision": True,
                "silentReinterpretationAllowed": False,
                "rerunCreatesNewTask": True,
            },
            "blockers": blockers[:12],
        },
        blockers=blockers[:8],
    )


def blizzard_api_health_component():
    configured = bool(
        (os.environ.get("WOW_BLIZZARD_CLIENT_ID") or os.environ.get("WOW_BNET_CLIENT_ID"))
        and (os.environ.get("WOW_BLIZZARD_CLIENT_SECRET") or os.environ.get("WOW_BNET_CLIENT_SECRET"))
    )
    return data_health_component(
        "blizzard_api",
        "Battle.net Game Data API",
        "pending_official_audit" if configured else "missing_credentials",
        details={
            "configured": configured,
            "region": os.environ.get("WOW_BLIZZARD_REGION", "us"),
            "locale": os.environ.get("WOW_BLIZZARD_LOCALE", "zh_CN"),
        },
        blockers=[] if configured else ["Battle.net credentials are not configured."],
    )


def warcraftlogs_api_health_component():
    credentials = warcraftlogs_credentials_state()
    return data_health_component(
        "wcl_credentials",
        "Warcraft Logs API credentials",
        "partial" if credentials["configured"] else "missing_credentials",
        details={
            "configured": credentials["configured"],
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
        },
        blockers=[] if credentials["configured"] else ["Warcraft Logs API credentials are not configured."],
    )


def news_health_component_from_latest(latest):
    latest = latest if isinstance(latest, dict) else {}
    accepted = int(latest.get("acceptedCount") or 0)
    blocked = int(latest.get("blockedArticleCount") or latest.get("rejectedCount") or 0)
    queued = int(latest.get("queuedCount") or 0)
    retryable = int(latest.get("retryableCount") or 0)
    discovered = int(latest.get("discoveredCount") or 0)
    processed = int(latest.get("processedCount") or 0)
    errors = latest.get("sourceFetchErrors") or latest.get("collectorErrors") or []
    if accepted and not blocked and not errors and not queued and not retryable:
        status = "verified"
    elif accepted or queued or retryable or discovered or processed:
        status = "partial"
    else:
        status = "blocked"
    return data_health_component(
        "news",
        "News publication gates",
        status,
        checked_at=latest.get("refreshedAt") or "",
        details={
            "refreshMode": latest.get("refreshMode") or "",
            "acceptedCount": accepted,
            "blockedArticleCount": blocked,
            "discoveredCount": discovered,
            "queuedCount": queued,
            "processedCount": processed,
            "publishedCount": latest.get("publishedCount") or 0,
            "retryableCount": retryable,
            "oldestBacklogAge": latest.get("oldestBacklogAge") or 0,
            "sourceCoverage": latest.get("sourceCoverage") or {},
            "translationIssueCount": latest.get("translationIssueCount") or 0,
            "verificationCounts": latest.get("verificationCounts") or {},
        },
        blockers=errors[:5],
    )


def news_health_component():
    return news_health_component_from_latest(latest_refresh_run_payload())


def template_simc_bridge_health_component(conn):
    rows = conn.execute(
        f"""
        SELECT {BUILD_TEMPLATE_SELECT_COLUMNS}
        FROM user_build_templates
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 200
        """
    ).fetchall()
    counts = {"ready": 0, "partial": 0, "blocked": 0, "total": 0}
    blockers = []
    samples = []
    for row in rows:
        template = public_build_template_from_row(row, conn=conn)
        readiness = template.get("simcraftReadiness") if isinstance(template, dict) else {}
        status = readiness.get("status") if isinstance(readiness, dict) else "blocked"
        if status not in {"ready", "partial", "blocked"}:
            status = "blocked"
        counts[status] += 1
        counts["total"] += 1
        template_blockers = readiness.get("blockers") if isinstance(readiness, dict) else []
        blockers.extend(template_blockers or [])
        if len(samples) < 8:
            samples.append({
                "id": template.get("id", ""),
                "type": template.get("type", ""),
                "title": template.get("title", ""),
                "status": status,
                "blockers": (template_blockers or [])[:3],
            })

    simc_version = simc_version_status()
    update_available = bool(simc_version.get("updateAvailable"))
    blockers = simcraft_template_unique_messages(blockers)
    warnings = []
    if counts["total"] <= 0:
        warnings.append("no saved build templates available for template SimC bridge sampling")
        status = "partial"
    elif counts["blocked"] and not counts["ready"]:
        status = "blocked"
    elif counts["blocked"] or counts["partial"] or update_available:
        status = "partial"
    else:
        status = "verified"
    if update_available:
        warnings.append("SimulationCraft update available")

    return data_health_component(
        "template_simc_bridge",
        "Template to SimC bridge",
        status,
        checked_at=utc_now(),
        details={
            "simcraftVersion": simc_version,
            "templateReadiness": counts,
            "sampleLimit": 200,
            "samples": samples,
            "warnings": warnings,
        },
        blockers=blockers[:8],
    )


def lightweight_template_evidence_audit_payload(community_state=None, community_sync_run=None):
    community_state = community_state if isinstance(community_state, dict) else {}
    community_sync_run = community_sync_run if isinstance(community_sync_run, dict) else {}
    gear = community_sync_run.get("gear") if isinstance(community_sync_run.get("gear"), dict) else {}
    default_templates = gear.get("defaultTemplates") if isinstance(gear.get("defaultTemplates"), dict) else {}
    real_gear = gear.get("realCommunityTemplates") if isinstance(gear.get("realCommunityTemplates"), dict) else {}
    scan_coverage = community_state.get("scanCoverage") if isinstance(community_state.get("scanCoverage"), dict) else {}
    coverage_matrix = community_state.get("coverageMatrix") if isinstance(community_state.get("coverageMatrix"), dict) else {}
    templates = community_state.get("templates") if isinstance(community_state.get("templates"), dict) else {}
    real_covered_specs = real_gear.get("coveredSpecs") if isinstance(real_gear.get("coveredSpecs"), list) else []
    fallback_talent_count = int(templates.get("verified") or 0) if isinstance(templates, dict) else 0
    total_specs = (
        int(scan_coverage.get("totalSpecCount") or 0)
        or int(default_templates.get("totalSpecCount") or 0)
        or 0
    )
    return {
        "schemaRevision": "template-evidence-audit-v1",
        "checkedAt": utc_now(),
        "status": "deferred",
        "deferred": True,
        "deferredReason": "full per-spec evidence matrix is skipped for admin summary performance",
        "summary": {
            "totalSpecCount": total_specs,
            "defaultGearCoveredSpecCount": int(default_templates.get("coveredSpecCount") or 0),
            "realCommunityGearCoveredSpecCount": int(real_gear.get("coveredSpecCount") or len(real_covered_specs) or 0),
            "realCommunityTalentCoveredSpecCount": int(scan_coverage.get("coveredSpecCount") or 0),
            "realCommunityTalentCoveredHeroSlotCount": int(
                scan_coverage.get("coveredHeroSlotCount") or coverage_matrix.get("verifiedHeroSlotCount") or 0
            ),
            "communityTalentTotalHeroSlotCount": int(
                scan_coverage.get("totalHeroSlotCount") or coverage_matrix.get("totalHeroSlotCount") or 0
            ),
            "communityTalentPendingHeroSlotCount": int(
                scan_coverage.get("pendingCollectionHeroSlotCount")
                or coverage_matrix.get("pendingCollectionHeroSlotCount")
                or 0
            ),
            "communityTalentBlockedHeroSlotCount": int(
                scan_coverage.get("blockedHeroSlotCount") or coverage_matrix.get("blockedHeroSlotCount") or 0
            ),
            "fallbackTalentCoveredSpecCount": fallback_talent_count,
            "topBlockers": (default_templates.get("topBlockers") or [])[:4],
        },
    }


def postgres_only_sync_state(cache_store, key, default_blocker):
    if cache_store and hasattr(cache_store, "get_sync_state"):
        try:
            state = cache_store.get_sync_state(key)
        except Exception as error:
            return {"sourceStatus": "blocked", "status": "blocked", "errors": [str(error)]}
        if isinstance(state, dict) and state:
            return state
    return {"sourceStatus": "blocked", "status": "blocked", "errors": [default_blocker]}


def postgres_only_stat_weights_sync_state(cache_store):
    if cache_store and hasattr(cache_store, "get_sync_state"):
        for key in ("stat_weights_sync", "stat_weights"):
            try:
                state = cache_store.get_sync_state(key)
            except Exception as error:
                return {"sourceStatus": "blocked", "status": "blocked", "errors": [str(error)]}
            if isinstance(state, dict) and state:
                return state
    return {"sourceStatus": "blocked", "status": "blocked", "errors": ["PostgreSQL stat weights state is missing"]}


def postgres_only_latest_refresh_state(content_store):
    if content_store and hasattr(content_store, "latest_refresh_run_payload"):
        try:
            latest = content_store.latest_refresh_run_payload()
        except Exception as error:
            return {
                "refreshMode": "postgres_only",
                "refreshedAt": "",
                "acceptedCount": 0,
                "rejectedCount": 1,
                "sourceFetchErrors": [str(error)],
            }
        if isinstance(latest, dict) and latest:
            return latest
    return {
        "refreshMode": "postgres_only",
        "refreshedAt": "",
        "acceptedCount": 0,
        "rejectedCount": 1,
        "sourceFetchErrors": ["PostgreSQL content refresh state is missing"],
    }


def postgres_only_raiderio_payload(cache_store):
    if cache_store and hasattr(cache_store, "get_raiderio_payload"):
        try:
            payload = cache_store.get_raiderio_payload()
        except Exception as error:
            return {"sourceStatus": "blocked", "status": "blocked", "errors": [str(error)]}
        if isinstance(payload, dict) and payload:
            return payload
    return postgres_only_sync_state(cache_store, "raiderio", "PostgreSQL Raider.IO cache is missing")


def postgres_only_talent_catalog_health_payload(websim_state, community_state):
    websim_state = websim_state if isinstance(websim_state, dict) else {}
    community_state = community_state if isinstance(community_state, dict) else {}
    simc = websim_state.get("simc") if isinstance(websim_state.get("simc"), dict) else {}
    talent_count = int(websim_state.get("talentCount") or simc.get("talents") or 0)
    profile_count = int(simc.get("profiles") or simc.get("presets") or 0)
    community_templates = community_state.get("templates") if isinstance(community_state.get("templates"), dict) else {}
    errors = websim_state.get("errors") if isinstance(websim_state.get("errors"), list) else []
    if talent_count:
        status = "partial"
        blockers = errors
    else:
        status = "blocked"
        blockers = errors or ["PostgreSQL talent catalog has no cached talent nodes"]
    return {
        "status": status,
        "checkedAt": websim_state.get("checkedAt") or websim_state.get("updatedAt") or community_state.get("checkedAt") or "",
        "details": {
            "catalogContract": {
                "status": status,
                "checkedAt": websim_state.get("checkedAt") or websim_state.get("updatedAt") or "",
                "schemaRevision": websim_state.get("schemaRevision") or "",
                "revision": websim_state.get("talentRevision") or "",
                "sourceStatus": websim_state.get("dataStatus") or websim_state.get("status") or "",
                "coverage": {
                    "talentCount": talent_count,
                    "profilePresetCount": profile_count,
                    "communityTemplateCount": community_templates.get("total") or 0,
                },
                "topBlockers": blockers[:8],
                "lastError": blockers[0] if blockers else "",
                "staleAfter": websim_state.get("staleAt") or "",
            },
            "talentCount": talent_count,
            "profilePresetCount": profile_count,
            "communityTemplates": community_templates,
        },
        "blockers": blockers[:8],
    }


def postgres_only_template_bridge_health_component():
    return data_health_component(
        "template_simc_bridge",
        "Template to SimC bridge",
        "partial",
        checked_at=utc_now(),
        details={
            "simcraftVersion": simc_version_status(),
            "templateReadiness": {"ready": 0, "partial": 0, "blocked": 0, "total": 0},
            "sampleLimit": 0,
            "samples": [],
            "warnings": ["PG-only health does not sample private template rows without an aggregate read model"],
        },
        blockers=[],
    )


def active_manifest_health_component(cache_store):
    reader = getattr(cache_store, "active_manifest_health", None) if cache_store else None
    if callable(reader):
        try:
            state = reader()
        except Exception:
            state = {}
    else:
        state = {}
    state = state if isinstance(state, dict) else {}
    details = state.get("details") if isinstance(state.get("details"), dict) else {}
    blockers = state.get("blockers") if isinstance(state.get("blockers"), list) else []
    if not state:
        details = {
            "pointerMode": "unavailable",
            "formalActiveManifest": False,
            "pointerGeneration": 0,
        }
        blockers = ["active Manifest health reader is unavailable"]
    return data_health_component(
        "active_manifest",
        "Active retail Season Manifest",
        state.get("status") or "blocked",
        checked_at=details.get("updatedAt") or "",
        details=details,
        blockers=blockers,
    )


def release_refresh_health_component(cache_store):
    reader = getattr(cache_store, "release_refresh_health", None) if cache_store else None
    if callable(reader):
        try:
            state = reader()
        except Exception:
            state = {}
    else:
        state = {}
    state = state if isinstance(state, dict) else {}
    details = state.get("details") if isinstance(state.get("details"), dict) else {}
    blockers = state.get("blockers") if isinstance(state.get("blockers"), list) else []
    if not state:
        details = {
            "lastStatus": "unavailable",
            "timer": {
                "unit": "wow-gear-release-refresh.timer",
                "deployStartsService": False,
            },
        }
        blockers = ["gear release refresh health reader is unavailable"]
    return data_health_component(
        "gear_release_refresh",
        "Immutable gear release refresh",
        state.get("status") or "blocked",
        checked_at=details.get("lastRunAt") or "",
        details=details,
        blockers=blockers,
    )


def build_postgres_only_data_health_payload(*, include_template_evidence_audit=True):
    content_store = content_data_store()
    cache_store = cache_data_store()
    latest = postgres_only_latest_refresh_state(content_store)
    season = runtime_season_payload()
    websim_state = postgres_only_sync_state(cache_store, "websim_sync", "PostgreSQL WebSim sync state is missing")
    gear_state = postgres_only_sync_state(cache_store, "gearCatalog", "PostgreSQL gear catalog state is missing")
    community = postgres_only_sync_state(cache_store, COMMUNITY_TALENT_SYNC_KEY, "PostgreSQL community talent template state is missing")
    community_sync_run = postgres_only_sync_state(cache_store, COMMUNITY_TEMPLATE_SYNC_RUN_KEY, "PostgreSQL community template sync run is missing")
    raiderio = postgres_only_raiderio_payload(cache_store)
    stat_weights = postgres_only_stat_weights_sync_state(cache_store)
    talent_catalog = postgres_only_talent_catalog_health_payload(websim_state, community)
    gear_catalog = gear_catalog_health_payload_from_sync_state(gear_state)
    websim_simc = websim_state.get("simc") if isinstance(websim_state.get("simc"), dict) else {}
    community_gear = community_sync_run.get("gear") if isinstance(community_sync_run.get("gear"), dict) else {}
    default_gear_templates = (
        community_gear.get("defaultTemplates")
        if isinstance(community_gear.get("defaultTemplates"), dict)
        else {}
    )
    gear_templates = community_gear.get("templates") if isinstance(community_gear.get("templates"), dict) else {}
    gear_template_preflight = community_gear.get("preflight") if isinstance(community_gear.get("preflight"), dict) else {}
    baseline_gear_templates = (
        community_gear.get("baselineTemplates")
        if isinstance(community_gear.get("baselineTemplates"), dict)
        else {}
    )
    season_recommendation = (
        community_gear.get("seasonRecommendation")
        if isinstance(community_gear.get("seasonRecommendation"), dict)
        else {}
    )
    community_import_templates = (
        community_gear.get("communityImportTemplates")
        if isinstance(community_gear.get("communityImportTemplates"), dict)
        else {}
    )
    if not community_import_templates and isinstance(gear_template_preflight.get("communityImport"), dict):
        community_import_templates = gear_template_preflight.get("communityImport") or {}
    real_community_templates = (
        community_gear.get("realCommunityTemplates")
        if isinstance(community_gear.get("realCommunityTemplates"), dict)
        else {}
    )
    template_chains = (
        community_gear.get("templateChains")
        if isinstance(community_gear.get("templateChains"), dict)
        else {}
    )
    recommended_bis_guard = (
        community_gear.get("recommendedBisGuard")
        if isinstance(community_gear.get("recommendedBisGuard"), dict)
        else {}
    )
    recommended_bis_prototype = (
        community_gear.get("recommendedBisPrototype")
        if isinstance(community_gear.get("recommendedBisPrototype"), dict)
        else {}
    )
    community_observed_guard = (
        community_gear.get("communityObservedGuard")
        if isinstance(community_gear.get("communityObservedGuard"), dict)
        else {}
    )
    live_gear_template_run_id = ""
    if cache_store and hasattr(cache_store, "community_gear_template_live_health_summary"):
        try:
            live_gear_templates = cache_store.community_gear_template_live_health_summary()
        except Exception:
            live_gear_templates = {}
        if isinstance(live_gear_templates, dict) and live_gear_templates:
            gear_templates = live_gear_templates.get("templates") or gear_templates
            gear_template_preflight = live_gear_templates.get("preflight") or gear_template_preflight
            baseline_gear_templates = live_gear_templates.get("baselineTemplates") or baseline_gear_templates
            season_recommendation = live_gear_templates.get("seasonRecommendation") or season_recommendation
            community_import_templates = live_gear_templates.get("communityImportTemplates") or community_import_templates
            real_community_templates = live_gear_templates.get("realCommunityTemplates") or real_community_templates
            template_chains = live_gear_templates.get("templateChains") or template_chains
            recommended_bis_guard = live_gear_templates.get("recommendedBisGuard") or recommended_bis_guard
            recommended_bis_prototype = live_gear_templates.get("recommendedBisPrototype") or recommended_bis_prototype
            community_observed_guard = live_gear_templates.get("communityObservedGuard") or community_observed_guard
            live_gear_template_run_id = live_gear_templates.get("scanRunId") or ""
    gear_legality_templates = gear_legality_template_records_from_cache_store(cache_store)
    gear_legality_candidate_audits = [
        gear_state.get("candidateLegalityAudit") if isinstance(gear_state, dict) else {},
        (gear_catalog.get("details") or {}).get("candidateLegalityAudit") if isinstance(gear_catalog.get("details"), dict) else {},
    ]
    template_evidence_audit = lightweight_template_evidence_audit_payload(
        community_state=community,
        community_sync_run=community_sync_run,
    )
    community_status = community.get("sourceStatus") or community.get("status")
    if community_import_templates.get("status") and community_import_templates.get("status") != "verified":
        community_status = "partial" if community_status in {"synced", "verified"} else (community_status or "partial")
    components = [
        data_health_component("backend", "Backend service", "verified", checked_at=utc_now()),
        data_health_followup_health_component(cache_store),
        active_manifest_health_component(cache_store),
        release_refresh_health_component(cache_store),
        gear_stat_snapshot_health_component(),
        news_health_component_from_latest(latest),
        data_health_component(
            "raiderio",
            "Raider.IO cache",
            raiderio.get("sourceStatus") or raiderio.get("status"),
            checked_at=raiderio.get("checkedAt") or raiderio.get("updatedAt") or "",
            details={
                "region": raiderio.get("region") or "",
                "seasonSlug": raiderio.get("seasonSlug") or "",
                "runCount": raiderio.get("runCount") or 0,
                "profileCount": raiderio.get("profileCount") or 0,
                "targetItemCoverage": raiderio.get("targetItemCoverage") or {},
                "expiresAt": raiderio.get("expiresAt") or "",
                "staleAt": raiderio.get("staleAt") or "",
            },
            blockers=raiderio.get("errors") or [],
        ),
        data_health_component(
            "websim_season",
            "WebSim active season",
            season.get("dataStatus"),
            checked_at=season.get("verifiedAt") or "",
            details={
                "seasonId": season.get("seasonId") or season.get("id") or "",
                "seasonRevision": season.get("seasonRevision") or season.get("revision") or "",
                "locale": season.get("locale") or "",
                "expiresAt": season.get("expiresAt") or "",
                "sourceRefs": season.get("sourceRefs") or [],
            },
            blockers=season.get("errors") or [],
        ),
        data_health_component(
            "websim_sync",
            "WebSim sync state",
            websim_state.get("dataStatus") or websim_state.get("sourceStatus") or websim_state.get("status"),
            checked_at=websim_state.get("checkedAt") or websim_state.get("updatedAt") or "",
            details={
                "dataStatus": websim_state.get("dataStatus") or "",
                "simc": websim_simc,
                "gearCatalog": gear_state,
                "currentSeason": websim_state.get("currentSeason") if isinstance(websim_state.get("currentSeason"), dict) else {},
                "blizzardSkipped": websim_state.get("blizzardSkipped"),
                "itemCount": websim_state.get("itemCount") or 0,
                "talentCount": websim_state.get("talentCount") or websim_simc.get("talents") or 0,
                "profileCount": websim_simc.get("profiles") or websim_simc.get("presets") or 0,
                "gearItemCount": gear_state.get("itemCount") or 0,
                "observedVariantCount": gear_state.get("observedVariantCount") or 0,
            },
            blockers=websim_state.get("errors") or [],
        ),
        data_health_component(
            "gear_catalog",
            "Authoritative gear catalog",
            gear_catalog.get("status"),
            checked_at=gear_catalog.get("checkedAt") or "",
            details=gear_catalog.get("details") or {},
            blockers=gear_catalog.get("blockers") or [],
        ),
        gear_legality_authority_health_component(
            candidate_legality_audits=gear_legality_candidate_audits,
            templates=gear_legality_templates,
        ),
        data_health_component(
            "talent_catalog",
            "Authoritative talent catalog",
            talent_catalog.get("status"),
            checked_at=talent_catalog.get("checkedAt") or "",
            details=talent_catalog.get("details") or {},
            blockers=talent_catalog.get("blockers") or [],
        ),
        postgres_only_template_bridge_health_component(),
        data_health_component(
            "community_templates",
            "Community talent and gear templates",
            community_status,
            checked_at=community.get("checkedAt") or community.get("updatedAt") or "",
            details={
                "templates": community.get("templates") or {},
                "sources": community.get("sources") or {},
                "templateRevision": community.get("templateRevision") or "",
                "scanCoverage": community.get("scanCoverage") or {},
                "coverageMatrix": community.get("coverageMatrix") or {},
                "dedupedCount": community.get("dedupedCount") or 0,
                "hiddenDuplicateCount": community.get("hiddenDuplicateCount") or 0,
                "wclTemplateSource": (community.get("sources") or {}).get("warcraftlogs") or {},
                "gearTemplates": gear_templates,
                "gearTemplatePreflight": gear_template_preflight,
                "communityImportTemplates": community_import_templates,
                "realCommunityGearTemplates": real_community_templates,
                "baselineGearTemplates": baseline_gear_templates,
                "seasonRecommendation": season_recommendation,
                "templateChains": template_chains,
                "recommendedBisGuard": recommended_bis_guard,
                "recommendedBisPrototype": recommended_bis_prototype,
                "communityObservedGuard": community_observed_guard,
                "defaultGearTemplates": default_gear_templates,
                "changeReport": community_sync_run.get("changeReport") or {},
                "templateEvidenceAudit": template_evidence_audit,
                "lastSyncRun": live_gear_template_run_id or community_sync_run.get("scanRunId") or default_gear_templates.get("lastSyncRun") or "",
            },
            blockers=[
                error
                for source in (community.get("sources") or {}).values()
                for error in (source.get("errors") or [])
            ][:8] + (community.get("errors") or [])[:8],
        ),
        data_health_component(
            "stat_weights",
            "Raider.IO + SimC stat weights",
            stat_weights.get("sourceStatus") or stat_weights.get("status"),
            checked_at=stat_weights.get("refreshedAt") or stat_weights.get("checkedAt") or stat_weights.get("updatedAt") or "",
            details={
                "acceptedCount": stat_weights.get("acceptedCount") or 0,
                "blockedCount": stat_weights.get("blockedCount") or 0,
                "raiderioStatus": stat_weights.get("raiderioStatus") or "",
                "specCount": stat_weights.get("specCount") or 0,
                "scenarioCount": stat_weights.get("scenarioCount") or 0,
            },
            blockers=(stat_weights.get("errors") or stat_weights.get("message", {}).get("errors") or [])[:8],
        ),
        season_cutover_readiness_component(
            season,
            websim_state,
            gear_catalog,
            talent_catalog,
            community_state=community,
            community_sync_run=community_sync_run,
            stat_weights=stat_weights,
        ),
        warcraftlogs_api_health_component(),
        blizzard_api_health_component(),
    ]
    return {
        "schemaRevision": "data-health-v1",
        "checkedAt": utc_now(),
        "allowedStatuses": DATA_HEALTH_STATUSES,
        "overallStatus": data_health_overall_status(components),
        "components": components,
    }


def build_data_health_payload(*, include_template_evidence_audit=True):
    if postgres_only_runtime_enabled():
        return build_postgres_only_data_health_payload(
            include_template_evidence_audit=include_template_evidence_audit
        )
    init_db()
    cache_store = cache_data_store()
    pg_websim_state = cache_store.get_sync_state("websim_sync") if cache_store else {}
    pg_gear_state = cache_store.get_sync_state("gearCatalog") if cache_store else {}
    components = [
        data_health_component("backend", "Backend service", "verified", checked_at=utc_now()),
        data_health_followup_health_component(cache_store),
        news_health_component(),
    ]
    with db_connection() as conn:
        raiderio = get_raiderio_payload(conn, allow_sync=False)
        components.append(
            data_health_component(
                "raiderio",
                "Raider.IO cache",
                raiderio.get("sourceStatus") or raiderio.get("status"),
                checked_at=raiderio.get("checkedAt") or "",
                details={
                    "region": raiderio.get("region") or "",
                    "seasonSlug": raiderio.get("seasonSlug") or "",
                    "runCount": raiderio.get("runCount") or 0,
                    "profileCount": raiderio.get("profileCount") or 0,
                    "targetItemCoverage": raiderio.get("targetItemCoverage") or {},
                    "expiresAt": raiderio.get("expiresAt") or "",
                    "staleAt": raiderio.get("staleAt") or "",
                },
                blockers=raiderio.get("errors") or [],
            )
        )

        season = get_active_season_payload(conn)
        components.append(
            data_health_component(
                "websim_season",
                "WebSim active season",
                season.get("dataStatus"),
                checked_at=season.get("verifiedAt") or "",
                details={
                    "seasonId": season.get("seasonId") or season.get("id") or "",
                    "seasonRevision": season.get("seasonRevision") or season.get("revision") or "",
                    "locale": season.get("locale") or "",
                    "expiresAt": season.get("expiresAt") or "",
                    "sourceRefs": season.get("sourceRefs") or [],
                },
                blockers=season.get("errors") or [],
            )
        )

        websim_state = pg_websim_state or get_sync_state(conn, "websim_sync") or {}
        websim_errors = websim_state.get("errors") if isinstance(websim_state.get("errors"), list) else []
        websim_simc = websim_state.get("simc") if isinstance(websim_state.get("simc"), dict) else {}
        websim_gear = websim_state.get("gearCatalog") if isinstance(websim_state.get("gearCatalog"), dict) else {}
        standalone_gear = pg_gear_state or get_sync_state(conn, "gearCatalog") or {}
        if isinstance(standalone_gear, dict) and standalone_gear:
            websim_gear = standalone_gear
        websim_season = websim_state.get("currentSeason") if isinstance(websim_state.get("currentSeason"), dict) else {}
        if websim_state:
            websim_status = websim_state.get("dataStatus") or ("verified" if websim_state.get("ok") else "blocked")
            websim_blockers = websim_errors if websim_errors else ([] if websim_state.get("ok") else ["websim cache sync did not complete successfully"])
        else:
            websim_status = "blocked"
            websim_blockers = ["websim cache has not been synced"]
        components.append(
            data_health_component(
                "websim_sync",
                "WebSim sync state",
                websim_status,
                checked_at=websim_state.get("checkedAt") or websim_state.get("updatedAt") or "",
                details={
                    "dataStatus": websim_state.get("dataStatus") or "",
                    "simc": websim_simc,
                    "gearCatalog": websim_gear,
                    "currentSeason": websim_season,
                    "blizzardSkipped": websim_state.get("blizzardSkipped"),
                    "itemCount": websim_state.get("itemCount") or 0,
                    "talentCount": websim_state.get("talentCount") or websim_simc.get("talents") or 0,
                    "profileCount": websim_simc.get("presets") or 0,
                    "gearItemCount": websim_gear.get("itemCount") or 0,
                    "observedVariantCount": websim_gear.get("observedVariantCount") or 0,
                },
                blockers=websim_blockers,
            )
        )

        gear_catalog = gear_catalog_health_payload_from_sync_state(pg_gear_state) if pg_gear_state else gear_catalog_health_payload(conn)
        components.append(
            data_health_component(
                "gear_catalog",
                "Authoritative gear catalog",
                gear_catalog.get("status"),
                checked_at=gear_catalog.get("checkedAt") or "",
                details=gear_catalog.get("details") or {},
                blockers=gear_catalog.get("blockers") or [],
            )
        )
        components.append(
            gear_legality_authority_health_component(
                candidate_legality_audits=[
                    standalone_gear.get("candidateLegalityAudit") if isinstance(standalone_gear, dict) else {},
                    (gear_catalog.get("details") or {}).get("candidateLegalityAudit") if isinstance(gear_catalog.get("details"), dict) else {},
                ],
                templates=gear_legality_template_records_from_cache_store(cache_store),
            )
        )

        talent_catalog = talent_catalog_health_payload(conn)
        components.append(
            data_health_component(
                "talent_catalog",
                "Authoritative talent catalog",
                talent_catalog.get("status"),
                checked_at=talent_catalog.get("checkedAt") or "",
                details=talent_catalog.get("details") or {},
                blockers=talent_catalog.get("blockers") or [],
            )
        )

        components.append(template_simc_bridge_health_component(conn))

        community = community_talent_sync_state(conn)
        community_sync_run = get_sync_state(conn, COMMUNITY_TEMPLATE_SYNC_RUN_KEY) or {}
        community_gear = community_sync_run.get("gear") if isinstance(community_sync_run.get("gear"), dict) else {}
        default_gear_templates = (
            community_gear.get("defaultTemplates")
            if isinstance(community_gear.get("defaultTemplates"), dict)
            else {}
        )
        gear_templates = community_gear.get("templates") if isinstance(community_gear.get("templates"), dict) else {}
        gear_template_preflight = community_gear.get("preflight") if isinstance(community_gear.get("preflight"), dict) else {}
        baseline_gear_templates = (
            community_gear.get("baselineTemplates")
            if isinstance(community_gear.get("baselineTemplates"), dict)
            else {}
        )
        community_import_templates = (
            community_gear.get("communityImportTemplates")
            if isinstance(community_gear.get("communityImportTemplates"), dict)
            else {}
        )
        if not community_import_templates and isinstance(gear_template_preflight.get("communityImport"), dict):
            community_import_templates = gear_template_preflight.get("communityImport") or {}
        real_community_templates = (
            community_gear.get("realCommunityTemplates")
            if isinstance(community_gear.get("realCommunityTemplates"), dict)
            else {}
        )
        if include_template_evidence_audit:
            template_evidence_audit = template_evidence_audit_payload(
                conn,
                community_state=community,
                community_sync_run=community_sync_run,
            )
        else:
            template_evidence_audit = lightweight_template_evidence_audit_payload(
                community_state=community,
                community_sync_run=community_sync_run,
            )
        community_status = community.get("sourceStatus")
        if community_import_templates.get("status") and community_import_templates.get("status") != "verified":
            community_status = "partial" if community_status in {"synced", "verified"} else (community_status or "partial")
        if default_gear_templates.get("blockedSpecCount") and community_status in {"synced", "verified"}:
            community_status = "partial"
        components.append(
            data_health_component(
                "community_templates",
                "Community talent and gear templates",
                community_status,
                checked_at=community.get("checkedAt") or "",
                details={
                    "templates": community.get("templates") or {},
                    "sources": community.get("sources") or {},
                    "templateRevision": community.get("templateRevision") or "",
                    "scanCoverage": community.get("scanCoverage") or {},
                    "coverageMatrix": community.get("coverageMatrix") or {},
                    "dedupedCount": community.get("dedupedCount") or 0,
                    "hiddenDuplicateCount": community.get("hiddenDuplicateCount") or 0,
                    "wclTemplateSource": (community.get("sources") or {}).get("warcraftlogs") or {},
                    "gearTemplates": gear_templates,
                    "gearTemplatePreflight": gear_template_preflight,
                    "communityImportTemplates": community_import_templates,
                    "realCommunityGearTemplates": real_community_templates,
                    "baselineGearTemplates": baseline_gear_templates,
                    "defaultGearTemplates": default_gear_templates,
                    "changeReport": community_sync_run.get("changeReport") or {},
                    "templateEvidenceAudit": template_evidence_audit,
                    "lastSyncRun": community_sync_run.get("scanRunId") or default_gear_templates.get("lastSyncRun") or "",
                },
                blockers=[
                    error
                    for source in (community.get("sources") or {}).values()
                    for error in (source.get("errors") or [])
                ][:8] + [
                    blocker.get("reason") or blocker.get("specId") or "default gear template blocked"
                    for blocker in (default_gear_templates.get("blockers") or [])[:8]
                    if isinstance(blocker, dict)
                ],
            )
        )

        stat_weights = latest_stat_weight_run_payload(conn)
        components.append(
            data_health_component(
                "stat_weights",
                "Raider.IO + SimC stat weights",
                stat_weights.get("sourceStatus") or stat_weights.get("status"),
                checked_at=stat_weights.get("refreshedAt") or stat_weights.get("raiderioCheckedAt") or "",
                details={
                    "acceptedCount": stat_weights.get("acceptedCount") or 0,
                    "blockedCount": stat_weights.get("blockedCount") or 0,
                    "raiderioStatus": stat_weights.get("raiderioStatus") or "",
                    "specCount": stat_weights.get("specCount") or 0,
                    "scenarioCount": stat_weights.get("scenarioCount") or 0,
                },
                blockers=(stat_weights.get("errors") or stat_weights.get("message", {}).get("errors") or [])[:8],
            )
        )

        components.append(
            season_cutover_readiness_component(
                season,
                websim_state,
                gear_catalog,
                talent_catalog,
                community_state=community,
                community_sync_run=community_sync_run,
                stat_weights=stat_weights,
            )
        )

    components.append(warcraftlogs_api_health_component())
    components.append(blizzard_api_health_component())
    return {
        "schemaRevision": "data-health-v1",
        "checkedAt": utc_now(),
        "allowedStatuses": DATA_HEALTH_STATUSES,
        "overallStatus": data_health_overall_status(components),
        "components": components,
    }


def public_user_from_row(row):
    if not row:
        return None
    return {
        "id": row[0],
        "openid": row[1],
        "unionid": row[2],
        "nickname": row[3],
        "avatarUrl": row[4],
        "createdAt": row[5],
        "updatedAt": row[6],
    }


def exchange_wechat_code(code):
    if not code:
        raise ValueError("missing wechat login code")
    appid = os.environ.get("WOW_WECHAT_APPID", "").strip()
    secret = os.environ.get("WOW_WECHAT_SECRET", "").strip()
    if not appid or not secret:
        raise RuntimeError("wechat app credentials are not configured")

    query = urlencode(
        {
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"
    with urlopen(url, timeout=int_env("WOW_WECHAT_TIMEOUT_SECONDS", 8)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("errcode"):
        raise RuntimeError(payload.get("errmsg") or f"wechat code2Session failed: {payload['errcode']}")
    if not payload.get("openid"):
        raise RuntimeError("wechat code2Session response did not include openid")
    return payload


def upsert_wechat_user(openid, unionid=""):
    store = personal_data_store()
    if store:
        return store.upsert_wechat_user(openid, unionid or "", now=utc_now())
    now = utc_now()
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO wechat_users (openid, unionid, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(openid) DO UPDATE SET
                unionid=COALESCE(NULLIF(excluded.unionid, ''), wechat_users.unionid),
                updated_at=excluded.updated_at
            """,
            (openid, unionid or "", now, now),
        )
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE openid = ?
            """,
            (openid,),
        ).fetchone()
    return public_user_from_row(row)


def create_auth_token(user_id):
    token = f"wow_{secrets.token_urlsafe(32)}"
    created_at = utc_now()
    expires_at = auth_token_expires_at()
    store = personal_data_store()
    if store:
        store.create_auth_token(user_id, token, created_at, expires_at)
        return token, expires_at
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, created_at, expires_at),
        )
    return token, expires_at


def login_with_wechat_code(code, exchange_code=exchange_wechat_code):
    payload = exchange_code(code)
    openid = (payload.get("openid") or "").strip()
    if not openid:
        raise ValueError("wechat login did not return openid")

    user = upsert_wechat_user(openid, (payload.get("unionid") or "").strip())
    token, expires_at = create_auth_token(user["id"])
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresAt": auth_expires_at_ms(expires_at),
        "user": user,
    }


def bearer_token_from_headers(headers):
    authorization = headers.get("Authorization", "") if headers else ""
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def authenticate_token(token):
    if not token:
        return None
    store = personal_data_store()
    if store:
        return store.authenticate_token(token, now=utc_now())
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.openid, u.unionid, u.nickname, u.avatar_url, u.created_at, u.updated_at
            FROM auth_tokens t
            JOIN wechat_users u ON u.id = t.user_id
            WHERE t.token = ? AND t.expires_at > ?
            """,
            (token, utc_now()),
        ).fetchone()
    return public_user_from_row(row)


def guest_openid_from_id(guest_id):
    normalized = str(guest_id or "").strip()[:128]
    if not normalized:
        return ""
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{GUEST_SIMULATOR_OPENID}-{digest}"


def guest_simulator_user(guest_id=""):
    guest_openid = guest_openid_from_id(guest_id)
    if not guest_openid:
        return None
    return upsert_wechat_user(guest_openid)


def find_guest_simulator_user(guest_id=""):
    guest_openid = guest_openid_from_id(guest_id)
    if not guest_openid:
        return None
    store = personal_data_store()
    if store:
        return store.find_wechat_user_by_openid(guest_openid)
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE openid = ?
            """,
            (guest_openid,),
        ).fetchone()
    return public_user_from_row(row)


def clean_text(value, limit):
    return str(value or "").strip()[:limit]


def append_unique_text(values, text):
    value = str(text or "").strip()
    if value and value not in values:
        values.append(value)


def append_unique_item(values, item):
    if item and item not in values:
        values.append(item)


def safe_json_loads(value, fallback, label):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError) as error:
        print(f"warning: failed to decode {label}: {error}", file=sys.stderr)
        return fallback


def update_user_profile(access_token, profile):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")

    nickname = clean_text(profile.get("nickname"), 64)
    avatar_url = clean_text(profile.get("avatarUrl") or profile.get("avatar_url"), 500)
    now = utc_now()
    store = personal_data_store()
    if store:
        return store.update_user_profile(user["id"], nickname, avatar_url, now)
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE wechat_users
            SET nickname = ?, avatar_url = ?, updated_at = ?
            WHERE id = ?
            """,
            (nickname, avatar_url, now, user["id"]),
        )
        row = conn.execute(
            """
            SELECT id, openid, unionid, nickname, avatar_url, created_at, updated_at
            FROM wechat_users WHERE id = ?
            """,
            (user["id"],),
        ).fetchone()
    return public_user_from_row(row)


BUILD_TEMPLATE_SELECT_COLUMNS = """
    id, client_id, template_type, title, class_key, class_name, spec_key, spec_name,
    hero_key, hero_label, scenario_key, scenario_title, raw_string, simc_lines_json,
    status, status_label, source, metadata_json, schema_version, created_at, updated_at
"""


def build_template_status_label(template_type, status):
    if status == "saved":
        return "已保存"
    if status == "complete":
        return "完整配置"
    if status == "encoded":
        return "Encoded"
    if status == "simc_ready":
        return "SimC-ready"
    if status == "partial":
        return "Partial"
    if status == "blocked":
        return "Blocked"
    return "已保存" if template_type == "talent" else "完整配置"


def normalize_build_template_payload(record):
    source = record if isinstance(record, dict) else {}
    template_type = clean_text(source.get("type") or source.get("templateType"), 32)
    if template_type not in VALID_BUILD_TEMPLATE_TYPES:
        raise ValueError("invalid build template type")
    raw_string = clean_text(source.get("rawString") or source.get("raw_string"), 20000)
    if not raw_string:
        raise ValueError("build template rawString is required")

    simc_lines = source.get("simcLines") or source.get("simc_lines") or []
    if not isinstance(simc_lines, list):
        simc_lines = []
    simc_lines = [clean_text(line, 2000) for line in simc_lines if clean_text(line, 2000)]
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    if template_type == "gear" and isinstance(metadata.get("gearSnapshot"), dict) and not raw_string.strip().startswith("{"):
        raw_string = clean_text(json.dumps(metadata.get("gearSnapshot"), ensure_ascii=False), 20000)
    status = clean_text(source.get("status"), 64) or ("saved" if template_type == "talent" else "complete")
    title = clean_text(source.get("title"), 200) or ("Talent Template" if template_type == "talent" else "Gear Template")
    now = utc_now()
    return {
        "client_id": clean_text(source.get("clientId") or source.get("id"), 128),
        "template_type": template_type,
        "title": title,
        "class_key": clean_text(source.get("classKey") or source.get("class_key"), 64),
        "class_name": clean_text(source.get("className") or source.get("class_name"), 100),
        "spec_key": clean_text(source.get("specKey") or source.get("spec_key"), 64),
        "spec_name": clean_text(source.get("specName") or source.get("spec_name"), 100),
        "hero_key": clean_text(source.get("heroKey") or source.get("hero_key"), 64),
        "hero_label": clean_text(source.get("heroLabel") or source.get("hero_label"), 100),
        "scenario_key": clean_text(source.get("scenarioKey") or source.get("scenario_key"), 64),
        "scenario_title": clean_text(source.get("scenarioTitle") or source.get("scenario_title"), 120),
        "raw_string": raw_string,
        "simc_lines_json": json.dumps(simc_lines, ensure_ascii=False),
        "status": status,
        "status_label": clean_text(source.get("statusLabel") or source.get("status_label"), 100)
        or build_template_status_label(template_type, status),
        "source": clean_text(source.get("source"), 120) or "local",
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "schema_version": int(source.get("schemaVersion") or BUILD_TEMPLATE_SCHEMA_VERSION),
        "created_at": clean_text(source.get("createdAt") or source.get("created_at"), 64) or now,
        "updated_at": clean_text(source.get("updatedAt") or source.get("updated_at"), 64) or now,
    }


def public_build_template_from_row(row, conn=None):
    if not row:
        return None
    simc_lines = safe_json_loads(row[13], [], f"build template simc lines {row[0]}")
    metadata = safe_json_loads(row[17], {}, f"build template metadata {row[0]}")
    if not isinstance(simc_lines, list):
        simc_lines = []
    if not isinstance(metadata, dict):
        metadata = {}
    template = {
        "id": row[0],
        "clientId": row[1],
        "type": row[2],
        "title": row[3],
        "classKey": row[4],
        "className": row[5],
        "specKey": row[6],
        "specName": row[7],
        "heroKey": row[8],
        "heroLabel": row[9],
        "scenarioKey": row[10],
        "scenarioTitle": row[11],
        "rawString": row[12],
        "simcLines": simc_lines,
        "status": row[14],
        "statusLabel": row[15],
        "source": row[16],
        "metadata": metadata,
        "schemaVersion": row[18],
        "createdAt": row[19],
        "updatedAt": row[20],
        "remote": True,
    }
    template["simcraftReadiness"] = simcraft_template_readiness(template, conn=conn)
    return template


def list_user_build_templates(access_token, template_type=""):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized_type = clean_text(template_type, 32)
    store = personal_data_store()
    if store:
        store_type = normalized_type if normalized_type in VALID_BUILD_TEMPLATE_TYPES else ""
        return {
            "user": user,
            "schemaVersion": BUILD_TEMPLATE_SCHEMA_VERSION,
            "templates": store.list_build_templates(user["id"], store_type),
        }
    params = [user["id"]]
    where = "WHERE user_id = ?"
    if normalized_type in VALID_BUILD_TEMPLATE_TYPES:
        where += " AND template_type = ?"
        params.append(normalized_type)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {BUILD_TEMPLATE_SELECT_COLUMNS}
            FROM user_build_templates
            {where}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 200
            """,
            tuple(params),
        ).fetchall()
        templates = [public_build_template_from_row(row, conn=conn) for row in rows]
    return {
        "user": user,
        "schemaVersion": BUILD_TEMPLATE_SCHEMA_VERSION,
        "templates": templates,
    }


def save_user_build_template(access_token, record):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized = normalize_build_template_payload(record)
    store = personal_data_store()
    if store:
        return store.save_build_template(user["id"], normalized)
    with db_connection() as conn:
        existing = conn.execute(
            """
            SELECT id, created_at FROM user_build_templates
            WHERE user_id = ? AND template_type = ? AND raw_string = ?
            """,
            (user["id"], normalized["template_type"], normalized["raw_string"]),
        ).fetchone()
        template_id = existing[0] if existing else uuid.uuid4().hex
        created_at = existing[1] if existing else normalized["created_at"]
        conn.execute(
            """
            INSERT INTO user_build_templates (
                id, user_id, client_id, template_type, title, class_key, class_name,
                spec_key, spec_name, hero_key, hero_label, scenario_key, scenario_title,
                raw_string, simc_lines_json, status, status_label, source, metadata_json,
                schema_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, template_type, raw_string) DO UPDATE SET
                client_id = excluded.client_id,
                title = excluded.title,
                class_key = excluded.class_key,
                class_name = excluded.class_name,
                spec_key = excluded.spec_key,
                spec_name = excluded.spec_name,
                hero_key = excluded.hero_key,
                hero_label = excluded.hero_label,
                scenario_key = excluded.scenario_key,
                scenario_title = excluded.scenario_title,
                simc_lines_json = excluded.simc_lines_json,
                status = excluded.status,
                status_label = excluded.status_label,
                source = excluded.source,
                metadata_json = excluded.metadata_json,
                schema_version = excluded.schema_version,
                updated_at = excluded.updated_at
            """,
            (
                template_id,
                user["id"],
                normalized["client_id"],
                normalized["template_type"],
                normalized["title"],
                normalized["class_key"],
                normalized["class_name"],
                normalized["spec_key"],
                normalized["spec_name"],
                normalized["hero_key"],
                normalized["hero_label"],
                normalized["scenario_key"],
                normalized["scenario_title"],
                normalized["raw_string"],
                normalized["simc_lines_json"],
                normalized["status"],
                normalized["status_label"],
                normalized["source"],
                normalized["metadata_json"],
                normalized["schema_version"],
                created_at,
                normalized["updated_at"],
            ),
        )
        row = conn.execute(
            f"""
            SELECT {BUILD_TEMPLATE_SELECT_COLUMNS}
            FROM user_build_templates
            WHERE user_id = ? AND id = ?
            """,
            (user["id"], template_id),
        ).fetchone()
        return public_build_template_from_row(row, conn=conn)


def delete_user_build_template(access_token, template_id):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized_id = clean_text(template_id, 128)
    if not normalized_id:
        raise KeyError("build template not found")
    store = personal_data_store()
    if store:
        return store.delete_build_template(user["id"], normalized_id)
    with db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM user_build_templates WHERE user_id = ? AND id = ?",
            (user["id"], normalized_id),
        )
    if cursor.rowcount <= 0:
        raise KeyError("build template not found")
    return {"id": normalized_id, "deleted": True}


SIMCRAFT_TEMPLATE_REQUIRED_GEAR_SLOTS = [
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
    "off_hand",
]

SIMCRAFT_TEMPLATE_SCENARIOS = {
    "single": {"label": "单体基准", "fightStyle": "Patchwerk", "targets": 1, "durationSeconds": 300},
    "aoe_5": {"label": "5目标AOE基准", "fightStyle": "Patchwerk", "targets": 5, "durationSeconds": 300},
    "mythic_plus": {"label": "近似大秘境", "fightStyle": "DungeonSlice", "targets": 5, "durationSeconds": 360},
}

SIMCRAFT_TEMPLATE_ANALYSIS_TYPES = {"baseline", "stat_weights"}
SIMCRAFT_TEMPLATE_READY_GEAR_STATUSES = {"complete", "complete_with_warnings"}
SIMCRAFT_TEMPLATE_STAT_SNAPSHOT_REQUIRED_ERROR = "gear stat snapshot is not verified"


def simcraft_template_record(source, template_type):
    record = source if isinstance(source, dict) else {}
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return {
        "id": clean_text(record.get("id") or record.get("clientId"), 128),
        "type": clean_text(record.get("type") or record.get("templateType"), 32) or template_type,
        "title": clean_text(record.get("title"), 200) or ("天赋模板" if template_type == "talent" else "装备模板"),
        "rawString": clean_text(record.get("rawString") or record.get("raw_string"), 20000),
        "classKey": clean_text(record.get("classKey") or record.get("class_key"), 64),
        "className": clean_text(record.get("className") or record.get("class_name"), 100),
        "specKey": clean_text(record.get("specKey") or record.get("spec_key"), 64),
        "specName": clean_text(record.get("specName") or record.get("spec_name"), 100),
        "heroKey": clean_text(record.get("heroKey") or record.get("hero_key"), 64),
        "heroLabel": clean_text(record.get("heroLabel") or record.get("hero_label"), 100),
        "scenarioKey": clean_text(record.get("scenarioKey") or record.get("scenario_key"), 64),
        "scenarioTitle": clean_text(record.get("scenarioTitle") or record.get("scenario_title"), 120),
        "status": clean_text(record.get("status"), 64),
        "source": clean_text(record.get("source"), 120),
        "metadata": metadata,
    }


def simcraft_template_unique_messages(values):
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def simcraft_template_has_verified_stat_snapshot(source, gear_template):
    request = source if isinstance(source, dict) else {}
    template = gear_template if isinstance(gear_template, dict) else {}
    metadata = template.get("metadata") if isinstance(template.get("metadata"), dict) else {}
    candidates = [
        metadata.get("statSnapshot"),
        metadata.get("gearStatSnapshot"),
        request.get("statSnapshot"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("statStatus") == "verified":
            return True
    return False


def simcraft_template_gear_snapshot_raw(metadata):
    source = metadata if isinstance(metadata, dict) else {}
    snapshot = source.get("gearSnapshot")
    if isinstance(snapshot, dict):
        return json.dumps(snapshot, ensure_ascii=False)
    if isinstance(snapshot, str):
        return clean_text(snapshot, 20000)
    return ""


def simcraft_template_effective_gear_raw(raw_string, metadata=None):
    text = str(raw_string or "").strip()
    snapshot_raw = simcraft_template_gear_snapshot_raw(metadata)
    if snapshot_raw and not text.startswith("{"):
        return snapshot_raw
    return text


def parse_simcraft_template_gear_line(line):
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts or "=" not in parts[0]:
        return None, f"invalid gear line: {text[:80]}"
    slot_key, _, name = parts[0].partition("=")
    slot = normalize_simc_slot(slot_key)
    if not slot:
        return None, f"invalid gear slot: {slot_key}"
    item = {"slot": slot, "name": name.strip()}
    for part in parts[1:]:
        key, separator, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            continue
        item[key] = value
    normalized = clean_simc_gear_items([item], limit=1)
    if not normalized:
        return None, f"missing item id for gear slot: {slot}"
    return normalized[0], ""


def parse_simcraft_template_gear_raw(raw_string, class_key="", spec_key="", conn=None, metadata=None):
    text = simcraft_template_effective_gear_raw(raw_string, metadata)
    if text.startswith("{"):
        payload = build_websim_profile_response(
            {
                "classKey": class_key,
                "specKey": spec_key,
                "rawString": text,
            },
            conn=conn,
        )
        readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
        enhancement = readiness.get("enhancement") if isinstance(readiness.get("enhancement"), dict) else {}
        items = payload.get("simcItems") if isinstance(payload.get("simcItems"), list) else []
        seen_slots = {item.get("slot") for item in items if isinstance(item, dict)}
        errors = []
        missing_required = set(readiness.get("missingRequiredSlots") if isinstance(readiness.get("missingRequiredSlots"), list) else [])
        missing_core = set(readiness.get("missingCoreSlots") if isinstance(readiness.get("missingCoreSlots"), list) else [])
        required_slots = [
            slot
            for slot in SIMCRAFT_TEMPLATE_REQUIRED_GEAR_SLOTS
            if not (slot == "off_hand" and readiness.get("fullReady") and slot in missing_required and slot not in missing_core)
        ]
        missing_slots = [slot for slot in required_slots if slot not in seen_slots]
        if missing_slots:
            errors.append(f"missing gear slots: {', '.join(missing_slots)}")
        errors.extend([str(item) for item in (enhancement.get("blockers") or []) if str(item or "").strip()])
        return items, errors
    errors = []
    items = []
    seen_slots = set()
    for line in text.splitlines():
        item, error = parse_simcraft_template_gear_line(line)
        if error:
            errors.append(error)
            continue
        if not item:
            continue
        if item["slot"] in seen_slots:
            errors.append(f"duplicate gear slot: {item['slot']}")
            continue
        seen_slots.add(item["slot"])
        items.append(item)
    missing_slots = [slot for slot in SIMCRAFT_TEMPLATE_REQUIRED_GEAR_SLOTS if slot not in seen_slots]
    if missing_slots:
        errors.append(f"missing gear slots: {', '.join(missing_slots)}")
    return items if not errors else [], errors


def simcraft_template_empty_readiness(template_type, checked_at=None):
    return {
        "status": "blocked",
        "profileSource": "",
        "checkedAt": checked_at or utc_now(),
        "blockers": [],
        "warnings": [],
        "talent": {} if template_type == "talent" else None,
        "gear": {} if template_type == "gear" else None,
    }


def simcraft_template_talent_readiness(record, conn=None):
    template = simcraft_template_record(record, "talent")
    readiness = simcraft_template_empty_readiness("talent")
    blockers = []
    if template["type"] != "talent":
        blockers.append("talent template is required")
    context, errors = simcraft_template_talent_context(conn, template)
    blockers.extend(errors)
    blockers = simcraft_template_unique_messages(blockers)
    readiness.update({
        "status": "blocked" if blockers else "ready",
        "profileSource": "" if blockers else "template",
        "blockers": blockers,
        "talent": {
            "encodingStatus": context.get("encodingStatus", ""),
            "simcLineCount": len(context.get("simcLines") or []),
            "hasImportCode": bool(context.get("importCode")),
            "selectedNodeCount": len(context.get("selectedNodes") or []),
            "heroKey": context.get("heroKey", "") or template.get("heroKey", ""),
        },
    })
    return readiness


def simcraft_template_gear_readiness(record, conn=None):
    template = simcraft_template_record(record, "gear")
    readiness = simcraft_template_empty_readiness("gear")
    blockers = []
    if template["type"] != "gear":
        blockers.append("gear template is required")
    if template["status"] not in SIMCRAFT_TEMPLATE_READY_GEAR_STATUSES:
        blockers.append("gear template must be complete")
    gear_items, errors = parse_simcraft_template_gear_raw(
        template.get("rawString"),
        template.get("classKey") or "",
        template.get("specKey") or "",
        conn=conn,
        metadata=template.get("metadata") or {},
    )
    blockers.extend(errors)
    blockers = simcraft_template_unique_messages(blockers)
    parsed_slots = [item.get("slot", "") for item in gear_items if isinstance(item, dict)]
    snapshot_raw = simcraft_template_gear_snapshot_raw(template.get("metadata") or {})
    raw_string = str(template.get("rawString") or "").strip()
    readiness.update({
        "status": "blocked" if blockers else "ready",
        "profileSource": "" if blockers else "template",
        "blockers": blockers,
        "gear": {
            "parsedSlots": parsed_slots,
            "parsedSlotCount": len(parsed_slots),
            "requiredSlots": SIMCRAFT_TEMPLATE_REQUIRED_GEAR_SLOTS,
            "rawSource": "metadata.gearSnapshot" if snapshot_raw and not raw_string.startswith("{") else "rawString",
        },
    })
    return readiness


def simcraft_template_readiness(record, conn=None):
    source = record if isinstance(record, dict) else {}
    if conn is None:
        with db_connection() as active_conn:
            return simcraft_template_readiness(source, conn=active_conn)
    template_type = clean_text(source.get("type") or source.get("templateType"), 32)
    if template_type == "talent":
        return simcraft_template_talent_readiness(source, conn=conn)
    if template_type == "gear":
        return simcraft_template_gear_readiness(source, conn=conn)
    readiness = simcraft_template_empty_readiness(template_type or "unknown")
    readiness["blockers"] = ["invalid build template type"]
    return readiness


def simcraft_template_talent_context(conn, talent_template):
    raw_string = str(talent_template.get("rawString") or "").strip()
    if not raw_string:
        return {}, ["talent template rawString is required"]
    parsed = parse_websim_talent_export_code(raw_string)
    if parsed:
        expected_class = talent_template.get("classKey") or ""
        expected_spec = talent_template.get("specKey") or ""
        errors = []
        if expected_class and parsed.get("classKey") != expected_class:
            errors.append("talent rawString class mismatch")
        if expected_spec and parsed.get("specKey") != expected_spec:
            errors.append("talent rawString spec mismatch")
        if errors:
            return {}, errors
        encoding_source = {**talent_template, **parsed}
        encoding = encode_websim_talents(conn, encoding_source)
        if encoding.get("status") != "encoded":
            return {}, [str(item) for item in (encoding.get("errors") or ["WebSim talent encoding failed"])]
        return {
            "importCode": "",
            "simcLines": list(encoding.get("lines") or []),
            "encodingStatus": "encoded",
            "sourceName": talent_template.get("source") or "WebSim 天赋模板",
            "websimExportCode": raw_string.replace("talents=", "", 1).strip(),
            "selectedNodes": (parsed.get("talentState") or {}).get("selectedNodes") or [],
            "heroKey": parsed.get("heroKey") or talent_template.get("heroKey") or "",
        }, []
    import_code = raw_string
    if import_code.startswith("talents="):
        import_code = import_code.split("=", 1)[1].strip()
    if not import_code:
        return {}, ["talent import code is required"]
    if import_code.startswith("websim:"):
        return {}, ["websim talent code could not be parsed"]
    return {
        "importCode": import_code,
        "simcLines": [],
        "encodingStatus": "external",
        "sourceName": talent_template.get("source") or "官方天赋导入码",
        "websimExportCode": "",
        "selectedNodes": [],
        "heroKey": talent_template.get("heroKey") or "",
    }, []


def prepare_simcraft_template_request(request_payload):
    source = request_payload if isinstance(request_payload, dict) else {}
    template_context = source.get("templateContext") if isinstance(source.get("templateContext"), dict) else {}
    talent_template = simcraft_template_record(template_context.get("talent"), "talent")
    gear_template = simcraft_template_record(template_context.get("gear"), "gear")
    scenario_key = clean_text(source.get("scenarioKey"), 64) or "single"
    analysis_type = clean_text(source.get("analysisType"), 64) or "baseline"
    race_key = normalize_simc_race(source.get("raceKey") or source.get("race"))
    race_name = clean_text(source.get("raceName"), 80)
    source_validation = source.get("templateValidation") if isinstance(source.get("templateValidation"), dict) else {}
    errors = []
    errors.extend([str(item) for item in source_validation.get("errors") or [] if str(item or "").strip()])
    if scenario_key not in SIMCRAFT_TEMPLATE_SCENARIOS:
        errors.append(f"unsupported scenario: {scenario_key}")
    if analysis_type not in SIMCRAFT_TEMPLATE_ANALYSIS_TYPES:
        errors.append(f"unsupported analysis type: {analysis_type}")
    if talent_template["type"] != "talent":
        errors.append("talent template is required")
    if gear_template["type"] != "gear":
        errors.append("gear template is required")
    if not talent_template["classKey"] or not talent_template["specKey"]:
        errors.append("talent template class/spec is required")
    if not gear_template["classKey"] or not gear_template["specKey"]:
        errors.append("gear template class/spec is required")
    if (
        talent_template["classKey"]
        and gear_template["classKey"]
        and talent_template["specKey"]
        and gear_template["specKey"]
        and (talent_template["classKey"], talent_template["specKey"]) != (gear_template["classKey"], gear_template["specKey"])
    ):
        errors.append("template class/spec mismatch")
    if gear_template["status"] not in SIMCRAFT_TEMPLATE_READY_GEAR_STATUSES:
        errors.append("gear template must be complete")

    if postgres_only_runtime_enabled():
        talent_context, talent_errors = simcraft_template_talent_context(None, talent_template)
        gear_items, gear_errors = parse_simcraft_template_gear_raw(
            gear_template.get("rawString"),
            gear_template.get("classKey") or "",
            gear_template.get("specKey") or "",
            conn=None,
            metadata=gear_template.get("metadata") or {},
        )
    else:
        with db_connection() as conn:
            talent_context, talent_errors = simcraft_template_talent_context(conn, talent_template)
            gear_items, gear_errors = parse_simcraft_template_gear_raw(
                gear_template.get("rawString"),
                gear_template.get("classKey") or "",
                gear_template.get("specKey") or "",
                conn=conn,
                metadata=gear_template.get("metadata") or {},
            )
    errors.extend(talent_errors)
    errors.extend(gear_errors)
    compatibility_errors = simcraft_known_compatibility_blockers(
        talent_template.get("classKey"),
        talent_template.get("specKey"),
        (talent_context or {}).get("heroKey") or talent_template.get("heroKey"),
        scenario_key,
    )
    errors.extend(compatibility_errors)
    if not compatibility_errors and not simcraft_template_has_verified_stat_snapshot(source, gear_template):
        errors.append(SIMCRAFT_TEMPLATE_STAT_SNAPSHOT_REQUIRED_ERROR)

    scenario = SIMCRAFT_TEMPLATE_SCENARIOS.get(scenario_key) or SIMCRAFT_TEMPLATE_SCENARIOS["single"]
    simc_items = gear_items
    build_context = {
        "specId": f'{talent_template.get("classKey")}-{talent_template.get("specKey")}',
        "className": talent_template.get("className") or talent_template.get("classKey"),
        "specName": talent_template.get("specName") or talent_template.get("specKey"),
        "raceKey": race_key,
        "raceName": race_name,
        "role": "",
        "activeQueryKey": "simcraft_template",
        "activeQueryTitle": "SimC 模板组合",
        "sourceName": "个人模板库",
        "analysisWindow": scenario["label"],
        "sourceNote": "天赋模板和装备模板来自玩家已保存模板；场景由当前 SimC 页面预设决定。",
        "details": {
            "talents": {
                "importCode": talent_context.get("importCode", ""),
                "simcLines": talent_context.get("simcLines", []),
                "encodingStatus": talent_context.get("encodingStatus", ""),
                "sourceName": talent_context.get("sourceName", ""),
                "sourceUrl": "",
                "coreTalents": [],
            },
            "gear": {
                "gear": [
                    {"slot": item.get("slot", ""), "name": item.get("name", ""), "source": gear_template.get("title", "")}
                    for item in simc_items
                ],
                "simcItems": simc_items,
            },
            "statWeights": {"stats": []},
        },
        "simulatorState": {
            "profileOptions": {
                "raceKey": race_key,
                "raceName": race_name,
            },
            "talent": {
                "selectedNodes": talent_context.get("selectedNodes", []),
                "websimExportCode": talent_context.get("websimExportCode", ""),
                "heroKey": talent_context.get("heroKey", ""),
                "scenarioKey": scenario_key,
                "encodingStatus": talent_context.get("encodingStatus", ""),
                "simcLines": talent_context.get("simcLines", []),
                "importCode": talent_context.get("importCode", ""),
                "summary": talent_template.get("title", ""),
                "simcHint": scenario["label"],
            },
            "gear": {
                "selectedItems": simc_items,
                "progressText": f"{len(simc_items)}/16 槽可解析",
                "nextAction": "" if not errors else "补齐完整装备模板后再提交",
            },
        },
    }
    prepared = dict(source)
    prepared.update({
        "mode": "simcraft_template",
        "raceKey": race_key,
        "raceName": race_name,
        "scenarioKey": scenario_key,
        "analysisType": analysis_type,
        "message": f"{build_context['specName']}{build_context['className']} · {scenario['label']} · {analysis_type}",
        "prompt": f"{build_context['specName']}{build_context['className']} · {scenario['label']} · {analysis_type}",
        "buildContext": build_context,
        "gearSelection": {"items": simc_items},
        "templateContext": {"talent": talent_template, "gear": gear_template},
        "templateValidation": {
            "passed": not errors,
            "errors": errors,
            "warnings": [],
            "requiredGearSlots": SIMCRAFT_TEMPLATE_REQUIRED_GEAR_SLOTS,
            "parsedGearSlots": [item.get("slot", "") for item in simc_items],
        },
    })
    return prepared


def should_store_simulator_task(request_payload, analysis):
    if not isinstance(request_payload, dict) or not isinstance(analysis, dict):
        return True
    if request_payload.get("mode") != "simcraft_template":
        return True
    agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
    simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
    return agent.get("status") == "simc_completed" and bool(simulation.get("ran"))


SIMCRAFT_TEMPLATE_TASK_ACTIVE_STATUSES = {"queued", "running"}


def simcraft_template_active_task_limit():
    return max(1, int_env("WOW_SIMC_TEMPLATE_ACTIVE_TASK_LIMIT", 2))


def simcraft_template_active_limit_message(active_count, limit):
    return f"已有 {active_count} 个模拟任务正在排队或运行，请等待前面的任务完成后再提交。"


def is_simcraft_template_final_submit(request_payload):
    source = request_payload if isinstance(request_payload, dict) else {}
    return (
        source.get("mode") == "simcraft_template"
        and bool(source.get("saveTask"))
        and not bool(source.get("confirmOnly"))
    )


def json_clone(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def simcraft_template_task_fingerprint(request_payload):
    source = request_payload if isinstance(request_payload, dict) else {}
    build_context = source.get("buildContext") if isinstance(source.get("buildContext"), dict) else {}
    details = build_context.get("details") if isinstance(build_context.get("details"), dict) else {}
    template_context = source.get("templateContext") if isinstance(source.get("templateContext"), dict) else {}
    talent = template_context.get("talent") if isinstance(template_context.get("talent"), dict) else {}
    gear = template_context.get("gear") if isinstance(template_context.get("gear"), dict) else {}
    fingerprint_source = {
        "mode": "simcraft_template",
        "classKey": source.get("classKey") or talent.get("classKey") or gear.get("classKey") or "",
        "raceKey": source.get("raceKey") or build_context.get("raceKey") or "",
        "scenarioKey": source.get("scenarioKey") or "single",
        "analysisType": source.get("analysisType") or "baseline",
        "talent": {
            "id": talent.get("id") or talent.get("clientId") or "",
            "rawString": talent.get("rawString") or "",
            "classKey": talent.get("classKey") or "",
            "specKey": talent.get("specKey") or "",
            "heroKey": talent.get("heroKey") or "",
        },
        "gear": {
            "id": gear.get("id") or gear.get("clientId") or "",
            "rawString": gear.get("rawString") or "",
            "classKey": gear.get("classKey") or "",
            "specKey": gear.get("specKey") or "",
            "status": gear.get("status") or "",
        },
        "talentInput": (details.get("talents") or {}) if isinstance(details.get("talents"), dict) else {},
        "gearItems": (source.get("gearSelection") or {}).get("items") if isinstance(source.get("gearSelection"), dict) else [],
    }
    encoded = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def simulator_task_owner_payload(user):
    return {
        "id": user["id"],
        "openid": user["openid"],
        "nickname": user["nickname"],
        "avatarUrl": user["avatarUrl"],
    }


def iso_elapsed_ms(started_at, finished_at):
    try:
        start = datetime.fromisoformat(str(started_at or ""))
        finish = datetime.fromisoformat(str(finished_at or ""))
    except ValueError:
        return None
    return max(0, int((finish - start).total_seconds() * 1000))


def simcraft_template_state(analysis, row_status=""):
    status = str(row_status or analysis.get("status") or "").strip()
    if status in {"queued", "running", "completed", "failed", "blocked"}:
        return status
    agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
    simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
    agent_status = str(agent.get("status") or "").strip()
    if agent_status == "template_ready":
        return "ready"
    if agent_status in {"template_blocked", "template_invalid"}:
        return "blocked"
    if agent_status == "simc_queued":
        return "queued"
    if agent_status == "simc_running":
        return "running"
    if agent_status == "simc_completed" and simulation.get("ran"):
        return "completed"
    if agent_status == "simc_failed":
        return "failed"
    if simulation.get("ran"):
        return "completed"
    if simulation.get("error"):
        return "failed"
    return "ready"


def simcraft_template_report_messages(state, analysis, dps):
    agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
    simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
    validation = agent.get("validation") if isinstance(agent.get("validation"), dict) else {}
    blockers = []
    for item in validation.get("errors") or []:
        append_unique_text(blockers, item)
    if state in {"blocked", "failed"}:
        append_unique_text(blockers, simulation.get("error"))
    warnings = []
    for item in validation.get("warnings") or []:
        append_unique_text(warnings, item)
    next_actions_by_state = {
        "ready": ["Submit this template combination to run SimC."],
        "queued": ["Open the task list after the backend SimC run finishes."],
        "running": ["Wait for the backend SimC run to finish; the result will update in the task list."],
        "completed": ["Use this result as the baseline for this saved template combination."],
        "failed": ["Review the SimC error, template data, and SimC version before submitting again."],
        "blocked": ["Fix the template blockers before submitting a SimC task."],
    }
    evidence_refs = []
    if dps:
        evidence_refs.append("simc.dps")
    if state in {"ready", "queued", "running", "blocked"}:
        evidence_refs.append("simc.template")
    if blockers:
        evidence_refs.append("simc.error")
    return {
        "blockers": blockers,
        "warnings": warnings,
        "nextActions": next_actions_by_state.get(state, []),
        "evidenceRefs": evidence_refs,
    }


def simcraft_template_report_summary(state, dps, blockers):
    if state == "ready":
        return "Template payload validated; submit to run SimC."
    if state == "queued":
        return "SimC task accepted and queued; results will appear in the task list."
    if state == "running":
        return "SimC task is running; results will appear in the task list."
    if state == "completed" and dps:
        return f"SimC completed with {dps} DPS."
    if state == "completed":
        return "SimC completed but no parseable DPS was found."
    if state == "blocked":
        return "; ".join(blockers[:3]) if blockers else "Template validation blocked this SimC task."
    if state == "failed":
        return "; ".join(blockers[:3]) if blockers else "SimC did not complete."
    return "SimC report is not available yet."


def simcraft_template_report_timing(analysis, timing=None):
    source = timing if isinstance(timing, dict) else analysis.get("taskTiming")
    source = source if isinstance(source, dict) else {}
    queued_at = clean_text(source.get("queuedAt") or analysis.get("createdAt"), 64)
    started_at = clean_text(source.get("startedAt"), 64)
    finished_at = clean_text(source.get("finishedAt"), 64)
    elapsed_ms = source.get("elapsedMs")
    if elapsed_ms is None and started_at and finished_at:
        elapsed_ms = iso_elapsed_ms(started_at, finished_at)
    return {
        "queuedAt": queued_at,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "elapsedMs": elapsed_ms,
    }


SIMCRAFT_TEMPLATE_REPORT_SECONDARY_STATS = {"crit", "haste", "mastery", "versatility"}


def simcraft_template_report_stat_metric(source):
    row = source if isinstance(source, dict) else {}
    key = clean_text(row.get("key"), 64)
    label = clean_text(row.get("label"), 80)
    value = clean_text(row.get("value"), 64)
    converted_value = clean_text(row.get("convertedValue"), 64)
    metric = {}
    if key:
        metric["key"] = key
    if label:
        metric["label"] = label
    if value:
        metric["value"] = value
    if converted_value:
        metric["convertedValue"] = converted_value
    for numeric_key in ("rawValue", "convertedRawValue"):
        numeric_value = row.get(numeric_key)
        if isinstance(numeric_value, (int, float)) and not isinstance(numeric_value, bool):
            metric[numeric_key] = numeric_value
    return metric


def simcraft_template_report_stat_snapshot(source):
    snapshot = source if isinstance(source, dict) else {}
    if snapshot.get("statStatus") != "verified":
        return {}
    primary = simcraft_template_report_stat_metric(snapshot.get("primary"))
    secondary = []
    for row in snapshot.get("secondary") or []:
        metric = simcraft_template_report_stat_metric(row)
        if metric.get("key") in SIMCRAFT_TEMPLATE_REPORT_SECONDARY_STATS:
            secondary.append(metric)
    result = {
        "statStatus": "verified",
        "primary": primary,
        "secondary": secondary,
    }
    stat_source = clean_text(snapshot.get("statSource"), 80)
    if stat_source:
        result["statSource"] = stat_source
    return result


def simcraft_template_report_stat_snapshot_from_request(request, build_context, gear_template):
    details = build_context.get("details") if isinstance(build_context.get("details"), dict) else {}
    gear_details = details.get("gear") if isinstance(details.get("gear"), dict) else {}
    metadata = gear_template.get("metadata") if isinstance(gear_template.get("metadata"), dict) else {}
    candidates = [
        metadata.get("statSnapshot"),
        metadata.get("gearStatSnapshot"),
        request.get("statSnapshot") if isinstance(request, dict) else None,
        gear_details.get("statSnapshot"),
    ]
    for candidate in candidates:
        snapshot = simcraft_template_report_stat_snapshot(candidate)
        if snapshot:
            return snapshot
    return {}


def simcraft_template_report_stat_snapshot_from_analysis(analysis):
    source = analysis if isinstance(analysis, dict) else {}
    report = source.get("simcReport") if isinstance(source.get("simcReport"), dict) else {}
    build = report.get("build") if isinstance(report.get("build"), dict) else {}
    return simcraft_template_report_stat_snapshot(build.get("statSnapshot"))


def simcraft_template_stat_snapshot_request_payload(request):
    source = request if isinstance(request, dict) else {}
    template_context = source.get("templateContext") if isinstance(source.get("templateContext"), dict) else {}
    talent = template_context.get("talent") if isinstance(template_context.get("talent"), dict) else {}
    gear = template_context.get("gear") if isinstance(template_context.get("gear"), dict) else {}
    metadata = gear.get("metadata") if isinstance(gear.get("metadata"), dict) else {}
    gear_snapshot = metadata.get("gearSnapshot") if isinstance(metadata.get("gearSnapshot"), dict) else None
    raw_string = str(gear.get("rawString") or "").strip()
    if not raw_string and gear_snapshot:
        raw_string = json.dumps(gear_snapshot, ensure_ascii=False)
    talents = str(talent.get("rawString") or "").strip()
    if not raw_string or not talents:
        return {}
    payload = {
        "classKey": clean_text(source.get("classKey") or gear.get("classKey") or talent.get("classKey"), 64),
        "specKey": clean_text(source.get("specKey") or gear.get("specKey") or talent.get("specKey"), 64),
        "raceKey": clean_text(source.get("raceKey"), 64),
        "level": source.get("level") or metadata.get("maxLevel") or 90,
        "scenarioKey": clean_text(source.get("scenarioKey") or gear.get("scenarioKey"), 64),
        "talents": talents,
        "rawString": raw_string,
        "metadata": {},
    }
    if gear_snapshot:
        payload["metadata"]["gearSnapshot"] = gear_snapshot
    return payload


def backfill_simcraft_template_detail_stat_snapshot(task_id, row_status, request_payload, analysis_payload):
    if simcraft_template_report_stat_snapshot_from_analysis(analysis_payload):
        return analysis_payload
    stats_request = simcraft_template_stat_snapshot_request_payload(request_payload)
    if not stats_request:
        return analysis_payload
    with db_connection() as conn:
        try:
            snapshot = simcraft_template_report_stat_snapshot(
                build_websim_gear_stats_response(stats_request, conn=conn)
            )
        except Exception:
            return analysis_payload
        if not snapshot:
            return analysis_payload
        updated = json_clone(analysis_payload if isinstance(analysis_payload, dict) else {})
        report = updated.get("simcReport") if isinstance(updated.get("simcReport"), dict) else None
        if not report:
            report = build_simcraft_template_report({**updated, "request": request_payload}, row_status=row_status)
        build = report.get("build") if isinstance(report.get("build"), dict) else {}
        build["statSnapshot"] = snapshot
        report["build"] = build
        updated["simcReport"] = report
        conn.execute(
            "UPDATE simulator_tasks SET analysis_json = ? WHERE id = ?",
            (json.dumps(updated, ensure_ascii=False), task_id),
        )
        return updated


def build_simcraft_template_report(analysis, row_status="", timing=None):
    source = analysis if isinstance(analysis, dict) else {}
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    build_context = request.get("buildContext") if isinstance(request.get("buildContext"), dict) else {}
    template_context = request.get("templateContext") if isinstance(request.get("templateContext"), dict) else {}
    talent = template_context.get("talent") if isinstance(template_context.get("talent"), dict) else {}
    gear = template_context.get("gear") if isinstance(template_context.get("gear"), dict) else {}
    simulation = source.get("simulation") if isinstance(source.get("simulation"), dict) else {}
    metrics = simulation.get("metrics") if isinstance(simulation.get("metrics"), dict) else {}
    dps = clean_text(metrics.get("dps"), 64)
    state = simcraft_template_state(source, row_status=row_status)
    messages = simcraft_template_report_messages(state, source, dps)
    scenario_key = clean_text(request.get("scenarioKey"), 64) or "single"
    scenario = dict(SIMCRAFT_TEMPLATE_SCENARIOS.get(scenario_key) or SIMCRAFT_TEMPLATE_SCENARIOS["single"])
    scenario["key"] = scenario_key
    class_name = clean_text(build_context.get("className") or talent.get("className") or gear.get("className"), 80)
    spec_name = clean_text(build_context.get("specName") or talent.get("specName") or gear.get("specName"), 80)
    title_subject = f"{spec_name}{class_name}".strip() or "Template"
    summary = simcraft_template_report_summary(state, dps, messages["blockers"])
    stat_snapshot = simcraft_template_report_stat_snapshot_from_request(request, build_context, gear)
    build_payload = {
        "classKey": clean_text(talent.get("classKey") or gear.get("classKey"), 64),
        "specKey": clean_text(talent.get("specKey") or gear.get("specKey"), 64),
        "className": class_name,
        "specName": spec_name,
        "heroKey": clean_text(build_context.get("heroKey") or talent.get("heroKey") or gear.get("heroKey"), 64),
        "heroLabel": clean_text(build_context.get("heroLabel") or talent.get("heroLabel") or gear.get("heroLabel"), 100),
        "raceKey": clean_text(request.get("raceKey") or build_context.get("raceKey"), 64),
        "raceName": clean_text(request.get("raceName") or build_context.get("raceName"), 80),
        "talentTemplate": {
            "id": clean_text(talent.get("id") or talent.get("clientId"), 128),
            "title": clean_text(talent.get("title") or talent.get("name"), 160),
        },
        "gearTemplate": {
            "id": clean_text(gear.get("id") or gear.get("clientId"), 128),
            "title": clean_text(gear.get("title") or gear.get("name"), 160),
        },
    }
    if stat_snapshot:
        build_payload["statSnapshot"] = stat_snapshot
    preparation = request.get("preparation") if isinstance(request.get("preparation"), dict) else {}
    if not preparation:
        temporary_buffs = request.get("temporaryBuffs") if isinstance(request.get("temporaryBuffs"), dict) else {}
        preparation = simc_preparation_report(
            simc_preparation_payload(build_payload.get("classKey"), build_payload.get("specKey"), temporary_buffs=temporary_buffs)
        )
    return {
        "schemaRevision": "simc-report-v2",
        "state": state,
        "title": f"{title_subject} SimC",
        "summary": summary,
        "statusText": state,
        "profileSource": "template",
        "scenario": {
            "key": scenario_key,
            "label": scenario.get("label", ""),
            "fightStyle": scenario.get("fightStyle", ""),
            "targets": scenario.get("targets", 0),
            "durationSeconds": scenario.get("durationSeconds", 0),
        },
        "preparation": preparation,
        "build": build_payload,
        "result": {
            "ran": bool(simulation.get("ran")),
            "hasDps": bool(dps),
            "dps": dps,
            "dpsDisplay": f"{dps} DPS" if dps else "",
            "metricLabel": clean_text(simulation.get("metricLabel"), 64) or "DPS",
            "metricUnit": clean_text(simulation.get("metricUnit"), 64) or "伤害/秒",
        },
        "timing": simcraft_template_report_timing(source, timing=timing),
        "messages": messages,
    }


def attach_simcraft_template_report(analysis, row_status="", timing=None):
    if not isinstance(analysis, dict) or analysis.get("mode") != "simcraft_template":
        return analysis
    analysis["simcReport"] = build_simcraft_template_report(analysis, row_status=row_status, timing=timing)
    return analysis


def merge_non_empty_dict(preferred, fallback):
    result = dict(fallback if isinstance(fallback, dict) else {})
    for key, value in (preferred if isinstance(preferred, dict) else {}).items():
        if value not in (None, "", [], {}):
            result[key] = value
    return result


def merge_simcraft_template_report_for_summary(report, rebuilt_report):
    if not isinstance(report, dict):
        return rebuilt_report if isinstance(rebuilt_report, dict) else {}
    merged = {**(rebuilt_report if isinstance(rebuilt_report, dict) else {}), **report}
    for key in ("build", "scenario", "timing", "result", "messages", "preparation"):
        merged[key] = merge_non_empty_dict(report.get(key), (rebuilt_report or {}).get(key))
    return merged


def simcraft_template_report_summary_payload(analysis, row_status="", updated_at="", request_payload=None):
    source = analysis if isinstance(analysis, dict) else {}
    request_fallback = request_payload if isinstance(request_payload, dict) else {}
    if request_fallback and not isinstance(source.get("request"), dict):
        source = {**source, "request": request_fallback}
    report = source.get("simcReport") if isinstance(source.get("simcReport"), dict) else None
    report_build = report.get("build") if isinstance(report, dict) and isinstance(report.get("build"), dict) else {}
    report_timing = report.get("timing") if isinstance(report, dict) and isinstance(report.get("timing"), dict) else {}
    missing_build_context = any(
        report_build.get(key) in (None, "")
        for key in ("className", "specName", "heroKey", "raceName")
    )
    if not report or missing_build_context or not report_timing:
        report = merge_simcraft_template_report_for_summary(
            report,
            build_simcraft_template_report(source, row_status=row_status),
        )
        report_build = report.get("build") if isinstance(report.get("build"), dict) else {}
        report_timing = report.get("timing") if isinstance(report.get("timing"), dict) else {}
    summary_build = {
        key: report_build.get(key, "")
        for key in ("classKey", "specKey", "className", "specName", "heroKey", "heroLabel", "raceKey", "raceName")
        if report_build.get(key, "") not in (None, "")
    }
    summary_timing = {
        "queuedAt": report_timing.get("queuedAt", ""),
        "startedAt": report_timing.get("startedAt", ""),
        "finishedAt": report_timing.get("finishedAt", ""),
        "elapsedMs": report_timing.get("elapsedMs"),
    }
    return {
        "state": report.get("state", row_status or ""),
        "title": report.get("title", ""),
        "summary": report.get("summary", ""),
        "dpsDisplay": (report.get("result") or {}).get("dpsDisplay", ""),
        "scenario": report.get("scenario") or {},
        "preparation": report.get("preparation") or {},
        "build": summary_build,
        "timing": summary_timing,
        "statusText": report.get("statusText", ""),
        "updatedAt": updated_at,
    }


def merge_simcraft_template_task_summary(stored_summary, generated_summary):
    if not isinstance(stored_summary, dict) or not stored_summary:
        return generated_summary
    merged = {**(generated_summary if isinstance(generated_summary, dict) else {}), **stored_summary}
    for key in ("build", "scenario", "timing", "preparation"):
        merged[key] = merge_non_empty_dict(stored_summary.get(key), (generated_summary or {}).get(key))
    return merged


def backfill_simulator_task_summaries(conn):
    rows = conn.execute(
        """
        SELECT id, status, request_json, analysis_json, summary_json, updated_at
        FROM simulator_tasks
        WHERE mode = 'simcraft_template'
        """
    ).fetchall()
    for row in rows:
        request_payload = safe_json_loads(row[2], {}, f"simulator task request {row[0]}")
        analysis_payload = safe_json_loads(row[3], {}, f"simulator task analysis {row[0]}")
        stored_summary = safe_json_loads(row[4], {}, f"simulator task summary {row[0]}")
        generated_summary = simcraft_template_report_summary_payload(
            analysis_payload,
            row_status=row[1],
            updated_at=row[5],
            request_payload=request_payload,
        )
        merged_summary = merge_simcraft_template_task_summary(stored_summary, generated_summary)
        if merged_summary != stored_summary:
            conn.execute(
                "UPDATE simulator_tasks SET summary_json = ? WHERE id = ?",
                (json.dumps(merged_summary, ensure_ascii=False), row[0]),
            )


def public_simcraft_template_request(request_payload):
    request = json_clone(request_payload if isinstance(request_payload, dict) else {})
    request.pop("profile", None)
    request.pop("guestId", None)
    request.pop("_executeSimcTask", None)
    template_context = request.get("templateContext") if isinstance(request.get("templateContext"), dict) else {}
    slim_context = {}
    for key in ("talent", "gear"):
        template = template_context.get(key) if isinstance(template_context.get(key), dict) else {}
        slim_context[key] = {
            field: template.get(field)
            for field in (
                "id",
                "clientId",
                "type",
                "templateType",
                "title",
                "name",
                "classKey",
                "className",
                "specKey",
                "specName",
                "heroKey",
                "heroLabel",
                "status",
                "updatedAt",
            )
            if template.get(field) not in (None, "")
        }
    if slim_context:
        request["templateContext"] = slim_context
    return request


def public_simcraft_template_analysis(analysis, row_status="", strip_profile=False):
    if not isinstance(analysis, dict) or analysis.get("mode") != "simcraft_template":
        return analysis
    public = json_clone(analysis)
    existing_report = public.get("simcReport") if isinstance(public.get("simcReport"), dict) else {}
    existing_build = existing_report.get("build") if isinstance(existing_report.get("build"), dict) else {}
    existing_stat_snapshot = simcraft_template_report_stat_snapshot(existing_build.get("statSnapshot"))
    attach_simcraft_template_report(public, row_status=row_status)
    if existing_stat_snapshot:
        report = public.get("simcReport") if isinstance(public.get("simcReport"), dict) else {}
        build = report.get("build") if isinstance(report.get("build"), dict) else {}
        build["statSnapshot"] = existing_stat_snapshot
        report["build"] = build
        public["simcReport"] = report
    public.pop("llm", None)
    public.pop("codex", None)
    public.pop("allowedNumbers", None)
    if strip_profile:
        public["request"] = public_simcraft_template_request(public.get("request") or {})
        agent = public.get("agent") if isinstance(public.get("agent"), dict) else {}
        agent.pop("draftProfile", None)
        public["agent"] = agent
    simulation = public.get("simulation") if isinstance(public.get("simulation"), dict) else {}
    simulation["summary"] = ""
    public["simulation"] = simulation
    public["stages"] = [
        stage for stage in (public.get("stages") or [])
        if not (isinstance(stage, dict) and stage.get("key") == "ai_interpretation")
    ]
    return public


def simcraft_template_queue_analysis(confirm_analysis, request_payload, task_id, user, fingerprint, task_lock=None, timing=None):
    analysis = json_clone(confirm_analysis)
    request = analysis.get("request") if isinstance(analysis.get("request"), dict) else {}
    request["confirmOnly"] = False
    request["saveTask"] = True
    request["runSimulation"] = False
    request["simcTaskFingerprint"] = fingerprint
    analysis["request"] = request
    analysis["taskId"] = task_id
    analysis["status"] = "queued"
    analysis["owner"] = simulator_task_owner_payload(user)
    analysis["taskLock"] = task_lock or {
        "active": True,
        "taskId": task_id,
        "status": "queued",
        "reason": "simc_task_queued",
    }
    if timing:
        analysis["taskTiming"] = timing
    agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
    agent["status"] = "simc_queued"
    agent["canSubmitTask"] = False
    analysis["agent"] = agent
    simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
    simulation.update({"ran": False, "summary": "", "error": "", "metrics": {}, "status": "queued"})
    analysis["simulation"] = simulation
    for stage in analysis.get("stages") or []:
        if isinstance(stage, dict) and stage.get("key") == "simc_execution":
            stage.update({
                "status": "queued",
                "summary": "SimC task has been queued for backend execution.",
                "metric": "",
            })
    analysis["evidenceState"] = {
        "phase": "queued",
        "profileSource": "template",
        "simcRan": False,
        "hasDps": False,
        "blockers": [],
    }
    analysis["runPolicy"] = {
        "policy": "queued",
        "profileSource": "template",
        "canRunSimc": True,
        "didRunSimc": False,
        "requiresFullProfile": False,
        "validationPassed": True,
        "reason": "simc task queued",
    }
    analysis["report"] = {
        "schemaRevision": "simc-report-v1",
        "source": "deterministic_queued",
        "fallbackReason": "queued",
        "topFindings": [{
            "text": "SimC task accepted and queued; results will appear in the task list.",
            "evidenceRefs": ["simc.taskQueued", "simc.template"],
        }],
        "nextActions": ["Open the task list after the backend SimC run finishes."],
        "limitations": ["No DPS is available until the queued SimC task completes."],
    }
    analysis["recommendations"] = ["SimC task has been queued. Check the task list for the completed result."]
    if isinstance(analysis.get("llm"), dict):
        analysis["llm"]["called"] = False
        analysis["llm"]["content"] = ""
        analysis["llm"]["error"] = ""
    if isinstance(analysis.get("codex"), dict):
        analysis["codex"]["called"] = False
        analysis["codex"]["status"] = "skipped"
        analysis["codex"]["reason"] = "simcraft template deterministic path"
    attach_simcraft_template_report(analysis, row_status="queued", timing=analysis.get("taskTiming"))
    return analysis


def simcraft_template_active_task_limit_analysis(confirm_analysis, active_count, limit):
    analysis = json_clone(confirm_analysis)
    message = simcraft_template_active_limit_message(active_count, limit)
    analysis["status"] = "blocked"
    analysis["updatedAt"] = utc_now()
    analysis["taskLock"] = {
        "active": True,
        "taskId": "",
        "status": "blocked",
        "reason": "active_simc_task_limit",
        "activeCount": active_count,
        "limit": limit,
    }
    agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
    validation = agent.get("validation") if isinstance(agent.get("validation"), dict) else {}
    validation["passed"] = False
    errors = [str(item) for item in validation.get("errors") or [] if str(item).strip()]
    if message not in errors:
        errors.append(message)
    validation["errors"] = errors
    agent["validation"] = validation
    agent["status"] = "task_limit_reached"
    agent["canSubmitTask"] = False
    analysis["agent"] = agent
    simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
    simulation.update({"ran": False, "summary": "", "error": message, "metrics": {}, "status": "blocked"})
    analysis["simulation"] = simulation
    analysis["evidenceState"] = {
        "phase": "blocked",
        "profileSource": "template",
        "simcRan": False,
        "hasDps": False,
        "blockers": [message],
    }
    analysis["runPolicy"] = {
        "policy": "blocked",
        "profileSource": "template",
        "canRunSimc": False,
        "didRunSimc": False,
        "requiresFullProfile": False,
        "validationPassed": False,
        "reason": "active simc task limit",
    }
    analysis["report"] = {
        "schemaRevision": "simc-report-v1",
        "source": "deterministic_blocked",
        "fallbackReason": "active_simc_task_limit",
        "topFindings": [{
            "text": message,
            "evidenceRefs": ["simc.activeTaskLimit"],
        }],
        "nextActions": ["Wait for an active SimC task to finish before submitting another one."],
        "limitations": ["No new SimC task was queued."],
    }
    analysis["recommendations"] = [message]
    attach_simcraft_template_report(analysis, row_status="blocked")
    return public_simcraft_template_analysis(analysis, row_status="blocked")


def active_simcraft_template_task_from_rows(rows, fingerprint):
    for row in rows:
        request_payload = safe_json_loads(row[2], {}, f"simcraft template task request {row[0]}")
        if request_payload.get("simcTaskFingerprint") != fingerprint:
            continue
        analysis = safe_json_loads(row[3], {}, f"simcraft template task analysis {row[0]}")
        if not isinstance(analysis, dict):
            analysis = {}
        analysis["taskId"] = row[0]
        analysis["status"] = row[1]
        analysis["taskLock"] = {
            "active": True,
            "taskId": row[0],
            "status": row[1],
            "reason": "active_simc_task",
        }
        attach_simcraft_template_report(analysis, row_status=row[1])
        return public_simcraft_template_analysis(analysis, row_status=row[1])
    return None


def active_simcraft_template_task_rows(conn, user_id):
    return conn.execute(
        """
        SELECT id, status, request_json, analysis_json, created_at, updated_at
        FROM simulator_tasks
        WHERE user_id = ? AND mode = 'simcraft_template' AND status IN ('queued', 'running')
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (user_id,),
    ).fetchall()


def active_simcraft_template_task(conn, user_id, fingerprint):
    return active_simcraft_template_task_from_rows(active_simcraft_template_task_rows(conn, user_id), fingerprint)


def simcraft_template_task_autorun_enabled():
    return bool_env("WOW_SIMC_TEMPLATE_TASK_AUTORUN", True)


def start_simcraft_template_task_runner(task_id):
    if not simcraft_template_task_autorun_enabled():
        return False
    thread = threading.Thread(target=run_simcraft_template_task, args=(task_id,), daemon=True)
    thread.start()
    return True


def enqueue_simcraft_template_task(request_payload, access_token=""):
    prepared = prepare_simcraft_template_request(request_payload)
    confirm_payload = dict(prepared)
    confirm_payload["confirmOnly"] = True
    confirm_payload["saveTask"] = False
    validation_analysis = analyze_simulator_request(confirm_payload)
    agent = validation_analysis.get("agent") if isinstance(validation_analysis.get("agent"), dict) else {}
    if agent.get("status") != "template_ready" or not agent.get("canSubmitTask"):
        return validation_analysis

    user = authenticate_token(access_token)
    if not user:
        user = guest_simulator_user(prepared.get("guestId"))
    if not user:
        return validation_analysis

    fingerprint = simcraft_template_task_fingerprint(prepared)
    task_id = uuid.uuid4().hex
    stored_request = dict(prepared)
    stored_request.pop("guestId", None)
    stored_request["confirmOnly"] = False
    stored_request["saveTask"] = True
    stored_request["simcTaskFingerprint"] = fingerprint
    now = utc_now()
    store = personal_data_store()
    if store:
        active_rows = store.active_simulator_task_rows(user["id"])
        existing = active_simcraft_template_task_from_rows(
            active_rows,
            fingerprint,
        )
        if existing:
            return existing
        active_limit = simcraft_template_active_task_limit()
        if len(active_rows) >= active_limit:
            return simcraft_template_active_task_limit_analysis(validation_analysis, len(active_rows), active_limit)
        queued_timing = {"queuedAt": now, "startedAt": "", "finishedAt": "", "elapsedMs": None}
        queued_analysis = simcraft_template_queue_analysis(
            validation_analysis,
            stored_request,
            task_id,
            user,
            fingerprint,
            timing=queued_timing,
        )
        queued_summary = simcraft_template_report_summary_payload(
            queued_analysis,
            row_status="queued",
            updated_at=now,
            request_payload=stored_request,
        )
        store.insert_simulator_task(
            {
                "id": task_id,
                "user_id": user["id"],
                "mode": "simcraft_template",
                "status": "queued",
                "request_json": stored_request,
                "analysis_json": queued_analysis,
                "summary_json": queued_summary,
                "queued_at": now,
                "created_at": now,
                "updated_at": now,
            }
        )
    else:
        with db_connection() as conn:
            active_rows = active_simcraft_template_task_rows(conn, user["id"])
            existing = active_simcraft_template_task_from_rows(active_rows, fingerprint)
            if existing:
                return existing
            active_limit = simcraft_template_active_task_limit()
            if len(active_rows) >= active_limit:
                return simcraft_template_active_task_limit_analysis(validation_analysis, len(active_rows), active_limit)
            queued_timing = {"queuedAt": now, "startedAt": "", "finishedAt": "", "elapsedMs": None}
            queued_analysis = simcraft_template_queue_analysis(
                validation_analysis,
                stored_request,
                task_id,
                user,
                fingerprint,
                timing=queued_timing,
            )
            queued_summary = simcraft_template_report_summary_payload(
                queued_analysis,
                row_status="queued",
                updated_at=now,
                request_payload=stored_request,
            )
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, summary_json,
                    queued_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user["id"],
                    "simcraft_template",
                    "queued",
                    json.dumps(stored_request, ensure_ascii=False),
                    json.dumps(queued_analysis, ensure_ascii=False),
                    json.dumps(queued_summary, ensure_ascii=False),
                    now,
                    now,
                    now,
                ),
            )
    start_simcraft_template_task_runner(task_id)
    return public_simcraft_template_analysis(queued_analysis)


def simcraft_template_task_running_payload(row, request_payload, analysis_payload):
    now = utc_now()
    running = json_clone(analysis_payload if isinstance(analysis_payload, dict) else {})
    running["status"] = "running"
    running["updatedAt"] = now
    timing = running.get("taskTiming") if isinstance(running.get("taskTiming"), dict) else {}
    timing["startedAt"] = now
    timing["finishedAt"] = ""
    timing["elapsedMs"] = None
    running["taskTiming"] = timing
    agent = running.get("agent") if isinstance(running.get("agent"), dict) else {}
    agent["status"] = "simc_running"
    agent["canSubmitTask"] = False
    running["agent"] = agent
    running["evidenceState"] = {
        "phase": "running",
        "profileSource": "template",
        "simcRan": False,
        "hasDps": False,
        "blockers": [],
    }
    running["runPolicy"] = {
        "policy": "running",
        "profileSource": "template",
        "canRunSimc": True,
        "didRunSimc": False,
        "requiresFullProfile": False,
        "validationPassed": True,
        "reason": "simc task running",
    }
    attach_simcraft_template_report(running, row_status="running", timing=timing)
    running_summary = simcraft_template_report_summary_payload(
        running,
        row_status="running",
        updated_at=now,
        request_payload=request_payload,
    )
    return running, running_summary, now


def mark_simcraft_template_task_running(conn, row, request_payload, analysis_payload):
    running, running_summary, now = simcraft_template_task_running_payload(row, request_payload, analysis_payload)
    conn.execute(
        """
        UPDATE simulator_tasks
        SET status = ?, analysis_json = ?, summary_json = ?, started_at = ?,
            attempt = attempt + 1, updated_at = ?
        WHERE id = ?
        """,
        ("running", json.dumps(running, ensure_ascii=False), json.dumps(running_summary, ensure_ascii=False), now, now, row[0]),
    )
    return running


def complete_simcraft_template_task_analysis(task_id, request_payload, running_analysis):
    public_task_id = public_row_value(task_id)
    run_request = dict(request_payload)
    run_request["confirmOnly"] = False
    run_request["saveTask"] = True
    run_request["_executeSimcTask"] = True
    analysis = analyze_simulator_request(run_request)
    final_status = "completed" if bool((analysis.get("simulation") or {}).get("ran")) else "failed"
    analysis = dict(analysis)
    analysis["taskId"] = public_task_id
    analysis["status"] = final_status
    if not isinstance(analysis.get("owner"), dict) and isinstance(running_analysis.get("owner"), dict):
        analysis["owner"] = running_analysis["owner"]
    finished_at = utc_now()
    timing = running_analysis.get("taskTiming") if isinstance(running_analysis.get("taskTiming"), dict) else {}
    timing["finishedAt"] = finished_at
    timing["elapsedMs"] = iso_elapsed_ms(timing.get("startedAt"), finished_at)
    analysis["taskTiming"] = timing
    analysis["taskLock"] = {"active": False, "taskId": public_task_id, "status": final_status, "reason": "task_finished"}
    attach_simcraft_template_report(analysis, row_status=final_status, timing=timing)
    final_summary = simcraft_template_report_summary_payload(
        analysis,
        row_status=final_status,
        updated_at=finished_at,
        request_payload=request_payload,
    )
    final_error = ""
    if final_status == "failed":
        final_error = str(
            (analysis.get("simulation") or {}).get("error")
            or (analysis.get("simcReport") or {}).get("summary")
            or "simcraft task failed"
        )
    return analysis, final_status, final_summary, final_error, finished_at


def run_simcraft_template_task_postgres(store, task_id):
    row = store.get_simcraft_template_task_for_runner(task_id)
    if not row:
        raise KeyError("simcraft template task not found")
    request_payload = safe_json_loads(row[4], {}, f"simcraft template task request {row[0]}")
    analysis_payload = safe_json_loads(row[5], {}, f"simcraft template task analysis {row[0]}")
    if row[3] not in SIMCRAFT_TEMPLATE_TASK_ACTIVE_STATUSES:
        return analysis_payload
    running_analysis, running_summary, started_at = simcraft_template_task_running_payload(
        row,
        request_payload,
        analysis_payload,
    )
    store.mark_simcraft_template_task_running(row[0], running_analysis, running_summary, started_at)
    analysis, final_status, final_summary, final_error, finished_at = complete_simcraft_template_task_analysis(
        row[0],
        request_payload,
        running_analysis,
    )
    store.finish_simcraft_template_task(row[0], final_status, analysis, final_summary, finished_at, final_error)
    return public_simcraft_template_analysis(analysis, row_status=final_status)


def run_simcraft_template_task(task_id):
    store = personal_data_store()
    if store:
        return run_simcraft_template_task_postgres(store, task_id)
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
            FROM simulator_tasks
            WHERE id = ? AND mode = 'simcraft_template'
            """,
            (task_id,),
        ).fetchone()
        if not row:
            raise KeyError("simcraft template task not found")
        request_payload = safe_json_loads(row[4], {}, f"simcraft template task request {row[0]}")
        analysis_payload = safe_json_loads(row[5], {}, f"simcraft template task analysis {row[0]}")
        if row[3] not in SIMCRAFT_TEMPLATE_TASK_ACTIVE_STATUSES:
            return analysis_payload
        running_analysis = mark_simcraft_template_task_running(conn, row, request_payload, analysis_payload)

    analysis, final_status, final_summary, final_error, finished_at = complete_simcraft_template_task_analysis(
        row[0],
        request_payload,
        running_analysis,
    )
    with db_connection() as conn:
        owner = conn.execute(
            "SELECT id, openid, nickname, avatar_url FROM wechat_users WHERE id = ?",
            (row[1],),
        ).fetchone()
        if owner:
            analysis["owner"] = {
                "id": owner[0],
                "openid": owner[1],
                "nickname": owner[2],
                "avatarUrl": owner[3],
            }
        now = finished_at
        conn.execute(
            """
            UPDATE simulator_tasks
            SET status = ?, analysis_json = ?, summary_json = ?, finished_at = ?,
                last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                json.dumps(analysis, ensure_ascii=False),
                json.dumps(final_summary, ensure_ascii=False),
                now,
                final_error,
                now,
                task_id,
            ),
        )
    return public_simcraft_template_analysis(analysis, row_status=final_status)


def analyze_and_store_simulator_task(request_data, access_token=""):
    request_payload = dict(request_data or {})
    if is_simcraft_template_final_submit(request_payload):
        return enqueue_simcraft_template_task(request_payload, access_token=access_token)
    if request_payload.get("mode") == "simcraft_template":
        request_payload = prepare_simcraft_template_request(request_payload)
    analysis = analyze_simulator_request(request_payload)
    if request_payload.get("mode") == "simcraft_template":
        attach_simcraft_template_report(analysis)
    if not should_store_simulator_task(request_payload, analysis):
        if request_payload.get("mode") == "simcraft_template":
            return public_simcraft_template_analysis(analysis)
        return analysis
    user = authenticate_token(access_token)
    if not user and request_payload.get("saveTask"):
        user = guest_simulator_user(request_payload.get("guestId"))
    if not user:
        return analysis

    task_id = uuid.uuid4().hex
    now = utc_now()
    stored_request = dict(request_payload)
    stored_request.pop("guestId", None)
    analysis = dict(analysis)
    analysis["taskId"] = task_id
    analysis["owner"] = {
        "id": user["id"],
        "openid": user["openid"],
        "nickname": user["nickname"],
        "avatarUrl": user["avatarUrl"],
    }
    if request_payload.get("mode") == "simcraft_template":
        attach_simcraft_template_report(analysis)
    summary_payload = (
        simcraft_template_report_summary_payload(
            analysis,
            row_status=analysis.get("status", ""),
            updated_at=now,
            request_payload=stored_request,
        )
        if request_payload.get("mode") == "simcraft_template"
        else {}
    )
    store = personal_data_store()
    if store:
        store.insert_simulator_task(
            {
                "id": task_id,
                "user_id": user["id"],
                "mode": analysis.get("mode", ""),
                "status": analysis.get("status", ""),
                "request_json": stored_request,
                "analysis_json": analysis,
                "summary_json": summary_payload,
                "created_at": now,
                "updated_at": now,
            }
        )
    else:
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, summary_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user["id"],
                    analysis.get("mode", ""),
                    analysis.get("status", ""),
                    json.dumps(stored_request, ensure_ascii=False),
                    json.dumps(analysis, ensure_ascii=False),
                    json.dumps(summary_payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
    if request_payload.get("mode") == "simcraft_template":
        return public_simcraft_template_analysis(analysis)
    return analysis


def list_simulator_tasks(access_token, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        if allow_guest:
            return {"user": None, "tasks": []}
        raise PermissionError("invalid auth token")

    store = personal_data_store()
    if store:
        rows = store.list_simulator_task_rows(user["id"])
    else:
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, mode, status, request_json, analysis_json, summary_json, created_at, updated_at
                FROM simulator_tasks
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (user["id"],),
            ).fetchall()
    tasks = []
    for row in rows:
        request_payload = safe_json_loads(row[3], {}, f"simulator task request {row[0]}")
        analysis_payload = safe_json_loads(row[4], {}, f"simulator task analysis {row[0]}")
        question = (
            request_payload.get("question")
            or request_payload.get("prompt")
            or request_payload.get("message")
            or ""
        )
        task = {
            "taskId": public_row_value(row[0]),
            "mode": public_row_value(row[1]),
            "status": public_row_value(row[2]),
            "question": question,
            "recommendations": analysis_payload.get("recommendations", []),
            "createdAt": public_row_value(row[6]),
            "updatedAt": public_row_value(row[7]),
        }
        if row[1] == "simcraft_template":
            stored_summary = safe_json_loads(row[5], {}, f"simulator task summary {row[0]}")
            generated_summary = simcraft_template_report_summary_payload(
                analysis_payload,
                row_status=row[2],
                updated_at=row[7],
                request_payload=request_payload,
            )
            task["simcReportSummary"] = merge_simcraft_template_task_summary(stored_summary, generated_summary)
        tasks.append(task)
    return {"user": user, "tasks": tasks}


def get_simulator_task(access_token, task_id, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")

    store = personal_data_store()
    should_backfill_detail = False
    if store:
        row = store.get_simulator_task_row(user["id"], task_id)
    else:
        should_backfill_detail = True
        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT id, mode, status, request_json, analysis_json, created_at, updated_at
                FROM simulator_tasks
                WHERE user_id = ? AND id = ?
                """,
                (user["id"], task_id),
            ).fetchone()
    if not row:
        raise KeyError("simulator task not found")

    request_payload = safe_json_loads(row[3], {}, f"simulator task request {row[0]}")
    analysis_payload = safe_json_loads(row[4], {}, f"simulator task analysis {row[0]}")
    if row[1] == "simcraft_template" and should_backfill_detail:
        analysis_payload = backfill_simcraft_template_detail_stat_snapshot(
            row[0],
            row[2],
            request_payload,
            analysis_payload,
        )
    question = (
        request_payload.get("question")
        or request_payload.get("prompt")
        or request_payload.get("message")
        or ""
    )
    public_analysis = (
        public_simcraft_template_analysis(analysis_payload, row_status=row[2], strip_profile=True)
        if row[1] == "simcraft_template"
        else analysis_payload
    )
    public_request = (
        public_simcraft_template_request(request_payload)
        if row[1] == "simcraft_template"
        else request_payload
    )
    return {
        "user": user,
        "task": {
            "taskId": public_row_value(row[0]),
            "mode": public_row_value(row[1]),
            "status": public_row_value(row[2]),
            "question": question,
            "recommendations": public_analysis.get("recommendations", []),
            "request": public_request,
            "analysis": public_analysis,
            "createdAt": public_row_value(row[5]),
            "updatedAt": public_row_value(row[6]),
        },
    }


def normalize_chickenbro_phase(value):
    phase = str(value or "retail").strip().lower()
    return phase if phase in CHICKENBRO_PRODUCT_PHASES else "retail"


def normalize_chickenbro_scenario(value):
    scenario = str(value or "").strip().lower()
    if scenario in CHICKENBRO_SCENARIOS:
        return scenario
    aliases = {
        "mplus": "mplus_fortified",
        "mythic_plus": "mplus_fortified",
        "fortified": "mplus_fortified",
        "tyrannical": "mplus_tyrannical",
        "single": "raid_single",
        "raid": "raid_single",
        "cleave": "raid_cleave",
        "aoe": "raid_multi",
    }
    return aliases.get(scenario, "mplus_fortified")


def normalize_chickenbro_region(value):
    region = str(value or "cn").strip().lower()
    return "global" if region in {"global", "world", "all"} else (region or "cn")


def chickenbro_profile_key(profile):
    return (
        profile.get("profileKey")
        or ":".join(
            [
                normalize_chickenbro_phase(profile.get("productPhase")),
                normalize_chickenbro_region(profile.get("region")),
                str(profile.get("classKey") or "").strip().lower(),
                str(profile.get("specKey") or "").strip().lower(),
                normalize_chickenbro_scenario(profile.get("scenarioKey")),
            ]
        )
    )


def upsert_chickenbro_spec_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("chickenbro profile must be an object")
    payload = profile.get("payload") if isinstance(profile.get("payload"), dict) else {}
    class_key = str(profile.get("classKey") or "").strip().lower()
    spec_key = str(profile.get("specKey") or "").strip().lower()
    if not class_key or not spec_key:
        raise ValueError("chickenbro profile requires classKey and specKey")
    status = str(profile.get("status") or "partial").strip().lower()
    if status not in CHICKENBRO_PROFILE_STATUSES:
        raise ValueError(f"unsupported chickenbro profile status: {status}")
    now = utc_now()
    profile_key = chickenbro_profile_key(profile)
    with db_connection() as conn:
        existing = conn.execute(
            """
            SELECT status, published_at
            FROM chickenbro_spec_profiles
            WHERE profile_key = ?
            """,
            (profile_key,),
        ).fetchone()
        previous_status = existing[0] if existing else ""
        previous_published_at = existing[1] if existing else ""
        published_at = str(profile.get("publishedAt") or "")
        downgraded = previous_status == "published" and status != "published"
        # A downgrade invalidates runtime conclusions but should preserve the
        # historical publish timestamp for audit and rollback review.
        if downgraded and not published_at:
            published_at = previous_published_at
        conn.execute(
            """
            INSERT INTO chickenbro_spec_profiles (
                profile_key, product_phase, season_slug, patch_version, region,
                class_key, spec_key, role, scenario_key, status, source_status,
                checked_at, published_at, stale_at, expires_at, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_key) DO UPDATE SET
                product_phase = excluded.product_phase,
                season_slug = excluded.season_slug,
                patch_version = excluded.patch_version,
                region = excluded.region,
                class_key = excluded.class_key,
                spec_key = excluded.spec_key,
                role = excluded.role,
                scenario_key = excluded.scenario_key,
                status = excluded.status,
                source_status = excluded.source_status,
                checked_at = excluded.checked_at,
                published_at = excluded.published_at,
                stale_at = excluded.stale_at,
                expires_at = excluded.expires_at,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                profile_key,
                normalize_chickenbro_phase(profile.get("productPhase")),
                str(profile.get("seasonSlug") or ""),
                str(profile.get("patchVersion") or ""),
                normalize_chickenbro_region(profile.get("region")),
                class_key,
                spec_key,
                str(profile.get("role") or ""),
                normalize_chickenbro_scenario(profile.get("scenarioKey")),
                status,
                str(profile.get("sourceStatus") or status).strip().lower(),
                str(profile.get("checkedAt") or now),
                published_at,
                str(profile.get("staleAt") or ""),
                str(profile.get("expiresAt") or ""),
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
    return {
        "profileKey": profile_key,
        "status": status,
        "previousStatus": previous_status,
        "statusChanged": bool(previous_status and previous_status != status),
        "downgraded": downgraded,
    }


def chickenbro_profile_from_row(row):
    if not row:
        return None
    payload = safe_json_loads(row[15], {}, f"chickenbro profile {row[0]}")
    return {
        "profileKey": row[0],
        "productPhase": row[1],
        "seasonSlug": row[2],
        "patchVersion": row[3],
        "region": row[4],
        "classKey": row[5],
        "specKey": row[6],
        "role": row[7],
        "scenarioKey": row[8],
        "status": row[9],
        "sourceStatus": row[10],
        "checkedAt": row[11],
        "publishedAt": row[12],
        "staleAt": row[13],
        "expiresAt": row[14],
        "payload": payload if isinstance(payload, dict) else {},
        "updatedAt": row[16],
    }


def load_chickenbro_profiles(context):
    class_key = str(context.get("classKey") or (context.get("character") or {}).get("classKey") or "").strip().lower()
    spec_key = str(context.get("specKey") or (context.get("character") or {}).get("specKey") or "").strip().lower()
    if not class_key or not spec_key:
        return []
    phase = normalize_chickenbro_phase(context.get("productPhase") or context.get("phase"))
    scenario = normalize_chickenbro_scenario(context.get("scenarioKey") or context.get("scenario"))
    region = normalize_chickenbro_region(context.get("region"))
    store = personal_data_store()
    if store and hasattr(store, "load_chickenbro_spec_profiles"):
        return store.load_chickenbro_spec_profiles(
            phase=phase,
            class_key=class_key,
            spec_key=spec_key,
            scenario=scenario,
            region=region,
        )
    if postgres_only_runtime_enabled():
        return []
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT profile_key, product_phase, season_slug, patch_version, region,
                   class_key, spec_key, role, scenario_key, status, source_status,
                   checked_at, published_at, stale_at, expires_at, payload_json, updated_at
            FROM chickenbro_spec_profiles
            WHERE product_phase = ? AND class_key = ? AND spec_key = ? AND scenario_key = ?
            ORDER BY
                CASE region WHEN ? THEN 0 WHEN 'global' THEN 1 ELSE 2 END,
                CASE status WHEN 'published' THEN 0 WHEN 'partial' THEN 1 ELSE 2 END,
                updated_at DESC
            """,
            (phase, class_key, spec_key, scenario, region),
        ).fetchall()
    return [chickenbro_profile_from_row(row) for row in rows]


def public_chickenbro_profile(profile, include_payload=True):
    if not profile:
        return None
    public = {
        "profileKey": profile["profileKey"],
        "productPhase": profile["productPhase"],
        "seasonSlug": profile["seasonSlug"],
        "patchVersion": profile["patchVersion"],
        "region": profile["region"],
        "classKey": profile["classKey"],
        "specKey": profile["specKey"],
        "role": profile["role"],
        "scenarioKey": profile["scenarioKey"],
        "status": profile["status"],
        "sourceStatus": profile["sourceStatus"],
        "checkedAt": profile["checkedAt"],
        "publishedAt": profile["publishedAt"],
        "staleAt": profile["staleAt"],
        "expiresAt": profile["expiresAt"],
        "updatedAt": profile["updatedAt"],
    }
    if include_payload:
        public["payload"] = profile.get("payload", {})
    return public


def get_chickenbro_profiles(query):
    context = {
        "productPhase": query.get("phase") or query.get("productPhase"),
        "region": query.get("region") or "cn",
        "classKey": query.get("class") or query.get("classKey"),
        "specKey": query.get("spec") or query.get("specKey"),
        "scenarioKey": query.get("scenario") or query.get("scenarioKey"),
    }
    return {
        "profiles": [public_chickenbro_profile(profile) for profile in load_chickenbro_profiles(context)],
        "query": {
            "productPhase": normalize_chickenbro_phase(context.get("productPhase")),
            "region": normalize_chickenbro_region(context.get("region")),
            "classKey": str(context.get("classKey") or "").strip().lower(),
            "specKey": str(context.get("specKey") or "").strip().lower(),
            "scenarioKey": normalize_chickenbro_scenario(context.get("scenarioKey")),
        },
    }


def chickenbro_topic_scope(message, context=None):
    text = str(message or "").strip()
    lowered = text.lower()
    forbidden = ("classic", "怀旧服", "私服", "外挂", "自动脚本", "脚本规避", "账号交易", "代练")
    if any(term in lowered for term in forbidden):
        return {"status": "out_of_scope", "reason": "unsupported_wow_scope"}
    context = context if isinstance(context, dict) else {}
    if context.get("classKey") or (context.get("character") or {}).get("classKey"):
        return {"status": "in_scope", "reason": "structured_context"}
    wow_terms = (
        "魔兽", "wow", "正式服", "ptr", "beta", "大秘境", "团本", "副本", "专精", "天赋",
        "装备", "配装", "手法", "属性", "绿字", "强韧", "残暴", "法师", "奥法", "冰法",
        "火法", "战士", "术士", "牧师", "盗贼", "潜行者", "武僧", "萨满", "猎人",
        "德鲁伊", "圣骑", "死亡骑士", "恶魔猎手", "唤魔师",
    )
    if any(term in lowered for term in CHICKENBRO_ALLOWED_TOOL_TOPICS) or any(term in text for term in wow_terms):
        return {"status": "in_scope", "reason": "wow_topic"}
    return {"status": "out_of_scope", "reason": "non_wow_topic"}


def compact_chickenbro_runtime_profile(profile):
    payload = profile.get("payload") if isinstance(profile.get("payload"), dict) else {}
    runtime = payload.get("runtimeProjection") if isinstance(payload.get("runtimeProjection"), dict) else {}
    coach_pack = payload.get("coachPack") if isinstance(payload.get("coachPack"), dict) else {}
    evidence_refs = runtime.get("evidenceRefs") or [
        item.get("id")
        for item in payload.get("evidenceRefs", [])
        if isinstance(item, dict) and item.get("id")
    ]
    allowed_numbers = runtime.get("allowedNumbers") or (
        (payload.get("performanceModel") or {}).get("allowedNumbers")
        if isinstance(payload.get("performanceModel"), dict)
        else []
    )
    compact_runtime = {
        "summary": clean_text(runtime.get("summary") or "", 600),
        "evidenceRefs": compact_chickenbro_evidence_refs(runtime.get("evidenceRefs") or evidence_refs),
        "allowedNumbers": compact_chickenbro_allowed_numbers(runtime.get("allowedNumbers") or allowed_numbers),
        "limitations": compact_chickenbro_text_list(runtime.get("limitations") or payload.get("limitations") or []),
    }
    compact_coach_pack = {
        "summary": clean_text(coach_pack.get("summary") or runtime.get("summary") or "", 600),
        "priorityActions": compact_chickenbro_priority_actions(coach_pack.get("priorityActions") or []),
        "limitations": compact_chickenbro_text_list(coach_pack.get("limitations") or []),
    }
    return {
        "profileKey": profile["profileKey"],
        "region": profile["region"],
        "status": profile["status"],
        "sourceStatus": profile["sourceStatus"],
        "productPhase": profile["productPhase"],
        "seasonSlug": profile["seasonSlug"],
        "patchVersion": profile["patchVersion"],
        "classKey": profile["classKey"],
        "specKey": profile["specKey"],
        "role": profile["role"],
        "scenarioKey": profile["scenarioKey"],
        "summary": compact_runtime["summary"] or compact_coach_pack["summary"],
        "priorityActions": compact_coach_pack["priorityActions"],
        "limitations": compact_chickenbro_text_list(
            runtime.get("limitations") or payload.get("limitations") or coach_pack.get("limitations") or []
        ),
        "evidenceRefs": compact_runtime["evidenceRefs"],
        "allowedNumbers": compact_runtime["allowedNumbers"],
        "runtimeProjection": compact_runtime,
        "coachPack": compact_coach_pack,
        "sourceCoverage": payload.get("sourceCoverage") if isinstance(payload.get("sourceCoverage"), dict) else {},
        "sampleWindow": payload.get("sampleWindow") if isinstance(payload.get("sampleWindow"), dict) else {},
    }


def compact_chickenbro_text_list(value, limit=160, max_items=12):
    if not isinstance(value, list):
        value = [value] if value else []
    output = []
    for item in value:
        append_unique_text(output, clean_text(item, limit))
        if len(output) >= max_items:
            break
    return output


def compact_chickenbro_evidence_refs(value, max_items=24):
    if isinstance(value, dict):
        value = [value]
    elif not isinstance(value, list):
        value = [value] if value else []
    output = []
    for item in value:
        ref = ""
        if isinstance(item, dict):
            ref = item.get("id") or item.get("ref") or item.get("key") or item.get("evidenceRef")
        else:
            ref = item
        append_unique_text(output, clean_text(ref, 120))
        if len(output) >= max_items:
            break
    return output


def compact_chickenbro_allowed_numbers(value, max_items=24):
    if isinstance(value, dict):
        value = [value]
    elif not isinstance(value, list):
        value = [value] if value else []
    output = []
    for item in value:
        if isinstance(item, dict):
            number = {
                "key": clean_text(item.get("key") or item.get("id") or item.get("label"), 120),
                "value": clean_text(item.get("value"), 120),
            }
        else:
            number = {"key": "", "value": clean_text(item, 120)}
        if number["value"]:
            append_unique_item(output, number)
        if len(output) >= max_items:
            break
    return output


def compact_chickenbro_priority_actions(value, max_items=6):
    if not isinstance(value, list):
        return []
    output = []
    for item in value:
        if not isinstance(item, dict):
            continue
        action = {
            "title": clean_text(item.get("title") or item.get("summary") or "", 220),
            "evidenceRefs": compact_chickenbro_evidence_refs(item.get("evidenceRefs") or []),
        }
        if action["title"]:
            append_unique_item(output, action)
        if len(output) >= max_items:
            break
    return output


def compact_chickenbro_saved_template_evidence(context):
    template = context.get("savedTemplate") or context.get("template")
    if not isinstance(template, dict):
        return None
    compact = {
        "templateId": clean_text(template.get("templateId") or template.get("id"), 120),
        "name": clean_text(template.get("name") or template.get("title"), 160),
        "type": clean_text(template.get("type") or template.get("templateType"), 80),
        "status": clean_text(template.get("status") or "", 80),
    }
    for key in (
        "seasonRevision",
        "gearCatalogRevision",
        "talentCatalogRevision",
        "simcRuntimeRevision",
        "terminologyRevision",
    ):
        if template.get(key):
            compact[key] = clean_text(template.get(key), 160)
    return {key: value for key, value in compact.items() if value}


def compact_chickenbro_task_evidence(source):
    if not isinstance(source, dict):
        return None
    compact = {}
    for key in (
        "taskId",
        "status",
        "sourceStatus",
        "scenarioKey",
        "reportCode",
        "fightId",
        "seasonRevision",
        "gearCatalogRevision",
        "talentCatalogRevision",
        "simcRuntimeRevision",
        "terminologyRevision",
    ):
        if source.get(key) is not None:
            compact[key] = clean_text(source.get(key), 180)
    if source.get("summary"):
        compact["summary"] = clean_text(source.get("summary"), 600)
    evidence_refs = compact_chickenbro_evidence_refs(source.get("evidenceRefs") or [])
    allowed_numbers = compact_chickenbro_allowed_numbers(source.get("allowedNumbers") or [])
    if evidence_refs:
        compact["evidenceRefs"] = evidence_refs
    if allowed_numbers:
        compact["allowedNumbers"] = allowed_numbers
    return compact or None


def compact_chickenbro_context_evidence(context):
    context = context if isinstance(context, dict) else {}
    saved_templates = []
    saved_template = compact_chickenbro_saved_template_evidence(context)
    if saved_template:
        saved_templates.append(saved_template)
    simc_tasks = []
    for source in (context.get("simcTask"), context.get("simcAnalysis"), context.get("simcResult")):
        task = compact_chickenbro_task_evidence(source)
        if task:
            append_unique_item(simc_tasks, task)
    wcl_tasks = []
    for source in (context.get("wclTask"), context.get("wclAnalysis"), context.get("wclReport")):
        task = compact_chickenbro_task_evidence(source)
        if task:
            append_unique_item(wcl_tasks, task)

    evidence_refs = []
    allowed_numbers = []
    limitations = []
    for collection in (saved_templates, simc_tasks, wcl_tasks):
        for item in collection:
            for ref in item.get("evidenceRefs") or []:
                append_unique_text(evidence_refs, ref)
            for number in item.get("allowedNumbers") or []:
                append_unique_item(allowed_numbers, number)
            for limitation in item.get("limitations") or []:
                append_unique_text(limitations, limitation)

    return {
        "savedTemplates": saved_templates,
        "simcTasks": simc_tasks,
        "wclTasks": wcl_tasks,
        "evidenceRefs": evidence_refs,
        "allowedNumbers": allowed_numbers,
        "limitations": limitations,
    }


def chickenbro_evidence_packet_from_context(bounded_context):
    context_evidence = bounded_context.get("contextEvidence") if isinstance(bounded_context.get("contextEvidence"), dict) else {}
    profiles = [
        profile
        for profile in (bounded_context.get("usableProfiles") or [])[:2]
        if isinstance(profile, dict)
    ]
    allowed_numbers = []
    evidence_refs = []
    limitations = []
    for profile in profiles:
        for number in profile.get("allowedNumbers") or []:
            append_unique_item(allowed_numbers, number)
        for ref in profile.get("evidenceRefs") or []:
            append_unique_text(evidence_refs, ref)
        for limitation in profile.get("limitations") or []:
            append_unique_text(limitations, limitation)
    for number in context_evidence.get("allowedNumbers") or []:
        append_unique_item(allowed_numbers, number)
    for ref in context_evidence.get("evidenceRefs") or []:
        append_unique_text(evidence_refs, ref)
    for limitation in (bounded_context.get("limitations") or []) + (context_evidence.get("limitations") or []):
        append_unique_text(limitations, limitation)
    return {
        "schemaRevision": "chickenbro-evidence-packet-v1",
        "answerLayer": bounded_context.get("answerLayer") or chickenbro_answer_layer_for_context(bounded_context),
        "requestContext": bounded_context.get("requestContext") or {},
        "profiles": profiles,
        "contextEvidence": context_evidence,
        "allowedNumbers": allowed_numbers,
        "evidenceRefs": evidence_refs,
        "limitations": limitations,
    }


def chickenbro_answer_layer_for_context(bounded_context):
    if bounded_context.get("usableProfiles"):
        return "evidence"
    context_evidence = bounded_context.get("contextEvidence") if isinstance(bounded_context.get("contextEvidence"), dict) else {}
    if context_evidence.get("evidenceRefs") or context_evidence.get("allowedNumbers"):
        return "evidence"
    evidence_packet = bounded_context.get("evidencePacket") if isinstance(bounded_context.get("evidencePacket"), dict) else {}
    if evidence_packet.get("evidenceRefs") or evidence_packet.get("allowedNumbers"):
        return "evidence"
    request_context = bounded_context.get("requestContext") if isinstance(bounded_context.get("requestContext"), dict) else {}
    if request_context.get("classKey") or request_context.get("specKey"):
        return "diagnostic"
    return "direct_chat"


def chickenbro_basis_label(answer_layer):
    return {
        "evidence": "已基于你的模板或 SimC 分析",
        "diagnostic": "需要证据确认",
        "direct_chat": "通用建议",
    }.get(answer_layer, "通用建议")


def chickenbro_missing_inputs_for_context(bounded_context, answer_layer):
    request_context = bounded_context.get("requestContext") if isinstance(bounded_context.get("requestContext"), dict) else {}
    missing = []
    if not request_context.get("classKey") and not request_context.get("specKey"):
        missing.append("class_spec")
    elif not request_context.get("specKey"):
        missing.append("spec")
    if answer_layer == "direct_chat":
        missing.append("published_profile")
    elif answer_layer == "diagnostic":
        missing.extend(["simc_or_wcl", "published_profile"])
    elif answer_layer == "evidence":
        missing.append("personal_simc_or_wcl")
    output = []
    for item in missing:
        append_unique_text(output, item)
    return output


def chickenbro_next_question_for_context(bounded_context, answer_layer):
    request_context = bounded_context.get("requestContext") if isinstance(bounded_context.get("requestContext"), dict) else {}
    if answer_layer == "evidence":
        return "要不要补你的个人 SimC 或 WCL，让我把建议收窄到你自己的角色？"
    if answer_layer == "diagnostic":
        return "你能补一份 SimC 报告或 WCL 链接吗？"
    if not request_context.get("classKey") and not request_context.get("specKey"):
        return "你现在玩的职业和专精是什么？"
    return "你主要想优化大秘境、团本单体，还是某个具体副本场景？"


def enrich_chickenbro_context_layers(bounded_context):
    enriched = dict(bounded_context)
    answer_layer = chickenbro_answer_layer_for_context(enriched)
    enriched["answerLayer"] = answer_layer
    enriched["basisLabel"] = chickenbro_basis_label(answer_layer)
    enriched["missingInputs"] = chickenbro_missing_inputs_for_context(enriched, answer_layer)
    enriched["nextQuestion"] = chickenbro_next_question_for_context(enriched, answer_layer)
    return enriched


def build_chickenbro_bounded_context(message, context, user_profile=None):
    context = context if isinstance(context, dict) else {}
    topic = chickenbro_topic_scope(message, context)
    profiles = load_chickenbro_profiles(context)
    desired_region = normalize_chickenbro_region(context.get("region"))
    context_evidence = compact_chickenbro_context_evidence(context)
    usable = []
    background = []
    excluded = []
    limitations = []
    for profile in profiles:
        compact = compact_chickenbro_runtime_profile(profile)
        status = profile.get("status")
        if status == "published":
            usable.append(compact)
        elif status == "partial":
            background.append(compact)
        else:
            excluded.append({"profileKey": profile["profileKey"], "region": profile["region"], "status": status})
    if usable and usable[0]["region"] != desired_region:
        limitations.append(f"{desired_region}_sample_insufficient_global_fallback")
    if background:
        limitations.append("partial_profiles_background_only")
    if excluded:
        limitations.append("unpublished_profiles_excluded")

    allowed_refs = []
    allowed_numbers = []
    for profile in usable:
        for ref in profile.get("evidenceRefs") or []:
            append_unique_text(allowed_refs, ref)
        for number in profile.get("allowedNumbers") or []:
            if isinstance(number, dict):
                append_unique_text(allowed_numbers, str(number.get("value") or ""))
            else:
                append_unique_text(allowed_numbers, str(number))
    for ref in context_evidence.get("evidenceRefs") or []:
        append_unique_text(allowed_refs, ref)
    for number in context_evidence.get("allowedNumbers") or []:
        if isinstance(number, dict):
            append_unique_text(allowed_numbers, str(number.get("value") or ""))
        else:
            append_unique_text(allowed_numbers, str(number))
    for limitation in context_evidence.get("limitations") or []:
        append_unique_text(limitations, limitation)

    bounded_context = {
        "schemaRevision": "chickenbro-bounded-context-v1",
        "topic": topic,
        "message": clean_text(message, 1000),
        "requestContext": {
            "productPhase": normalize_chickenbro_phase(context.get("productPhase") or context.get("phase")),
            "region": desired_region,
            "classKey": str(context.get("classKey") or (context.get("character") or {}).get("classKey") or "").strip().lower(),
            "specKey": str(context.get("specKey") or (context.get("character") or {}).get("specKey") or "").strip().lower(),
            "scenarioKey": normalize_chickenbro_scenario(context.get("scenarioKey") or context.get("scenario")),
        },
        "userProfile": user_profile if isinstance(user_profile, dict) else {},
        "usableProfiles": usable[:2],
        "backgroundProfiles": background[:3],
        "excludedProfiles": excluded[:5],
        "contextEvidence": context_evidence,
        "allowedEvidenceRefs": allowed_refs,
        "allowedNumbers": [number for number in allowed_numbers if number],
        "limitations": limitations,
        "policy": {
            "publishedProfilesSupportConclusions": True,
            "partialProfilesAreBackgroundOnly": True,
            "staleBlockedNeedsReviewExcluded": True,
            "noRealtimeExternalFetch": True,
        },
    }
    bounded_context = enrich_chickenbro_context_layers(bounded_context)
    bounded_context["evidencePacket"] = chickenbro_evidence_packet_from_context(bounded_context)
    return bounded_context


def chickenbro_prompt_from_context(bounded_context):
    answer_layer = bounded_context.get("answerLayer") or chickenbro_answer_layer_for_context(bounded_context)
    if answer_layer == "evidence":
        instructions = [
            "你是炸鸡队长，只回答魔兽世界正式服和 PTR/Beta 相关问题。",
            "证据档才允许输出数字、排名、强个人化结论；仍只能使用 boundedContext 中的事实、证据引用和 allowedNumbers。",
            "只能使用 boundedContext 中的事实、证据引用和 allowedNumbers。",
            "不要编造 DPS、排名、分位、日志发现或来源。",
            "最多追问一个关键缺口；输出 JSON：answer, confidence, answerLayer, basisLabel, priorityActions, evidenceRefs, limitations, missingInputs, nextQuestion。",
        ]
    elif answer_layer == "diagnostic":
        instructions = [
            "你是炸鸡队长，只回答魔兽世界正式服和 PTR/Beta 相关问题。",
            "这是 direct Codex chat 的诊断档：用专业教练结构，在少量职业/专精/场景信息下给可执行 checklist。",
            "不要输出数字、排名、分位、日志发现或强个人化结论；这些只能在证据档出现。",
            "不要把通用知识包装成本地证据；没有 boundedContext 证据时 evidenceRefs 保持为空。",
            "最多追问一个关键缺口；输出 JSON：answer, confidence, answerLayer, basisLabel, priorityActions, evidenceRefs, limitations, missingInputs, nextQuestion。",
        ]
    else:
        instructions = [
            "你是炸鸡队长，只回答魔兽世界正式服和 PTR/Beta 相关问题。",
            "这是 direct Codex chat 的直聊档：默认口吻是老玩家陪练，先接住问题，给低风险通用判断和下一步排查方向。",
            "不要把通用知识包装成本地证据；没有 boundedContext 证据时 evidenceRefs 保持为空，并在 limitations 里说明未经过本地证据验证。",
            "不要编造 DPS、排名、分位、日志发现或来源。",
            "最多追问一个关键缺口；输出 JSON：answer, confidence, answerLayer, basisLabel, priorityActions, evidenceRefs, limitations, missingInputs, nextQuestion。",
        ]
    return json.dumps(
        {
            "instructions": instructions,
            "boundedContext": bounded_context,
        },
        ensure_ascii=False,
        indent=2,
    )


def default_chickenbro_codex_runner(prompt, schema=None):
    if os.environ.get("WOW_CHICKENBRO_CODEX_ENABLED") != "1" or run_codex_job is None:
        return {"status": "skipped", "error": "chickenbro codex disabled"}
    timeout_seconds = max(1, min(60, int_env("WOW_CHICKENBRO_CODEX_TIMEOUT_SECONDS", 12)))
    return run_codex_job(prompt, schema=schema, timeout_seconds=timeout_seconds)


def parse_chickenbro_codex_output(codex_result):
    if isinstance(codex_result, dict) and isinstance(codex_result.get("answer"), str):
        return codex_result
    last_message = ""
    if isinstance(codex_result, dict):
        last_message = codex_result.get("lastMessage") or codex_result.get("content") or ""
    if not str(last_message).strip():
        raise ValueError("empty codex output")
    try:
        payload = json.loads(last_message)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid codex json: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("codex output must be an object")
    return payload


def chickenbro_text_numbers(value):
    return re.findall(r"(?<![A-Za-z])\d{3,}(?:\.\d+)?%?", str(value or ""))


def validate_chickenbro_codex_output(payload, bounded_context):
    answer = str(payload.get("answer") or "").strip()
    if not answer:
        raise ValueError("missing answer")
    allowed_refs = set(bounded_context.get("allowedEvidenceRefs") or [])
    refs = [str(ref) for ref in payload.get("evidenceRefs") or [] if ref]
    if any(ref not in allowed_refs for ref in refs):
        raise ValueError("codex_output_invalid: unknown evidence ref")
    for action in payload.get("priorityActions") or []:
        if not isinstance(action, dict):
            raise ValueError("codex_output_invalid: priority action must be object")
        for ref in action.get("evidenceRefs") or []:
            if str(ref) not in allowed_refs:
                raise ValueError("codex_output_invalid: unknown action evidence ref")
    allowed_numbers = {str(number).rstrip("%") for number in bounded_context.get("allowedNumbers") or []}
    output_text = json.dumps(payload, ensure_ascii=False)
    for number in chickenbro_text_numbers(output_text):
        normalized = number.rstrip("%")
        if normalized not in allowed_numbers:
            raise ValueError("codex_output_invalid: unapproved number")
    answer_layer = bounded_context.get("answerLayer") or chickenbro_answer_layer_for_context(bounded_context)
    basis_label = bounded_context.get("basisLabel") or chickenbro_basis_label(answer_layer)
    missing_inputs = (
        payload.get("missingInputs")
        if isinstance(payload.get("missingInputs"), list)
        else bounded_context.get("missingInputs")
    )
    next_question = clean_text(
        payload.get("nextQuestion") or bounded_context.get("nextQuestion") or "",
        240,
    )
    return {
        "answer": answer,
        "confidence": str(payload.get("confidence") or "medium"),
        "answerLayer": answer_layer,
        "basisLabel": basis_label,
        "priorityActions": payload.get("priorityActions") if isinstance(payload.get("priorityActions"), list) else [],
        "evidenceRefs": refs,
        "limitations": payload.get("limitations") if isinstance(payload.get("limitations"), list) else [],
        "missingInputs": [str(item) for item in (missing_inputs or []) if str(item or "").strip()],
        "nextQuestion": next_question,
    }


def deterministic_chickenbro_answer(bounded_context, answer_source="deterministic_fallback"):
    topic = bounded_context.get("topic") or {}
    if topic.get("status") != "in_scope":
        return {
            "answer": "炸鸡队长只回答魔兽世界正式服和 PTR/Beta 相关的玩法、机制、日志、构筑、装备、SimC、WCL、Raider.IO、插件和宏问题。这个问题不在范围内。",
            "answerSource": "deterministic_scope_refusal",
            "confidence": "blocked",
            "answerLayer": "direct_chat",
            "basisLabel": "通用建议",
            "priorityActions": [],
            "evidenceRefs": [],
            "missingInputs": [],
            "nextQuestion": "",
            "limitations": [topic.get("reason") or "out_of_scope"],
        }
    usable = bounded_context.get("usableProfiles") or []
    if not usable:
        answer_layer = bounded_context.get("answerLayer") or chickenbro_answer_layer_for_context(bounded_context)
        basis_label = bounded_context.get("basisLabel") or chickenbro_basis_label(answer_layer)
        missing_inputs = bounded_context.get("missingInputs") or []
        next_question = bounded_context.get("nextQuestion") or ""
        if answer_layer == "diagnostic":
            return {
                "answer": "按专业教练的排查顺序，先把问题拆成三步：第一看当前场景是不是大秘境还是团本，第二检查天赋和装备是否能稳定服务这个场景，第三再用 SimC 或 WCL 确认瓶颈。现在没有本地证据，所以这些是待验证 checklist，不是强结论。",
                "answerSource": answer_source,
                "confidence": "low",
                "answerLayer": answer_layer,
                "basisLabel": basis_label,
                "priorityActions": [
                    {"title": "先确认当前场景和目标：大秘境群体、团本单体，或某个具体副本机制。", "evidenceRefs": []},
                    {"title": "检查天赋、饰品和爆发技能是否围绕主要战斗窗口服务。", "evidenceRefs": []},
                    {"title": "补一份 SimC 或 WCL 后，再判断到底是配装、循环还是战斗执行问题。", "evidenceRefs": []},
                ],
                "evidenceRefs": [],
                "missingInputs": missing_inputs,
                "nextQuestion": next_question,
                "limitations": bounded_context.get("limitations") or ["missing_published_profile"],
            }
        return {
            "answer": "先按老玩家陪练的方式说：别一上来追求所谓最优，先把问题拆小。大秘境打得乱，通常先看三件事：是不是经常在不该交爆发的小波次交掉了技能、是不是天赋和饰品服务的场景不一致、以及是不是因为走位和断档导致实际输出窗口变短。没有你的角色证据时，我只能给通用方向，不会说你具体排名或 DPS。",
            "answerSource": answer_source,
            "confidence": "low",
            "answerLayer": answer_layer,
            "basisLabel": basis_label,
            "priorityActions": [
                {"title": "先选一个最常出问题的场景，把爆发、资源和生存压力分开看。", "evidenceRefs": []},
                {"title": "再补职业专精、主要场景和一份 SimC 或 WCL，我再帮你收窄判断。", "evidenceRefs": []},
            ],
            "evidenceRefs": [],
            "missingInputs": missing_inputs,
            "nextQuestion": next_question,
            "limitations": bounded_context.get("limitations") or ["missing_published_profile"],
        }
    profile = usable[0]
    actions = [
        action for action in profile.get("priorityActions") or []
        if isinstance(action, dict)
    ][:3]
    refs = []
    for ref in profile.get("evidenceRefs") or []:
        append_unique_text(refs, ref)
    summary = profile.get("summary") or "已找到可用的专精打法画像，但摘要为空。"
    return {
        "answer": summary,
        "answerSource": answer_source,
        "confidence": "medium",
        "answerLayer": bounded_context.get("answerLayer") or "evidence",
        "basisLabel": bounded_context.get("basisLabel") or chickenbro_basis_label("evidence"),
        "priorityActions": actions,
        "evidenceRefs": refs,
        "missingInputs": bounded_context.get("missingInputs") or [],
        "nextQuestion": bounded_context.get("nextQuestion") or "",
        "limitations": list((bounded_context.get("limitations") or []) + (profile.get("limitations") or [])),
    }


def sanitize_chickenbro_request_context(context):
    context = context if isinstance(context, dict) else {}
    character = context.get("character") if isinstance(context.get("character"), dict) else {}
    allowed_character = {
        key: clean_text(character.get(key), 120)
        for key in ("classKey", "className", "specKey", "specName", "role", "itemLevel", "realm", "characterName")
        if character.get(key) is not None
    }
    sanitized = {
        "productPhase": normalize_chickenbro_phase(context.get("productPhase") or context.get("phase")),
        "region": normalize_chickenbro_region(context.get("region")),
        "scenarioKey": normalize_chickenbro_scenario(context.get("scenarioKey") or context.get("scenario")),
    }
    for key in ("classKey", "className", "specKey", "specName", "role"):
        if context.get(key) is not None:
            sanitized[key] = clean_text(context.get(key), 120)
    if allowed_character:
        sanitized["character"] = allowed_character
    return sanitized


def load_chickenbro_user_profile(conn, user_id):
    row = conn.execute(
        "SELECT profile_json FROM chickenbro_user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return safe_json_loads(row[0], {}, f"chickenbro user profile {user_id}") if row else {}


def merge_chickenbro_user_profile(existing, context, message):
    profile = existing if isinstance(existing, dict) else {}
    context = sanitize_chickenbro_request_context(context)
    character = context.get("character") if isinstance(context.get("character"), dict) else {}
    class_key = context.get("classKey") or character.get("classKey")
    spec_key = context.get("specKey") or character.get("specKey")
    scenario_key = context.get("scenarioKey")
    if class_key or spec_key:
        characters = [
            item for item in profile.get("characters", [])
            if isinstance(item, dict)
            and not (item.get("classKey") == class_key and item.get("specKey") == spec_key)
        ]
        characters.insert(
            0,
            {
                "classKey": clean_text(class_key, 80),
                "specKey": clean_text(spec_key, 80),
                "role": clean_text(context.get("role") or character.get("role"), 80),
                "lastScenarioKey": scenario_key,
                "updatedAt": utc_now(),
            },
        )
        profile["characters"] = characters[:10]
    if scenario_key:
        scenarios = [item for item in profile.get("preferredScenarios", []) if item != scenario_key]
        scenarios.insert(0, scenario_key)
        profile["preferredScenarios"] = scenarios[:10]
    if str(message or "").strip():
        profile["lastIntentSummary"] = clean_text(message, 160)
    profile["schemaRevision"] = "chickenbro-user-profile-v1"
    return profile


def upsert_chickenbro_user_profile(conn, user_id, context, message):
    existing = load_chickenbro_user_profile(conn, user_id)
    profile = merge_chickenbro_user_profile(existing, context, message)
    now = utc_now()
    conn.execute(
        """
        INSERT INTO chickenbro_user_profiles (user_id, profile_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            profile_json = excluded.profile_json,
            updated_at = excluded.updated_at
        """,
        (user_id, json.dumps(profile, ensure_ascii=False), now, now),
    )
    return profile


def public_chickenbro_session_from_row(row):
    return {
        "sessionId": row[0],
        "title": row[2],
        "productPhase": row[3],
        "metadata": safe_json_loads(row[4], {}, f"chickenbro session metadata {row[0]}"),
        "createdAt": row[5],
        "updatedAt": row[6],
    }


def public_chickenbro_message_from_row(row):
    payload = safe_json_loads(row[5], {}, f"chickenbro message payload {row[0]}")
    return {
        "messageId": row[0],
        "sessionId": row[1],
        "role": row[3],
        "content": row[4],
        "payload": payload,
        "agentJobId": row[6],
        "createdAt": row[7],
    }


def public_chickenbro_job_from_row(row):
    return {
        "jobId": row[0],
        "sessionId": row[2],
        "kind": row[3],
        "status": row[4],
        "request": safe_json_loads(row[5], {}, f"agent job request {row[0]}"),
        "boundedContext": safe_json_loads(row[6], {}, f"agent job context {row[0]}"),
        "result": safe_json_loads(row[7], {}, f"agent job result {row[0]}"),
        "error": row[8],
        "createdAt": row[9],
        "updatedAt": row[10],
        "startedAt": row[11],
        "finishedAt": row[12],
    }


def resolve_chickenbro_user(access_token="", guest_id="", create_guest=False):
    user = authenticate_token(access_token)
    if not user and guest_id:
        user = guest_simulator_user(guest_id) if create_guest else find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")
    return user


def create_chickenbro_session(access_token="", guest_id="", metadata=None):
    user = resolve_chickenbro_user(access_token, guest_id, create_guest=True)
    metadata = metadata if isinstance(metadata, dict) else {}
    now = utc_now()
    session_id = uuid.uuid4().hex
    title = clean_text(metadata.get("title") or "炸鸡队长对话", 80)
    product_phase = normalize_chickenbro_phase(metadata.get("productPhase") or metadata.get("phase"))
    store = personal_data_store()
    if store:
        return {
            "user": user,
            "session": store.create_chickenbro_session(user["id"], title, product_phase, metadata, now),
        }
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO chickenbro_sessions (
                id, user_id, title, product_phase, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user["id"],
                title,
                product_phase,
                json.dumps(metadata, ensure_ascii=False),
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id, user_id, title, product_phase, metadata_json, created_at, updated_at
            FROM chickenbro_sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return {"user": user, "session": public_chickenbro_session_from_row(row)}


def find_or_create_chickenbro_session(conn, user, session_id, message, context):
    if session_id:
        row = conn.execute(
            """
            SELECT id, user_id, title, product_phase, metadata_json, created_at, updated_at
            FROM chickenbro_sessions WHERE id = ? AND user_id = ?
            """,
            (session_id, user["id"]),
        ).fetchone()
        if not row:
            raise KeyError("chickenbro session not found")
        return public_chickenbro_session_from_row(row)
    now = utc_now()
    new_id = uuid.uuid4().hex
    title = clean_text(message, 36) or "炸鸡队长对话"
    metadata = {
        "createdFrom": "message",
        "context": sanitize_chickenbro_request_context(context),
    }
    conn.execute(
        """
        INSERT INTO chickenbro_sessions (
            id, user_id, title, product_phase, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            user["id"],
            title,
            normalize_chickenbro_phase(context.get("productPhase") or context.get("phase")),
            json.dumps(metadata, ensure_ascii=False),
            now,
            now,
        ),
    )
    return {
        "sessionId": new_id,
        "title": title,
        "productPhase": normalize_chickenbro_phase(context.get("productPhase") or context.get("phase")),
        "metadata": metadata,
        "createdAt": now,
        "updatedAt": now,
    }


def insert_chickenbro_message(conn, user_id, session_id, role, content, payload=None, agent_job_id=""):
    now = utc_now()
    message_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO chickenbro_messages (
            id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            session_id,
            user_id,
            role,
            clean_text(content, 4000),
            json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False),
            agent_job_id or "",
            now,
        ),
    )
    return {
        "messageId": message_id,
        "sessionId": session_id,
        "role": role,
        "content": clean_text(content, 4000),
        "payload": payload if isinstance(payload, dict) else {},
        "agentJobId": agent_job_id or "",
        "createdAt": now,
    }


def insert_agent_job(conn, user_id, session_id, request_payload, bounded_context):
    now = utc_now()
    job_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO agent_jobs (
            id, user_id, session_id, kind, status, request_json, bounded_context_json,
            result_json, error, created_at, updated_at, started_at, finished_at
        ) VALUES (?, ?, ?, 'chickenbro', 'queued', ?, ?, '{}', '', ?, ?, '', '')
        """,
        (
            job_id,
            user_id,
            session_id,
            json.dumps(request_payload, ensure_ascii=False),
            json.dumps(bounded_context, ensure_ascii=False),
            now,
            now,
        ),
    )
    return job_id


def update_agent_job(conn, job_id, status, result=None, error="", started_at=None, finished_at=None):
    if status not in CHICKENBRO_JOB_STATUSES:
        raise ValueError(f"unsupported agent job status: {status}")
    conn.execute(
        """
        UPDATE agent_jobs
        SET status = ?,
            result_json = ?,
            error = ?,
            updated_at = ?,
            started_at = COALESCE(NULLIF(?, ''), started_at),
            finished_at = COALESCE(NULLIF(?, ''), finished_at)
        WHERE id = ?
        """,
        (
            status,
            json.dumps(result if isinstance(result, dict) else {}, ensure_ascii=False),
            error or "",
            utc_now(),
            started_at or "",
            finished_at or "",
            job_id,
        ),
    )


def run_chickenbro_agent(bounded_context, codex_runner=None):
    if (bounded_context.get("topic") or {}).get("status") != "in_scope":
        answer = deterministic_chickenbro_answer(bounded_context)
        return {
            "answer": answer,
            "topic": bounded_context.get("topic"),
            "validation": {"status": "skipped", "reason": "out_of_scope"},
            "codex": {"status": "skipped"},
        }
    runner = codex_runner or default_chickenbro_codex_runner
    prompt = chickenbro_prompt_from_context(bounded_context)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "answer",
            "confidence",
            "answerLayer",
            "basisLabel",
            "priorityActions",
            "evidenceRefs",
            "limitations",
            "missingInputs",
            "nextQuestion",
        ],
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "string"},
            "answerLayer": {"type": "string", "enum": ["direct_chat", "diagnostic", "evidence"]},
            "basisLabel": {"type": "string"},
            "priorityActions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "evidenceRefs"],
                    "properties": {
                        "title": {"type": "string"},
                        "evidenceRefs": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "evidenceRefs": {"type": "array", "items": {"type": "string"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "missingInputs": {"type": "array", "items": {"type": "string"}},
            "nextQuestion": {"type": "string"},
        },
    }
    try:
        codex_result = runner(prompt, schema=schema)
        if isinstance(codex_result, dict) and codex_result.get("status") in {"skipped", "timed_out", "failed"}:
            raise ValueError(codex_result.get("error") or codex_result.get("status"))
        parsed = parse_chickenbro_codex_output(codex_result)
        validated = validate_chickenbro_codex_output(parsed, bounded_context)
        validated["answerSource"] = "codex"
        return {
            "answer": validated,
            "topic": bounded_context.get("topic"),
            "validation": {"status": "passed"},
            "codex": {"status": (codex_result or {}).get("status", "succeeded") if isinstance(codex_result, dict) else "succeeded"},
        }
    except Exception as error:
        fallback = deterministic_chickenbro_answer(bounded_context)
        return {
            "answer": fallback,
            "topic": bounded_context.get("topic"),
            "validation": {"status": "failed", "error": f"codex_output_invalid: {error}"},
            "codex": {"status": "failed", "error": str(error)},
        }


def send_chickenbro_message_postgres(store, user, payload, message, context, codex_runner=None):
    requested_session_id = clean_text(payload.get("sessionId"), 80)
    if requested_session_id:
        session = store.get_chickenbro_session(user["id"], requested_session_id)["session"]
    else:
        metadata = {
            "createdFrom": "message",
            "context": sanitize_chickenbro_request_context(context),
        }
        session = store.create_chickenbro_session(
            user["id"],
            clean_text(message, 36) or "炸鸡队长对话",
            normalize_chickenbro_phase(context.get("productPhase") or context.get("phase")),
            metadata,
            utc_now(),
        )

    existing_profile = store.load_chickenbro_user_profile(user["id"])
    user_profile = merge_chickenbro_user_profile(existing_profile, context, message)
    store.upsert_chickenbro_user_profile(user["id"], user_profile, utc_now())
    bounded_context = build_chickenbro_bounded_context(message, context, user_profile=user_profile)
    sanitized_request = {
        "message": message,
        "context": sanitize_chickenbro_request_context(context),
        "sessionId": session["sessionId"],
    }
    user_message = store.insert_chickenbro_message(
        user["id"],
        session["sessionId"],
        "user",
        message,
        {"context": sanitized_request["context"]},
        now=utc_now(),
    )
    job_id = store.insert_agent_job(user["id"], session["sessionId"], sanitized_request, bounded_context, utc_now())
    started_at = utc_now()
    store.update_agent_job(user["id"], job_id, "running", started_at=started_at, now=started_at)

    agent_result = run_chickenbro_agent(bounded_context, codex_runner=codex_runner)
    answer_payload = agent_result["answer"]
    job_status = "timed_out" if (agent_result.get("codex") or {}).get("status") == "timed_out" else "succeeded"
    finished_at = utc_now()
    store.update_agent_job(user["id"], job_id, job_status, result=agent_result, finished_at=finished_at, now=finished_at)
    assistant_message = store.insert_chickenbro_message(
        user["id"],
        session["sessionId"],
        "assistant",
        answer_payload.get("answer", ""),
        answer_payload,
        agent_job_id=job_id,
        now=finished_at,
    )
    store.touch_chickenbro_session(user["id"], session["sessionId"], finished_at)
    return {
        "mode": "chickenbro",
        "user": user,
        "session": session,
        "userMessage": user_message,
        "assistantMessage": assistant_message,
        "job": store.get_chickenbro_job(user["id"], job_id),
    }


def send_chickenbro_message(payload, access_token="", codex_runner=None):
    payload = payload if isinstance(payload, dict) else {}
    message = clean_text(payload.get("message") or payload.get("prompt") or payload.get("question"), 4000)
    if not message:
        raise ValueError("chickenbro message is required")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    guest_id = payload.get("guestId") or context.get("guestId") or ""
    user = resolve_chickenbro_user(access_token, guest_id, create_guest=True)
    store = personal_data_store()
    if store:
        return send_chickenbro_message_postgres(store, user, payload, message, context, codex_runner=codex_runner)

    with db_connection() as conn:
        session = find_or_create_chickenbro_session(conn, user, payload.get("sessionId"), message, context)
        user_profile = upsert_chickenbro_user_profile(conn, user["id"], context, message)
        bounded_context = build_chickenbro_bounded_context(message, context, user_profile=user_profile)
        sanitized_request = {
            "message": message,
            "context": sanitize_chickenbro_request_context(context),
            "sessionId": session["sessionId"],
        }
        user_message = insert_chickenbro_message(
            conn,
            user["id"],
            session["sessionId"],
            "user",
            message,
            {"context": sanitized_request["context"]},
        )
        job_id = insert_agent_job(conn, user["id"], session["sessionId"], sanitized_request, bounded_context)
        update_agent_job(conn, job_id, "running", started_at=utc_now())

    agent_result = run_chickenbro_agent(bounded_context, codex_runner=codex_runner)
    answer_payload = agent_result["answer"]
    job_status = "timed_out" if (agent_result.get("codex") or {}).get("status") == "timed_out" else "succeeded"
    finished_at = utc_now()
    with db_connection() as conn:
        update_agent_job(conn, job_id, job_status, result=agent_result, finished_at=finished_at)
        assistant_message = insert_chickenbro_message(
            conn,
            user["id"],
            session["sessionId"],
            "assistant",
            answer_payload.get("answer", ""),
            answer_payload,
            agent_job_id=job_id,
        )
        conn.execute(
            "UPDATE chickenbro_sessions SET updated_at = ? WHERE id = ?",
            (finished_at, session["sessionId"]),
        )
        job_row = conn.execute(
            """
            SELECT id, user_id, session_id, kind, status, request_json, bounded_context_json,
                   result_json, error, created_at, updated_at, started_at, finished_at
            FROM agent_jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    return {
        "mode": "chickenbro",
        "user": user,
        "session": session,
        "userMessage": user_message,
        "assistantMessage": assistant_message,
        "job": public_chickenbro_job_from_row(job_row),
    }


def get_chickenbro_session(access_token, session_id, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")
    store = personal_data_store()
    if store:
        session_payload = store.get_chickenbro_session(user["id"], session_id)
        return {"user": user, **session_payload}
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, title, product_phase, metadata_json, created_at, updated_at
            FROM chickenbro_sessions WHERE user_id = ? AND id = ?
            """,
            (user["id"], session_id),
        ).fetchone()
        if not row:
            raise KeyError("chickenbro session not found")
        message_rows = conn.execute(
            """
            SELECT id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
            FROM chickenbro_messages
            WHERE user_id = ? AND session_id = ?
            ORDER BY created_at
            """,
            (user["id"], session_id),
        ).fetchall()
    return {
        "user": user,
        "session": public_chickenbro_session_from_row(row),
        "messages": [public_chickenbro_message_from_row(message_row) for message_row in message_rows],
    }


def get_chickenbro_job(access_token, job_id, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")
    store = personal_data_store()
    if store:
        return {"user": user, "job": store.get_chickenbro_job(user["id"], job_id)}
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, session_id, kind, status, request_json, bounded_context_json,
                   result_json, error, created_at, updated_at, started_at, finished_at
            FROM agent_jobs
            WHERE user_id = ? AND id = ? AND kind = 'chickenbro'
            """,
            (user["id"], job_id),
        ).fetchone()
    if not row:
        raise KeyError("agent job not found")
    return {"user": user, "job": public_chickenbro_job_from_row(row)}


def load_articles():
    store = content_data_store()
    if store:
        articles = store.load_articles()
        if not articles:
            refresh_articles("bootstrap", collector_enabled=False)
            articles = store.load_articles()
        if articles and not any(is_valid_article(article) for article in articles):
            return []
        return articles
    if postgres_only_runtime_enabled():
        return []
    init_db()
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, channel, category, tags_json, importance,
                   source_name, source_url, published_at, source_note,
                   body_zh, original_title, translation_status, content_status,
                   tag_items_json, blocked_reason, source_id, source_tier,
                   license_status, verification_status, source_badges_json,
                   body_blocks_zh_json, canonical_topic_id, reading_meta_json,
                   translation_fidelity
            FROM news_articles
            WHERE content_status = 'ready'
            ORDER BY published_at DESC, importance DESC
            """
        ).fetchall()
    if not rows:
        refresh_articles("bootstrap", collector_enabled=False)
        with db_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, summary, channel, category, tags_json, importance,
                       source_name, source_url, published_at, source_note,
                       body_zh, original_title, translation_status, content_status,
                       tag_items_json, blocked_reason, source_id, source_tier,
                       license_status, verification_status, source_badges_json,
                       body_blocks_zh_json, canonical_topic_id, reading_meta_json,
                       translation_fidelity
                FROM news_articles
                WHERE content_status = 'ready'
                ORDER BY published_at DESC, importance DESC
                """
            ).fetchall()
    articles = []
    for row in rows:
        articles.append(
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "channel": row[3],
                "category": row[4],
                "tags": json.loads(row[5]),
                "importance": row[6],
                "sourceName": row[7],
                "sourceUrl": row[8],
                "publishedAt": row[9],
                "sourceNote": row[10],
                "bodyZh": row[11],
                "originalTitle": row[12],
                "translationStatus": row[13],
                "contentStatus": row[14],
                "tagItems": safe_json_loads(row[15], [], "news article tag items"),
                "blockedReason": row[16],
                "sourceId": row[17],
                "sourceTier": row[18],
                "licenseStatus": row[19],
                "verificationStatus": row[20],
                "sourceBadges": safe_json_loads(row[21], [], "news article source badges"),
                "bodyBlocksZh": safe_json_loads(row[22], [], "news article translated body blocks"),
                "canonicalTopicId": row[23],
                "readingMeta": safe_json_loads(row[24], {}, "news article reading meta"),
                "translationFidelity": row[25],
            }
        )
    if rows and not any(is_valid_article(article) for article in articles):
        return []
    return articles


def dedupe_articles(articles):
    by_key = {}
    for article in articles:
        key = canonical_article_key(article)
        current = by_key.get(key)
        if not current or (article.get("publishedAt", ""), article.get("importance", 0)) > (current.get("publishedAt", ""), current.get("importance", 0)):
            by_key[key] = article
    return sorted(
        by_key.values(),
        key=lambda item: (item.get("publishedAt", ""), item.get("importance", 0)),
        reverse=True,
    )


def row_to_article(row):
    return {
        "id": row[0],
        "title": row[1],
        "summary": row[2],
        "channel": row[3],
        "category": row[4],
        "tags": json.loads(row[5]),
        "importance": row[6],
        "sourceName": row[7],
        "sourceUrl": row[8],
        "publishedAt": row[9],
        "sourceNote": row[10],
        "bodyZh": row[11],
        "originalTitle": row[12],
        "translationStatus": row[13],
        "contentStatus": row[14],
        "tagItems": safe_json_loads(row[15], [], "news article tag items"),
        "blockedReason": row[16],
        "sourceId": row[17],
        "sourceTier": row[18],
        "licenseStatus": row[19],
        "verificationStatus": row[20],
        "sourceBadges": safe_json_loads(row[21], [], "news article source badges"),
        "bodyBlocksZh": safe_json_loads(row[22], [], "news article translated body blocks"),
        "canonicalTopicId": row[23],
        "readingMeta": safe_json_loads(row[24], {}, "news article reading meta"),
        "translationFidelity": row[25],
    }


def get_article_detail(article_id):
    if not article_id:
        return None
    store = content_data_store()
    if store:
        article = store.get_article(article_id)
        if not article or not is_valid_article(article):
            return None
        return article
    if postgres_only_runtime_enabled():
        return None
    init_db()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, summary, channel, category, tags_json, importance,
                   source_name, source_url, published_at, source_note,
                   body_zh, original_title, translation_status, content_status,
                   tag_items_json, blocked_reason, source_id, source_tier,
                   license_status, verification_status, source_badges_json,
                   body_blocks_zh_json, canonical_topic_id, reading_meta_json,
                   translation_fidelity
            FROM news_articles
            WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
    if not row:
        return None
    article = row_to_article(row)
    if not is_valid_article(article):
        return None
    return article


def count_by_tag(articles, tag):
    return sum(1 for article in articles if tag in article.get("tags", []))


def article_search_text(article):
    tag_items = article.get("tagItems", []) if isinstance(article.get("tagItems"), list) else []
    parts = [
        article.get("title", ""),
        article.get("summary", ""),
        article.get("channel", ""),
        article.get("category", ""),
        article.get("sourceName", ""),
        article.get("sourceTier", ""),
        article.get("verificationStatus", ""),
        *article.get("tags", []),
        *[
            f"{tag.get('id', '')} {tag.get('label', '')}"
            for tag in tag_items
            if isinstance(tag, dict)
        ],
    ]
    return " ".join(str(part) for part in parts).lower()


def channels_with_counts(articles):
    return [
        {
            **channel,
            "updateCount": sum(1 for article in articles if article.get("channel") == channel["title"]),
        }
        for channel in CHANNELS
    ]


def article_list_title(query):
    if query.get("type") == "channel":
        return query.get("value") or "资讯列表"
    key = query.get("key")
    if key == "class-change":
        return "职业变动"
    if key == "ptr":
        return "测试服重点"
    if key == "official":
        return "官方"
    if key == "updates":
        return "更新"
    if key == "events":
        return "活动"
    if key == "community":
        return "社区"
    if key == "guides":
        return "攻略"
    if key == "mythic-plus":
        return "大秘境"
    if key == "gear":
        return "装备"
    if key == "system":
        return "系统"
    return "今日更新"


def filter_articles(articles, query):
    if query.get("type") == "channel":
        return [article for article in articles if article.get("channel") == query.get("value")]
    key = query.get("key")
    if key == "class-change":
        return [article for article in articles if "class-change" in article.get("tags", [])]
    if key == "ptr":
        return [article for article in articles if article.get("channel") == "测试服前瞻"]
    if key == "official":
        return [
            article
            for article in articles
            if re.search(r"blizzard|官方|official|official_verified", article_search_text(article))
        ]
    if key == "updates":
        return [
            article
            for article in articles
            if re.search(r"content-update|hotfix|patch|ptr|beta|class-change|更新|热修|测试服|职业调整", article_search_text(article))
        ]
    if key == "events":
        return [
            article
            for article in articles
            if re.search(r"event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways", article_search_text(article))
        ]
    if key == "community":
        return [
            article
            for article in articles
            if re.search(r"community|社区|wowhead|icy veins|icy-veins", article_search_text(article))
        ]
    if key == "guides":
        return [
            article
            for article in articles
            if re.search(r"guide|攻略|指南|how to|玩法|build|rotation|simc|wcl", article_search_text(article))
        ]
    if key == "mythic-plus":
        return [
            article
            for article in articles
            if re.search(r"mythic[- ]?plus|mythic\+|keystone|m\+|大秘|史诗钥石|秘境", article_search_text(article))
        ]
    if key == "gear":
        return [
            article
            for article in articles
            if re.search(r"gear|item|loot|trinket|weapon|armor|tier[- ]?set|equipment|装备|物品|战利品|饰品|武器|护甲|套装", article_search_text(article))
        ]
    if key == "system":
        return [
            article
            for article in articles
            if re.search(r"system|feature|interface|warband|delve|housing|profession|collection|account|系统|功能|界面|战团|地下堡|住房|专业|收藏|账号", article_search_text(article))
        ]
    return articles


def build_article_list_payload(query):
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    filtered = filter_articles(articles, query)
    payload = {
        "title": article_list_title(query),
        "type": query.get("type", "metric"),
        "key": query.get("key", ""),
        "value": query.get("value", ""),
        "count": len(filtered),
        "articles": filtered,
    }
    if postgres_only_runtime_enabled() and not content_data_store():
        payload["dataStatus"] = "blocked"
        payload["errors"] = ["PostgreSQL content store is not available"]
    return payload


def build_home_payload():
    state = latest_refresh_state()
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    articles.sort(key=lambda item: (item.get("publishedAt", ""), item.get("importance", 0)), reverse=True)
    payload = {
        "navTitle": "最新资讯",
        "heroNews": articles[:3],
        "metrics": [
            {"key": "today", "value": str(len(articles)), "label": "今日更新"},
            {"key": "updates", "value": str(len(filter_articles(articles, {"type": "metric", "key": "updates"}))), "label": "更新"},
            {"key": "class-change", "value": str(count_by_tag(articles, "class-change")), "label": "职业变动"},
            {"key": "events", "value": str(len(filter_articles(articles, {"type": "metric", "key": "events"}))), "label": "活动"},
            {"key": "ptr", "value": str(sum(1 for article in articles if article.get("channel") == "测试服前瞻")), "label": "测试服重点"},
        ],
        "channels": channels_with_counts(articles),
        "highlights": articles[3:9],
        "lastRefreshedAt": state["lastRefreshedAt"],
        "refreshMode": state["refreshMode"],
    }
    if state.get("dataStatus"):
        payload["dataStatus"] = state.get("dataStatus")
    if state.get("errors"):
        payload["errors"] = state.get("errors")
    return payload


def load_js_payload(module_path, export_name, *args):
    script = """
const modulePath = process.argv[1]
const exportName = process.argv[2]
const args = process.argv.slice(3).map((value) => JSON.parse(value))
const mod = require(modulePath)
const target = mod[exportName]
if (typeof target !== 'function') {
  throw new Error(`Missing export ${exportName}`)
}
const result = target(...args)
process.stdout.write(JSON.stringify(result))
"""
    command = [
        "node",
        "-e",
        script,
        str(PROJECT_DIR / module_path),
        export_name,
        *[json.dumps(arg, ensure_ascii=False) for arg in args],
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=PROJECT_DIR,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "node payload failed").strip())
    return json.loads(completed.stdout)


def runtime_raiderio_payload():
    store = cache_data_store()
    if store and hasattr(store, "get_raiderio_payload"):
        try:
            payload = store.get_raiderio_payload()
            if isinstance(payload, dict) and payload:
                payload.setdefault("sourceStatus", payload.get("status") or "blocked")
                return payload
        except Exception as error:
            return {
                "sourceStatus": "blocked",
                "status": "blocked",
                "errors": [str(error)],
            }
    return {
        "sourceStatus": "blocked",
        "status": "blocked",
        "errors": ["PostgreSQL Raider.IO cache is missing"],
    }


def get_builds_home_payload():
    payload = apply_runtime_season_gate(load_js_payload("server/builds/home-payload.js", "buildSpecializationHomePayload"), "builds_home")
    if postgres_only_runtime_enabled():
        return enrich_raiderio_builds_home_payload(payload, runtime_raiderio_payload())
    try:
        init_db()
        with db_connection() as conn:
            return enrich_raiderio_builds_home_payload(payload, get_raiderio_payload(conn))
    except Exception as error:
        if isinstance(payload, dict):
            payload["raiderioError"] = str(error)
        return payload


def get_builds_intel_payload():
    payload = apply_runtime_season_gate(load_js_payload("server/builds/home-payload.js", "buildSpecializationIntelPayload"), "builds_intel")
    if postgres_only_runtime_enabled():
        return enrich_raiderio_builds_intel_payload(payload, runtime_raiderio_payload())
    try:
        init_db()
        with db_connection() as conn:
            return enrich_raiderio_builds_intel_payload(payload, get_raiderio_payload(conn))
    except Exception as error:
        if isinstance(payload, dict):
            payload["raiderioError"] = str(error)
        return payload


def get_builds_detail_payload(spec_id):
    payload = load_js_payload("server/builds/home-payload.js", "getSpecializationDetail", spec_id)
    payload = apply_runtime_season_gate(payload, "builds_detail") if payload else payload
    if not payload:
        return payload
    if postgres_only_runtime_enabled():
        payload = enrich_raiderio_builds_detail_payload(payload, runtime_raiderio_payload())
        store = cache_data_store()
        if store and hasattr(store, "enrich_builds_detail_stat_weights"):
            try:
                payload = store.enrich_builds_detail_stat_weights(payload)
            except Exception as error:
                payload["statWeightError"] = str(error)
        else:
            payload["statWeightError"] = "PostgreSQL stat-weight detail cache is not available"
        payload["gearMetadataError"] = "PostgreSQL detail gear enrichment is not available in PG-only runtime"
        return payload
    try:
        init_db()
        with db_connection() as conn:
            ensure_websim_tables(conn)
            payload = enrich_raiderio_builds_detail_payload(payload, get_raiderio_payload(conn))
            payload = enrich_build_gear_payload(conn, payload)
            return enrich_builds_detail_stat_weights(conn, payload)
    except Exception as error:
        payload["gearMetadataError"] = str(error)
        return payload


def get_pve_home_payload():
    payload = apply_runtime_season_gate(load_js_payload("server/pve/home-payload.js", "buildPveHomePayload"), "pve_home")
    if postgres_only_runtime_enabled():
        return enrich_raiderio_pve_home_payload(payload, runtime_raiderio_payload())
    try:
        init_db()
        with db_connection() as conn:
            return enrich_raiderio_pve_home_payload(payload, get_raiderio_payload(conn))
    except Exception as error:
        if isinstance(payload, dict):
            payload["raiderioError"] = str(error)
        return payload


def get_pve_module_payload(module_key):
    payload = apply_runtime_season_gate(load_js_payload("server/pve/home-payload.js", "getPveModuleDetail", module_key), "pve_module")
    if postgres_only_runtime_enabled():
        return enrich_raiderio_pve_module_payload(payload, runtime_raiderio_payload())
    try:
        init_db()
        with db_connection() as conn:
            return enrich_raiderio_pve_module_payload(payload, get_raiderio_payload(conn))
    except Exception as error:
        if isinstance(payload, dict):
            payload["raiderioError"] = str(error)
        return payload


def runtime_season_payload():
    store = cache_data_store()
    if store:
        try:
            payload = store.get_active_season_payload()
        except Exception:
            payload = {}
        if postgres_only_runtime_enabled():
            if isinstance(payload, dict) and payload:
                return payload
            return {
                "seasonId": "",
                "id": "",
                "seasonLabel": "",
                "label": "",
                "seasonRevision": "",
                "revision": "",
                "locale": "",
                "dataStatus": "blocked",
                "verifiedAt": "",
                "expiresAt": "",
                "sourceRefs": [],
                "errors": ["PostgreSQL active season cache is missing"],
                "dungeons": [],
            }
        if isinstance(payload, dict) and payload.get("dataStatus") == "verified":
            return payload
    if postgres_only_runtime_enabled():
        return {
            "seasonId": "",
            "id": "",
            "seasonLabel": "",
            "label": "",
            "seasonRevision": "",
            "revision": "",
            "locale": "",
            "dataStatus": "blocked",
            "verifiedAt": "",
            "expiresAt": "",
            "sourceRefs": [],
            "errors": ["PostgreSQL cache store is not available"],
            "dungeons": [],
        }
    init_db()
    with db_connection() as conn:
        return get_active_season_payload(conn)


def runtime_season_payload_with_raiderio():
    season = runtime_season_payload()
    if postgres_only_runtime_enabled():
        season["raiderio"] = runtime_raiderio_payload()
        return season
    init_db()
    with db_connection() as conn:
        return enrich_game_season_payload(season, get_raiderio_payload(conn))


def runtime_stat_weight_latest_payload():
    if postgres_only_runtime_enabled():
        cache_store = cache_data_store()
        if cache_store and hasattr(cache_store, "latest_stat_weight_run_payload"):
            try:
                payload = cache_store.latest_stat_weight_run_payload()
            except Exception as error:
                payload = {"sourceStatus": "blocked", "status": "blocked", "errors": [str(error)]}
            if isinstance(payload, dict) and payload:
                payload.setdefault("sourceStatus", payload.get("status") or "blocked")
                payload.setdefault("status", payload.get("sourceStatus") or "blocked")
                payload.setdefault("errors", [])
                return payload
        if cache_store and hasattr(cache_store, "get_sync_state"):
            payload = postgres_only_stat_weights_sync_state(cache_store)
            if isinstance(payload, dict) and payload:
                payload.setdefault("sourceStatus", payload.get("status") or "blocked")
                payload.setdefault("status", payload.get("sourceStatus") or "blocked")
                payload.setdefault("errors", [])
                return payload
        return {
            "sourceStatus": "blocked",
            "status": "blocked",
            "errors": ["PostgreSQL stat weight cache is missing"],
        }
    init_db()
    with db_connection() as conn:
        return latest_stat_weight_run_payload(conn)


def runtime_websim_bootstrap_payload():
    if postgres_only_runtime_enabled():
        cache_store = cache_data_store()
        if cache_store and hasattr(cache_store, "get_websim_bootstrap"):
            try:
                payload = cache_store.get_websim_bootstrap()
                if isinstance(payload, dict) and payload:
                    return payload
            except Exception as error:
                return {
                    "navTitle": "WebSim",
                    "title": "SimC 构筑工坊",
                    "dataStatus": "blocked",
                    "instances": [],
                    "syncState": {"ok": False, "errors": [str(error)]},
                    "blockers": [str(error)],
                }
        return {
            "navTitle": "WebSim",
            "title": "SimC 构筑工坊",
            "dataStatus": "blocked",
            "instances": [],
            "syncState": {"ok": False, "errors": ["PostgreSQL WebSim bootstrap cache is missing"]},
            "blockers": ["PostgreSQL WebSim bootstrap cache is missing"],
        }
    init_db()
    with db_connection() as conn:
        return get_websim_bootstrap(conn)


def runtime_websim_assets_payload(filters):
    if postgres_only_runtime_enabled():
        cache_store = cache_data_store()
        if cache_store and hasattr(cache_store, "get_websim_assets"):
            try:
                payload = cache_store.get_websim_assets(filters)
                if isinstance(payload, dict) and payload:
                    return payload
            except Exception as error:
                return {
                    "assets": [],
                    "counts": {"byStatus": {}, "bySource": {}},
                    "status": "blocked",
                    "blockers": [str(error)],
                }
        return {
            "assets": [],
            "counts": {"byStatus": {}, "bySource": {}},
            "status": "blocked",
            "blockers": ["PostgreSQL WebSim asset registry is not available"],
        }
    init_db()
    with db_connection() as conn:
        return get_websim_assets(conn, filters)


def runtime_websim_loot_payload(filters):
    store = cache_data_store()
    if store:
        try:
            payload = store.get_websim_loot(filters)
        except Exception:
            payload = {}
        if postgres_only_runtime_enabled():
            if isinstance(payload, dict) and payload:
                return payload
            return {
                "schemaRevision": "websim-loot-v1",
                "dataStatus": "blocked",
                "items": [],
                "blockers": ["PostgreSQL WebSim loot cache is missing"],
            }
        if isinstance(payload, dict) and (payload.get("dataStatus") == "verified" or payload.get("items")):
            return payload
    if postgres_only_runtime_enabled():
        return {
            "schemaRevision": "websim-loot-v1",
            "dataStatus": "blocked",
            "items": [],
            "blockers": ["PostgreSQL cache store is not available"],
        }
    init_db()
    with db_connection() as conn:
        return get_websim_loot(conn, filters)


def websim_gear_payload_has_items(payload):
    if not isinstance(payload, dict):
        return False
    for group in payload.get("replacementCandidates") or []:
        if isinstance(group, dict) and group.get("items"):
            return True
    return bool(payload.get("catalogItems"))


WEBSIM_GEAR_INITIAL_CANDIDATE_LIMIT = 4
WEBSIM_GEAR_INITIAL_CANDIDATE_KEYS = {
    "id",
    "itemId",
    "key",
    "slot",
    "simcSlot",
    "name",
    "displayName",
    "iconUrl",
    "quality",
    "ilevel",
    "itemLevel",
    "source",
    "sourceName",
    "sourceType",
    "sourceStatus",
    "status",
    "dataStatus",
    "difficultyKey",
    "difficultyLabel",
    "variantKey",
    "defaultVariantKey",
    "variantLabel",
    "primaryStatKey",
    "primaryStatLabel",
    "bonus_id",
    "gem_id",
    "gem_bonus_id",
    "gem_ilevel",
    "enchant_id",
    "crafted_stats",
    "embellishment",
    "craftedStatOptionKey",
    "selectedCraftedStatKey",
    "socketOptionLabel",
    "enchantOptionLabel",
    "embellishmentOptionLabel",
    "armorType",
    "weaponType",
    "itemSetName",
    "hasBuiltInEmbellishment",
    "builtInEmbellishment",
    "intrinsicEmbellishment",
    "inherentEmbellishment",
    "builtInEmbellishmentLabel",
    "embellishmentSource",
    "compatibility",
    "missingFields",
    "blockers",
    "variantBlockers",
    "simcReady",
    "simcIlevelOnly",
    "modCapabilities",
}


def websim_gear_initial_candidate(item):
    if not isinstance(item, dict):
        return item
    slim = {
        key: copy.deepcopy(item[key])
        for key in WEBSIM_GEAR_INITIAL_CANDIDATE_KEYS
        if key in item and item[key] not in (None, "")
    }
    sources = item.get("sources") if isinstance(item.get("sources"), list) else []
    first_source = next((source for source in sources if isinstance(source, dict)), {})
    if first_source:
        slim.setdefault(
            "source",
            first_source.get("label") or first_source.get("sourceLabel") or first_source.get("source") or "",
        )
        slim.setdefault("sourceType", first_source.get("sourceType") or first_source.get("type") or "")
    slim["detailMode"] = "summary"
    slim["slotDetailAvailable"] = True
    return slim


def websim_gear_initial_group(group):
    if not isinstance(group, dict):
        return group
    slim = {
        key: copy.deepcopy(value)
        for key, value in group.items()
        if key != "items"
    }
    items = group.get("items") if isinstance(group.get("items"), list) else []
    slim["items"] = [
        websim_gear_initial_candidate(item)
        for item in items[:WEBSIM_GEAR_INITIAL_CANDIDATE_LIMIT]
    ]
    slim["detailMode"] = "partial"
    slim["fullItemCount"] = len(items)
    return slim


def websim_gear_payload_for_mode(payload, mode="", slot=""):
    if not isinstance(payload, dict):
        return payload
    normalized_mode = str(mode or "").strip().lower()
    normalized_slot = str(slot or "").strip()
    if normalized_mode == "initial":
        output = copy.deepcopy(payload)
        output["gearPayloadMode"] = "initial"
        output["gearInitialCandidateLimit"] = WEBSIM_GEAR_INITIAL_CANDIDATE_LIMIT
        for group_key in ("replacementCandidates", "slotGroups"):
            if isinstance(output.get(group_key), list):
                output[group_key] = [websim_gear_initial_group(group) for group in output[group_key]]
        return output
    if normalized_mode == "slot" and normalized_slot:
        output = copy.deepcopy(payload)
        output["gearPayloadMode"] = "slot"
        output["gearSlot"] = normalized_slot
        for group_key in ("replacementCandidates", "slotGroups"):
            if isinstance(output.get(group_key), list):
                output[group_key] = [
                    group
                    for group in output[group_key]
                    if isinstance(group, dict) and (group.get("slot") or group.get("simcSlot")) == normalized_slot
                ]
                for group in output[group_key]:
                    group["detailMode"] = "complete"
        return output
    return payload


def websim_gear_payload_with_template_legality(payload):
    if not isinstance(payload, dict):
        return payload
    class_key = str(payload.get("classKey") or "").strip()
    spec_key = str(payload.get("specKey") or "").strip()
    if not class_key:
        return payload
    changed = False
    output = payload
    selected_blockers = []
    equipped_set = payload.get("equippedSet")
    if isinstance(equipped_set, dict):
        equipped_items = [
            item
            for item in equipped_set.values()
            if isinstance(item, dict)
        ]
        blockers, invalid_slots = selected_gear_weapon_rule_blockers(equipped_items, class_key, spec_key)
        if invalid_slots:
            output = dict(payload)
            output["equippedSet"] = {
                slot: item
                for slot, item in equipped_set.items()
                if slot not in invalid_slots
            }
            changed = True
            selected_blockers.extend(blockers)
    baseline_set = payload.get("baselineSet")
    if isinstance(baseline_set, list):
        blockers, invalid_slots = selected_gear_weapon_rule_blockers(baseline_set, class_key, spec_key)
        if invalid_slots:
            if output is payload:
                output = dict(payload)
            output["baselineSet"] = [
                item
                for item in baseline_set
                if not (
                    isinstance(item, dict)
                    and (item.get("slot") or item.get("simcSlot")) in invalid_slots
                )
            ]
            changed = True
            selected_blockers.extend(blockers)
    for template_key in ("communityTemplates", "baselineTemplates"):
        templates = payload.get(template_key)
        if not isinstance(templates, list):
            continue
        gated_templates = []
        for template in templates:
            gated = apply_gear_template_legality_gate(template, class_key, spec_key)
            if gated is not template:
                changed = True
            gated_templates.append(gated)
        if changed and output is payload:
            output = dict(payload)
        if output is not payload:
            output[template_key] = gated_templates
    if changed:
        output["communityTemplateSync"] = websim_gear_community_template_sync_state(
            [
                *(output.get("communityTemplates") or []),
                *(output.get("baselineTemplates") or []),
            ]
        )
    template_sync = output.get("communityTemplateSync") if isinstance(output.get("communityTemplateSync"), dict) else {}
    templates_for_sync = [
        *(output.get("communityTemplates") or []),
        *(output.get("baselineTemplates") or []),
    ]
    if templates_for_sync and not isinstance(template_sync.get("templateChains"), dict):
        if output is payload:
            output = dict(payload)
        output["communityTemplateSync"] = websim_gear_community_template_sync_state(templates_for_sync)
    if selected_blockers:
        output["gearLegalityBlockers"] = list(dict.fromkeys(
            [
                *(output.get("gearLegalityBlockers") or []),
                *selected_blockers,
            ]
        ))
    return output


def current_gear_simc_runtime_revision():
    simc_status = simc_version_status()
    websim_state = simc_status.get("websimState") if isinstance(simc_status.get("websimState"), dict) else {}
    for candidate in (
        simc_status.get("sourceCommit"),
        simc_status.get("simcRuntimeRevision"),
        simc_status.get("localTag"),
    ):
        value = str(candidate or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    source_match = re.search(r"(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])", str(websim_state.get("source") or "").lower())
    if source_match:
        return source_match.group(1)
    return first_text_value(
        simc_status.get("simcRuntimeRevision"),
        simc_status.get("localTag"),
        simc_status.get("sourceCommit"),
    )


def websim_gear_payload_with_resolver_context(payload, store, class_key, spec_key):
    if not isinstance(payload, dict) or not payload:
        return payload
    binding = payload.get("_activeManifestBinding") if isinstance(payload.get("_activeManifestBinding"), dict) else None
    public_payload = (
        {key: value for key, value in payload.items() if key != "_activeManifestBinding"}
        if "_activeManifestBinding" in payload
        else payload
    )
    if not callable(getattr(store, "get_gear_resolver_context", None)):
        return public_payload
    simc_revision = current_gear_simc_runtime_revision()
    if not simc_revision:
        return public_payload
    try:
        runtime_authority = gear_resolver_runtime_authority(
            class_key,
            spec_key,
            simc_runtime_revision=simc_revision,
        )
        if binding is not None:
            resolver_context = store.get_gear_resolver_context(runtime_authority, binding=binding)
        else:
            resolver_context = store.get_gear_resolver_context(runtime_authority)
    except Exception:
        return public_payload
    if not isinstance(resolver_context, dict) or not resolver_context:
        return public_payload
    return {**public_payload, "resolverContext": resolver_context}


def runtime_websim_gear_payload(class_key, spec_key, compact=False, mode="", slot=""):
    store = cache_data_store()
    allow_sqlite_fallback = (
        os.environ.get("WOW_ALLOW_SQLITE_PUBLIC_CACHE_FALLBACK") == "1"
        and not postgres_only_runtime_enabled()
    )
    if store:
        try:
            try:
                payload = store.get_websim_gear(class_key, spec_key, compact=compact, mode=mode, slot=slot)
            except TypeError as exc:
                if "unexpected keyword" not in str(exc):
                    raise
                payload = store.get_websim_gear(class_key, spec_key, compact=compact)
            payload = websim_gear_payload_with_resolver_context(
                payload,
                store,
                class_key,
                spec_key,
            )
        except Exception:
            payload = {}
        if postgres_only_runtime_enabled():
            if isinstance(payload, dict) and payload:
                return websim_gear_payload_with_template_legality(payload)
            return {
                "schemaRevision": "websim-gear-v1",
                "classKey": class_key,
                "specKey": spec_key,
                "dataStatus": "blocked",
                "catalogStatus": "blocked",
                "catalogBlockers": ["PostgreSQL WebSim gear cache is missing"],
                "replacementCandidates": [],
                "slots": [],
                "communityTemplates": [],
            }
        if isinstance(payload, dict) and payload:
            if payload.get("dataStatus") == "verified" and websim_gear_payload_has_items(payload):
                return websim_gear_payload_with_template_legality(payload)
            if not allow_sqlite_fallback:
                return websim_gear_payload_with_template_legality(payload)
    if postgres_only_runtime_enabled():
        return {
            "schemaRevision": "websim-gear-v1",
            "classKey": class_key,
            "specKey": spec_key,
            "dataStatus": "blocked",
            "catalogStatus": "blocked",
            "catalogBlockers": ["PostgreSQL cache store is not available"],
            "replacementCandidates": [],
            "slots": [],
            "communityTemplates": [],
        }
    init_db()
    with db_connection() as conn:
        return websim_gear_payload_with_template_legality(
            get_websim_gear(conn, class_key, spec_key, compact=compact)
        )


def websim_talent_payload_has_nodes(payload):
    return isinstance(payload, dict) and bool(payload.get("nodes"))


def runtime_websim_talents_payload(class_key, spec_key, hero_key=""):
    store = cache_data_store()
    if store:
        try:
            payload = store.get_websim_talents(class_key, spec_key, hero_key)
        except Exception:
            payload = {}
        if postgres_only_runtime_enabled():
            if isinstance(payload, dict) and payload:
                return payload
            return {
                "schemaRevision": "websim-talents-v1",
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": hero_key,
                "dataStatus": "blocked",
                "talentStatus": "blocked",
                "nodes": [],
                "presets": [],
                "communityTemplates": [],
                "blockers": ["PostgreSQL WebSim talent cache is missing"],
            }
        if (
            isinstance(payload, dict)
            and payload.get("dataStatus") == "verified"
            and websim_talent_payload_has_nodes(payload)
        ):
            return payload
    if postgres_only_runtime_enabled():
        return {
            "schemaRevision": "websim-talents-v1",
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
            "dataStatus": "blocked",
            "talentStatus": "blocked",
            "nodes": [],
            "presets": [],
            "communityTemplates": [],
            "blockers": ["PostgreSQL cache store is not available"],
        }
    init_db()
    with db_connection() as conn:
        return get_websim_talents(conn, class_key, spec_key, hero_key)


def runtime_websim_talent_import_payload(class_key, spec_key, hero_key=""):
    store = cache_data_store()
    if store and hasattr(store, "get_websim_talent_import"):
        try:
            payload = store.get_websim_talent_import(class_key, spec_key, hero_key)
        except Exception:
            payload = {}
        if postgres_only_runtime_enabled():
            if isinstance(payload, dict) and payload:
                return payload
            return websim_talent_import_response(
                class_key,
                spec_key,
                hero_key,
                blockers=["PostgreSQL talent import cache is missing"],
            )
        if isinstance(payload, dict) and payload:
            return payload
    if postgres_only_runtime_enabled():
        return websim_talent_import_response(
            class_key,
            spec_key,
            hero_key,
            blockers=["PostgreSQL cache store is not available"],
        )
    init_db()
    with db_connection() as conn:
        return get_websim_talent_import(conn, class_key, spec_key, hero_key)


def runtime_talent_api_store():
    if not postgres_only_runtime_enabled():
        return None
    store = cache_data_store()
    if store and hasattr(store, "get_websim_talents"):
        return store
    return None


def postgres_only_talent_validation_payload(payload):
    store = runtime_talent_api_store()
    if store:
        return validate_talent_api_payload(store, payload)
    source = payload if isinstance(payload, dict) else {}
    parsed = parse_websim_talent_export_code(source.get("code") or source.get("talents") or source.get("websimExportCode") or "")
    request_payload = {**source, **parsed} if parsed else dict(source)
    try:
        encoding = encode_websim_talents(None, request_payload)
    except Exception as error:
        encoding = {
            "status": "failed",
            "source": "postgres_only",
            "schemaRevision": "websim-talent-rules-v1",
            "errors": [str(error)],
            "warnings": [],
            "lines": [],
            "selectedCounts": {"class": 0, "spec": 0, "hero": 0},
        }
    blockers = ["PostgreSQL talent authority store is not available"]
    return {
        **encoding,
        "classKey": request_payload.get("classKey") or "",
        "specKey": request_payload.get("specKey") or "",
        "heroKey": request_payload.get("heroKey") or "",
        "talentState": {"selectedNodes": []},
        "talentAuthority": {"runtime": {"status": "blocked"}, "blockers": blockers},
        "talentReadiness": {"status": "blocked", "blockers": blockers},
        "blockers": blockers,
    }


def runtime_validate_talent_api_payload(payload):
    if postgres_only_runtime_enabled():
        return postgres_only_talent_validation_payload(payload)
    init_db()
    with db_connection() as conn:
        return validate_talent_api_payload(conn, payload)


def runtime_export_talent_api_payload(payload):
    if postgres_only_runtime_enabled():
        store = runtime_talent_api_store()
        if store:
            return export_talent_api_payload(store, payload)
        validation = postgres_only_talent_validation_payload(payload)
        return {
            "classKey": validation.get("classKey") or "",
            "specKey": validation.get("specKey") or "",
            "heroKey": validation.get("heroKey") or "",
            "talentState": validation.get("talentState") or {"selectedNodes": []},
            "websimExportCode": str((payload or {}).get("websimExportCode") or ""),
            "validation": validation,
            "talentSchemaRevision": validation.get("schemaRevision") or "websim-talent-rules-v1",
        }
    init_db()
    with db_connection() as conn:
        return export_talent_api_payload(conn, payload)


def runtime_import_talent_api_payload(payload):
    if postgres_only_runtime_enabled():
        store = runtime_talent_api_store()
        if store:
            return import_talent_api_payload(store, payload)
        source = payload if isinstance(payload, dict) else {}
        raw_import_code = str(source.get("code") or source.get("talents") or source.get("websimExportCode") or "").strip()
        validation = postgres_only_talent_validation_payload({"talents": raw_import_code} if raw_import_code else source)
        return {
            "classKey": source.get("classKey") or "",
            "specKey": source.get("specKey") or "",
            "heroKey": source.get("heroKey") or "",
            "rawImportCode": raw_import_code,
            "talentState": validation.get("talentState") or {"selectedNodes": []},
            "validation": validation,
            "talentSchemaRevision": validation.get("schemaRevision") or "websim-talent-rules-v1",
        }
    init_db()
    with db_connection() as conn:
        return import_talent_api_payload(conn, payload)


def safe_positive_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def has_verified_external_pve_sources(payload):
    if not isinstance(payload, dict) or payload.get("key") != "specLadder":
        return False
    source_checks = payload.get("sourceChecks")
    if not isinstance(source_checks, list):
        return False
    verified_sources = {
        source.get("key"): source
        for source in source_checks
        if source.get("status") in {"verified", "synced", "partial", "stale"} and safe_positive_int(source.get("sampleCount")) > 0
    }
    if verified_sources.get("raiderio"):
        return True
    return {"archon", "warcraftlogs"}.issubset(set(verified_sources))


def has_source_backed_pve_items(payload):
    if not isinstance(payload, dict):
        return False
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        if not str(item.get("sourceUrl") or "").startswith("https://"):
            return False
        if not str(item.get("sourceName") or "").strip():
            return False
        if not str(item.get("analysisWindow") or "").strip():
            return False
    return True


def has_source_backed_pve_home(payload):
    if not isinstance(payload, dict):
        return False
    zones = payload.get("zones")
    if not isinstance(zones, list) or not zones:
        return False
    for zone in zones:
        modules = zone.get("modules") if isinstance(zone, dict) else None
        if not isinstance(modules, list):
            continue
        for module in modules:
            if has_verified_external_pve_sources(module) or has_source_backed_pve_items(module):
                return True
    return False


def apply_runtime_season_gate(payload, payload_type):
    if not isinstance(payload, dict):
        return payload
    season = runtime_season_payload()
    gated = dict(payload)
    gated.update(
        {
            "currentSeason": season,
            "seasonId": season.get("seasonId") or season.get("id") or "",
            "seasonLabel": season.get("seasonLabel") or season.get("label") or "",
            "seasonRevision": season.get("seasonRevision") or season.get("revision") or "",
            "verifiedAt": season.get("verifiedAt") or "",
            "expiresAt": season.get("expiresAt") or "",
            "locale": season.get("locale") or "",
            "dataStatus": season.get("dataStatus") or "blocked",
            "sourceRefs": season.get("sourceRefs") or [],
        }
    )
    if gated["dataStatus"] == "verified":
        return gated

    gated["blockedReason"] = "赛季数据尚未通过暴雪官方 API 校验，暂不返回可能过期的天赋、装备或副本数据。"
    if payload_type == "pve_home" and has_source_backed_pve_home(gated):
        gated["runtimeSeasonGate"] = "external_sources_available"
        return gated

    if payload_type == "pve_module" and has_verified_external_pve_sources(gated):
        gated["runtimeSeasonGate"] = "external_sources_verified"
        return gated
    if payload_type == "pve_module" and has_source_backed_pve_items(gated):
        gated["runtimeSeasonGate"] = "external_sources_available"
        return gated

    if payload_type == "pve_home":
        gated["zones"] = []
    elif payload_type == "pve_module":
        gated["items"] = []
        gated["itemCount"] = 0
    elif payload_type == "builds_home":
        gated["featuredSpecializations"] = []
        gated["specializations"] = []
    elif payload_type == "builds_intel":
        gated["items"] = []
        gated["count"] = 0
    elif payload_type == "builds_detail":
        gated["details"] = {}
    return gated


def analytics_admin_authorized(headers):
    expected = os.environ.get("WOW_ANALYTICS_ADMIN_TOKEN", "").strip()
    if not expected:
        return False
    token = bearer_token_from_headers(headers)
    return secrets.compare_digest(token, expected)


def analytics_admin_page():
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WOW Analytics</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #111; color: #eee; }
    header { padding: 24px; border-bottom: 1px solid #333; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    input, button, select { background: #181818; color: #eee; border: 1px solid #444; border-radius: 6px; padding: 9px 10px; }
    button { cursor: pointer; background: #f8b700; color: #151515; border-color: #f8b700; font-weight: 700; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { background: #181818; border: 1px solid #333; border-radius: 8px; padding: 16px; }
    .metric { font-size: 28px; font-weight: 700; margin-top: 6px; color: #f8b700; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border-bottom: 1px solid #2b2b2b; padding: 8px; text-align: left; vertical-align: top; }
    th { color: #c7b077; font-weight: 700; }
    code { color: #f8b700; }
    .section { margin-top: 18px; }
    .muted { color: #aaa; }
  </style>
</head>
<body>
  <header>
    <h1>WOW 用户行为统计</h1>
    <p class="muted">输入管理员 token 后查看自建事件统计。openid 已脱敏，事件属性已过滤敏感正文。</p>
  </header>
  <main>
    <div class="toolbar">
      <input id="token" type="password" placeholder="WOW_ANALYTICS_ADMIN_TOKEN">
      <input id="from" type="date">
      <input id="to" type="date">
      <button id="load">加载统计</button>
    </div>
    <div id="summary" class="grid"></div>
    <div class="section grid">
      <div class="card"><h2>功能事件</h2><table id="features"></table></div>
      <div class="card"><h2>页面排行</h2><table id="pages"></table></div>
    </div>
    <div class="section card">
      <h2>SimC / WCL</h2>
      <table id="simulator"></table>
    </div>
    <div class="section card">
      <h2>最近事件</h2>
      <table id="events"></table>
    </div>
  </main>
  <script>
    const today = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
    document.getElementById('from').value = weekAgo;
    document.getElementById('to').value = today;
    async function api(path) {
      const token = document.getElementById('token').value.trim();
      const from = document.getElementById('from').value;
      const to = document.getElementById('to').value;
      const sep = path.includes('?') ? '&' : '?';
      const res = await fetch(`${path}${sep}from=${from}&to=${to}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    }
    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }
    function table(id, headers, rows) {
      document.getElementById(id).innerHTML = '<tr>' + headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr>' +
        rows.map(row => '<tr>' + row.map(value => `<td>${escapeHtml(value)}</td>`).join('') + '</tr>').join('');
    }
    async function load() {
      const [summary, features, pages, simulator, events] = await Promise.all([
        api('/api/admin/analytics/summary'),
        api('/api/admin/analytics/features'),
        api('/api/admin/analytics/pages'),
        api('/api/admin/analytics/simulator'),
        api('/api/admin/analytics/events')
      ]);
      const s = summary.summary;
      document.getElementById('summary').innerHTML = [
        ['PV', s.pv], ['UV', s.uv], ['登录 UV', s.loginUv], ['访客 UV', s.guestUv], ['会话', s.sessions], ['活跃用户', s.activeUsers]
      ].map(item => `<div class="card"><div>${item[0]}</div><div class="metric">${item[1]}</div></div>`).join('');
      table('features', ['分组/事件', '次数'], features.events.slice(0, 20).map(item => [`${item.group} / ${item.eventName}`, item.count]));
      table('pages', ['页面', 'PV', 'UV'], pages.pages.slice(0, 20).map(item => [item.page, item.pv, item.uv]));
      table('simulator', ['Mode', 'Status', 'Spec', 'Ran', 'DPS', '时间'], simulator.tasks.slice(0, 30).map(item => [item.mode, item.agentStatus || item.status, item.specId, item.simulationRan, item.dps, item.createdAt]));
      table('events', ['事件', '用户', '页面', '时间', '属性'], events.events.slice(0, 50).map(item => [item.eventName, item.userId || item.clientHash, item.page, item.occurredAt, JSON.stringify(item.properties)]));
    }
    document.getElementById('load').addEventListener('click', () => load().catch(error => alert(error.message || error)));
  </script>
</body>
</html>"""


def admin_analytics_response(handler, path, query):
    if not analytics_admin_authorized(handler.headers):
        json_response(handler, 401, {"error": "unauthorized"})
        return
    store = analytics_data_store()
    if store:
        if path == "/api/admin/analytics/summary":
            json_response(handler, 200, store.analytics_summary(query))
            return
        if path == "/api/admin/analytics/pages":
            json_response(handler, 200, store.analytics_pages(query))
            return
        if path == "/api/admin/analytics/features":
            json_response(handler, 200, store.analytics_features(query))
            return
        if path == "/api/admin/analytics/simulator" and hasattr(store, "analytics_simulator"):
            json_response(handler, 200, store.analytics_simulator(query))
            return
        if path == "/api/admin/analytics/events":
            json_response(handler, 200, store.analytics_events(query))
            return
        if path == "/api/admin/analytics/users":
            json_response(handler, 200, store.analytics_users(query))
            return
    init_db()
    with db_connection() as conn:
        if path == "/api/admin/analytics/summary":
            json_response(handler, 200, analytics_summary(conn, query))
            return
        if path == "/api/admin/analytics/pages":
            json_response(handler, 200, analytics_pages(conn, query))
            return
        if path == "/api/admin/analytics/features":
            json_response(handler, 200, analytics_features(conn, query))
            return
        if path == "/api/admin/analytics/simulator":
            json_response(handler, 200, analytics_simulator(conn, query))
            return
        if path == "/api/admin/analytics/events":
            json_response(handler, 200, analytics_events(conn, query))
            return
        if path == "/api/admin/analytics/users":
            json_response(handler, 200, analytics_users(conn, query))
            return
    json_response(handler, 404, {"error": "not_found"})


ADMIN_GATE_DIAGNOSES = {
    "system_gap_suspected",
    "evidence_missing",
    "rule_too_strict",
    "parser_or_mapping_bug",
    "stale_or_not_resynced",
    "source_conflict_needs_policy",
}
ADMIN_GATE_GAP_TYPES = {
    "system_gap_suspected",
    "evidence_missing",
    "rule_too_strict",
    "parser_or_mapping_bug",
    "stale_or_not_resynced",
    "source_conflict_needs_policy",
    "source_ref_missing",
    "serializer_blocked",
    "stat_weight_gate",
    "class_spec_mapping",
}
ADMIN_GATE_PASS_STATUSES = {"verified", "synced", "ready", "complete", "published", "passed"}
ADMIN_GATE_QUEUE_STATUSES = {
    "partial",
    "stale",
    "blocked",
    "missing_credentials",
    "pending_official_audit",
    "source_reference",
}


def admin_expected_token():
    return (
        os.environ.get("WOW_ADMIN_TOKEN", "").strip()
        or os.environ.get("WOW_ANALYTICS_ADMIN_TOKEN", "").strip()
    )


def admin_bearer_authorized(headers):
    expected = admin_expected_token()
    if not expected:
        return False
    return secrets.compare_digest(bearer_token_from_headers(headers), expected)


def admin_authorized(headers):
    return admin_bearer_authorized(headers)


def sqlite_has_table(conn, table_name):
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return bool(row)
    except sqlite3.Error:
        return False


def sqlite_table_columns(conn, table_name):
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except sqlite3.Error:
        return set()


def admin_query_value(query, key, default=""):
    value = query.get(key, default) if isinstance(query, dict) else default
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value if value is not None else default).strip()


def admin_query_int(query, key, default, minimum=1, maximum=None):
    try:
        value = int(admin_query_value(query, key, str(default)) or default)
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(maximum, value) if maximum is not None else value


def admin_query_limit(query, default=50, maximum=200):
    return admin_query_int(query, "limit", default, maximum=maximum)


def admin_query_page(query):
    return admin_query_int(query, "page", 1)


def admin_query_page_size(query, default=20, maximum=200):
    raw_page_size = admin_query_value(query, "pageSize", "")
    if not raw_page_size:
        return admin_query_limit(query, default=default, maximum=maximum)
    return admin_query_int(query, "pageSize", default, maximum=maximum)


def admin_gate_status(*statuses, blockers=None):
    normalized = []
    for status in statuses:
        raw = str(status or "").strip().lower()
        if not raw:
            continue
        if raw in ADMIN_GATE_PASS_STATUSES:
            normalized.append("verified")
        else:
            normalized.append(normalize_data_health_status(raw))
    blocker_list = [item for item in (blockers or []) if str(item or "").strip()]
    if "missing_credentials" in normalized:
        return "missing_credentials"
    if "source_reference" in normalized:
        return "source_reference"
    if "blocked" in normalized or blocker_list:
        return "blocked"
    if "stale" in normalized:
        return "stale"
    if "pending_official_audit" in normalized:
        return "pending_official_audit"
    if normalized and all(status == "verified" for status in normalized):
        return "verified"
    return "partial" if normalized else "blocked"


def admin_gate_summarize_text(value, limit=180):
    text = redact_health_text(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return f"{text[:limit - 1]}…"
    return text


def admin_gate_blocker_detail(blocker):
    code = admin_gate_summarize_text(blocker, 220)
    normalized = code.lower()
    if normalized == "invalid_llm_translation" or "invalid_llm_translation" in normalized:
        return {
            "code": code,
            "title": "LLM 翻译未通过校验",
            "explanation": "上游原文已经采集到，但中文本地化、摘要或结构化结果没有通过系统校验。系统会阻止发布，避免把不完整、不忠实或结构异常的译文展示给前端。",
            "action": "先重跑新闻翻译审计；如果持续失败，检查 translator prompt、JSON 解析、忠实度校验和原文长度处理。",
        }
    if normalized == "duplicate_seed_source_translation" or "duplicate_seed_source_translation" in normalized:
        return {
            "code": code,
            "title": "已存在同源译文，阻止重复发布",
            "explanation": "发现队列里的文章与已有种子内容或已入库来源译文指向同一 canonical topic。系统阻止新增一条重复新闻，这通常不是内容质量问题。",
            "action": "如果已有文章正确，保持阻断即可；如果需要更新内容，应走更新已有文章或重新翻译同一 canonical topic，而不是新增发布。",
        }
    if "translation" in normalized:
        return {
            "code": code,
            "title": "翻译链路未通过",
            "explanation": "新闻进入了采集队列，但翻译、摘要或发布校验链路返回了阻断信号。",
            "action": "查看原始采集内容和翻译运行日志，修复后重跑新闻 refresh。",
        }
    return {
        "code": code,
        "title": "系统门禁阻断",
        "explanation": "该记录存在系统门禁 blocker，当前不能被前端消费。",
        "action": "查看原始数据、规则审计和证据链，修复对应采集、解析或规则问题后重跑审计。",
    }


def admin_gate_json_summary(value, fallback):
    return sanitize_health_value(safe_json_loads(value, fallback, "admin gate payload"))


def admin_gate_record(domain, target_type, target_id, title, *, status="", source_status="", source_name="", source_url="", checked_at="", blockers=None, facets=None, stages=None, raw_summary=None, evidence=None, publication=None, article_category=None, talent_category=None, talent_publication=None, talent_block_reason=None, gear_category=None, gear_visibility=None, gear_block_reason=None):
    blockers = [admin_gate_summarize_text(item, 220) for item in (blockers or []) if str(item or "").strip()]
    status_inputs = (status,) if domain == "talents" and target_type == "community_talent_template" else (source_status, status)
    effective_status = admin_gate_status(*status_inputs, blockers=blockers)
    source_status_value = normalize_data_health_status(source_status or status or effective_status)
    severity = admin_gate_severity(effective_status, domain, target_type)
    facets_value = facets if isinstance(facets, dict) else {}
    evidence_value = evidence if isinstance(evidence, dict) else {}
    if domain == "talents":
        talent_block_reason = talent_block_reason or admin_gate_talent_block_reason(effective_status, blockers, facets_value, evidence_value)
        talent_publication = talent_publication or admin_gate_talent_publication(target_type, effective_status, blockers, checked_at, talent_block_reason)
    if domain in {"gear", "gear_templates"}:
        gear_block_reason = gear_block_reason or admin_gate_gear_block_reason(effective_status, blockers, facets_value, evidence_value)
        gear_visibility = gear_visibility or admin_gate_gear_visibility(target_type, effective_status, blockers, checked_at, gear_block_reason)
    return {
        "id": f"{domain}:{target_type}:{target_id}",
        "domain": domain,
        "targetType": target_type,
        "targetId": str(target_id or ""),
        "title": admin_gate_summarize_text(title or target_id or target_type, 120),
        "status": effective_status,
        "statusLabel": admin_gate_status_label(effective_status),
        "sourceStatus": source_status_value,
        "sourceStatusLabel": admin_gate_status_label(source_status_value),
        "rawStatus": str(status or ""),
        "sourceName": admin_gate_summarize_text(source_name, 120),
        "sourceUrl": admin_gate_summarize_text(source_url, 260),
        "checkedAt": checked_at or "",
        "blockers": blockers,
        "blockerDetails": [admin_gate_blocker_detail(item) for item in blockers],
        "severity": severity,
        "severityLabel": admin_gate_severity_label(severity),
        "facets": facets_value,
        "stages": stages or admin_gate_default_stages(effective_status, blockers),
        "rawSummary": sanitize_health_value(raw_summary or {}),
        "evidence": sanitize_health_value(evidence or {}),
        "publication": sanitize_health_value(publication or {}),
        "articleCategory": sanitize_health_value(article_category or {}),
        "talentCategory": sanitize_health_value(talent_category or {}),
        "talentPublication": sanitize_health_value(talent_publication or {}),
        "talentBlockReason": sanitize_health_value(talent_block_reason or {}),
        "gearCategory": sanitize_health_value(gear_category or {}),
        "gearVisibility": sanitize_health_value(gear_visibility or {}),
        "gearBlockReason": sanitize_health_value(gear_block_reason or {}),
    }


def admin_gate_talent_block_reason(status, blockers=None, facets=None, evidence=None):
    status_value = str(status or "").strip() or "blocked"
    blocker_list = [admin_gate_summarize_text(item, 220) for item in (blockers or []) if str(item or "").strip()]
    if status_value == "verified" and not blocker_list:
        return {
            "state": "clear",
            "stateLabel": "无阻断",
            "reason": "无阻断",
            "status": status_value,
            "statusLabel": admin_gate_status_label(status_value),
        }
    if status_value in {"blocked", "missing_credentials"} or blocker_list:
        state = "blocked"
        state_label = "已阻断"
    else:
        state = "not_passed"
        state_label = "未通过"
    reason = blocker_list[0] if blocker_list else admin_gate_talent_context_reason(status_value, facets, evidence)
    return {
        "state": state,
        "stateLabel": state_label,
        "reason": reason,
        "status": status_value,
        "statusLabel": admin_gate_status_label(status_value),
    }


def admin_gate_talent_context_reason(status, facets=None, evidence=None):
    facets = facets if isinstance(facets, dict) else {}
    evidence = evidence if isinstance(evidence, dict) else {}
    source_key = str(facets.get("sourceKey") or "").strip()
    sample_count = admin_gate_int_value(facets.get("sampleCount"), 0)
    max_key_level = admin_gate_int_value(facets.get("maxKeyLevel"), 0)
    refs = evidence.get("sourceRefs") if isinstance(evidence.get("sourceRefs"), list) else []
    ref = refs[0] if refs and isinstance(refs[0], dict) else {}
    ref_source_key = str(ref.get("sourceKey") or "").strip()
    if (source_key == "websim_baseline" or ref_source_key == "websim_baseline") and sample_count <= 0 and max_key_level <= 0:
        return "WebSim 基线模板没有真实社区样本（sampleCount=0 / maxKeyLevel=0），系统不会把基线模板发布到小程序端。"
    if source_key:
        return f"{source_key} 来源状态为 {admin_gate_status_text(status)}，未达到 verified 发布门禁。"
    return admin_gate_status_text(status)


def admin_gate_status_text(status):
    status_value = str(status or "").strip()
    label = admin_gate_status_label(status_value)
    return f"{status_value}（{label}）" if label and label != status_value else status_value


def admin_gate_talent_publication(target_type, status, blockers=None, checked_at="", block_reason=None):
    status_value = str(status or "").strip() or "blocked"
    blocker_list = [admin_gate_summarize_text(item, 220) for item in (blockers or []) if str(item or "").strip()]
    target_value = str(target_type or "").strip()
    surface = "天赋导入列表" if target_value == "community_talent_template" else "天赋树基础数据"
    is_visible = status_value == "verified"
    if is_visible:
        reason = f"状态 {status_value}，已进入小程序{surface}"
    else:
        block_reason = block_reason if isinstance(block_reason, dict) else {}
        reason = blocker_list[0] if blocker_list else (block_reason.get("reason") or f"状态 {admin_gate_status_text(status_value)}，未进入小程序{surface}")
    return {
        "state": "visible" if is_visible else "hidden",
        "stateLabel": "已可见" if is_visible else "不可见",
        "visibleToMiniProgram": is_visible,
        "surface": surface,
        "reason": reason,
        "visibleAt": (checked_at or "") if is_visible else "",
    }


def admin_gate_gear_block_reason(status, blockers=None, facets=None, evidence=None):
    status_value = str(status or "").strip() or "blocked"
    blocker_list = [admin_gate_summarize_text(item, 220) for item in (blockers or []) if str(item or "").strip()]
    if status_value == "verified" and not blocker_list:
        return {
            "state": "clear",
            "stateLabel": "无阻断",
            "reason": "无阻断",
            "status": status_value,
            "statusLabel": admin_gate_status_label(status_value),
        }
    state = "blocked" if status_value in {"blocked", "missing_credentials"} or blocker_list else "not_passed"
    return {
        "state": state,
        "stateLabel": "已阻断" if state == "blocked" else "未通过",
        "reason": blocker_list[0] if blocker_list else admin_gate_status_text(status_value),
        "status": status_value,
        "statusLabel": admin_gate_status_label(status_value),
    }


def admin_gate_gear_visibility(target_type, status, blockers=None, checked_at="", block_reason=None):
    status_value = str(status or "").strip() or "blocked"
    target_value = str(target_type or "").strip()
    surface = "装备库" if target_value == "gear_variant" else "装备模板"
    is_visible = status_value == "verified"
    block_reason = block_reason if isinstance(block_reason, dict) else {}
    blocker_list = [admin_gate_summarize_text(item, 220) for item in (blockers or []) if str(item or "").strip()]
    reason = (
        f"状态 {status_value}，已进入小程序{surface}"
        if is_visible
        else (blocker_list[0] if blocker_list else (block_reason.get("reason") or f"状态 {admin_gate_status_text(status_value)}，未进入小程序{surface}"))
    )
    return {
        "state": "visible" if is_visible else "hidden",
        "stateLabel": "已可见" if is_visible else "不可见",
        "visibleToMiniProgram": is_visible,
        "surface": surface,
        "reason": reason,
        "visibleAt": (checked_at or "") if is_visible else "",
    }


def admin_gate_gear_class_keys_from_payload(payload, slot=""):
    payload_value = payload if isinstance(payload, dict) else {}
    class_keys = []
    for key in payload_playable_class_keys(payload_value):
        if key and key not in class_keys:
            class_keys.append(key)
    if class_keys:
        return class_keys

    slot_value = str(slot or "").strip()
    if slot_value in ARMOR_SLOTS:
        item_class = payload_value.get("item_class") if isinstance(payload_value.get("item_class"), dict) else {}
        item_subclass = payload_value.get("item_subclass") if isinstance(payload_value.get("item_subclass"), dict) else {}
        armor_type = normalized_armor_subclass(item_subclass)
        if payload_item_class_is_armor(item_class) and armor_type and armor_type not in {"Miscellaneous", "Cosmetic"}:
            return [
                key
                for key, expected_armor in CLASS_ARMOR_TYPES.items()
                if str(expected_armor or "").lower() == str(armor_type or "").lower()
            ]

    if slot_value in WEAPON_SLOTS:
        weapon_type = item_type_metadata_from_payload(payload_value).get("weaponType") or ""
        if weapon_type:
            return [
                key
                for key in WOW_CLASS_LABELS
                if weapon_type_allowed_for_slot(key, "", slot_value, weapon_type)
            ]

    return []


def admin_gate_gear_class_label_payload(class_keys):
    keys = [str(item or "").strip() for item in (class_keys or []) if str(item or "").strip()]
    labels = [admin_gate_talent_class_label(key) for key in keys]
    return {
        "classKeys": keys,
        "classLabels": labels,
        "classLabel": " / ".join(labels) if labels else "未标注职业",
    }


GEAR_ARMOR_TYPE_LABELS = {
    "Cloth": "布甲",
    "Leather": "皮甲",
    "Mail": "锁甲",
    "Plate": "板甲",
    "Shield": "盾牌",
    "Cosmetic": "外观",
    "Miscellaneous": "其他护甲",
}

GEAR_WEAPON_TYPE_LABELS = {
    "Dagger": "匕首",
    "Fist Weapon": "拳套",
    "One-Handed Axe": "单手斧",
    "One-Handed Mace": "单手锤",
    "One-Handed Sword": "单手剑",
    "Warglaive": "战刃",
    "Wand": "魔杖",
    "Two-Handed Axe": "双手斧",
    "Two-Handed Mace": "双手锤",
    "Two-Handed Sword": "双手剑",
    "Polearm": "长柄武器",
    "Staff": "法杖",
    "Bow": "弓",
    "Crossbow": "弩",
    "Gun": "枪械",
    "Held In Off-hand": "副手物品",
    "Shield": "盾牌",
}

GEAR_JEWELRY_SLOT_LABELS = {
    "neck": "项链",
    "finger": "戒指",
    "finger1": "戒指",
    "finger2": "戒指",
    "trinket": "饰品",
    "trinket1": "饰品",
    "trinket2": "饰品",
}

GEAR_MISC_SLOT_TYPE_LABELS = {
    "back": "披风",
    "shirt": "衬衣",
    "tabard": "战袍",
}


def admin_gate_nested_dict(payload, keys):
    source = payload if isinstance(payload, dict) else {}
    for key in keys:
        value = source.get(key)
        if isinstance(value, dict):
            return value
    return {}


def admin_gate_gear_item_type_metadata_payload(payload, slot=""):
    source = payload if isinstance(payload, dict) else {}
    normalized = dict(source)
    item_class = admin_gate_nested_dict(source, ("item_class", "itemClass", "item_class_payload", "class"))
    item_subclass = admin_gate_nested_dict(source, ("item_subclass", "itemSubclass", "itemSubClass", "subclass"))
    inventory_type = admin_gate_nested_dict(source, ("inventory_type", "inventoryType", "inventory"))
    if item_class and not isinstance(normalized.get("item_class"), dict):
        normalized["item_class"] = item_class
    if item_subclass and not isinstance(normalized.get("item_subclass"), dict):
        normalized["item_subclass"] = item_subclass
    if inventory_type and not isinstance(normalized.get("inventory_type"), dict):
        normalized["inventory_type"] = inventory_type
    if slot and not normalized.get("slot"):
        normalized["slot"] = slot
    return normalized


def admin_gate_gear_item_type_key(value):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", str(value or "").strip().lower()).strip("_") or "unknown"


def admin_gate_gear_item_type_payload(payload=None, slot=""):
    slot_value = str(slot or "").strip()
    if slot_value in GEAR_JEWELRY_SLOT_LABELS:
        label = GEAR_JEWELRY_SLOT_LABELS[slot_value]
        return {
            "itemTypeKey": slot_value,
            "itemTypeLabel": label,
            "itemTypeGroupKey": "jewelry",
            "itemTypeGroupLabel": "首饰",
            "itemTypeRaw": slot_value,
            "itemTypeAliases": [label, "首饰", slot_value],
        }

    metadata_payload = admin_gate_gear_item_type_metadata_payload(payload, slot_value)
    type_metadata = item_type_metadata_from_payload(metadata_payload)
    weapon_type = str(type_metadata.get("weaponType") or "").strip()
    if weapon_type:
        label = GEAR_WEAPON_TYPE_LABELS.get(weapon_type) or weapon_type
        return {
            "itemTypeKey": admin_gate_gear_item_type_key(weapon_type),
            "itemTypeLabel": admin_gate_summarize_text(label, 80),
            "itemTypeGroupKey": "weapon",
            "itemTypeGroupLabel": "武器类型",
            "itemTypeRaw": admin_gate_summarize_text(weapon_type, 80),
            "itemTypeAliases": [label, "武器类型", weapon_type, admin_gate_gear_item_type_key(weapon_type)],
        }

    armor_type = str(type_metadata.get("armorType") or "").strip()
    if armor_type:
        label = GEAR_ARMOR_TYPE_LABELS.get(armor_type) or armor_type
        return {
            "itemTypeKey": admin_gate_gear_item_type_key(armor_type),
            "itemTypeLabel": admin_gate_summarize_text(label, 80),
            "itemTypeGroupKey": "armor",
            "itemTypeGroupLabel": "护甲类型",
            "itemTypeRaw": admin_gate_summarize_text(armor_type, 80),
            "itemTypeAliases": [label, "护甲类型", armor_type, admin_gate_gear_item_type_key(armor_type)],
        }

    if slot_value in GEAR_MISC_SLOT_TYPE_LABELS:
        label = GEAR_MISC_SLOT_TYPE_LABELS[slot_value]
        return {
            "itemTypeKey": slot_value,
            "itemTypeLabel": label,
            "itemTypeGroupKey": "misc",
            "itemTypeGroupLabel": "其他",
            "itemTypeRaw": slot_value,
            "itemTypeAliases": [label, "其他", slot_value],
        }

    if slot_value in ARMOR_SLOTS:
        return {
            "itemTypeKey": "armor",
            "itemTypeLabel": "护甲",
            "itemTypeGroupKey": "armor",
            "itemTypeGroupLabel": "护甲类型",
            "itemTypeRaw": slot_value,
            "itemTypeAliases": ["护甲", "护甲类型", slot_value],
        }
    if slot_value in WEAPON_SLOTS:
        return {
            "itemTypeKey": "weapon",
            "itemTypeLabel": "武器",
            "itemTypeGroupKey": "weapon",
            "itemTypeGroupLabel": "武器类型",
            "itemTypeRaw": slot_value,
            "itemTypeAliases": ["武器", "武器类型", slot_value],
        }
    return {
        "itemTypeKey": "unknown",
        "itemTypeLabel": "未标注分类",
        "itemTypeGroupKey": "unknown",
        "itemTypeGroupLabel": "未标注分类",
        "itemTypeRaw": slot_value,
        "itemTypeAliases": ["未标注分类", slot_value],
    }


def admin_gate_news_publication(status, *, published_at="", captured_at="", unpublished_reason=""):
    raw_status = str(status or "").strip().lower()
    is_published = raw_status in {"published", "ready"}
    return {
        "state": "published" if is_published else "unpublished",
        "stateLabel": "已发布" if is_published else "未发布",
        "publishedAt": str(published_at or "") if is_published else "",
        "capturedAt": str(captured_at or ""),
        "unpublishedReason": "" if is_published else admin_gate_summarize_text(unpublished_reason or raw_status or "not_published", 220),
    }


def admin_gate_news_article_category(channel="", category="", tags=None):
    channel_value = str(channel or "").strip()
    category_value = str(category or "").strip()
    tags_value = [str(item or "").strip() for item in (tags or []) if str(item or "").strip()]
    known_channels = {item["title"] for item in CHANNELS}
    if channel_value in known_channels:
        label = channel_value
    elif category_value in known_channels:
        label = category_value
    elif "ptr" in tags_value or category_value == "测试服":
        label = "测试服前瞻"
    elif "class-change" in tags_value:
        label = "职业强度变化"
    elif channel_value:
        label = channel_value
    elif category_value:
        label = "正式服动态" if category_value == "正式服" else category_value
    else:
        label = "未分类"
    return {
        "label": admin_gate_summarize_text(label, 80),
        "channel": admin_gate_summarize_text(channel_value, 80),
        "category": admin_gate_summarize_text(category_value, 80),
        "tags": tags_value[:8],
    }


WOW_CLASS_LABELS = {
    "deathknight": "死亡骑士",
    "demonhunter": "恶魔猎手",
    "druid": "德鲁伊",
    "evoker": "唤魔师",
    "hunter": "猎人",
    "mage": "法师",
    "monk": "武僧",
    "paladin": "圣骑士",
    "priest": "牧师",
    "rogue": "潜行者",
    "shaman": "萨满祭司",
    "warlock": "术士",
    "warrior": "战士",
}


def admin_gate_talent_class_label(class_key):
    class_value = str(class_key or "").strip()
    normalized = class_value.lower().replace("-", "").replace("_", "")
    return WOW_CLASS_LABELS.get(normalized) or class_value or "未知职业"


def admin_gate_talent_record_category(class_key="", spec_key="", hero_key="", source_key="", target_type=""):
    class_value = str(class_key or "").strip()
    spec_value = str(spec_key or "").strip()
    hero_value = str(hero_key or "").strip()
    source_value = str(source_key or "").strip()
    is_community = str(target_type or "").strip() == "community_talent_template" or bool(source_value)
    class_label = admin_gate_talent_class_label(class_value)
    return {
        "label": admin_gate_summarize_text(class_label, 80),
        "classKey": admin_gate_summarize_text(class_value, 80),
        "classLabel": admin_gate_summarize_text(class_label, 80),
        "specKey": admin_gate_summarize_text(spec_value, 80),
        "heroKey": admin_gate_summarize_text(hero_value, 80),
        "sourceKind": "community" if is_community else "catalog",
        "sourceLabel": "社区来源" if is_community else "基础目录",
        "sourceKey": admin_gate_summarize_text(source_value, 80),
    }


GEAR_SOURCE_LABELS = {
    "catalog": "基础目录",
    "crafted": "制造业",
    "dungeon": "地下城",
    "raid": "团本",
    "observed_profile": "社区样本",
    "verifiedLoot": "已验证掉落",
    "verified_loot": "已验证掉落",
    "default_template": "默认模板",
    "websim_baseline": "WebSim 基线",
}

GEAR_SOURCE_INSTANCE_ALIASES = {
    "Magisters' Terrace": ["Magisters Terrace", "魔导师平台"],
    "Maisara Caverns": ["迈萨拉洞窟"],
    "Nexus-Point Xenas": ["节点希纳斯"],
    "Windrunner Spire": ["风行者之塔"],
    "Algeth'ar Academy": ["艾杰斯亚学院"],
    "Pit of Saron": ["萨隆矿坑"],
    "Seat of the Triumvirate": ["The Seat of the Triumvirate", "执政团之座"],
    "Skyreach": ["通天峰"],
    "The Voidspire": ["虚影尖塔"],
    "The Dreamrift": ["梦境裂隙"],
    "March on Quel'Danas": ["进军奎尔丹纳斯"],
    "Sporefall": ["孢陨幽境"],
}


def admin_gate_int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def admin_gate_gear_source_label(source_type):
    value = str(source_type or "").strip()
    return GEAR_SOURCE_LABELS.get(value) or GEAR_SOURCE_LABELS.get(value.lower()) or value or "未知来源"


def admin_gate_gear_source_instance_label(source_type="", source_detail_label="", source_instance_label=""):
    source_type_value = str(source_type or "").strip().lower()
    if source_type_value not in {"dungeon", "raid"}:
        return ""
    explicit = str(source_instance_label or "").strip()
    if explicit:
        return explicit
    detail = str(source_detail_label or "").strip()
    if not detail:
        return ""
    for separator in (" - ", " – ", " — "):
        if separator in detail:
            tail = detail.rsplit(separator, 1)[-1].strip()
            if tail:
                return tail
    return detail


def admin_gate_gear_source_instance_terms(instance_label):
    label = str(instance_label or "").strip()
    if not label:
        return []
    normalized = label.lower().replace("’", "'")
    terms = [label]
    for canonical, aliases in GEAR_SOURCE_INSTANCE_ALIASES.items():
        candidates = [canonical, *(aliases or [])]
        normalized_candidates = [str(item or "").lower().replace("’", "'") for item in candidates]
        if normalized in normalized_candidates:
            for item in candidates:
                if item and item not in terms:
                    terms.append(item)
            break
    return terms


ADMIN_GATE_GEAR_VARIANT_STATUS_RANK = {
    "verified": 4,
    "complete": 4,
    "synced": 3,
    "partial": 2,
    "source_reference": 1,
    "blocked": 0,
}


def admin_gate_unique_text_list(values):
    result = []
    seen = set()
    for value in values or []:
        if isinstance(value, (list, tuple, set)):
            nested = admin_gate_unique_text_list(value)
            for item in nested:
                key = str(item or "").strip().lower()
                if key and key not in seen:
                    result.append(item)
                    seen.add(key)
            continue
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def admin_gate_gear_variant_blockers(item):
    blockers = item.get("blockers") if isinstance(item, dict) and isinstance(item.get("blockers"), list) else []
    return [str(blocker or "").strip() for blocker in blockers if str(blocker or "").strip()]


def admin_gate_gear_variant_status_rank(item):
    status = str((item or {}).get("status") or "").strip().lower()
    return ADMIN_GATE_GEAR_VARIANT_STATUS_RANK.get(status, 0)


def admin_gate_gear_variant_simc_options(item):
    if not isinstance(item, dict):
        return {}
    candidates = []
    if isinstance(item.get("simcOptions"), dict):
        candidates.append(item.get("simcOptions"))
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    for key in ("simcOptions", "simc_options", "simc_options_json"):
        if isinstance(payload.get(key), dict):
            candidates.append(payload.get(key))
    merged = {}
    for candidate in candidates:
        for key, value in (candidate or {}).items():
            if value not in (None, "", [], {}):
                merged[str(key)] = value
    return merged


def admin_gate_gear_variant_display_ready(item):
    if not isinstance(item, dict):
        return False
    blockers = admin_gate_gear_variant_blockers(item)
    return admin_gate_status(item.get("status"), blockers=blockers) == "verified"


def admin_gate_gear_variant_sort_key(item):
    simc_options = admin_gate_gear_variant_simc_options(item)
    return (
        1 if admin_gate_gear_variant_display_ready(item) else 0,
        admin_gate_gear_variant_status_rank(item),
        1 if simc_options else 0,
        admin_gate_int_value((item or {}).get("itemLevel"), 0),
        str((item or {}).get("updatedAt") or ""),
        str((item or {}).get("id") or ""),
    )


def admin_gate_gear_variant_internal_label(label="", difficulty_key=""):
    label_value = str(label or "").strip().lower()
    difficulty_value = str(difficulty_key or "").strip().lower()
    return difficulty_value == "observed_profile" or label_value.startswith("observed")


def admin_gate_gear_variant_display_label(item, item_level=0):
    if not isinstance(item, dict):
        return ""
    label = str(item.get("label") or item.get("difficultyKey") or "").strip()
    difficulty_key = str(item.get("difficultyKey") or "").strip()
    if admin_gate_gear_variant_internal_label(label, difficulty_key):
        return ""
    if item_level > 0:
        label = re.sub(rf"\s*(?:ilvl\s*)?{re.escape(str(item_level))}\s*$", "", label, flags=re.IGNORECASE).strip()
    return label


def admin_gate_gear_variant_display_group_key(item, has_item_level_variant=False):
    item_level = admin_gate_int_value((item or {}).get("itemLevel"), 0)
    if has_item_level_variant and item_level > 0:
        return ("item-level", item_level)
    label = admin_gate_gear_variant_display_label(item, item_level)
    return (
        "variant",
        label.lower(),
        str((item or {}).get("difficultyKey") or "").strip().lower(),
        admin_gate_status((item or {}).get("status"), blockers=admin_gate_gear_variant_blockers(item or {})),
        item_level,
    )


def admin_gate_gear_variant_display_representative_key(item):
    item_level = admin_gate_int_value((item or {}).get("itemLevel"), 0)
    label = admin_gate_gear_variant_display_label(item, item_level)
    simc_options = admin_gate_gear_variant_simc_options(item)
    return (
        1 if admin_gate_gear_variant_display_ready(item) else 0,
        admin_gate_gear_variant_status_rank(item),
        1 if label else 0,
        1 if simc_options else 0,
        str((item or {}).get("updatedAt") or ""),
        str((item or {}).get("id") or ""),
    )


def admin_gate_gear_variant_display_order_key(item):
    item_level = admin_gate_int_value((item or {}).get("itemLevel"), 0)
    label = admin_gate_gear_variant_display_label(item, item_level)
    return (
        1 if admin_gate_gear_variant_display_ready(item) else 0,
        admin_gate_gear_variant_status_rank(item),
        item_level,
        1 if label else 0,
        str((item or {}).get("updatedAt") or ""),
        str((item or {}).get("id") or ""),
    )


def admin_gate_gear_variant_display_rows(variant_items):
    ranked = sorted(
        [item for item in (variant_items or []) if isinstance(item, dict)],
        key=admin_gate_gear_variant_sort_key,
        reverse=True,
    )
    if not ranked:
        return []
    has_item_level_variant = any(admin_gate_int_value(item.get("itemLevel"), 0) > 0 for item in ranked)
    display_groups = {}
    for item in ranked:
        item_level = admin_gate_int_value(item.get("itemLevel"), 0)
        if has_item_level_variant and item_level <= 0:
            continue
        key = admin_gate_gear_variant_display_group_key(item, has_item_level_variant)
        current = display_groups.get(key)
        if current is None or admin_gate_gear_variant_display_representative_key(item) > admin_gate_gear_variant_display_representative_key(current):
            display_groups[key] = item
    rows = []
    for item in sorted(display_groups.values(), key=admin_gate_gear_variant_display_order_key, reverse=True):
        item_level = admin_gate_int_value(item.get("itemLevel"), 0)
        blockers = admin_gate_gear_variant_blockers(item)
        status = admin_gate_status(item.get("status"), blockers=blockers)
        label = admin_gate_gear_variant_display_label(item, item_level)
        rows.append({
            "id": admin_gate_summarize_text(str(item.get("id") or "").strip(), 100),
            "label": admin_gate_summarize_text(label, 80),
            "difficultyKey": admin_gate_summarize_text(str(item.get("difficultyKey") or "").strip(), 80),
            "itemLevel": item_level,
            "status": status,
            "statusLabel": admin_gate_status_label(status),
        })
    return rows[:12]


def admin_gate_gear_variant_group_key(item):
    if not isinstance(item, dict):
        return ("unknown", "")
    item_id = str(item.get("itemId") or "").strip()
    slot = str(item.get("slot") or "").strip()
    if item_id and slot:
        return ("item-slot", item_id, slot)
    if item_id:
        return ("item", item_id)
    return ("variant", str(item.get("id") or ""))


def admin_gate_gear_variant_source_instance_terms(item):
    if not isinstance(item, dict):
        return []
    source_label = item.get("sourceLabel") or ""
    instance_label = admin_gate_gear_source_instance_label(
        item.get("sourceType") or "",
        source_label,
        item.get("sourceInstanceLabel") or "",
    )
    return admin_gate_unique_text_list([
        item.get("sourceInstanceId") or "",
        instance_label,
        admin_gate_gear_source_instance_terms(instance_label),
        source_label,
    ])


def admin_gate_primary_gear_variants(variant_items):
    grouped = {}
    for item in variant_items or []:
        if not isinstance(item, dict):
            continue
        grouped.setdefault(admin_gate_gear_variant_group_key(item), []).append(item)
    primary_items = []
    for group_items in grouped.values():
        ranked = sorted(group_items, key=admin_gate_gear_variant_sort_key, reverse=True)
        if not ranked:
            continue
        primary = dict(ranked[0])
        primary["adminGateVariantCount"] = len(group_items)
        primary["adminGateVerifiedVariantCount"] = len([item for item in group_items if admin_gate_gear_variant_display_ready(item)])
        primary["adminGateBlockedVariantCount"] = len(group_items) - primary["adminGateVerifiedVariantCount"]
        primary["adminGateVariantIds"] = [str(item.get("id") or "") for item in group_items if str(item.get("id") or "").strip()]
        primary["adminGateVariants"] = admin_gate_gear_variant_display_rows(group_items)
        primary["adminGateSourceInstanceTerms"] = admin_gate_unique_text_list(
            term
            for item in group_items
            for term in admin_gate_gear_variant_source_instance_terms(item)
        )
        primary["adminGateLatestUpdatedAt"] = max([str(item.get("updatedAt") or "") for item in group_items] + [""])
        primary_items.append(primary)
    return sorted(primary_items, key=lambda item: str(item.get("adminGateLatestUpdatedAt") or item.get("updatedAt") or ""), reverse=True)


def admin_gate_gear_record_category(
    target_type="",
    *,
    class_key="",
    spec_key="",
    source_key="",
    slot="",
    label="",
    source_type="",
    source_detail_label="",
    source_instance_id="",
    source_instance_label="",
    difficulty_key="",
    item_level=0,
    class_keys=None,
    item_type_payload=None,
    ready_slot_count=None,
    missing_slots=None,
):
    target_value = str(target_type or "").strip()
    source_value = str(source_key or source_type or "").strip()
    if target_value == "community_gear_template":
        class_value = str(class_key or "").strip()
        spec_value = str(spec_key or "").strip()
        class_label = admin_gate_talent_class_label(class_value)
        missing_value = missing_slots if isinstance(missing_slots, list) else []
        is_baseline_source = source_value in {"default_template", "simc_preset"}
        source_kind = "baseline" if is_baseline_source else "community"
        source_label = "基线模板" if is_baseline_source else "社区模板"
        return {
            "label": admin_gate_summarize_text(class_label, 80),
            "classKey": admin_gate_summarize_text(class_value, 80),
            "classLabel": admin_gate_summarize_text(class_label, 80),
            "specKey": admin_gate_summarize_text(spec_value, 80),
            "sourceKind": source_kind,
            "sourceLabel": source_label,
            "sourceKey": admin_gate_summarize_text(source_value, 80),
            "readySlotCount": admin_gate_int_value(ready_slot_count, 0),
            "missingSlotCount": len(missing_value),
        }
    slot_value = str(slot or "").strip()
    slot_label = GEAR_SLOT_LABELS.get(slot_value) or slot_value or "未知槽位"
    class_payload = admin_gate_gear_class_label_payload(class_keys or [])
    item_type_payload_value = admin_gate_gear_item_type_payload(item_type_payload, slot_value)
    source_detail_value = str(source_detail_label or "").strip()
    source_instance_value = admin_gate_gear_source_instance_label(source_type, source_detail_value, source_instance_label)
    return {
        "label": admin_gate_summarize_text(slot_label, 80),
        "slot": admin_gate_summarize_text(slot_value, 80),
        "slotLabel": admin_gate_summarize_text(slot_label, 80),
        "classKeys": class_payload["classKeys"],
        "classLabels": class_payload["classLabels"],
        "classLabel": admin_gate_summarize_text(class_payload["classLabel"], 120),
        "itemTypeKey": admin_gate_summarize_text(item_type_payload_value["itemTypeKey"], 80),
        "itemTypeLabel": admin_gate_summarize_text(item_type_payload_value["itemTypeLabel"], 80),
        "itemTypeGroupKey": admin_gate_summarize_text(item_type_payload_value["itemTypeGroupKey"], 80),
        "itemTypeGroupLabel": admin_gate_summarize_text(item_type_payload_value["itemTypeGroupLabel"], 80),
        "itemTypeRaw": admin_gate_summarize_text(item_type_payload_value["itemTypeRaw"], 80),
        "itemTypeAliases": item_type_payload_value["itemTypeAliases"],
        "sourceType": admin_gate_summarize_text(str(source_type or "").strip(), 80),
        "sourceLabel": admin_gate_summarize_text(admin_gate_gear_source_label(source_type), 80),
        "sourceDetailLabel": admin_gate_summarize_text(source_detail_value, 140),
        "sourceInstanceId": admin_gate_summarize_text(str(source_instance_id or "").strip(), 80),
        "sourceInstanceLabel": admin_gate_summarize_text(source_instance_value, 100),
        "sourceInstanceAliases": admin_gate_gear_source_instance_terms(source_instance_value),
        "difficultyKey": admin_gate_summarize_text(str(difficulty_key or "").strip(), 80),
        "variantLabel": admin_gate_summarize_text(str(label or "").strip(), 80),
        "itemLevel": admin_gate_int_value(item_level, 0),
    }


def admin_gate_default_stages(status, blockers):
    upstream = "passed" if status not in {"blocked", "missing_credentials"} else "partial"
    audit = "blocked" if status in {"blocked", "missing_credentials"} else ("partial" if status != "verified" else "passed")
    stages = [
        {"key": "upstream", "title": "上游原始数据摘要", "status": upstream},
        {"key": "rules", "title": "规则审计", "status": audit},
        {"key": "evidence", "title": "证据链", "status": audit, "blockers": blockers[:3]},
        {"key": "storage", "title": "入库状态", "status": "passed"},
        {"key": "consumption", "title": "前端/SimC 消费状态", "status": "passed" if status == "verified" else "blocked"},
    ]
    for stage in stages:
        stage["statusLabel"] = admin_gate_status_label(stage.get("status"))
    return stages


def admin_gate_record_domain_for_target(domain, target_type):
    domain_value = str(domain or "").strip()
    target_value = str(target_type or "").strip()
    if target_value == "community_gear_template" and domain_value in {"gear", "gear_templates"}:
        return "gear_templates"
    return domain_value


def admin_gate_severity(status, domain, target_type):
    if status == "verified":
        return "ok"
    if domain in {"gear", "gear_templates"} and target_type in {"community_gear_template", "gear_variant"}:
        return "blocks_simc_or_strong_claim"
    if domain == "talents" and "template" in target_type:
        return "blocks_frontend_template"
    if domain == "news":
        return "blocks_frontend_publish"
    return "blocks_diagnostic_or_record"


def admin_gate_record_passed(record):
    if not isinstance(record, dict):
        return False
    if record.get("blockers"):
        return False
    return record.get("status") == "verified" and record.get("sourceStatus") in {"verified"}


def admin_gate_record_fingerprint(record):
    material = {
        "status": record.get("status") if isinstance(record, dict) else "",
        "sourceStatus": record.get("sourceStatus") if isinstance(record, dict) else "",
        "blockers": record.get("blockers") if isinstance(record, dict) else [],
    }
    raw = json.dumps(material, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def collect_admin_news_records(conn):
    records = []
    if sqlite_has_table(conn, "news_discovery_queue"):
        rows = conn.execute(
            """
            SELECT id, canonical_topic_id, source_id, source_name, source_tier,
                   source_url, original_title, published_at, status, attempts,
                   last_error, payload_json, discovered_at, updated_at, processed_at
            FROM news_discovery_queue
            ORDER BY updated_at DESC, discovered_at DESC
            LIMIT 500
            """
        ).fetchall()
        for row in rows:
            payload = admin_gate_json_summary(row[11], {})
            blockers = [row[10]] if row[10] else []
            records.append(admin_gate_record(
                "news",
                "news_discovery_queue",
                row[0],
                row[6],
                status=row[8],
                source_status="verified" if row[8] == "published" else row[8],
                source_name=row[3],
                source_url=row[5],
                checked_at=row[13] or row[12] or "",
                blockers=blockers,
                facets={
                    "sourceKey": row[2],
                    "sourceTier": row[4],
                    "canonicalTopicId": row[1],
                    "attempts": row[9],
                },
                raw_summary={
                    "originalTitle": row[6],
                    "publishedAt": row[7],
                    "payloadKeys": sorted(payload.keys())[:12] if isinstance(payload, dict) else [],
                },
                evidence={
                    "contentGate": "discovery_queue",
                    "processedAt": row[14] or "",
                },
                publication=admin_gate_news_publication(
                    row[8],
                    published_at=row[7],
                    captured_at=row[12],
                    unpublished_reason=row[10],
                ),
                article_category=admin_gate_news_article_category(
                    payload.get("channel") if isinstance(payload, dict) else "",
                    payload.get("category") if isinstance(payload, dict) else "",
                    payload.get("tags") if isinstance(payload, dict) else [],
                ),
            ))
    if sqlite_has_table(conn, "news_articles"):
        rows = conn.execute(
            """
            SELECT id, title, source_name, source_url, published_at, updated_at,
                   content_status, translation_status, license_status,
                   verification_status, translation_fidelity, blocked_reason,
                   channel, category, tags_json
            FROM news_articles
            ORDER BY updated_at DESC
            LIMIT 500
            """
        ).fetchall()
        for row in rows:
            status = "published" if row[6] == "ready" else row[6]
            blockers = [row[11]] if row[11] else []
            records.append(admin_gate_record(
                "news",
                "news_article",
                row[0],
                row[1],
                status=status,
                source_status="verified" if row[6] == "ready" else row[6],
                source_name=row[2],
                source_url=row[3],
                checked_at=row[5],
                blockers=blockers,
                facets={
                    "contentStatus": row[6],
                    "translationStatus": row[7],
                    "licenseStatus": row[8],
                    "verificationStatus": row[9],
                    "translationFidelity": row[10],
                    "publishedAt": row[4],
                },
                raw_summary={"title": row[1], "publishedAt": row[4]},
                evidence={"contentGate": "public_article"},
                publication=admin_gate_news_publication(
                    status,
                    published_at=row[4],
                    captured_at=row[5] if status != "published" else "",
                    unpublished_reason=row[11] or row[6],
                ),
                article_category=admin_gate_news_article_category(
                    row[12],
                    row[13],
                    admin_gate_json_summary(row[14], []),
                ),
            ))
    return records


def collect_admin_talent_records(conn):
    records = []
    if sqlite_has_table(conn, "websim_community_talent_templates"):
        rows = conn.execute(
            """
            SELECT id, class_key, spec_key, hero_key, scenario_key, name,
                   source_key, source_name, source_url, source_status, status,
                   sample_count, max_key_level, analysis_window, payload_json,
                   updated_at, expires_at, signature, source_refs_json, scan_run_id
            FROM websim_community_talent_templates
            WHERE expires_at > ?
            ORDER BY updated_at DESC
            LIMIT 500
            """,
            (utc_now(),),
        ).fetchall()
        for row in rows:
            payload = admin_gate_json_summary(row[14], {})
            refs = admin_gate_json_summary(row[18], [])
            records.append(admin_gate_record(
                "talents",
                "community_talent_template",
                row[0],
                row[5],
                status=row[10],
                source_status=row[9],
                source_name=row[7],
                source_url=row[8],
                checked_at=row[15],
                blockers=admin_gate_payload_error_texts(payload),
                facets={
                    "classKey": row[1],
                    "specKey": row[2],
                    "heroKey": row[3],
                    "scenarioKey": row[4],
                    "sourceKey": row[6],
                    "sampleCount": row[11],
                    "maxKeyLevel": row[12],
                    "analysisWindow": row[13],
                    "signature": row[17],
                    "scanRunId": row[19],
                },
                raw_summary={"name": row[5], "expiresAt": row[16]},
                evidence={"sourceRefs": refs[:5] if isinstance(refs, list) else []},
                talent_category=admin_gate_talent_record_category(row[1], row[2], row[3], row[6], "community_talent_template"),
            ))
    return records


def collect_admin_gear_template_records(conn):
    records = []
    if sqlite_has_table(conn, "websim_community_gear_templates"):
        rows = conn.execute(
            """
            SELECT id, class_key, spec_key, name, source_key, source_name,
                   source_url, source_status, status, signature, source_refs_json,
                   gear_items_json, raw_string, ready_slot_count, missing_slots_json,
                   analysis_window, payload_json, updated_at, expires_at, scan_run_id
            FROM websim_community_gear_templates
            ORDER BY updated_at DESC
            LIMIT 500
            """
        ).fetchall()
        for row in rows:
            missing_slots = admin_gate_json_summary(row[14], [])
            payload = admin_gate_json_summary(row[16], {})
            blockers = payload.get("blockers") if isinstance(payload, dict) else []
            if missing_slots:
                blockers = [*(blockers or []), f"missing slots: {', '.join(str(item) for item in missing_slots[:6])}"]
            records.append(admin_gate_record(
                "gear_templates",
                "community_gear_template",
                row[0],
                row[3],
                status=row[8],
                source_status=row[7],
                source_name=row[5],
                source_url=row[6],
                checked_at=row[17],
                blockers=blockers,
                facets={
                    "classKey": row[1],
                    "specKey": row[2],
                    "sourceKey": row[4],
                    "signature": row[9],
                    "readySlotCount": row[13],
                    "missingSlots": missing_slots,
                    "analysisWindow": row[15],
                    "scanRunId": row[19],
                },
                raw_summary={
                    "name": row[3],
                    "readySlotCount": row[13],
                    "rawLineCount": len([line for line in str(row[12] or "").splitlines() if line.strip()]),
                    "expiresAt": row[18],
                },
                evidence={
                    "sourceRefs": admin_gate_json_summary(row[10], [])[:5],
                    "templateEvidence": payload.get("templateEvidence") if isinstance(payload, dict) else {},
                },
                gear_category=admin_gate_gear_record_category(
                    "community_gear_template",
                    class_key=row[1],
                    spec_key=row[2],
                    source_key=row[4],
                    ready_slot_count=row[13],
                    missing_slots=missing_slots,
                ),
            ))
    return records


def collect_admin_gear_records(conn):
    records = []
    if sqlite_has_table(conn, "websim_gear_variants"):
        variant_columns = sqlite_table_columns(conn, "websim_gear_variants")

        def variant_expr(column, default="''"):
            return f"v.{column}" if column in variant_columns else default

        variant_id_expr = variant_expr("id")
        item_id_expr = variant_expr("item_id")
        slot_expr = variant_expr("slot")
        label_expr = variant_expr("label")
        source_type_expr = variant_expr("source_type")
        difficulty_expr = variant_expr("difficulty_key")
        item_level_expr = variant_expr("item_level", "0")
        simc_options_expr = variant_expr("simc_options_json", "'{}'")
        status_expr = variant_expr("status")
        blockers_expr = variant_expr("blockers_json", "'[]'")
        payload_expr = variant_expr("payload_json", "'{}'")
        updated_expr = variant_expr("updated_at")
        order_expr = "v.updated_at DESC" if "updated_at" in variant_columns else "v.id"
        source_label_expr = "''"
        source_instance_expr = "''"
        if sqlite_has_table(conn, "websim_gear_sources"):
            source_columns = sqlite_table_columns(conn, "websim_gear_sources")
            can_match_source = (
                {"item_id", "source_type", "source_label"}.issubset(source_columns)
                and {"item_id", "source_type"}.issubset(variant_columns)
            )
            has_source_difficulty = "difficulty_key" in source_columns and "difficulty_key" in variant_columns
            if can_match_source:
                source_match_parts = [
                    "s.item_id = v.item_id",
                    "s.source_type = v.source_type",
                ]
                if has_source_difficulty:
                    source_match_parts.append(
                        "(s.difficulty_key = v.difficulty_key OR s.difficulty_key = '' OR v.difficulty_key = '')"
                    )
                source_match = " AND ".join(source_match_parts)
                source_order_parts = []
                source_order_parts.append("NULLIF(s.source_label, '')")
                if "updated_at" in source_columns:
                    source_order_parts.append("s.updated_at DESC")
                source_order = f"ORDER BY {', '.join(source_order_parts)}" if source_order_parts else ""
                source_label_expr = f"""
                    COALESCE((
                        SELECT s.source_label
                        FROM websim_gear_sources s
                        WHERE {source_match}
                        {source_order}
                        LIMIT 1
                    ), '')
                """
                if "instance_id" in source_columns:
                    source_instance_expr = f"""
                        COALESCE((
                            SELECT s.instance_id
                            FROM websim_gear_sources s
                            WHERE {source_match}
                            {source_order}
                            LIMIT 1
                        ), '')
                    """
        rows = conn.execute(
            f"""
            SELECT {variant_id_expr}, {item_id_expr}, COALESCE(NULLIF(i.name, ''), {item_id_expr}),
                   {slot_expr}, {label_expr}, {source_type_expr}, {difficulty_expr},
                   {item_level_expr}, {simc_options_expr}, {status_expr}, {blockers_expr}, {payload_expr},
                   COALESCE(i.payload_json, '{{}}'),
                   {source_label_expr}, {source_instance_expr},
                   {updated_expr}
            FROM websim_gear_variants v
            LEFT JOIN websim_items i ON i.id = v.item_id
            ORDER BY {order_expr}
            """
        ).fetchall()
        variant_items = []
        for row in rows:
            blockers = admin_gate_json_summary(row[10], [])
            payload = admin_gate_json_summary(row[11], {})
            item_payload = admin_gate_json_summary(row[12], {})
            variant_items.append({
                "id": row[0],
                "itemId": row[1],
                "itemName": row[2],
                "slot": row[3],
                "label": row[4],
                "sourceType": row[5],
                "difficultyKey": row[6],
                "itemLevel": row[7],
                "simcOptions": admin_gate_json_summary(row[8], {}),
                "status": row[9],
                "blockers": blockers if isinstance(blockers, list) else [],
                "payload": payload if isinstance(payload, dict) else {},
                "itemPayload": item_payload if isinstance(item_payload, dict) else {},
                "sourceLabel": row[13],
                "sourceInstanceId": row[14],
                "updatedAt": row[15],
            })
        records.extend(collect_admin_gear_records_from_variant_items(variant_items))
    return records


def collect_admin_news_records_from_store(store):
    payload = store.admin_gate_news_records()
    queue_items = payload.get("discoveryQueue") if isinstance(payload, dict) else []
    article_items = payload.get("articles") if isinstance(payload, dict) else []
    records = []
    for item in queue_items or []:
        payload_summary = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        blockers = [item.get("lastError")] if item.get("lastError") else []
        records.append(admin_gate_record(
            "news",
            "news_discovery_queue",
            item.get("id"),
            item.get("originalTitle"),
            status=item.get("status"),
            source_status="verified" if item.get("status") == "published" else item.get("status"),
            source_name=item.get("sourceName"),
            source_url=item.get("sourceUrl"),
            checked_at=item.get("updatedAt") or item.get("discoveredAt") or "",
            blockers=blockers,
            facets={
                "sourceKey": item.get("sourceId") or "",
                "sourceTier": item.get("sourceTier") or "",
                "canonicalTopicId": item.get("canonicalTopicId") or "",
                "attempts": item.get("attempts") or 0,
            },
            raw_summary={
                "originalTitle": item.get("originalTitle") or "",
                "publishedAt": item.get("publishedAt") or "",
                "payloadKeys": sorted(payload_summary.keys())[:12] if isinstance(payload_summary, dict) else [],
            },
            evidence={
                "contentGate": "discovery_queue",
                "runtimeStore": "postgres_content",
                "processedAt": item.get("processedAt") or "",
            },
            publication=admin_gate_news_publication(
                item.get("status"),
                published_at=item.get("publishedAt") or "",
                captured_at=item.get("discoveredAt") or "",
                unpublished_reason=item.get("lastError") or "",
            ),
            article_category=admin_gate_news_article_category(
                payload_summary.get("channel") if isinstance(payload_summary, dict) else "",
                payload_summary.get("category") if isinstance(payload_summary, dict) else "",
                payload_summary.get("tags") if isinstance(payload_summary, dict) else [],
            ),
        ))
    for item in article_items or []:
        status = "published" if item.get("contentStatus") == "ready" else item.get("contentStatus")
        blockers = [item.get("blockedReason")] if item.get("blockedReason") else []
        records.append(admin_gate_record(
            "news",
            "news_article",
            item.get("id"),
            item.get("title"),
            status=status,
            source_status="verified" if item.get("contentStatus") == "ready" else item.get("contentStatus"),
            source_name=item.get("sourceName"),
            source_url=item.get("sourceUrl"),
            checked_at=item.get("updatedAt") or "",
            blockers=blockers,
            facets={
                "contentStatus": item.get("contentStatus") or "",
                "translationStatus": item.get("translationStatus") or "",
                "licenseStatus": item.get("licenseStatus") or "",
                "verificationStatus": item.get("verificationStatus") or "",
                "translationFidelity": item.get("translationFidelity") or "",
                "publishedAt": item.get("publishedAt") or "",
            },
            raw_summary={"title": item.get("title") or "", "publishedAt": item.get("publishedAt") or ""},
            evidence={"contentGate": "public_article", "runtimeStore": "postgres_content"},
            publication=admin_gate_news_publication(
                status,
                published_at=item.get("publishedAt") or "",
                captured_at=item.get("updatedAt") if status != "published" else "",
                unpublished_reason=item.get("blockedReason") or item.get("contentStatus") or "",
            ),
            article_category=admin_gate_news_article_category(
                item.get("channel") or "",
                item.get("category") or "",
                item.get("tags") or [],
            ),
        ))
    return records


def admin_gate_payload_error_texts(payload):
    if not isinstance(payload, dict):
        return []
    texts = []
    for key in ("blockers", "errors"):
        value = payload.get(key)
        if isinstance(value, list):
            texts.extend(str(item) for item in value if str(item or "").strip())
        elif str(value or "").strip():
            texts.append(str(value))
    for key in ("talentLoadoutParse", "talentEncoding"):
        section = payload.get(key) if isinstance(payload.get(key), dict) else {}
        value = section.get("errors")
        if isinstance(value, list):
            texts.extend(str(item) for item in value if str(item or "").strip())
        elif str(value or "").strip():
            texts.append(str(value))
    unique = []
    seen = set()
    for text in texts:
        if text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def collect_admin_talent_records_from_store(store):
    payload = store.admin_gate_talent_records()
    template_items = payload.get("communityTalentTemplates") if isinstance(payload, dict) else []
    records = []
    for item in template_items or []:
        if timestamp_expired(item.get("expiresAt") or ""):
            continue
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        wcl_evidence = item_payload.get("wclEvidence") if isinstance(item_payload.get("wclEvidence"), dict) else {}
        rio_evidence = item_payload.get("rioEvidence") if isinstance(item_payload.get("rioEvidence"), dict) else {}
        records.append(admin_gate_record(
            "talents",
            "community_talent_template",
            item.get("id"),
            item.get("name"),
            status=item.get("status"),
            source_status=item.get("sourceStatus"),
            source_name=item.get("sourceName"),
            source_url=item.get("sourceUrl"),
            checked_at=item.get("updatedAt") or "",
            blockers=admin_gate_payload_error_texts(item_payload),
            facets={
                "classKey": item.get("classKey") or "",
                "specKey": item.get("specKey") or "",
                "heroKey": item.get("heroKey") or "",
                "scenarioKey": item.get("scenarioKey") or "",
                "sourceKey": item.get("sourceKey") or "",
                "sampleCount": item.get("sampleCount") or 0,
                "maxKeyLevel": item.get("maxKeyLevel") or 0,
                "analysisWindow": item.get("analysisWindow") or "",
                "signature": item.get("signature") or "",
                "scanRunId": item.get("scanRunId") or "",
                "evidenceTier": item_payload.get("evidenceTier") or wcl_evidence.get("tier") or "",
                "wclEvidenceTier": wcl_evidence.get("tier") or "",
                "qualityScore": item_payload.get("qualityScore") or 0,
            },
            raw_summary={"name": item.get("name") or "", "expiresAt": item.get("expiresAt") or ""},
            evidence={
                "sourceRefs": (item.get("sourceRefs") or [])[:5] if isinstance(item.get("sourceRefs"), list) else [],
                "runtimeStore": "postgres_cache",
                "rioEvidence": rio_evidence,
                "wclEvidence": wcl_evidence,
                "promotionReason": item_payload.get("promotionReason") or "",
            },
            talent_category=admin_gate_talent_record_category(
                item.get("classKey") or "",
                item.get("specKey") or "",
                item.get("heroKey") or "",
                item.get("sourceKey") or "",
                "community_talent_template",
            ),
        ))
    return records


def collect_admin_gear_template_records_from_store(store):
    if hasattr(store, "admin_gate_gear_template_records"):
        payload = store.admin_gate_gear_template_records()
    else:
        payload = store.admin_gate_gear_records()
    template_items = payload.get("communityGearTemplates") if isinstance(payload, dict) else []
    records = []
    for item in template_items or []:
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        missing_slots = item.get("missingSlots") if isinstance(item.get("missingSlots"), list) else []
        blockers = item_payload.get("blockers") if isinstance(item_payload, dict) else []
        if missing_slots:
            blockers = [*(blockers or []), f"missing slots: {', '.join(str(slot) for slot in missing_slots[:6])}"]
        records.append(admin_gate_record(
            "gear_templates",
            "community_gear_template",
            item.get("id"),
            item.get("name"),
            status=item.get("status"),
            source_status=item.get("sourceStatus"),
            source_name=item.get("sourceName"),
            source_url=item.get("sourceUrl"),
            checked_at=item.get("updatedAt") or "",
            blockers=blockers,
            facets={
                "classKey": item.get("classKey") or "",
                "specKey": item.get("specKey") or "",
                "sourceKey": item.get("sourceKey") or "",
                "signature": item.get("signature") or "",
                "readySlotCount": item.get("readySlotCount") or 0,
                "missingSlots": missing_slots,
                "analysisWindow": item.get("analysisWindow") or "",
                "scanRunId": item.get("scanRunId") or "",
            },
            raw_summary={
                "name": item.get("name") or "",
                "readySlotCount": item.get("readySlotCount") or 0,
                "expiresAt": item.get("expiresAt") or "",
            },
            evidence={
                "sourceRefs": (item.get("sourceRefs") or [])[:5] if isinstance(item.get("sourceRefs"), list) else [],
                "runtimeStore": "postgres_cache",
            },
            gear_category=admin_gate_gear_record_category(
                "community_gear_template",
                class_key=item.get("classKey") or "",
                spec_key=item.get("specKey") or "",
                source_key=item.get("sourceKey") or "",
                ready_slot_count=item.get("readySlotCount") or 0,
                missing_slots=missing_slots,
            ),
        ))
    return records


def collect_admin_gear_records_from_variant_items(variant_items, runtime_store=""):
    records = []
    for item in admin_gate_primary_gear_variants(variant_items):
        variant_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        item_payload = item.get("itemPayload") if isinstance(item.get("itemPayload"), dict) else {}
        combined_payload = {**item_payload, **variant_payload}
        simc_options = admin_gate_gear_variant_simc_options(item)
        if simc_options:
            combined_payload["simcOptions"] = simc_options
        blockers = item.get("blockers") if isinstance(item.get("blockers"), list) else []
        class_keys = admin_gate_gear_class_keys_from_payload(combined_payload, item.get("slot") or "")
        source_detail_label = item.get("sourceLabel") or ""
        source_instance_id = item.get("sourceInstanceId") or ""
        source_instance_label = item.get("sourceInstanceLabel") or ""
        variant_ids = item.get("adminGateVariantIds") if isinstance(item.get("adminGateVariantIds"), list) else []
        evidence = {
            "variant": "websim_gear_variants",
            "representativeVariantId": item.get("id") or "",
            "variantIds": variant_ids[:12],
        }
        if runtime_store:
            evidence["runtimeStore"] = runtime_store
        raw_summary = {
            "payloadKeys": sorted(combined_payload.keys())[:12] if isinstance(combined_payload, dict) else [],
            "variantCount": item.get("adminGateVariantCount") or 1,
            "verifiedVariantCount": item.get("adminGateVerifiedVariantCount") or 0,
            "blockedOrPartialVariantCount": item.get("adminGateBlockedVariantCount") or 0,
        }
        gear_category = admin_gate_gear_record_category(
            "gear_variant",
            slot=item.get("slot") or "",
            label=item.get("label") or "",
            source_type=item.get("sourceType") or "",
            source_detail_label=source_detail_label,
            source_instance_id=source_instance_id,
            source_instance_label=source_instance_label,
            difficulty_key=item.get("difficultyKey") or "",
            item_level=item.get("itemLevel") or 0,
            class_keys=class_keys,
            item_type_payload=combined_payload,
        )
        source_terms = item.get("adminGateSourceInstanceTerms")
        if isinstance(source_terms, list) and source_terms:
            gear_category["sourceInstanceAliases"] = admin_gate_unique_text_list([
                gear_category.get("sourceInstanceAliases") or [],
                source_terms,
            ])
        variants = item.get("adminGateVariants")
        if isinstance(variants, list) and variants:
            gear_category["variants"] = variants
        records.append(admin_gate_record(
            "gear",
            "gear_variant",
            item.get("id"),
            item.get("itemName") or item.get("itemId"),
            status=item.get("status"),
            source_status=item.get("status"),
            source_name=item.get("sourceType"),
            checked_at=item.get("updatedAt") or "",
            blockers=blockers,
            facets={
                "itemId": item.get("itemId") or "",
                "slot": item.get("slot") or "",
                "label": item.get("label") or "",
                "sourceType": item.get("sourceType") or "",
                "sourceDetailLabel": source_detail_label,
                "sourceInstanceId": source_instance_id,
                "sourceInstanceLabel": source_instance_label,
                "difficultyKey": item.get("difficultyKey") or "",
                "itemLevel": item.get("itemLevel") or 0,
                "classKeys": class_keys,
                "variantIds": variant_ids,
            },
            raw_summary=raw_summary,
            evidence=evidence,
            gear_category=gear_category,
        ))
    return records


def collect_admin_gear_records_from_store(store):
    if hasattr(store, "admin_gate_gear_variant_records"):
        payload = store.admin_gate_gear_variant_records()
    else:
        payload = store.admin_gate_gear_records()
    variant_items = payload.get("gearVariants") if isinstance(payload, dict) else []
    return collect_admin_gear_records_from_variant_items(variant_items, runtime_store="postgres_cache")


def collect_admin_gate_records_from_runtime_stores(query=None):
    query = query or {}
    domain = admin_query_value(query, "domain", "")
    requested = {domain} if domain else {"news", "talents", "gear", "gear_templates"}
    records = []
    used_runtime_store = False
    if "news" in requested:
        store = content_data_store()
        if store and hasattr(store, "admin_gate_news_records"):
            used_runtime_store = True
            records.extend(collect_admin_news_records_from_store(store))
    if "talents" in requested or "talent" in requested:
        store = cache_data_store()
        if store and hasattr(store, "admin_gate_talent_records"):
            used_runtime_store = True
            records.extend(collect_admin_talent_records_from_store(store))
    if "gear" in requested:
        store = cache_data_store()
        if store and (hasattr(store, "admin_gate_gear_variant_records") or hasattr(store, "admin_gate_gear_records")):
            used_runtime_store = True
            records.extend(collect_admin_gear_records_from_store(store))
    if "gear_templates" in requested:
        store = cache_data_store()
        if store and (hasattr(store, "admin_gate_gear_template_records") or hasattr(store, "admin_gate_gear_records")):
            used_runtime_store = True
            template_records = collect_admin_gear_template_records_from_store(store)
            records.extend(template_records)
    if not used_runtime_store:
        return None
    return filter_admin_gate_records(records, query)


def collect_admin_gate_records(conn, query=None):
    query = query or {}
    domain = admin_query_value(query, "domain", "")
    requested = {domain} if domain else {"news", "talents", "gear", "gear_templates"}
    records = []
    if "news" in requested:
        records.extend(collect_admin_news_records(conn))
    if "talents" in requested or "talent" in requested:
        records.extend(collect_admin_talent_records(conn))
    if "gear" in requested:
        records.extend(collect_admin_gear_records(conn))
    if "gear_templates" in requested:
        records.extend(collect_admin_gear_template_records(conn))
    return filter_admin_gate_records(records, query)


ADMIN_GATE_RECORD_DOMAINS = ["news", "talents", "gear", "gear_templates"]
ADMIN_GATE_PG_RUNTIME_BLOCKER = "PostgreSQL runtime store is not available"


def admin_gate_filter_text(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(admin_gate_filter_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(admin_gate_filter_text(item) for item in value)
    return str(value)


def admin_gate_record_filter_fields(record):
    domain = str(record.get("domain") or "").strip()
    common = {
        "title": [
            record.get("title"),
            record.get("targetType"),
            record.get("targetId"),
        ],
        "status": [
            record.get("status"),
            record.get("statusLabel"),
        ],
        "source": [
            record.get("sourceName"),
            record.get("sourceUrl"),
        ],
        "blockers": [
            record.get("blockers"),
            record.get("blockerDetails"),
        ],
    }
    if domain == "news":
        fields = {
            **common,
            "category": [record.get("articleCategory")],
            "publication": [record.get("publication")],
        }
        fields["all"] = [
            fields["title"],
            fields["category"],
            fields["status"],
            fields["publication"],
            fields["source"],
            fields["blockers"],
        ]
        return fields
    if domain == "talents":
        category = record.get("talentCategory") if isinstance(record.get("talentCategory"), dict) else {}
        publication = record.get("talentPublication") if isinstance(record.get("talentPublication"), dict) else {}
        block_reason = record.get("talentBlockReason") if isinstance(record.get("talentBlockReason"), dict) else {}
        is_blocked = str(record.get("status") or "").strip() in {"blocked", "missing_credentials"}
        blocked_text = ["已阻断", "被阻断", "blocked", record.get("status"), record.get("statusLabel")] if is_blocked else [
            "未阻断",
            "未被阻断",
            "not blocked",
            record.get("status"),
            record.get("statusLabel"),
        ]
        fields = {
            "talentTemplate": [
                record.get("title"),
                record.get("targetType"),
                record.get("targetId"),
            ],
            "class": [
                category.get("label"),
                category.get("classKey"),
                category.get("classLabel"),
                category.get("specKey"),
                category.get("heroKey"),
            ],
            "source": [
                record.get("sourceName"),
                record.get("sourceUrl"),
                category.get("sourceKind"),
                category.get("sourceLabel"),
                category.get("sourceKey"),
            ],
            "blocked": blocked_text,
            "blockReason": [
                block_reason.get("state"),
                block_reason.get("stateLabel"),
                block_reason.get("reason"),
                record.get("blockers"),
            ],
            "visibility": [
                publication.get("state"),
                publication.get("stateLabel"),
                publication.get("surface"),
                publication.get("reason"),
                publication.get("visibleAt"),
                "小程序可见" if publication.get("visibleToMiniProgram") else "小程序不可见",
            ],
        }
        fields["title"] = fields["talentTemplate"]
        fields["category"] = fields["class"]
        fields["status"] = fields["blocked"]
        fields["blockers"] = fields["blockReason"]
        fields["all"] = [
            fields["talentTemplate"],
            fields["class"],
            fields["source"],
            fields["blocked"],
            fields["blockReason"],
            fields["visibility"],
        ]
        return fields
    if domain == "gear":
        category = record.get("gearCategory") if isinstance(record.get("gearCategory"), dict) else {}
        visibility = record.get("gearVisibility") if isinstance(record.get("gearVisibility"), dict) else {}
        block_reason = record.get("gearBlockReason") if isinstance(record.get("gearBlockReason"), dict) else {}
        fields = {
            "gearName": [
                record.get("title"),
                record.get("targetType"),
                record.get("targetId"),
                category.get("variantLabel"),
                category.get("itemLevel"),
            ],
            "slot": [
                category.get("slot"),
                category.get("slotLabel"),
                category.get("label"),
            ],
            "dropSource": [
                record.get("sourceName"),
                record.get("sourceUrl"),
                category.get("sourceType"),
                category.get("sourceLabel"),
                category.get("sourceDetailLabel"),
                category.get("sourceInstanceLabel"),
                category.get("difficultyKey"),
            ],
            "sourceInstance": [
                category.get("sourceInstanceId"),
                category.get("sourceInstanceLabel"),
                category.get("sourceInstanceAliases"),
                category.get("sourceDetailLabel"),
            ],
            "class": [
                category.get("classKeys"),
                category.get("classLabels"),
                category.get("classLabel"),
            ],
            "itemType": [
                category.get("itemTypeKey"),
                category.get("itemTypeLabel"),
                category.get("itemTypeGroupKey"),
                category.get("itemTypeGroupLabel"),
                category.get("itemTypeRaw"),
                category.get("itemTypeAliases"),
            ],
            "visibility": [
                visibility.get("state"),
                visibility.get("stateLabel"),
                visibility.get("surface"),
                visibility.get("reason"),
                visibility.get("visibleAt"),
                "小程序可见" if visibility.get("visibleToMiniProgram") else "小程序不可见",
            ],
            "blockReason": [
                block_reason.get("state"),
                block_reason.get("stateLabel"),
                block_reason.get("reason"),
                record.get("blockers"),
            ],
        }
        fields["title"] = fields["gearName"]
        fields["category"] = [category]
        fields["status"] = common["status"]
        fields["source"] = fields["dropSource"]
        fields["blockers"] = fields["blockReason"]
        fields["all"] = [
            fields["gearName"],
            fields["slot"],
            fields["dropSource"],
            fields["sourceInstance"],
            fields["status"],
            fields["itemType"],
            fields["visibility"],
            fields["blockReason"],
        ]
        return fields
    if domain == "gear_templates":
        category = record.get("gearCategory") if isinstance(record.get("gearCategory"), dict) else {}
        visibility = record.get("gearVisibility") if isinstance(record.get("gearVisibility"), dict) else {}
        block_reason = record.get("gearBlockReason") if isinstance(record.get("gearBlockReason"), dict) else {}
        fields = {
            "template": common["title"],
            "class": [
                category.get("label"),
                category.get("classKey"),
                category.get("classLabel"),
                category.get("specKey"),
                category.get("sourceKind"),
                category.get("sourceLabel"),
            ],
            "visibility": [
                visibility.get("state"),
                visibility.get("stateLabel"),
                visibility.get("surface"),
                visibility.get("reason"),
                visibility.get("visibleAt"),
                "小程序可见" if visibility.get("visibleToMiniProgram") else "小程序不可见",
            ],
            "blockReason": [
                block_reason.get("state"),
                block_reason.get("stateLabel"),
                block_reason.get("reason"),
                record.get("blockers"),
            ],
        }
        fields["title"] = fields["template"]
        fields["category"] = fields["class"]
        fields["status"] = common["status"]
        fields["source"] = [
            *common["source"],
            category.get("sourceKind"),
            category.get("sourceLabel"),
            category.get("sourceKey"),
        ]
        fields["blockers"] = fields["blockReason"]
        fields["all"] = [
            fields["title"],
            fields["category"],
            fields["status"],
            fields["visibility"],
            fields["source"],
            fields["blockers"],
        ]
        return fields
    fields = dict(common)
    fields["all"] = [fields["title"], fields["status"], fields["source"], fields["blockers"]]
    return fields


def admin_gate_record_matches_search(record, search, field):
    search_value = str(search or "").strip().lower()
    if not search_value:
        return True
    fields = admin_gate_record_filter_fields(record)
    field_value = str(field or "all").strip() or "all"
    if field_value not in fields:
        field_value = "all"
    return search_value in admin_gate_filter_text(fields.get(field_value)).lower()


def filter_admin_gate_records(records, query):
    status = admin_query_value(query, "status", "")
    source = admin_query_value(query, "source", "").lower()
    class_key = admin_query_value(query, "classKey", "")
    spec_key = admin_query_value(query, "specKey", "")
    search = admin_query_value(query, "q", "").lower()
    field = admin_query_value(query, "field", "all")
    filtered = []
    for record in records:
        facets = record.get("facets") if isinstance(record.get("facets"), dict) else {}
        if status and record.get("status") != status:
            continue
        if source and source not in f"{record.get('sourceName', '')} {facets.get('sourceKey', '')} {facets.get('sourceType', '')}".lower():
            continue
        if class_key and facets.get("classKey") != class_key:
            continue
        if spec_key and facets.get("specKey") != spec_key:
            continue
        if search and not admin_gate_record_matches_search(record, search, field):
            continue
        filtered.append(record)
    return filtered


def paginate_admin_gate_records(records, query):
    page_size = admin_query_page_size(query)
    total = len(records)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(admin_query_page(query), total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasPrev": page > 1,
        "hasNext": page < total_pages,
    }


def admin_gate_records_payload(query):
    paged_gear_payload = admin_gate_paged_gear_records_payload(query)
    if paged_gear_payload is not None:
        return paged_gear_payload
    records = collect_admin_gate_records_from_runtime_stores(query)
    runtime_blockers = []
    if records is None:
        if postgres_only_runtime_enabled():
            records = []
            runtime_blockers.append(ADMIN_GATE_PG_RUNTIME_BLOCKER)
        else:
            init_db()
            with db_connection() as conn:
                records = collect_admin_gate_records(conn, query)
    page_records, pagination = paginate_admin_gate_records(records, query)
    return {
        "schemaRevision": "admin-gates-records-v1",
        "records": page_records,
        "count": len(page_records),
        "totalCount": pagination["total"],
        "pagination": pagination,
        "runtimeBlockers": runtime_blockers,
        "filters": {
            "domain": admin_query_value(query, "domain", ""),
            "status": admin_query_value(query, "status", ""),
            "source": admin_query_value(query, "source", ""),
            "classKey": admin_query_value(query, "classKey", ""),
            "specKey": admin_query_value(query, "specKey", ""),
            "field": admin_query_value(query, "field", "all"),
            "q": admin_query_value(query, "q", ""),
            "page": str(pagination["page"]),
            "pageSize": str(pagination["pageSize"]),
        },
    }


def admin_gate_paged_gear_records_payload(query):
    if admin_query_value(query, "domain", "") != "gear":
        return None
    for key in ("status", "source", "classKey", "specKey", "q"):
        if admin_query_value(query, key, ""):
            return None
    store = cache_data_store()
    if not store or not hasattr(store, "admin_gate_gear_variant_records_page"):
        return None
    page_size = admin_query_page_size(query)
    page = admin_query_page(query)
    offset = (page - 1) * page_size
    payload = store.admin_gate_gear_variant_records_page(limit=page_size, offset=offset)
    if not isinstance(payload, dict):
        return None
    variant_items = payload.get("gearVariants") if isinstance(payload.get("gearVariants"), list) else []
    records = collect_admin_gear_records_from_variant_items(variant_items, runtime_store="postgres_cache")
    total = safe_positive_int(payload.get("totalGroups"))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    return {
        "schemaRevision": "admin-gates-records-v1",
        "records": records,
        "count": len(records),
        "totalCount": total,
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
            "hasPrev": page > 1,
            "hasNext": page < total_pages,
        },
        "filters": {
            "domain": "gear",
            "status": "",
            "source": "",
            "classKey": "",
            "specKey": "",
            "field": admin_query_value(query, "field", "all"),
            "q": "",
            "page": str(page),
            "pageSize": str(page_size),
        },
    }


def merge_admin_gate_queue_summaries(*summaries):
    total = 0
    domain_counts = {}
    blocker_counts = {}
    used = False
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        used = True
        total += safe_positive_int(summary.get("count"))
        for domain, count in (summary.get("domainCounts") or {}).items():
            key = str(domain or "unknown")
            domain_counts[key] = domain_counts.get(key, 0) + safe_positive_int(count)
        for item in summary.get("topBlockers") or []:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "").strip()
            if reason:
                blocker_counts[reason] = blocker_counts.get(reason, 0) + (safe_positive_int(item.get("count")) or 1)
    if not used:
        return None
    return {
        "count": total,
        "domainCounts": domain_counts,
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }


def admin_gate_queue_summary_from_runtime_stores():
    summaries = []
    content_store = content_data_store()
    if content_store and hasattr(content_store, "admin_gate_queue_summary"):
        summaries.append(content_store.admin_gate_queue_summary())
    cache_store = cache_data_store()
    if cache_store and hasattr(cache_store, "admin_gate_queue_summary"):
        summaries.append(cache_store.admin_gate_queue_summary())
    return merge_admin_gate_queue_summaries(*summaries)


def find_admin_gate_record(conn, domain, target_type, target_id):
    domain = admin_gate_record_domain_for_target(domain, target_type)
    records = collect_admin_gate_records(conn, {"domain": [domain], "limit": ["200"]})
    for record in records:
        if record.get("targetType") == target_type and record.get("targetId") == target_id:
            return record
    return None


def find_admin_gate_record_runtime(domain, target_type, target_id):
    domain = admin_gate_record_domain_for_target(domain, target_type)
    records = collect_admin_gate_records_from_runtime_stores({"domain": [domain], "limit": ["200"]})
    if records is None:
        return None
    for record in records:
        if record.get("targetType") == target_type and record.get("targetId") == target_id:
            return record
    return None


def admin_gate_diagnosis_from_row(row, record=None):
    payload = admin_gate_json_summary(row[11], {})
    record = record or {}
    resolved = bool(record and admin_gate_record_passed(record))
    return {
        "id": row[0],
        "targetDomain": row[1],
        "targetType": row[2],
        "targetId": row[3],
        "diagnosis": row[4],
        "gapType": row[5],
        "reason": row[6],
        "note": row[7],
        "actor": row[8],
        "targetFingerprint": row[9],
        "resolutionStatus": "resolved" if resolved else "open",
        "resolutionStatusLabel": admin_gate_status_label("resolved" if resolved else "open"),
        "currentStatus": record.get("status") or "",
        "currentStatusLabel": admin_gate_status_label(record.get("status") or ""),
        "currentSourceStatus": record.get("sourceStatus") or "",
        "currentSourceStatusLabel": admin_gate_status_label(record.get("sourceStatus") or ""),
        "createdAt": row[10],
        "updatedAt": row[12],
        "expiresAt": row[13],
        "payload": payload,
    }


def admin_gate_diagnosis_from_mapping(item, record=None):
    record = record or {}
    resolved = bool(record and admin_gate_record_passed(record))
    payload = sanitize_health_value(item.get("payload") if isinstance(item.get("payload"), dict) else {})
    return {
        "id": item.get("id") or "",
        "targetDomain": item.get("targetDomain") or "",
        "targetType": item.get("targetType") or "",
        "targetId": item.get("targetId") or "",
        "diagnosis": item.get("diagnosis") or "",
        "gapType": item.get("gapType") or "",
        "reason": item.get("reason") or "",
        "note": item.get("note") or "",
        "actor": item.get("actor") or "",
        "targetFingerprint": item.get("targetFingerprint") or "",
        "resolutionStatus": "resolved" if resolved else "open",
        "resolutionStatusLabel": admin_gate_status_label("resolved" if resolved else "open"),
        "currentStatus": record.get("status") or "",
        "currentStatusLabel": admin_gate_status_label(record.get("status") or ""),
        "currentSourceStatus": record.get("sourceStatus") or "",
        "currentSourceStatusLabel": admin_gate_status_label(record.get("sourceStatus") or ""),
        "createdAt": item.get("createdAt") or "",
        "updatedAt": item.get("updatedAt") or "",
        "expiresAt": item.get("expiresAt") or "",
        "payload": payload,
    }


def create_admin_gate_diagnosis(payload, actor="admin"):
    target_domain = str(payload.get("targetDomain") or payload.get("domain") or "").strip()
    target_type = str(payload.get("targetType") or "").strip()
    target_id = str(payload.get("targetId") or "").strip()
    target_domain = admin_gate_record_domain_for_target(target_domain, target_type)
    diagnosis = str(payload.get("diagnosis") or "system_gap_suspected").strip()
    gap_type = str(payload.get("gapType") or diagnosis).strip()
    reason = admin_gate_summarize_text(payload.get("reason") or "", 500)
    note = admin_gate_summarize_text(payload.get("note") or "", 1000)
    if not target_domain or not target_type or not target_id:
        raise ValueError("targetDomain, targetType and targetId are required")
    if diagnosis not in ADMIN_GATE_DIAGNOSES:
        raise ValueError("invalid admin gate diagnosis")
    if gap_type not in ADMIN_GATE_GAP_TYPES:
        raise ValueError("invalid admin gate gap type")
    if not reason:
        raise ValueError("diagnosis reason is required")
    now = utc_now()
    diagnosis_id = f"agd-{uuid.uuid4()}"
    runtime_ops_store = ops_data_store()
    if runtime_ops_store and hasattr(runtime_ops_store, "create_admin_gate_diagnosis"):
        record = find_admin_gate_record_runtime(target_domain, target_type, target_id)
        fingerprint = admin_gate_record_fingerprint(record or {"status": "missing_target"})
        safe_payload = {
            "targetTitle": (record or {}).get("title", ""),
            "targetStatus": (record or {}).get("status", ""),
            "targetSourceStatus": (record or {}).get("sourceStatus", ""),
            "blockers": (record or {}).get("blockers", [])[:8],
        }
        entry = {
            "id": diagnosis_id,
            "targetDomain": target_domain,
            "targetType": target_type,
            "targetId": target_id,
            "diagnosis": diagnosis,
            "gapType": gap_type,
            "reason": reason,
            "note": note,
            "actor": actor,
            "targetFingerprint": fingerprint,
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": str(payload.get("expiresAt") or ""),
        }
        stored = runtime_ops_store.create_admin_gate_diagnosis(
            entry,
            {
                "targetDomain": target_domain,
                "diagnosis": diagnosis,
                "gapType": gap_type,
                "reason": reason,
                **safe_payload,
            },
        )
        return admin_gate_diagnosis_from_mapping(stored, record)

    init_db()
    with db_connection() as conn:
        ensure_admin_gate_tables(conn)
        record = find_admin_gate_record(conn, target_domain, target_type, target_id)
        fingerprint = admin_gate_record_fingerprint(record or {"status": "missing_target"})
        safe_payload = {
            "targetTitle": (record or {}).get("title", ""),
            "targetStatus": (record or {}).get("status", ""),
            "targetSourceStatus": (record or {}).get("sourceStatus", ""),
            "blockers": (record or {}).get("blockers", [])[:8],
        }
        conn.execute(
            """
            INSERT INTO admin_gate_diagnoses (
                id, target_domain, target_type, target_id, diagnosis, gap_type,
                reason, note, actor, target_fingerprint, created_at, updated_at,
                expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                diagnosis_id,
                target_domain,
                target_type,
                target_id,
                diagnosis,
                gap_type,
                reason,
                note,
                actor,
                fingerprint,
                now,
                now,
                str(payload.get("expiresAt") or ""),
            ),
        )
        audit_id = f"audit-{uuid.uuid4()}"
        conn.execute(
            """
            INSERT INTO ops_audit_logs (
                id, actor, action, target_type, target_id, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                actor,
                "admin_gate.diagnose",
                target_type,
                target_id,
                json.dumps(
                    {
                        "diagnosisId": diagnosis_id,
                        "targetDomain": target_domain,
                        "diagnosis": diagnosis,
                        "gapType": gap_type,
                        "reason": reason,
                        **safe_payload,
                    },
                    ensure_ascii=False,
                ),
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, target_domain, target_type, target_id, diagnosis, gap_type,
                   reason, note, actor, target_fingerprint, created_at, '{}',
                   updated_at, expires_at
            FROM admin_gate_diagnoses WHERE id = ?
            """,
            (diagnosis_id,),
        ).fetchone()
    return admin_gate_diagnosis_from_row(row, record)


def admin_gate_diagnoses_payload(query):
    domain = admin_query_value(query, "domain", "")
    status = admin_query_value(query, "resolutionStatus", "")
    runtime_ops_store = ops_data_store()
    if runtime_ops_store and hasattr(runtime_ops_store, "list_admin_gate_diagnoses"):
        rows = runtime_ops_store.list_admin_gate_diagnoses()
        items = []
        for row in rows:
            if domain and row.get("targetDomain") != domain:
                continue
            record = find_admin_gate_record_runtime(row.get("targetDomain"), row.get("targetType"), row.get("targetId"))
            item = admin_gate_diagnosis_from_mapping(row, record)
            if status and item["resolutionStatus"] != status:
                continue
            items.append(item)
        return {
            "schemaRevision": "admin-gates-diagnoses-v1",
            "items": items[:admin_query_limit(query)],
            "count": len(items[:admin_query_limit(query)]),
        }

    init_db()
    with db_connection() as conn:
        ensure_admin_gate_tables(conn)
        rows = conn.execute(
            """
            SELECT id, target_domain, target_type, target_id, diagnosis, gap_type,
                   reason, note, actor, target_fingerprint, created_at, '{}',
                   updated_at, expires_at
            FROM admin_gate_diagnoses
            ORDER BY created_at DESC
            LIMIT 500
            """
        ).fetchall()
        items = []
        for row in rows:
            if domain and row[1] != domain:
                continue
            record = find_admin_gate_record(conn, row[1], row[2], row[3])
            item = admin_gate_diagnosis_from_row(row, record)
            if status and item["resolutionStatus"] != status:
                continue
            items.append(item)
    return {
        "schemaRevision": "admin-gates-diagnoses-v1",
        "items": items[:admin_query_limit(query)],
        "count": len(items[:admin_query_limit(query)]),
    }


def admin_gate_queue_payload(query):
    domain = admin_query_value(query, "domain", "")
    limit = admin_query_limit(query)
    severity = admin_query_value(query, "severity", "")
    runtime_ops_store = ops_data_store()
    diagnoses_by_target = {}
    runtime_blockers = []
    if runtime_ops_store and hasattr(runtime_ops_store, "list_admin_gate_diagnoses"):
        for row in runtime_ops_store.list_admin_gate_diagnoses():
            diagnoses_by_target.setdefault((row.get("targetDomain"), row.get("targetType"), row.get("targetId")), []).append(row)
        diagnosis_builder = admin_gate_diagnosis_from_mapping
    elif postgres_only_runtime_enabled():
        runtime_blockers.append(ADMIN_GATE_PG_RUNTIME_BLOCKER)
        diagnosis_builder = admin_gate_diagnosis_from_mapping
    else:
        init_db()
        with db_connection() as conn:
            diagnoses_rows = conn.execute(
                """
                SELECT id, target_domain, target_type, target_id, diagnosis, gap_type,
                       reason, note, actor, target_fingerprint, created_at, '{}',
                       updated_at, expires_at
                FROM admin_gate_diagnoses
                ORDER BY created_at DESC
                LIMIT 500
                """
            ).fetchall() if sqlite_has_table(conn, "admin_gate_diagnoses") else []
            for row in diagnoses_rows:
                diagnoses_by_target.setdefault((row[1], row[2], row[3]), []).append(row)
        diagnosis_builder = admin_gate_diagnosis_from_row

    def load_records(load_domain):
        domain_query = {"domain": [load_domain], "limit": ["200"]} if load_domain else {"limit": ["200"]}
        records = collect_admin_gate_records_from_runtime_stores(domain_query)
        if records is None:
            if postgres_only_runtime_enabled():
                if ADMIN_GATE_PG_RUNTIME_BLOCKER not in runtime_blockers:
                    runtime_blockers.append(ADMIN_GATE_PG_RUNTIME_BLOCKER)
                records = []
            else:
                init_db()
                with db_connection() as conn:
                    records = collect_admin_gate_records(conn, domain_query)
        return records or []

    def queue_items_from_records(records, remaining):
        output = []
        for record in records:
            if admin_gate_record_passed(record):
                continue
            if record.get("status") not in ADMIN_GATE_QUEUE_STATUSES and not record.get("blockers"):
                continue
            key = (record.get("domain"), record.get("targetType"), record.get("targetId"))
            open_diagnoses = []
            for row in diagnoses_by_target.get(key, []):
                diagnosis = diagnosis_builder(row, record)
                if diagnosis["resolutionStatus"] == "open":
                    open_diagnoses.append(diagnosis)
            item = {
                "id": f"queue:{record['id']}",
                "targetDomain": record.get("domain"),
                "targetType": record.get("targetType"),
                "targetId": record.get("targetId"),
                "title": record.get("title"),
                "status": record.get("status"),
                "statusLabel": admin_gate_status_label(record.get("status")),
                "sourceStatus": record.get("sourceStatus"),
                "sourceStatusLabel": admin_gate_status_label(record.get("sourceStatus")),
                "severity": record.get("severity"),
                "severityLabel": admin_gate_severity_label(record.get("severity")),
                "blockers": record.get("blockers", [])[:5],
                "blockerDetails": record.get("blockerDetails", [])[:5],
                "diagnoses": open_diagnoses,
                "checkedAt": record.get("checkedAt", ""),
            }
            if severity and item.get("severity") != severity:
                continue
            output.append(item)
            if len(output) >= remaining:
                break
        return output

    items = []
    domains = [domain] if domain else ADMIN_GATE_RECORD_DOMAINS
    for load_domain in domains:
        remaining = limit - len(items)
        if remaining <= 0:
            break
        items.extend(queue_items_from_records(load_records(load_domain), remaining))
    return {
        "schemaRevision": "admin-gates-queue-v1",
        "items": items[:limit],
        "count": len(items[:limit]),
        "runtimeBlockers": runtime_blockers,
    }


def admin_gate_queue_summary_payload(records=None):
    if records is None:
        runtime_summary = admin_gate_queue_summary_from_runtime_stores()
        if runtime_summary is not None:
            return runtime_summary
    records = records if records is not None else collect_admin_gate_records_from_runtime_stores({"limit": ["200"]})
    if records is None:
        if postgres_only_runtime_enabled():
            return {
                "count": 0,
                "domainCounts": {},
                "topBlockers": [],
                "runtimeBlockers": [ADMIN_GATE_PG_RUNTIME_BLOCKER],
            }
        init_db()
        with db_connection() as conn:
            records = collect_admin_gate_records(conn, {"limit": ["200"]})
    counts = {}
    top_blockers = {}
    total = 0
    for record in records or []:
        if admin_gate_record_passed(record):
            continue
        if record.get("status") not in ADMIN_GATE_QUEUE_STATUSES and not record.get("blockers"):
            continue
        total += 1
        domain = record.get("domain") or "unknown"
        counts[domain] = counts.get(domain, 0) + 1
        for blocker in record.get("blockers") or []:
            text = str(blocker or "").strip()
            if text:
                top_blockers[text] = top_blockers.get(text, 0) + 1
    return {
        "count": total,
        "domainCounts": counts,
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(top_blockers.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }


def admin_gate_summary_payload():
    health = build_data_health_payload(include_template_evidence_audit=False)
    components = health.get("components") if isinstance(health.get("components"), list) else []
    status_counts = {status: 0 for status in DATA_HEALTH_STATUSES}
    for component in components:
        status = component.get("status") or "blocked"
        status_counts[status] = status_counts.get(status, 0) + 1
    queue_summary = admin_gate_queue_summary_payload()
    return {
        "schemaRevision": "admin-gates-summary-v1",
        "checkedAt": utc_now(),
        "productRule": {
            "systemGate": "consumption_fact",
            "humanJudgement": "diagnostic_fact",
            "manualVerifiedOverride": False,
            "manualPublishOverride": False,
        },
        "navigation": [
            {"key": "overview", "label": "总览"},
            {"key": "news", "label": "新闻资讯"},
            {"key": "talents", "label": "天赋模板"},
            {"key": "gear", "label": "装备库"},
            {"key": "gearTemplates", "label": "装备模板"},
            {"key": "queue", "label": "待诊断阻断项"},
            {"key": "diagnoses", "label": "诊断记录"},
            {"key": "system", "label": "系统状态"},
        ],
        "overallStatus": health.get("overallStatus") or data_health_overall_status(components),
        "overallStatusLabel": admin_gate_status_label(health.get("overallStatus") or data_health_overall_status(components)),
        "statusCounts": status_counts,
        "statusLabels": {status: admin_gate_status_label(status) for status in DATA_HEALTH_STATUSES},
        "severityLabels": ADMIN_GATE_SEVERITY_LABELS,
        "modules": [
            {
                "key": component.get("key", ""),
                "title": admin_gate_module_title(component),
                "rawTitle": component.get("title", ""),
                "status": component.get("status", ""),
                "statusLabel": admin_gate_status_label(component.get("status", "")),
                "checkedAt": component.get("checkedAt", ""),
                "blockers": [
                    admin_gate_localized_blocker(item)
                    for item in (component.get("blockers") or [])[:5]
                ],
                "topBlockers": [
                    admin_gate_localized_top_blocker(item)
                    for item in ((component.get("details") or {}).get("topBlockers") or [])[:5]
                ],
            }
            for component in components
        ],
        "queueSummary": queue_summary,
        "diagnosticQueue": {
            "count": queue_summary.get("count", 0),
            "items": [],
        },
        "sourceHealth": health,
    }


def admin_gate_record_detail_payload(domain, target_type, target_id):
    record = find_admin_gate_record_runtime(domain, target_type, target_id)
    if record is None:
        if postgres_only_runtime_enabled():
            return {}
        init_db()
        with db_connection() as conn:
            record = find_admin_gate_record(conn, domain, target_type, target_id)
    if not record:
        return {}
    return {
        "schemaRevision": "admin-gates-record-detail-v1",
        "record": record,
        "sections": record.get("stages", []),
    }


def admin_gates_response(handler, path, query):
    if not admin_authorized(handler.headers):
        json_response(handler, 401, {"error": "unauthorized"})
        return
    if path == "/api/admin/gates/summary":
        json_response(handler, 200, admin_gate_summary_payload())
        return
    if path == "/api/admin/gates/records":
        json_response(handler, 200, admin_gate_records_payload(query))
        return
    if path.startswith("/api/admin/gates/records/"):
        record_id = unquote(path.removeprefix("/api/admin/gates/records/"))
        parts = record_id.split(":", 2)
        if len(parts) == 3:
            payload = admin_gate_record_detail_payload(parts[0], parts[1], parts[2])
            json_response(handler, 200 if payload else 404, payload or {"error": "admin_gate_record_not_found"})
        else:
            json_response(handler, 400, {"error": "invalid_admin_gate_record_id"})
        return
    if path == "/api/admin/gates/queue":
        json_response(handler, 200, admin_gate_queue_payload(query))
        return
    if path == "/api/admin/gates/diagnoses":
        json_response(handler, 200, admin_gate_diagnoses_payload(query))
        return
    json_response(handler, 404, {"error": "not_found"})


def admin_gates_page():
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>门禁治理台</title>
  <style>
    :root { color-scheme: dark; --bg:#0d1117; --panel:#161b22; --line:#30363d; --text:#e6edf3; --muted:#8b949e; --gold:#f0b429; --red:#f85149; --green:#3fb950; --blue:#58a6ff; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; letter-spacing:0; }
    .shell { display:grid; grid-template-columns:220px minmax(0,1fr); min-height:100vh; }
    aside { border-right:1px solid var(--line); padding:20px; background:#010409; }
    main { padding:22px; min-width:0; max-width:1500px; width:100%; }
    h1,h2,h3,p { margin-top:0; }
    h1 { font-size:24px; margin-bottom:4px; }
    h2 { font-size:18px; margin:18px 0 10px; }
    h3 { font-size:15px; margin:0 0 8px; }
    .muted { color:var(--muted); }
    input,select,button,textarea { width:100%; border:1px solid var(--line); border-radius:6px; background:#0d1117; color:var(--text); padding:9px 10px; font:inherit; }
    button { cursor:pointer; background:var(--gold); color:#111; border-color:var(--gold); font-weight:700; }
    nav button { margin-bottom:8px; background:#161b22; color:var(--text); border-color:var(--line); text-align:left; }
    nav button.active { border-color:var(--gold); color:var(--gold); background:#1f252d; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
    .module-grid, .queue-list { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; }
    .card { border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:14px; }
    .metric { font-size:26px; color:var(--gold); font-weight:800; }
    .status { display:inline-block; border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:12px; color:var(--muted); }
    .status.verified { color:var(--green); border-color:rgba(63,185,80,.4); }
    .status.blocked, .status.missing_credentials { color:var(--red); border-color:rgba(248,81,73,.4); }
    .status.partial, .status.pending_official_audit, .status.source_reference { color:var(--gold); border-color:rgba(240,180,41,.4); }
    .category-pill { display:inline-block; border:1px solid rgba(88,166,255,.45); border-radius:999px; padding:2px 8px; color:var(--blue); font-size:12px; white-space:nowrap; }
    .variant-list { display:flex; flex-wrap:wrap; gap:4px 6px; margin-top:6px; }
    .variant-chip { display:inline-flex; align-items:center; gap:4px; border:1px solid rgba(63,185,80,.4); border-radius:999px; padding:2px 7px; color:var(--green); font-size:12px; white-space:nowrap; }
    .variant-chip.partial { color:var(--gold); border-color:rgba(240,180,41,.4); }
    .variant-chip.blocked, .variant-chip.missing_credentials { color:var(--red); border-color:rgba(248,81,73,.4); }
    table { width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }
    th,td { border-bottom:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }
    th { color:var(--muted); font-weight:700; }
    .toolbar { display:grid; grid-template-columns:1fr 1fr 1fr minmax(260px,1.4fr) auto; gap:8px; margin:14px 0; align-items:end; }
    .toolbar[hidden] { display:none; }
    .news-toolbar { grid-template-columns:minmax(160px,.8fr) minmax(220px,1fr) auto; }
    .gear-toolbar { grid-template-columns:minmax(160px,.7fr) minmax(180px,.8fr) minmax(220px,1fr) auto; }
    .pagination { display:flex; align-items:center; gap:8px; justify-content:flex-end; margin-top:10px; flex-wrap:wrap; }
    .pagination button { width:auto; min-width:76px; padding:7px 10px; }
    .pagination button:disabled { opacity:.45; cursor:not-allowed; }
    .pagination select { width:auto; min-width:112px; padding:7px 10px; }
    .pagination .summary { min-width:160px; text-align:center; }
    .queue-item { border:1px solid var(--line); border-radius:8px; padding:10px; margin-bottom:10px; background:var(--panel); }
    .view { display:none; }
    .view.active { display:block; }
    .view.active.stack { display:grid; }
    .stack { gap:14px; }
    .notice { border:1px solid var(--line); border-radius:8px; padding:10px; margin:10px 0; color:var(--muted); background:#0d1117; }
    .notice.error { color:var(--red); border-color:rgba(248,81,73,.45); }
    .small { font-size:12px; }
    .auth-panel { border:1px solid var(--line); border-radius:8px; padding:10px; margin:14px 0; background:#0d1117; }
    .auth-panel button, .auth-panel input { margin-top:8px; }
    .token-actions { display:grid; grid-template-columns:1fr; gap:6px; margin-top:6px; }
    .token-actions button { background:#161b22; color:var(--text); border-color:var(--line); }
    @media (max-width: 900px) {
      .shell { grid-template-columns:1fr; }
      aside { border-right:0; border-bottom:1px solid var(--line); }
      .toolbar { grid-template-columns:1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>门禁治理台</h1>
      <p class="muted small">系统门禁是消费事实，人工判断是诊断事实。</p>
      <div class="auth-panel">
        <p id="authStatus" class="muted small">请输入固定 WOW_ADMIN_TOKEN。</p>
        <input id="token" type="password" placeholder="WOW_ADMIN_TOKEN">
        <div class="token-actions">
          <button id="saveToken" type="button">保存 token 到本机</button>
          <button id="clearToken" type="button">清除本机 token</button>
        </div>
        <p class="muted small">保存后会写入当前浏览器本机存储，后续自动加载。</p>
      </div>
      <h2>导航</h2>
      <nav id="nav"></nav>
    </aside>
    <main>
      <div id="adminGateMessage" class="notice">请输入固定 WOW_ADMIN_TOKEN 后加载。</div>
      <section id="overviewView" class="view active stack" data-admin-gate-view="overview">
        <section class="card">
          <h2>治理驾驶舱</h2>
          <div id="summary" class="grid"><div class="card muted">等待加载线上门禁数据。</div></div>
        </section>
        <section>
          <h2>模块概览</h2>
          <div id="modules" class="module-grid"><div class="card muted">等待加载模块状态。</div></div>
        </section>
      </section>
      <section id="recordsView" class="view" data-admin-gate-view="records">
        <h2 id="recordsTitle">全量记录</h2>
        <div id="genericToolbar" class="toolbar">
          <select id="domain"><option value="">全部模块</option><option value="news">新闻资讯</option><option value="talents">天赋模板</option><option value="gear">装备库</option><option value="gear_templates">装备模板</option></select>
          <select id="status"><option value="">全部状态</option><option value="verified">verified（已验证）</option><option value="partial">partial（部分通过）</option><option value="stale">stale（已过期）</option><option value="blocked">blocked（已阻断）</option><option value="missing_credentials">missing_credentials（缺少凭据）</option><option value="pending_official_audit">pending_official_audit（待官方校验）</option><option value="source_reference">source_reference（仅作参考）</option></select>
          <select id="field"></select>
          <input id="q" placeholder="搜索当前模块展示字段">
          <button id="load">加载</button>
        </div>
        <div id="newsToolbar" class="toolbar news-toolbar" hidden>
          <select id="newsFilterKey"><option value="category">分类</option><option value="status">状态</option><option value="publication">发布情况</option></select>
          <select id="newsFilterValue"></select>
          <button id="newsLoad" type="button">加载</button>
        </div>
        <div id="talentToolbar" class="toolbar news-toolbar" hidden>
          <select id="talentFilterKey"><option value="class">职业</option><option value="status">状态</option><option value="visibility">小程序可见性</option></select>
          <select id="talentFilterValue"></select>
          <button id="talentLoad" type="button">加载</button>
        </div>
        <div id="gearToolbar" class="toolbar news-toolbar gear-toolbar" hidden>
          <select id="gearFilterKey"><option value="dropSource">掉落来源</option><option value="itemType">装备分类</option><option value="visibility">小程序可见性</option></select>
          <select id="gearFilterValue"></select>
          <select id="gearSourceInstanceValue" hidden></select>
          <button id="gearLoad" type="button">加载</button>
        </div>
        <div id="gearTemplateToolbar" class="toolbar news-toolbar" hidden>
          <select id="gearTemplateFilterKey"><option value="class">职业</option><option value="visibility">小程序是否可见</option></select>
          <select id="gearTemplateFilterValue"></select>
          <button id="gearTemplateLoad" type="button">加载</button>
        </div>
        <table id="records"><tr><td class="muted">登录后加载线上门禁数据。</td></tr></table>
        <div class="pagination" aria-label="记录分页">
          <button id="prevPage" type="button">上一页</button>
          <span id="paginationSummary" class="muted small summary">第 1 / 1 页，共 0 条</span>
          <button id="nextPage" type="button">下一页</button>
          <select id="pageSize" aria-label="单页展示数量">
            <option value="20" selected>20 条/页</option>
            <option value="50">50 条/页</option>
            <option value="100">100 条/页</option>
            <option value="200">200 条/页</option>
          </select>
        </div>
      </section>
      <section id="queueView" class="view stack" data-admin-gate-view="queue">
        <section>
          <h2>待诊断阻断项</h2>
          <div id="queue" class="queue-list"><div class="queue-item muted">等待加载待诊断阻断项。</div></div>
        </section>
        <section class="card">
          <h2>提交诊断</h2>
          <textarea id="diagnosisPayload" rows="9" spellcheck="false" placeholder='{"targetDomain":"gear_templates","targetType":"community_gear_template","targetId":"...","diagnosis":"system_gap_suspected","gapType":"parser_or_mapping_bug","reason":"..."}'></textarea>
          <button id="submitDiagnosis">记录诊断</button>
          <p id="diagnosisResult" class="muted small"></p>
        </section>
      </section>
      <section id="diagnosesView" class="view" data-admin-gate-view="diagnoses">
        <h2>诊断记录</h2>
        <div id="diagnoses"><p class="muted">等待加载诊断记录。</p></div>
      </section>
      <section id="systemView" class="view" data-admin-gate-view="system">
        <h2>系统状态</h2>
        <div id="systemHealth"><p class="muted">等待加载系统状态。</p></div>
      </section>
    </main>
  </div>
  <script>
    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    const ADMIN_TOKEN_STORAGE_KEY = 'wowAdminToken';
    const ADMIN_GATE_DEFAULT_PAGE_SIZE = 20;
    let currentAdminGateNav = 'overview';
    let adminGateRecordsPage = 1;
    let latestAdminGateNavigation = [];
    const domainByNavKey = { news:'news', talents:'talents', gear:'gear', gearTemplates:'gear_templates' };
    const recordTitleByNavKey = { news:'新闻资讯记录', talents:'天赋模板记录', gear:'装备库记录', gearTemplates:'装备模板记录' };
    const statusLabels = { verified:'已验证', partial:'部分通过', stale:'已过期', blocked:'已阻断', missing_credentials:'缺少凭据', pending_official_audit:'待官方校验', source_reference:'仅作参考', passed:'已通过', synced:'已同步', ready:'已就绪', complete:'已完成', published:'已发布', open:'未解决', resolved:'已解决' };
    const severityLabels = { ok:'正常', blocks_frontend_publish:'阻断前端发布', blocks_frontend_template:'阻断前端模板展示', blocks_simc_or_strong_claim:'阻断 SimC 或强结论', blocks_diagnostic_or_record:'影响诊断记录' };
    const domainLabels = { news:'新闻资讯', talents:'天赋模板', gear:'装备库', gear_templates:'装备模板' };
    const adminGateFilterFields = {
      news: [
        { value:'all', label:'全部展示字段', placeholder:'搜索标题、分类、状态、发布情况、来源、Blockers' },
        { value:'title', label:'标题', placeholder:'搜索标题、target type、target id' },
        { value:'category', label:'分类', placeholder:'搜索正式服动态、测试服前瞻、职业强度变化或标签' },
        { value:'status', label:'状态', placeholder:'搜索 verified、blocked、已验证、已阻断' },
        { value:'publication', label:'发布情况', placeholder:'搜索已发布、未发布、发布时间、抓取时间或未发布原因' },
        { value:'source', label:'来源', placeholder:'搜索来源名称或 URL' },
        { value:'blockers', label:'Blockers', placeholder:'搜索 blocker 或诊断建议' },
      ],
      talents: [
        { value:'all', label:'全部展示字段', placeholder:'搜索天赋模板、职业、来源、是否被阻断、阻断原因、小程序可见' },
        { value:'talentTemplate', label:'天赋模板', placeholder:'搜索模板名、target type、target id' },
        { value:'class', label:'职业', placeholder:'搜索职业、专精或英雄天赋' },
        { value:'source', label:'来源', placeholder:'搜索来源名称、URL 或社区来源' },
        { value:'blocked', label:'是否被阻断', placeholder:'搜索已阻断、未阻断、blocked 或 verified' },
        { value:'blockReason', label:'阻断原因', placeholder:'搜索阻断原因、blocker 或未通过状态' },
        { value:'visibility', label:'小程序可见', placeholder:'搜索已可见、不可见、天赋导入列表或原因' },
      ],
      gear: [
        { value:'all', label:'全部展示字段', placeholder:'搜索装备名称、部位、掉落来源、状态、装备分类、小程序可见性、Block原因' },
        { value:'gearName', label:'装备名称', placeholder:'搜索装备名、target type、target id' },
        { value:'slot', label:'部位', placeholder:'搜索头部、手套、head、hands 等部位' },
        { value:'dropSource', label:'掉落来源', placeholder:'搜索地下城、团本、制造业、dungeon、raid 等来源' },
        { value:'sourceInstance', label:'具体副本 / 团本', placeholder:'搜索 Magisters Terrace、The Voidspire、通天峰等具体来源' },
        { value:'status', label:'状态', placeholder:'搜索 verified、blocked、已验证、已阻断' },
        { value:'itemType', label:'装备分类', placeholder:'搜索护甲类型、武器类型、首饰、布甲、法杖、饰品等分类' },
        { value:'visibility', label:'小程序可见性', placeholder:'搜索已可见、不可见' },
        { value:'blockReason', label:'Block原因', placeholder:'搜索 blocker 或诊断建议' },
      ],
      gear_templates: [
        { value:'all', label:'全部展示字段', placeholder:'搜索装备模板、职业、来源、状态、Blockers' },
        { value:'title', label:'装备模板', placeholder:'搜索模板名、target type、target id' },
        { value:'category', label:'职业', placeholder:'搜索职业、专精或社区来源' },
        { value:'status', label:'状态', placeholder:'搜索 verified、blocked、已验证、已阻断' },
        { value:'source', label:'来源', placeholder:'搜索来源名称或 URL' },
        { value:'blockers', label:'Blockers', placeholder:'搜索 blocker 或诊断建议' },
      ],
      all: [
        { value:'all', label:'全部展示字段', placeholder:'搜索当前模块展示字段' },
        { value:'title', label:'标题', placeholder:'搜索标题、target type、target id' },
        { value:'status', label:'状态', placeholder:'搜索状态' },
        { value:'source', label:'来源', placeholder:'搜索来源名称或 URL' },
        { value:'blockers', label:'Blockers', placeholder:'搜索 blocker 或诊断建议' },
      ],
    };
    const newsFilterOptions = [
      {
        value:'category',
        label:'分类',
        queryField:'category',
        values:[
          { value:'', label:'全部分类' },
          { value:'正式服动态', label:'正式服动态' },
          { value:'测试服前瞻', label:'测试服前瞻' },
          { value:'职业强度变化', label:'职业强度变化' },
        ],
      },
      {
        value:'status',
        label:'状态',
        queryField:'status',
        values:[
          { value:'', label:'全部状态' },
          { value:'verified', label:'verified（已验证）' },
          { value:'partial', label:'partial（部分通过）' },
          { value:'stale', label:'stale（已过期）' },
          { value:'blocked', label:'blocked（已阻断）' },
          { value:'missing_credentials', label:'missing_credentials（缺少凭据）' },
          { value:'pending_official_audit', label:'pending_official_audit（待官方校验）' },
          { value:'source_reference', label:'source_reference（仅作参考）' },
        ],
      },
      {
        value:'publication',
        label:'发布情况',
        queryField:'publication',
        values:[
          { value:'', label:'全部发布情况' },
          { value:'已发布', label:'已发布' },
          { value:'未发布', label:'未发布' },
        ],
      },
    ];
    const talentFilterOptions = [
      {
        value:'class',
        label:'职业',
        queryField:'class',
        values:[
          { value:'', label:'全部职业' },
          { value:'死亡骑士', label:'死亡骑士' },
          { value:'恶魔猎手', label:'恶魔猎手' },
          { value:'德鲁伊', label:'德鲁伊' },
          { value:'唤魔师', label:'唤魔师' },
          { value:'猎人', label:'猎人' },
          { value:'法师', label:'法师' },
          { value:'武僧', label:'武僧' },
          { value:'圣骑士', label:'圣骑士' },
          { value:'牧师', label:'牧师' },
          { value:'潜行者', label:'潜行者' },
          { value:'萨满祭司', label:'萨满祭司' },
          { value:'术士', label:'术士' },
          { value:'战士', label:'战士' },
        ],
      },
      {
        value:'status',
        label:'状态',
        queryField:'status',
        values:[
          { value:'', label:'全部状态' },
          { value:'verified', label:'verified（已验证）' },
          { value:'partial', label:'partial（部分通过）' },
          { value:'stale', label:'stale（已过期）' },
          { value:'blocked', label:'blocked（已阻断）' },
          { value:'missing_credentials', label:'missing_credentials（缺少凭据）' },
          { value:'pending_official_audit', label:'pending_official_audit（待官方校验）' },
          { value:'source_reference', label:'source_reference（仅作参考）' },
        ],
      },
      {
        value:'visibility',
        label:'小程序可见性',
        queryField:'visibility',
        values:[
          { value:'', label:'全部可见性' },
          { value:'已可见', label:'已可见' },
          { value:'不可见', label:'不可见' },
        ],
      },
    ];
    const gearFilterOptions = [
      {
        value:'dropSource',
        label:'掉落来源',
        queryField:'dropSource',
        values:[
          { value:'', label:'全部掉落来源' },
          { value:'地下城', label:'地下城' },
          { value:'团本', label:'团本' },
          { value:'制造业', label:'制造业' },
          { value:'已验证掉落', label:'已验证掉落' },
          { value:'社区样本', label:'社区样本' },
          { value:'默认模板', label:'默认模板' },
          { value:'WebSim 基线', label:'WebSim 基线' },
        ],
      },
      {
        value:'itemType',
        label:'装备分类',
        queryField:'itemType',
        values:[
          { value:'', label:'全部装备分类' },
          { value:'护甲类型', label:'护甲类型' },
          { value:'布甲', label:'布甲' },
          { value:'皮甲', label:'皮甲' },
          { value:'锁甲', label:'锁甲' },
          { value:'板甲', label:'板甲' },
          { value:'武器类型', label:'武器类型' },
          { value:'匕首', label:'匕首' },
          { value:'拳套', label:'拳套' },
          { value:'单手斧', label:'单手斧' },
          { value:'单手锤', label:'单手锤' },
          { value:'单手剑', label:'单手剑' },
          { value:'战刃', label:'战刃' },
          { value:'魔杖', label:'魔杖' },
          { value:'双手斧', label:'双手斧' },
          { value:'双手锤', label:'双手锤' },
          { value:'双手剑', label:'双手剑' },
          { value:'长柄武器', label:'长柄武器' },
          { value:'法杖', label:'法杖' },
          { value:'弓', label:'弓' },
          { value:'弩', label:'弩' },
          { value:'枪械', label:'枪械' },
          { value:'盾牌', label:'盾牌' },
          { value:'副手物品', label:'副手物品' },
          { value:'首饰', label:'首饰' },
          { value:'项链', label:'项链' },
          { value:'戒指', label:'戒指' },
          { value:'饰品', label:'饰品' },
          { value:'披风', label:'披风' },
          { value:'未标注分类', label:'未标注分类' },
        ],
      },
      {
        value:'visibility',
        label:'小程序可见性',
        queryField:'visibility',
        values:[
          { value:'', label:'全部可见性' },
          { value:'已可见', label:'已可见' },
          { value:'不可见', label:'不可见' },
        ],
      },
    ];
    const gearSourceInstanceOptions = {
      dungeon: [
        { value:"Magisters' Terrace", label:"Magisters' Terrace / 魔导师平台" },
        { value:'Maisara Caverns', label:'Maisara Caverns / 迈萨拉洞窟' },
        { value:'Nexus-Point Xenas', label:'Nexus-Point Xenas / 节点希纳斯' },
        { value:'Windrunner Spire', label:'Windrunner Spire / 风行者之塔' },
        { value:"Algeth'ar Academy", label:"Algeth'ar Academy / 艾杰斯亚学院" },
        { value:'Pit of Saron', label:'Pit of Saron / 萨隆矿坑' },
        { value:'Seat of the Triumvirate', label:'Seat of the Triumvirate / 执政团之座' },
        { value:'Skyreach', label:'Skyreach / 通天峰' },
      ],
      raid: [
        { value:'The Voidspire', label:'The Voidspire / 虚影尖塔' },
        { value:'The Dreamrift', label:'The Dreamrift / 梦境裂隙' },
        { value:"March on Quel'Danas", label:"March on Quel'Danas / 进军奎尔丹纳斯" },
        { value:'Sporefall', label:'Sporefall / 孢陨幽境' },
      ],
    };
    const gearTemplateFilterOptions = [
      {
        value:'class',
        label:'职业',
        queryField:'class',
        values:[
          { value:'', label:'全部职业' },
          { value:'死亡骑士', label:'死亡骑士' },
          { value:'恶魔猎手', label:'恶魔猎手' },
          { value:'德鲁伊', label:'德鲁伊' },
          { value:'唤魔师', label:'唤魔师' },
          { value:'猎人', label:'猎人' },
          { value:'法师', label:'法师' },
          { value:'武僧', label:'武僧' },
          { value:'圣骑士', label:'圣骑士' },
          { value:'牧师', label:'牧师' },
          { value:'潜行者', label:'潜行者' },
          { value:'萨满祭司', label:'萨满祭司' },
          { value:'术士', label:'术士' },
          { value:'战士', label:'战士' },
          { value:'未标注职业', label:'未标注职业' },
        ],
      },
      {
        value:'visibility',
        label:'小程序是否可见',
        queryField:'visibility',
        values:[
          { value:'', label:'全部可见性' },
          { value:'已可见', label:'已可见' },
          { value:'不可见', label:'不可见' },
        ],
      },
    ];
    function token() { return document.getElementById('token').value.trim(); }
    function loadSavedAdminToken() {
      try {
        const saved = localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || '';
        if (saved) document.getElementById('token').value = saved;
        return saved;
      } catch (error) {
        return '';
      }
    }
    function saveAdminToken() {
      const value = token();
      if (!value) {
        showAuthStatus('请输入 token 后再保存到本机。', true);
        return;
      }
      try {
        localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, value);
        showAuthStatus('token 已保存到本机浏览器。');
      } catch (error) {
        showAuthStatus('token 保存失败：浏览器禁止本地存储。', true);
      }
    }
    function clearSavedAdminToken() {
      try {
        localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      } catch (error) {}
      document.getElementById('token').value = '';
      showAuthStatus('本机保存的 token 已清除。');
    }
    function showAuthStatus(message, isError = false) {
      const node = document.getElementById('authStatus');
      node.className = isError ? 'notice error small' : 'muted small';
      node.textContent = message;
    }
    function showAdminGateError(message) {
      const node = document.getElementById('adminGateMessage');
      node.className = 'notice error';
      node.textContent = message || '加载失败';
    }
    function clearAdminGateError() {
      const node = document.getElementById('adminGateMessage');
      node.className = 'notice';
      node.textContent = '正在加载线上门禁数据...';
    }
    async function api(path, options = {}) {
      if (!token()) throw new Error('请输入固定 WOW_ADMIN_TOKEN 后加载');
      const headers = { 'Content-Type':'application/json', ...(options.headers || {}) };
      if (token()) headers.Authorization = `Bearer ${token()}`;
      const res = await fetch(path, { ...options, credentials:'same-origin', headers });
      if (!res.ok) throw new Error(res.status === 401 ? '认证失败：请检查 WOW_ADMIN_TOKEN' : `HTTP ${res.status}`);
      return res.json();
    }
    function withQuery(path, params) {
      const query = params.toString();
      return query ? `${path}?${query}` : path;
    }
    function statusText(value) {
      const key = String(value ?? '').trim();
      const label = statusLabels[key] || key;
      return label && label !== key ? `${key}（${label}）` : key;
    }
    function severityText(value) {
      const key = String(value ?? '').trim();
      const label = severityLabels[key] || key;
      return label && label !== key ? `${key}（${label}）` : key;
    }
    function statusPill(value) { return `<span class="status ${escapeHtml(value)}">${escapeHtml(statusText(value))}</span>`; }
    function blockerText(item) {
      const details = item.blockerDetails || [];
      if (details.length) {
        return details.map(detail => `${detail.title}：${detail.explanation} 建议：${detail.action}（${detail.code}）`).join(' / ');
      }
      return (item.blockers || []).join(' / ');
    }
    function renderAdminGateNav(items) {
      latestAdminGateNavigation = items || latestAdminGateNavigation;
      document.getElementById('nav').innerHTML = items.map(item => `<button type="button" data-admin-gate-nav="${escapeHtml(item.key)}" class="${item.key === currentAdminGateNav ? 'active' : ''}">${escapeHtml(item.label)}</button>`).join('');
    }
    function setAdminGateDomainFilter(domain) {
      document.getElementById('domain').value = domain;
    }
    function resetAdminGatePage() {
      adminGateRecordsPage = 1;
    }
    function recordsPageSize() {
      const node = document.getElementById('pageSize');
      return node ? (node.value || String(ADMIN_GATE_DEFAULT_PAGE_SIZE)) : String(ADMIN_GATE_DEFAULT_PAGE_SIZE);
    }
    function renderRecordsPagination(pagination) {
      const page = Number((pagination || {}).page || adminGateRecordsPage || 1);
      const pageSize = Number((pagination || {}).pageSize || recordsPageSize() || ADMIN_GATE_DEFAULT_PAGE_SIZE);
      const total = Number((pagination || {}).total || 0);
      const totalPages = Math.max(1, Number((pagination || {}).totalPages || 1));
      adminGateRecordsPage = page;
      document.getElementById('prevPage').disabled = !(pagination || {}).hasPrev;
      document.getElementById('nextPage').disabled = !(pagination || {}).hasNext;
      document.getElementById('paginationSummary').textContent = `第 ${page} / ${totalPages} 页，共 ${total} 条`;
      const pageSizeNode = document.getElementById('pageSize');
      if (pageSizeNode) pageSizeNode.value = String(pageSize);
    }
    function updateAdminGateFilterControls() {
      const domain = document.getElementById('domain').value.trim() || 'all';
      const fieldNode = document.getElementById('field');
      const qNode = document.getElementById('q');
      const options = adminGateFilterFields[domain] || adminGateFilterFields.all;
      const current = fieldNode.value || 'all';
      fieldNode.innerHTML = options.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      fieldNode.value = options.some(item => item.value === current) ? current : 'all';
      const selected = options.find(item => item.value === fieldNode.value) || options[0];
      qNode.placeholder = selected.placeholder;
    }
    function currentNewsFilterOption() {
      const key = document.getElementById('newsFilterKey').value || 'category';
      return newsFilterOptions.find(item => item.value === key) || newsFilterOptions[0];
    }
    function updateNewsFilterValueOptions() {
      const valueNode = document.getElementById('newsFilterValue');
      const selected = currentNewsFilterOption();
      const current = valueNode.value || '';
      valueNode.innerHTML = selected.values.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      valueNode.value = selected.values.some(item => item.value === current) ? current : '';
    }
    function currentTalentFilterOption() {
      const key = document.getElementById('talentFilterKey').value || 'class';
      return talentFilterOptions.find(item => item.value === key) || talentFilterOptions[0];
    }
    function updateTalentFilterValueOptions() {
      const valueNode = document.getElementById('talentFilterValue');
      const selected = currentTalentFilterOption();
      const current = valueNode.value || '';
      valueNode.innerHTML = selected.values.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      valueNode.value = selected.values.some(item => item.value === current) ? current : '';
    }
    function currentGearFilterOption() {
      const key = document.getElementById('gearFilterKey').value || 'dropSource';
      return gearFilterOptions.find(item => item.value === key) || gearFilterOptions[0];
    }
    function updateGearFilterValueOptions() {
      const valueNode = document.getElementById('gearFilterValue');
      const selected = currentGearFilterOption();
      const current = valueNode.value || '';
      valueNode.innerHTML = selected.values.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      valueNode.value = selected.values.some(item => item.value === current) ? current : '';
      updateGearSourceInstanceOptions();
    }
    function gearSourceInstanceKind() {
      const selected = currentGearFilterOption();
      if (selected.value !== 'dropSource') return '';
      const sourceValue = document.getElementById('gearFilterValue').value.trim();
      if (sourceValue === '地下城') return 'dungeon';
      if (sourceValue === '团本') return 'raid';
      return '';
    }
    function updateGearSourceInstanceOptions() {
      const valueNode = document.getElementById('gearSourceInstanceValue');
      const kind = gearSourceInstanceKind();
      const options = kind ? (gearSourceInstanceOptions[kind] || []) : [];
      const current = valueNode.value || '';
      if (!options.length) {
        valueNode.hidden = true;
        valueNode.innerHTML = '';
        valueNode.value = '';
        return;
      }
      valueNode.hidden = false;
      const allLabel = kind === 'raid' ? '全部团本' : '全部地下城';
      const values = [{ value:'', label:allLabel }, ...options];
      valueNode.innerHTML = values.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      valueNode.value = values.some(item => item.value === current) ? current : '';
    }
    function currentGearTemplateFilterOption() {
      const key = document.getElementById('gearTemplateFilterKey').value || 'class';
      return gearTemplateFilterOptions.find(item => item.value === key) || gearTemplateFilterOptions[0];
    }
    function updateGearTemplateFilterValueOptions() {
      const valueNode = document.getElementById('gearTemplateFilterValue');
      const selected = currentGearTemplateFilterOption();
      const current = valueNode.value || '';
      valueNode.innerHTML = selected.values.map(item => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join('');
      valueNode.value = selected.values.some(item => item.value === current) ? current : '';
    }
    function applyRecordToolbarForDomain(domain) {
      const isNews = domain === 'news';
      const isTalent = domain === 'talents';
      const isGear = domain === 'gear';
      const isGearTemplate = domain === 'gear_templates';
      document.getElementById('genericToolbar').hidden = isNews || isTalent || isGear || isGearTemplate;
      document.getElementById('newsToolbar').hidden = !isNews;
      document.getElementById('talentToolbar').hidden = !isTalent;
      document.getElementById('gearToolbar').hidden = !isGear;
      document.getElementById('gearTemplateToolbar').hidden = !isGearTemplate;
      if (isNews) {
        updateNewsFilterValueOptions();
      } else if (isTalent) {
        updateTalentFilterValueOptions();
      } else if (isGear) {
        updateGearFilterValueOptions();
      } else if (isGearTemplate) {
        updateGearTemplateFilterValueOptions();
      } else {
        updateAdminGateFilterControls();
      }
    }
    function applyNewsFilterParams(params) {
      params.set('domain', 'news');
      const selected = currentNewsFilterOption();
      const value = document.getElementById('newsFilterValue').value.trim();
      if (!value) return;
      if (selected.queryField === 'status') {
        params.set('status', value);
        return;
      }
      params.set('field', selected.queryField);
      params.set('q', value);
    }
    function applyTalentFilterParams(params) {
      params.set('domain', 'talents');
      const selected = currentTalentFilterOption();
      const value = document.getElementById('talentFilterValue').value.trim();
      if (!value) return;
      if (selected.queryField === 'status') {
        params.set('status', value);
        return;
      }
      params.set('field', selected.queryField);
      params.set('q', value);
    }
    function applyGearFilterParams(params) {
      params.set('domain', 'gear');
      const selected = currentGearFilterOption();
      const value = document.getElementById('gearFilterValue').value.trim();
      if (!value) return;
      const sourceInstanceValue = document.getElementById('gearSourceInstanceValue').value.trim();
      if (selected.queryField === 'dropSource' && sourceInstanceValue && !document.getElementById('gearSourceInstanceValue').hidden) {
        params.set('field', 'sourceInstance');
        params.set('q', sourceInstanceValue);
        return;
      }
      params.set('field', selected.queryField);
      params.set('q', value);
    }
    function applyGearTemplateFilterParams(params) {
      params.set('domain', 'gear_templates');
      const selected = currentGearTemplateFilterOption();
      const value = document.getElementById('gearTemplateFilterValue').value.trim();
      if (!value) return;
      params.set('field', selected.queryField);
      params.set('q', value);
    }
    function adminGateShowsRecords() {
      return ['news', 'talents', 'gear', 'gearTemplates'].includes(currentAdminGateNav);
    }
    function applyAdminGateView() {
      const recordsNavs = ['news', 'talents', 'gear', 'gearTemplates'];
      const active = recordsNavs.includes(currentAdminGateNav) ? 'records' : currentAdminGateNav;
      document.querySelectorAll('[data-admin-gate-view]').forEach(node => {
        const key = node.dataset.adminGateView;
        const isActive = key === active;
        node.classList.toggle('active', isActive);
      });
      document.getElementById('recordsTitle').textContent = recordTitleByNavKey[currentAdminGateNav] || '全量记录';
      applyRecordToolbarForDomain(domainByNavKey[currentAdminGateNav] || document.getElementById('domain').value.trim());
    }
    function selectAdminGateNav(key) {
      currentAdminGateNav = key || 'overview';
      resetAdminGatePage();
      if (currentAdminGateNav === 'overview') {
        setAdminGateDomainFilter('');
        document.getElementById('status').value = '';
        document.getElementById('field').value = 'all';
        document.getElementById('q').value = '';
      } else {
        const domain = domainByNavKey[currentAdminGateNav] || '';
        document.getElementById('domain').value = domain;
        document.getElementById('field').value = 'all';
        document.getElementById('q').value = '';
      }
      applyRecordToolbarForDomain(domainByNavKey[currentAdminGateNav] || document.getElementById('domain').value.trim());
      applyAdminGateView();
      refreshAdminGates();
    }
    function renderSummary(data) {
      document.getElementById('summary').innerHTML = Object.entries(data.statusCounts || {}).map(([key, value]) => `<div class="card"><div>${escapeHtml(statusText(key))}</div><div class="metric">${escapeHtml(value)}</div></div>`).join('');
    }
    function renderModules(modules) {
      document.getElementById('modules').innerHTML = (modules || []).map(item => {
        const blockers = [...(item.blockers || []), ...(item.topBlockers || []).map(blocker => blocker.reason || blocker.code || '')].filter(Boolean).slice(0, 3);
        return `<div class="card"><h3>${escapeHtml(item.title || item.key)}</h3><div>${statusPill(item.status)}</div><p class="muted small">${escapeHtml(item.checkedAt || '')}</p><p class="muted small">${escapeHtml(blockers.join(' / ') || '暂无 blocker')}</p></div>`;
      }).join('') || '<div class="card muted">暂无模块状态。</div>';
    }
    function renderSystemHealth(data) {
      const health = data.sourceHealth || {};
      const modules = data.modules || [];
      document.getElementById('systemHealth').innerHTML = `<div class="grid"><div class="card"><h3>overallStatus</h3>${statusPill(data.overallStatus || health.overallStatus || '')}</div><div class="card"><h3>checkedAt</h3><p class="muted small">${escapeHtml(data.checkedAt || '')}</p></div><div class="card"><h3>schemaRevision</h3><p class="muted small">${escapeHtml(data.schemaRevision || '')}</p></div></div><table><tr><th>模块</th><th>状态</th><th>检查时间</th><th>Blockers</th></tr>${modules.map(item => `<tr><td>${escapeHtml(item.title || item.key)}</td><td>${statusPill(item.status)}</td><td>${escapeHtml(item.checkedAt || '')}</td><td>${escapeHtml([...(item.blockers || []), ...(item.topBlockers || []).map(blocker => blocker.reason || blocker.code || '')].filter(Boolean).slice(0, 5).join(' / '))}</td></tr>`).join('')}</table>`;
    }
    async function loadSummary() {
      const data = await api('/api/admin/gates/summary');
      renderAdminGateNav(data.navigation);
      renderSummary(data);
      renderModules(data.modules);
      renderSystemHealth(data);
      applyAdminGateView();
    }
    function newsPublicationCell(item) {
      const publication = item.publication || {};
      if (publication.state === 'published') {
        const publishedAt = publication.publishedAt || (item.rawSummary || {}).publishedAt || '';
        return `<div>${statusPill('published')}</div><p class="muted small">发布时间：${escapeHtml(publishedAt || '未记录')}</p>`;
      }
      const capturedAt = publication.capturedAt || item.checkedAt || '';
      const reason = publication.unpublishedReason || blockerText(item) || item.rawStatus || item.status || '';
      return `<div><span class="status blocked">未发布</span></div><p class="muted small">抓取时间：${escapeHtml(capturedAt || '未记录')}</p><p class="muted small">未发布原因：${escapeHtml(reason || '未记录')}</p>`;
    }
    function newsCategoryCell(item) {
      const category = item.articleCategory || {};
      const label = category.label || category.channel || category.category || '未分类';
      const meta = [category.category, ...(category.tags || [])].filter(Boolean).slice(0, 4).join(' / ');
      return `<span class="category-pill">${escapeHtml(label)}</span>${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}`;
    }
    function talentCategoryCell(item) {
      const category = item.talentCategory || {};
      const label = category.classLabel || category.label || category.classKey || '未知职业';
      const sourceLabel = category.sourceLabel || '社区来源';
      const meta = [category.specKey, category.heroKey].filter(Boolean).join(' / ');
      return `<span class="category-pill">${escapeHtml(label)}</span><br><span class="muted small">${escapeHtml(sourceLabel)}</span>${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}`;
    }
    function talentPublicationCell(item) {
      const publication = item.talentPublication || {};
      const state = publication.state === 'visible' ? 'verified' : 'blocked';
      const reason = publication.reason || '';
      const visibleAt = publication.visibleAt || '';
      return `<div>${statusPill(state)}</div><p class="muted small">${escapeHtml(publication.stateLabel || '未知')}</p><p class="muted small">${escapeHtml(publication.surface || '小程序')}</p>${visibleAt ? `<p class="muted small">可见时间：${escapeHtml(visibleAt)}</p>` : ''}${reason ? `<p class="muted small">${escapeHtml(reason)}</p>` : ''}`;
    }
    function talentBlockReasonCell(item) {
      const blockReason = item.talentBlockReason || {};
      const state = blockReason.state === 'clear' ? 'verified' : 'blocked';
      const reason = blockReason.reason || blockerText(item) || '未记录';
      return `<div>${statusPill(state)}</div><p class="muted small">${escapeHtml(blockReason.stateLabel || '')}</p><p class="muted small">${escapeHtml(reason)}</p>`;
    }
    function gearCategoryCell(item) {
      const category = item.gearCategory || {};
      const label = category.slotLabel || category.classLabel || category.label || '未分类';
      const sourceLabel = category.sourceLabel || category.sourceType || '';
      const variantMeta = [
        category.sourceType,
        category.difficultyKey,
        category.itemLevel ? `ilvl ${category.itemLevel}` : '',
      ].filter(Boolean).join(' / ');
      const templateMeta = [
        category.specKey,
        category.readySlotCount ? `${category.readySlotCount}/16 ready` : '',
        category.missingSlotCount ? `${category.missingSlotCount} missing` : '',
      ].filter(Boolean).join(' / ');
      const meta = item.targetType === 'community_gear_template' ? templateMeta : variantMeta;
      return `<span class="category-pill">${escapeHtml(label)}</span>${sourceLabel ? `<br><span class="muted small">${escapeHtml(sourceLabel)}</span>` : ''}${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}`;
    }
    function gearSlotCell(item) {
      const category = item.gearCategory || {};
      const label = category.slotLabel || category.slot || '未知部位';
      const meta = category.slot && category.slot !== label ? category.slot : '';
      return `<span class="category-pill">${escapeHtml(label)}</span>${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}`;
    }
    function gearSourceDetailWithoutInstance(detail, instance) {
      let value = String(detail || '').trim();
      const instanceValue = String(instance || '').trim();
      if (!value || !instanceValue) return value;
      if (value === instanceValue) return '';
      [' - ', ' – ', ' — ', ' / '].forEach(separator => {
        const suffix = `${separator}${instanceValue}`;
        const prefix = `${instanceValue}${separator}`;
        if (value.endsWith(suffix)) value = value.slice(0, -suffix.length).trim();
        if (value.startsWith(prefix)) value = value.slice(prefix.length).trim();
      });
      return value === instanceValue ? '' : value;
    }
    function gearVariantListCell(category) {
      const variants = Array.isArray(category.variants) ? category.variants : [];
      if (!variants.length) return '';
      return `<div class="variant-list">${variants.map(variant => {
        const label = variant.label || '';
        const itemLevel = variant.itemLevel ? `ilvl ${variant.itemLevel}` : '';
        const statusClass = String(variant.status || '').replace(/[^a-z0-9_-]/gi, '');
        const text = [label, itemLevel].filter(Boolean).join(' ') || variant.statusLabel || '变体';
        return `<span class="variant-chip ${escapeHtml(statusClass)}">${escapeHtml(text)}</span>`;
      }).join('')}</div>`;
    }
    function gearDropSourceCell(item) {
      const category = item.gearCategory || {};
      const label = category.sourceLabel || category.sourceType || item.sourceName || '未知来源';
      const sourceDetail = gearSourceDetailWithoutInstance(category.sourceDetailLabel, category.sourceInstanceLabel);
      const variantList = gearVariantListCell(category);
      const fallbackVariantMeta = variantList ? '' : [
        category.difficultyKey,
        category.itemLevel ? `ilvl ${category.itemLevel}` : '',
      ].filter(Boolean).join(' / ');
      const meta = [
        sourceDetail,
        fallbackVariantMeta,
      ].filter(Boolean).join(' / ');
      return `<span class="category-pill">${escapeHtml(label)}</span>${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}${variantList}`;
    }
    function gearItemTypeCell(item) {
      const category = item.gearCategory || {};
      const label = category.itemTypeLabel || '未标注分类';
      const raw = category.itemTypeRaw && category.itemTypeRaw !== label ? category.itemTypeRaw : '';
      const meta = [category.itemTypeGroupLabel, raw].filter(Boolean).join(' / ');
      return `<span class="category-pill">${escapeHtml(label)}</span>${meta ? `<br><span class="muted small">${escapeHtml(meta)}</span>` : ''}`;
    }
    function gearVisibilityCell(item) {
      const visibility = item.gearVisibility || {};
      const state = visibility.state === 'visible' ? 'verified' : 'blocked';
      const reason = visibility.reason || '';
      return `<div>${statusPill(state)}</div><p class="muted small">${escapeHtml(visibility.stateLabel || '未知')}</p>${reason ? `<p class="muted small">${escapeHtml(reason)}</p>` : ''}`;
    }
    function gearBlockReasonCell(item) {
      const blockReason = item.gearBlockReason || {};
      const state = blockReason.state === 'clear' ? 'verified' : 'blocked';
      const reason = blockReason.reason || blockerText(item) || '未记录';
      return `<div>${statusPill(state)}</div><p class="muted small">${escapeHtml(blockReason.stateLabel || '')}</p><p class="muted small">${escapeHtml(reason)}</p>`;
    }
    async function loadRecords() {
      const params = new URLSearchParams();
      const domainValue = domainByNavKey[currentAdminGateNav] || document.getElementById('domain').value.trim();
      if (domainValue === 'news') {
        applyNewsFilterParams(params);
      } else if (domainValue === 'talents') {
        applyTalentFilterParams(params);
      } else if (domainValue === 'gear') {
        applyGearFilterParams(params);
      } else if (domainValue === 'gear_templates') {
        applyGearTemplateFilterParams(params);
      } else {
        updateAdminGateFilterControls();
        ['domain','status','field','q'].forEach(id => { const value = document.getElementById(id).value.trim(); if (value) params.set(id, value); });
      }
      params.set('page', String(adminGateRecordsPage));
      params.set('pageSize', recordsPageSize());
      const data = await api(withQuery('/api/admin/gates/records', params));
      const isNewsRecords = domainValue === 'news';
      const isTalentRecords = domainValue === 'talents';
      const isGearRecords = domainValue === 'gear';
      const isGearTemplateRecords = domainValue === 'gear_templates';
      const hasCategoryColumn = isNewsRecords || isTalentRecords || isGearTemplateRecords;
      const header = isNewsRecords ? '<tr><th>模块</th><th>标题</th><th>分类</th><th>状态</th><th>发布情况</th><th>来源</th><th>Blockers</th></tr>' : (isTalentRecords ? '<tr><th>模块</th><th>标题</th><th>分类</th><th>状态</th><th>小程序可见</th><th>来源</th><th>阻断原因</th></tr>' : (isGearRecords ? '<tr><th>装备名称</th><th>部位</th><th>掉落来源</th><th>状态</th><th>装备分类</th><th>小程序可见</th><th>Block原因</th></tr>' : (isGearTemplateRecords ? '<tr><th>模块</th><th>装备模板</th><th>职业</th><th>状态</th><th>小程序是否可见</th><th>来源</th><th>Blockers</th></tr>' : (hasCategoryColumn ? '<tr><th>模块</th><th>标题</th><th>分类</th><th>状态</th><th>来源</th><th>Blockers</th></tr>' : '<tr><th>模块</th><th>标题</th><th>状态</th><th>来源</th><th>Blockers</th></tr>'))));
      const emptyColspan = isNewsRecords ? 7 : (isTalentRecords ? 7 : (isGearRecords ? 7 : (isGearTemplateRecords ? 7 : (hasCategoryColumn ? 6 : 5))));
      const rows = data.records.length ? data.records.map(item => {
        if (isGearRecords) {
          return `<tr><td>${escapeHtml(item.title)}</td><td>${gearSlotCell(item)}</td><td>${gearDropSourceCell(item)}</td><td>${statusPill(item.status)}</td><td>${gearItemTypeCell(item)}</td><td>${gearVisibilityCell(item)}</td><td>${gearBlockReasonCell(item)}</td></tr>`;
        }
        if (isGearTemplateRecords) {
          return `<tr><td>${escapeHtml(domainLabels[item.domain] || item.domain)}</td><td>${escapeHtml(item.title)}<br><span class="muted small">${escapeHtml(item.targetType)} / ${escapeHtml(item.targetId)}</span></td><td>${gearCategoryCell(item)}</td><td>${statusPill(item.status)}</td><td>${gearVisibilityCell(item)}</td><td>${escapeHtml(item.sourceName)}<br><span class="muted small">${escapeHtml(item.sourceUrl)}</span></td><td>${escapeHtml(blockerText(item))}</td></tr>`;
        }
        const publicationCell = isNewsRecords ? `<td>${newsPublicationCell(item)}</td>` : '';
        const categoryCell = hasCategoryColumn ? `<td>${isNewsRecords ? newsCategoryCell(item) : (isTalentRecords ? talentCategoryCell(item) : gearCategoryCell(item))}</td>` : '';
        const talentPublication = isTalentRecords ? `<td>${talentPublicationCell(item)}</td>` : '';
        const blockerCell = isTalentRecords ? talentBlockReasonCell(item) : escapeHtml(blockerText(item));
        return `<tr><td>${escapeHtml(domainLabels[item.domain] || item.domain)}</td><td>${escapeHtml(item.title)}<br><span class="muted small">${escapeHtml(item.targetType)} / ${escapeHtml(item.targetId)}</span></td>${categoryCell}<td>${statusPill(item.status)}</td>${publicationCell}${talentPublication}<td>${escapeHtml(item.sourceName)}<br><span class="muted small">${escapeHtml(item.sourceUrl)}</span></td><td>${blockerCell}</td></tr>`;
      }).join('') : `<tr><td colspan="${emptyColspan}" class="muted">当前过滤条件下没有记录。</td></tr>`;
      document.getElementById('records').innerHTML = header + rows;
      renderRecordsPagination(data.pagination);
    }
    async function loadQueue() {
      const data = await api('/api/admin/gates/queue?limit=80');
      document.getElementById('queue').innerHTML = data.items.map(item => `<div class="queue-item"><h3>${escapeHtml(item.title)}</h3><div>${statusPill(item.status)} <span class="muted small">${escapeHtml(severityText(item.severity))}</span></div><p class="muted small">${escapeHtml(item.targetDomain)} / ${escapeHtml(item.targetType)} / ${escapeHtml(item.targetId)}</p><p class="muted small">${escapeHtml(blockerText(item))}</p><p class="muted small">未解决诊断：${escapeHtml((item.diagnoses || []).length)}</p></div>`).join('') || '<div class="queue-item muted">暂无待诊断阻断项。</div>';
    }
    async function loadDiagnoses() {
      const data = await api('/api/admin/gates/diagnoses?limit=100');
      document.getElementById('diagnoses').innerHTML = '<table><tr><th>目标</th><th>状态</th><th>诊断</th><th>原因</th><th>时间</th></tr>' +
        (data.items.length ? data.items.map(item => `<tr><td>${escapeHtml(item.targetDomain)} / ${escapeHtml(item.targetType)} / ${escapeHtml(item.targetId)}</td><td>${statusPill(item.resolutionStatus)}<br>${statusPill(item.currentStatus)}</td><td>${escapeHtml(item.gapType || item.diagnosis)}</td><td>${escapeHtml(item.reason)}</td><td>${escapeHtml(item.createdAt)}</td></tr>`).join('') : '<tr><td colspan="5" class="muted">暂无诊断记录。</td></tr>') +
        '</table>';
    }
    async function refreshAdminGates() {
      try {
        clearAdminGateError();
        const tasks = [loadSummary()];
        if (adminGateShowsRecords()) tasks.push(loadRecords());
        if (currentAdminGateNav === 'queue') tasks.push(loadQueue());
        if (currentAdminGateNav === 'diagnoses') tasks.push(loadDiagnoses());
        await Promise.all(tasks);
        document.getElementById('adminGateMessage').textContent = '已加载线上门禁数据。';
      } catch (error) {
        showAdminGateError(error.message || String(error));
      }
    }
    document.getElementById('load').addEventListener('click', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('newsLoad').addEventListener('click', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('talentLoad').addEventListener('click', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('gearLoad').addEventListener('click', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('gearTemplateLoad').addEventListener('click', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('domain').addEventListener('change', () => {
      resetAdminGatePage();
      applyRecordToolbarForDomain(document.getElementById('domain').value.trim());
    });
    document.getElementById('status').addEventListener('change', resetAdminGatePage);
    document.getElementById('field').addEventListener('change', () => {
      resetAdminGatePage();
      updateAdminGateFilterControls();
    });
    document.getElementById('newsFilterKey').addEventListener('change', () => {
      resetAdminGatePage();
      updateNewsFilterValueOptions();
    });
    document.getElementById('newsFilterValue').addEventListener('change', resetAdminGatePage);
    document.getElementById('talentFilterKey').addEventListener('change', () => {
      resetAdminGatePage();
      updateTalentFilterValueOptions();
    });
    document.getElementById('talentFilterValue').addEventListener('change', resetAdminGatePage);
    document.getElementById('gearFilterKey').addEventListener('change', () => {
      resetAdminGatePage();
      updateGearFilterValueOptions();
    });
    document.getElementById('gearFilterValue').addEventListener('change', () => {
      resetAdminGatePage();
      updateGearSourceInstanceOptions();
    });
    document.getElementById('gearSourceInstanceValue').addEventListener('change', resetAdminGatePage);
    document.getElementById('gearTemplateFilterKey').addEventListener('change', () => {
      resetAdminGatePage();
      updateGearTemplateFilterValueOptions();
    });
    document.getElementById('gearTemplateFilterValue').addEventListener('change', resetAdminGatePage);
    document.getElementById('pageSize').addEventListener('change', () => {
      resetAdminGatePage();
      refreshAdminGates();
    });
    document.getElementById('prevPage').addEventListener('click', () => {
      if (adminGateRecordsPage <= 1) return;
      adminGateRecordsPage -= 1;
      refreshAdminGates();
    });
    document.getElementById('nextPage').addEventListener('click', () => {
      adminGateRecordsPage += 1;
      refreshAdminGates();
    });
    document.getElementById('nav').addEventListener('click', (event) => {
      const item = event.target.closest('[data-admin-gate-nav]');
      if (!item) return;
      selectAdminGateNav(item.dataset.adminGateNav);
    });
    document.getElementById('saveToken').addEventListener('click', () => {
      saveAdminToken();
      refreshAdminGates();
    });
    document.getElementById('clearToken').addEventListener('click', clearSavedAdminToken);
    document.getElementById('submitDiagnosis').addEventListener('click', async () => {
      try {
        const payload = JSON.parse(document.getElementById('diagnosisPayload').value || '{}');
        const result = await api('/api/admin/gates/diagnoses', { method:'POST', body: JSON.stringify(payload) });
        document.getElementById('diagnosisResult').textContent = `已记录：${result.id}`;
        await Promise.all([loadSummary(), loadRecords(), loadQueue(), loadDiagnoses()]);
      } catch (error) {
        document.getElementById('diagnosisResult').textContent = error.message || String(error);
        showAdminGateError(error.message || String(error));
      }
    });
    loadSavedAdminToken();
    updateAdminGateFilterControls();
    updateNewsFilterValueOptions();
    updateTalentFilterValueOptions();
    updateGearFilterValueOptions();
    updateGearTemplateFilterValueOptions();
    applyAdminGateView();
    if (token()) refreshAdminGates();
  </script>
</body>
</html>"""


def record_analytics_request(handler, payload):
    access_token = bearer_token_from_headers(handler.headers)
    user = authenticate_token(access_token) if access_token else None
    store = analytics_data_store()
    if store:
        return store.record_events(
            payload,
            user_id=user["id"] if user else None,
            client_id=handler.headers.get("X-Wow-Client-Id", ""),
            session_id=handler.headers.get("X-Wow-Session-Id", ""),
            platform=handler.headers.get("X-Wow-Platform", "miniprogram"),
        )
    if postgres_only_runtime_enabled():
        return {
            "ok": False,
            "status": "blocked",
            "errors": ["PostgreSQL analytics store is not available"],
        }
    init_db()
    with db_connection() as conn:
        return record_events(
            conn,
            payload,
            user_id=user["id"] if user else None,
            client_id=handler.headers.get("X-Wow-Client-Id", ""),
            session_id=handler.headers.get("X-Wow-Session-Id", ""),
            platform=handler.headers.get("X-Wow-Platform", "miniprogram"),
        )


def client_accepts_gzip(handler):
    return "gzip" in str(handler.headers.get("Accept-Encoding", "")).lower()


def json_response(handler, status, payload, *, extra_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    should_gzip = len(body) >= 1024 and client_accepts_gzip(handler)
    output = gzip.compress(body, compresslevel=6) if should_gzip else body
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        if should_gzip:
            handler.send_header("Content-Encoding", "gzip")
            handler.send_header("Vary", "Accept-Encoding")
        headers = extra_headers if isinstance(extra_headers, dict) else {}
        server_timing = headers.get("Server-Timing")
        if isinstance(server_timing, str) and server_timing:
            handler.send_header("Server-Timing", server_timing)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Wow-Client-Id, X-Wow-Session-Id, X-Wow-Platform")
        handler.send_header("Content-Length", str(len(output)))
        handler.end_headers()
        handler.wfile.write(output)
        return True
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        return False


def community_import_server_timing(timings):
    """Serialize fixed numeric timing fields without request or template content."""

    values = timings if isinstance(timings, dict) else {}

    def duration(key):
        try:
            return max(0.0, float(values.get(key) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    fields = (
        ("queue", "queueMs"),
        ("release_read", "releaseReadMs"),
        ("reconcile", "reconcileMs"),
        ("resolve", "resolveMs"),
        ("serialize", "serializeMs"),
    )
    parts = [f"{token};dur={duration(key):.3f}" for token, key in fields]
    parts.append(f"cache;dur={1.0 if values.get('cache') == 'hit' else 0.0:.3f}")
    return ", ".join(parts)


def text_response(handler, status, body, content_type="text/plain; charset=utf-8"):
    body_bytes = str(body or "").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)


def static_response(handler, path):
    if path in {"/websim", "/websim/"}:
        target = WEBSIM_DIR / "index.html"
    else:
        relative = path.removeprefix("/websim/").strip("/")
        target = WEBSIM_DIR / relative
    try:
        resolved = target.resolve()
        root = WEBSIM_DIR.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        json_response(handler, 404, {"error": "not_found"})
        return
    if not resolved.is_file():
        json_response(handler, 404, {"error": "not_found"})
        return
    content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
    if content_type.startswith("text/") or resolved.suffix in {".js", ".json", ".css"}:
        content_type = f"{content_type}; charset=utf-8"
    body = resolved.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw_body = handler.rfile.read(length)
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def websim_encoding_blocked_response(request_payload):
    encoding = request_payload.get("talentEncoding") if isinstance(request_payload, dict) else {}
    errors = encoding.get("errors") if isinstance(encoding, dict) else []
    error_text = "; ".join(str(item) for item in errors if item) or "WebSim talent encoding failed"
    return {
        "mode": "simcraft",
        "status": "blocked",
        "createdAt": utc_now(),
        "request": request_payload,
        "talentEncoding": encoding,
        "stages": [
            {
                "key": "websim_talent_encoding",
                "title": "WebSim talent encoding",
                "status": "failed",
                "executor": "backend",
                "summary": error_text,
            },
            {
                "key": "simc_execution",
                "title": "SimC execution",
                "status": "skipped",
                "executor": "simcraft",
                "summary": "SimC was not started because WebSim talents could not be encoded.",
                "metric": "",
            },
        ],
        "simulation": {
            "ran": False,
            "available": False,
            "summary": "",
            "error": error_text,
            "metrics": {},
        },
        "recommendations": [error_text],
    }


def websim_submission_blockers(request_payload):
    if not isinstance(request_payload, dict):
        return [{"key": "request", "summary": "WebSim request payload is invalid."}]
    build_context = request_payload.get("buildContext") if isinstance(request_payload.get("buildContext"), dict) else {}
    details = build_context.get("details") if isinstance(build_context.get("details"), dict) else {}
    talents = details.get("talents") if isinstance(details.get("talents"), dict) else {}
    simc_lines = talents.get("simcLines") if isinstance(talents.get("simcLines"), list) else []
    has_talents = bool(str(talents.get("importCode") or "").strip() or any(str(line or "").strip() for line in simc_lines))
    gear = details.get("gear") if isinstance(details.get("gear"), dict) else {}
    readiness = gear.get("readiness") if isinstance(gear.get("readiness"), dict) else {}
    try:
        ready_count = int(readiness.get("simcReadyCount") or 0)
    except (TypeError, ValueError):
        ready_count = 0
    missing_core_slots = readiness.get("missingCoreSlots") if isinstance(readiness.get("missingCoreSlots"), list) else []
    full_ready = bool(readiness.get("fullReady"))
    simc_items = gear.get("simcItems") if isinstance(gear.get("simcItems"), list) else []
    blockers = []
    if not has_talents:
        blockers.append({
            "key": "talents",
            "summary": "WebSim needs a talent import code or server-encoded SimC talent lines before submission.",
        })
    if not full_ready or ready_count < 1 or not simc_items:
        missing_text = f" Missing core slots: {', '.join(str(slot) for slot in missing_core_slots)}." if missing_core_slots else ""
        blockers.append({
            "key": "gear",
            "summary": "WebSim needs a complete core SimC-ready gear set before submission." + missing_text,
        })
    return blockers


def websim_submission_blocked_response(request_payload, blockers):
    blocker_list = blockers or [{"key": "request", "summary": "WebSim submission is not ready."}]
    missing_slots = [str(item.get("key") or "request") for item in blocker_list]
    summary = "; ".join(str(item.get("summary") or item.get("key") or "WebSim submission is not ready.") for item in blocker_list)
    return {
        "mode": "simcraft_agent",
        "status": "blocked",
        "createdAt": utc_now(),
        "request": request_payload,
        "talentEncoding": request_payload.get("talentEncoding") if isinstance(request_payload, dict) else {},
        "agent": {
            "status": "needs_clarification",
            "missingSlots": missing_slots,
            "filledSlots": {},
            "question": summary,
            "quickReplies": [],
            "draftProfile": "",
            "validation": {"passed": False, "errors": missing_slots, "warnings": []},
            "canSubmitTask": False,
        },
        "stages": [
            {
                "key": "websim_readiness",
                "title": "WebSim readiness",
                "status": "blocked",
                "executor": "backend",
                "summary": summary,
            },
            {
                "key": "simc_execution",
                "title": "SimC execution",
                "status": "skipped",
                "executor": "simcraft",
                "summary": "SimC was not started because WebSim gear or talents are not ready.",
                "metric": "",
            },
        ],
        "simulation": {
            "ran": False,
            "available": False,
            "summary": "",
            "error": summary,
            "metrics": {},
        },
        "recommendations": [summary],
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        if path == "/health":
            json_response(self, 200, {"ok": True, "service": "wow-backend"})
            return
        if path == "/admin/analytics":
            text_response(self, 200, analytics_admin_page(), "text/html; charset=utf-8")
            return
        if path == "/admin/gates":
            text_response(self, 200, admin_gates_page(), "text/html; charset=utf-8")
            return
        if path.startswith("/api/admin/gates/"):
            admin_gates_response(self, path, query)
            return
        if path.startswith("/api/admin/analytics/"):
            admin_analytics_response(self, path, query)
            return
        if path == "/websim" or path.startswith("/websim/"):
            static_response(self, path)
            return
        if path == "/api/data/health":
            include_audit = str(query.get("audit", [""])[0]).lower() in {"1", "true", "yes"}
            json_response(self, 200, build_data_health_payload(include_template_evidence_audit=include_audit))
            return
        if path == "/api/news/home":
            json_response(self, 200, build_home_payload())
            return
        if path == "/api/news/refresh-runs/latest":
            json_response(self, 200, latest_refresh_run_payload())
            return
        if path == "/api/builds/home":
            json_response(self, 200, get_builds_home_payload())
            return
        if path == "/api/builds/intel":
            json_response(self, 200, get_builds_intel_payload())
            return
        if path == "/api/builds/stat-weights/refresh-runs/latest":
            json_response(self, 200, runtime_stat_weight_latest_payload())
            return
        if path == "/api/builds/detail":
            query = parse_qs(urlparse(self.path).query)
            detail = get_builds_detail_payload(query.get("id", [""])[0])
            if detail:
                json_response(self, 200, detail)
            else:
                json_response(self, 404, {"error": "specialization_not_found"})
            return
        if path == "/api/game/season":
            json_response(self, 200, runtime_season_payload_with_raiderio())
            return
        if path == "/api/pve/home":
            json_response(self, 200, get_pve_home_payload())
            return
        if path == "/api/pve/module":
            query = parse_qs(urlparse(self.path).query)
            json_response(self, 200, get_pve_module_payload(query.get("key", ["teamLadder"])[0]))
            return
        if path == "/api/simulator/home":
            json_response(self, 200, build_simulator_home_payload())
            return
        if path == "/api/chickenbro/sessions":
            try:
                json_response(
                    self,
                    200,
                    get_chickenbro_session(
                        bearer_token_from_headers(self.headers),
                        query.get("id", query.get("sessionId", [""]))[0],
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except KeyError:
                json_response(self, 404, {"error": "chickenbro_session_not_found"})
            return
        if path == "/api/chickenbro/jobs":
            try:
                json_response(
                    self,
                    200,
                    get_chickenbro_job(
                        bearer_token_from_headers(self.headers),
                        query.get("id", query.get("jobId", [""]))[0],
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except KeyError:
                json_response(self, 404, {"error": "agent_job_not_found"})
            return
        if path == "/api/chickenbro/profiles":
            flat_query = {key: values[0] for key, values in query.items() if values}
            json_response(self, 200, get_chickenbro_profiles(flat_query))
            return
        if path == "/api/websim/bootstrap":
            json_response(self, 200, runtime_websim_bootstrap_payload())
            return
        if path == "/api/websim/assets":
            query = parse_qs(urlparse(self.path).query)
            filters = {
                "entityType": query.get("entityType", [""])[0],
                "entityId": query.get("entityId", [""])[0],
                "context": query.get("context", query.get("contextKey", [""]))[0],
                "status": query.get("status", [""])[0],
                "source": query.get("source", [""])[0],
                "limit": query.get("limit", [""])[0],
            }
            json_response(self, 200, runtime_websim_assets_payload(filters))
            return
        if path == "/api/talents/tree":
            json_response(
                self,
                200,
                runtime_websim_talents_payload(
                    query.get("class", query.get("classKey", ["mage"]))[0],
                    query.get("spec", query.get("specKey", ["arcane"]))[0],
                    query.get("hero", query.get("heroKey", [""]))[0],
                ),
            )
            return
        if path == "/api/websim/talents/import":
            query = parse_qs(urlparse(self.path).query)
            json_response(
                self,
                200,
                runtime_websim_talent_import_payload(
                    query.get("class", query.get("classKey", ["mage"]))[0],
                    query.get("spec", query.get("specKey", ["arcane"]))[0],
                    query.get("hero", query.get("heroKey", [""]))[0],
                ),
            )
            return
        if path == "/api/websim/talents":
            query = parse_qs(urlparse(self.path).query)
            json_response(
                self,
                200,
                runtime_websim_talents_payload(
                    query.get("class", query.get("classKey", ["mage"]))[0],
                    query.get("spec", query.get("specKey", ["arcane"]))[0],
                    query.get("hero", query.get("heroKey", [""]))[0],
                ),
            )
            return
        if path == "/api/websim/gear":
            query = parse_qs(urlparse(self.path).query)
            platform = str(self.headers.get("X-Wow-Platform", "")).lower()
            compact = (
                str(query.get("compact", [""])[0]).lower() in {"1", "true", "yes"}
                or platform == "miniprogram"
            )
            class_key = query.get("class", query.get("classKey", ["mage"]))[0]
            spec_key = query.get("spec", query.get("specKey", ["arcane"]))[0]
            mode = query.get("mode", [""])[0]
            slot = query.get("slot", [""])[0]

            def build_payload():
                payload = runtime_websim_gear_payload(
                    class_key,
                    spec_key,
                    compact=compact,
                    mode=mode,
                    slot=slot,
                )
                return websim_gear_payload_for_mode(payload, mode=mode, slot=slot)

            json_response(self, 200, run_websim_gear_build(build_payload))
            return
        if path == "/api/websim/loot":
            query = parse_qs(urlparse(self.path).query)
            filters = {
                "instanceId": query.get("instanceId", [""])[0],
                "encounterId": query.get("encounterId", [""])[0],
                "slot": query.get("slot", [""])[0],
                "q": query.get("q", [""])[0],
            }
            json_response(self, 200, runtime_websim_loot_payload(filters))
            return
        if path == "/api/simulator/tasks":
            query = parse_qs(urlparse(self.path).query)
            try:
                json_response(
                    self,
                    200,
                    list_simulator_tasks(
                        bearer_token_from_headers(self.headers),
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if path == "/api/me/build-templates":
            try:
                json_response(
                    self,
                    200,
                    list_user_build_templates(
                        bearer_token_from_headers(self.headers),
                        template_type=query.get("type", query.get("templateType", [""]))[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if path == "/api/simulator/task":
            query = parse_qs(urlparse(self.path).query)
            try:
                json_response(
                    self,
                    200,
                    get_simulator_task(
                        bearer_token_from_headers(self.headers),
                        query.get("id", [""])[0],
                        allow_guest=query.get("guest", ["0"])[0] == "1",
                        guest_id=query.get("guestId", [""])[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except KeyError:
                json_response(self, 404, {"error": "simulator_task_not_found"})
            return
        if path == "/api/news/article":
            query = parse_qs(urlparse(self.path).query)
            article = get_article_detail(query.get("id", [""])[0])
            if article:
                json_response(self, 200, article)
            else:
                json_response(self, 404, {"error": "article_not_found"})
            return
        if path == "/api/news/list":
            query = parse_qs(urlparse(self.path).query)
            payload = build_article_list_payload({
                "type": query.get("type", ["metric"])[0],
                "key": query.get("key", ["today"])[0],
                "value": query.get("value", [""])[0],
            })
            json_response(self, 200, payload)
            return
        json_response(self, 404, {"error": "not_found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/me/build-templates":
            try:
                json_response(
                    self,
                    200,
                    delete_user_build_template(
                        bearer_token_from_headers(self.headers),
                        query.get("id", query.get("templateId", [""]))[0],
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except KeyError:
                json_response(self, 404, {"error": "build_template_not_found"})
            return
        json_response(self, 404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/analytics/events":
            try:
                json_response(self, 200, record_analytics_request(self, read_json_body(self)))
            except Exception as error:
                json_response(self, 400, {"error": "analytics_record_failed", "message": str(error)})
            return
        if parsed.path == "/api/admin/analytics/rollup":
            if not analytics_admin_authorized(self.headers):
                json_response(self, 401, {"error": "unauthorized"})
                return
            payload = read_json_body(self)
            store = analytics_data_store()
            if store:
                json_response(self, 200, store.rollup_daily_metrics(payload.get("date", "")))
                return
            if postgres_only_runtime_enabled():
                json_response(
                    self,
                    503,
                    {
                        "error": "postgres_analytics_store_unavailable",
                        "message": "PostgreSQL analytics store is not available in PG-only runtime",
                    },
                )
                return
            init_db()
            with db_connection() as conn:
                json_response(self, 200, rollup_daily_metrics(conn, payload.get("date", "")))
            return
        if parsed.path == "/api/admin/gates/diagnoses":
            if not admin_authorized(self.headers):
                json_response(self, 401, {"error": "unauthorized"})
                return
            try:
                json_response(self, 200, create_admin_gate_diagnosis(read_json_body(self), actor="admin"))
            except ValueError as error:
                json_response(self, 400, {"error": "admin_gate_diagnosis_invalid", "message": str(error)})
            return
        if parsed.path == "/api/auth/wechat-login":
            try:
                json_response(self, 200, login_with_wechat_code(read_json_body(self).get("code", "")))
            except (ValueError, RuntimeError) as error:
                json_response(self, 400, {"error": "wechat_login_failed", "message": str(error)})
            return
        if parsed.path == "/api/me/profile":
            try:
                json_response(
                    self,
                    200,
                    update_user_profile(bearer_token_from_headers(self.headers), read_json_body(self)),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if parsed.path == "/api/me/build-templates":
            payload = read_json_body(self)
            try:
                access_token = bearer_token_from_headers(self.headers)
                template = save_user_build_template(
                    access_token,
                    payload.get("template") if isinstance(payload.get("template"), dict) else payload,
                )
                json_response(
                    self,
                    200,
                    {
                        "template": template,
                        "templates": list_user_build_templates(access_token)["templates"],
                        "schemaVersion": BUILD_TEMPLATE_SCHEMA_VERSION,
                    },
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except ValueError as error:
                json_response(self, 400, {"error": "invalid_build_template", "message": str(error)})
            return
        if parsed.path == "/api/chickenbro/sessions":
            payload = read_json_body(self)
            try:
                json_response(
                    self,
                    200,
                    create_chickenbro_session(
                        access_token=bearer_token_from_headers(self.headers),
                        guest_id=payload.get("guestId", ""),
                        metadata=payload,
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            return
        if parsed.path == "/api/chickenbro/messages":
            payload = read_json_body(self)
            try:
                json_response(
                    self,
                    200,
                    send_chickenbro_message(
                        payload,
                        access_token=bearer_token_from_headers(self.headers),
                    ),
                )
            except PermissionError:
                json_response(self, 401, {"error": "unauthorized"})
            except (KeyError, ValueError) as error:
                json_response(self, 400, {"error": "invalid_chickenbro_message", "message": str(error)})
            return
        if parsed.path == "/api/simulator/analyze":
            json_response(
                self,
                200,
                analyze_and_store_simulator_task(
                    read_json_body(self),
                    access_token=bearer_token_from_headers(self.headers),
                ),
            )
            return
        if parsed.path == "/api/websim/gear/resolve":
            http_status, envelope = resolve_selection_intent(
                read_json_body(self),
                store=cache_data_store(),
                simc_runtime_revision=current_gear_simc_runtime_revision(),
                request_id=f"gear-{uuid.uuid4().hex}",
            )
            json_response(self, http_status, envelope)
            return
        if parsed.path == "/api/websim/gear/community-import":
            payload = read_json_body(self)

            def build_import():
                return import_community_template(
                    payload,
                    store=cache_data_store(),
                    simc_runtime_revision=current_gear_simc_runtime_revision(),
                    request_id=f"gear-import-{uuid.uuid4().hex}",
                )

            (http_status, envelope, timings), queue_ms = run_websim_gear_build_with_queue(build_import)
            timings = dict(timings) if isinstance(timings, dict) else {}
            timings["queueMs"] = queue_ms
            json_response(
                self,
                http_status,
                envelope,
                extra_headers={"Server-Timing": community_import_server_timing(timings)},
            )
            return
        if parsed.path == "/api/websim/gear/stat-snapshots":
            http_status, envelope = get_or_start_stat_snapshot(
                read_json_body(self),
                authority_store=cache_data_store(),
                snapshot_store=gear_stat_snapshot_data_store(),
                simc_runtime_revision=current_gear_simc_runtime_revision(),
                request_id=f"gear-stat-{uuid.uuid4().hex}",
                client_id=self.headers.get("X-Wow-Client-Id", ""),
                now=utc_now(),
            )
            json_response(self, http_status, envelope)
            return
        if parsed.path == "/api/websim/profile":
            request_payload = read_json_body(self)
            if is_canonical_profile_request(request_payload):
                http_status, envelope = build_profile_from_selection_intent(
                    request_payload,
                    store=cache_data_store(),
                    simc_runtime_revision=current_gear_simc_runtime_revision(),
                    request_id=f"gear-profile-{uuid.uuid4().hex}",
                    profile_builder=build_websim_profile_response_from_resolved_snapshot,
                )
                json_response(self, http_status, envelope)
                return
            if postgres_only_runtime_enabled():
                json_response(
                    self,
                    200,
                    build_websim_profile_response(
                        request_payload,
                        conn=None,
                        talent_store=runtime_talent_api_store(),
                    ),
                )
                return
            init_db()
            with db_connection() as conn:
                json_response(self, 200, build_websim_profile_response(request_payload, conn=conn))
            return
        if parsed.path == "/api/websim/gear/stats":
            try:
                stat_store = gear_stat_snapshot_data_store()
                if stat_store is not None:
                    stat_store.record_legacy_request()
            except Exception:
                pass
            if postgres_only_runtime_enabled():
                json_response(self, 200, build_websim_gear_stats_response(read_json_body(self), conn=None))
                return
            init_db()
            with db_connection() as conn:
                json_response(self, 200, build_websim_gear_stats_response(read_json_body(self), conn=conn))
            return
        if parsed.path == "/api/talents/validate":
            payload = read_json_body(self)
            json_response(self, 200, runtime_validate_talent_api_payload(payload))
            return
        if parsed.path == "/api/talents/export":
            payload = read_json_body(self)
            json_response(self, 200, runtime_export_talent_api_payload(payload))
            return
        if parsed.path == "/api/talents/import":
            payload = read_json_body(self)
            json_response(self, 200, runtime_import_talent_api_payload(payload))
            return
        if parsed.path == "/api/websim/simulate":
            payload = read_json_body(self)
            if postgres_only_runtime_enabled():
                request_payload = build_websim_simulator_request(payload, guest_id=payload.get("guestId", ""), conn=None)
            else:
                init_db()
                with db_connection() as conn:
                    request_payload = build_websim_simulator_request(payload, guest_id=payload.get("guestId", ""), conn=conn)
            if request_payload.get("talentEncoding", {}).get("status") == "failed":
                json_response(self, 200, websim_encoding_blocked_response(request_payload))
                return
            blockers = websim_submission_blockers(request_payload)
            if blockers:
                json_response(self, 200, websim_submission_blocked_response(request_payload, blockers))
                return
            analysis = analyze_and_store_simulator_task(
                request_payload,
                access_token=bearer_token_from_headers(self.headers),
            )
            analysis = dict(analysis)
            analysis["talentEncoding"] = request_payload.get("talentEncoding")
            json_response(
                self,
                200,
                analysis,
            )
            return
        if parsed.path == "/api/news/refresh":
            query = parse_qs(parsed.query)
            mode = normalize_refresh_mode(query.get("mode", [""])[0])
            if not mode:
                json_response(self, 400, {"error": "invalid_refresh_mode", "allowedModes": sorted(PUBLIC_REFRESH_MODES)})
                return
            scope = (query.get("scope", ["full"])[0] or "full").strip().lower()
            if scope not in {"full", "queue"}:
                json_response(self, 400, {"error": "invalid_refresh_scope", "allowedScopes": ["full", "queue"]})
                return
            process_limit_override = None
            if query.get("limit", [""])[0]:
                try:
                    process_limit_override = int(query.get("limit", [""])[0])
                except (TypeError, ValueError):
                    json_response(self, 400, {"error": "invalid_refresh_limit"})
                    return
            try:
                if scope == "queue":
                    refresh_articles(
                        mode,
                        collector_enabled=False,
                        seed_enabled=False,
                        queue_enabled=True,
                        process_limit_override=process_limit_override,
                    )
                else:
                    refresh_articles(mode, process_limit_override=process_limit_override)
                json_response(self, 200, build_home_payload())
            except Exception as error:
                json_response(self, 500, {"error": "refresh_failed", "message": str(error)})
            return
        json_response(self, 404, {"error": "not_found"})

    def log_message(self, format, *args):
        print("%s - %s" % (self.log_date_time_string(), format % args))


def main():
    if not sqlite_runtime_disabled():
        init_db()
    latest_refresh_state()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"wow-backend listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
