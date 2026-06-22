#!/usr/bin/env python3
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
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
    from .simulator_payload import (
        analyze_simulator_request,
        build_simulator_home_payload,
        clean_simc_gear_items,
        normalize_simc_slot,
        warcraftlogs_credentials_state,
    )
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
    from .websim_payload import (
        build_websim_profile,
        build_websim_gear_stats_response,
        build_websim_profile_response,
        build_websim_simulator_request,
        community_talent_sync_state,
        enrich_build_gear_payload,
        ensure_websim_tables,
        gear_catalog_health_payload,
        export_talent_api_payload,
        get_active_season_payload,
        get_sync_state,
        get_websim_assets,
        get_websim_bootstrap,
        get_websim_gear,
        get_websim_loot,
        get_websim_talents,
        get_active_season_payload,
        import_talent_api_payload,
        encode_websim_talents,
        parse_websim_talent_export_code,
        validate_talent_api_payload,
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
    from simulator_payload import (
        analyze_simulator_request,
        build_simulator_home_payload,
        clean_simc_gear_items,
        normalize_simc_slot,
        warcraftlogs_credentials_state,
    )
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
    from websim_payload import (
        build_websim_profile,
        build_websim_gear_stats_response,
        build_websim_profile_response,
        build_websim_simulator_request,
        community_talent_sync_state,
        enrich_build_gear_payload,
        ensure_websim_tables,
        gear_catalog_health_payload,
        export_talent_api_payload,
        get_active_season_payload,
        get_sync_state,
        get_websim_assets,
        get_websim_bootstrap,
        get_websim_gear,
        get_websim_loot,
        get_websim_talents,
        get_active_season_payload,
        import_talent_api_payload,
        encode_websim_talents,
        parse_websim_talent_export_code,
        validate_talent_api_payload,
    )

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
WEBSIM_DIR = PROJECT_DIR / "websim"
SEED_PATH = BASE_DIR / "news" / "articles.seed.json"
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))
HOST = os.environ.get("WOW_NEWS_HOST", "0.0.0.0")
PORT = int(os.environ.get("WOW_NEWS_PORT", "8787"))
ENABLE_COLLECTORS = os.environ.get("WOW_NEWS_ENABLE_COLLECTORS", "0") == "1"
PUBLIC_REFRESH_MODES = {"scheduled"}
AUTH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
GUEST_SIMULATOR_OPENID = "guest-simulator"
BUILD_TEMPLATE_SCHEMA_VERSION = 1
VALID_BUILD_TEMPLATE_TYPES = {"talent", "gear"}
SCHEMA_MIGRATIONS = [
    ("core_schema_v1", "Core news, auth, simulator, WebSim, and analytics tables are initialized."),
    ("user_build_templates_v1", "Authenticated user build template sync table is initialized."),
    ("chickenbro_backend_v1", "Chickenbro sessions, messages, jobs, structured memory, and playstyle profiles are initialized."),
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


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES wechat_users(id)
            )
            """
        )
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


def parse_iso_datetime(value):
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


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
        SELECT payload_json
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
            articles.append(article)
    return articles


def queue_status_for_reviewed_article(article):
    if is_valid_article(article):
        return "published", ""
    reason = article.get("blockedReason") or article.get("verificationStatus") or "invalid_article"
    if article.get("sourceTier") == "official" and reason in RETRYABLE_NEWS_BLOCK_REASONS:
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


def refresh_articles(refresh_mode, collector_enabled=None):
    init_db()
    seed_articles = load_seed_articles()
    collected_articles = []
    discovered_articles = []
    duplicate_seed_articles = []
    discovered_collected_count = 0
    skipped_seed_duplicate_count = 0
    collector_errors = []
    collector_limit = collector_discovery_limit()
    process_limit = collector_process_limit()
    should_collect = ENABLE_COLLECTORS if collector_enabled is None else bool(collector_enabled)
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
    with db_connection() as conn:
        if should_collect and discovered_collected_count:
            enqueue_discovered_articles(conn, discovered_articles, refreshed_at)
            for article in duplicate_seed_articles:
                mark_queue_article(conn, article, "blocked", "duplicate_seed_source_translation", refreshed_at, increment_attempts=False)
        queued_articles = load_queued_articles(conn, process_limit) if should_collect else []

    accepted = []
    blocked = []
    processed = []
    rejected = 0
    for article in merge_articles(seed_articles, queued_articles):
        if article.get("contentStatus") == "ready":
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
    with db_connection() as conn:
        for article in processed:
            persist_news_raw_article(conn, article, refreshed_at)
            persist_news_evidence(conn, article, refreshed_at)
            if should_collect and article.get("id"):
                queue_status, queue_error = queue_status_for_reviewed_article(article)
                mark_queue_article(conn, article, queue_status, queue_error, refreshed_at)
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
        if accepted_ids and not should_collect:
            placeholders = ",".join("?" for _ in accepted_ids)
            conn.execute(f"DELETE FROM news_articles WHERE id NOT IN ({placeholders})", accepted_ids)
        audited_blocked = audit_existing_public_articles(conn)
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


def data_health_overall_status(components):
    statuses = [component.get("status") for component in components]
    if statuses and all(status == "verified" for status in statuses):
        return "verified"
    if any(status in {"verified", "partial", "stale", "pending_official_audit", "source_reference"} for status in statuses):
        return "partial"
    if any(status == "missing_credentials" for status in statuses):
        return "missing_credentials"
    return "blocked"


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


def news_health_component():
    latest = latest_refresh_run_payload()
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


def build_data_health_payload():
    init_db()
    components = [
        data_health_component("backend", "Backend service", "verified", checked_at=utc_now()),
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

        websim_state = get_sync_state(conn, "websim_sync") or {}
        websim_errors = websim_state.get("errors") if isinstance(websim_state.get("errors"), list) else []
        websim_simc = websim_state.get("simc") if isinstance(websim_state.get("simc"), dict) else {}
        websim_gear = websim_state.get("gearCatalog") if isinstance(websim_state.get("gearCatalog"), dict) else {}
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

        gear_catalog = gear_catalog_health_payload(conn)
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

        community = community_talent_sync_state(conn)
        components.append(
            data_health_component(
                "community_templates",
                "Community talent templates",
                community.get("sourceStatus"),
                checked_at=community.get("checkedAt") or "",
                details={
                    "templates": community.get("templates") or {},
                    "sources": community.get("sources") or {},
                    "templateRevision": community.get("templateRevision") or "",
                    "scanCoverage": community.get("scanCoverage") or {},
                    "dedupedCount": community.get("dedupedCount") or 0,
                    "hiddenDuplicateCount": community.get("hiddenDuplicateCount") or 0,
                    "wclTemplateSource": (community.get("sources") or {}).get("warcraftlogs") or {},
                },
                blockers=[
                    error
                    for source in (community.get("sources") or {}).values()
                    for error in (source.get("errors") or [])
                ][:8],
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


def safe_json_loads(value, fallback, label):
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


def public_build_template_from_row(row):
    if not row:
        return None
    simc_lines = safe_json_loads(row[13], [], f"build template simc lines {row[0]}")
    metadata = safe_json_loads(row[17], {}, f"build template metadata {row[0]}")
    if not isinstance(simc_lines, list):
        simc_lines = []
    if not isinstance(metadata, dict):
        metadata = {}
    return {
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


def list_user_build_templates(access_token, template_type=""):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized_type = clean_text(template_type, 32)
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
    return {
        "user": user,
        "schemaVersion": BUILD_TEMPLATE_SCHEMA_VERSION,
        "templates": [public_build_template_from_row(row) for row in rows],
    }


def save_user_build_template(access_token, record):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized = normalize_build_template_payload(record)
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
    return public_build_template_from_row(row)


def delete_user_build_template(access_token, template_id):
    user = authenticate_token(access_token)
    if not user:
        raise PermissionError("invalid auth token")
    normalized_id = clean_text(template_id, 128)
    if not normalized_id:
        raise KeyError("build template not found")
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
    "mythic_plus": {"label": "大秘境基准", "fightStyle": "DungeonSlice", "targets": 5, "durationSeconds": 360},
}

SIMCRAFT_TEMPLATE_ANALYSIS_TYPES = {"baseline", "stat_weights"}


def simcraft_template_record(source, template_type):
    record = source if isinstance(source, dict) else {}
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
    }


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


def parse_simcraft_template_gear_raw(raw_string):
    errors = []
    items = []
    seen_slots = set()
    for line in str(raw_string or "").splitlines():
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
    errors = []
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
    if gear_template["status"] != "complete":
        errors.append("gear template must be complete")

    with db_connection() as conn:
        talent_context, talent_errors = simcraft_template_talent_context(conn, talent_template)
    errors.extend(talent_errors)
    gear_items, gear_errors = parse_simcraft_template_gear_raw(gear_template.get("rawString"))
    errors.extend(gear_errors)

    scenario = SIMCRAFT_TEMPLATE_SCENARIOS.get(scenario_key) or SIMCRAFT_TEMPLATE_SCENARIOS["single"]
    simc_items = gear_items if not errors else []
    build_context = {
        "specId": f'{talent_template.get("classKey")}-{talent_template.get("specKey")}',
        "className": talent_template.get("className") or talent_template.get("classKey"),
        "specName": talent_template.get("specName") or talent_template.get("specKey"),
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


def analyze_and_store_simulator_task(request_data, access_token=""):
    request_payload = dict(request_data or {})
    if request_payload.get("mode") == "simcraft_template":
        request_payload = prepare_simcraft_template_request(request_payload)
    analysis = analyze_simulator_request(request_payload)
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
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO simulator_tasks (
                id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                user["id"],
                analysis.get("mode", ""),
                analysis.get("status", ""),
                json.dumps(stored_request, ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                now,
                now,
            ),
        )
    return analysis


def list_simulator_tasks(access_token, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        if allow_guest:
            return {"user": None, "tasks": []}
        raise PermissionError("invalid auth token")

    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, mode, status, request_json, analysis_json, created_at, updated_at
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
        tasks.append(
            {
                "taskId": row[0],
                "mode": row[1],
                "status": row[2],
                "question": question,
                "recommendations": analysis_payload.get("recommendations", []),
                "createdAt": row[5],
                "updatedAt": row[6],
            }
        )
    return {"user": user, "tasks": tasks}


def get_simulator_task(access_token, task_id, allow_guest=False, guest_id=""):
    user = authenticate_token(access_token)
    if not user and allow_guest:
        user = find_guest_simulator_user(guest_id)
    if not user:
        raise PermissionError("invalid auth token")

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
    question = (
        request_payload.get("question")
        or request_payload.get("prompt")
        or request_payload.get("message")
        or ""
    )
    return {
        "user": user,
        "task": {
            "taskId": row[0],
            "mode": row[1],
            "status": row[2],
            "question": question,
            "recommendations": analysis_payload.get("recommendations", []),
            "request": request_payload,
            "analysis": analysis_payload,
            "createdAt": row[5],
            "updatedAt": row[6],
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
        "summary": runtime.get("summary") or coach_pack.get("summary") or "",
        "priorityActions": coach_pack.get("priorityActions") or [],
        "limitations": list(runtime.get("limitations") or payload.get("limitations") or coach_pack.get("limitations") or []),
        "evidenceRefs": [str(ref) for ref in evidence_refs if ref],
        "allowedNumbers": allowed_numbers if isinstance(allowed_numbers, list) else [],
        "sourceCoverage": payload.get("sourceCoverage") if isinstance(payload.get("sourceCoverage"), dict) else {},
        "sampleWindow": payload.get("sampleWindow") if isinstance(payload.get("sampleWindow"), dict) else {},
    }


def build_chickenbro_bounded_context(message, context, user_profile=None):
    context = context if isinstance(context, dict) else {}
    topic = chickenbro_topic_scope(message, context)
    profiles = load_chickenbro_profiles(context)
    desired_region = normalize_chickenbro_region(context.get("region"))
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

    return {
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


def chickenbro_prompt_from_context(bounded_context):
    return json.dumps(
        {
            "instructions": [
                "你是炸鸡队长，只回答魔兽世界正式服和 PTR/Beta 相关问题。",
                "只能使用 boundedContext 中的事实、证据引用和 allowedNumbers。",
                "不要编造 DPS、排名、分位、日志发现或来源。",
                "输出 JSON：answer, confidence, priorityActions, evidenceRefs, limitations。",
            ],
            "boundedContext": bounded_context,
        },
        ensure_ascii=False,
        indent=2,
    )


def default_chickenbro_codex_runner(prompt, schema=None):
    if os.environ.get("WOW_CHICKENBRO_CODEX_ENABLED") != "1" or run_codex_job is None:
        return {"status": "skipped", "error": "chickenbro codex disabled"}
    return run_codex_job(prompt, schema=schema)


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
    return {
        "answer": answer,
        "confidence": str(payload.get("confidence") or "medium"),
        "priorityActions": payload.get("priorityActions") if isinstance(payload.get("priorityActions"), list) else [],
        "evidenceRefs": refs,
        "limitations": payload.get("limitations") if isinstance(payload.get("limitations"), list) else [],
    }


def deterministic_chickenbro_answer(bounded_context, answer_source="deterministic_fallback"):
    topic = bounded_context.get("topic") or {}
    if topic.get("status") != "in_scope":
        return {
            "answer": "炸鸡队长只回答魔兽世界正式服和 PTR/Beta 相关的玩法、机制、日志、构筑、装备、SimC、WCL、Raider.IO、插件和宏问题。这个问题不在范围内。",
            "answerSource": "deterministic_scope_refusal",
            "confidence": "blocked",
            "priorityActions": [],
            "evidenceRefs": [],
            "limitations": [topic.get("reason") or "out_of_scope"],
        }
    usable = bounded_context.get("usableProfiles") or []
    if not usable:
        return {
            "answer": "当前缺少已发布的专精打法画像，不能给出具体强度、排名或日志结论。可以先补充角色专精、场景、SimC 报告或 WCL 链接；后台会优先使用本地已同步证据，不在本次请求里实时抓取外部数据。",
            "answerSource": answer_source,
            "confidence": "low",
            "priorityActions": [
                {"title": "先补齐角色、专精、场景和可追踪证据。", "evidenceRefs": []}
            ],
            "evidenceRefs": [],
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
        "priorityActions": actions,
        "evidenceRefs": refs,
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
    if not bounded_context.get("usableProfiles"):
        answer = deterministic_chickenbro_answer(bounded_context)
        return {
            "answer": answer,
            "topic": bounded_context.get("topic"),
            "validation": {"status": "skipped", "reason": "missing_published_profile"},
            "codex": {"status": "skipped"},
        }

    runner = codex_runner or default_chickenbro_codex_runner
    prompt = chickenbro_prompt_from_context(bounded_context)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer", "confidence", "priorityActions", "evidenceRefs", "limitations"],
        "properties": {
            "answer": {"type": "string"},
            "confidence": {"type": "string"},
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


def send_chickenbro_message(payload, access_token="", codex_runner=None):
    payload = payload if isinstance(payload, dict) else {}
    message = clean_text(payload.get("message") or payload.get("prompt") or payload.get("question"), 4000)
    if not message:
        raise ValueError("chickenbro message is required")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    guest_id = payload.get("guestId") or context.get("guestId") or ""
    user = resolve_chickenbro_user(access_token, guest_id, create_guest=True)

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
            ORDER BY importance DESC, published_at DESC
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
                ORDER BY importance DESC, published_at DESC
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
        if not current or (article.get("importance", 0), article.get("publishedAt", "")) > (current.get("importance", 0), current.get("publishedAt", "")):
            by_key[key] = article
    return sorted(
        by_key.values(),
        key=lambda item: (item.get("importance", 0), item.get("publishedAt", "")),
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
    init_db()
    if not article_id:
        return None
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
    return "今日更新"


def filter_articles(articles, query):
    if query.get("type") == "channel":
        return [article for article in articles if article.get("channel") == query.get("value")]
    key = query.get("key")
    if key == "class-change":
        return [article for article in articles if "class-change" in article.get("tags", [])]
    if key == "ptr":
        return [article for article in articles if article.get("channel") == "测试服前瞻"]
    return articles


def build_article_list_payload(query):
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    filtered = filter_articles(articles, query)
    return {
        "title": article_list_title(query),
        "type": query.get("type", "metric"),
        "key": query.get("key", ""),
        "value": query.get("value", ""),
        "count": len(filtered),
        "articles": filtered,
    }


def build_home_payload():
    state = latest_refresh_state()
    articles = dedupe_articles([article for article in load_articles() if is_valid_article(article)])
    articles.sort(key=lambda item: (item.get("importance", 0), item.get("publishedAt", "")), reverse=True)
    return {
        "navTitle": "最新资讯",
        "heroNews": articles[:3],
        "metrics": [
            {"key": "today", "value": str(len(articles)), "label": "今日更新"},
            {"key": "class-change", "value": str(count_by_tag(articles, "class-change")), "label": "职业变动"},
            {"key": "ptr", "value": str(sum(1 for article in articles if article.get("channel") == "测试服前瞻")), "label": "测试服重点"},
        ],
        "channels": channels_with_counts(articles),
        "highlights": articles[:6],
        "lastRefreshedAt": state["lastRefreshedAt"],
        "refreshMode": state["refreshMode"],
    }


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


def get_builds_home_payload():
    payload = apply_runtime_season_gate(load_js_payload("server/builds/home-payload.js", "buildSpecializationHomePayload"), "builds_home")
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
    try:
        init_db()
        with db_connection() as conn:
            return enrich_raiderio_pve_module_payload(payload, get_raiderio_payload(conn))
    except Exception as error:
        if isinstance(payload, dict):
            payload["raiderioError"] = str(error)
        return payload


def runtime_season_payload():
    init_db()
    with db_connection() as conn:
        return get_active_season_payload(conn)


def runtime_season_payload_with_raiderio():
    init_db()
    with db_connection() as conn:
        return enrich_game_season_payload(get_active_season_payload(conn), get_raiderio_payload(conn))


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


def record_analytics_request(handler, payload):
    access_token = bearer_token_from_headers(handler.headers)
    user = authenticate_token(access_token) if access_token else None
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


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Wow-Client-Id, X-Wow-Session-Id, X-Wow-Platform")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


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
        if path.startswith("/api/admin/analytics/"):
            admin_analytics_response(self, path, query)
            return
        if path == "/websim" or path.startswith("/websim/"):
            static_response(self, path)
            return
        if path == "/api/data/health":
            json_response(self, 200, build_data_health_payload())
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
            init_db()
            with db_connection() as conn:
                json_response(self, 200, latest_stat_weight_run_payload(conn))
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
            init_db()
            with db_connection() as conn:
                json_response(self, 200, get_websim_bootstrap(conn))
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
            init_db()
            with db_connection() as conn:
                json_response(self, 200, get_websim_assets(conn, filters))
            return
        if path == "/api/talents/tree":
            init_db()
            with db_connection() as conn:
                json_response(
                    self,
                    200,
                    get_websim_talents(
                        conn,
                        query.get("class", query.get("classKey", ["mage"]))[0],
                        query.get("spec", query.get("specKey", ["arcane"]))[0],
                        query.get("hero", query.get("heroKey", [""]))[0],
                    ),
                )
            return
        if path == "/api/websim/talents":
            query = parse_qs(urlparse(self.path).query)
            init_db()
            with db_connection() as conn:
                json_response(
                    self,
                    200,
                    get_websim_talents(
                        conn,
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
            init_db()
            with db_connection() as conn:
                json_response(
                    self,
                    200,
                    get_websim_gear(
                        conn,
                        query.get("class", query.get("classKey", ["mage"]))[0],
                        query.get("spec", query.get("specKey", ["arcane"]))[0],
                        compact=compact,
                    ),
                )
            return
        if path == "/api/websim/loot":
            query = parse_qs(urlparse(self.path).query)
            filters = {
                "instanceId": query.get("instanceId", [""])[0],
                "encounterId": query.get("encounterId", [""])[0],
                "slot": query.get("slot", [""])[0],
                "q": query.get("q", [""])[0],
            }
            init_db()
            with db_connection() as conn:
                json_response(self, 200, get_websim_loot(conn, filters))
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
            init_db()
            with db_connection() as conn:
                json_response(self, 200, rollup_daily_metrics(conn, payload.get("date", "")))
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
        if parsed.path == "/api/websim/profile":
            init_db()
            with db_connection() as conn:
                json_response(self, 200, build_websim_profile_response(read_json_body(self), conn=conn))
            return
        if parsed.path == "/api/websim/gear/stats":
            init_db()
            with db_connection() as conn:
                json_response(self, 200, build_websim_gear_stats_response(read_json_body(self), conn=conn))
            return
        if parsed.path == "/api/talents/validate":
            payload = read_json_body(self)
            init_db()
            with db_connection() as conn:
                json_response(self, 200, validate_talent_api_payload(conn, payload))
            return
        if parsed.path == "/api/talents/export":
            payload = read_json_body(self)
            init_db()
            with db_connection() as conn:
                json_response(self, 200, export_talent_api_payload(conn, payload))
            return
        if parsed.path == "/api/talents/import":
            payload = read_json_body(self)
            init_db()
            with db_connection() as conn:
                json_response(self, 200, import_talent_api_payload(conn, payload))
            return
        if parsed.path == "/api/websim/simulate":
            payload = read_json_body(self)
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
            try:
                refresh_articles(mode)
                json_response(self, 200, build_home_payload())
            except Exception as error:
                json_response(self, 500, {"error": "refresh_failed", "message": str(error)})
            return
        json_response(self, 404, {"error": "not_found"})

    def log_message(self, format, *args):
        print("%s - %s" % (self.log_date_time_string(), format % args))


def main():
    init_db()
    latest_refresh_state()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"wow-backend listening on {HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
