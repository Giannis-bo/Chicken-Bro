#!/usr/bin/env python3
"""PostgreSQL repository for async Gear stat snapshots and fenced jobs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class GearStatSnapshotIntegrityError(RuntimeError):
    pass


class GearStatSnapshotQueueUnavailable(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _json_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _snapshot_from_row(row: Any) -> dict[str, Any]:
    values = list(row or [])
    if len(values) < 11:
        return {}
    return {
        "statSignature": _text(values[0]),
        "schemaRevision": _text(values[1]),
        "resolvedGearSignature": _text(values[2]),
        "manifestRevision": _text(values[3]),
        "gearReleaseId": _text(values[4]),
        "simcRuntimeRevision": _text(values[5]),
        "dependencyVector": _canonical(values[6] if isinstance(values[6], dict) else {}),
        "profileHash": _text(values[7]),
        "snapshotHash": _text(values[8]),
        "snapshot": _canonical(values[9] if isinstance(values[9], dict) else {}),
        "verifiedAt": _text(values[10]),
    }


def _job_from_row(row: Any) -> dict[str, Any]:
    values = list(row or [])
    if len(values) < 15:
        return {}
    return {
        "jobId": _int(values[0]),
        "statSignature": _text(values[1]),
        "status": _text(values[2]),
        "request": _canonical(values[3] if isinstance(values[3], dict) else {}),
        "releaseContext": _canonical(values[4] if isinstance(values[4], dict) else {}),
        "clientKeyHash": _text(values[5]),
        "attempt": _int(values[6]),
        "lockedBy": _text(values[7]),
        "lockToken": _text(values[8]),
        "leaseUntil": _text(values[9]),
        "queuedAt": _text(values[10]),
        "startedAt": _text(values[11]),
        "heartbeatAt": _text(values[12]),
        "finishedAt": _text(values[13]),
        "problem": _canonical(values[14] if isinstance(values[14], dict) else {}),
    }


_SNAPSHOT_COLUMNS = """
stat_signature, schema_revision, resolved_gear_signature, manifest_revision,
gear_release_id, simc_runtime_revision, dependency_vector_json, profile_hash,
snapshot_hash, snapshot_json, verified_at
"""

_JOB_COLUMN_NAMES = (
    "job_id",
    "stat_signature",
    "status",
    "request_json",
    "release_context_json",
    "client_key_hash",
    "attempt",
    "locked_by",
    "lock_token",
    "lease_until",
    "queued_at",
    "started_at",
    "heartbeat_at",
    "finished_at",
    "problem_json",
)
_JOB_COLUMNS = ", ".join(_JOB_COLUMN_NAMES)
_CLAIM_JOB_COLUMNS = ", ".join(f"job.{column}" for column in _JOB_COLUMN_NAMES)


class GearStatSnapshotStore:
    """Own every SQL operation for Phase 5 stat snapshots and jobs."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate_signature(stat_signature: Any) -> str:
        normalized = _text(stat_signature)
        if not normalized.startswith("stat-snapshot:sha256:") or len(normalized) != len("stat-snapshot:sha256:") + 64:
            raise GearStatSnapshotIntegrityError("valid stat signature is required")
        return normalized

    @staticmethod
    def _record_metric(cur, column: str) -> None:
        if column not in {"request_count", "cache_hit_count", "queue_miss_count", "legacy_request_count"}:
            raise GearStatSnapshotIntegrityError("unsupported stat snapshot metric")
        cur.execute(
            f"""
            INSERT INTO ops.websim_gear_stat_metrics (metric_key, {column}, updated_at)
            VALUES ('global', 1, now())
            ON CONFLICT (metric_key) DO UPDATE
            SET {column} = ops.websim_gear_stat_metrics.{column} + 1,
                updated_at = now()
            """
        )

    def lookup_snapshot(self, stat_signature: str) -> dict[str, Any]:
        signature = self._validate_signature(stat_signature)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"SELECT {_SNAPSHOT_COLUMNS} FROM cache.websim_gear_stat_snapshots WHERE stat_signature = %s",
                    (signature,),
                )
                return _snapshot_from_row(cur.fetchone())

    def get_or_start(
        self,
        stat_signature: str,
        *,
        request_payload: dict[str, Any],
        release_context: dict[str, Any],
        client_key_hash: str,
        now: str,
        global_limit: int = 100,
        per_client_limit: int = 2,
    ) -> dict[str, Any]:
        """Return one verified cache hit or create/reuse one active job."""

        signature = self._validate_signature(stat_signature)
        request = _canonical(request_payload if isinstance(request_payload, dict) else {})
        release = _canonical(release_context if isinstance(release_context, dict) else {})
        client_hash = _text(client_key_hash)
        global_cap = max(1, min(_int(global_limit), 10000))
        client_cap = max(1, min(_int(per_client_limit), 100))
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._record_metric(cur, "request_count")
                cur.execute(
                    f"SELECT {_SNAPSHOT_COLUMNS} FROM cache.websim_gear_stat_snapshots WHERE stat_signature = %s",
                    (signature,),
                )
                snapshot = _snapshot_from_row(cur.fetchone())
                if snapshot:
                    self._record_metric(cur, "cache_hit_count")
                    return {"status": "verified", "snapshot": snapshot}

                cur.execute(
                    f"""
                    SELECT {_JOB_COLUMNS}
                    FROM ops.websim_gear_stat_jobs
                    WHERE stat_signature = %s AND status IN ('queued', 'running')
                    ORDER BY job_id DESC
                    LIMIT 1
                    """,
                    (signature,),
                )
                active = _job_from_row(cur.fetchone())
                if active:
                    return {"status": "pending", "job": active}

                cur.execute(
                    """
                    SELECT status, problem_json, cooldown_until,
                           (cooldown_until IS NOT NULL AND cooldown_until > %s::timestamptz)
                    FROM ops.websim_gear_stat_jobs
                    WHERE stat_signature = %s AND status IN ('blocked', 'failed')
                    ORDER BY job_id DESC
                    LIMIT 1
                    """,
                    (_text(now), signature),
                )
                terminal = cur.fetchone()
                if terminal:
                    terminal_status = _text(terminal[0])
                    problem = _canonical(terminal[1] if isinstance(terminal[1], dict) else {})
                    if terminal_status == "blocked":
                        return {"status": "blocked", "problem": problem}
                    if bool(terminal[3]):
                        return {
                            "status": "unavailable",
                            "problem": problem,
                            "cooldownUntil": _text(terminal[2]),
                        }

                cur.execute(
                    "SELECT count(*) FROM ops.websim_gear_stat_jobs WHERE status IN ('queued', 'running')"
                )
                if _int((cur.fetchone() or (0,))[0]) >= global_cap:
                    raise GearStatSnapshotQueueUnavailable("GEAR_STAT_QUEUE_SATURATED", "stat snapshot queue is saturated")
                if client_hash:
                    cur.execute(
                        """
                        SELECT count(*)
                        FROM ops.websim_gear_stat_jobs
                        WHERE status IN ('queued', 'running') AND client_key_hash = %s
                        """,
                        (client_hash,),
                    )
                    if _int((cur.fetchone() or (0,))[0]) >= client_cap:
                        raise GearStatSnapshotQueueUnavailable(
                            "GEAR_STAT_CLIENT_LIMIT",
                            "client stat snapshot limit is reached",
                        )

                self._record_metric(cur, "queue_miss_count")
                cur.execute(
                    f"""
                    INSERT INTO ops.websim_gear_stat_jobs (
                        stat_signature, status, request_json, release_context_json,
                        client_key_hash, queued_at
                    ) VALUES (%s, 'queued', %s::jsonb, %s::jsonb, %s, %s::timestamptz)
                    ON CONFLICT (stat_signature) WHERE status IN ('queued', 'running')
                    DO NOTHING
                    RETURNING {_JOB_COLUMNS}
                    """,
                    (signature, _json(request), _json(release), client_hash, _text(now)),
                )
                job = _job_from_row(cur.fetchone())
                if not job:
                    cur.execute(
                        f"""
                        SELECT {_JOB_COLUMNS}
                        FROM ops.websim_gear_stat_jobs
                        WHERE stat_signature = %s AND status IN ('queued', 'running')
                        ORDER BY job_id DESC
                        LIMIT 1
                        """,
                        (signature,),
                    )
                    job = _job_from_row(cur.fetchone())
                if not job:
                    raise GearStatSnapshotIntegrityError("single-flight job could not be created or loaded")
                return {"status": "pending", "job": job}

    def claim_next(
        self,
        *,
        worker_id: str,
        lock_token: str,
        now: str,
        lease_seconds: int = 30,
    ) -> dict[str, Any]:
        worker = _text(worker_id)
        token = _text(lock_token)
        if not worker or not token:
            raise GearStatSnapshotIntegrityError("worker identity and lock token are required")
        lease = max(10, min(_int(lease_seconds), 3600))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_gear_stat_jobs
                    SET status = 'failed', lease_until = NULL, locked_by = '', lock_token = '',
                        finished_at = %s::timestamptz, updated_at = %s::timestamptz,
                        problem_json = jsonb_build_object('code', 'GEAR_STAT_MAX_ATTEMPTS')
                    WHERE attempt >= 20
                      AND (
                        status = 'queued'
                        OR (status = 'running' AND lease_until < %s::timestamptz)
                      )
                    RETURNING job_id
                    """,
                    (_text(now), _text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    """
                    UPDATE ops.websim_gear_stat_jobs
                    SET status = 'queued', locked_by = '', lock_token = '', lease_until = NULL,
                        heartbeat_at = NULL, started_at = NULL,
                        updated_at = %s::timestamptz,
                        problem_json = jsonb_build_object('code', 'GEAR_STAT_JOB_RECLAIMED')
                    WHERE status = 'running' AND attempt < 20 AND lease_until < %s::timestamptz
                    RETURNING job_id
                    """,
                    (_text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    f"""
                    WITH next_job AS (
                        SELECT job_id
                        FROM ops.websim_gear_stat_jobs
                        WHERE status = 'queued' AND attempt < 20
                        ORDER BY queued_at, job_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE ops.websim_gear_stat_jobs job
                    SET status = 'running', attempt = job.attempt + 1,
                        locked_by = %s, lock_token = %s,
                        lease_until = %s::timestamptz + make_interval(secs => %s),
                        heartbeat_at = %s::timestamptz,
                        started_at = COALESCE(job.started_at, %s::timestamptz),
                        updated_at = %s::timestamptz,
                        problem_json = '{{}}'::jsonb
                    FROM next_job
                    WHERE job.job_id = next_job.job_id
                    RETURNING {_CLAIM_JOB_COLUMNS}
                    """,
                    (worker, token, _text(now), lease, _text(now), _text(now), _text(now)),
                )
                return _job_from_row(cur.fetchone())

    def heartbeat(self, *, job_id: int, lock_token: str, now: str, lease_seconds: int = 30) -> bool:
        lease = max(10, min(_int(lease_seconds), 3600))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_gear_stat_jobs
                    SET heartbeat_at = %s::timestamptz,
                        lease_until = %s::timestamptz + make_interval(secs => %s),
                        updated_at = %s::timestamptz
                    WHERE job_id = %s AND lock_token = %s AND status = 'running'
                    RETURNING job_id
                    """,
                    (_text(now), _text(now), lease, _text(now), _int(job_id), _text(lock_token)),
                )
                return bool(cur.fetchone())

    def publish_verified(
        self,
        *,
        job_id: int,
        lock_token: str,
        record: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        publication = record if isinstance(record, dict) else {}
        signature = self._validate_signature(publication.get("statSignature"))
        snapshot_payload = publication.get("snapshot") if isinstance(publication.get("snapshot"), dict) else {}
        required_fields = (
            "schemaRevision",
            "resolvedGearSignature",
            "manifestRevision",
            "gearReleaseId",
            "simcRuntimeRevision",
            "profileHash",
            "snapshotHash",
        )
        if any(not _text(publication.get(field)) for field in required_fields):
            raise GearStatSnapshotIntegrityError("stat snapshot publication identity is incomplete")
        if snapshot_payload.get("statStatus") != "verified":
            raise GearStatSnapshotIntegrityError("only verified stat snapshots may be published")
        if _json_hash(snapshot_payload) != _text(publication.get("snapshotHash")):
            raise GearStatSnapshotIntegrityError("stat snapshot content hash does not match its bounded payload")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT stat_signature
                    FROM ops.websim_gear_stat_jobs
                    WHERE job_id = %s AND lock_token = %s AND status = 'running'
                    FOR UPDATE
                    """,
                    (_int(job_id), _text(lock_token)),
                )
                fence = cur.fetchone()
                if not fence or _text(fence[0]) != signature:
                    raise GearStatSnapshotIntegrityError("stat snapshot job lease was lost before publication")
                cur.execute(
                    """
                    INSERT INTO cache.websim_gear_stat_snapshots (
                        stat_signature, schema_revision, resolved_gear_signature,
                        manifest_revision, gear_release_id, simc_runtime_revision,
                        dependency_vector_json, profile_hash, snapshot_hash,
                        snapshot_json, verified_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::timestamptz
                    )
                    ON CONFLICT (stat_signature) DO NOTHING
                    RETURNING snapshot_hash
                    """,
                    (
                        signature,
                        _text(publication.get("schemaRevision")),
                        _text(publication.get("resolvedGearSignature")),
                        _text(publication.get("manifestRevision")),
                        _text(publication.get("gearReleaseId")),
                        _text(publication.get("simcRuntimeRevision")),
                        _json(publication.get("dependencyVector") or {}),
                        _text(publication.get("profileHash")),
                        _text(publication.get("snapshotHash")),
                        _json(publication.get("snapshot") or {}),
                        _text(publication.get("verifiedAt") or now),
                    ),
                )
                stored = cur.fetchone()
                if not stored:
                    cur.execute(
                        """
                        SELECT snapshot_hash
                        FROM cache.websim_gear_stat_snapshots
                        WHERE stat_signature = %s
                        """,
                        (signature,),
                    )
                    stored = cur.fetchone()
                if not stored or _text(stored[0]) != _text(publication.get("snapshotHash")):
                    raise GearStatSnapshotIntegrityError("immutable stat snapshot content hash conflict")
                cur.execute(
                    """
                    UPDATE ops.websim_gear_stat_jobs
                    SET status = 'completed', finished_at = %s::timestamptz,
                        heartbeat_at = %s::timestamptz, lease_until = NULL,
                        locked_by = '', lock_token = '', problem_json = '{}'::jsonb,
                        updated_at = %s::timestamptz
                    WHERE job_id = %s AND lock_token = %s AND status = 'running'
                    RETURNING job_id
                    """,
                    (_text(now), _text(now), _text(now), _int(job_id), _text(lock_token)),
                )
                if not cur.fetchone():
                    raise GearStatSnapshotIntegrityError("stat snapshot job lease was lost during publication")
                return {"status": "verified", "statSignature": signature, "snapshotHash": _text(stored[0])}

    def fail_job(
        self,
        *,
        job_id: int,
        lock_token: str,
        problem: dict[str, Any],
        now: str,
        deterministic: bool,
        cooldown_seconds: int = 60,
    ) -> bool:
        status = "blocked" if deterministic else "failed"
        cooldown = 0 if deterministic else max(1, min(_int(cooldown_seconds), 86400))
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_gear_stat_jobs
                    SET status = %s, finished_at = %s::timestamptz,
                        cooldown_until = CASE WHEN %s > 0 THEN %s::timestamptz + make_interval(secs => %s) ELSE NULL END,
                        lease_until = NULL, locked_by = '', lock_token = '',
                        problem_json = %s::jsonb, updated_at = %s::timestamptz
                    WHERE job_id = %s AND lock_token = %s AND status = 'running'
                    RETURNING job_id
                    """,
                    (status, _text(now), cooldown, _text(now), cooldown, _json(problem or {}), _text(now), _int(job_id), _text(lock_token)),
                )
                return bool(cur.fetchone())

    def update_worker_state(
        self,
        *,
        worker_id: str,
        status: str,
        worker_revision: str,
        simc_runtime_revision: str,
        now: str,
        current_job_id: int = 0,
        last_outcome: dict[str, Any] | None = None,
    ) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ops.websim_gear_stat_worker_state (
                        worker_id, status, worker_revision, simc_runtime_revision,
                        current_job_id, heartbeat_at, last_outcome_json
                    ) VALUES (%s, %s, %s, %s, NULLIF(%s, 0), %s::timestamptz, %s::jsonb)
                    ON CONFLICT (worker_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        worker_revision = EXCLUDED.worker_revision,
                        simc_runtime_revision = EXCLUDED.simc_runtime_revision,
                        current_job_id = EXCLUDED.current_job_id,
                        heartbeat_at = EXCLUDED.heartbeat_at,
                        last_outcome_json = EXCLUDED.last_outcome_json,
                        updated_at = EXCLUDED.heartbeat_at
                    """,
                    (
                        _text(worker_id),
                        _text(status),
                        _text(worker_revision),
                        _text(simc_runtime_revision),
                        _int(current_job_id),
                        _text(now),
                        _json(last_outcome or {}),
                    ),
                )

    def record_legacy_request(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._record_metric(cur, "legacy_request_count")

    def health_summary(self, *, now: str) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    WITH active_jobs AS (
                        SELECT status, queued_at
                        FROM ops.websim_gear_stat_jobs
                        WHERE status IN ('queued', 'running')
                    ), terminal_history AS (
                        SELECT status, queued_at
                        FROM ops.websim_gear_stat_jobs
                        WHERE status NOT IN ('queued', 'running')
                        ORDER BY job_id DESC
                        LIMIT 1000
                    ), bounded_jobs AS (
                        SELECT * FROM active_jobs
                        UNION ALL
                        SELECT * FROM terminal_history
                    )
                    SELECT
                        count(*) FILTER (WHERE status = 'queued'),
                        count(*) FILTER (WHERE status = 'running'),
                        count(*) FILTER (WHERE status = 'failed'),
                        count(*) FILTER (WHERE status = 'blocked'),
                        min(queued_at) FILTER (WHERE status = 'queued')
                    FROM bounded_jobs
                    """
                )
                queue = cur.fetchone() or (0, 0, 0, 0, None)
                cur.execute(
                    """
                    SELECT count(*)
                    FROM (
                        SELECT 1
                        FROM cache.websim_gear_stat_snapshots
                        LIMIT 10001
                    ) bounded_snapshots
                    """
                )
                raw_snapshot_count = _int((cur.fetchone() or (0,))[0])
                cur.execute(
                    """
                    SELECT worker_id, status, worker_revision, simc_runtime_revision,
                           current_job_id, heartbeat_at, last_outcome_json
                    FROM ops.websim_gear_stat_worker_state
                    ORDER BY heartbeat_at DESC
                    LIMIT 4
                    """
                )
                workers = [
                    {
                        "workerId": _text(row[0]),
                        "status": _text(row[1]),
                        "workerRevision": _text(row[2]),
                        "simcRuntimeRevision": _text(row[3]),
                        "currentJobId": _int(row[4]),
                        "heartbeatAt": _text(row[5]),
                        "lastOutcome": _canonical(row[6] if isinstance(row[6], dict) else {}),
                    }
                    for row in cur.fetchall()
                ]
                cur.execute(
                    """
                    SELECT request_count, cache_hit_count, queue_miss_count,
                           legacy_request_count, updated_at
                    FROM ops.websim_gear_stat_metrics
                    WHERE metric_key = 'global'
                    """
                )
                metrics = cur.fetchone() or (0, 0, 0, 0, None)
        request_count = _int(metrics[0])
        cache_hits = _int(metrics[1])
        return {
            "checkedAt": _text(now),
            "queue": {
                "queued": _int(queue[0]),
                "running": _int(queue[1]),
                "failed": _int(queue[2]),
                "blocked": _int(queue[3]),
                "oldestQueuedAt": _text(queue[4]),
            },
            "snapshotCount": min(raw_snapshot_count, 10000),
            "snapshotCountTruncated": raw_snapshot_count > 10000,
            "workers": workers,
            "metrics": {
                "requestCount": request_count,
                "cacheHitCount": cache_hits,
                "queueMissCount": _int(metrics[2]),
                "legacyRequestCount": _int(metrics[3]),
                "cacheHitRate": round(cache_hits / request_count, 4) if request_count else 0.0,
                "updatedAt": _text(metrics[4]),
            },
        }


__all__ = (
    "GearStatSnapshotIntegrityError",
    "GearStatSnapshotQueueUnavailable",
    "GearStatSnapshotStore",
)
