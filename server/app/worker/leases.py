import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class LostLeaseError(RuntimeError):
    """Raised when a worker no longer owns the job it tried to mutate."""


@dataclass(frozen=True)
class JobLease:
    id: UUID
    domain: str
    command_type: str
    aggregate_id: UUID | None
    payload: Mapping[str, object]
    attempt: int
    max_attempts: int


_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")


_CLAIM_SQL = """
WITH candidate AS (
    SELECT id
    FROM ops.job_queue
    WHERE (
        status = 'queued' AND available_at <= now()
    ) OR (
        status = 'running' AND lease_expires_at < now()
    )
    ORDER BY available_at, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE ops.job_queue AS jobs
SET status = 'running',
    attempt = jobs.attempt + 1,
    lease_owner = %s,
    lease_expires_at = now() + make_interval(secs => %s),
    heartbeat_at = now(),
    updated_at = now()
FROM candidate
WHERE jobs.id = candidate.id
RETURNING jobs.id, jobs.domain, jobs.command_type, jobs.aggregate_id,
          jobs.payload_json, jobs.attempt, jobs.max_attempts;
"""


class PostgresJobQueue:
    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def enqueue(
        self,
        *,
        job_id: UUID,
        domain: str,
        command_type: str,
        aggregate_id: UUID | None,
        payload: Mapping[str, object],
        max_attempts: int = 3,
    ) -> None:
        if not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sql = """
            INSERT INTO ops.job_queue (
                id, domain, command_type, aggregate_id, payload_json,
                status, max_attempts
            ) VALUES (%s, %s, %s, %s, %s::jsonb, 'queued', %s)
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (job_id, domain, command_type, aggregate_id, payload_json, max_attempts))

    def claim(self, *, worker_id: str, lease_seconds: int) -> JobLease | None:
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(_CLAIM_SQL, (worker_id, lease_seconds))
                row = cursor.fetchone()
        if row is None:
            return None
        return self._lease_from_row(row)

    def heartbeat(self, job_id: UUID, *, worker_id: str, lease_seconds: int) -> None:
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        sql = """
            UPDATE ops.job_queue
            SET lease_expires_at = now() + make_interval(secs => %s),
                heartbeat_at = now(), updated_at = now()
            WHERE id = %s AND status = 'running' AND lease_owner = %s
        """
        self._lease_update(sql, (lease_seconds, job_id, worker_id))

    def succeed(self, job_id: UUID, *, worker_id: str) -> None:
        sql = """
            UPDATE ops.job_queue
            SET status = 'succeeded', lease_owner = '',
                lease_expires_at = NULL, heartbeat_at = NULL,
                public_error_code = '', updated_at = now()
            WHERE id = %s AND status = 'running' AND lease_owner = %s
        """
        self._lease_update(sql, (job_id, worker_id))

    def fail(self, job_id: UUID, *, worker_id: str, error_code: str, retryable: bool) -> None:
        if _ERROR_CODE.fullmatch(error_code) is None:
            raise ValueError("error_code must be a stable public literal")
        sql = """
            UPDATE ops.job_queue
            SET status = CASE
                    WHEN %s AND attempt < max_attempts AND NOT cancel_requested THEN 'queued'
                    ELSE 'failed'
                END,
                available_at = CASE
                    WHEN %s AND attempt < max_attempts AND NOT cancel_requested THEN now()
                    ELSE available_at
                END,
                lease_owner = '', lease_expires_at = NULL, heartbeat_at = NULL,
                public_error_code = %s, updated_at = now()
            WHERE id = %s AND status = 'running' AND lease_owner = %s
        """
        self._lease_update(sql, (retryable, retryable, error_code, job_id, worker_id))

    def request_cancel(self, job_id: UUID) -> bool:
        sql = """
            UPDATE ops.job_queue
            SET cancel_requested = TRUE,
                status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                lease_owner = CASE WHEN status = 'queued' THEN '' ELSE lease_owner END,
                lease_expires_at = CASE WHEN status = 'queued' THEN NULL ELSE lease_expires_at END,
                heartbeat_at = CASE WHEN status = 'queued' THEN NULL ELSE heartbeat_at END,
                updated_at = now()
            WHERE id = %s AND status IN ('queued', 'running') AND NOT cancel_requested
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (job_id,))
                return cursor.rowcount == 1

    def _lease_update(self, sql: str, params: tuple[object, ...]) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.rowcount != 1:
                    raise LostLeaseError("job lease is no longer owned by this worker")

    @staticmethod
    def _lease_from_row(row: Any) -> JobLease:
        values = (
            _row_value(row, "id", 0),
            _row_value(row, "domain", 1),
            _row_value(row, "command_type", 2),
            _row_value(row, "aggregate_id", 3),
            _row_value(row, "payload_json", 4),
            _row_value(row, "attempt", 5),
            _row_value(row, "max_attempts", 6),
        )
        payload = values[4]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, Mapping):
            raise ValueError("job payload must be a JSON object")
        return JobLease(
            id=values[0] if isinstance(values[0], UUID) else UUID(str(values[0])),
            domain=str(values[1]),
            command_type=str(values[2]),
            aggregate_id=(
                values[3]
                if values[3] is None or isinstance(values[3], UUID)
                else UUID(str(values[3]))
            ),
            payload=dict(payload),
            attempt=int(values[5]),
            max_attempts=int(values[6]),
        )


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    return row[index]
