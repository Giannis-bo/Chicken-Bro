#!/usr/bin/env python3
"""PostgreSQL owner for fenced winner attribute-rule audit records."""

from __future__ import annotations

import json
from typing import Any


class AttributeRuleAuditIntegrityError(RuntimeError):
    pass


_ENQUEUE_STATUSES = {"pending", "not_applicable", "blocked_missing_evidence"}
_FINISH_STATUSES = {
    "blocked_source_unavailable",
    "inconclusive_input_mismatch",
    "pass",
    "confirmed_mismatch",
}
_ROW_COLUMNS = (
    "audit_key", "candidate_community_release_id", "candidate_gear_release_id", "manifest_revision",
    "attribute_rule_revision", "context_key", "status", "canonical_input_signature", "input_json",
    "result_json", "attempt", "locked_by", "lock_token", "lease_until", "queued_at", "started_at",
    "finished_at", "created_at", "updated_at",
)
_ROW_SELECT = ", ".join(_ROW_COLUMNS)
_CLAIM_ROW_SELECT = ", ".join(f"audit.{column}" for column in _ROW_COLUMNS)


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
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_hash(value: Any, prefix: str) -> bool:
    text = _text(value)
    suffix = text[len(prefix):] if text.startswith(prefix) else ""
    return len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)


def _audit_from_row(row: Any) -> dict[str, Any]:
    values = list(row or [])
    if len(values) < len(_ROW_COLUMNS):
        return {}
    return {
        "auditKey": _text(values[0]),
        "candidateCommunityReleaseId": _text(values[1]),
        "candidateGearReleaseId": _text(values[2]),
        "manifestRevision": _text(values[3]),
        "attributeRuleRevision": _text(values[4]),
        "contextKey": _text(values[5]),
        "status": _text(values[6]),
        "canonicalInputSignature": _text(values[7]),
        "input": _canonical(values[8] if isinstance(values[8], dict) else {}),
        "result": _canonical(values[9] if isinstance(values[9], dict) else {}),
        "attempt": _int(values[10]),
        "lockedBy": _text(values[11]),
        "lockToken": _text(values[12]),
        "leaseUntil": _text(values[13]),
        "queuedAt": _text(values[14]),
        "startedAt": _text(values[15]),
        "finishedAt": _text(values[16]),
        "createdAt": _text(values[17]),
        "updatedAt": _text(values[18]),
    }


class AttributeRuleAuditStore:
    """Own every SQL operation for asynchronous winner attribute audits."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _validate_intent(intent: Any) -> dict[str, Any]:
        if not isinstance(intent, dict):
            raise AttributeRuleAuditIntegrityError("attribute audit intent must be an object")
        if _text(intent.get("status")) not in _ENQUEUE_STATUSES:
            raise AttributeRuleAuditIntegrityError("unsupported attribute audit enqueue status")
        required = (
            "auditKey", "candidateCommunityReleaseId", "candidateGearReleaseId", "manifestRevision",
            "attributeRuleRevision", "contextKey", "canonicalInputSignature",
        )
        normalized = {key: _text(intent.get(key)) for key in required}
        if any(not value for value in normalized.values()):
            raise AttributeRuleAuditIntegrityError("attribute audit identity is incomplete")
        if not _is_hash(normalized["auditKey"], "attribute-audit:sha256:"):
            raise AttributeRuleAuditIntegrityError("attribute audit key is invalid")
        if not _is_hash(normalized["canonicalInputSignature"], "sha256:"):
            raise AttributeRuleAuditIntegrityError("attribute audit input signature is invalid")
        input_payload = {
            "sourceIdentity": _canonical(intent.get("sourceIdentity") if isinstance(intent.get("sourceIdentity"), dict) else {}),
            "sealedInput": _canonical(intent.get("sealedInput") if isinstance(intent.get("sealedInput"), dict) else {}),
            "rule": _canonical(intent.get("rule") if isinstance(intent.get("rule"), dict) else {}),
        }
        status = _text(intent.get("status"))
        if status == "pending" and (not input_payload["sourceIdentity"] or not input_payload["sealedInput"] or not input_payload["rule"]):
            raise AttributeRuleAuditIntegrityError("pending attribute audit input is incomplete")
        code = _text(intent.get("code"))[:120]
        return {
            **normalized,
            "status": status,
            "input": input_payload,
            "result": {"code": code} if status != "pending" and code else {},
        }

    def enqueue_intents(self, intents: list[dict[str, Any]], *, now: str) -> dict[str, int]:
        inserted = 0
        reused = 0
        for raw_intent in intents if isinstance(intents, list) else []:
            intent = self._validate_intent(raw_intent)
            with self.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ops.websim_attribute_rule_audits (
                            audit_key, candidate_community_release_id, candidate_gear_release_id,
                            manifest_revision, attribute_rule_revision, context_key, status,
                            canonical_input_signature, input_json, result_json, queued_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::timestamptz)
                        ON CONFLICT (audit_key) DO NOTHING
                        RETURNING audit_key, status
                        """,
                        (
                            intent["auditKey"], intent["candidateCommunityReleaseId"], intent["candidateGearReleaseId"],
                            intent["manifestRevision"], intent["attributeRuleRevision"], intent["contextKey"],
                            intent["status"], intent["canonicalInputSignature"], _json(intent["input"]),
                            _json(intent["result"]), _text(now),
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
            raise AttributeRuleAuditIntegrityError("worker identity and lock token are required")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_attribute_rule_audits
                    SET status = 'blocked_source_unavailable', lease_until = NULL, locked_by = '', lock_token = '',
                        finished_at = %s::timestamptz, updated_at = %s::timestamptz,
                        result_json = jsonb_build_object('code', 'ATTRIBUTE_AUDIT_MAX_ATTEMPTS')
                    WHERE attempt >= 3 AND (status = 'pending' OR (status = 'running' AND lease_until < %s::timestamptz))
                    RETURNING audit_key
                    """,
                    (_text(now), _text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    """
                    UPDATE ops.websim_attribute_rule_audits
                    SET status = 'pending', locked_by = '', lock_token = '', lease_until = NULL,
                        updated_at = %s::timestamptz,
                        result_json = jsonb_build_object('code', 'ATTRIBUTE_AUDIT_RECLAIMED')
                    WHERE status = 'running' AND attempt < 3 AND lease_until < %s::timestamptz
                    RETURNING audit_key
                    """,
                    (_text(now), _text(now)),
                )
                cur.fetchall()
                cur.execute(
                    f"""
                    WITH next_audit AS (
                        SELECT audit_key
                        FROM ops.websim_attribute_rule_audits
                        WHERE status = 'pending' AND attempt < 3
                        ORDER BY queued_at, audit_key
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE ops.websim_attribute_rule_audits audit
                    SET status = 'running', attempt = audit.attempt + 1,
                        locked_by = %s, lock_token = %s,
                        lease_until = %s::timestamptz + make_interval(secs => %s),
                        started_at = COALESCE(audit.started_at, %s::timestamptz),
                        updated_at = %s::timestamptz,
                        result_json = '{{}}'::jsonb
                    FROM next_audit
                    WHERE audit.audit_key = next_audit.audit_key
                    RETURNING {_CLAIM_ROW_SELECT}
                    """,
                    (worker, token, _text(now), lease, _text(now), _text(now)),
                )
                return _audit_from_row(cur.fetchone())

    def finish(self, *, audit_key: str, lock_token: str, outcome: dict[str, Any], now: str) -> dict[str, Any]:
        key = _text(audit_key)
        token = _text(lock_token)
        status = _text((outcome or {}).get("status"))
        if not _is_hash(key, "attribute-audit:sha256:") or not token:
            raise AttributeRuleAuditIntegrityError("attribute audit fence identity is invalid")
        if status not in _FINISH_STATUSES:
            raise AttributeRuleAuditIntegrityError("unsupported attribute audit terminal status")
        result = _canonical((outcome or {}).get("result") if isinstance((outcome or {}).get("result"), dict) else {})
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ops.websim_attribute_rule_audits
                    SET status = %s, result_json = %s::jsonb, finished_at = %s::timestamptz,
                        updated_at = %s::timestamptz, lease_until = NULL, locked_by = '', lock_token = ''
                    WHERE audit_key = %s AND lock_token = %s AND status = 'running'
                    RETURNING audit_key, status
                    """,
                    (status, _json(result), _text(now), _text(now), key, token),
                )
                row = cur.fetchone()
        if not row:
            raise AttributeRuleAuditIntegrityError("attribute audit lease was lost before completion")
        return {"auditKey": _text(row[0]), "status": _text(row[1])}

    def health_summary(self, *, now: str) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE status = 'pending'),
                        count(*) FILTER (WHERE status = 'running'),
                        count(*) FILTER (WHERE status = 'pass'),
                        count(*) FILTER (WHERE status = 'confirmed_mismatch'),
                        count(*) FILTER (WHERE status = 'inconclusive_input_mismatch'),
                        count(*) FILTER (WHERE status = 'blocked_source_unavailable'),
                        max(finished_at)
                    FROM (
                        SELECT status, finished_at
                        FROM ops.websim_attribute_rule_audits
                        ORDER BY queued_at DESC
                        LIMIT 1000
                    ) bounded_audits
                    """
                )
                counts = cur.fetchone() or (0, 0, 0, 0, 0, 0, None)
                cur.execute(
                    """
                    SELECT attribute_rule_revision, context_key
                    FROM ops.websim_attribute_rule_audits
                    WHERE status = 'confirmed_mismatch'
                    ORDER BY finished_at DESC, audit_key
                    LIMIT 8
                    """
                )
                findings = [
                    {"attributeRuleRevision": _text(row[0]), "contextKey": _text(row[1])}
                    for row in cur.fetchall()
                ]
        return {
            "checkedAt": _text(now),
            "queue": {"pending": _int(counts[0]), "running": _int(counts[1])},
            "terminalCounts": {
                "pass": _int(counts[2]),
                "confirmedMismatch": _int(counts[3]),
                "inconclusive": _int(counts[4]),
                "sourceUnavailable": _int(counts[5]),
            },
            "latestCheckedAt": _text(counts[6]),
            "findingRuleContexts": findings,
        }


__all__ = ("AttributeRuleAuditIntegrityError", "AttributeRuleAuditStore")
