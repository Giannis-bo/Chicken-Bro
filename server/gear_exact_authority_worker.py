#!/usr/bin/env python3
"""Dormant dedicated-role worker for owner-scoped exact import jobs."""

from __future__ import annotations

import copy
import os
import re
import signal
import socket
import threading
from typing import Any, Callable, Mapping

try:
    from .db import connect_postgres
    from .gear_exact_import_job_store import (
        DEPENDENCY_VECTOR_KEYS,
        ExactImportJobRequest,
        GearExactImportJobStore,
        GearExactImportJobStoreIntegrityError,
        REQUEST_V2_SCHEMA_REVISION,
        REQUEST_V3_SCHEMA_REVISION,
    )
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from db import connect_postgres
    from gear_exact_import_job_store import (
        DEPENDENCY_VECTOR_KEYS,
        ExactImportJobRequest,
        GearExactImportJobStore,
        GearExactImportJobStoreIntegrityError,
        REQUEST_V2_SCHEMA_REVISION,
        REQUEST_V3_SCHEMA_REVISION,
    )


WORKER_REVISION = "exact-authority-worker-v1"
WORKER_ROLE = "wow_exact_worker"
_SIMULATION_SNAPSHOT_V3_SCHEMA_REVISION = "simulation-snapshot-v3"
_RESULT_IDENTITY = re.compile(r"^simc-result:sha256:[0-9a-f]{64}$")
_PRIVATE_RESULT_KEYS = frozenset({
    "rawProfile", "rawString", "playerName", "characterName", "realm",
    "server", "userId", "user_id", "ownerKeyHash", "owner_key_hash",
})


class WorkerConfigurationError(RuntimeError):
    """The dedicated worker environment is absent or mixed with the app DSN."""


class WorkerRoleError(RuntimeError):
    """The connection cannot prove the pre-provisioned role boundary."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def worker_database_url_from_env(environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    if _text(environment.get("WOW_DATABASE_URL")):
        raise WorkerConfigurationError(
            "exact authority worker refuses public WOW_DATABASE_URL",
        )
    dedicated = _text(environment.get("WOW_EXACT_WORKER_DATABASE_URL"))
    if not dedicated:
        raise WorkerConfigurationError(
            "WOW_EXACT_WORKER_DATABASE_URL is required",
        )
    return dedicated


def establish_exact_worker_role(connection: Any) -> None:
    """SET ROLE first, then prove the complete least-privilege role boundary."""

    with connection.cursor() as cur:
        cur.execute("SET ROLE wow_exact_worker")
        cur.execute(
            """
            SELECT
                session_user,
                current_user,
                pg_catalog.pg_has_role(
                    session_user,
                    'wow_exact_worker',
                    'MEMBER'
                ),
                login_role.rolcanlogin,
                login_role.rolinherit,
                login_role.rolsuper,
                login_role.rolcreatedb,
                login_role.rolcreaterole,
                login_role.rolreplication,
                login_role.rolbypassrls,
                worker_role.rolcanlogin,
                worker_role.rolsuper,
                worker_role.rolcreatedb,
                worker_role.rolcreaterole,
                worker_role.rolreplication,
                worker_role.rolbypassrls,
                pg_catalog.pg_has_role(
                    'wow_app',
                    'wow_exact_worker',
                    'MEMBER'
                ),
                pg_catalog.pg_has_role(
                    'wow_migrator',
                    'wow_exact_worker',
                    'MEMBER'
                )
            FROM pg_catalog.pg_roles AS login_role
            CROSS JOIN pg_catalog.pg_roles AS worker_role
            WHERE login_role.rolname = session_user
              AND worker_role.rolname = 'wow_exact_worker'
            """
        )
        row = cur.fetchone()
    if (
        not row
        or len(row) != 18
        or row[0] in {WORKER_ROLE, "wow_app", "wow_migrator"}
        or row[1] != WORKER_ROLE
        or row[2] is not True
        or row[3] is not True
        or row[4] is not True
        or any(value is not False for value in row[5:18])
    ):
        raise WorkerRoleError(
            "worker connection must be a dedicated LOGIN INHERIT least-privilege "
            "member with an isolated least-privilege wow_exact_worker group",
        )


def dedicated_worker_connection_factory(
    database_url: str,
    *,
    connect: Callable[[str], Any] = connect_postgres,
) -> Callable[[], Any]:
    if not _text(database_url):
        raise WorkerConfigurationError("dedicated worker database URL is required")

    def factory():
        connection = connect(database_url)
        try:
            establish_exact_worker_role(connection)
        except Exception:
            connection.close()
            raise
        return connection

    return factory


def _internal_error_outcome() -> dict[str, Any]:
    return {
        "terminalStatus": "failed",
        "terminalClassification": "internal_error",
        "resultJson": None,
        "problemJson": {"code": "EXACT_IMPORT_INTERNAL_ERROR"},
        "catalogStatus": "unknown",
    }


def unavailable_processor(_request: ExactImportJobRequest) -> dict[str, Any]:
    """Fail closed until a later task authorizes an exact authority processor."""

    return {
        "terminalStatus": "unsupported",
        "terminalClassification": "runtime_gap",
        "resultJson": None,
        "problemJson": {"code": "EXACT_IMPORT_PROCESSOR_UNAVAILABLE"},
        "catalogStatus": "unknown",
    }


def _snapshot_blocked_outcome(code: str) -> dict[str, Any]:
    return {
        "terminalStatus": "blocked",
        "terminalClassification": "incomplete",
        "resultJson": None,
        "problemJson": {"code": code},
        "catalogStatus": "unknown",
    }


def _snapshot_unsupported_outcome(code: str) -> dict[str, Any]:
    return {
        "terminalStatus": "unsupported",
        "terminalClassification": "runtime_gap",
        "resultJson": None,
        "problemJson": {"code": code},
        "catalogStatus": "unknown",
    }


def _snapshot_internal_error_outcome(code: str) -> dict[str, Any]:
    return {
        "terminalStatus": "failed",
        "terminalClassification": "internal_error",
        "resultJson": None,
        "problemJson": {"code": code},
        "catalogStatus": "unknown",
    }


def _contains_private_result_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _PRIVATE_RESULT_KEYS or _contains_private_result_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_private_result_key(nested) for nested in value)
    return False


def snapshot_bound_processor(
    *,
    snapshot_store: Any,
    simc_runtime_revision: str,
    runner: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> Callable[[ExactImportJobRequest], dict[str, Any]]:
    """Return the only worker processor allowed to run a sealed V3 snapshot.

    The claimed request already passed the database function boundary.  This
    processor repeats the critical identity checks against the single named
    persisted snapshot, so no worker branch can infer a snapshot from an
    intent, use a latest row, or replay materialization.
    """

    runtime_revision = _text(simc_runtime_revision)
    if not runtime_revision:
        raise WorkerConfigurationError("pinned SimC runtime revision is required")

    def processor(request: ExactImportJobRequest) -> dict[str, Any]:
        reference = request.snapshot_reference
        schema_revision = request.request_json.get("schemaRevision")
        if schema_revision != REQUEST_V3_SCHEMA_REVISION:
            code = (
                "EXACT_IMPORT_REQUEST_V1_UNSUPPORTED"
                if schema_revision != REQUEST_V2_SCHEMA_REVISION
                else "EXACT_IMPORT_REQUEST_V2_UNSUPPORTED"
            )
            return _snapshot_unsupported_outcome(
                code,
            )
        if (
            reference is None
            or not reference.runtime_authority_release_key
            or not reference.resolver_context_key
        ):
            return _snapshot_blocked_outcome(
                "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH",
            )
        dependency_vector = request.request_json.get("dependencyVector")
        if (
            not isinstance(dependency_vector, Mapping)
            or set(dependency_vector) != DEPENDENCY_VECTOR_KEYS
            or dependency_vector.get("simcRuntimeRevision") != runtime_revision
        ):
            return _snapshot_unsupported_outcome("EXACT_IMPORT_RUNTIME_MISMATCH")
        try:
            snapshot = snapshot_store.load_snapshot(
                reference.simulation_snapshot_key,
                include_result=False,
            )
        except Exception:
            return _snapshot_blocked_outcome("EXACT_IMPORT_SNAPSHOT_UNAVAILABLE")
        if not isinstance(snapshot, Mapping) or not snapshot:
            return _snapshot_blocked_outcome("EXACT_IMPORT_SNAPSHOT_UNAVAILABLE")
        if (
            snapshot.get("schemaRevision") != _SIMULATION_SNAPSHOT_V3_SCHEMA_REVISION
            or snapshot.get("status") != "ready"
            or snapshot.get("simulationSnapshotKey")
                != reference.simulation_snapshot_key
            or snapshot.get("resolvedLoadoutKey")
                != reference.resolved_loadout_key
            or snapshot.get("rowHash") != reference.snapshot_row_hash
            or snapshot.get("runtimeAuthorityReleaseKey")
                != reference.runtime_authority_release_key
            or snapshot.get("resolverContextKey") != reference.resolver_context_key
            or snapshot.get("dependencyVector") != dependency_vector
        ):
            return _snapshot_blocked_outcome(
                "EXACT_IMPORT_SNAPSHOT_REFERENCE_MISMATCH",
            )
        if snapshot.get("simcRuntimeRevision") != runtime_revision:
            return _snapshot_unsupported_outcome("EXACT_IMPORT_RUNTIME_MISMATCH")
        try:
            runner_result = runner(copy.deepcopy(dict(snapshot)))
        except Exception:
            return _snapshot_internal_error_outcome("EXACT_IMPORT_RUNNER_FAILED")
        if not isinstance(runner_result, Mapping) or _contains_private_result_key(runner_result):
            return _snapshot_internal_error_outcome("EXACT_IMPORT_RUNNER_INVALID")
        try:
            bound = snapshot_store.bind_result(
                reference.simulation_snapshot_key,
                dict(runner_result),
            )
        except Exception:
            return _snapshot_internal_error_outcome("EXACT_IMPORT_RESULT_BIND_FAILED")
        if (
            not isinstance(bound, Mapping)
            or bound.get("status") != "executed"
            or bound.get("simulationSnapshotKey")
                != reference.simulation_snapshot_key
            or bound.get("resolvedLoadoutKey")
                != reference.resolved_loadout_key
            or bound.get("snapshotRowHash") != reference.snapshot_row_hash
            or not isinstance(bound.get("resultIdentity"), str)
            or _RESULT_IDENTITY.fullmatch(bound["resultIdentity"]) is None
            or not isinstance(bound.get("result"), Mapping)
        ):
            return _snapshot_internal_error_outcome("EXACT_IMPORT_RESULT_BIND_INVALID")
        if bound["result"].get("status") != "completed":
            return _snapshot_internal_error_outcome("EXACT_IMPORT_RUNNER_FAILED")
        return {
            "terminalStatus": "resolved",
            "terminalClassification": "resolved",
            "resultJson": {
                "resultIdentity": bound["resultIdentity"],
                "status": "resolved",
                "simulationSnapshotKey": reference.simulation_snapshot_key,
            },
            "problemJson": None,
            "catalogStatus": "unknown",
        }

    return processor


def _validated_outcome(value: Any) -> dict[str, Any]:
    keys = {
        "terminalStatus",
        "terminalClassification",
        "resultJson",
        "problemJson",
        "catalogStatus",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        return _internal_error_outcome()
    return {key: value[key] for key in keys}


def process_claimed_job(
    job: Mapping[str, Any],
    *,
    store: GearExactImportJobStore,
    processor: Callable[[ExactImportJobRequest], Mapping[str, Any]] = unavailable_processor,
) -> dict[str, str]:
    """Process one typed claim and publish only through the token/lease CAS."""

    request = job.get("request")
    if type(request) is not ExactImportJobRequest:
        raise GearExactImportJobStoreIntegrityError("claimed request is not typed")
    try:
        terminal = _validated_outcome(processor(request))
    except Exception:
        terminal = _internal_error_outcome()

    try:
        published = store.terminalize(
            int(job.get("jobId") or 0),
            _text(job.get("lockToken")),
            terminal_status=terminal["terminalStatus"],
            terminal_classification=terminal["terminalClassification"],
            result_json=terminal["resultJson"],
            problem_json=terminal["problemJson"],
            catalog_status=terminal["catalogStatus"],
        )
    except GearExactImportJobStoreIntegrityError:
        fallback = _internal_error_outcome()
        published = store.terminalize(
            int(job.get("jobId") or 0),
            _text(job.get("lockToken")),
            terminal_status=fallback["terminalStatus"],
            terminal_classification=fallback["terminalClassification"],
            result_json=fallback["resultJson"],
            problem_json=fallback["problemJson"],
            catalog_status=fallback["catalogStatus"],
        )
        terminal = fallback
    if published is None:
        return {"status": "abandoned", "code": "EXACT_IMPORT_LEASE_LOST"}
    status = terminal["terminalStatus"]
    code = {
        "resolved": "EXACT_IMPORT_RESOLVED",
        "blocked": "EXACT_IMPORT_BLOCKED",
        "unsupported": "EXACT_IMPORT_UNSUPPORTED",
        "failed": "EXACT_IMPORT_INTERNAL_ERROR",
    }[status]
    return {"status": status, "code": code}


def worker_identity(
    *,
    hostname: str = "",
    environ: Mapping[str, str] | None = None,
) -> str:
    environment = os.environ if environ is None else environ
    configured = _text(environment.get("WOW_EXACT_WORKER_ID"))
    return configured or f"{_text(hostname or socket.gethostname())}-exact-authority"


def main() -> int:
    database_url = worker_database_url_from_env()
    simc_runtime_revision = _text(
        os.environ.get("WOW_EXACT_WORKER_SIMC_RUNTIME_REVISION"),
    )
    if not simc_runtime_revision:
        raise WorkerConfigurationError(
            "WOW_EXACT_WORKER_SIMC_RUNTIME_REVISION is required",
        )
    poll_seconds = max(
        0.25,
        min(float(os.environ.get("WOW_EXACT_WORKER_POLL_SECONDS", "1")), 30.0),
    )
    store = GearExactImportJobStore(
        dedicated_worker_connection_factory(database_url),
    )
    identity = worker_identity()
    stopping = threading.Event()

    def stop(_signum, _frame) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping.is_set():
        store.update_worker_state(
            worker_id=identity,
            status="idle",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=simc_runtime_revision,
        )
        job = store.claim_next(identity, WORKER_REVISION, simc_runtime_revision)
        if job is None:
            stopping.wait(poll_seconds)
            continue
        store.update_worker_state(
            worker_id=identity,
            status="running",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=simc_runtime_revision,
            current_job_id=job["jobId"],
        )
        outcome = process_claimed_job(job, store=store)
        store.update_worker_state(
            worker_id=identity,
            status="idle",
            worker_revision=WORKER_REVISION,
            simc_runtime_revision=simc_runtime_revision,
            last_outcome_json=outcome,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
