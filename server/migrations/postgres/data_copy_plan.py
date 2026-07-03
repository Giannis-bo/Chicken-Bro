#!/usr/bin/env python3
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.migrations.postgres import identity_shadow_plan
from server.postgres_content_store import content_uuid


SCHEMA_REVISION = "postgres-data-copy-plan-v1"

SQL_COLUMNS = {
    "identity.users": ("id", "display_name", "status", "created_at", "updated_at"),
    "identity.user_identities": (
        "id",
        "user_id",
        "provider",
        "provider_subject",
        "profile_json",
        "created_at",
        "updated_at",
    ),
    "app.build_templates": (
        "id",
        "user_id",
        "template_type",
        "name",
        "payload_json",
        "metadata_json",
        "config_hash",
        "created_at",
        "updated_at",
    ),
    "app.simulator_tasks": (
        "id",
        "user_id",
        "mode",
        "status",
        "request_json",
        "analysis_json",
        "summary_json",
        "queued_at",
        "started_at",
        "finished_at",
        "attempt",
        "locked_by",
        "heartbeat_at",
        "cancel_requested",
        "last_error",
        "created_at",
        "updated_at",
    ),
    "app.chickenbro_sessions": (
        "id",
        "user_id",
        "title",
        "status",
        "context_json",
        "created_at",
        "updated_at",
    ),
    "app.chickenbro_messages": (
        "id",
        "session_id",
        "user_id",
        "role",
        "content",
        "payload_json",
        "evidence_refs_json",
        "created_at",
    ),
    "app.agent_jobs": (
        "id",
        "user_id",
        "session_id",
        "task_id",
        "job_type",
        "status",
        "request_json",
        "result_json",
        "queued_at",
        "started_at",
        "finished_at",
        "attempt",
        "locked_by",
        "heartbeat_at",
        "cancel_requested",
        "last_error",
        "created_at",
        "updated_at",
    ),
    "knowledge.user_context_summaries": (
        "id",
        "user_id",
        "context_type",
        "summary_json",
        "source_refs_json",
        "created_at",
        "updated_at",
    ),
    "content.sources": (
        "id",
        "source_key",
        "name",
        "url",
        "source_type",
        "status",
        "metadata_json",
        "created_at",
        "updated_at",
    ),
    "content.raw_articles": (
        "id",
        "source_id",
        "source_url",
        "title",
        "summary",
        "body",
        "payload_json",
        "discovered_at",
        "published_at",
        "updated_at",
    ),
    "content.article_evidence": (
        "id",
        "article_id",
        "evidence_type",
        "status",
        "payload_json",
        "created_at",
    ),
    "content.articles": (
        "id",
        "raw_article_id",
        "title",
        "summary",
        "body_zh",
        "channel",
        "category",
        "tags_json",
        "importance",
        "source_name",
        "source_url",
        "source_note",
        "published_at",
        "updated_at",
        "original_title",
        "translation_status",
        "content_status",
        "tag_items_json",
        "blocked_reason",
        "source_key",
        "source_tier",
        "license_status",
        "verification_status",
        "source_badges_json",
        "body_blocks_zh_json",
        "canonical_topic_id",
        "reading_meta_json",
        "translation_fidelity",
        "payload_json",
    ),
    "content.discovery_queue": (
        "id",
        "canonical_topic_id",
        "source_key",
        "source_name",
        "source_tier",
        "source_url",
        "original_title",
        "published_at",
        "status",
        "attempts",
        "last_error",
        "payload_json",
        "discovered_at",
        "updated_at",
        "processed_at",
    ),
    "content.refresh_runs": (
        "id",
        "refresh_mode",
        "refreshed_at",
        "accepted_count",
        "rejected_count",
        "message_json",
        "created_at",
    ),
    "cache.websim_sync_state": (
        "id",
        "state_json",
        "updated_at",
    ),
    "cache.websim_items": (
        "id",
        "name",
        "slot",
        "item_level",
        "payload_json",
        "source_status",
        "updated_at",
    ),
    "cache.websim_gear_sources": (
        "id",
        "item_id",
        "source_type",
        "source_key",
        "source_label",
        "instance_id",
        "encounter_id",
        "difficulty_key",
        "season_revision",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_gear_variants": (
        "id",
        "item_id",
        "variant_key",
        "readiness",
        "slot",
        "label",
        "source_type",
        "difficulty_key",
        "item_level",
        "simc_options_json",
        "status",
        "blockers_json",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_gear_mod_options": (
        "id",
        "variant_id",
        "option_key",
        "is_visible",
        "option_type",
        "name",
        "applicable_slots_json",
        "simc_options_json",
        "status",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_community_gear_templates": (
        "id",
        "class_key",
        "spec_key",
        "name",
        "source_key",
        "source_name",
        "source_url",
        "source_status",
        "status",
        "signature",
        "source_refs_json",
        "gear_items_json",
        "raw_string",
        "ready_slot_count",
        "missing_slots_json",
        "analysis_window",
        "payload_json",
        "updated_at",
        "expires_at",
        "scan_run_id",
    ),
    "cache.websim_talents": (
        "id",
        "class_key",
        "spec_key",
        "tree_id",
        "row_index",
        "col_index",
        "spell_id",
        "name",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_profile_presets": (
        "id",
        "class_key",
        "spec_key",
        "name",
        "profile",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_spell_details": (
        "id",
        "spell_id",
        "name",
        "description",
        "icon_url",
        "locale",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_community_talent_templates": (
        "id",
        "class_key",
        "spec_key",
        "source_key",
        "hero_key",
        "scenario_key",
        "name",
        "flow_label",
        "source_name",
        "source_url",
        "raw_import_code",
        "websim_export_code",
        "talent_state_json",
        "sample_count",
        "max_key_level",
        "analysis_window",
        "source_status",
        "status",
        "payload_json",
        "updated_at",
        "expires_at",
        "signature",
        "source_refs_json",
        "scan_run_id",
    ),
    "cache.websim_season_state": (
        "key",
        "season_id",
        "season_label",
        "season_revision",
        "locale",
        "data_status",
        "verified_at",
        "expires_at",
        "source_refs_json",
        "payload_json",
        "active",
        "updated_at",
    ),
    "cache.websim_season_dungeons": (
        "id",
        "season_id",
        "season_revision",
        "dungeon_id",
        "instance_id",
        "name",
        "short_name",
        "timer_seconds",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_instances": (
        "id",
        "name",
        "category",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_encounters": (
        "id",
        "instance_id",
        "name",
        "payload_json",
        "updated_at",
    ),
    "cache.websim_loot": (
        "id",
        "instance_id",
        "encounter_id",
        "item_id",
        "name",
        "slot",
        "quality",
        "icon_url",
        "payload_json",
        "updated_at",
    ),
    "cache.raiderio_cache": (
        "cache_key",
        "payload_json",
        "fetched_at",
        "expires_at",
    ),
    "cache.stat_weight_cache": (
        "cache_key",
        "payload_json",
        "computed_at",
        "source_status",
    ),
    "cache.websim_asset_registry": (
        "id",
        "entity_type",
        "entity_id",
        "context_key",
        "asset_type",
        "icon_url",
        "resolution_tier",
        "source",
        "status",
        "semantic_tags_json",
        "usage_json",
        "fallback_text",
        "payload_json",
        "updated_at",
    ),
}

JSON_COLUMNS = {
    "profile_json",
    "payload_json",
    "metadata_json",
    "request_json",
    "analysis_json",
    "summary_json",
    "context_json",
    "result_json",
    "evidence_refs_json",
    "source_refs_json",
    "tags_json",
    "tag_items_json",
    "source_badges_json",
    "body_blocks_zh_json",
    "reading_meta_json",
    "message_json",
    "state_json",
    "applicable_slots_json",
    "simc_options_json",
    "blockers_json",
    "talent_state_json",
    "semantic_tags_json",
    "usage_json",
    "gear_items_json",
    "missing_slots_json",
}


def safe_json_loads(raw, fallback):
    try:
        value = json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback
    return value if value is not None else fallback


def table_columns(conn, table_name):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def column_expr(columns, column_name, fallback_sql):
    if column_name in columns:
        return column_name
    return f"{fallback_sql} AS {column_name}"


def pg_uuid(table, sqlite_id):
    return identity_shadow_plan.stable_pg_uuid(table, str(sqlite_id))


def pg_content_uuid(table, key):
    return content_uuid(table, str(key))


def nullable_timestamp(value):
    return str(value or "").strip() or None


def optional_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def payload_item_level(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("itemLevel", "item_level", "previewItemLevel", "ilevel"):
        value = optional_int(payload.get(key))
        if value is not None:
            return value
    return None


def config_hash(*parts):
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def user_mapping(identity_plan):
    return {
        user["sqliteUserId"]: user["pgUserId"]
        for user in identity_plan["users"]
    }


def build_identity_tables(identity_plan):
    users = [
        {
            "id": user["pgUserId"],
            "display_name": user["displayName"],
            "status": user["status"],
            "created_at": user["createdAt"],
            "updated_at": user["updatedAt"],
        }
        for user in identity_plan["users"]
    ]
    user_by_id = {
        user["sqliteUserId"]: user
        for user in identity_plan["users"]
    }
    identities = []
    for identity in identity_plan["userIdentities"]:
        source_user = user_by_id[identity["sqliteUserId"]]
        identities.append(
            {
                "id": identity["pgIdentityId"],
                "user_id": identity["pgUserId"],
                "provider": identity["provider"],
                "provider_subject": identity["providerSubject"],
                "profile_json": identity["profile"],
                "created_at": source_user["createdAt"],
                "updated_at": source_user["updatedAt"],
            }
        )
    return users, identities


def build_template_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "user_build_templates") or not users:
        return []
    rows = conn.execute(
        """
        SELECT id, user_id, client_id, template_type, title, class_key, class_name,
               spec_key, spec_name, hero_key, hero_label, scenario_key, scenario_title,
               raw_string, simc_lines_json, status, status_label, source, metadata_json,
               schema_version, created_at, updated_at
        FROM user_build_templates
        ORDER BY user_id, updated_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[1])
        if not pg_user_id:
            continue
        simc_lines = safe_json_loads(row[14], [])
        metadata = safe_json_loads(row[18], {})
        payload = {
            "sqliteId": row[0],
            "clientId": row[2],
            "title": row[4],
            "classKey": row[5],
            "className": row[6],
            "specKey": row[7],
            "specName": row[8],
            "heroKey": row[9],
            "heroLabel": row[10],
            "scenarioKey": row[11],
            "scenarioTitle": row[12],
            "rawString": row[13],
            "simcLines": simc_lines,
            "status": row[15],
            "statusLabel": row[16],
            "source": row[17],
            "schemaVersion": row[19],
        }
        output.append(
            {
                "id": pg_uuid("app.build_templates", row[0]),
                "user_id": pg_user_id,
                "template_type": row[3],
                "name": row[4],
                "payload_json": payload,
                "metadata_json": metadata,
                "config_hash": config_hash(row[3], row[13]),
                "created_at": row[20],
                "updated_at": row[21],
            }
        )
    return output


def build_simulator_task_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "simulator_tasks") or not users:
        return []
    columns = table_columns(conn, "simulator_tasks")
    select_columns = (
        "id",
        "user_id",
        "mode",
        "status",
        column_expr(columns, "request_json", "'{}'"),
        column_expr(columns, "analysis_json", "'{}'"),
        column_expr(columns, "summary_json", "'{}'"),
        column_expr(columns, "queued_at", "created_at"),
        column_expr(columns, "started_at", "''"),
        column_expr(columns, "finished_at", "''"),
        column_expr(columns, "attempt", "0"),
        column_expr(columns, "locked_by", "''"),
        column_expr(columns, "heartbeat_at", "''"),
        column_expr(columns, "cancel_requested", "0"),
        column_expr(columns, "last_error", "''"),
        "created_at",
        "updated_at",
    )
    rows = conn.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM simulator_tasks
        ORDER BY user_id, created_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[1])
        if not pg_user_id:
            continue
        output.append(
            {
                "id": pg_uuid("app.simulator_tasks", row[0]),
                "user_id": pg_user_id,
                "mode": row[2],
                "status": row[3],
                "request_json": safe_json_loads(row[4], {}),
                "analysis_json": safe_json_loads(row[5], {}),
                "summary_json": safe_json_loads(row[6], {}),
                "queued_at": row[7] or row[15],
                "started_at": row[8] or None,
                "finished_at": row[9] or None,
                "attempt": row[10],
                "locked_by": row[11],
                "heartbeat_at": row[12] or None,
                "cancel_requested": bool(row[13]),
                "last_error": row[14],
                "created_at": row[15],
                "updated_at": row[16],
            }
        )
    return output


def evidence_refs_from_payload(payload):
    if not isinstance(payload, dict):
        return []
    refs = payload.get("evidenceRefs")
    if isinstance(refs, list):
        return refs
    coach = payload.get("coach")
    if isinstance(coach, dict) and isinstance(coach.get("evidenceRefs"), list):
        return coach["evidenceRefs"]
    return []


def build_chickenbro_session_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "chickenbro_sessions") or not users:
        return []
    rows = conn.execute(
        """
        SELECT id, user_id, title, product_phase, metadata_json, created_at, updated_at
        FROM chickenbro_sessions
        ORDER BY user_id, created_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[1])
        if not pg_user_id:
            continue
        output.append(
            {
                "id": pg_uuid("app.chickenbro_sessions", row[0]),
                "user_id": pg_user_id,
                "title": row[2],
                "status": "active",
                "context_json": {
                    "sqliteId": row[0],
                    "productPhase": row[3],
                    "metadata": safe_json_loads(row[4], {}),
                },
                "created_at": row[5],
                "updated_at": row[6],
            }
        )
    return output


def build_chickenbro_message_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "chickenbro_messages") or not users:
        return []
    rows = conn.execute(
        """
        SELECT id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
        FROM chickenbro_messages
        ORDER BY user_id, created_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[2])
        if not pg_user_id:
            continue
        payload = safe_json_loads(row[5], {})
        if row[6]:
            payload = {**payload, "sqliteAgentJobId": row[6]}
        output.append(
            {
                "id": pg_uuid("app.chickenbro_messages", row[0]),
                "session_id": pg_uuid("app.chickenbro_sessions", row[1]),
                "user_id": pg_user_id,
                "role": row[3],
                "content": row[4],
                "payload_json": payload,
                "evidence_refs_json": evidence_refs_from_payload(payload),
                "created_at": row[7],
            }
        )
    return output


def build_agent_job_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "agent_jobs") or not users:
        return []
    rows = conn.execute(
        """
        SELECT id, user_id, session_id, kind, status, request_json, bounded_context_json,
               result_json, error, created_at, updated_at, started_at, finished_at
        FROM agent_jobs
        ORDER BY user_id, created_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[1])
        if not pg_user_id:
            continue
        request = safe_json_loads(row[5], {})
        bounded_context = safe_json_loads(row[6], {})
        if bounded_context:
            request = {**request, "boundedContext": bounded_context}
        output.append(
            {
                "id": pg_uuid("app.agent_jobs", row[0]),
                "user_id": pg_user_id,
                "session_id": pg_uuid("app.chickenbro_sessions", row[2]),
                "task_id": None,
                "job_type": row[3],
                "status": row[4],
                "request_json": request,
                "result_json": safe_json_loads(row[7], {}),
                "queued_at": row[9],
                "started_at": row[11] or None,
                "finished_at": row[12] or None,
                "attempt": 0,
                "locked_by": "",
                "heartbeat_at": None,
                "cancel_requested": False,
                "last_error": row[8],
                "created_at": row[9],
                "updated_at": row[10],
            }
        )
    return output


def build_user_context_rows(conn, users):
    if not identity_shadow_plan.table_exists(conn, "chickenbro_user_profiles") or not users:
        return []
    rows = conn.execute(
        """
        SELECT user_id, profile_json, created_at, updated_at
        FROM chickenbro_user_profiles
        ORDER BY user_id
        """
    ).fetchall()
    output = []
    for row in rows:
        pg_user_id = users.get(row[0])
        if not pg_user_id:
            continue
        output.append(
            {
                "id": pg_uuid("knowledge.user_context_summaries", f"{row[0]}:chickenbro_user_profile"),
                "user_id": pg_user_id,
                "context_type": "chickenbro_user_profile",
                "summary_json": safe_json_loads(row[1], {}),
                "source_refs_json": [],
                "created_at": row[2],
                "updated_at": row[3],
            }
        )
    return output


def build_content_source_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_sources"):
        return []
    rows = conn.execute(
        """
        SELECT source_id, source_name, tier, fetch_mode, retail_only, license_status,
               rate_limit, enabled, hostnames_json, source_url, updated_at
        FROM news_sources
        ORDER BY source_id
        """
    ).fetchall()
    output = []
    for row in rows:
        metadata = {
            "tier": row[2],
            "retailOnly": bool(row[4]),
            "licenseStatus": row[5],
            "rateLimit": row[6],
            "hostnames": safe_json_loads(row[8], []),
        }
        output.append(
            {
                "id": pg_content_uuid("content.sources", row[0]),
                "source_key": row[0],
                "name": row[1],
                "url": row[9],
                "source_type": row[3],
                "status": "active" if row[7] else "disabled",
                "metadata_json": metadata,
                "created_at": row[10],
                "updated_at": row[10],
            }
        )
    return output


def build_raw_article_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_raw_articles"):
        return []
    rows = conn.execute(
        """
        SELECT id, source_id, source_name, source_tier, canonical_url, original_title,
               original_summary, original_body, body_blocks_json, published_at, fetched_at,
               fetch_error, license_status, verification_status, canonical_topic_id
        FROM news_raw_articles
        ORDER BY fetched_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        payload = {
            "sourceKey": row[1],
            "sourceName": row[2],
            "sourceTier": row[3],
            "bodyBlocks": safe_json_loads(row[8], []),
            "fetchError": row[11],
            "licenseStatus": row[12],
            "verificationStatus": row[13],
            "canonicalTopicId": row[14],
        }
        output.append(
            {
                "id": row[0],
                "source_id": pg_content_uuid("content.sources", row[1]) if row[1] else None,
                "source_url": row[4],
                "title": row[5],
                "summary": row[6],
                "body": row[7],
                "payload_json": payload,
                "discovered_at": row[10],
                "published_at": nullable_timestamp(row[9]),
                "updated_at": row[10],
            }
        )
    return output


def build_article_evidence_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_article_evidence"):
        return []
    rows = conn.execute(
        """
        SELECT id, article_id, canonical_topic_id, source_id, source_name, source_tier,
               evidence_url, verification_status, conflict_reason, checked_at
        FROM news_article_evidence
        ORDER BY checked_at, id
        """
    ).fetchall()
    output = []
    for row in rows:
        output.append(
            {
                "id": pg_uuid("content.article_evidence", row[0]),
                "article_id": row[1],
                "evidence_type": "source_verification",
                "status": row[7],
                "payload_json": {
                    "sqliteId": row[0],
                    "canonicalTopicId": row[2],
                    "sourceKey": row[3],
                    "sourceName": row[4],
                    "sourceTier": row[5],
                    "evidenceUrl": row[6],
                    "conflictReason": row[8],
                },
                "created_at": row[9],
            }
        )
    return output


def raw_article_ids(conn):
    if not identity_shadow_plan.table_exists(conn, "news_raw_articles"):
        return set()
    return {row[0] for row in conn.execute("SELECT id FROM news_raw_articles").fetchall()}


def build_public_article_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_articles"):
        return []
    columns = table_columns(conn, "news_articles")
    raw_ids = raw_article_ids(conn)
    select_columns = (
        "id",
        "title",
        "summary",
        "channel",
        "category",
        "tags_json",
        "importance",
        "source_name",
        "source_url",
        "published_at",
        "source_note",
        "updated_at",
        column_expr(columns, "body_zh", "''"),
        column_expr(columns, "original_title", "''"),
        column_expr(columns, "original_summary", "''"),
        column_expr(columns, "original_body", "''"),
        column_expr(columns, "translation_status", "''"),
        column_expr(columns, "content_status", "'ready'"),
        column_expr(columns, "tag_items_json", "'[]'"),
        column_expr(columns, "blocked_reason", "''"),
        column_expr(columns, "source_id", "''"),
        column_expr(columns, "source_tier", "''"),
        column_expr(columns, "license_status", "''"),
        column_expr(columns, "verification_status", "''"),
        column_expr(columns, "source_badges_json", "'[]'"),
        column_expr(columns, "body_blocks_zh_json", "'[]'"),
        column_expr(columns, "canonical_topic_id", "''"),
        column_expr(columns, "reading_meta_json", "'{}'"),
        column_expr(columns, "translation_fidelity", "''"),
    )
    rows = conn.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM news_articles
        ORDER BY importance DESC, published_at DESC, id
        """
    ).fetchall()
    output = []
    for row in rows:
        payload = {
            "sqliteId": row[0],
            "originalSummary": row[14],
            "originalBody": row[15],
        }
        output.append(
            {
                "id": row[0],
                "raw_article_id": row[0] if row[0] in raw_ids else None,
                "title": row[1],
                "summary": row[2],
                "body_zh": row[12],
                "channel": row[3],
                "category": row[4],
                "tags_json": safe_json_loads(row[5], []),
                "importance": row[6],
                "source_name": row[7],
                "source_url": row[8],
                "source_note": row[10],
                "published_at": nullable_timestamp(row[9]),
                "updated_at": row[11],
                "original_title": row[13],
                "translation_status": row[16],
                "content_status": row[17] or "ready",
                "tag_items_json": safe_json_loads(row[18], []),
                "blocked_reason": row[19],
                "source_key": row[20],
                "source_tier": row[21],
                "license_status": row[22],
                "verification_status": row[23],
                "source_badges_json": safe_json_loads(row[24], []),
                "body_blocks_zh_json": safe_json_loads(row[25], []),
                "canonical_topic_id": row[26],
                "reading_meta_json": safe_json_loads(row[27], {}),
                "translation_fidelity": row[28],
                "payload_json": payload,
            }
        )
    return output


def build_discovery_queue_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_discovery_queue"):
        return []
    rows = conn.execute(
        """
        SELECT id, canonical_topic_id, source_id, source_name, source_tier, source_url,
               original_title, published_at, status, attempts, last_error, payload_json,
               discovered_at, updated_at, processed_at
        FROM news_discovery_queue
        ORDER BY updated_at, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "canonical_topic_id": row[1],
            "source_key": row[2],
            "source_name": row[3],
            "source_tier": row[4],
            "source_url": row[5],
            "original_title": row[6],
            "published_at": nullable_timestamp(row[7]),
            "status": row[8],
            "attempts": row[9],
            "last_error": row[10],
            "payload_json": safe_json_loads(row[11], {}),
            "discovered_at": row[12],
            "updated_at": row[13],
            "processed_at": nullable_timestamp(row[14]),
        }
        for row in rows
    ]


def build_refresh_run_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "news_refresh_runs"):
        return []
    rows = conn.execute(
        """
        SELECT id, refresh_mode, refreshed_at, accepted_count, rejected_count, message
        FROM news_refresh_runs
        ORDER BY id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "refresh_mode": row[1],
            "refreshed_at": row[2],
            "accepted_count": row[3],
            "rejected_count": row[4],
            "message_json": safe_json_loads(row[5], {}),
            "created_at": row[2],
        }
        for row in rows
    ]


def build_websim_sync_state_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_sync_state"):
        return []
    rows = conn.execute(
        """
        SELECT key, value_json, updated_at
        FROM websim_sync_state
        ORDER BY key
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "state_json": safe_json_loads(row[1], {}),
            "updated_at": row[2],
        }
        for row in rows
    ]


def build_websim_item_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_items"):
        return []
    rows = conn.execute(
        """
        SELECT id, name, slot, quality, icon_url, payload_json, updated_at
        FROM websim_items
        ORDER BY id
        """
    ).fetchall()
    output = []
    for row in rows:
        payload = safe_json_loads(row[5], {})
        payload = dict(payload) if isinstance(payload, dict) else {}
        payload.setdefault("id", row[0])
        payload.setdefault("name", row[1])
        payload.setdefault("slot", row[2])
        payload.setdefault("quality", row[3])
        payload.setdefault("iconUrl", row[4])
        output.append(
            {
                "id": row[0],
                "name": row[1],
                "slot": row[2],
                "item_level": payload_item_level(payload),
                "payload_json": payload,
                "source_status": payload.get("sourceStatus") or payload.get("dataStatus") or "unknown",
                "updated_at": row[6],
            }
        )
    return output


def build_websim_gear_source_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_gear_sources"):
        return []
    rows = conn.execute(
        """
        SELECT id, item_id, source_type, source_label, instance_id, encounter_id,
               difficulty_key, season_revision, payload_json, updated_at
        FROM websim_gear_sources
        ORDER BY item_id, source_type, id
        """
    ).fetchall()
    return [
        {
            "id": pg_uuid("cache.websim_gear_sources", row[0]),
            "item_id": row[1],
            "source_type": row[2],
            "source_key": row[0],
            "source_label": row[3],
            "instance_id": row[4],
            "encounter_id": row[5],
            "difficulty_key": row[6],
            "season_revision": row[7],
            "payload_json": safe_json_loads(row[8], {}),
            "updated_at": row[9],
        }
        for row in rows
    ]


def build_websim_gear_variant_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_gear_variants"):
        return []
    rows = conn.execute(
        """
        SELECT id, item_id, slot, variant_key, label, source_type, difficulty_key,
               item_level, simc_options_json, status, blockers_json, payload_json, updated_at
        FROM websim_gear_variants
        ORDER BY item_id, variant_key,
                 CASE status
                    WHEN 'verified' THEN 0
                    WHEN 'partial' THEN 1
                    ELSE 2
                 END,
                 item_level DESC,
                 CASE source_type
                    WHEN 'tier_set' THEN 0
                    WHEN 'raid' THEN 1
                    WHEN 'dungeon' THEN 2
                    ELSE 3
                 END,
                 updated_at DESC,
                 id
        """
    ).fetchall()
    output = []
    seen_variant_keys = set()
    for row in rows:
        natural_key = (row[1], row[3])
        if natural_key in seen_variant_keys:
            continue
        seen_variant_keys.add(natural_key)
        output.append({
            "id": pg_uuid("cache.websim_gear_variants", row[0]),
            "item_id": row[1],
            "variant_key": row[3],
            "readiness": row[9] or "blocked",
            "slot": row[2],
            "label": row[4],
            "source_type": row[5],
            "difficulty_key": row[6],
            "item_level": optional_int(row[7]) or 0,
            "simc_options_json": safe_json_loads(row[8], {}),
            "status": row[9] or "blocked",
            "blockers_json": safe_json_loads(row[10], []),
            "payload_json": safe_json_loads(row[11], {}),
            "updated_at": row[12],
        })
    return output


def build_websim_gear_mod_option_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_gear_mod_options"):
        return []
    rows = conn.execute(
        """
        SELECT id, option_type, name, applicable_slots_json, simc_options_json,
               status, payload_json, updated_at
        FROM websim_gear_mod_options
        ORDER BY option_type, status DESC, id
        """
    ).fetchall()
    return [
        {
            "id": pg_uuid("cache.websim_gear_mod_options", row[0]),
            "variant_id": None,
            "option_key": row[0],
            "is_visible": str(row[5] or "").strip().lower() in {"verified", "ready"},
            "option_type": row[1],
            "name": row[2],
            "applicable_slots_json": safe_json_loads(row[3], []),
            "simc_options_json": safe_json_loads(row[4], {}),
            "status": row[5] or "blocked",
            "payload_json": safe_json_loads(row[6], {}),
            "updated_at": row[7],
        }
        for row in rows
    ]


def build_websim_community_gear_template_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_community_gear_templates"):
        return []
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, source_key, source_name, source_url,
               source_status, status, signature, source_refs_json, gear_items_json,
               raw_string, ready_slot_count, missing_slots_json, analysis_window,
               payload_json, updated_at, expires_at, scan_run_id
        FROM websim_community_gear_templates
        ORDER BY class_key, spec_key,
                 CASE source_key
                    WHEN 'default_template' THEN 1
                    ELSE 0
                 END,
                 status,
                 ready_slot_count DESC,
                 updated_at DESC,
                 id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "class_key": row[1],
            "spec_key": row[2],
            "name": row[3],
            "source_key": row[4],
            "source_name": row[5],
            "source_url": row[6],
            "source_status": row[7],
            "status": row[8],
            "signature": row[9],
            "source_refs_json": safe_json_loads(row[10], []),
            "gear_items_json": safe_json_loads(row[11], []),
            "raw_string": row[12] or "",
            "ready_slot_count": optional_int(row[13]) or 0,
            "missing_slots_json": safe_json_loads(row[14], []),
            "analysis_window": row[15] or "",
            "payload_json": safe_json_loads(row[16], {}),
            "updated_at": row[17],
            "expires_at": row[18],
            "scan_run_id": row[19] or "",
        }
        for row in rows
    ]


def build_websim_talent_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_talents"):
        return []
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, tree_id, row_index, col_index, spell_id,
               name, payload_json, updated_at
        FROM websim_talents
        ORDER BY class_key, spec_key, tree_id, row_index, col_index, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "class_key": row[1],
            "spec_key": row[2],
            "tree_id": row[3],
            "row_index": optional_int(row[4]) or 0,
            "col_index": optional_int(row[5]) or 0,
            "spell_id": optional_int(row[6]) or 0,
            "name": row[7],
            "payload_json": safe_json_loads(row[8], {}),
            "updated_at": row[9],
        }
        for row in rows
    ]


def build_websim_profile_preset_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_profile_presets"):
        return []
    rows = conn.execute(
        """
        SELECT id, class_key, spec_key, name, profile, payload_json, updated_at
        FROM websim_profile_presets
        ORDER BY class_key, spec_key, name, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "class_key": row[1],
            "spec_key": row[2],
            "name": row[3],
            "profile": row[4],
            "payload_json": safe_json_loads(row[5], {}),
            "updated_at": row[6],
        }
        for row in rows
    ]


def build_websim_spell_detail_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_spell_details"):
        return []
    rows = conn.execute(
        """
        SELECT id, spell_id, name, description, icon_url, locale, payload_json, updated_at
        FROM websim_spell_details
        ORDER BY spell_id, locale, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "spell_id": optional_int(row[1]) or 0,
            "name": row[2],
            "description": row[3],
            "icon_url": row[4],
            "locale": row[5],
            "payload_json": safe_json_loads(row[6], {}),
            "updated_at": row[7],
        }
        for row in rows
    ]


def build_websim_community_talent_template_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_community_talent_templates"):
        return []
    columns = table_columns(conn, "websim_community_talent_templates")
    rows = conn.execute(
        f"""
        SELECT id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
               source_key, source_name, source_url, raw_import_code, websim_export_code,
               talent_state_json, sample_count, max_key_level, analysis_window,
               source_status, status, payload_json, updated_at, expires_at,
               {column_expr(columns, "signature", "''")},
               {column_expr(columns, "source_refs_json", "'[]'")},
               {column_expr(columns, "scan_run_id", "''")}
        FROM websim_community_talent_templates
        ORDER BY class_key, spec_key, hero_key, source_key, id
        """
    ).fetchall()
    return [
        {
            "id": pg_uuid("cache.websim_community_talent_templates", row[0]),
            "class_key": row[1],
            "spec_key": row[2],
            "source_key": row[7],
            "hero_key": row[3],
            "scenario_key": row[4],
            "name": row[5],
            "flow_label": row[6],
            "source_name": row[8],
            "source_url": row[9],
            "raw_import_code": row[10],
            "websim_export_code": row[11],
            "talent_state_json": safe_json_loads(row[12], {}),
            "sample_count": optional_int(row[13]) or 0,
            "max_key_level": optional_int(row[14]) or 0,
            "analysis_window": row[15],
            "source_status": row[16],
            "status": row[17],
            "payload_json": safe_json_loads(row[18], {}),
            "updated_at": row[19],
            "expires_at": nullable_timestamp(row[20]),
            "signature": row[21],
            "source_refs_json": safe_json_loads(row[22], []),
            "scan_run_id": row[23],
        }
        for row in rows
    ]


def build_websim_season_state_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_season_state"):
        return []
    rows = conn.execute(
        """
        SELECT key, season_id, season_label, season_revision, locale, data_status,
               verified_at, expires_at, source_refs_json, payload_json, active, updated_at
        FROM websim_season_state
        ORDER BY key
        """
    ).fetchall()
    return [
        {
            "key": row[0],
            "season_id": row[1],
            "season_label": row[2],
            "season_revision": row[3],
            "locale": row[4],
            "data_status": row[5],
            "verified_at": nullable_timestamp(row[6]),
            "expires_at": nullable_timestamp(row[7]),
            "source_refs_json": safe_json_loads(row[8], []),
            "payload_json": safe_json_loads(row[9], {}),
            "active": bool(row[10]),
            "updated_at": row[11],
        }
        for row in rows
    ]


def build_websim_season_dungeon_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_season_dungeons"):
        return []
    rows = conn.execute(
        """
        SELECT id, season_id, season_revision, dungeon_id, instance_id, name,
               short_name, timer_seconds, payload_json, updated_at
        FROM websim_season_dungeons
        ORDER BY season_revision, name, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "season_id": row[1],
            "season_revision": row[2],
            "dungeon_id": row[3],
            "instance_id": row[4],
            "name": row[5],
            "short_name": row[6],
            "timer_seconds": row[7],
            "payload_json": safe_json_loads(row[8], {}),
            "updated_at": row[9],
        }
        for row in rows
    ]


def build_websim_instance_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_instances"):
        return []
    rows = conn.execute(
        """
        SELECT id, name, category, payload_json, updated_at
        FROM websim_instances
        ORDER BY name, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "payload_json": safe_json_loads(row[3], {}),
            "updated_at": row[4],
        }
        for row in rows
    ]


def build_websim_encounter_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_encounters"):
        return []
    rows = conn.execute(
        """
        SELECT id, instance_id, name, payload_json, updated_at
        FROM websim_encounters
        ORDER BY instance_id, name, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "instance_id": row[1],
            "name": row[2],
            "payload_json": safe_json_loads(row[3], {}),
            "updated_at": row[4],
        }
        for row in rows
    ]


def build_websim_loot_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_loot"):
        return []
    rows = conn.execute(
        """
        SELECT id, instance_id, encounter_id, item_id, name, slot, quality,
               icon_url, payload_json, updated_at
        FROM websim_loot
        ORDER BY instance_id, encounter_id, name, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "instance_id": row[1],
            "encounter_id": row[2],
            "item_id": row[3],
            "name": row[4],
            "slot": row[5],
            "quality": row[6],
            "icon_url": row[7],
            "payload_json": safe_json_loads(row[8], {}),
            "updated_at": row[9],
        }
        for row in rows
    ]


def build_raiderio_cache_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "raiderio_cache"):
        return []
    rows = conn.execute(
        """
        SELECT key, value_json, updated_at, expires_at, stale_at
        FROM raiderio_cache
        ORDER BY key
        """
    ).fetchall()
    output = []
    for row in rows:
        payload = safe_json_loads(row[1], {})
        if isinstance(payload, dict):
            payload.setdefault("staleAt", row[4])
        output.append(
            {
                "cache_key": row[0],
                "payload_json": payload,
                "fetched_at": row[2],
                "expires_at": nullable_timestamp(row[3]),
            }
        )
    return output


def build_stat_weight_cache_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "build_stat_weight_cache"):
        return []
    rows = conn.execute(
        """
        SELECT class_key, spec_key, scenario_key, status, value_json, updated_at
        FROM build_stat_weight_cache
        ORDER BY class_key, spec_key, scenario_key
        """
    ).fetchall()
    output = []
    for row in rows:
        class_key = str(row[0] or "").strip()
        spec_key = str(row[1] or "").strip()
        scenario_key = str(row[2] or "").strip()
        if not class_key or not spec_key or not scenario_key:
            continue
        payload = safe_json_loads(row[4], {})
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("classKey", class_key)
        payload.setdefault("specKey", spec_key)
        payload.setdefault("scenarioKey", scenario_key)
        payload.setdefault("sourceStatus", row[3] or "blocked")
        payload.setdefault("updatedAt", row[5])
        output.append(
            {
                "cache_key": f"{class_key}:{spec_key}:{scenario_key}",
                "payload_json": payload,
                "computed_at": row[5],
                "source_status": row[3] or payload.get("sourceStatus") or payload.get("status") or "blocked",
            }
        )
    return output


def build_websim_asset_registry_rows(conn):
    if not identity_shadow_plan.table_exists(conn, "websim_asset_registry"):
        return []
    rows = conn.execute(
        """
        SELECT id, entity_type, entity_id, context_key, asset_type, icon_url,
               resolution_tier, source, status, semantic_tags_json, usage_json,
               fallback_text, payload_json, updated_at
        FROM websim_asset_registry
        ORDER BY entity_type, entity_id, context_key, id
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "entity_type": row[1],
            "entity_id": row[2],
            "context_key": row[3],
            "asset_type": row[4],
            "icon_url": row[5],
            "resolution_tier": row[6],
            "source": row[7],
            "status": row[8],
            "semantic_tags_json": safe_json_loads(row[9], []),
            "usage_json": safe_json_loads(row[10], []),
            "fallback_text": row[11],
            "payload_json": safe_json_loads(row[12], {}),
            "updated_at": row[13],
        }
        for row in rows
    ]


def build_postgres_copy_plan(conn):
    identity_plan = identity_shadow_plan.build_identity_shadow_plan(conn)
    users = user_mapping(identity_plan)
    identity_users, identity_rows = build_identity_tables(identity_plan)
    tables = {
        "identity.users": identity_users,
        "identity.user_identities": identity_rows,
        "app.build_templates": build_template_rows(conn, users),
        "app.simulator_tasks": build_simulator_task_rows(conn, users),
        "app.chickenbro_sessions": build_chickenbro_session_rows(conn, users),
        "app.chickenbro_messages": build_chickenbro_message_rows(conn, users),
        "app.agent_jobs": build_agent_job_rows(conn, users),
        "knowledge.user_context_summaries": build_user_context_rows(conn, users),
        "content.sources": build_content_source_rows(conn),
        "content.raw_articles": build_raw_article_rows(conn),
        "content.article_evidence": build_article_evidence_rows(conn),
        "content.articles": build_public_article_rows(conn),
        "content.discovery_queue": build_discovery_queue_rows(conn),
        "content.refresh_runs": build_refresh_run_rows(conn),
        "cache.websim_sync_state": build_websim_sync_state_rows(conn),
        "cache.websim_items": build_websim_item_rows(conn),
        "cache.websim_gear_sources": build_websim_gear_source_rows(conn),
        "cache.websim_gear_variants": build_websim_gear_variant_rows(conn),
        "cache.websim_gear_mod_options": build_websim_gear_mod_option_rows(conn),
        "cache.websim_community_gear_templates": build_websim_community_gear_template_rows(conn),
        "cache.websim_talents": build_websim_talent_rows(conn),
        "cache.websim_profile_presets": build_websim_profile_preset_rows(conn),
        "cache.websim_spell_details": build_websim_spell_detail_rows(conn),
        "cache.websim_community_talent_templates": build_websim_community_talent_template_rows(conn),
        "cache.websim_season_state": build_websim_season_state_rows(conn),
        "cache.websim_season_dungeons": build_websim_season_dungeon_rows(conn),
        "cache.websim_instances": build_websim_instance_rows(conn),
        "cache.websim_encounters": build_websim_encounter_rows(conn),
        "cache.websim_loot": build_websim_loot_rows(conn),
        "cache.raiderio_cache": build_raiderio_cache_rows(conn),
        "cache.stat_weight_cache": build_stat_weight_cache_rows(conn),
        "cache.websim_asset_registry": build_websim_asset_registry_rows(conn),
    }
    rows_by_table = {table: len(rows) for table, rows in tables.items()}
    return {
        "schemaRevision": SCHEMA_REVISION,
        "identitySchemaRevision": identity_plan["schemaRevision"],
        "tables": tables,
        "skipped": identity_plan["skipped"],
        "totals": {
            "rowsByTable": rows_by_table,
            "totalRows": sum(rows_by_table.values()),
            "formalUsers": identity_plan["totals"]["formalUsers"],
            "guestUsers": identity_plan["totals"]["guestUsers"],
        },
        "errors": identity_plan["errors"],
    }


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sql_value(column, value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if column in JSON_COLUMNS:
        return f"{sql_literal(json.dumps(value, ensure_ascii=False, sort_keys=True))}::jsonb"
    return sql_literal(value)


def render_insert(table, row):
    columns = SQL_COLUMNS[table]
    values = ", ".join(sql_value(column, row.get(column)) for column in columns)
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values});"


def render_sql(plan):
    lines = [
        "-- Generated dry-run SQL. Review before use; do not run against production without owner approval.",
        "BEGIN;",
    ]
    for table in SQL_COLUMNS:
        for row in plan["tables"].get(table, []):
            lines.append(render_insert(table, row))
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a PostgreSQL dry-run copy plan from a SQLite WoW database.")
    parser.add_argument("--format", choices=("json", "sql"), default="json")
    parser.add_argument("sqlite_path")
    args = parser.parse_args(argv)

    with sqlite3.connect(f"file:{Path(args.sqlite_path)}?mode=ro", uri=True) as conn:
        plan = build_postgres_copy_plan(conn)
    if args.format == "sql":
        print(render_sql(plan), end="")
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
