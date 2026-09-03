#!/usr/bin/env python3
"""Transactional PostgreSQL adapter for the whitelist legacy migration.

DSNs and the approved Mini Program app context are read only from named
environment variables. Reports contain redacted migration/reconciliation
summaries and never serialize credentials or provider subjects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence
from urllib.parse import unquote, urlsplit

from server.migrations.product.migrate_legacy import (
    MIGRATION_REVISION,
    TARGET_NAMESPACE,
    MigrationDecision,
    MigrationError,
    MigrationReport,
    MigrationTarget,
    MigrationWatermark,
    canonical_json,
    content_hash,
    migrate_delta,
    migrate_full,
)
from server.migrations.product.reconcile_legacy import ReconciliationReport, reconcile


SAFE_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
DATABASE_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}\Z")
RESTORE_SCHEMAS = ("chat", "identity", "ops", "simc")

SOURCE_TABLES = (
    "identity.users",
    "identity.user_identities",
    "identity.auth_tokens",
    "identity.auth_sessions",
    "identity.web_login_sessions",
    "identity.prototype_sessions",
    "chat.conversations",
    "chat.messages",
    "chat.agent_runs",
    "simc.source_snapshots",
    "simc.simulation_jobs",
    "simc.simulation_attempts",
    "simc.simulation_results",
    "app.chickenbro_sessions",
    "app.chickenbro_messages",
    "app.agent_jobs",
    "app.simulator_tasks",
)
AUXILIARY_TABLES = ("app.chickenbro_agent_traces",)

PRIMARY_KEYS: Mapping[str, tuple[str, ...]] = {
    **{table: ("id",) for table in SOURCE_TABLES if table not in {
        "identity.auth_tokens",
        "identity.auth_sessions",
    }},
    "identity.auth_tokens": ("token_hash",),
    "identity.auth_sessions": ("token_hash",),
}

TARGET_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "identity.users": ("id", "display_name", "status", "created_at", "updated_at"),
    "identity.user_identities": (
        "id", "user_id", "provider", "app_context", "provider_subject", "union_id",
        "profile_json", "created_at", "updated_at",
    ),
    "chat.conversations": ("id", "user_id", "title", "status", "created_at", "updated_at"),
    "chat.messages": (
        "id", "conversation_id", "user_id", "role", "content", "client_message_id", "created_at",
    ),
    "chat.agent_runs": (
        "id", "user_id", "conversation_id", "user_message_id", "assistant_message_id", "status",
        "runtime_revision", "public_error_code", "started_at", "finished_at", "idempotency_key",
    ),
    "simc.source_snapshots": (
        "id", "user_id", "provider", "source_url", "source_key", "revision", "readiness",
        "snapshot_json", "provenance_json", "raw_sha256", "fetched_at", "created_at",
    ),
    "simc.simulation_jobs": (
        "id", "user_id", "snapshot_id", "scenario_hash", "compiler_revision", "runtime_revision",
        "idempotency_key", "status", "public_error_code", "created_at", "updated_at",
    ),
    "simc.simulation_attempts": (
        "id", "job_id", "user_id", "attempt_number", "worker_id", "started_at", "finished_at",
        "exit_code", "diagnostic",
    ),
    "simc.simulation_results": (
        "id", "job_id", "user_id", "profile_sha256", "result_json", "primary_metric_name",
        "primary_metric_value", "compiler_revision", "runtime_revision", "provenance_json", "created_at",
    ),
}

JSON_COLUMNS = frozenset({"profile_json", "snapshot_json", "provenance_json", "result_json"})
MUTABLE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "identity.users": ("display_name", "status", "created_at", "updated_at"),
    "identity.user_identities": ("union_id", "profile_json", "created_at", "updated_at"),
    "chat.conversations": ("title", "status", "created_at", "updated_at"),
}
IMMUTABLE_OWNER_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "identity.user_identities": ("user_id", "provider", "app_context", "provider_subject"),
    "chat.conversations": ("user_id",),
}


def _pick(row: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: deepcopy(row[key]) for key in keys if key in row}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_code(value: Any, fallback: str = "") -> str:
    candidate = str(value or "")
    return candidate if SAFE_CODE.fullmatch(candidate) else fallback


def _source_timestamp(row: Mapping[str, Any]) -> Any:
    for key in (
        "updated_at", "created_at", "finished_at", "fetched_at", "queued_at", "issued_at", "expires_at",
    ):
        if row.get(key) is not None:
            return row[key]
    raise ValueError("source row has no deterministic timestamp")


def _source_pk(table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    fields = PRIMARY_KEYS.get(table, ("id",))
    primary_key = {field: row[field] for field in fields if row.get(field) is not None}
    if len(primary_key) != len(fields):
        raise ValueError(f"source row is missing the primary key for {table}")
    return primary_key


def _normalize_identity(row: Mapping[str, Any], approved_app_context: str) -> dict[str, Any]:
    normalized = _pick(
        row,
        (
            "id", "user_id", "provider", "app_context", "provider_subject", "union_id",
            "profile_json", "created_at", "updated_at",
        ),
    )
    if normalized.get("provider") == "wechat_openid":
        normalized["provider"] = "wechat_mini"
        normalized["app_context"] = approved_app_context
        normalized.setdefault("union_id", None)
    elif normalized.get("provider") == "wechat_mini":
        if normalized.get("app_context") != approved_app_context:
            normalized["app_context"] = ""
    return normalized


def _normalize_message(row: Mapping[str, Any], *, direct: bool) -> dict[str, Any]:
    parent_key = "conversation_id" if direct else "session_id"
    normalized = _pick(
        row,
        ("id", parent_key, "user_id", "role", "content", "client_message_id", "created_at"),
    )
    if not direct and "client_message_id" not in normalized:
        client_message_id = _mapping(row.get("payload_json")).get("clientMessageId")
        if isinstance(client_message_id, str) and client_message_id:
            normalized["client_message_id"] = client_message_id
    return normalized


def _normalize_legacy_agent_jobs(
    jobs: Iterable[Mapping[str, Any]],
    traces: Iterable[Mapping[str, Any]],
    messages: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    traces_by_job: MutableMapping[str, list[Mapping[str, Any]]] = defaultdict(list)
    assistants_by_job: MutableMapping[str, list[Mapping[str, Any]]] = defaultdict(list)
    for trace in traces:
        traces_by_job[str(trace.get("agent_job_id") or "")].append(trace)
    for message in messages:
        if message.get("role") == "assistant" and message.get("agent_job_id"):
            assistants_by_job[str(message["agent_job_id"])].append(message)

    output: list[dict[str, Any]] = []
    for row in jobs:
        normalized = _pick(
            row,
            (
                "id", "user_id", "session_id", "status", "started_at", "finished_at",
                "created_at", "updated_at",
            ),
        )
        if row.get("job_type") != "chickenbro":
            normalized["status"] = "not_migrated"
            normalized["public_error_code"] = ""
            output.append(normalized)
            continue
        job_id = str(row.get("id") or "")
        matching_traces = traces_by_job.get(job_id, [])
        matching_assistants = assistants_by_job.get(job_id, [])
        if len(matching_traces) == 1:
            normalized["user_message_id"] = matching_traces[0].get("user_message_id")
            normalized["runtime_revision"] = matching_traces[0].get("runtime_version")
        if len(matching_assistants) == 1:
            normalized["assistant_message_id"] = matching_assistants[0].get("id")
        request = _mapping(row.get("request_json"))
        idempotency_key = request.get("clientMessageId")
        if isinstance(idempotency_key, str) and idempotency_key:
            normalized["idempotency_key"] = idempotency_key
        normalized["public_error_code"] = (
            "LEGACY_CHAT_FAILED" if row.get("status") == "failed" else ""
        )
        output.append(normalized)
    return output


def _normalize_simulator_task(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _pick(
        row,
        (
            "id", "user_id", "mode", "status", "request_json", "summary_json", "queued_at",
            "started_at", "finished_at", "attempt", "locked_by", "created_at", "updated_at",
        ),
    )
    explicit_exit = row.get("exit_code")
    if not isinstance(explicit_exit, int) or isinstance(explicit_exit, bool):
        explicit_exit = _mapping(row.get("analysis_json")).get("exitCode")
    if isinstance(explicit_exit, int) and not isinstance(explicit_exit, bool):
        normalized["exit_code"] = explicit_exit
    return normalized


def _normalize_direct_row(table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if table == "identity.users":
        return _pick(
            row,
            ("id", "display_name", "status", "account_kind", "created_at", "updated_at"),
        )
    if table == "chat.conversations":
        return _pick(row, ("id", "user_id", "title", "status", "created_at", "updated_at"))
    if table == "chat.messages":
        return _normalize_message(row, direct=True)
    if table == "chat.agent_runs":
        normalized = _pick(
            row,
            (
                "id", "user_id", "conversation_id", "user_message_id", "assistant_message_id", "status",
                "runtime_revision", "public_error_code", "started_at", "finished_at", "idempotency_key",
                "created_at", "updated_at",
            ),
        )
        normalized["public_error_code"] = _safe_code(
            normalized.get("public_error_code"),
            "LEGACY_CHAT_FAILED" if row.get("status") == "failed" else "",
        )
        return normalized
    if table == "simc.source_snapshots":
        return _pick(row, TARGET_COLUMNS[table])
    if table == "simc.simulation_jobs":
        normalized = _pick(row, TARGET_COLUMNS[table])
        normalized["public_error_code"] = _safe_code(
            normalized.get("public_error_code"),
            "SIMC_FAILED" if row.get("status") == "failed" else "",
        )
        return normalized
    if table == "simc.simulation_attempts":
        normalized = _pick(row, TARGET_COLUMNS[table])
        normalized["diagnostic"] = _safe_code(
            normalized.get("diagnostic"),
            "SIMC_DIAGNOSTIC_REDACTED" if normalized.get("diagnostic") else "",
        )
        return normalized
    if table == "simc.simulation_results":
        return _pick(row, TARGET_COLUMNS[table])
    if table in {
        "identity.auth_tokens",
        "identity.auth_sessions",
        "identity.web_login_sessions",
        "identity.prototype_sessions",
    }:
        return _pick(row, ("id", "user_id", "kind", "status", "created_at", "updated_at", "issued_at"))
    return deepcopy(dict(row))


def normalize_legacy_rows(
    rows_by_table: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    approved_app_context: str,
) -> list[dict[str, Any]]:
    """Create the minimal deterministic source envelopes used by the rule layer."""

    if (
        not isinstance(approved_app_context, str)
        or not 1 <= len(approved_app_context) <= 128
        or any(character.isspace() for character in approved_app_context)
    ):
        raise ValueError("approved_app_context must be a non-empty reviewed Mini Program AppID")

    legacy_messages = list(rows_by_table.get("app.chickenbro_messages", ()))
    derived_jobs = _normalize_legacy_agent_jobs(
        rows_by_table.get("app.agent_jobs", ()),
        rows_by_table.get("app.chickenbro_agent_traces", ()),
        legacy_messages,
    )
    derived_jobs_by_id = {str(row.get("id") or ""): row for row in derived_jobs}
    records: list[dict[str, Any]] = []
    for table in SOURCE_TABLES:
        for raw_row in rows_by_table.get(table, ()):
            row = deepcopy(dict(raw_row))
            if table == "identity.user_identities":
                normalized = _normalize_identity(row, approved_app_context)
            elif table == "app.chickenbro_sessions":
                normalized = _pick(row, ("id", "user_id", "title", "status", "created_at", "updated_at"))
            elif table == "app.chickenbro_messages":
                normalized = _normalize_message(row, direct=False)
            elif table == "app.agent_jobs":
                normalized = derived_jobs_by_id.get(str(row.get("id") or ""), {})
            elif table == "app.simulator_tasks":
                normalized = _normalize_simulator_task(row)
            else:
                normalized = _normalize_direct_row(table, row)
            records.append({
                "table": table,
                "pk": _source_pk(table, row),
                "updated_at": _source_timestamp(row),
                "row": normalized,
            })
    return records


def read_source_rows(connection: Any) -> dict[str, list[Mapping[str, Any]]]:
    output: dict[str, list[Mapping[str, Any]]] = {}
    for table in (*SOURCE_TABLES, *AUXILIARY_TABLES):
        exists = connection.execute("SELECT pg_catalog.to_regclass(%s)", (table,)).fetchone()
        if not exists or exists[0] is None:
            continue
        if table not in SOURCE_TABLES and table not in AUXILIARY_TABLES:
            raise AssertionError("unreviewed source table")
        cursor = connection.execute(f"SELECT to_jsonb(source_row) FROM {table} AS source_row")
        rows: list[Mapping[str, Any]] = []
        for item in cursor.fetchall():
            value = item[0]
            if isinstance(value, str):
                value = json.loads(value)
            if not isinstance(value, Mapping):
                raise ValueError(f"source table {table} returned a non-object row")
            rows.append(value)
        output[table] = rows
    return output


def _cursor_row(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    names = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
    return dict(zip(names, row, strict=True))


class PostgresMigrationTarget(MigrationTarget):
    def __init__(self, connection: Any):
        self.connection = connection

    def get(self, table: str, target_id: str) -> Mapping[str, Any] | None:
        columns = TARGET_COLUMNS.get(table)
        if columns is None:
            raise MigrationError(f"TARGET_TABLE_NOT_ALLOWED:{table}")
        cursor = self.connection.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE id = %s",
            (target_id,),
        )
        return _cursor_row(cursor)

    def has(self, table: str, target_id: str) -> bool:
        return self.get(table, target_id) is not None

    def rows(self, table: str) -> list[dict[str, Any]]:
        columns = TARGET_COLUMNS.get(table)
        if columns is None:
            if table != "ops.audit_events":
                raise MigrationError(f"TARGET_TABLE_NOT_ALLOWED:{table}")
            columns = ("id", "user_id", "event_type", "subject_key", "payload_json", "created_at")
        cursor = self.connection.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")
        names = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def upsert(self, table: str, row: Mapping[str, Any], *, mutable: bool) -> None:
        columns = TARGET_COLUMNS.get(table)
        if columns is None or set(row) != set(columns):
            raise MigrationError(f"TARGET_SHAPE_INVALID:{table}")
        existing = self.get(table, str(row["id"]))
        for key in IMMUTABLE_OWNER_COLUMNS.get(table, ()):
            if existing is not None and existing.get(key) != row.get(key):
                raise MigrationError(f"TARGET_OWNER_CONFLICT:{table}")

        placeholders = ["%s::jsonb" if column in JSON_COLUMNS else "%s" for column in columns]
        values = [canonical_json(row[column]) if column in JSON_COLUMNS else row[column] for column in columns]
        if mutable:
            updates = MUTABLE_COLUMNS.get(table)
            if updates is None:
                raise MigrationError(f"TARGET_MUTABILITY_INVALID:{table}")
            conflict = "DO UPDATE SET " + ", ".join(
                f"{column} = EXCLUDED.{column}" for column in updates
            )
        else:
            conflict = "DO NOTHING"
        self.connection.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT (id) {conflict}",
            tuple(values),
        )
        actual = self.get(table, str(row["id"]))
        if actual is None or content_hash(actual) != content_hash(row):
            raise MigrationError(f"TARGET_CONTENT_CONFLICT:{table}")

    def record_mapping(self, decision: MigrationDecision) -> None:
        if decision.status != "accepted" or not decision.target_id or not decision.target_table:
            raise MigrationError("ONLY_ACCEPTED_MAPPINGS_ARE_STORED")
        audit_id = str(uuid.uuid5(TARGET_NAMESPACE, f"audit:{decision.subject_key}"))
        payload = {
            "migrationRevision": MIGRATION_REVISION,
            "sourceTable": decision.source_table,
            "sourcePrimaryKeyHash": decision.source_primary_key_hash,
            "targetTable": decision.target_table,
            "targetId": decision.target_id,
            "generatedTargets": [
                {"table": table, "id": target_id}
                for table, target_id in decision.generated_targets
            ],
        }
        self.connection.execute(
            """
            INSERT INTO ops.audit_events (
                id, user_id, event_type, subject_key, payload_json
            ) VALUES (%s, NULL, 'legacy_migration.accepted', %s, %s::jsonb)
            ON CONFLICT (event_type, subject_key) DO NOTHING
            """,
            (audit_id, decision.subject_key, canonical_json(payload)),
        )
        cursor = self.connection.execute(
            """
            SELECT payload_json
            FROM ops.audit_events
            WHERE event_type = 'legacy_migration.accepted' AND subject_key = %s
            """,
            (decision.subject_key,),
        )
        stored = cursor.fetchone()
        stored_payload = stored[0] if stored else None
        if isinstance(stored_payload, str):
            stored_payload = json.loads(stored_payload)
        if stored_payload != payload:
            raise MigrationError("MIGRATION_MAPPING_CONFLICT")

    def has_mapping(self, subject_key: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM ops.audit_events
            WHERE event_type = 'legacy_migration.accepted' AND subject_key = %s
            """,
            (subject_key,),
        ).fetchone()
        return row is not None


def validate_local_app_dsn(dsn: str, expected_database: str) -> str:
    """Require the reviewed local wow_app/PGPASS transport identity."""

    if not isinstance(dsn, str) or any(character.isspace() for character in dsn):
        raise ValueError("database DSN is not the reviewed local wow_app identity")
    try:
        parsed = urlsplit(dsn)
        port = parsed.port
    except ValueError as error:
        raise ValueError("database DSN is not the reviewed local wow_app identity") from error
    name = unquote(parsed.path.lstrip("/"))
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.username != "wow_app"
        or parsed.password is not None
        or parsed.hostname != "127.0.0.1"
        or port != 5432
        or parsed.query
        or parsed.fragment
        or name != expected_database
        or DATABASE_NAME.fullmatch(name) is None
    ):
        raise ValueError("database DSN is not the reviewed local wow_app identity")
    return name


def _capture_relation_content_identity(
    connection: Any,
    relations: Iterable[tuple[str, str]],
    *,
    invalid_code: str,
) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for schema_name, relation_name in relations:
        if schema_name not in RESTORE_SCHEMAS or DATABASE_NAME.fullmatch(relation_name) is None:
            raise MigrationError(invalid_code)
        digest = hashlib.sha256()
        row_count = 0
        cursor = connection.execute(
            f'SELECT to_jsonb(row_value) FROM "{schema_name}"."{relation_name}" AS row_value '
            "ORDER BY to_jsonb(row_value)::text",
        )
        for (raw_row,) in cursor:
            row = json.loads(raw_row) if isinstance(raw_row, str) else raw_row
            encoded = canonical_json(row).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, byteorder="big"))
            digest.update(encoded)
            row_count += 1
        identities[f"{schema_name}.{relation_name}"] = {
            "rowCount": row_count,
            "contentHash": digest.hexdigest(),
        }
    return identities


def capture_restore_identity(connection: Any, expected_database: str) -> dict[str, Any]:
    """Read a deterministic schema/table/content identity without changing the database."""

    database_identity = connection.execute(
        "SELECT current_database(), current_setting('transaction_read_only')",
    ).fetchone()
    if database_identity != (expected_database, "on"):
        raise MigrationError("RESTORE_READ_ONLY_IDENTITY_MISMATCH")

    schema_identity_rows = connection.execute(
        """
        SELECT namespace.nspname, pg_catalog.pg_get_userbyid(namespace.nspowner),
               COALESCE((
                   SELECT string_agg(acl_item::text, E'\n' ORDER BY acl_item::text)
                   FROM unnest(namespace.nspacl) AS acl_item
               ), '')
        FROM pg_catalog.pg_namespace AS namespace
        WHERE namespace.nspname = ANY(%s)
        ORDER BY namespace.nspname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    relation_identity_rows = connection.execute(
        """
        SELECT namespace.nspname, relation.relname, relation.relkind,
               pg_catalog.pg_get_userbyid(relation.relowner),
               relation.relrowsecurity, relation.relforcerowsecurity,
               COALESCE((
                   SELECT string_agg(acl_item::text, E'\n' ORDER BY acl_item::text)
                   FROM unnest(relation.relacl) AS acl_item
               ), '')
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = ANY(%s)
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ORDER BY namespace.nspname, relation.relname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    schema_rows = connection.execute(
        """
        SELECT table_schema, table_name, column_name, ordinal_position, data_type,
               udt_schema, udt_name, is_nullable, column_default, is_identity
        FROM information_schema.columns
        WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    constraint_rows = connection.execute(
        """
        SELECT namespace.nspname, relation.relname, constraint_record.conname,
               constraint_record.contype,
               pg_catalog.pg_get_constraintdef(constraint_record.oid, true)
        FROM pg_catalog.pg_constraint AS constraint_record
        JOIN pg_catalog.pg_class AS relation ON relation.oid = constraint_record.conrelid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = ANY(%s)
        ORDER BY namespace.nspname, relation.relname, constraint_record.conname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    index_rows = connection.execute(
        """
        SELECT schemaname, tablename, indexname, indexdef
        FROM pg_catalog.pg_indexes
        WHERE schemaname = ANY(%s)
        ORDER BY schemaname, tablename, indexname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    function_rows = connection.execute(
        """
        SELECT namespace.nspname, procedure.proname,
               pg_catalog.pg_get_function_identity_arguments(procedure.oid),
               pg_catalog.pg_get_function_result(procedure.oid), procedure.prokind,
               procedure.provolatile, procedure.proparallel, procedure.prosecdef,
               pg_catalog.pg_get_userbyid(procedure.proowner),
               COALESCE((
                   SELECT string_agg(acl_item::text, E'\n' ORDER BY acl_item::text)
                   FROM unnest(procedure.proacl) AS acl_item
               ), ''),
               pg_catalog.pg_get_functiondef(procedure.oid)
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname = ANY(%s) AND procedure.prokind IN ('f', 'p')
        ORDER BY namespace.nspname, procedure.proname,
                 pg_catalog.pg_get_function_identity_arguments(procedure.oid)
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    trigger_rows = connection.execute(
        """
        SELECT namespace.nspname, relation.relname, trigger_record.tgname,
               pg_catalog.pg_get_triggerdef(trigger_record.oid, true)
        FROM pg_catalog.pg_trigger AS trigger_record
        JOIN pg_catalog.pg_class AS relation ON relation.oid = trigger_record.tgrelid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = ANY(%s) AND NOT trigger_record.tgisinternal
        ORDER BY namespace.nspname, relation.relname, trigger_record.tgname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    policy_rows = connection.execute(
        """
        SELECT schemaname, tablename, policyname, permissive, roles, cmd,
               qual, with_check
        FROM pg_catalog.pg_policies
        WHERE schemaname = ANY(%s)
        ORDER BY schemaname, tablename, policyname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    sequence_rows = connection.execute(
        """
        SELECT namespace.nspname, relation.relname,
               pg_catalog.pg_get_userbyid(relation.relowner),
               pg_catalog.format_type(sequence_record.seqtypid, NULL),
               sequence_record.seqstart, sequence_record.seqincrement,
               sequence_record.seqmin, sequence_record.seqmax,
               sequence_record.seqcache, sequence_record.seqcycle
        FROM pg_catalog.pg_sequence AS sequence_record
        JOIN pg_catalog.pg_class AS relation ON relation.oid = sequence_record.seqrelid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = ANY(%s)
        ORDER BY namespace.nspname, relation.relname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    sequences: dict[str, dict[str, Any]] = {}
    for sequence_row in sequence_rows:
        schema_name, sequence_name = sequence_row[:2]
        if schema_name not in RESTORE_SCHEMAS or DATABASE_NAME.fullmatch(sequence_name) is None:
            raise MigrationError("RESTORE_SEQUENCE_IDENTITY_INVALID")
        state = connection.execute(
            f'SELECT last_value, is_called FROM "{schema_name}"."{sequence_name}"',
        ).fetchone()
        if state is None or len(state) != 2 or not isinstance(state[1], bool):
            raise MigrationError("RESTORE_SEQUENCE_STATE_UNAVAILABLE")
        sequences[f"{schema_name}.{sequence_name}"] = {
            "definition": sequence_row[2:],
            "lastValue": state[0],
            "isCalled": state[1],
        }
    view_rows = connection.execute(
        """
        SELECT schemaname, viewname, definition
        FROM pg_catalog.pg_views
        WHERE schemaname = ANY(%s)
        ORDER BY schemaname, viewname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    materialized_view_rows = connection.execute(
        """
        SELECT schemaname, matviewname, matviewowner, tablespace,
               hasindexes, ispopulated, definition
        FROM pg_catalog.pg_matviews
        WHERE schemaname = ANY(%s)
        ORDER BY schemaname, matviewname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    type_rows = connection.execute(
        """
        SELECT namespace.nspname, type_record.typname, type_record.typtype,
               type_record.typcategory,
               pg_catalog.format_type(type_record.typelem, NULL),
               pg_catalog.format_type(type_record.typbasetype, NULL),
               type_record.typnotnull, type_record.typdefault,
               pg_catalog.pg_get_userbyid(type_record.typowner),
               COALESCE((
                   SELECT string_agg(acl_item::text, E'\n' ORDER BY acl_item::text)
                   FROM unnest(type_record.typacl) AS acl_item
               ), '')
        FROM pg_catalog.pg_type AS type_record
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
        WHERE namespace.nspname = ANY(%s)
          AND NOT (type_record.typcategory = 'A' AND type_record.typelem <> 0)
        ORDER BY namespace.nspname, type_record.typname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    domain_constraint_rows = connection.execute(
        """
        SELECT namespace.nspname, type_record.typname, constraint_record.conname,
               pg_catalog.pg_get_constraintdef(constraint_record.oid, true)
        FROM pg_catalog.pg_constraint AS constraint_record
        JOIN pg_catalog.pg_type AS type_record ON type_record.oid = constraint_record.contypid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
        WHERE namespace.nspname = ANY(%s) AND constraint_record.contypid <> 0
        ORDER BY namespace.nspname, type_record.typname, constraint_record.conname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    composite_attribute_rows = connection.execute(
        """
        SELECT namespace.nspname, type_record.typname, attribute_record.attname,
               attribute_record.attnum,
               pg_catalog.format_type(attribute_record.atttypid, attribute_record.atttypmod),
               attribute_record.attcollation::pg_catalog.regcollation::text
        FROM pg_catalog.pg_attribute AS attribute_record
        JOIN pg_catalog.pg_type AS type_record ON type_record.typrelid = attribute_record.attrelid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
        WHERE namespace.nspname = ANY(%s)
          AND type_record.typtype = 'c'
          AND attribute_record.attnum > 0
          AND NOT attribute_record.attisdropped
        ORDER BY namespace.nspname, type_record.typname, attribute_record.attnum
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    enum_rows = connection.execute(
        """
        SELECT namespace.nspname, type_record.typname,
               enum_record.enumsortorder, enum_record.enumlabel
        FROM pg_catalog.pg_enum AS enum_record
        JOIN pg_catalog.pg_type AS type_record ON type_record.oid = enum_record.enumtypid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
        WHERE namespace.nspname = ANY(%s)
        ORDER BY namespace.nspname, type_record.typname, enum_record.enumsortorder
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    range_rows = connection.execute(
        """
        SELECT namespace.nspname, type_record.typname,
               pg_catalog.format_type(range_record.rngsubtype, NULL),
               range_record.rngcollation::pg_catalog.regcollation::text,
               range_record.rngcanonical::pg_catalog.regprocedure::text,
               range_record.rngsubdiff::pg_catalog.regprocedure::text,
               pg_catalog.format_type(range_record.rngmultitypid, NULL)
        FROM pg_catalog.pg_range AS range_record
        JOIN pg_catalog.pg_type AS type_record ON type_record.oid = range_record.rngtypid
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = type_record.typnamespace
        WHERE namespace.nspname = ANY(%s)
        ORDER BY namespace.nspname, type_record.typname
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()
    table_rows = connection.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE' AND table_schema = ANY(%s)
        ORDER BY table_schema, table_name
        """,
        (list(RESTORE_SCHEMAS),),
    ).fetchall()

    tables = _capture_relation_content_identity(
        connection,
        table_rows,
        invalid_code="RESTORE_TABLE_IDENTITY_INVALID",
    )
    populated_materialized_views: list[tuple[str, str]] = []
    materialized_views: dict[str, dict[str, Any]] = {}
    for materialized_view_row in materialized_view_rows:
        schema_name, view_name = materialized_view_row[:2]
        is_populated = materialized_view_row[5]
        if (
            schema_name not in RESTORE_SCHEMAS
            or DATABASE_NAME.fullmatch(view_name) is None
            or not isinstance(is_populated, bool)
        ):
            raise MigrationError("RESTORE_MATERIALIZED_VIEW_IDENTITY_INVALID")
        key = f"{schema_name}.{view_name}"
        if is_populated:
            populated_materialized_views.append((schema_name, view_name))
        else:
            materialized_views[key] = {
                "rowCount": None,
                "contentHash": None,
                "isPopulated": False,
            }
    for key, identity in _capture_relation_content_identity(
        connection,
        populated_materialized_views,
        invalid_code="RESTORE_MATERIALIZED_VIEW_IDENTITY_INVALID",
    ).items():
        materialized_views[key] = {**identity, "isPopulated": True}

    return {
        "schemaHash": content_hash({
            "schemas": schema_identity_rows,
            "relations": relation_identity_rows,
            "columns": schema_rows,
            "constraints": constraint_rows,
            "indexes": index_rows,
            "functions": function_rows,
            "triggers": trigger_rows,
            "policies": policy_rows,
            "views": view_rows,
            "materializedViews": materialized_view_rows,
            "types": type_rows,
            "domainConstraints": domain_constraint_rows,
            "compositeAttributes": composite_attribute_rows,
            "enumLabels": enum_rows,
            "ranges": range_rows,
        }),
        "sequences": sequences,
        "materializedViews": materialized_views,
        "tables": tables,
    }


def compare_restore_identities(
    candidate: Mapping[str, Any], restored: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless an independently restored database is semantically equal."""

    candidate_hash = content_hash(candidate)
    restored_hash = content_hash(restored)
    if candidate_hash != restored_hash:
        raise MigrationError("RESTORE_DATABASE_IDENTITY_MISMATCH")
    return {
        "status": "matched",
        "identitySha256": candidate_hash,
        "schemaSha256": str(candidate.get("schemaHash") or ""),
        "tableCount": len(candidate.get("tables") or {}),
        "rowCount": sum(
            int(table.get("rowCount") or 0)
            for table in (candidate.get("tables") or {}).values()
        ),
    }


def _timestamp_text(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    report_path = Path(path)
    if not report_path.is_absolute() or report_path.exists() or report_path.is_symlink():
        raise ValueError("report path must be a new absolute file")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        output.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the redacted PostgreSQL legacy product migration")
    parser.add_argument("--mode", choices=("full", "delta", "verify-restore"), required=True)
    parser.add_argument("--source-dsn-env", default="CHICKENBRO_LEGACY_SOURCE_DATABASE_URL")
    parser.add_argument("--target-dsn-env", default="WOW_DATABASE_URL")
    parser.add_argument("--approved-app-context-env", default="WOW_MIGRATION_WECHAT_APP_CONTEXT")
    parser.add_argument("--expected-source-database", default="wow_test")
    parser.add_argument("--expected-target-database", required=True)
    parser.add_argument("--restore-dsn-env", default="CHICKENBRO_RESTORE_DATABASE_URL")
    parser.add_argument("--expected-restore-database")
    parser.add_argument("--from-watermark")
    parser.add_argument("--report-path", type=Path, required=True)
    return parser


def _migration_payload(
    report: MigrationReport,
    reconciliation: ReconciliationReport,
    *,
    captured_watermark: str,
    source_database: str,
    target_database: str,
) -> dict[str, Any]:
    return {
        "capturedWatermark": captured_watermark,
        "sourceDatabase": source_database,
        "sourceMode": "repeatable_read_read_only",
        "targetDatabase": target_database,
        "migration": report.to_public_dict(),
        "reconciliation": reconciliation.to_public_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not DATABASE_NAME.fullmatch(args.expected_source_database):
        raise SystemExit("expected source database name is invalid")
    if not DATABASE_NAME.fullmatch(args.expected_target_database):
        raise SystemExit("expected target database name is invalid")
    if args.mode == "verify-restore":
        if not args.expected_restore_database or not DATABASE_NAME.fullmatch(args.expected_restore_database):
            raise SystemExit("expected restore database name is invalid")
        target_dsn = os.environ.get(args.target_dsn_env, "")
        restore_dsn = os.environ.get(args.restore_dsn_env, "")
        if not target_dsn or not restore_dsn:
            raise SystemExit("restore verification DSN environment is incomplete")
        try:
            validate_local_app_dsn(target_dsn, args.expected_target_database)
            validate_local_app_dsn(restore_dsn, args.expected_restore_database)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        if target_dsn == restore_dsn:
            raise SystemExit("candidate and restore DSNs must be distinct")
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - exercised on the managed host
            raise SystemExit("psycopg is required in the managed Chickenbro runtime") from error
        with (
            psycopg.connect(target_dsn, autocommit=True) as candidate_connection,
            psycopg.connect(restore_dsn, autocommit=True) as restore_connection,
            candidate_connection.transaction(),
            restore_connection.transaction(),
        ):
            candidate_connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            restore_connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            candidate_identity = capture_restore_identity(
                candidate_connection, args.expected_target_database,
            )
            restore_identity = capture_restore_identity(
                restore_connection, args.expected_restore_database,
            )
            comparison = compare_restore_identities(candidate_identity, restore_identity)
        _write_report(args.report_path, {
            "sourceMode": "candidate_and_restore_repeatable_read_read_only",
            "candidateDatabase": args.expected_target_database,
            "restoreDatabase": args.expected_restore_database,
            "comparison": comparison,
        })
        return 0
    source_dsn = os.environ.get(args.source_dsn_env, "")
    target_dsn = os.environ.get(args.target_dsn_env, "")
    approved_app_context = os.environ.get(args.approved_app_context_env, "")
    if not source_dsn or not target_dsn or not approved_app_context:
        raise SystemExit("migration DSN/app-context environment is incomplete")
    try:
        validate_local_app_dsn(source_dsn, args.expected_source_database)
        validate_local_app_dsn(target_dsn, args.expected_target_database)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if source_dsn == target_dsn:
        raise SystemExit("source and target DSNs must be distinct")

    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - exercised on the managed host
        raise SystemExit("psycopg is required in the managed Chickenbro runtime") from error

    with (
        psycopg.connect(source_dsn, autocommit=True) as source,
        psycopg.connect(target_dsn, autocommit=True) as target_connection,
        source.transaction(),
    ):
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        source_identity = source.execute(
            "SELECT current_database(), current_setting('transaction_read_only')",
        ).fetchone()
        if source_identity != (args.expected_source_database, "on"):
            raise MigrationError("SOURCE_READ_ONLY_IDENTITY_MISMATCH")
        target_database = target_connection.execute("SELECT current_database()").fetchone()
        if not target_database or target_database[0] != args.expected_target_database:
            raise MigrationError("TARGET_DATABASE_IDENTITY_MISMATCH")
        captured = source.execute("SELECT transaction_timestamp()").fetchone()[0]
        captured_text = _timestamp_text(captured)
        raw_rows = read_source_rows(source)
        records = normalize_legacy_rows(raw_rows, approved_app_context=approved_app_context)
        target = PostgresMigrationTarget(target_connection)
        through = MigrationWatermark.through(captured_text)
        with target_connection.transaction():
            if args.mode == "full":
                report = migrate_full(records, target, through)
            else:
                if not args.from_watermark:
                    raise MigrationError("FROM_WATERMARK_REQUIRED")
                report = migrate_delta(
                    records,
                    target,
                    MigrationWatermark.through(args.from_watermark),
                    through,
                )
            reconciliation = reconcile(records, target, report)
            if reconciliation.status != "matched":
                raise MigrationError("MIGRATION_RECONCILIATION_DIVERGED")

    _write_report(
        args.report_path,
        _migration_payload(
            report,
            reconciliation,
            captured_watermark=captured_text,
            source_database=args.expected_source_database,
            target_database=args.expected_target_database,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PostgresMigrationTarget",
    "capture_restore_identity",
    "compare_restore_identities",
    "normalize_legacy_rows",
    "read_source_rows",
    "validate_local_app_dsn",
]
