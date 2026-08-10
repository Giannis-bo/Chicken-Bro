#!/usr/bin/env python3
"""Typed canonical request and PostgreSQL function boundary for exact imports."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping
import uuid

try:
    from .gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from .gear_contracts import parse_exact_loadout_intent
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from gear_contracts import parse_exact_loadout_intent


REQUEST_SCHEMA_REVISION = "exact-import-job-request-v1"
REQUEST_V2_SCHEMA_REVISION = "exact-import-job-request-v2"
REQUEST_V3_SCHEMA_REVISION = "exact-import-job-request-v3"
RETRY_POLICY_REVISION = "exact-import-retry-policy-v1"
REQUEST_KEY_PREFIX = "exact-import-request:sha256:"
DEPENDENCY_VECTOR_KEYS = frozenset({
    "seasonRevision",
    "gameBuild",
    "gearRuleRevision",
    "resolverRevision",
    "compilerRevision",
    "workerRevision",
    "simcRuntimeRevision",
    "effectAuthorityRevision",
})
SENSITIVE_KEYS = frozenset({
    "rawProfile",
    "rawString",
    "playerName",
    "characterName",
    "realm",
    "server",
})
_OWNER_KEY_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUEST_KEY = re.compile(r"^exact-import-request:sha256:[0-9a-f]{64}$")
_RESOLVED_LOADOUT_V2_KEY = re.compile(r"^resolved-loadout-v2:sha256:[0-9a-f]{64}$")
_SIMULATION_SNAPSHOT_V2_KEY = re.compile(r"^simulation-snapshot-v2:sha256:[0-9a-f]{64}$")
_RESOLVED_LOADOUT_V3_KEY = re.compile(r"^resolved-loadout-v3:sha256:[0-9a-f]{64}$")
_SIMULATION_SNAPSHOT_V3_KEY = re.compile(r"^simulation-snapshot-v3:sha256:[0-9a-f]{64}$")
_RUNTIME_RELEASE_KEY = re.compile(r"^exact-runtime-authority-release:sha256:[0-9a-f]{64}$")
_RESOLVER_CONTEXT_KEY = re.compile(r"^exact-runtime-resolver-context:sha256:[0-9a-f]{64}$")
_SNAPSHOT_ROW_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_V1_REQUEST_FIELDS = frozenset({
    "schemaRevision", "exactLoadoutIntent", "dependencyVector",
})
_V2_REQUEST_FIELDS = _V1_REQUEST_FIELDS | frozenset({
    "resolvedLoadoutKey", "simulationSnapshotKey", "snapshotRowHash",
})
_V3_REQUEST_FIELDS = _V2_REQUEST_FIELDS | frozenset({
    "runtimeAuthorityReleaseKey", "resolverContextKey",
})
_MAX_REQUEST_BYTES = 131_072
_MAX_RESULT_BYTES = 131_072
_MAX_PROBLEM_BYTES = 16_384


class ExactImportJobRequestError(ValueError):
    """A request cannot enter the canonical exact-import language."""


class GearExactImportJobStoreIntegrityError(RuntimeError):
    """A persisted job row fails its typed bytes/key or state boundary."""


@dataclass(frozen=True)
class ExactSnapshotReference:
    """The one immutable v2 snapshot a worker may reload for a job."""

    resolved_loadout_key: str
    simulation_snapshot_key: str
    snapshot_row_hash: str
    runtime_authority_release_key: str | None = None
    resolver_context_key: str | None = None


@dataclass(frozen=True)
class ExactImportJobRequest:
    request_key: str
    canonical_bytes: bytes
    request_json: dict[str, Any]
    snapshot_reference: ExactSnapshotReference | None = None


def _canonical_json(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _find_sensitive_key(value: Any, path: str = "request") -> tuple[str, str] | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in SENSITIVE_KEYS:
                return key, f"{path}.{key}"
            found = _find_sensitive_key(nested, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found = _find_sensitive_key(nested, f"{path}.{index}")
            if found is not None:
                return found
    return None


def _dependency_vector(raw: Any) -> dict[str, str]:
    if type(raw) is not dict or set(raw) != DEPENDENCY_VECTOR_KEYS:
        raise ExactImportJobRequestError(
            "dependencyVector must contain exactly the eight frozen revision keys",
        )
    canonical: dict[str, str] = {}
    for key in sorted(DEPENDENCY_VECTOR_KEYS):
        try:
            canonical[key] = canonical_identity_token(
                raw[key],
                path=f"request.dependencyVector.{key}",
                max_bytes=256,
            )
        except CanonicalValueError as error:
            raise ExactImportJobRequestError(str(error)) from error
    return canonical


def _snapshot_reference(raw: Any) -> ExactSnapshotReference:
    if type(raw) is not dict or set(raw) not in ({
        "resolvedLoadoutKey", "simulationSnapshotKey", "snapshotRowHash",
    }, {
        "resolvedLoadoutKey", "simulationSnapshotKey", "snapshotRowHash",
        "runtimeAuthorityReleaseKey", "resolverContextKey",
    }):
        raise ExactImportJobRequestError(
            "snapshot reference must contain one sealed v2 or v3 identity set",
        )
    resolved_loadout_key = raw["resolvedLoadoutKey"]
    simulation_snapshot_key = raw["simulationSnapshotKey"]
    snapshot_row_hash = raw["snapshotRowHash"]
    is_v3 = "runtimeAuthorityReleaseKey" in raw
    if (
        type(resolved_loadout_key) is not str
        or (_RESOLVED_LOADOUT_V3_KEY if is_v3 else _RESOLVED_LOADOUT_V2_KEY).fullmatch(resolved_loadout_key) is None
    ):
        raise ExactImportJobRequestError("invalid resolvedLoadoutKey")
    if (
        type(simulation_snapshot_key) is not str
        or (_SIMULATION_SNAPSHOT_V3_KEY if is_v3 else _SIMULATION_SNAPSHOT_V2_KEY).fullmatch(simulation_snapshot_key) is None
    ):
        raise ExactImportJobRequestError("invalid simulationSnapshotKey")
    if (
        type(snapshot_row_hash) is not str
        or _SNAPSHOT_ROW_HASH.fullmatch(snapshot_row_hash) is None
    ):
        raise ExactImportJobRequestError("invalid snapshotRowHash")
    release_key = raw.get("runtimeAuthorityReleaseKey")
    context_key = raw.get("resolverContextKey")
    if is_v3 and (
        type(release_key) is not str or _RUNTIME_RELEASE_KEY.fullmatch(release_key) is None
        or type(context_key) is not str or _RESOLVER_CONTEXT_KEY.fullmatch(context_key) is None
    ):
        raise ExactImportJobRequestError("invalid runtime authority reference")
    return ExactSnapshotReference(
        resolved_loadout_key=resolved_loadout_key,
        simulation_snapshot_key=simulation_snapshot_key,
        snapshot_row_hash=snapshot_row_hash,
        runtime_authority_release_key=release_key if is_v3 else None,
        resolver_context_key=context_key if is_v3 else None,
    )


def build_exact_import_job_request(
    exact_loadout_intent: Any,
    dependency_vector: Any,
    *,
    snapshot_reference: Any = None,
) -> ExactImportJobRequest:
    """Validate the Exact intent and seal the one accepted request representation."""

    sensitive = _find_sensitive_key({
        "exactLoadoutIntent": exact_loadout_intent,
        "dependencyVector": dependency_vector,
        "snapshotReference": snapshot_reference,
    })
    if sensitive is not None:
        key, path = sensitive
        raise ExactImportJobRequestError(f"forbidden sensitive field {key} at {path}")

    canonical_intent, issues = parse_exact_loadout_intent(exact_loadout_intent)
    if canonical_intent is None or issues:
        raise ExactImportJobRequestError(
            "invalid canonical Exact intent: "
            + ",".join(str(issue.get("code") or "INVALID_INTENT") for issue in issues),
        )
    if canonical_intent != exact_loadout_intent:
        raise ExactImportJobRequestError("exactLoadoutIntent is not already canonical")

    sealed_snapshot_reference = None
    payload = {
        "schemaRevision": REQUEST_SCHEMA_REVISION,
        "exactLoadoutIntent": canonical_intent,
        "dependencyVector": _dependency_vector(dependency_vector),
    }
    if snapshot_reference is not None:
        sealed_snapshot_reference = _snapshot_reference(snapshot_reference)
        payload.update({
            "schemaRevision": (
                REQUEST_V3_SCHEMA_REVISION
                if sealed_snapshot_reference.runtime_authority_release_key
                else REQUEST_V2_SCHEMA_REVISION
            ),
            "resolvedLoadoutKey": sealed_snapshot_reference.resolved_loadout_key,
            "simulationSnapshotKey": sealed_snapshot_reference.simulation_snapshot_key,
            "snapshotRowHash": sealed_snapshot_reference.snapshot_row_hash,
        })
        if sealed_snapshot_reference.runtime_authority_release_key:
            payload.update({
                "runtimeAuthorityReleaseKey": sealed_snapshot_reference.runtime_authority_release_key,
                "resolverContextKey": sealed_snapshot_reference.resolver_context_key,
            })
    canonical_payload = _canonical_json(payload)
    raw = _canonical_bytes(canonical_payload)
    if not 2 <= len(raw) <= _MAX_REQUEST_BYTES:
        raise ExactImportJobRequestError("canonical request exceeds the 131072-byte bound")
    request_key = REQUEST_KEY_PREFIX + hashlib.sha256(raw).hexdigest()
    return ExactImportJobRequest(
        request_key=request_key,
        canonical_bytes=raw,
        request_json=canonical_payload,
        snapshot_reference=sealed_snapshot_reference,
    )


def reload_exact_import_job_request(
    request_key: Any,
    request_bytes: Any,
    request_json: Any,
) -> ExactImportJobRequest:
    """Recompute the full typed request boundary from one claimed database row."""

    try:
        if type(request_key) is not str or _REQUEST_KEY.fullmatch(request_key) is None:
            raise GearExactImportJobStoreIntegrityError("invalid exact import request key")
        if isinstance(request_bytes, memoryview):
            request_bytes = request_bytes.tobytes()
        if type(request_bytes) is not bytes or not 2 <= len(request_bytes) <= _MAX_REQUEST_BYTES:
            raise GearExactImportJobStoreIntegrityError("invalid exact import request bytes")
        if type(request_json) is not dict:
            raise GearExactImportJobStoreIntegrityError("invalid exact import request JSON")
        decoded = json.loads(request_bytes.decode("utf-8"))
        if type(decoded) is not dict or decoded != request_json:
            raise GearExactImportJobStoreIntegrityError("request bytes/JSON drift")
        schema_revision = decoded.get("schemaRevision")
        if schema_revision == REQUEST_SCHEMA_REVISION:
            if set(decoded) != _V1_REQUEST_FIELDS:
                raise GearExactImportJobStoreIntegrityError("request schema drift")
            snapshot_reference = None
        elif schema_revision == REQUEST_V2_SCHEMA_REVISION:
            if set(decoded) != _V2_REQUEST_FIELDS:
                raise GearExactImportJobStoreIntegrityError("request schema drift")
            snapshot_reference = {
                "resolvedLoadoutKey": decoded.get("resolvedLoadoutKey"),
                "simulationSnapshotKey": decoded.get("simulationSnapshotKey"),
                "snapshotRowHash": decoded.get("snapshotRowHash"),
            }
        elif schema_revision == REQUEST_V3_SCHEMA_REVISION:
            if set(decoded) != _V3_REQUEST_FIELDS:
                raise GearExactImportJobStoreIntegrityError("request schema drift")
            snapshot_reference = {
                "resolvedLoadoutKey": decoded.get("resolvedLoadoutKey"),
                "simulationSnapshotKey": decoded.get("simulationSnapshotKey"),
                "snapshotRowHash": decoded.get("snapshotRowHash"),
                "runtimeAuthorityReleaseKey": decoded.get("runtimeAuthorityReleaseKey"),
                "resolverContextKey": decoded.get("resolverContextKey"),
            }
        else:
            raise GearExactImportJobStoreIntegrityError("request schema drift")
        rebuilt = build_exact_import_job_request(
            decoded.get("exactLoadoutIntent"),
            decoded.get("dependencyVector"),
            snapshot_reference=snapshot_reference,
        )
        if rebuilt.request_key != request_key or rebuilt.canonical_bytes != request_bytes:
            raise GearExactImportJobStoreIntegrityError("request bytes/key drift")
        return rebuilt
    except GearExactImportJobStoreIntegrityError:
        raise
    except (ExactImportJobRequestError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GearExactImportJobStoreIntegrityError(
            "claimed exact import request is not canonical",
        ) from error


def _exact_text(value: Any, *, field: str, max_bytes: int = 256) -> str:
    try:
        return canonical_identity_token(value, path=field, max_bytes=max_bytes)
    except CanonicalValueError as error:
        raise GearExactImportJobStoreIntegrityError(f"invalid {field}") from error


def _owner_hash(value: Any) -> str:
    if type(value) is not str or _OWNER_KEY_HASH.fullmatch(value) is None:
        raise GearExactImportJobStoreIntegrityError("invalid owner_key_hash")
    return value


def _job_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GearExactImportJobStoreIntegrityError("invalid job_id")
    return value


def _lock_token(value: Any) -> uuid.UUID:
    try:
        token = value if type(value) is uuid.UUID else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise GearExactImportJobStoreIntegrityError("invalid lock_token") from error
    return token


def _bounded_object(value: Any, *, field: str, max_bytes: int, nullable: bool) -> Any:
    if value is None and nullable:
        return None
    if type(value) is not dict:
        raise GearExactImportJobStoreIntegrityError(f"{field} must be an object")
    canonical = _canonical_json(value)
    if len(_canonical_bytes(canonical)) > max_bytes:
        raise GearExactImportJobStoreIntegrityError(f"{field} exceeds its byte bound")
    if _find_sensitive_key(canonical, field) is not None:
        raise GearExactImportJobStoreIntegrityError(f"{field} contains sensitive identity data")
    return canonical


class GearExactImportJobStore:
    """Invoke only the fixed 0032 function surface; no direct table DML."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    def enqueue(self, owner_key_hash: Any, request: Any) -> dict[str, Any]:
        owner = _owner_hash(owner_key_hash)
        if type(request) is not ExactImportJobRequest:
            raise GearExactImportJobStoreIntegrityError("request must be typed")
        request = reload_exact_import_job_request(
            request.request_key,
            request.canonical_bytes,
            request.request_json,
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ops.websim_exact_enqueue(%s, %s, %s::jsonb)
                    """,
                    (
                        owner,
                        request.canonical_bytes,
                        json.dumps(request.request_json, ensure_ascii=False),
                    ),
                )
                row = cur.fetchone()
        if not row or len(row) != 5:
            raise GearExactImportJobStoreIntegrityError("enqueue returned no job")
        return {
            "jobId": _job_id(row[0]),
            "requestKey": str(row[1]),
            "status": str(row[2]),
            "reused": row[3] is True,
            "cooldownUntil": row[4],
        }

    def read(self, owner_key_hash: Any, job_id: Any) -> dict[str, Any] | None:
        owner = _owner_hash(owner_key_hash)
        identifier = _job_id(job_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ops.websim_exact_read(%s, %s)",
                    (owner, identifier),
                )
                row = cur.fetchone()
        if row is None:
            return None
        if len(row) != 9:
            raise GearExactImportJobStoreIntegrityError("read returned malformed job")
        return {
            "jobId": _job_id(row[0]),
            "requestKey": str(row[1]),
            "status": str(row[2]),
            "resultJson": row[3],
            "problemJson": row[4],
            "queuedAt": row[5],
            "startedAt": row[6],
            "finishedAt": row[7],
            "cooldownUntil": row[8],
        }

    def claim_next(
        self,
        worker_id: Any,
        worker_revision: Any,
        simc_runtime_revision: Any,
    ) -> dict[str, Any] | None:
        worker = _exact_text(worker_id, field="worker_id", max_bytes=160)
        revision = _exact_text(worker_revision, field="worker_revision")
        simc_revision = _exact_text(
            simc_runtime_revision,
            field="simc_runtime_revision",
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ops.websim_exact_claim(%s, %s, %s)",
                    (worker, revision, simc_revision),
                )
                row = cur.fetchone()
        if row is None:
            return None
        if len(row) != 6:
            raise GearExactImportJobStoreIntegrityError("claim returned malformed job")
        typed_request = reload_exact_import_job_request(row[1], row[2], row[3])
        token = _lock_token(row[4])
        return {
            "jobId": _job_id(row[0]),
            "requestKey": typed_request.request_key,
            "request": typed_request,
            "lockToken": str(token),
            "leaseUntil": row[5],
        }

    def heartbeat(self, job_id: Any, lock_token: Any) -> dict[str, Any] | None:
        identifier = _job_id(job_id)
        token = _lock_token(lock_token)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ops.websim_exact_heartbeat(%s, %s)",
                    (identifier, token),
                )
                row = cur.fetchone()
        if row is None:
            return None
        if len(row) != 2 or _job_id(row[0]) != identifier:
            raise GearExactImportJobStoreIntegrityError("heartbeat returned malformed job")
        return {"jobId": identifier, "leaseUntil": row[1]}

    def terminalize(
        self,
        job_id: Any,
        lock_token: Any,
        *,
        terminal_status: Any,
        terminal_classification: Any,
        result_json: Any,
        problem_json: Any,
        catalog_status: Any,
    ) -> dict[str, Any] | None:
        identifier = _job_id(job_id)
        token = _lock_token(lock_token)
        status = str(terminal_status or "")
        classification = str(terminal_classification or "")
        allowed = {
            "resolved": {"resolved"},
            "blocked": {"incomplete", "illegal"},
            "unsupported": {"runtime_gap"},
            "failed": {"internal_error"},
        }
        if status not in allowed or classification not in allowed[status]:
            raise GearExactImportJobStoreIntegrityError("invalid terminal status/classification")
        result = _bounded_object(
            result_json,
            field="result_json",
            max_bytes=_MAX_RESULT_BYTES,
            nullable=True,
        )
        problem = _bounded_object(
            problem_json,
            field="problem_json",
            max_bytes=_MAX_PROBLEM_BYTES,
            nullable=True,
        )
        catalog = _exact_text(catalog_status, field="catalog_status")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ops.websim_exact_terminalize(
                        %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
                    )
                    """,
                    (
                        identifier,
                        token,
                        status,
                        classification,
                        None if result is None else json.dumps(result, ensure_ascii=False),
                        None if problem is None else json.dumps(problem, ensure_ascii=False),
                        catalog,
                    ),
                )
                row = cur.fetchone()
        if row is None:
            return None
        if len(row) != 4 or _job_id(row[0]) != identifier:
            raise GearExactImportJobStoreIntegrityError("terminalize returned malformed job")
        return {
            "jobId": identifier,
            "status": str(row[1]),
            "finishedAt": row[2],
            "cooldownUntil": row[3],
        }

    def update_worker_state(
        self,
        *,
        worker_id: Any,
        status: Any,
        worker_revision: Any,
        simc_runtime_revision: Any,
        current_job_id: Any = None,
        last_outcome_json: Any = None,
    ) -> None:
        worker = _exact_text(worker_id, field="worker_id", max_bytes=160)
        state = _exact_text(status, field="worker_status", max_bytes=32)
        revision = _exact_text(worker_revision, field="worker_revision")
        simc_revision = _exact_text(simc_runtime_revision, field="simc_runtime_revision")
        current = None if current_job_id is None else _job_id(current_job_id)
        outcome = _bounded_object(
            last_outcome_json,
            field="last_outcome_json",
            max_bytes=_MAX_PROBLEM_BYTES,
            nullable=True,
        )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ops.websim_exact_update_worker_state("
                    "%s, %s, %s, %s, %s, %s::jsonb)",
                    (
                        worker,
                        state,
                        revision,
                        simc_revision,
                        current,
                        None if outcome is None else json.dumps(outcome, ensure_ascii=False),
                    ),
                )

    def prune_jobs(self, limit_rows: Any) -> int:
        return self._prune("ops.websim_exact_prune_jobs", limit_rows)

    def prune_metrics(self, limit_rows: Any) -> int:
        return self._prune("ops.websim_exact_prune_metrics", limit_rows)

    def _prune(self, function: str, limit_rows: Any) -> int:
        if isinstance(limit_rows, bool) or not isinstance(limit_rows, int) or not 1 <= limit_rows <= 100:
            raise GearExactImportJobStoreIntegrityError("prune limit must be 1..100")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT {function}(%s)", (limit_rows,))
                row = cur.fetchone()
        if not row or isinstance(row[0], bool) or not isinstance(row[0], int):
            raise GearExactImportJobStoreIntegrityError("prune returned invalid count")
        return row[0]


__all__ = [
    "DEPENDENCY_VECTOR_KEYS",
    "ExactImportJobRequest",
    "ExactImportJobRequestError",
    "GearExactImportJobStore",
    "GearExactImportJobStoreIntegrityError",
    "REQUEST_SCHEMA_REVISION",
    "RETRY_POLICY_REVISION",
    "SENSITIVE_KEYS",
    "build_exact_import_job_request",
    "reload_exact_import_job_request",
]
