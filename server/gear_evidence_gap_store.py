#!/usr/bin/env python3
"""PostgreSQL owner for the fenced operational Gear Evidence Gap queue."""

from __future__ import annotations

import json
from typing import Any


class GearEvidenceGapIntegrityError(RuntimeError):
    pass


_ROOT_CODES = {
    "artifact_missing",
    "source_unavailable",
    "parser_unhandled_shape",
    "observation_conflict",
    "compiler_policy_missing",
    "projection_contract_regression",
}
_FINISH_STATUSES = {"retryable", "terminal"}
_GAP_KEYS = {
    "schemaRevision",
    "gapKey",
    "factKey",
    "status",
    "problemCode",
    "missingRequirement",
    "attempt",
    "nextAttemptAt",
}
_OUTCOME_KEYS = {
    "status",
    "problemCode",
    "missingRequirement",
    "nextAttemptAt",
}
_MISSING_REQUIREMENT_STRING_FIELDS = {
    "seasonRevision": 256,
    "subjectKey": 512,
    "factType": 120,
    "sourceType": 120,
    "sourceIdentity": 1024,
    "sourceRevision": 256,
    "sourceScope": 120,
    "parserRevision": 256,
    "compilerRuleRevision": 256,
    "artifactId": 128,
    "observationId": 128,
    "requiredInputKey": 120,
}
_REQUIRED_MISSING_REQUIREMENT_FIELDS = {"subjectKey", "factType"}
_ROW_COLUMNS = (
    "gap_key",
    "fact_key",
    "schema_revision",
    "status",
    "problem_code",
    "missing_requirement_json",
    "attempt",
    "locked_by",
    "lock_token",
    "lease_until",
    "next_attempt_at",
    "queued_at",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
)
_ROW_SELECT = ", ".join(_ROW_COLUMNS)
_CLAIM_ROW_SELECT = ", ".join(f"gap.{column}" for column in _ROW_COLUMNS)


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
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as error:
        raise GearEvidenceGapIntegrityError(
            "Gear Evidence Gap values must be JSON-canonical."
        ) from error


def _json(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _is_hash(value: Any, prefix: str) -> bool:
    text = _text(value)
    suffix = text[len(prefix) :] if text.startswith(prefix) else ""
    return len(suffix) == 64 and all(character in "0123456789abcdef" for character in suffix)


def _validated_missing_requirement(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise GearEvidenceGapIntegrityError(
            "Gear Evidence Gap missing requirement must use approved operational fields."
        )
    keys = set(value)
    if (
        not _REQUIRED_MISSING_REQUIREMENT_FIELDS.issubset(keys)
        or not keys.issubset(_MISSING_REQUIREMENT_STRING_FIELDS)
    ):
        raise GearEvidenceGapIntegrityError(
            "Gear Evidence Gap missing requirement must use approved operational fields."
        )
    normalized: dict[str, str] = {}
    for key, raw_value in value.items():
        if not isinstance(raw_value, str):
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap missing requirement must use approved operational fields."
            )
        field_value = raw_value.strip()
        if not field_value or len(field_value) > _MISSING_REQUIREMENT_STRING_FIELDS[key]:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap missing requirement must use approved operational fields."
            )
        normalized[key] = field_value
    if normalized.get("artifactId") and not _is_hash(
        normalized["artifactId"], "gear-artifact:sha256:"
    ):
        raise GearEvidenceGapIntegrityError(
            "Gear Evidence Gap missing requirement Artifact identity is invalid."
        )
    if normalized.get("observationId") and not _is_hash(
        normalized["observationId"], "gear-observation:sha256:"
    ):
        raise GearEvidenceGapIntegrityError(
            "Gear Evidence Gap missing requirement Observation identity is invalid."
        )
    return _canonical(normalized)


def _gap_from_row(row: Any) -> dict[str, Any]:
    values = list(row or [])
    if len(values) < len(_ROW_COLUMNS):
        return {}
    return {
        "gapKey": _text(values[0]),
        "factKey": _text(values[1]),
        "schemaRevision": _text(values[2]),
        "status": _text(values[3]),
        "problemCode": _text(values[4]),
        "missingRequirement": _validated_missing_requirement(values[5]),
        "attempt": _int(values[6]),
        "lockedBy": _text(values[7]),
        "lockToken": _text(values[8]),
        "leaseUntil": _text(values[9]),
        "nextAttemptAt": _text(values[10]),
        "queuedAt": _text(values[11]),
        "startedAt": _text(values[12]),
        "finishedAt": _text(values[13]),
        "createdAt": _text(values[14]),
        "updatedAt": _text(values[15]),
    }


class GearEvidenceGapStore:
    """Own only enqueue, claim, finish, and health SQL for operational gaps."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate_gap(record: Any) -> dict[str, Any]:
        if not isinstance(record, dict) or set(record) != _GAP_KEYS:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gaps may contain only approved operational fields."
            )
        normalized = {
            "schemaRevision": _text(record.get("schemaRevision")),
            "gapKey": _text(record.get("gapKey")),
            "factKey": _text(record.get("factKey")),
            "status": _text(record.get("status")),
            "problemCode": _text(record.get("problemCode")),
            "missingRequirement": _validated_missing_requirement(
                record.get("missingRequirement")
            ),
            "attempt": _int(record.get("attempt")),
            "nextAttemptAt": _text(record.get("nextAttemptAt")),
        }
        if normalized["schemaRevision"] != "gear-evidence-gap-v1":
            raise GearEvidenceGapIntegrityError("Gear Evidence Gap schema is invalid.")
        if not _is_hash(normalized["gapKey"], "gear-gap:sha256:") or not _is_hash(
            normalized["factKey"], "gear-fact:sha256:"
        ):
            raise GearEvidenceGapIntegrityError("Gear Evidence Gap identity is invalid.")
        if normalized["status"] != "pending" or normalized["attempt"] != 0:
            raise GearEvidenceGapIntegrityError(
                "New Gear Evidence Gaps must start pending at attempt zero."
            )
        if normalized["problemCode"] not in _ROOT_CODES:
            raise GearEvidenceGapIntegrityError("Gear Evidence Gap root code is invalid.")
        if not normalized["nextAttemptAt"]:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap next attempt time is required."
            )
        return normalized

    def enqueue_gaps(self, gaps: list[dict[str, Any]], *, now: str) -> dict[str, int]:
        inserted = 0
        reused = 0
        for raw_gap in gaps if isinstance(gaps, list) else []:
            gap = self._validate_gap(raw_gap)
            with self.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ops.websim_gear_evidence_gaps (
                            gap_key, fact_key, schema_revision, status, problem_code,
                            missing_requirement_json, attempt, next_attempt_at, queued_at
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::timestamptz, %s::timestamptz)
                        ON CONFLICT (gap_key) DO NOTHING
                        RETURNING gap_key, status
                        """,
                        (
                            gap["gapKey"],
                            gap["factKey"],
                            gap["schemaRevision"],
                            gap["status"],
                            gap["problemCode"],
                            _json(gap["missingRequirement"]),
                            gap["attempt"],
                            gap["nextAttemptAt"],
                            _text(now),
                        ),
                    )
                    if cur.fetchone():
                        inserted += 1
                    else:
                        reused += 1
        return {"inserted": inserted, "reused": reused}

    def claim_next(
        self,
        *,
        worker_id: str,
        lock_token: str,
        now: str,
        lease_seconds: int = 90,
    ) -> dict[str, Any]:
        worker = _text(worker_id)
        token = _text(lock_token)
        lease = max(30, min(_int(lease_seconds), 600))
        if not worker or not token:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap worker identity and lock token are required."
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_gear_evidence_gaps
                    SET status = 'terminal', lease_until = NULL, locked_by = '', lock_token = '',
                        finished_at = %s::timestamptz, updated_at = %s::timestamptz
                    WHERE attempt >= 3
                      AND (
                          status IN ('pending', 'retryable')
                          OR (status = 'running' AND lease_until < %s::timestamptz)
                      )
                    RETURNING gap_key
                    """,
                    (_text(now), _text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    """
                    UPDATE ops.websim_gear_evidence_gaps
                    SET status = 'retryable', locked_by = '', lock_token = '', lease_until = NULL,
                        next_attempt_at = %s::timestamptz, updated_at = %s::timestamptz
                    WHERE status = 'running'
                      AND attempt < 3
                      AND lease_until < %s::timestamptz
                    RETURNING gap_key
                    """,
                    (_text(now), _text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    f"""
                    WITH next_gap AS (
                        SELECT gap_key
                        FROM ops.websim_gear_evidence_gaps
                        WHERE status IN ('pending', 'retryable')
                          AND attempt < 3
                          AND next_attempt_at <= %s::timestamptz
                        ORDER BY next_attempt_at, queued_at, gap_key
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE ops.websim_gear_evidence_gaps gap
                    SET status = 'running', attempt = gap.attempt + 1,
                        locked_by = %s, lock_token = %s,
                        lease_until = %s::timestamptz + make_interval(secs => %s),
                        started_at = COALESCE(gap.started_at, %s::timestamptz),
                        finished_at = NULL, updated_at = %s::timestamptz
                    FROM next_gap
                    WHERE gap.gap_key = next_gap.gap_key
                    RETURNING {_CLAIM_ROW_SELECT}
                    """,
                    (
                        _text(now),
                        worker,
                        token,
                        _text(now),
                        lease,
                        _text(now),
                        _text(now),
                    ),
                )
                return _gap_from_row(cur.fetchone())

    def finish(
        self,
        *,
        gap_key: str,
        lock_token: str,
        outcome: dict[str, Any],
        now: str,
    ) -> dict[str, Any]:
        key = _text(gap_key)
        token = _text(lock_token)
        if not _is_hash(key, "gear-gap:sha256:") or not token:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap fence identity is invalid."
            )
        if not isinstance(outcome, dict) or not set(outcome).issubset(_OUTCOME_KEYS):
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap outcome may contain only approved operational fields."
            )
        status = _text(outcome.get("status"))
        problem_code = _text(outcome.get("problemCode"))
        next_attempt_at = _text(outcome.get("nextAttemptAt")) or _text(now)
        missing_requirement = outcome.get("missingRequirement")
        if status not in _FINISH_STATUSES:
            raise GearEvidenceGapIntegrityError(
                "Unsupported Gear Evidence Gap terminal status."
            )
        if problem_code not in _ROOT_CODES:
            raise GearEvidenceGapIntegrityError("Gear Evidence Gap root code is invalid.")
        if status == "retryable" and not _text(outcome.get("nextAttemptAt")):
            raise GearEvidenceGapIntegrityError(
                "Retryable Gear Evidence Gap requires a next attempt time."
            )
        if missing_requirement is not None:
            missing_requirement = _validated_missing_requirement(missing_requirement)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_gear_evidence_gaps
                    SET status = %s, problem_code = %s,
                        missing_requirement_json = COALESCE(%s::jsonb, missing_requirement_json),
                        next_attempt_at = %s::timestamptz,
                        finished_at = CASE WHEN %s = 'terminal' THEN %s::timestamptz ELSE NULL END,
                        updated_at = %s::timestamptz,
                        lease_until = NULL, locked_by = '', lock_token = ''
                    WHERE gap_key = %s AND lock_token = %s AND status = 'running'
                    RETURNING gap_key, status
                    """,
                    (
                        status,
                        problem_code,
                        _json(missing_requirement) if missing_requirement is not None else None,
                        next_attempt_at,
                        status,
                        _text(now),
                        _text(now),
                        key,
                        token,
                    ),
                )
                row = cur.fetchone()
        if not row:
            raise GearEvidenceGapIntegrityError(
                "Gear Evidence Gap lease was lost before completion."
            )
        return {"gapKey": _text(row[0]), "status": _text(row[1])}

    def health_summary(self, *, now: str) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE status = 'pending'),
                        count(*) FILTER (WHERE status = 'running'),
                        count(*) FILTER (WHERE status = 'retryable'),
                        count(*) FILTER (WHERE status = 'terminal'),
                        min(next_attempt_at) FILTER (WHERE status IN ('pending', 'retryable'))
                    FROM (
                        SELECT status, next_attempt_at
                        FROM ops.websim_gear_evidence_gaps
                        ORDER BY queued_at DESC
                        LIMIT 1000
                    ) bounded_gaps
                    """
                )
                counts = cur.fetchone() or (0, 0, 0, 0, None)
                cur.execute(
                    """
                    SELECT problem_code, count(*)
                    FROM (
                        SELECT problem_code
                        FROM ops.websim_gear_evidence_gaps
                        WHERE status <> 'terminal'
                        ORDER BY queued_at DESC
                        LIMIT 1000
                    ) bounded_active_gaps
                    GROUP BY problem_code
                    ORDER BY count(*) DESC, problem_code
                    LIMIT 8
                    """
                )
                problem_counts = [
                    {"problemCode": _text(row[0]), "count": _int(row[1])}
                    for row in cur.fetchall()
                ]
        return {
            "checkedAt": _text(now),
            "statusCounts": {
                "pending": _int(counts[0]),
                "running": _int(counts[1]),
                "retryable": _int(counts[2]),
                "terminal": _int(counts[3]),
            },
            "oldestReadyAt": _text(counts[4]),
            "topProblemCodes": problem_counts,
        }


__all__ = ("GearEvidenceGapIntegrityError", "GearEvidenceGapStore")
