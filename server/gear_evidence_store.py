#!/usr/bin/env python3
"""PostgreSQL owner for immutable Gear Evidence Registry records."""

from __future__ import annotations

import json
from typing import Any

from server.gear_evidence_registry import (
    build_canonical_fact,
    build_evidence_artifact,
    build_evidence_observation,
)


class GearEvidenceStoreIntegrityError(RuntimeError):
    pass


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
        raise GearEvidenceStoreIntegrityError(
            "Gear evidence persistence values must be JSON-canonical."
        ) from error


def _json(value: Any) -> str:
    return json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_limit(value: Any) -> int:
    if isinstance(value, bool):
        return 100
    try:
        return max(1, min(int(value), 500))
    except (TypeError, ValueError, OverflowError):
        return 100


def _is_hash(value: Any, prefix: str) -> bool:
    text = _text(value)
    suffix = text[len(prefix) :] if text.startswith(prefix) else ""
    return len(suffix) == 64 and all(character in "0123456789abcdef" for character in suffix)


def _validated_artifact(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise GearEvidenceStoreIntegrityError("Gear evidence artifact must be an object.")
    try:
        expected = build_evidence_artifact(
            source_type=record.get("sourceType"),
            source_identity=record.get("sourceIdentity"),
            source_revision=record.get("sourceRevision"),
            season_revision=record.get("seasonRevision"),
            captured_at=record.get("capturedAt"),
            payload=record.get("payload"),
        )
    except ValueError as error:
        raise GearEvidenceStoreIntegrityError(str(error)) from error
    if _canonical(record) != expected:
        raise GearEvidenceStoreIntegrityError(
            "Gear evidence artifact does not match its canonical constructor."
        )
    return expected


def _validated_observation(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise GearEvidenceStoreIntegrityError("Gear evidence observation must be an object.")
    try:
        expected = build_evidence_observation(
            artifact_id=record.get("artifactId"),
            subject_key=record.get("subjectKey"),
            fact_type=record.get("factType"),
            observed_value=record.get("observedValue"),
            parser_revision=record.get("parserRevision"),
            source_scope=record.get("sourceScope"),
            status=record.get("status"),
        )
    except ValueError as error:
        raise GearEvidenceStoreIntegrityError(str(error)) from error
    if _canonical(record) != expected:
        raise GearEvidenceStoreIntegrityError(
            "Gear evidence observation does not match its canonical constructor."
        )
    return expected


def _validated_fact(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise GearEvidenceStoreIntegrityError("Canonical gear fact must be an object.")
    try:
        expected = build_canonical_fact(
            season_revision=record.get("seasonRevision"),
            subject_key=record.get("subjectKey"),
            fact_type=record.get("factType"),
            value=record.get("value"),
            status=record.get("status"),
            observation_refs=record.get("observationRefs") or [],
            compiler_rule_revision=record.get("compilerRuleRevision"),
            impact_scope=record.get("impactScope"),
            problem_code=record.get("problemCode"),
        )
    except ValueError as error:
        raise GearEvidenceStoreIntegrityError(str(error)) from error
    if _canonical(record) != expected:
        raise GearEvidenceStoreIntegrityError(
            "Canonical gear fact does not match its public hash constructors."
        )
    return expected


def _validated_invalidation(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise GearEvidenceStoreIntegrityError("Gear evidence invalidation must be an object.")
    allowed_keys = {
        "schemaRevision",
        "invalidationId",
        "artifactId",
        "observationId",
        "reasonCode",
        "detail",
        "invalidatedAt",
    }
    if set(record) != allowed_keys:
        raise GearEvidenceStoreIntegrityError("Gear evidence invalidation fields are invalid.")
    normalized = {
        "schemaRevision": _text(record.get("schemaRevision")),
        "invalidationId": _text(record.get("invalidationId")),
        "artifactId": _text(record.get("artifactId")),
        "observationId": _text(record.get("observationId")),
        "reasonCode": _text(record.get("reasonCode")),
        "detail": _canonical(record.get("detail")),
        "invalidatedAt": _text(record.get("invalidatedAt")),
    }
    if normalized["schemaRevision"] != "gear-evidence-invalidation-v1":
        raise GearEvidenceStoreIntegrityError("Gear evidence invalidation schema is invalid.")
    if not _is_hash(normalized["invalidationId"], "gear-invalidation:sha256:"):
        raise GearEvidenceStoreIntegrityError("Gear evidence invalidation identity is invalid.")
    if bool(normalized["artifactId"]) == bool(normalized["observationId"]):
        raise GearEvidenceStoreIntegrityError(
            "Gear evidence invalidation must target one Artifact or Observation."
        )
    if normalized["artifactId"] and not _is_hash(
        normalized["artifactId"], "gear-artifact:sha256:"
    ):
        raise GearEvidenceStoreIntegrityError("Gear evidence Artifact target is invalid.")
    if normalized["observationId"] and not _is_hash(
        normalized["observationId"], "gear-observation:sha256:"
    ):
        raise GearEvidenceStoreIntegrityError("Gear evidence Observation target is invalid.")
    if (
        not normalized["reasonCode"]
        or not normalized["invalidatedAt"]
        or not isinstance(normalized["detail"], dict)
    ):
        raise GearEvidenceStoreIntegrityError("Gear evidence invalidation is incomplete.")
    return normalized


class GearEvidenceStore:
    """Own Artifact, Observation, invalidation, and Fact SQL only."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    def persist_artifact(self, record: dict[str, Any]) -> dict[str, Any]:
        artifact = _validated_artifact(record)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_gear_evidence_artifacts (
                        artifact_id, schema_revision, source_type, source_identity,
                        source_revision, season_revision, captured_at, payload_hash, payload_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s::jsonb
                    )
                    ON CONFLICT (artifact_id) DO NOTHING
                    RETURNING jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'artifactId', artifact_id,
                        'sourceType', source_type,
                        'sourceIdentity', source_identity,
                        'sourceRevision', source_revision,
                        'seasonRevision', season_revision,
                        'capturedAt', captured_at,
                        'payloadHash', payload_hash,
                        'payload', payload_json
                    )
                    """,
                    (
                        artifact["artifactId"],
                        artifact["schemaRevision"],
                        artifact["sourceType"],
                        artifact["sourceIdentity"],
                        artifact["sourceRevision"],
                        artifact["seasonRevision"],
                        artifact["capturedAt"],
                        artifact["payloadHash"],
                        _json(artifact["payload"]),
                    ),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT jsonb_build_object(
                            'schemaRevision', schema_revision,
                            'artifactId', artifact_id,
                            'sourceType', source_type,
                            'sourceIdentity', source_identity,
                            'sourceRevision', source_revision,
                            'seasonRevision', season_revision,
                            'capturedAt', captured_at,
                            'payloadHash', payload_hash,
                            'payload', payload_json
                        )
                        FROM cache.websim_gear_evidence_artifacts
                        WHERE artifact_id = %s
                        """,
                        (artifact["artifactId"],),
                    )
                    row = cur.fetchone()
        persisted = row[0] if row and isinstance(row[0], dict) else {}
        if not persisted:
            raise GearEvidenceStoreIntegrityError(
                "Gear evidence Artifact conflict could not be reused."
            )
        return _validated_artifact(persisted)

    def persist_observation(self, record: dict[str, Any]) -> dict[str, Any]:
        observation = _validated_observation(record)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_gear_evidence_observations (
                        observation_id, artifact_id, schema_revision, subject_key, fact_type,
                        observed_value_json, parser_revision, source_scope, status
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (observation_id) DO NOTHING
                    RETURNING jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'observationId', observation_id,
                        'artifactId', artifact_id,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'observedValue', observed_value_json,
                        'parserRevision', parser_revision,
                        'sourceScope', source_scope,
                        'status', status
                    )
                    """,
                    (
                        observation["observationId"],
                        observation["artifactId"],
                        observation["schemaRevision"],
                        observation["subjectKey"],
                        observation["factType"],
                        _json(observation["observedValue"]),
                        observation["parserRevision"],
                        observation["sourceScope"],
                        observation["status"],
                    ),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT jsonb_build_object(
                            'schemaRevision', schema_revision,
                            'observationId', observation_id,
                            'artifactId', artifact_id,
                            'subjectKey', subject_key,
                            'factType', fact_type,
                            'observedValue', observed_value_json,
                            'parserRevision', parser_revision,
                            'sourceScope', source_scope,
                            'status', status
                        )
                        FROM cache.websim_gear_evidence_observations
                        WHERE observation_id = %s
                        """,
                        (observation["observationId"],),
                    )
                    row = cur.fetchone()
        persisted = row[0] if row and isinstance(row[0], dict) else {}
        if not persisted:
            raise GearEvidenceStoreIntegrityError(
                "Gear evidence Observation conflict could not be reused."
            )
        return _validated_observation(persisted)

    def persist_fact(self, record: dict[str, Any]) -> dict[str, Any]:
        fact = _validated_fact(record)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_gear_canonical_facts (
                        fact_key, schema_revision, season_revision, subject_key, fact_type,
                        value_json, status, observation_refs_json, fact_value_hash,
                        provenance_hash, compiler_rule_revision, impact_scope, problem_code
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (fact_key, fact_value_hash, provenance_hash) DO NOTHING
                    RETURNING jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'factKey', fact_key,
                        'seasonRevision', season_revision,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'value', value_json,
                        'status', status,
                        'observationRefs', observation_refs_json,
                        'compilerRuleRevision', compiler_rule_revision,
                        'factValueHash', fact_value_hash,
                        'provenanceHash', provenance_hash,
                        'impactScope', impact_scope,
                        'problemCode', problem_code
                    )
                    """,
                    (
                        fact["factKey"],
                        fact["schemaRevision"],
                        fact["seasonRevision"],
                        fact["subjectKey"],
                        fact["factType"],
                        _json(fact["value"]),
                        fact["status"],
                        _json(fact["observationRefs"]),
                        fact["factValueHash"],
                        fact["provenanceHash"],
                        fact["compilerRuleRevision"],
                        fact["impactScope"],
                        fact["problemCode"],
                    ),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT jsonb_build_object(
                            'schemaRevision', schema_revision,
                            'factKey', fact_key,
                            'seasonRevision', season_revision,
                            'subjectKey', subject_key,
                            'factType', fact_type,
                            'value', value_json,
                            'status', status,
                            'observationRefs', observation_refs_json,
                            'compilerRuleRevision', compiler_rule_revision,
                            'factValueHash', fact_value_hash,
                            'provenanceHash', provenance_hash,
                            'impactScope', impact_scope,
                            'problemCode', problem_code
                        )
                        FROM cache.websim_gear_canonical_facts
                        WHERE fact_key = %s
                          AND fact_value_hash = %s
                          AND provenance_hash = %s
                        """,
                        (
                            fact["factKey"],
                            fact["factValueHash"],
                            fact["provenanceHash"],
                        ),
                    )
                    row = cur.fetchone()
        persisted = row[0] if row and isinstance(row[0], dict) else {}
        if not persisted:
            raise GearEvidenceStoreIntegrityError(
                "Canonical gear Fact conflict could not be reused."
            )
        return _validated_fact(persisted)

    def persist_invalidation(self, record: dict[str, Any]) -> dict[str, Any]:
        invalidation = _validated_invalidation(record)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cache.websim_gear_evidence_invalidations (
                        invalidation_id, schema_revision, artifact_id, observation_id,
                        reason_code, detail_json, invalidated_at
                    ) VALUES (%s, %s, NULLIF(%s, ''), NULLIF(%s, ''), %s, %s::jsonb, %s::timestamptz)
                    ON CONFLICT (invalidation_id) DO NOTHING
                    RETURNING jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'invalidationId', invalidation_id,
                        'artifactId', artifact_id,
                        'observationId', observation_id,
                        'reasonCode', reason_code,
                        'detail', detail_json,
                        'invalidatedAt', invalidated_at
                    )
                    """,
                    (
                        invalidation["invalidationId"],
                        invalidation["schemaRevision"],
                        invalidation["artifactId"],
                        invalidation["observationId"],
                        invalidation["reasonCode"],
                        _json(invalidation["detail"]),
                        invalidation["invalidatedAt"],
                    ),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT jsonb_build_object(
                            'schemaRevision', schema_revision,
                            'invalidationId', invalidation_id,
                            'artifactId', artifact_id,
                            'observationId', observation_id,
                            'reasonCode', reason_code,
                            'detail', detail_json,
                            'invalidatedAt', invalidated_at
                        )
                        FROM cache.websim_gear_evidence_invalidations
                        WHERE invalidation_id = %s
                        """,
                        (invalidation["invalidationId"],),
                    )
                    row = cur.fetchone()
        persisted = row[0] if row and isinstance(row[0], dict) else {}
        if not persisted:
            raise GearEvidenceStoreIntegrityError(
                "Gear evidence invalidation conflict could not be reused."
            )
        return _validated_invalidation(persisted)

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        identity = _text(artifact_id)
        if not _is_hash(identity, "gear-artifact:sha256:"):
            raise GearEvidenceStoreIntegrityError("Gear evidence Artifact identity is invalid.")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'artifactId', artifact_id,
                        'sourceType', source_type,
                        'sourceIdentity', source_identity,
                        'sourceRevision', source_revision,
                        'seasonRevision', season_revision,
                        'capturedAt', captured_at,
                        'payloadHash', payload_hash,
                        'payload', payload_json
                    )
                    FROM cache.websim_gear_evidence_artifacts
                    WHERE artifact_id = %s
                    """,
                    (identity,),
                )
                row = cur.fetchone()
        return _canonical(row[0]) if row and isinstance(row[0], dict) else {}

    def list_invalidations(
        self,
        *,
        artifact_id: str = "",
        observation_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        artifact = _text(artifact_id)
        observation = _text(observation_id)
        if bool(artifact) == bool(observation):
            raise GearEvidenceStoreIntegrityError(
                "Invalidation query requires one Artifact or Observation target."
            )
        if artifact and not _is_hash(artifact, "gear-artifact:sha256:"):
            raise GearEvidenceStoreIntegrityError("Gear evidence Artifact identity is invalid.")
        if observation and not _is_hash(observation, "gear-observation:sha256:"):
            raise GearEvidenceStoreIntegrityError(
                "Gear evidence Observation identity is invalid."
            )
        target_column = "artifact_id" if artifact else "observation_id"
        target_identity = artifact or observation
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    f"""
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'invalidationId', invalidation_id,
                        'artifactId', artifact_id,
                        'observationId', observation_id,
                        'reasonCode', reason_code,
                        'detail', detail_json,
                        'invalidatedAt', invalidated_at
                    )
                    FROM cache.websim_gear_evidence_invalidations
                    WHERE {target_column} = %s
                    ORDER BY invalidated_at DESC, invalidation_id
                    LIMIT %s
                    """,
                    (target_identity, _bounded_limit(limit)),
                )
                rows = cur.fetchall()
        return [
            _validated_invalidation(row[0])
            for row in rows
            if row and isinstance(row[0], dict)
        ]

    def list_observations(
        self,
        *,
        subject_key: str,
        fact_type: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        subject = _text(subject_key)
        if not subject:
            raise GearEvidenceStoreIntegrityError("Observation subject key is required.")
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'observationId', observation_id,
                        'artifactId', artifact_id,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'observedValue', observed_value_json,
                        'parserRevision', parser_revision,
                        'sourceScope', source_scope,
                        'status', status
                    )
                    FROM cache.websim_gear_evidence_observations
                    WHERE subject_key = %s
                      AND (%s = '' OR fact_type = %s)
                    ORDER BY observation_id
                    LIMIT %s
                    """,
                    (subject, _text(fact_type), _text(fact_type), _bounded_limit(limit)),
                )
                rows = cur.fetchall()
        return [_canonical(row[0]) for row in rows if row and isinstance(row[0], dict)]

    def list_facts(
        self,
        *,
        season_revision: str,
        subject_key: str,
        fact_type: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        season = _text(season_revision)
        subject = _text(subject_key)
        if not season or not subject:
            raise GearEvidenceStoreIntegrityError(
                "Fact season revision and subject key are required."
            )
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT jsonb_build_object(
                        'schemaRevision', schema_revision,
                        'factKey', fact_key,
                        'seasonRevision', season_revision,
                        'subjectKey', subject_key,
                        'factType', fact_type,
                        'value', value_json,
                        'status', status,
                        'observationRefs', observation_refs_json,
                        'compilerRuleRevision', compiler_rule_revision,
                        'factValueHash', fact_value_hash,
                        'provenanceHash', provenance_hash,
                        'impactScope', impact_scope,
                        'problemCode', problem_code
                    )
                    FROM cache.websim_gear_canonical_facts
                    WHERE season_revision = %s
                      AND subject_key = %s
                      AND (%s = '' OR fact_type = %s)
                    ORDER BY created_at DESC, fact_value_hash, provenance_hash
                    LIMIT %s
                    """,
                    (
                        season,
                        subject,
                        _text(fact_type),
                        _text(fact_type),
                        _bounded_limit(limit),
                    ),
                )
                rows = cur.fetchall()
        return [_canonical(row[0]) for row in rows if row and isinstance(row[0], dict)]


__all__ = ("GearEvidenceStore", "GearEvidenceStoreIntegrityError")
