import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from server.app.simulation.domain import (
    SimulationAttempt,
    SimulationJob,
    SimulationJobStatus,
    SimulationResult,
    SourceProvider,
    SourceReadiness,
    SourceSnapshot,
)
from server.app.worker.leases import LostLeaseError, enqueue_job, require_current_lease


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    return row[index]


def _json_value(value: object) -> object:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PostgresSimulationRepository:
    """Owner-scoped persistence for immutable source snapshots and SimC jobs."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def save_snapshot_with_next_revision(self, snapshot: SourceSnapshot) -> SourceSnapshot:
        """Serialize per-owner revision allocation and immutable snapshot insertion."""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM identity.users
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (snapshot.user_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("snapshot owner disappeared")
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(revision), 0) + 1 AS next_revision
                    FROM simc.source_snapshots
                    WHERE user_id = %s AND provider = %s AND source_key = %s
                    """,
                    (snapshot.user_id, snapshot.provider.value, snapshot.source_key),
                )
                revision_row = cursor.fetchone()
                if revision_row is None:
                    raise RuntimeError("snapshot revision could not be allocated")
                persisted = replace(
                    snapshot,
                    revision=int(_row_value(revision_row, "next_revision", 0)),
                )
                cursor.execute(
                    """
                    INSERT INTO simc.source_snapshots (
                        id, user_id, provider, source_url, source_key, revision,
                        readiness, snapshot_json, provenance_json, raw_sha256, fetched_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                    """,
                    (
                        persisted.id,
                        persisted.user_id,
                        persisted.provider.value,
                        persisted.source_url,
                        persisted.source_key,
                        persisted.revision,
                        persisted.readiness.value,
                        _json_value(persisted.snapshot),
                        _json_value(persisted.provenance),
                        persisted.raw_sha256,
                        persisted.fetched_at,
                    ),
                )
        return persisted

    def get_snapshot(self, user_id: UUID, snapshot_id: UUID) -> SourceSnapshot | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, provider, source_url, source_key, revision,
                           readiness, snapshot_json, provenance_json, raw_sha256, fetched_at
                    FROM simc.source_snapshots
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, snapshot_id),
                )
                row = cursor.fetchone()
        return self._snapshot_from_row(row) if row is not None else None

    def get_snapshot_for_job(self, user_id: UUID, snapshot_id: UUID) -> SourceSnapshot | None:
        return self.get_snapshot(user_id, snapshot_id)

    def create_job_and_enqueue(
        self,
        job: SimulationJob,
        *,
        payload: Mapping[str, object],
        max_attempts: int = 3,
    ) -> SimulationJob:
        """Create the immutable job identity and its queue command in one transaction."""
        if job.status is not SimulationJobStatus.QUEUED:
            raise ValueError("new simulation job must be queued")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO simc.simulation_jobs (
                        id, user_id, snapshot_id, scenario_hash, compiler_revision,
                        runtime_revision, idempotency_key, status, public_error_code,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, idempotency_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        job.id,
                        job.user_id,
                        job.snapshot_id,
                        job.scenario_hash,
                        job.compiler_revision,
                        job.runtime_revision,
                        job.idempotency_key,
                        job.status.value,
                        job.public_error_code,
                        job.created_at,
                        job.updated_at,
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """
                        SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                               runtime_revision, idempotency_key, status, public_error_code,
                               created_at, updated_at
                        FROM simc.simulation_jobs
                        WHERE user_id = %s AND idempotency_key = %s
                        FOR SHARE
                        """,
                        (job.user_id, job.idempotency_key),
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise RuntimeError("idempotent simulation job disappeared")
                    return self._job_from_row(existing)
                enqueue_job(
                    cursor,
                    job_id=job.id,
                    domain="simc",
                    command_type="run_simulation",
                    aggregate_id=job.id,
                    payload=payload,
                    max_attempts=max_attempts,
                )
        return job

    def get_job_by_idempotency(self, user_id: UUID, idempotency_key: str) -> SimulationJob | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                           runtime_revision, idempotency_key, status, public_error_code,
                           created_at, updated_at
                    FROM simc.simulation_jobs
                    WHERE user_id = %s AND idempotency_key = %s
                    """,
                    (user_id, idempotency_key),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row is not None else None

    def get_job(self, user_id: UUID, job_id: UUID) -> SimulationJob | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                           runtime_revision, idempotency_key, status, public_error_code,
                           created_at, updated_at
                    FROM simc.simulation_jobs
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, job_id),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row is not None else None

    def list_jobs(
        self,
        user_id: UUID,
        boundary: tuple[datetime, UUID] | None,
        limit: int,
    ) -> Sequence[SimulationJob]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                if boundary is None:
                    cursor.execute(
                        """
                        SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                               runtime_revision, idempotency_key, status, public_error_code,
                               created_at, updated_at
                        FROM simc.simulation_jobs
                        WHERE user_id = %s
                        ORDER BY updated_at DESC, id DESC LIMIT %s
                        """,
                        (user_id, limit),
                    )
                else:
                    updated_at, job_id = boundary
                    cursor.execute(
                        """
                        SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                               runtime_revision, idempotency_key, status, public_error_code,
                               created_at, updated_at
                        FROM simc.simulation_jobs
                        WHERE user_id = %s
                          AND (updated_at, id) < (%s, %s)
                        ORDER BY updated_at DESC, id DESC LIMIT %s
                        """,
                        (user_id, updated_at, job_id, limit),
                    )
                rows = cursor.fetchall()
        return [self._job_from_row(row) for row in rows]

    def list_attempts(self, job_id: UUID, limit: int = 20) -> Sequence[SimulationAttempt]:
        bounded_limit = min(max(int(limit), 1), 20)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, job_id, user_id, attempt_number, worker_id,
                           started_at, finished_at, exit_code, diagnostic
                    FROM simc.simulation_attempts
                    WHERE job_id = %s
                    ORDER BY attempt_number ASC, id ASC
                    LIMIT %s
                    """,
                    (job_id, bounded_limit),
                )
                rows = cursor.fetchall()
        return [self._attempt_from_row(row) for row in rows]

    def get_job_by_id(self, job_id: UUID) -> SimulationJob | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                           runtime_revision, idempotency_key, status, public_error_code,
                           created_at, updated_at
                    FROM simc.simulation_jobs
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row is not None else None

    def begin_job_attempt(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        attempt_number: int,
        now: datetime,
    ) -> tuple[SimulationJob, UUID | None] | None:
        """Claim one domain attempt while the matching queue lease is still owned."""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                require_current_lease(cursor, job_id, worker_id)
                cursor.execute(
                    """
                    SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                           runtime_revision, idempotency_key, status, public_error_code,
                           created_at, updated_at
                    FROM simc.simulation_jobs
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                job = self._job_from_row(row)
                terminal = job.status in {
                    SimulationJobStatus.SUCCEEDED,
                    SimulationJobStatus.FAILED,
                    SimulationJobStatus.CANCELLED,
                }
                cursor.execute(
                    """
                    UPDATE simc.simulation_attempts
                    SET diagnostic = 'LEASE_EXPIRED', finished_at = %s
                    WHERE job_id = %s
                      AND finished_at IS NULL
                      AND attempt_number < %s
                    """,
                    (now, job.id, attempt_number),
                )
                cursor.execute(
                    """
                    INSERT INTO simc.simulation_attempts (
                        id, job_id, user_id, attempt_number, worker_id, started_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (job_id, attempt_number) DO NOTHING
                    RETURNING id
                    """,
                    (uuid4(), job.id, job.user_id, attempt_number, worker_id[:64], now),
                )
                attempt_row = cursor.fetchone()
                if attempt_row is None:
                    raise LostLeaseError("simulation attempt was already started")
                attempt_id = UUID(str(_row_value(attempt_row, "id", 0)))
                if terminal:
                    cursor.execute(
                        """
                        UPDATE simc.simulation_attempts
                        SET diagnostic = 'ALREADY_TERMINAL', finished_at = %s
                        WHERE id = %s AND finished_at IS NULL
                        """,
                        (now, attempt_id),
                    )
                    return job, None
                cursor.execute(
                    """
                    UPDATE simc.simulation_jobs
                    SET status = 'running', public_error_code = '', updated_at = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (now, job.id, job.user_id),
                )
                return replace(
                    job,
                    status=SimulationJobStatus.RUNNING,
                    public_error_code="",
                    updated_at=now,
                ), attempt_id

    def exhaust_job_after_attempt_limit(
        self,
        job_id: UUID,
        *,
        worker_id: str,
        finished_at: datetime,
    ) -> SimulationJobStatus | None:
        """Fence an expired final attempt without executing SimC again."""
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                require_current_lease(cursor, job_id, worker_id)
                current = self._lock_job(cursor, job_id)
                if current is None:
                    return None
                if current.status in {
                    SimulationJobStatus.SUCCEEDED,
                    SimulationJobStatus.FAILED,
                    SimulationJobStatus.CANCELLED,
                }:
                    return current.status
                cursor.execute(
                    """
                    UPDATE simc.simulation_attempts
                    SET diagnostic = 'ATTEMPT_EXHAUSTED', finished_at = %s
                    WHERE job_id = %s AND finished_at IS NULL
                    """,
                    (finished_at, current.id),
                )
                cursor.execute(
                    """
                    UPDATE simc.simulation_jobs
                    SET status = 'failed', public_error_code = 'ATTEMPT_EXHAUSTED',
                        updated_at = %s
                    WHERE id = %s AND user_id = %s AND status IN ('queued', 'running')
                    """,
                    (finished_at, current.id, current.user_id),
                )
                if cursor.rowcount != 1:
                    raise LostLeaseError("simulation job is no longer claimable")
        return SimulationJobStatus.FAILED

    def complete_job_success(
        self,
        job: SimulationJob,
        attempt_id: UUID,
        result: SimulationResult,
        *,
        worker_id: str,
        return_code: int,
        finished_at: datetime,
    ) -> SimulationJobStatus:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                require_current_lease(cursor, job.id, worker_id)
                current = self._lock_job(cursor, job.id)
                if current is None:
                    raise ValueError("simulation job disappeared")
                if current.status in {
                    SimulationJobStatus.SUCCEEDED,
                    SimulationJobStatus.FAILED,
                    SimulationJobStatus.CANCELLED,
                }:
                    return current.status
                self._insert_result(cursor, result)
                cursor.execute(
                    """
                    UPDATE simc.simulation_attempts
                    SET exit_code = %s, diagnostic = 'succeeded', finished_at = %s
                    WHERE id = %s AND job_id = %s AND finished_at IS NULL
                    """,
                    (return_code, finished_at, attempt_id, job.id),
                )
                if cursor.rowcount != 1:
                    raise LostLeaseError("simulation attempt is no longer active")
                cursor.execute(
                    """
                    UPDATE simc.simulation_jobs
                    SET status = 'succeeded', public_error_code = '', updated_at = %s
                    WHERE id = %s AND user_id = %s AND status = 'running'
                    """,
                    (finished_at, job.id, job.user_id),
                )
                if cursor.rowcount != 1:
                    raise LostLeaseError("simulation job is no longer running")
        return SimulationJobStatus.SUCCEEDED

    def complete_job_failure(
        self,
        job: SimulationJob,
        attempt_id: UUID,
        *,
        worker_id: str,
        status: SimulationJobStatus,
        error_code: str,
        return_code: int | None,
        finished_at: datetime,
    ) -> SimulationJobStatus:
        if status not in {SimulationJobStatus.QUEUED, SimulationJobStatus.FAILED}:
            raise ValueError("simulation failure status must be queued or failed")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                require_current_lease(cursor, job.id, worker_id)
                current = self._lock_job(cursor, job.id)
                if current is None:
                    raise ValueError("simulation job disappeared")
                if current.status in {
                    SimulationJobStatus.SUCCEEDED,
                    SimulationJobStatus.FAILED,
                    SimulationJobStatus.CANCELLED,
                }:
                    return current.status
                cursor.execute(
                    """
                    UPDATE simc.simulation_attempts
                    SET exit_code = %s, diagnostic = %s, finished_at = %s
                    WHERE id = %s AND job_id = %s AND finished_at IS NULL
                    """,
                    (return_code, error_code[:128], finished_at, attempt_id, job.id),
                )
                if cursor.rowcount != 1:
                    raise LostLeaseError("simulation attempt is no longer active")
                cursor.execute(
                    """
                    UPDATE simc.simulation_jobs
                    SET status = %s, public_error_code = %s, updated_at = %s
                    WHERE id = %s AND user_id = %s AND status = 'running'
                    """,
                    (status.value, error_code[:128], finished_at, job.id, job.user_id),
                )
                if cursor.rowcount != 1:
                    raise LostLeaseError("simulation job is no longer running")
        return status

    def get_result(self, user_id: UUID, job_id: UUID) -> SimulationResult | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, job_id, user_id, profile_sha256, result_json,
                           primary_metric_name, primary_metric_value, compiler_revision,
                           runtime_revision, provenance_json, created_at
                    FROM simc.simulation_results
                    WHERE user_id = %s AND job_id = %s
                    """,
                    (user_id, job_id),
                )
                row = cursor.fetchone()
        return self._result_from_row(row) if row is not None else None

    @classmethod
    def _lock_job(cls, cursor: Any, job_id: UUID) -> SimulationJob | None:
        cursor.execute(
            """
            SELECT id, user_id, snapshot_id, scenario_hash, compiler_revision,
                   runtime_revision, idempotency_key, status, public_error_code,
                   created_at, updated_at
            FROM simc.simulation_jobs
            WHERE id = %s
            FOR UPDATE
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        return cls._job_from_row(row) if row is not None else None

    @staticmethod
    def _insert_result(cursor: Any, result: SimulationResult) -> None:
        cursor.execute(
            """
            INSERT INTO simc.simulation_results (
                id, job_id, user_id, profile_sha256, result_json,
                primary_metric_name, primary_metric_value, compiler_revision,
                runtime_revision, provenance_json, created_at
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                result.id,
                result.job_id,
                result.user_id,
                result.profile_sha256,
                _json_value(result.result),
                result.primary_metric_name,
                result.primary_metric_value,
                result.compiler_revision,
                result.runtime_revision,
                _json_value(result.provenance),
                result.created_at,
            ),
        )

    @staticmethod
    def _snapshot_from_row(row: Any) -> SourceSnapshot:
        snapshot_json = _row_value(row, "snapshot_json", 7)
        provenance_json = _row_value(row, "provenance_json", 8)
        if isinstance(snapshot_json, str):
            snapshot_json = json.loads(snapshot_json)
        if isinstance(provenance_json, str):
            provenance_json = json.loads(provenance_json)
        return SourceSnapshot(
            id=UUID(str(_row_value(row, "id", 0))),
            user_id=UUID(str(_row_value(row, "user_id", 1))),
            provider=SourceProvider(str(_row_value(row, "provider", 2))),
            source_url=str(_row_value(row, "source_url", 3)),
            source_key=str(_row_value(row, "source_key", 4)),
            revision=int(_row_value(row, "revision", 5)),
            readiness=SourceReadiness(str(_row_value(row, "readiness", 6))),
            snapshot=snapshot_json if isinstance(snapshot_json, Mapping) else {},
            provenance=provenance_json if isinstance(provenance_json, Mapping) else {},
            raw_sha256=str(_row_value(row, "raw_sha256", 9)),
            fetched_at=_row_value(row, "fetched_at", 10),
        )

    @staticmethod
    def _job_from_row(row: Any) -> SimulationJob:
        return SimulationJob(
            id=UUID(str(_row_value(row, "id", 0))),
            user_id=UUID(str(_row_value(row, "user_id", 1))),
            snapshot_id=UUID(str(_row_value(row, "snapshot_id", 2))),
            scenario_hash=str(_row_value(row, "scenario_hash", 3)),
            compiler_revision=str(_row_value(row, "compiler_revision", 4)),
            runtime_revision=str(_row_value(row, "runtime_revision", 5)),
            idempotency_key=str(_row_value(row, "idempotency_key", 6)),
            status=SimulationJobStatus(str(_row_value(row, "status", 7))),
            public_error_code=str(_row_value(row, "public_error_code", 8) or ""),
            created_at=_row_value(row, "created_at", 9),
            updated_at=_row_value(row, "updated_at", 10),
        )

    @staticmethod
    def _attempt_from_row(row: Any) -> SimulationAttempt:
        return SimulationAttempt(
            id=UUID(str(_row_value(row, "id", 0))),
            job_id=UUID(str(_row_value(row, "job_id", 1))),
            user_id=UUID(str(_row_value(row, "user_id", 2))),
            attempt_number=int(_row_value(row, "attempt_number", 3)),
            worker_id=str(_row_value(row, "worker_id", 4)),
            started_at=_row_value(row, "started_at", 5),
            finished_at=_row_value(row, "finished_at", 6),
            exit_code=(
                None
                if _row_value(row, "exit_code", 7) is None
                else int(_row_value(row, "exit_code", 7))
            ),
            diagnostic=str(_row_value(row, "diagnostic", 8) or ""),
        )

    @staticmethod
    def _result_from_row(row: Any) -> SimulationResult:
        result_json = _row_value(row, "result_json", 4)
        provenance_json = _row_value(row, "provenance_json", 9)
        if isinstance(result_json, str):
            result_json = json.loads(result_json)
        if isinstance(provenance_json, str):
            provenance_json = json.loads(provenance_json)
        return SimulationResult(
            id=UUID(str(_row_value(row, "id", 0))),
            job_id=UUID(str(_row_value(row, "job_id", 1))),
            user_id=UUID(str(_row_value(row, "user_id", 2))),
            profile_sha256=str(_row_value(row, "profile_sha256", 3)),
            result=result_json if isinstance(result_json, Mapping) else {},
            primary_metric_name=str(_row_value(row, "primary_metric_name", 5)),
            primary_metric_value=float(_row_value(row, "primary_metric_value", 6)),
            compiler_revision=str(_row_value(row, "compiler_revision", 7)),
            runtime_revision=str(_row_value(row, "runtime_revision", 8)),
            provenance=provenance_json if isinstance(provenance_json, Mapping) else {},
            created_at=_row_value(row, "created_at", 10),
        )


__all__ = ("PostgresSimulationRepository",)
