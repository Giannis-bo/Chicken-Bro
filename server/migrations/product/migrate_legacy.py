#!/usr/bin/env python3
"""Whitelist-only legacy migration for the Chickenbro Chat and SimC product.

The module deliberately operates through small source/target interfaces.  It can
be exercised entirely in memory, while the candidate deployment can supply a
DB-API backed target without changing classification or transformation rules.
Public reports contain only hashes, counts, reason codes, and target UUIDs.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, MutableMapping, Protocol, Sequence
from urllib.parse import parse_qs, unquote, urlsplit


MIGRATION_REVISION = "chickenbro-simc-legacy-migration-v1"
TARGET_NAMESPACE = uuid.UUID("ea0aa77e-2fae-5b20-a97f-220192c38e28")

MigrationStatus = Literal["accepted", "rejected"]

AUTH_TABLES = frozenset({
    "identity.auth_tokens",
    "identity.auth_sessions",
    "identity.web_login_sessions",
})
PROTOTYPE_TABLES = frozenset({"identity.prototype_sessions"})

SOURCE_TO_TARGET = {
    "identity.users": "identity.users",
    "identity.user_identities": "identity.user_identities",
    "chat.conversations": "chat.conversations",
    "chat.messages": "chat.messages",
    "chat.agent_runs": "chat.agent_runs",
    "simc.source_snapshots": "simc.source_snapshots",
    "simc.simulation_jobs": "simc.simulation_jobs",
    "simc.simulation_attempts": "simc.simulation_attempts",
    "simc.simulation_results": "simc.simulation_results",
    "app.chickenbro_sessions": "chat.conversations",
    "app.chickenbro_messages": "chat.messages",
    "app.agent_jobs": "chat.agent_runs",
    "app.simulator_tasks": "simc.simulation_jobs",
}

SOURCE_ORDER = (
    "identity.users",
    "identity.user_identities",
    "chat.conversations",
    "app.chickenbro_sessions",
    "chat.messages",
    "app.chickenbro_messages",
    "chat.agent_runs",
    "app.agent_jobs",
    "simc.source_snapshots",
    "simc.simulation_jobs",
    "simc.simulation_attempts",
    "simc.simulation_results",
    "app.simulator_tasks",
)

MUTABLE_TARGET_TABLES = frozenset({
    "identity.users",
    "identity.user_identities",
    "chat.conversations",
})

TERMINAL_SIMC_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
TERMINAL_AGENT_STATUSES = frozenset({"succeeded", "failed"})
LEGACY_SIMC_MODES = frozenset({"simc", "simcraft", "simcraft_agent", "simcraft_template"})
SOURCE_READINESS = frozenset({
    "INVALID_LINK",
    "CHARACTER_NOT_FOUND",
    "ACCESS_RESTRICTED",
    "SNAPSHOT_UNAVAILABLE",
    "INCOMPLETE_FOR_SIMC",
    "READY_FOR_SIMC",
})
SHA256_PATTERN = frozenset("0123456789abcdef")


class MigrationError(RuntimeError):
    """A deterministic migration invariant failed."""


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"unsupported migration value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _record_row(record: Mapping[str, Any]) -> Mapping[str, Any]:
    row = record.get("row")
    return row if isinstance(row, Mapping) else record


def _record_pk(record: Mapping[str, Any]) -> Any:
    if "pk" in record:
        return record["pk"]
    row = _record_row(record)
    if "id" in row:
        return {"id": row["id"]}
    return {}


def _has_explicit_source_pk(record: Mapping[str, Any]) -> bool:
    if "pk" not in record or record.get("pk") is None:
        return False
    value = record["pk"]
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (str, bytes, tuple, list)):
        return bool(value)
    return True


def source_primary_key_hash(record: Mapping[str, Any]) -> str:
    return content_hash(_record_pk(record))


def stable_target_uuid(source_table: str, source_pk: Any, suffix: str = "") -> str:
    scope = f"{source_table}:{canonical_json(source_pk)}"
    if suffix:
        scope = f"{scope}:{suffix}"
    return str(uuid.uuid5(TARGET_NAMESPACE, scope))


def _target_id(record: Mapping[str, Any], suffix: str = "") -> str:
    table = str(record.get("table") or "")
    return stable_target_uuid(table, _record_pk(record), suffix)


def _decision_reason_for_table(table: str) -> str:
    if table in PROTOTYPE_TABLES:
        return "PROTOTYPE_NOT_MIGRATED"
    if table in AUTH_TABLES:
        return "AUTH_SESSION_NOT_MIGRATED"
    if table not in SOURCE_TO_TARGET:
        return "DOMAIN_NOT_MIGRATED"
    return "ACCEPTED_BY_WHITELIST"


@dataclass(frozen=True)
class MigrationDecision:
    source_table: str
    source_primary_key_hash: str
    source_content_hash: str
    status: MigrationStatus
    reason: str
    target_table: str | None
    target_id: str | None
    generated_targets: tuple[tuple[str, str], ...] = ()

    @property
    def subject_key(self) -> str:
        return f"{self.source_table}:{self.source_primary_key_hash}"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "sourceTable": self.source_table,
            "sourcePrimaryKeyHash": self.source_primary_key_hash,
            "sourceContentHash": self.source_content_hash,
            "status": self.status,
            "reason": self.reason,
            "targetTable": self.target_table,
            "targetId": self.target_id,
            "generatedTargets": [
                {"table": table, "id": target_id}
                for table, target_id in self.generated_targets
            ],
        }


def classify_record(record: Mapping[str, Any]) -> MigrationDecision:
    table = str(record.get("table") or "")
    row = _record_row(record)
    pk_hash = source_primary_key_hash(record)
    row_hash = content_hash(row)
    reason = _decision_reason_for_table(table)

    if table == "identity.users" and row.get("account_kind") == "prototype":
        reason = "PROTOTYPE_NOT_MIGRATED"
    elif table == "identity.user_identities" and row:
        if row.get("provider") != "wechat_mini":
            reason = "IDENTITY_PROVIDER_NOT_MIGRATED"
        elif not _bounded_text(row.get("app_context"), 128):
            reason = "APP_CONTEXT_REQUIRED"
    elif table == "app.simulator_tasks" and row and row.get("mode") not in LEGACY_SIMC_MODES:
        reason = "SIMC_MODE_NOT_MIGRATED"
    elif reason == "ACCEPTED_BY_WHITELIST" and not _has_explicit_source_pk(record):
        reason = "SOURCE_PRIMARY_KEY_REQUIRED"

    if reason != "ACCEPTED_BY_WHITELIST":
        return MigrationDecision(
            source_table=table,
            source_primary_key_hash=pk_hash,
            source_content_hash=row_hash,
            status="rejected",
            reason=reason,
            target_table=None,
            target_id=None,
        )

    suffix = "job" if table == "app.simulator_tasks" else ""
    return MigrationDecision(
        source_table=table,
        source_primary_key_hash=pk_hash,
        source_content_hash=row_hash,
        status="accepted",
        reason=reason,
        target_table=SOURCE_TO_TARGET[table],
        target_id=_target_id(record, suffix),
    )


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise MigrationError("INVALID_TIMESTAMP") from error
    else:
        raise MigrationError("INVALID_TIMESTAMP")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: Any) -> str:
    return _parse_timestamp(value).isoformat().replace("+00:00", "Z")


def _record_timestamp(record: Mapping[str, Any]) -> datetime:
    row = _record_row(record)
    for value in (
        record.get("updated_at"),
        row.get("updated_at"),
        row.get("created_at"),
        row.get("finished_at"),
        row.get("fetched_at"),
        row.get("queued_at"),
    ):
        if value:
            return _parse_timestamp(value)
    raise MigrationError("SOURCE_WATERMARK_REQUIRED")


def _record_position(record: Mapping[str, Any]) -> tuple[datetime, str]:
    return _record_timestamp(record), canonical_json(_record_pk(record))


@dataclass(frozen=True)
class MigrationWatermark:
    updated_at: datetime
    source_id_key: str

    @classmethod
    def through(cls, updated_at: str | datetime) -> "MigrationWatermark":
        return cls(_parse_timestamp(updated_at), "\U0010ffff")

    @classmethod
    def at(cls, updated_at: str | datetime, source_pk: Any) -> "MigrationWatermark":
        return cls(_parse_timestamp(updated_at), canonical_json(source_pk))

    def position(self) -> tuple[datetime, str]:
        return self.updated_at, self.source_id_key

    def public_hash(self) -> str:
        return content_hash({
            "updatedAt": self.updated_at.isoformat().replace("+00:00", "Z"),
            "sourceIdHash": hashlib.sha256(self.source_id_key.encode("utf-8")).hexdigest(),
        })


MINIMUM_WATERMARK = MigrationWatermark(datetime.min.replace(tzinfo=timezone.utc), "")


class MigrationTarget(Protocol):
    def upsert(self, table: str, row: Mapping[str, Any], *, mutable: bool) -> None: ...
    def has(self, table: str, target_id: str) -> bool: ...
    def get(self, table: str, target_id: str) -> Mapping[str, Any] | None: ...
    def rows(self, table: str) -> list[dict[str, Any]]: ...
    def record_mapping(self, decision: MigrationDecision) -> None: ...
    def has_mapping(self, subject_key: str) -> bool: ...


class InMemoryMigrationTarget:
    """Deterministic target used by tests and offline migration previews."""

    def __init__(self) -> None:
        self._tables: MutableMapping[str, MutableMapping[str, dict[str, Any]]] = defaultdict(dict)
        self._mapping_subjects: set[str] = set()

    @staticmethod
    def _unique_keys(table: str, row: Mapping[str, Any]) -> list[tuple[str, tuple[Any, ...]]]:
        if table == "identity.user_identities":
            return [("provider_subject", (
                row.get("provider"), row.get("app_context"), row.get("provider_subject"),
            ))]
        if table == "chat.messages" and row.get("client_message_id") is not None:
            return [("user_client_message", (row.get("user_id"), row.get("client_message_id")))]
        if table == "chat.agent_runs":
            return [
                ("user_idempotency", (row.get("user_id"), row.get("idempotency_key"))),
                ("user_message", (row.get("user_id"), row.get("user_message_id"))),
            ]
        if table == "simc.source_snapshots":
            return [("user_source_revision", (
                row.get("user_id"), row.get("provider"), row.get("source_key"), row.get("revision"),
            ))]
        if table == "simc.simulation_jobs":
            return [("user_idempotency", (row.get("user_id"), row.get("idempotency_key")))]
        if table == "simc.simulation_attempts":
            return [("job_attempt", (row.get("job_id"), row.get("attempt_number")))]
        if table == "simc.simulation_results":
            return [("job", (row.get("job_id"),))]
        return []

    def upsert(self, table: str, row: Mapping[str, Any], *, mutable: bool) -> None:
        target_id = str(row.get("id") or "")
        if not target_id:
            raise MigrationError("TARGET_ID_REQUIRED")
        normalized = deepcopy(dict(row))
        existing = self._tables[table].get(target_id)
        new_unique_keys = self._unique_keys(table, normalized)
        for other_id, other in self._tables[table].items():
            if other_id == target_id:
                continue
            other_unique_keys = dict(self._unique_keys(table, other))
            for constraint, key in new_unique_keys:
                if other_unique_keys.get(constraint) == key:
                    raise MigrationError(f"TARGET_UNIQUE_CONFLICT:{table}:{constraint}")
        if existing is None:
            self._tables[table][target_id] = normalized
            return
        if content_hash(existing) == content_hash(normalized):
            return
        if not mutable:
            raise MigrationError(f"TARGET_CONTENT_CONFLICT:{table}")
        for immutable_key in (
            "id",
            "user_id",
            "conversation_id",
            "job_id",
            "provider",
            "app_context",
            "provider_subject",
        ):
            if immutable_key in existing and existing.get(immutable_key) != normalized.get(immutable_key):
                raise MigrationError(f"TARGET_OWNER_CONFLICT:{table}")
        self._tables[table][target_id] = normalized

    def has(self, table: str, target_id: str) -> bool:
        return target_id in self._tables.get(table, {})

    def get(self, table: str, target_id: str) -> Mapping[str, Any] | None:
        row = self._tables.get(table, {}).get(target_id)
        return deepcopy(row) if row is not None else None

    def rows(self, table: str) -> list[dict[str, Any]]:
        return [deepcopy(row) for _, row in sorted(self._tables.get(table, {}).items())]

    def count(self, table: str) -> int:
        return len(self._tables.get(table, {}))

    def record_mapping(self, decision: MigrationDecision) -> None:
        if decision.status != "accepted" or not decision.target_id or not decision.target_table:
            raise MigrationError("ONLY_ACCEPTED_MAPPINGS_ARE_STORED")
        if decision.subject_key in self._mapping_subjects:
            return
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
        self._tables["ops.audit_events"][audit_id] = {
            "id": audit_id,
            "user_id": None,
            "event_type": "legacy_migration.accepted",
            "subject_key": decision.subject_key,
            "payload_json": payload,
        }
        self._mapping_subjects.add(decision.subject_key)

    def has_mapping(self, subject_key: str) -> bool:
        return subject_key in self._mapping_subjects

    def replace_for_test(self, table: str, target_id: str, row: Mapping[str, Any]) -> None:
        if target_id not in self._tables.get(table, {}):
            raise KeyError(target_id)
        self._tables[table][target_id] = deepcopy(dict(row))


@dataclass(frozen=True)
class MigrationReport:
    mode: Literal["full", "delta"]
    migration_revision: str
    source_snapshot_hash: str
    from_watermark_hash: str
    through_watermark_hash: str
    accepted_count: int
    rejected_count: int
    accepted_hash: str
    rejected_hash: str
    accepted_by_source_table: Mapping[str, int]
    rejected_by_source_table: Mapping[str, int]
    reason_counts: Mapping[str, int]
    target_counts: Mapping[str, int]
    target_table_hashes: Mapping[str, str]
    decisions: tuple[MigrationDecision, ...] = field(repr=False)
    expected_target_hashes: Mapping[str, Mapping[str, str]] = field(repr=False)
    message_order_hashes: Mapping[str, str] = field(repr=False)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "migrationRevision": self.migration_revision,
            "sourceSnapshotHash": self.source_snapshot_hash,
            "fromWatermarkHash": self.from_watermark_hash,
            "throughWatermarkHash": self.through_watermark_hash,
            "acceptedCount": self.accepted_count,
            "rejectedCount": self.rejected_count,
            "acceptedHash": self.accepted_hash,
            "rejectedHash": self.rejected_hash,
            "acceptedBySourceTable": dict(sorted(self.accepted_by_source_table.items())),
            "rejectedBySourceTable": dict(sorted(self.rejected_by_source_table.items())),
            "reasonCounts": dict(sorted(self.reason_counts.items())),
            "targetCounts": dict(sorted(self.target_counts.items())),
            "targetTableHashes": dict(sorted(self.target_table_hashes.items())),
        }


@dataclass
class _Context:
    records: Sequence[Mapping[str, Any]]
    target: MigrationTarget
    by_table_and_id: dict[tuple[str, str], Mapping[str, Any]] = field(default_factory=dict)
    formal_user_ids: set[str] = field(default_factory=set)
    ambiguous_identity_keys: set[tuple[str, str]] = field(default_factory=set)
    invalid_message_keys: set[tuple[str, str]] = field(default_factory=set)
    invalid_simc_job_reasons: dict[str, str] = field(default_factory=dict)
    invalid_simc_result_reasons: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for record in self.records:
            row = _record_row(record)
            source_id = _source_id(row)
            if source_id:
                self.by_table_and_id[(str(record.get("table") or ""), source_id)] = record

        users = {
            _source_id(_record_row(record)): record
            for record in self.records
            if record.get("table") == "identity.users" and _source_id(_record_row(record))
        }
        identity_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for record in self.records:
            if record.get("table") != "identity.user_identities":
                continue
            row = _record_row(record)
            owner = str(row.get("user_id") or "")
            user_record = users.get(owner)
            user_row = _record_row(user_record) if user_record else {}
            if (
                row.get("provider") == "wechat_mini"
                and _bounded_text(row.get("app_context"), 128)
                and _bounded_text(row.get("provider_subject"), 256)
                and user_record is not None
                and user_row.get("account_kind", "formal") != "prototype"
            ):
                identity_groups[(
                    str(row["provider"]),
                    str(row["app_context"]),
                    str(row["provider_subject"]),
                )].append(record)
        for group in identity_groups.values():
            if len(group) != 1:
                self.ambiguous_identity_keys.update(
                    (str(item.get("table") or ""), _source_id(_record_row(item)))
                    for item in group
                )
                continue
            self.formal_user_ids.add(str(_record_row(group[0]).get("user_id") or ""))

        message_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for record in self.records:
            table = str(record.get("table") or "")
            if table not in {"chat.messages", "app.chickenbro_messages"}:
                continue
            row = _record_row(record)
            parent = row.get("conversation_id") if table == "chat.messages" else row.get("session_id")
            message_groups[(table, str(parent or ""))].append(record)
        for group in message_groups.values():
            try:
                ordered = sorted(
                    group,
                    key=lambda item: (
                        _parse_timestamp(_record_row(item).get("created_at")),
                        _source_id(_record_row(item)),
                    ),
                )
            except MigrationError:
                self.invalid_message_keys.update(
                    (str(item.get("table") or ""), _source_id(_record_row(item)))
                    for item in group
                )
                continue
            unmatched_users = 0
            for item in ordered:
                row = _record_row(item)
                key = (str(item.get("table") or ""), _source_id(row))
                if row.get("role") == "user":
                    unmatched_users += 1
                elif row.get("role") == "assistant":
                    if unmatched_users <= 0:
                        self.invalid_message_keys.add(key)
                    else:
                        unmatched_users -= 1

        direct_results_by_job: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in self.records:
            if record.get("table") == "simc.simulation_results":
                direct_results_by_job[str(_record_row(record).get("job_id") or "")].append(record)
        for record in self.records:
            if record.get("table") != "simc.simulation_jobs":
                continue
            job_row = _record_row(record)
            if job_row.get("status") != "succeeded":
                continue
            job_id = _source_id(job_row)
            results = direct_results_by_job.get(job_id, [])
            if len(results) != 1:
                self.invalid_simc_job_reasons[job_id] = "SEMANTIC_RESULT_REQUIRED"
                for result in results:
                    self.invalid_simc_result_reasons[_source_id(_record_row(result))] = "SEMANTIC_RESULT_REQUIRED"
                continue
            snapshot_record = self.by_table_and_id.get((
                "simc.source_snapshots",
                str(job_row.get("snapshot_id") or ""),
            ))
            if snapshot_record is None:
                continue
            error = _semantic_result_error(
                _record_row(results[0]),
                job_row,
                _record_row(snapshot_record),
                _target_id(snapshot_record),
            )
            if error:
                self.invalid_simc_job_reasons[job_id] = error
                self.invalid_simc_result_reasons[_source_id(_record_row(results[0]))] = error

    def owner_target_id(self, source_user_id: Any) -> str | None:
        owner = str(source_user_id or "")
        if not owner or owner not in self.formal_user_ids:
            return None
        record = self.by_table_and_id.get(("identity.users", owner))
        if record is None:
            return None
        return _target_id(record)

    def parent_target_id(self, source_table: str, source_id: Any, suffix: str = "") -> str | None:
        record = self.by_table_and_id.get((source_table, str(source_id or "")))
        return _target_id(record, suffix) if record else None


def _source_id(row: Mapping[str, Any]) -> str:
    value = row.get("id")
    return str(value) if value is not None and str(value) else ""


def _bounded_text(value: Any, maximum: int, minimum: int = 1) -> bool:
    return isinstance(value, str) and minimum <= len(value) <= maximum


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value.lower()).issubset(SHA256_PATTERN)
    )


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _semantic_result_error(
    row: Mapping[str, Any],
    job_row: Mapping[str, Any],
    snapshot_row: Mapping[str, Any],
    snapshot_target_id: str,
    *,
    result_owner_id: Any | None = None,
) -> str | None:
    actual_owner = row.get("user_id") if result_owner_id is None else result_owner_id
    if actual_owner != job_row.get("user_id"):
        return "OWNER_PARENT_MISMATCH"
    if not _sha256(row.get("profile_sha256")) or not _positive_number(row.get("primary_metric_value")):
        return "SEMANTIC_RESULT_REQUIRED"
    if row.get("primary_metric_name") not in {"dps", "hps"}:
        return "SEMANTIC_RESULT_REQUIRED"
    for key in ("compiler_revision", "runtime_revision"):
        if not _bounded_text(row.get(key), 160):
            return "REQUIRED_INPUT_MISSING"
        if row.get(key) != job_row.get(key):
            return "RESULT_PROVENANCE_MISMATCH"
    result_json = row.get("result_json")
    provenance = row.get("provenance_json")
    snapshot_provenance = snapshot_row.get("provenance_json")
    source_revision = snapshot_provenance.get("sourceRevision") if isinstance(snapshot_provenance, Mapping) else None
    if (
        not isinstance(result_json, Mapping)
        or not isinstance(provenance, Mapping)
        or result_json.get("metricName") != row.get("primary_metric_name")
        or result_json.get("metricValue") != row.get("primary_metric_value")
        or not _bounded_text(source_revision, 160)
    ):
        return "SEMANTIC_RESULT_REQUIRED"
    expected_provenance = {
        "snapshotId": snapshot_target_id,
        "sourceRevision": source_revision,
        "sourceRawSha256": snapshot_row.get("raw_sha256"),
        "profileSha256": str(row["profile_sha256"]).lower(),
        "compilerRevision": row["compiler_revision"],
        "runtimeRevision": row["runtime_revision"],
        "scenarioHash": job_row.get("scenario_hash"),
    }
    if any(provenance.get(key) != value for key, value in expected_provenance.items()):
        return "RESULT_PROVENANCE_MISMATCH"
    return None


def _sanitized_profile(value: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    limits = {"nickname": 256, "avatarUrl": 2048}
    for key, maximum in limits.items():
        candidate = value.get(key)
        if isinstance(candidate, str) and 0 < len(candidate) <= maximum:
            output[key] = candidate
    return output


def _valid_source_url(provider: Any, value: Any) -> bool:
    if provider not in {"raiderio", "warcraftlogs"} or not _bounded_text(value, 2048):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        return False
    host = (parsed.hostname or "").lower()
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if provider == "raiderio":
        if host not in {"raider.io", "www.raider.io"} or parsed.query or parsed.fragment:
            return False
        if len(parts) == 5 and parts[1].lower() == "characters" and len(parts[0]) in {2, 5}:
            parts = parts[1:]
        return len(parts) == 4 and parts[0].lower() == "characters" and all(parts[1:])
    if host not in {"warcraftlogs.com", "www.warcraftlogs.com"}:
        return False
    if len(parts) not in {2, 3} or parts[0].lower() != "reports" or not parts[1].isalnum():
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    fragment = parse_qs(parsed.fragment, keep_blank_values=True)
    keys = set(query) | set(fragment)
    if any(key not in {"fight", "source"} for key in keys):
        return False
    for key in ("fight", "source"):
        values = query.get(key, []) + fragment.get(key, [])
        if len(values) > 1 or (values and (not values[0].isdigit() or int(values[0]) <= 0)):
            return False
    return True


def _required_timestamp(row: Mapping[str, Any], key: str, fallback: str | None = None) -> str:
    value = row.get(key) or (row.get(fallback) if fallback else None)
    return _timestamp_text(value)


def _reject(base: MigrationDecision, reason: str) -> tuple[MigrationDecision, list[tuple[str, dict[str, Any]]]]:
    return (
        MigrationDecision(
            source_table=base.source_table,
            source_primary_key_hash=base.source_primary_key_hash,
            source_content_hash=base.source_content_hash,
            status="rejected",
            reason=reason,
            target_table=None,
            target_id=None,
        ),
        [],
    )


def _accept(
    base: MigrationDecision,
    rows: Sequence[tuple[str, dict[str, Any]]],
    reason: str,
) -> tuple[MigrationDecision, list[tuple[str, dict[str, Any]]]]:
    generated = tuple((table, str(row["id"])) for table, row in rows)
    return (
        MigrationDecision(
            source_table=base.source_table,
            source_primary_key_hash=base.source_primary_key_hash,
            source_content_hash=base.source_content_hash,
            status="accepted",
            reason=reason,
            target_table=base.target_table,
            target_id=base.target_id,
            generated_targets=generated,
        ),
        list(rows),
    )


def _convert_identity_user(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    source_id = _source_id(row)
    if source_id not in context.formal_user_ids:
        if row.get("account_kind") == "prototype":
            return _reject(base, "PROTOTYPE_NOT_MIGRATED")
        return _reject(base, "FORMAL_IDENTITY_REQUIRED")
    status = row.get("status", "active")
    if status not in {"active", "disabled", "deleted"}:
        return _reject(base, "INVALID_USER_STATUS")
    try:
        target = {
            "id": base.target_id,
            "display_name": str(row.get("display_name") or "")[:256],
            "status": status,
            "created_at": _required_timestamp(row, "created_at", "updated_at"),
            "updated_at": _required_timestamp(row, "updated_at", "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("identity.users", target)], "FORMAL_WECHAT_USER")


def _convert_identity(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    if (base.source_table, _source_id(row)) in context.ambiguous_identity_keys:
        return _reject(base, "AMBIGUOUS_IDENTITY_MAPPING")
    owner = context.owner_target_id(row.get("user_id"))
    if not owner:
        source_user = context.by_table_and_id.get(("identity.users", str(row.get("user_id") or "")))
        if source_user and _record_row(source_user).get("account_kind") == "prototype":
            return _reject(base, "PROTOTYPE_NOT_MIGRATED")
        return _reject(base, "OWNER_NOT_MIGRATED")
    if row.get("provider") != "wechat_mini":
        return _reject(base, "IDENTITY_PROVIDER_NOT_MIGRATED")
    if not _bounded_text(row.get("app_context"), 128):
        return _reject(base, "APP_CONTEXT_REQUIRED")
    if not _bounded_text(row.get("provider_subject"), 256):
        return _reject(base, "PROVIDER_SUBJECT_REQUIRED")
    profile = row.get("profile_json", {})
    if not isinstance(profile, Mapping):
        return _reject(base, "INVALID_PROFILE")
    try:
        target = {
            "id": base.target_id,
            "user_id": owner,
            "provider": "wechat_mini",
            "app_context": row["app_context"],
            "provider_subject": row["provider_subject"],
            "union_id": row.get("union_id"),
            "profile_json": _sanitized_profile(profile),
            "created_at": _required_timestamp(row, "created_at", "updated_at"),
            "updated_at": _required_timestamp(row, "updated_at", "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("identity.user_identities", target)], "FORMAL_WECHAT_IDENTITY")


def _conversation_source_table(table: str) -> str:
    return "chat.conversations" if table == "chat.messages" else "app.chickenbro_sessions"


def _convert_conversation(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    owner = context.owner_target_id(row.get("user_id"))
    if not owner or not context.target.has("identity.users", owner):
        return _reject(base, "OWNER_NOT_MIGRATED")
    title = str(row.get("title") or "")
    status = row.get("status", "active")
    if len(title) > 256 or status not in {"active", "archived"}:
        return _reject(base, "INVALID_CONVERSATION")
    try:
        target = {
            "id": base.target_id,
            "user_id": owner,
            "title": title,
            "status": status,
            "created_at": _required_timestamp(row, "created_at", "updated_at"),
            "updated_at": _required_timestamp(row, "updated_at", "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("chat.conversations", target)], "OWNER_BOUND_CHAT")


def _convert_message(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    if (base.source_table, _source_id(row)) in context.invalid_message_keys:
        return _reject(base, "MESSAGE_ORDER_INVALID")
    owner = context.owner_target_id(row.get("user_id"))
    parent_source = _conversation_source_table(base.source_table)
    parent_source_id = row.get("conversation_id") if base.source_table == "chat.messages" else row.get("session_id")
    conversation = context.parent_target_id(parent_source, parent_source_id)
    if not owner:
        return _reject(base, "OWNER_NOT_MIGRATED")
    if not conversation or not context.target.has("chat.conversations", conversation):
        return _reject(base, "PARENT_NOT_MIGRATED")
    conversation_row = context.target.get("chat.conversations", conversation)
    if not conversation_row or conversation_row.get("user_id") != owner:
        return _reject(base, "OWNER_PARENT_MISMATCH")
    role = row.get("role")
    content = row.get("content")
    if role not in {"user", "assistant"} or not _bounded_text(content, 100000):
        return _reject(base, "INVALID_MESSAGE")
    client_message_id = row.get("client_message_id")
    if client_message_id is not None and not _bounded_text(client_message_id, 128):
        return _reject(base, "INVALID_MESSAGE")
    if role == "user" and client_message_id is None:
        client_message_id = f"legacy-{base.source_primary_key_hash[:48]}"
    try:
        target = {
            "id": base.target_id,
            "conversation_id": conversation,
            "user_id": owner,
            "role": role,
            "content": content,
            "client_message_id": client_message_id,
            "created_at": _required_timestamp(row, "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("chat.messages", target)], "OWNER_BOUND_CHAT")


def _convert_agent_run(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    if (
        base.source_table == "app.agent_jobs"
        and row.get("migration_rejection_reason") == "AMBIGUOUS_AGENT_RUN"
    ):
        return _reject(base, "AMBIGUOUS_AGENT_RUN")
    owner = context.owner_target_id(row.get("user_id"))
    status = row.get("status")
    if status not in TERMINAL_AGENT_STATUSES:
        return _reject(base, "TERMINAL_STATE_REQUIRED")
    if not owner:
        return _reject(base, "OWNER_NOT_MIGRATED")
    direct = base.source_table == "chat.agent_runs"
    conversation_source = "chat.conversations" if direct else "app.chickenbro_sessions"
    message_source = "chat.messages" if direct else "app.chickenbro_messages"
    conversation_source_id = row.get("conversation_id") if direct else row.get("session_id")
    conversation = context.parent_target_id(conversation_source, conversation_source_id)
    user_message = context.parent_target_id(message_source, row.get("user_message_id"))
    assistant_message = context.parent_target_id(message_source, row.get("assistant_message_id")) if row.get("assistant_message_id") else None
    if not conversation or not user_message:
        return _reject(base, "PARENT_NOT_MIGRATED")
    if not context.target.has("chat.conversations", conversation) or not context.target.has("chat.messages", user_message):
        return _reject(base, "PARENT_NOT_MIGRATED")
    conversation_row = context.target.get("chat.conversations", conversation)
    user_message_row = context.target.get("chat.messages", user_message)
    if (
        not conversation_row
        or not user_message_row
        or conversation_row.get("user_id") != owner
        or user_message_row.get("user_id") != owner
        or user_message_row.get("role") != "user"
    ):
        return _reject(base, "OWNER_PARENT_MISMATCH")
    if user_message_row.get("conversation_id") != conversation:
        return _reject(base, "RUN_MESSAGE_CONVERSATION_MISMATCH")
    if status == "succeeded" and (not assistant_message or not context.target.has("chat.messages", assistant_message)):
        return _reject(base, "ASSISTANT_MESSAGE_REQUIRED")
    if assistant_message:
        assistant_row = context.target.get("chat.messages", assistant_message)
        if not assistant_row or assistant_row.get("user_id") != owner or assistant_row.get("role") != "assistant":
            return _reject(base, "OWNER_PARENT_MISMATCH")
        if assistant_row.get("conversation_id") != conversation:
            return _reject(base, "RUN_MESSAGE_CONVERSATION_MISMATCH")
    runtime_revision = row.get("runtime_revision") or row.get("runtimeRevision")
    if not _bounded_text(runtime_revision, 160):
        return _reject(base, "RUNTIME_REVISION_REQUIRED")
    try:
        target = {
            "id": base.target_id,
            "user_id": owner,
            "conversation_id": conversation,
            "user_message_id": user_message,
            "assistant_message_id": assistant_message,
            "status": status,
            "runtime_revision": runtime_revision,
            "public_error_code": str(row.get("public_error_code") or row.get("error_code") or "")[:128],
            "started_at": _required_timestamp(row, "started_at", "created_at"),
            "finished_at": _required_timestamp(row, "finished_at", "updated_at"),
            "idempotency_key": str(row.get("idempotency_key") or f"legacy-{base.source_primary_key_hash[:48]}")[:128],
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("chat.agent_runs", target)], "TERMINAL_AGENT_RUN")


def _convert_snapshot(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    owner = context.owner_target_id(row.get("user_id"))
    if not owner or not context.target.has("identity.users", owner):
        return _reject(base, "OWNER_NOT_MIGRATED")
    if not _valid_source_url(row.get("provider"), row.get("source_url")):
        return _reject(base, "INVALID_SOURCE")
    if not _bounded_text(row.get("source_key"), 512) or not isinstance(row.get("revision"), int) or row["revision"] <= 0:
        return _reject(base, "INVALID_SOURCE")
    if row.get("readiness", "SNAPSHOT_UNAVAILABLE") not in SOURCE_READINESS:
        return _reject(base, "INVALID_SOURCE")
    if not _sha256(row.get("raw_sha256")):
        return _reject(base, "SOURCE_HASH_REQUIRED")
    snapshot = row.get("snapshot_json", {})
    provenance = row.get("provenance_json", {})
    if not isinstance(snapshot, Mapping) or not isinstance(provenance, Mapping):
        return _reject(base, "INVALID_SOURCE")
    try:
        target = {
            "id": base.target_id,
            "user_id": owner,
            "provider": row["provider"],
            "source_url": row["source_url"],
            "source_key": row["source_key"],
            "revision": row["revision"],
            "readiness": row.get("readiness", "SNAPSHOT_UNAVAILABLE"),
            "snapshot_json": deepcopy(dict(snapshot)),
            "provenance_json": deepcopy(dict(provenance)),
            "raw_sha256": str(row["raw_sha256"]).lower(),
            "fetched_at": _required_timestamp(row, "fetched_at", "created_at"),
            "created_at": _required_timestamp(row, "created_at", "fetched_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("simc.source_snapshots", target)], "OWNER_BOUND_SIMC")


def _convert_job(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    if row.get("status") not in TERMINAL_SIMC_STATUSES:
        return _reject(base, "TERMINAL_STATE_REQUIRED")
    invalid_result_reason = context.invalid_simc_job_reasons.get(_source_id(row))
    if invalid_result_reason:
        return _reject(base, invalid_result_reason)
    owner = context.owner_target_id(row.get("user_id"))
    snapshot = context.parent_target_id("simc.source_snapshots", row.get("snapshot_id"))
    if not owner:
        return _reject(base, "OWNER_NOT_MIGRATED")
    if not snapshot or not context.target.has("simc.source_snapshots", snapshot):
        return _reject(base, "PARENT_NOT_MIGRATED")
    snapshot_row = context.target.get("simc.source_snapshots", snapshot)
    if not snapshot_row or snapshot_row.get("user_id") != owner:
        return _reject(base, "OWNER_PARENT_MISMATCH")
    if row.get("status") == "succeeded" and snapshot_row.get("readiness") != "READY_FOR_SIMC":
        return _reject(base, "SEMANTIC_SOURCE_NOT_READY")
    if not _sha256(row.get("scenario_hash")):
        return _reject(base, "SCENARIO_HASH_REQUIRED")
    for key in ("compiler_revision", "runtime_revision", "idempotency_key"):
        if not _bounded_text(row.get(key), 160 if key != "idempotency_key" else 128):
            return _reject(base, "REQUIRED_INPUT_MISSING")
    try:
        target = {
            "id": base.target_id,
            "user_id": owner,
            "snapshot_id": snapshot,
            "scenario_hash": str(row["scenario_hash"]).lower(),
            "compiler_revision": row["compiler_revision"],
            "runtime_revision": row["runtime_revision"],
            "idempotency_key": row["idempotency_key"],
            "status": row["status"],
            "public_error_code": str(row.get("public_error_code") or "")[:128],
            "created_at": _required_timestamp(row, "created_at", "updated_at"),
            "updated_at": _required_timestamp(row, "updated_at", "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("simc.simulation_jobs", target)], "OWNER_BOUND_SIMC")


def _convert_attempt(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    owner = context.owner_target_id(row.get("user_id"))
    job = context.parent_target_id("simc.simulation_jobs", row.get("job_id"))
    if not owner:
        return _reject(base, "OWNER_NOT_MIGRATED")
    if not job or not context.target.has("simc.simulation_jobs", job):
        return _reject(base, "PARENT_NOT_MIGRATED")
    job_row = context.target.get("simc.simulation_jobs", job)
    if not job_row or job_row.get("user_id") != owner:
        return _reject(base, "OWNER_PARENT_MISMATCH")
    if not isinstance(row.get("attempt_number"), int) or row["attempt_number"] <= 0 or not row.get("finished_at"):
        return _reject(base, "TERMINAL_STATE_REQUIRED")
    worker = row.get("worker_id")
    if not _bounded_text(worker, 160):
        return _reject(base, "REQUIRED_INPUT_MISSING")
    try:
        target = {
            "id": base.target_id,
            "job_id": job,
            "user_id": owner,
            "attempt_number": row["attempt_number"],
            "worker_id": worker,
            "started_at": _required_timestamp(row, "started_at"),
            "finished_at": _required_timestamp(row, "finished_at"),
            "exit_code": row.get("exit_code"),
            "diagnostic": str(row.get("diagnostic") or "")[:4096],
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("simc.simulation_attempts", target)], "OWNER_BOUND_SIMC")


def _convert_result(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    invalid_result_reason = context.invalid_simc_result_reasons.get(_source_id(row))
    if invalid_result_reason:
        return _reject(base, invalid_result_reason)
    owner = context.owner_target_id(row.get("user_id"))
    job = context.parent_target_id("simc.simulation_jobs", row.get("job_id"))
    if not owner:
        return _reject(base, "OWNER_NOT_MIGRATED")
    if not job or not context.target.has("simc.simulation_jobs", job):
        return _reject(base, "PARENT_NOT_MIGRATED")
    job_row = context.target.get("simc.simulation_jobs", job)
    if not job_row or job_row.get("user_id") != owner:
        return _reject(base, "OWNER_PARENT_MISMATCH")
    if job_row.get("status") != "succeeded":
        return _reject(base, "SUCCEEDED_JOB_REQUIRED")
    snapshot_row = context.target.get("simc.source_snapshots", str(job_row.get("snapshot_id") or ""))
    if not snapshot_row:
        return _reject(base, "PARENT_NOT_MIGRATED")
    error = _semantic_result_error(
        row,
        job_row,
        snapshot_row,
        str(job_row.get("snapshot_id") or ""),
        result_owner_id=owner,
    )
    if error:
        return _reject(base, error)
    provenance = row["provenance_json"]
    try:
        target = {
            "id": base.target_id,
            "job_id": job,
            "user_id": owner,
            "profile_sha256": str(row["profile_sha256"]).lower(),
            "result_json": {
                "metricName": row["primary_metric_name"],
                "metricValue": row["primary_metric_value"],
                "provenance": deepcopy(dict(provenance)),
            },
            "primary_metric_name": row["primary_metric_name"],
            "primary_metric_value": row["primary_metric_value"],
            "compiler_revision": row["compiler_revision"],
            "runtime_revision": row["runtime_revision"],
            "provenance_json": deepcopy(dict(provenance)),
            "created_at": _required_timestamp(row, "created_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(base, [("simc.simulation_results", target)], "SEMANTIC_SIMC_RESULT")


def _legacy_simc_source(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    request = row.get("request_json")
    if not isinstance(request, Mapping):
        return None
    source = request.get("source")
    return source if isinstance(source, Mapping) else None


def _convert_legacy_simc(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    row = _record_row(record)
    status = row.get("status")
    if status not in TERMINAL_SIMC_STATUSES | {"completed", "blocked"}:
        return _reject(base, "TERMINAL_STATE_REQUIRED")
    if status not in {"succeeded", "completed"}:
        return _reject(base, "SUCCESSFUL_LEGACY_RESULT_REQUIRED")
    owner = context.owner_target_id(row.get("user_id"))
    if not owner or not context.target.has("identity.users", owner):
        return _reject(base, "OWNER_NOT_MIGRATED")
    request = row.get("request_json")
    summary = row.get("summary_json")
    source = _legacy_simc_source(row)
    if not isinstance(request, Mapping) or not isinstance(summary, Mapping) or source is None:
        return _reject(base, "REQUIRED_INPUT_MISSING")
    scenario_hash = request.get("scenarioHash")
    profile_hash = request.get("profileSha256")
    raw_hash = source.get("rawSha256")
    compiler = request.get("compilerRevision")
    runtime = request.get("runtimeRevision")
    metric_name = summary.get("metricName")
    metric_value = summary.get("metricValue")
    if not all((_sha256(scenario_hash), _sha256(profile_hash), _sha256(raw_hash))):
        return _reject(base, "REQUIRED_INPUT_MISSING")
    if not _bounded_text(compiler, 160) or not _bounded_text(runtime, 160):
        return _reject(base, "REQUIRED_INPUT_MISSING")
    if metric_name not in {"dps", "hps"} or not _positive_number(metric_value):
        return _reject(base, "SEMANTIC_RESULT_REQUIRED")
    if not _valid_source_url(source.get("provider"), source.get("sourceUrl")):
        return _reject(base, "INVALID_SOURCE")
    if not _bounded_text(source.get("sourceKey"), 512):
        return _reject(base, "INVALID_SOURCE")
    if not isinstance(source.get("revision"), int) or source["revision"] <= 0:
        return _reject(base, "INVALID_SOURCE")
    if source.get("readiness") != "READY_FOR_SIMC":
        if source.get("readiness") in SOURCE_READINESS:
            return _reject(base, "SEMANTIC_SOURCE_NOT_READY")
        return _reject(base, "INVALID_SOURCE")
    attempt_number = row.get("attempt")
    if not isinstance(attempt_number, int) or attempt_number <= 0 or not row.get("finished_at"):
        return _reject(base, "TERMINAL_STATE_REQUIRED")
    worker_id = row.get("locked_by")
    exit_code = row.get("exit_code")
    if not _bounded_text(worker_id, 160) or not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return _reject(base, "REQUIRED_INPUT_MISSING")
    if exit_code != 0:
        return _reject(base, "SEMANTIC_RESULT_REQUIRED")

    snapshot_id = _target_id(record, "snapshot")
    job_id = base.target_id
    attempt_id = _target_id(record, f"attempt:{attempt_number}")
    result_id = _target_id(record, "result")
    fetched_at = source.get("fetchedAt") or row.get("created_at")
    source_revision = source.get("sourceRevision")
    if not _bounded_text(source_revision, 160):
        return _reject(base, "REQUIRED_INPUT_MISSING")
    provenance = {
        "snapshotId": snapshot_id,
        "sourceRevision": source_revision,
        "sourceRawSha256": str(raw_hash).lower(),
        "profileSha256": str(profile_hash).lower(),
        "compilerRevision": compiler,
        "runtimeRevision": runtime,
        "scenarioHash": str(scenario_hash).lower(),
    }
    result_json = summary.get("resultJson", {})
    if not isinstance(result_json, Mapping):
        return _reject(base, "SEMANTIC_RESULT_REQUIRED")
    try:
        snapshot = {
            "id": snapshot_id,
            "user_id": owner,
            "provider": source["provider"],
            "source_url": source["sourceUrl"],
            "source_key": source["sourceKey"],
            "revision": source["revision"],
            "readiness": source.get("readiness", "READY_FOR_SIMC"),
            "snapshot_json": deepcopy(dict(source.get("snapshot") or {})),
            "provenance_json": {
                "sourceRevision": source_revision,
                "sourceRawSha256": str(raw_hash).lower(),
            },
            "raw_sha256": str(raw_hash).lower(),
            "fetched_at": _timestamp_text(fetched_at),
            "created_at": _required_timestamp(row, "created_at", "queued_at"),
        }
        job = {
            "id": job_id,
            "user_id": owner,
            "snapshot_id": snapshot_id,
            "scenario_hash": str(scenario_hash).lower(),
            "compiler_revision": compiler,
            "runtime_revision": runtime,
            "idempotency_key": str(request.get("idempotencyKey") or f"legacy-{base.source_primary_key_hash[:48]}")[:128],
            "status": "succeeded",
            "public_error_code": "",
            "created_at": _required_timestamp(row, "created_at", "queued_at"),
            "updated_at": _required_timestamp(row, "updated_at", "finished_at"),
        }
        attempt = {
            "id": attempt_id,
            "job_id": job_id,
            "user_id": owner,
            "attempt_number": attempt_number,
            "worker_id": worker_id,
            "started_at": _required_timestamp(row, "started_at", "queued_at"),
            "finished_at": _required_timestamp(row, "finished_at"),
            "exit_code": exit_code,
            "diagnostic": "",
        }
        semantic_result_json = {
            "metricName": metric_name,
            "metricValue": metric_value,
            "provenance": provenance,
        }
        result = {
            "id": result_id,
            "job_id": job_id,
            "user_id": owner,
            "profile_sha256": str(profile_hash).lower(),
            "result_json": semantic_result_json,
            "primary_metric_name": metric_name,
            "primary_metric_value": metric_value,
            "compiler_revision": compiler,
            "runtime_revision": runtime,
            "provenance_json": provenance,
            "created_at": _required_timestamp(row, "finished_at"),
        }
    except MigrationError:
        return _reject(base, "INVALID_TIMESTAMP")
    return _accept(
        base,
        [
            ("simc.source_snapshots", snapshot),
            ("simc.simulation_jobs", job),
            ("simc.simulation_attempts", attempt),
            ("simc.simulation_results", result),
        ],
        "SEMANTIC_LEGACY_SIMC",
    )


def _convert_record(record: Mapping[str, Any], base: MigrationDecision, context: _Context):
    if base.status == "rejected":
        return base, []
    table = base.source_table
    if table == "identity.users":
        return _convert_identity_user(record, base, context)
    if table == "identity.user_identities":
        return _convert_identity(record, base, context)
    if table in {"chat.conversations", "app.chickenbro_sessions"}:
        return _convert_conversation(record, base, context)
    if table in {"chat.messages", "app.chickenbro_messages"}:
        return _convert_message(record, base, context)
    if table in {"chat.agent_runs", "app.agent_jobs"}:
        return _convert_agent_run(record, base, context)
    if table == "simc.source_snapshots":
        return _convert_snapshot(record, base, context)
    if table == "simc.simulation_jobs":
        return _convert_job(record, base, context)
    if table == "simc.simulation_attempts":
        return _convert_attempt(record, base, context)
    if table == "simc.simulation_results":
        return _convert_result(record, base, context)
    if table == "app.simulator_tasks":
        return _convert_legacy_simc(record, base, context)
    return _reject(base, "DOMAIN_NOT_MIGRATED")


def _source_snapshot_hash(records: Sequence[Mapping[str, Any]]) -> str:
    summaries = [
        {
            "table": str(record.get("table") or ""),
            "pkHash": source_primary_key_hash(record),
            "contentHash": content_hash(_record_row(record)),
            "updatedAt": _record_timestamp(record).isoformat().replace("+00:00", "Z"),
        }
        for record in records
    ]
    return content_hash(sorted(summaries, key=canonical_json))


def source_snapshot_hash(records: Iterable[Mapping[str, Any]], report: MigrationReport) -> str:
    selected = _select_window(
        list(records),
        MINIMUM_WATERMARK if report.mode == "full" else None,
        None,
        report_decisions=report.decisions,
    )
    return _source_snapshot_hash(selected)


def _select_window(
    records: Sequence[Mapping[str, Any]],
    after: MigrationWatermark | None,
    through: MigrationWatermark | None,
    *,
    report_decisions: Sequence[MigrationDecision] | None = None,
) -> list[Mapping[str, Any]]:
    if report_decisions is not None:
        keys = {(item.source_table, item.source_primary_key_hash) for item in report_decisions}
        return [
            record for record in records
            if (str(record.get("table") or ""), source_primary_key_hash(record)) in keys
        ]
    if through is None:
        raise MigrationError("THROUGH_WATERMARK_REQUIRED")
    lower = after.position() if after else MINIMUM_WATERMARK.position()
    upper = through.position()
    if lower >= upper:
        raise MigrationError("INVALID_WATERMARK_RANGE")
    return [record for record in records if lower < _record_position(record) <= upper]


def _ordered(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    rank = {table: index for index, table in enumerate(SOURCE_ORDER)}
    return sorted(
        records,
        key=lambda record: (
            rank.get(str(record.get("table") or ""), len(rank)),
            _record_position(record),
            source_primary_key_hash(record),
        ),
    )


def _message_order_hashes(expected_rows: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, str]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in expected_rows.get("chat.messages", {}).values():
        grouped[str(row["conversation_id"])].append(row)
    output = {}
    for conversation_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: (str(row["created_at"]), str(row["id"])))
        output[conversation_id] = content_hash([
            {
                "id": row["id"],
                "userId": row["user_id"],
                "role": row["role"],
                "contentHash": content_hash(row["content"]),
                "createdAt": row["created_at"],
            }
            for row in ordered
        ])
    return output


def _migrate(
    records: Iterable[Mapping[str, Any]],
    target: MigrationTarget,
    *,
    mode: Literal["full", "delta"],
    after: MigrationWatermark | None,
    through: MigrationWatermark,
) -> MigrationReport:
    all_records = [deepcopy(dict(record)) for record in records]
    selected = _select_window(all_records, after, through)
    context_records = _select_window(all_records, None, through)
    context = _Context(context_records, target)
    decisions: list[MigrationDecision] = []
    expected_rows: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)

    for record in _ordered(selected):
        base = classify_record(record)
        decision, rows = _convert_record(record, base, context)
        decisions.append(decision)
        if decision.status != "accepted":
            continue
        for table, row in rows:
            target.upsert(table, row, mutable=table in MUTABLE_TARGET_TABLES)
            expected_rows[table][str(row["id"])] = deepcopy(row)
        target.record_mapping(decision)

    accepted = [item for item in decisions if item.status == "accepted"]
    rejected = [item for item in decisions if item.status == "rejected"]
    accepted_by_table = Counter(item.source_table for item in accepted)
    rejected_by_table = Counter(item.source_table for item in rejected)
    reasons = Counter(item.reason for item in rejected)
    expected_hashes = {
        table: {target_id: content_hash(row) for target_id, row in sorted(rows.items())}
        for table, rows in sorted(expected_rows.items())
    }
    target_table_hashes = {
        table: content_hash(mapping)
        for table, mapping in expected_hashes.items()
    }
    public_accepted = [item.to_public_dict() for item in accepted]
    public_rejected = [item.to_public_dict() for item in rejected]
    return MigrationReport(
        mode=mode,
        migration_revision=MIGRATION_REVISION,
        source_snapshot_hash=_source_snapshot_hash(selected),
        from_watermark_hash=(after or MINIMUM_WATERMARK).public_hash(),
        through_watermark_hash=through.public_hash(),
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        accepted_hash=content_hash(public_accepted),
        rejected_hash=content_hash(public_rejected),
        accepted_by_source_table=dict(sorted(accepted_by_table.items())),
        rejected_by_source_table=dict(sorted(rejected_by_table.items())),
        reason_counts=dict(sorted(reasons.items())),
        target_counts={table: len(rows) for table, rows in sorted(expected_rows.items())},
        target_table_hashes=target_table_hashes,
        decisions=tuple(decisions),
        expected_target_hashes=expected_hashes,
        message_order_hashes=_message_order_hashes(expected_rows),
    )


def migrate_full(
    source: Iterable[Mapping[str, Any]],
    target: MigrationTarget,
    watermark: MigrationWatermark,
) -> MigrationReport:
    return _migrate(source, target, mode="full", after=None, through=watermark)


def migrate_delta(
    source: Iterable[Mapping[str, Any]],
    target: MigrationTarget,
    from_watermark: MigrationWatermark,
    through_watermark: MigrationWatermark,
) -> MigrationReport:
    return _migrate(
        source,
        target,
        mode="delta",
        after=from_watermark,
        through=through_watermark,
    )


__all__ = [
    "InMemoryMigrationTarget",
    "MIGRATION_REVISION",
    "MigrationDecision",
    "MigrationError",
    "MigrationReport",
    "MigrationTarget",
    "MigrationWatermark",
    "canonical_json",
    "classify_record",
    "content_hash",
    "migrate_delta",
    "migrate_full",
    "source_snapshot_hash",
    "stable_target_uuid",
]
