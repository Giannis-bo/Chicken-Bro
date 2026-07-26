#!/usr/bin/env python3
"""Pure, deterministic contracts for immutable gear evidence records."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


EVIDENCE_ARTIFACT_SCHEMA_REVISION = "gear-evidence-artifact-v1"
EVIDENCE_OBSERVATION_SCHEMA_REVISION = "gear-evidence-observation-v1"
CANONICAL_FACT_SCHEMA_REVISION = "gear-canonical-fact-v1"
CANONICAL_FACT_STATUSES = (
    "verified",
    "unresolved_missing",
    "unresolved_conflict",
)

_SECRET_KEY_FRAGMENTS = (
    "accesstoken",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)


def _canonical(value: Any) -> Any:
    """Return a detached JSON value in canonical key order."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Evidence values must be JSON-canonical.") from error
    return json.loads(encoded)


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _required_string(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _normalized_refs(values: Iterable[Any]) -> list[str]:
    normalized = {_required_string(value, "observation reference") for value in values or ()}
    return sorted(normalized)


def _assert_no_secret_shaped_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError("Evidence payload keys must be strings.")
            normalized_key = "".join(character for character in key.lower() if character.isalnum())
            if any(fragment in normalized_key for fragment in _SECRET_KEY_FRAGMENTS):
                raise ValueError("Evidence payload cannot contain secret-shaped keys.")
            _assert_no_secret_shaped_keys(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            _assert_no_secret_shaped_keys(nested_value)


def canonical_fact_key(season_revision: Any, subject_key: Any, fact_type: Any) -> str:
    """Build the stable semantic identity for one season-scoped fact."""

    return "gear-fact:" + _sha256(
        {
            "seasonRevision": _required_string(season_revision, "season_revision"),
            "subjectKey": _required_string(subject_key, "subject_key"),
            "factType": _required_string(fact_type, "fact_type"),
        }
    )


def fact_value_hash(subject_key: Any, fact_type: Any, value: Any, status: Any) -> str:
    """Hash the resolved value/status independently from fact identity."""

    normalized_status = _required_string(status, "status")
    if normalized_status not in CANONICAL_FACT_STATUSES:
        raise ValueError(f"Unsupported canonical fact status: {normalized_status}")
    return _sha256(
        {
            "subjectKey": _required_string(subject_key, "subject_key"),
            "factType": _required_string(fact_type, "fact_type"),
            "value": _canonical(value),
            "status": normalized_status,
        }
    )


def provenance_hash(
    observation_refs: Iterable[Any], compiler_rule_revision: Any
) -> str:
    """Hash only the selected observations and the compiler policy revision."""

    return _sha256(
        {
            "observationRefs": _normalized_refs(observation_refs),
            "compilerRuleRevision": _required_string(
                compiler_rule_revision, "compiler_rule_revision"
            ),
        }
    )


def build_evidence_artifact(
    *,
    source_type: Any,
    source_identity: Any,
    source_revision: Any,
    season_revision: Any,
    captured_at: Any,
    payload: Any,
) -> dict[str, Any]:
    """Create an immutable source artifact without reading external state."""

    canonical_payload = _canonical(payload)
    _assert_no_secret_shaped_keys(canonical_payload)
    payload_hash = _sha256(canonical_payload)
    normalized_source_type = _required_string(source_type, "source_type")
    normalized_source_identity = _required_string(source_identity, "source_identity")
    normalized_source_revision = _required_string(source_revision, "source_revision")
    normalized_season_revision = _required_string(season_revision, "season_revision")
    artifact_id = "gear-artifact:" + _sha256(
        {
            "sourceType": normalized_source_type,
            "sourceIdentity": normalized_source_identity,
            "sourceRevision": normalized_source_revision,
            "seasonRevision": normalized_season_revision,
            "payloadHash": payload_hash,
        }
    )
    return _canonical(
        {
            "schemaRevision": EVIDENCE_ARTIFACT_SCHEMA_REVISION,
            "artifactId": artifact_id,
            "sourceType": normalized_source_type,
            "sourceIdentity": normalized_source_identity,
            "sourceRevision": normalized_source_revision,
            "seasonRevision": normalized_season_revision,
            "capturedAt": _required_string(captured_at, "captured_at"),
            "payloadHash": payload_hash,
            "payload": canonical_payload,
        }
    )


def build_evidence_observation(
    *,
    artifact_id: Any,
    subject_key: Any,
    fact_type: Any,
    observed_value: Any,
    parser_revision: Any,
    source_scope: Any,
    status: Any,
) -> dict[str, Any]:
    """Create one deterministic, normalized parser observation."""

    normalized_status = _required_string(status, "status")
    if normalized_status != "accepted":
        raise ValueError("Evidence observation status must be accepted.")
    canonical_observed_value = _canonical(observed_value)
    identity = {
        "artifactId": _required_string(artifact_id, "artifact_id"),
        "subjectKey": _required_string(subject_key, "subject_key"),
        "factType": _required_string(fact_type, "fact_type"),
        "observedValue": canonical_observed_value,
        "parserRevision": _required_string(parser_revision, "parser_revision"),
        "sourceScope": _required_string(source_scope, "source_scope"),
        "status": normalized_status,
    }
    return _canonical(
        {
            "schemaRevision": EVIDENCE_OBSERVATION_SCHEMA_REVISION,
            "observationId": "gear-observation:" + _sha256(identity),
            **identity,
        }
    )


def build_canonical_fact(
    *,
    season_revision: Any,
    subject_key: Any,
    fact_type: Any,
    value: Any,
    status: Any,
    observation_refs: Iterable[Any],
    compiler_rule_revision: Any,
    impact_scope: Any,
    problem_code: Any = "",
) -> dict[str, Any]:
    """Create one canonical fact while preserving the verified/unresolved boundary."""

    normalized_status = _required_string(status, "status")
    if normalized_status not in CANONICAL_FACT_STATUSES:
        raise ValueError(f"Unsupported canonical fact status: {normalized_status}")
    if normalized_status == "verified" and value is None:
        raise ValueError("Verified canonical facts require a value.")
    if normalized_status != "verified" and value is not None:
        raise ValueError("Unresolved canonical facts cannot carry a trusted value.")

    normalized_season_revision = _required_string(season_revision, "season_revision")
    normalized_subject_key = _required_string(subject_key, "subject_key")
    normalized_fact_type = _required_string(fact_type, "fact_type")
    normalized_observation_refs = _normalized_refs(observation_refs)
    normalized_compiler_rule_revision = _required_string(
        compiler_rule_revision, "compiler_rule_revision"
    )
    canonical_value = _canonical(value)
    return _canonical(
        {
            "schemaRevision": CANONICAL_FACT_SCHEMA_REVISION,
            "factKey": canonical_fact_key(
                normalized_season_revision, normalized_subject_key, normalized_fact_type
            ),
            "subjectKey": normalized_subject_key,
            "seasonRevision": normalized_season_revision,
            "factType": normalized_fact_type,
            "value": canonical_value,
            "status": normalized_status,
            "observationRefs": normalized_observation_refs,
            "compilerRuleRevision": normalized_compiler_rule_revision,
            "factValueHash": fact_value_hash(
                normalized_subject_key,
                normalized_fact_type,
                canonical_value,
                normalized_status,
            ),
            "provenanceHash": provenance_hash(
                normalized_observation_refs, normalized_compiler_rule_revision
            ),
            "impactScope": _required_string(impact_scope, "impact_scope"),
            "problemCode": str(problem_code or "").strip(),
        }
    )


__all__ = (
    "EVIDENCE_ARTIFACT_SCHEMA_REVISION",
    "EVIDENCE_OBSERVATION_SCHEMA_REVISION",
    "CANONICAL_FACT_SCHEMA_REVISION",
    "CANONICAL_FACT_STATUSES",
    "build_evidence_artifact",
    "build_evidence_observation",
    "build_canonical_fact",
    "canonical_fact_key",
    "fact_value_hash",
    "provenance_hash",
)
