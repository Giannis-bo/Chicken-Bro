#!/usr/bin/env python3
"""Fenced handoff records for candidate-only Gear evidence recompilation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
from typing import Any, Mapping

try:
    from .gear_evidence_registry import (
        build_evidence_artifact,
        build_evidence_observation,
    )
    from .gear_fact_compiler import FACT_POLICIES
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_registry import (  # type: ignore[no-redef]
        build_evidence_artifact,
        build_evidence_observation,
    )
    from gear_fact_compiler import FACT_POLICIES  # type: ignore[no-redef]


REQUEST_SCHEMA_REVISION = "gear-evidence-candidate-request-v1"
DEFAULT_CANDIDATE_LEASE_SECONDS = 120
RETRY_DELAY_SECONDS = 300
_REQUEST_KEYS = {
    "schemaRevision",
    "requestKey",
    "gapKey",
    "artifactId",
    "observationIds",
    "seasonRevision",
    "subjectKey",
    "factType",
    "sourceType",
    "status",
    "attempt",
    "nextAttemptAt",
}


class GearEvidenceCandidateRequestIntegrityError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


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
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation input must be JSON-canonical."
        ) from error


def _is_hash(value: Any, prefix: str) -> bool:
    text = _text(value)
    suffix = text[len(prefix):] if text.startswith(prefix) else ""
    return len(suffix) == 64 and all(character in "0123456789abcdef" for character in suffix)


def _artifact(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    try:
        expected = build_evidence_artifact(
            source_type=source.get("sourceType"),
            source_identity=source.get("sourceIdentity"),
            source_revision=source.get("sourceRevision"),
            season_revision=source.get("seasonRevision"),
            captured_at=source.get("capturedAt"),
            payload=source.get("payload"),
        )
    except ValueError as error:
        raise GearEvidenceCandidateRequestIntegrityError(str(error)) from error
    if _canonical(source) != expected:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation Artifact is not canonical."
        )
    return expected


def _observation(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    try:
        expected = build_evidence_observation(
            artifact_id=source.get("artifactId"),
            subject_key=source.get("subjectKey"),
            fact_type=source.get("factType"),
            observed_value=source.get("observedValue"),
            parser_revision=source.get("parserRevision"),
            source_scope=source.get("sourceScope"),
            status=source.get("status"),
        )
    except ValueError as error:
        raise GearEvidenceCandidateRequestIntegrityError(str(error)) from error
    if _canonical(source) != expected:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation Observation is not canonical."
        )
    return expected


def build_candidate_recompile_request(
    *,
    gap_key: Any,
    artifact: Any,
    observations: Any,
    now: Any,
) -> dict[str, Any]:
    """Bind one recovered gap to exact immutable evidence before any sealing."""

    normalized_gap_key = _text(gap_key)
    normalized_now = _text(now)
    if not _is_hash(normalized_gap_key, "gear-gap:sha256:") or not normalized_now:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation gap identity and time are required."
        )
    normalized_artifact = _artifact(artifact)
    normalized_observations = sorted(
        (_observation(value) for value in observations or ()),
        key=lambda row: row["observationId"],
    )
    observation_ids = [row["observationId"] for row in normalized_observations]
    if not normalized_observations or len(observation_ids) != len(set(observation_ids)):
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation requires unique accepted Observations."
        )
    subject_key = normalized_observations[0]["subjectKey"]
    fact_type = normalized_observations[0]["factType"]
    policy = FACT_POLICIES.get(fact_type) or {}
    if (
        any(
            observation["artifactId"] != normalized_artifact["artifactId"]
            or observation["subjectKey"] != subject_key
            or observation["factType"] != fact_type
            or observation["status"] != "accepted"
            for observation in normalized_observations
        )
        or normalized_artifact["sourceType"] not in policy.get("allowedSources", ())
        or any(
            observation["sourceScope"] not in policy.get("sourceScopes", ())
            for observation in normalized_observations
        )
    ):
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation evidence does not satisfy its policy."
        )
    identity = {
        "schemaRevision": REQUEST_SCHEMA_REVISION,
        "gapKey": normalized_gap_key,
        "artifactId": normalized_artifact["artifactId"],
        "observationIds": observation_ids,
    }
    request_key = "gear-candidate-request:sha256:" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schemaRevision": REQUEST_SCHEMA_REVISION,
        "requestKey": request_key,
        "gapKey": normalized_gap_key,
        "artifactId": normalized_artifact["artifactId"],
        "observationIds": identity["observationIds"],
        "seasonRevision": normalized_artifact["seasonRevision"],
        "subjectKey": subject_key,
        "factType": fact_type,
        "sourceType": normalized_artifact["sourceType"],
        "status": "candidate_pending",
        "attempt": 0,
        "nextAttemptAt": normalized_now,
    }


def _request(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    if set(source) != _REQUEST_KEYS:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation request fields are invalid."
        )
    raw_observation_ids = [
        _text(item) for item in source.get("observationIds") or () if _text(item)
    ]
    normalized = {
        "schemaRevision": _text(source.get("schemaRevision")),
        "requestKey": _text(source.get("requestKey")),
        "gapKey": _text(source.get("gapKey")),
        "artifactId": _text(source.get("artifactId")),
        "observationIds": sorted(set(raw_observation_ids)),
        "seasonRevision": _text(source.get("seasonRevision")),
        "subjectKey": _text(source.get("subjectKey")),
        "factType": _text(source.get("factType")),
        "sourceType": _text(source.get("sourceType")),
        "status": _text(source.get("status")),
        "attempt": source.get("attempt"),
        "nextAttemptAt": _text(source.get("nextAttemptAt")),
    }
    identity = {
        "schemaRevision": REQUEST_SCHEMA_REVISION,
        "gapKey": normalized["gapKey"],
        "artifactId": normalized["artifactId"],
        "observationIds": normalized["observationIds"],
    }
    expected_request_key = "gear-candidate-request:sha256:" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        normalized["schemaRevision"] != REQUEST_SCHEMA_REVISION
        or not _is_hash(normalized["requestKey"], "gear-candidate-request:sha256:")
        or not _is_hash(normalized["gapKey"], "gear-gap:sha256:")
        or not _is_hash(normalized["artifactId"], "gear-artifact:sha256:")
        or not normalized["observationIds"]
        or len(normalized["observationIds"]) > 8
        or any(not _is_hash(value, "gear-observation:sha256:") for value in normalized["observationIds"])
        or not all(normalized[field] for field in ("seasonRevision", "subjectKey", "factType", "sourceType", "nextAttemptAt"))
        or normalized["status"] != "candidate_pending"
        or normalized["attempt"] != 0
        or len(normalized["observationIds"]) != len(raw_observation_ids)
        or normalized["requestKey"] != expected_request_key
    ):
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation request is incomplete."
        )
    return normalized


def _retry_at(now: Any) -> str:
    try:
        parsed = datetime.fromisoformat(_text(now).replace("Z", "+00:00"))
    except ValueError as error:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation time must be ISO-8601."
        ) from error
    if parsed.tzinfo is None:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation time must include a timezone."
        )
    return (parsed + timedelta(seconds=RETRY_DELAY_SECONDS)).isoformat()


def _row(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    status = _text(source.get("status"))
    request_key = _text(source.get("requestKey"))
    if not _is_hash(request_key, "gear-candidate-request:sha256:"):
        return {}
    return {
        "schemaRevision": _text(source.get("schemaRevision")) or REQUEST_SCHEMA_REVISION,
        "requestKey": request_key,
        "gapKey": _text(source.get("gapKey")),
        "artifactId": _text(source.get("artifactId")),
        "observationIds": sorted(_text(item) for item in source.get("observationIds") or () if _text(item)),
        "seasonRevision": _text(source.get("seasonRevision")),
        "subjectKey": _text(source.get("subjectKey")),
        "factType": _text(source.get("factType")),
        "sourceType": _text(source.get("sourceType")),
        "status": status,
        "attempt": int(source.get("attempt") or 0),
        "lockToken": _text(source.get("lockToken")),
        "candidateGearReleaseId": _text(source.get("candidateGearReleaseId")),
    }


class GearEvidenceCandidateRequestStore:
    """Own the atomic candidate-request and matching evidence-gap handoff."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    @contextmanager
    def connection(self):
        connection = self._connection_factory()
        try:
            yield connection
            if hasattr(connection, "commit"):
                connection.commit()
        except Exception:
            if hasattr(connection, "rollback"):
                connection.rollback()
            raise
        finally:
            if hasattr(connection, "close"):
                connection.close()

    @staticmethod
    def _json_request(cur, *, comment: str, request: Mapping[str, Any], now: str):
        cur.execute(
            f"""
            /* {comment} */
            INSERT INTO ops.websim_gear_evidence_candidate_requests (
                request_key, schema_revision, gap_key, artifact_id,
                observation_ids_json, season_revision, subject_key, fact_type,
                source_type, status, attempt, next_attempt_at, queued_at
            ) VALUES (
                %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s,
                'candidate_pending', 0, %s::timestamptz, %s::timestamptz
            )
            ON CONFLICT (request_key) DO NOTHING
            RETURNING jsonb_build_object(
                'schemaRevision', schema_revision,
                'requestKey', request_key,
                'gapKey', gap_key,
                'artifactId', artifact_id,
                'observationIds', observation_ids_json,
                'seasonRevision', season_revision,
                'subjectKey', subject_key,
                'factType', fact_type,
                'sourceType', source_type,
                'status', status,
                'attempt', attempt,
                'lockToken', lock_token,
                'candidateGearReleaseId', candidate_gear_release_id
            )
            """,
            (
                request["requestKey"], request["schemaRevision"], request["gapKey"],
                request["artifactId"], json.dumps(request["observationIds"]),
                request["seasonRevision"], request["subjectKey"], request["factType"],
                request["sourceType"], request["nextAttemptAt"], now,
            ),
        )
        return cur.fetchone()

    def enqueue(self, request: Any, *, now: str) -> dict[str, Any]:
        normalized = _request(request)
        with self.connection() as conn:
            with conn.cursor() as cur:
                row = self._json_request(
                    cur,
                    comment="gear_evidence_candidate_enqueue",
                    request=normalized,
                    now=_text(now),
                )
                if not row:
                    cur.execute(
                        """
                        SELECT jsonb_build_object(
                            'schemaRevision', schema_revision,
                            'requestKey', request_key,
                            'gapKey', gap_key,
                            'artifactId', artifact_id,
                            'observationIds', observation_ids_json,
                            'seasonRevision', season_revision,
                            'subjectKey', subject_key,
                            'factType', fact_type,
                            'sourceType', source_type,
                            'status', status,
                            'attempt', attempt,
                            'lockToken', lock_token,
                            'candidateGearReleaseId', candidate_gear_release_id
                        )
                        FROM ops.websim_gear_evidence_candidate_requests
                        WHERE request_key = %s
                        """,
                        (normalized["requestKey"],),
                    )
                    row = cur.fetchone()
        result = _row(row[0] if isinstance(row, (list, tuple)) else row)
        if not result:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate recompilation request could not be persisted."
            )
        return result

    def handoff_recovered(
        self,
        *,
        request: Any,
        gap_lock_token: str,
        now: str,
    ) -> dict[str, Any]:
        """Atomically turn one worker-owned gap into a candidate-owned handoff."""

        normalized = _request(request)
        token = _text(gap_lock_token)
        if not token:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate handoff gap lock token is required."
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                self._json_request(
                    cur,
                    comment="gear_evidence_candidate_handoff_insert",
                    request=normalized,
                    now=_text(now),
                )
                cur.execute(
                    """
                    /* gear_evidence_candidate_handoff_gap */
                    WITH handoff_gap AS (
                        UPDATE ops.websim_gear_evidence_gaps gap
                        SET status = 'candidate_pending',
                            candidate_request_key = %s,
                            locked_by = '', lock_token = '', lease_until = NULL,
                            next_attempt_at = %s::timestamptz,
                            finished_at = NULL, updated_at = %s::timestamptz
                        WHERE gap.gap_key = %s
                          AND gap.status = 'running'
                          AND gap.lock_token = %s
                        RETURNING gap.gap_key
                    )
                    UPDATE ops.websim_gear_evidence_candidate_requests request
                    SET status = 'candidate_pending',
                        locked_by = '', lock_token = '', lease_until = NULL,
                        next_attempt_at = %s::timestamptz,
                        updated_at = %s::timestamptz
                    WHERE request.request_key = %s
                      AND request.status = 'candidate_pending'
                      AND EXISTS (SELECT 1 FROM handoff_gap)
                    RETURNING jsonb_build_object(
                        'schemaRevision', request.schema_revision,
                        'requestKey', request.request_key,
                        'gapKey', request.gap_key,
                        'artifactId', request.artifact_id,
                        'observationIds', request.observation_ids_json,
                        'seasonRevision', request.season_revision,
                        'subjectKey', request.subject_key,
                        'factType', request.fact_type,
                        'sourceType', request.source_type,
                        'status', request.status,
                        'attempt', request.attempt,
                        'lockToken', request.lock_token,
                        'candidateGearReleaseId', request.candidate_gear_release_id
                    )
                    """,
                    (
                        normalized["requestKey"], _text(now), _text(now),
                        normalized["gapKey"], token, _text(now), _text(now),
                        normalized["requestKey"],
                    ),
                )
                row = cur.fetchone()
        result = _row(row[0] if isinstance(row, (list, tuple)) else row)
        if not result:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate recompilation handoff lost the evidence-gap lease."
            )
        return result

    def claim_next(
        self,
        *,
        worker_id: str,
        lock_token: str,
        now: str,
        lease_seconds: int = DEFAULT_CANDIDATE_LEASE_SECONDS,
    ) -> dict[str, Any]:
        worker = _text(worker_id)
        token = _text(lock_token)
        lease = max(30, min(int(lease_seconds or 0), 600))
        if not worker or not token:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate worker identity and lock token are required."
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    /* gear_evidence_candidate_claim */
                    WITH exhausted AS (
                        UPDATE ops.websim_gear_evidence_candidate_requests request
                        SET status = 'terminal', locked_by = '', lock_token = '',
                            lease_until = NULL, last_problem_code = 'candidate_recompile_failed',
                            finished_at = %s::timestamptz, updated_at = %s::timestamptz
                        FROM ops.websim_gear_evidence_gaps gap
                        WHERE request.status = 'candidate_pending'
                          AND request.attempt >= 3
                          AND gap.gap_key = request.gap_key
                          AND gap.status = 'candidate_pending'
                          AND gap.candidate_request_key = request.request_key
                        RETURNING request.request_key, request.gap_key
                    ), exhausted_gaps AS (
                        UPDATE ops.websim_gear_evidence_gaps gap
                        SET status = 'terminal', problem_code = 'source_unavailable',
                            locked_by = '', lock_token = '', lease_until = NULL,
                            finished_at = %s::timestamptz, updated_at = %s::timestamptz
                        FROM exhausted
                        WHERE gap.gap_key = exhausted.gap_key
                          AND gap.status = 'candidate_pending'
                          AND gap.candidate_request_key = exhausted.request_key
                        RETURNING gap.gap_key
                    ), stale AS (
                        UPDATE ops.websim_gear_evidence_candidate_requests request
                        SET status = 'candidate_pending', locked_by = '', lock_token = '',
                            lease_until = NULL, next_attempt_at = %s::timestamptz,
                            updated_at = %s::timestamptz
                        FROM ops.websim_gear_evidence_gaps gap
                        WHERE request.status = 'candidate_running'
                          AND request.lease_until < %s::timestamptz
                          AND gap.gap_key = request.gap_key
                          AND gap.status = 'candidate_running'
                          AND gap.candidate_request_key = request.request_key
                          AND gap.lock_token = request.lock_token
                        RETURNING request.request_key, request.gap_key
                    ), stale_gaps AS (
                        UPDATE ops.websim_gear_evidence_gaps gap
                        SET status = 'candidate_pending', locked_by = '', lock_token = '',
                            lease_until = NULL, next_attempt_at = %s::timestamptz,
                            updated_at = %s::timestamptz
                        FROM stale
                        WHERE gap.gap_key = stale.gap_key
                          AND gap.status = 'candidate_running'
                          AND gap.candidate_request_key = stale.request_key
                        RETURNING gap.gap_key
                    ), next_request AS (
                        SELECT request.request_key, request.gap_key
                        FROM ops.websim_gear_evidence_candidate_requests request
                        JOIN ops.websim_gear_evidence_gaps gap
                          ON gap.gap_key = request.gap_key
                        WHERE request.status = 'candidate_pending'
                          AND request.attempt < 3
                          AND request.next_attempt_at <= %s::timestamptz
                          AND gap.status = 'candidate_pending'
                          AND gap.candidate_request_key = request.request_key
                        ORDER BY request.next_attempt_at, request.queued_at, request.request_key
                        FOR UPDATE OF request, gap SKIP LOCKED
                        LIMIT 1
                    ), claimed_gap AS (
                        UPDATE ops.websim_gear_evidence_gaps gap
                        SET status = 'candidate_running', locked_by = %s, lock_token = %s,
                            lease_until = %s::timestamptz + make_interval(secs => %s),
                            updated_at = %s::timestamptz
                        FROM next_request
                        WHERE gap.gap_key = next_request.gap_key
                          AND gap.status = 'candidate_pending'
                          AND gap.candidate_request_key = next_request.request_key
                        RETURNING gap.gap_key
                    ), claimed_request AS (
                        UPDATE ops.websim_gear_evidence_candidate_requests request
                        SET status = 'candidate_running', attempt = request.attempt + 1,
                            locked_by = %s, lock_token = %s,
                            lease_until = %s::timestamptz + make_interval(secs => %s),
                            started_at = COALESCE(request.started_at, %s::timestamptz),
                            updated_at = %s::timestamptz
                        FROM next_request
                        WHERE request.request_key = next_request.request_key
                          AND EXISTS (SELECT 1 FROM claimed_gap)
                        RETURNING request.*
                    )
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'requestKey', request_key,
                        'gapKey', gap_key,
                        'artifactId', artifact_id,
                        'observationIds', observation_ids_json,
                        'seasonRevision', season_revision,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'sourceType', source_type,
                        'status', status,
                        'attempt', attempt,
                        'lockToken', lock_token,
                        'candidateGearReleaseId', candidate_gear_release_id
                    )
                    FROM claimed_request
                    """,
                    (
                        _text(now), _text(now),
                        _text(now), _text(now),
                        _text(now), _text(now), _text(now),
                        _text(now), _text(now),
                        _text(now),
                        worker, token, _text(now), lease, _text(now),
                        worker, token, _text(now), lease, _text(now), _text(now),
                    ),
                )
                row = cur.fetchone()
        return _row(row[0] if isinstance(row, (list, tuple)) else row)

    def retry(
        self,
        *,
        request_key: str,
        lock_token: str,
        problem_code: str,
        now: str,
    ) -> dict[str, Any]:
        return self._finish(
            request_key=request_key,
            lock_token=lock_token,
            now=now,
            status="candidate_pending",
            problem_code=problem_code,
            candidate_gear_release_id="",
            comment="gear_evidence_candidate_retry",
        )

    def complete_sealed(
        self,
        *,
        request_key: str,
        lock_token: str,
        candidate_gear_release_id: str,
        now: str,
    ) -> dict[str, Any]:
        if not _text(candidate_gear_release_id):
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate Gear Release identity is required."
            )
        return self._finish(
            request_key=request_key,
            lock_token=lock_token,
            now=now,
            status="terminal",
            problem_code="",
            candidate_gear_release_id=_text(candidate_gear_release_id),
            comment="gear_evidence_candidate_complete",
        )

    def _finish(
        self,
        *,
        request_key: str,
        lock_token: str,
        now: str,
        status: str,
        problem_code: str,
        candidate_gear_release_id: str,
        comment: str,
    ) -> dict[str, Any]:
        key = _text(request_key)
        token = _text(lock_token)
        if not _is_hash(key, "gear-candidate-request:sha256:") or not token:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate recompilation fence identity is invalid."
            )
        next_attempt_at = _retry_at(now) if status == "candidate_pending" else _text(now)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    /* {comment} */
                    WITH finished_gap AS (
                        UPDATE ops.websim_gear_evidence_gaps gap
                        SET status = %s,
                            locked_by = '', lock_token = '', lease_until = NULL,
                            next_attempt_at = %s::timestamptz,
                            finished_at = CASE WHEN %s = 'terminal' THEN %s::timestamptz ELSE NULL END,
                            updated_at = %s::timestamptz
                        FROM ops.websim_gear_evidence_candidate_requests request
                        WHERE request.request_key = %s
                          AND request.status = 'candidate_running'
                          AND request.lock_token = %s
                          AND gap.gap_key = request.gap_key
                          AND gap.status = 'candidate_running'
                          AND gap.candidate_request_key = request.request_key
                          AND gap.lock_token = request.lock_token
                        RETURNING gap.gap_key
                    ), finished_request AS (
                        UPDATE ops.websim_gear_evidence_candidate_requests request
                        SET status = %s,
                            locked_by = '', lock_token = '', lease_until = NULL,
                            next_attempt_at = %s::timestamptz,
                            candidate_gear_release_id = %s,
                            last_problem_code = %s,
                            finished_at = CASE WHEN %s = 'terminal' THEN %s::timestamptz ELSE NULL END,
                            updated_at = %s::timestamptz
                        WHERE request.request_key = %s
                          AND request.status = 'candidate_running'
                          AND request.lock_token = %s
                          AND EXISTS (SELECT 1 FROM finished_gap)
                        RETURNING request.*
                    )
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'requestKey', request_key,
                        'gapKey', gap_key,
                        'artifactId', artifact_id,
                        'observationIds', observation_ids_json,
                        'seasonRevision', season_revision,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'sourceType', source_type,
                        'status', status,
                        'attempt', attempt,
                        'lockToken', lock_token,
                        'candidateGearReleaseId', candidate_gear_release_id
                    )
                    FROM finished_request
                    """,
                    (
                        status, next_attempt_at, status, _text(now), _text(now), key, token,
                        status, next_attempt_at, candidate_gear_release_id, _text(problem_code),
                        status, _text(now), _text(now), key, token,
                    ),
                )
                row = cur.fetchone()
        result = _row(row[0] if isinstance(row, (list, tuple)) else row)
        if not result:
            raise GearEvidenceCandidateRequestIntegrityError(
                "Candidate recompilation lease was lost before completion."
            )
        return result


def validate_candidate_recompile_evidence(
    request: Any,
    evidence: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Verify the worker-supplied immutable input has not changed before sealing."""

    source = request if isinstance(request, Mapping) else {}
    bundle = evidence if isinstance(evidence, Mapping) else {}
    artifacts = [_artifact(value) for value in bundle.get("artifacts") or ()]
    observations = [_observation(value) for value in bundle.get("observations") or ()]
    if len(artifacts) != 1 or not observations:
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation evidence bundle is incomplete."
        )
    artifact = artifacts[0]
    expected_observation_ids = sorted(_text(value) for value in source.get("observationIds") or ())
    if (
        artifact["artifactId"] != _text(source.get("artifactId"))
        or artifact["seasonRevision"] != _text(source.get("seasonRevision"))
        or artifact["sourceType"] != _text(source.get("sourceType"))
        or sorted(observation["observationId"] for observation in observations)
        != expected_observation_ids
        or any(
            observation["artifactId"] != artifact["artifactId"]
            or observation["subjectKey"] != _text(source.get("subjectKey"))
            or observation["factType"] != _text(source.get("factType"))
            or observation["status"] != "accepted"
            for observation in observations
        )
    ):
        raise GearEvidenceCandidateRequestIntegrityError(
            "Candidate recompilation evidence no longer matches its fenced request."
        )
    return {
        "artifacts": sorted(artifacts, key=lambda row: row["artifactId"]),
        "observations": sorted(observations, key=lambda row: row["observationId"]),
    }


__all__ = (
    "GearEvidenceCandidateRequestIntegrityError",
    "GearEvidenceCandidateRequestStore",
    "REQUEST_SCHEMA_REVISION",
    "build_candidate_recompile_request",
    "validate_candidate_recompile_evidence",
)
