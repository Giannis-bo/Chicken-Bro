#!/usr/bin/env python3
"""Server-owned Exact SimC confirm/submit boundary.

The page may submit selection-intent-v1, but it never creates Exact facts.
This owner accepts only materialized server outcomes and exposes bounded typed
envelopes for the Task 5A path.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Mapping
import uuid

try:
    from .gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from .gear_exact_import_job_store import DEPENDENCY_VECTOR_KEYS
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from gear_exact_import_job_store import DEPENDENCY_VECTOR_KEYS


EXACT_SIMC_ENVELOPE_REVISION = "exact-simc-envelope-v1"
EXACT_SIMC_SOURCE_REF_REVISION = "exact-simc-source-ref-v1"
_OWNER_KEY_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_JOB_OWNER_NAMESPACE = "exact-simc-job-owner-v1:"
_SOURCE_AUTHORITY_REVISION_KEYS = frozenset({
    "gear_exact_registry_revision",
    "gear_rule_revision",
    "resolver_revision",
    "simc_runtime_revision",
})


def exact_simc_job_owner_key_hash_for_user_id(user_id: Any) -> str:
    """Derive the only 0032 owner identity from an authenticated UUID.

    Callers keep ``user_id`` only in request memory for owner-scoped source
    reload.  The job store, API envelope, logs and result path receive this
    domain-separated hash instead.
    """

    if type(user_id) is not str:
        raise ValueError("user id must be a canonical UUID")
    try:
        parsed = uuid.UUID(user_id)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("user id must be a canonical UUID") from error
    normalized = str(parsed)
    if normalized != user_id:
        raise ValueError("user id must be a canonical UUID")
    return "sha256:" + hashlib.sha256(
        (_JOB_OWNER_NAMESPACE + normalized).encode("utf-8"),
    ).hexdigest()


def _problems(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for problem in value:
        if not isinstance(problem, Mapping):
            continue
        code = str(problem.get("code") or "").strip()
        path = str(problem.get("path") or "").strip()
        if code:
            normalized.append({"code": code, **({"path": path} if path else {})})
    return normalized


def _confirmation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    keys = {
        "requestKey",
        "resolvedLoadoutKey",
        "simulationSnapshotKey",
        "dependencyVector",
    }
    vector = value.get("dependencyVector")
    if set(value) != keys or type(vector) is not dict or set(vector) != DEPENDENCY_VECTOR_KEYS:
        return None
    normalized: dict[str, Any] = {"dependencyVector": {}}
    try:
        for key in sorted(DEPENDENCY_VECTOR_KEYS):
            normalized["dependencyVector"][key] = canonical_identity_token(
                vector[key],
                path=f"confirmation.dependencyVector.{key}",
                max_bytes=256,
            )
    except CanonicalValueError:
        return None
    for key in (
        "requestKey",
        "resolvedLoadoutKey",
        "simulationSnapshotKey",
    ):
        identity = value.get(key)
        if not isinstance(identity, str) or not identity:
            return None
        normalized[key] = identity
    return {
        "requestKey": normalized["requestKey"],
        "resolvedLoadoutKey": normalized["resolvedLoadoutKey"],
        "simulationSnapshotKey": normalized["simulationSnapshotKey"],
        "dependencyVector": normalized["dependencyVector"],
    }


def _source_ref(request: Any) -> dict[str, Any] | None:
    if not isinstance(request, Mapping):
        return None
    source = request.get("sourceRef")
    if not isinstance(source, Mapping) or set(source) != {
        "contractRevision", "kind", "sourceId", "remote",
    }:
        return None
    source_id = source.get("sourceId")
    if (
        source.get("contractRevision") != EXACT_SIMC_SOURCE_REF_REVISION
        or source.get("kind") != "template"
        or source.get("remote") is not True
        or not isinstance(source_id, str)
        or not source_id
        or source_id != source_id.strip()
        or len(source_id.encode("utf-8")) > 240
    ):
        return None
    return {
        "contractRevision": EXACT_SIMC_SOURCE_REF_REVISION,
        "kind": "template",
        "sourceId": source_id,
        "remote": True,
    }


def _owner_key_hash(value: Any) -> str | None:
    """Keep source lookup bound to an authenticated, opaque owner identity."""

    return value if isinstance(value, str) and _OWNER_KEY_HASH.fullmatch(value) else None


def _source_authority_required(operation: str) -> dict[str, Any]:
    return {
        "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
        "operation": operation,
        "status": "blocked",
        "data": {},
        "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}],
    }


class AuthenticatedExactSourceMaterializer:
    """Bind a route's private user scope to an opaque Exact job owner.

    This is only the first, source-replay part of the full Task 5A
    materializer.  It never discovers a template, derives v2 facts, or exposes
    the authenticated UUID.  A later materializer consumes its reverified
    internal closure to perform resolve/snapshot work.
    """

    def __init__(
        self,
        *,
        authenticated_user_id: Any,
        source_reader: Any,
        authority_revisions: Mapping[str, Any],
    ) -> None:
        self._authenticated_user_id = self._canonical_uuid(authenticated_user_id)
        self._expected_job_owner = exact_simc_job_owner_key_hash_for_user_id(
            self._authenticated_user_id,
        )
        if not isinstance(authority_revisions, Mapping) or set(authority_revisions) != _SOURCE_AUTHORITY_REVISION_KEYS:
            raise ValueError("source authority revisions are required")
        try:
            self._authority_revisions = {
                key: canonical_identity_token(
                    authority_revisions[key],
                    path=f"authorityRevisions.{key}",
                    max_bytes=256,
                )
                for key in sorted(_SOURCE_AUTHORITY_REVISION_KEYS)
            }
        except CanonicalValueError as error:
            raise ValueError("source authority revisions are invalid") from error
        self._source_reader = source_reader

    @staticmethod
    def _canonical_uuid(value: Any) -> str:
        if type(value) is not str:
            raise ValueError("authenticated user id must be a canonical UUID")
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("authenticated user id must be a canonical UUID") from error
        normalized = str(parsed)
        if normalized != value:
            raise ValueError("authenticated user id must be a canonical UUID")
        return normalized

    def __call__(self, request: Mapping[str, Any], job_owner_key_hash: str) -> dict[str, Any]:
        source_ref = _source_ref(request)
        if source_ref is None or job_owner_key_hash != self._expected_job_owner:
            return {"status": "blocked", "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}]}
        try:
            template_id = self._canonical_uuid(source_ref["sourceId"])
            replay = self._source_reader.read(
                self._authenticated_user_id,
                template_id,
                **self._authority_revisions,
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return {"status": "blocked", "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}]}
        if not isinstance(replay, Mapping):
            return {"status": "blocked", "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}]}
        return dict(replay)


class ExactSimcApi:
    """Keep intent materialization and task creation on distinct operations."""

    def __init__(
        self,
        *,
        materialize: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
        job_store: Any,
    ) -> None:
        self._materialize = materialize
        self._job_store = job_store

    def confirm(
        self,
        request: Mapping[str, Any],
        *,
        owner_key_hash: str,
    ) -> dict[str, Any]:
        """Materialize authority only; blocked outcomes never enqueue a job."""

        owner = _owner_key_hash(owner_key_hash)
        if _source_ref(request) is None or owner is None:
            return _source_authority_required("confirm")
        materialized = self._materialize(request, owner)
        if not isinstance(materialized, Mapping):
            materialized = {}
        status = str(materialized.get("status") or "").strip()
        if status in {"blocked", "unsupported"}:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "confirm",
                "status": status,
                "data": {},
                "problems": _problems(materialized.get("problems")),
            }
        if status == "ready":
            confirmation = _confirmation(materialized.get("confirmation"))
            if confirmation is not None:
                return {
                    "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                    "operation": "confirm",
                    "status": "ready",
                    "data": confirmation,
                    "problems": [],
                }
        return {
            "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_AUTHORITY_UNAVAILABLE"}],
        }

    def submit(
        self,
        request: Mapping[str, Any],
        *,
        confirmation: Mapping[str, Any],
        owner_key_hash: str,
    ) -> dict[str, Any]:
        """Re-materialize intent and enqueue only its unchanged confirmation."""

        supplied = _confirmation(confirmation)
        owner = _owner_key_hash(owner_key_hash)
        if _source_ref(request) is None or owner is None:
            return _source_authority_required("submit")
        materialized = self._materialize(request, owner)
        if not isinstance(materialized, Mapping):
            materialized = {}
        status = str(materialized.get("status") or "").strip()
        if status in {"blocked", "unsupported"}:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "submit",
                "status": status,
                "data": {},
                "problems": _problems(materialized.get("problems")),
            }
        authoritative = _confirmation(materialized.get("confirmation"))
        if (
            status != "ready"
            or supplied is None
            or authoritative is None
            or supplied != authoritative
        ):
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "submit",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
            }
        job_request = materialized.get("jobRequest")
        job_payload = getattr(job_request, "request_json", None)
        if (
            getattr(job_request, "request_key", None) != authoritative["requestKey"]
            or type(job_payload) is not dict
            or job_payload.get("dependencyVector")
            != authoritative["dependencyVector"]
        ):
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "submit",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
            }
        enqueued = self._job_store.enqueue(owner, job_request)
        if (
            not isinstance(enqueued, Mapping)
            or enqueued.get("requestKey") != authoritative["requestKey"]
            or not isinstance(enqueued.get("jobId"), int)
            or not isinstance(enqueued.get("status"), str)
        ):
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "submit",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_JOB_ENQUEUE_INVALID"}],
            }
        return {
            "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
            "operation": "submit",
            "status": "queued",
            "data": {
                **authoritative,
                "jobId": enqueued["jobId"],
                "jobStatus": enqueued["status"],
                "cooldownUntil": enqueued.get("cooldownUntil"),
            },
            "problems": [],
        }


__all__ = (
    "EXACT_SIMC_ENVELOPE_REVISION",
    "EXACT_SIMC_SOURCE_REF_REVISION",
    "AuthenticatedExactSourceMaterializer",
    "ExactSimcApi",
    "exact_simc_job_owner_key_hash_for_user_id",
)
