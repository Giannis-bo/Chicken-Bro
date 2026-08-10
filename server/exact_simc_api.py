#!/usr/bin/env python3
"""Server-owned Exact SimC confirm/submit boundary.

The page may submit selection-intent-v1, but it never creates Exact facts.
This owner accepts only materialized server outcomes and exposes bounded typed
envelopes for the Task 5A path.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping
import uuid

try:
    from .exact_template_authority_binding import (
        exact_template_authority_binding_payload,
    )
    from .gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from .gear_exact_import_job_store import (
        DEPENDENCY_VECTOR_KEYS,
        REQUEST_V3_SCHEMA_REVISION,
        build_exact_import_job_request,
    )
    from .gear_contracts import parse_selection_intent
    from .gear_loadout_effect_authority import resolve_loadout_effect_authority
    from .gear_resolved_loadout import build_resolved_loadout_v3
    from .gear_resolver import resolve_v2
    from .exact_runtime_authority_release import (
        resolve_release_effect_records,
        runtime_authority_release_payload,
        runtime_resolver_context_payload,
    )
    from .simulation_snapshot import (
        build_simulation_snapshot_v3,
        talent_profile_key_for_lines,
    )
except ImportError:  # pragma: no cover - direct server runtime compatibility
    from exact_template_authority_binding import exact_template_authority_binding_payload
    from gear_canonical_kernel import CanonicalValueError, canonical_identity_token
    from gear_exact_import_job_store import (
        DEPENDENCY_VECTOR_KEYS,
        REQUEST_V3_SCHEMA_REVISION,
        build_exact_import_job_request,
    )
    from gear_contracts import parse_selection_intent
    from gear_loadout_effect_authority import resolve_loadout_effect_authority
    from gear_resolved_loadout import build_resolved_loadout_v3
    from gear_resolver import resolve_v2
    from exact_runtime_authority_release import (
        resolve_release_effect_records,
        runtime_authority_release_payload,
        runtime_resolver_context_payload,
    )
    from simulation_snapshot import build_simulation_snapshot_v3, talent_profile_key_for_lines


EXACT_SIMC_ENVELOPE_REVISION = "exact-simc-envelope-v1"
EXACT_SIMC_SOURCE_REF_REVISION = "exact-simc-source-ref-v1"
EXACT_SIMC_PROFILE_REF_REVISION = "exact-simc-profile-ref-v1"
EXACT_SIMC_EXECUTION_INTENT_REVISION = "exact-simc-execution-intent-v1"
_OWNER_KEY_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_EXACT_IMPORT_REQUEST_KEY = re.compile(r"exact-import-request:sha256:[0-9a-f]{64}")
_EXECUTION_INTENT_KEY = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
_JOB_OWNER_NAMESPACE = "exact-simc-job-owner-v1:"
_SOURCE_AUTHORITY_REVISION_KEYS = frozenset({
    "gear_exact_registry_revision",
    "gear_rule_revision",
    "resolver_revision",
    "simc_runtime_revision",
})
_JOB_READ_STATUSES = frozenset({
    "pending", "running", "resolved", "blocked", "unsupported", "failed",
})
_JOB_READ_ROW_KEYS = frozenset({
    "jobId", "requestKey", "status", "resultJson", "problemJson",
    "queuedAt", "startedAt", "finishedAt", "cooldownUntil",
})
_PRIVATE_RESULT_KEYS = frozenset({
    "rawProfile", "rawString", "playerName", "characterName", "realm",
    "server", "userId", "user_id", "ownerKeyHash", "owner_key_hash",
})
_MAX_PUBLIC_RESULT_BYTES = 131_072


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


def _profile_ref(request: Any) -> dict[str, Any] | None:
    if not isinstance(request, Mapping) or "profileContext" in request:
        return None
    profile = request.get("profileRef")
    if not isinstance(profile, Mapping) or set(profile) != {
        "contractRevision", "kind", "sourceId", "remote",
    }:
        return None
    source_id = profile.get("sourceId")
    if (
        profile.get("contractRevision") != EXACT_SIMC_PROFILE_REF_REVISION
        or profile.get("kind") != "talent-template"
        or profile.get("remote") is not True
        or not isinstance(source_id, str)
        or not source_id
        or source_id != source_id.strip()
        or len(source_id.encode("utf-8")) > 240
    ):
        return None
    return {
        "contractRevision": EXACT_SIMC_PROFILE_REF_REVISION,
        "kind": "talent-template",
        "sourceId": source_id,
        "remote": True,
    }


def _execution_intent(request: Any) -> dict[str, Any] | None:
    if not isinstance(request, Mapping):
        return None
    execution = request.get("executionIntent")
    if not isinstance(execution, Mapping) or set(execution) != {
        "contractRevision", "raceKey", "scenarioKey",
    }:
        return None
    race_key, scenario_key = execution.get("raceKey"), execution.get("scenarioKey")
    if (
        execution.get("contractRevision") != EXACT_SIMC_EXECUTION_INTENT_REVISION
        or not isinstance(race_key, str)
        or not isinstance(scenario_key, str)
        or _EXECUTION_INTENT_KEY.fullmatch(race_key) is None
        or _EXECUTION_INTENT_KEY.fullmatch(scenario_key) is None
    ):
        return None
    return {
        "contractRevision": EXACT_SIMC_EXECUTION_INTENT_REVISION,
        "raceKey": race_key,
        "scenarioKey": scenario_key,
    }


def exact_simc_request_problem(request: Any) -> str | None:
    """Classify a public Exact request without promoting any client facts.

    Routes use this before constructing the private request-scoped owner.  The
    complete selection is still reloaded and compared by
    ``AuthenticatedExactSourceMaterializer``; this boundary only prevents raw
    profile data, local references, and unbounded fields from reaching it.
    """

    if not isinstance(request, Mapping):
        return "EXACT_SOURCE_AUTHORITY_REQUIRED"
    if _source_ref(request) is None:
        return "EXACT_SOURCE_AUTHORITY_REQUIRED"
    expected = {
        "selectionIntent", "sourceRef", "profileRef", "executionIntent",
    }
    if set(request) != expected:
        if "profileContext" in request or not {
            "profileRef", "executionIntent",
        }.issubset(request):
            return "EXACT_PROFILE_AUTHORITY_REQUIRED"
        return "EXACT_SOURCE_AUTHORITY_REQUIRED"
    selection, issues = parse_selection_intent(request.get("selectionIntent"))
    if selection is None or issues:
        return "EXACT_SOURCE_AUTHORITY_REQUIRED"
    if _profile_ref(request) is None or _execution_intent(request) is None:
        return "EXACT_PROFILE_AUTHORITY_REQUIRED"
    return None


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


def _contains_private_result_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key in _PRIVATE_RESULT_KEYS or _contains_private_result_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_private_result_key(nested) for nested in value)
    return False


def _public_result(value: Any) -> dict[str, Any] | None:
    """Accept only a bounded JSON object without private request identity."""

    if type(value) is not dict or _contains_private_result_key(value):
        return None
    try:
        canonical_bytes = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        canonical = json.loads(canonical_bytes.decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if len(canonical_bytes) > _MAX_PUBLIC_RESULT_BYTES or canonical != value:
        return None
    return canonical


def _public_problem(value: Any) -> list[dict[str, str]] | None:
    if value is None:
        return []
    if not isinstance(value, Mapping) or _contains_private_result_key(value):
        return None
    normalized = _problems([value])
    return normalized or None


def _public_job_read(row: Any, requested_job_id: Any) -> tuple[str, dict[str, Any], list[dict[str, str]]] | None:
    if not isinstance(row, Mapping) or set(row) != _JOB_READ_ROW_KEYS:
        return None
    job_id = row.get("jobId")
    request_key = row.get("requestKey")
    status = row.get("status")
    if (
        isinstance(job_id, bool)
        or not isinstance(job_id, int)
        or job_id <= 0
        or job_id != requested_job_id
        or not isinstance(request_key, str)
        or _EXACT_IMPORT_REQUEST_KEY.fullmatch(request_key) is None
        or status not in _JOB_READ_STATUSES
        or row.get("cooldownUntil") is not None
        and (not isinstance(row["cooldownUntil"], str) or len(row["cooldownUntil"].encode("utf-8")) > 256)
    ):
        return None
    result = row.get("resultJson")
    problems = _public_problem(row.get("problemJson"))
    if problems is None:
        return None
    if status == "resolved":
        result = _public_result(result)
        if result is None or problems:
            return None
    elif status in {"pending", "running"}:
        if result is not None or problems:
            return None
        result = None
    else:
        if result is not None or not problems:
            return None
        result = None
    return status, {
        "jobId": job_id,
        "requestKey": request_key,
        "jobStatus": status,
        "result": result,
        "cooldownUntil": row.get("cooldownUntil"),
    }, problems


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
        client_selection, selection_issues = parse_selection_intent(
            request.get("selectionIntent") if isinstance(request, Mapping) else None,
        )
        if client_selection is None or selection_issues:
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
        if getattr(replay.get("source"), "selection_intent", None) != client_selection:
            return {"status": "blocked", "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}]}
        return dict(replay)


def _profile_authority_required() -> dict[str, Any]:
    return {
        "status": "blocked",
        "problems": [{"code": "EXACT_PROFILE_AUTHORITY_REQUIRED"}],
    }


class ServerExactProfileCompiler:
    """Compose one Exact profile from server talent and options authorities only."""

    _EXECUTION_OPTIONS_KEYS = frozenset({
        "characterContext", "scenarioOptions", "preparationLines",
    })

    def __init__(
        self,
        *,
        talent_encoder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        execution_options_provider: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    ) -> None:
        self._talent_encoder = talent_encoder
        self._execution_options_provider = execution_options_provider

    def __call__(
        self,
        talent_source: Mapping[str, Any],
        execution_intent: Mapping[str, Any],
        gear_source: Any,
    ) -> dict[str, Any]:
        selection_intent = getattr(gear_source, "selection_intent", None)
        eligibility = (
            selection_intent.get("eligibilityContext")
            if isinstance(selection_intent, Mapping)
            else None
        )
        if not isinstance(eligibility, Mapping):
            raise ValueError("gear eligibility is required for Exact profile compilation")
        encoded = self._talent_encoder(dict(talent_source))
        if not isinstance(encoded, Mapping) or encoded.get("status") != "encoded":
            raise ValueError("server talent authority did not encode the saved template")
        if (
            encoded.get("classKey") != eligibility.get("classKey")
            or encoded.get("specKey") != eligibility.get("specKey")
            or encoded.get("classKey") != talent_source.get("classKey")
            or encoded.get("specKey") != talent_source.get("specKey")
            or (
                talent_source.get("heroKey")
                and encoded.get("heroKey") != talent_source.get("heroKey")
            )
        ):
            raise ValueError("server talent encoding does not match the saved source")
        talent_lines = encoded.get("lines")
        talent_profile_key = talent_profile_key_for_lines(talent_lines)
        if not talent_profile_key:
            raise ValueError("server talent encoding has no canonical lines")
        execution = self._execution_options_provider(execution_intent, gear_source)
        if (
            not isinstance(execution, Mapping)
            or set(execution) != self._EXECUTION_OPTIONS_KEYS
            or _contains_private_result_key(execution)
        ):
            raise ValueError("server execution options are unavailable")
        return {
            "talentProfileKey": talent_profile_key,
            "talentLines": list(talent_lines),
            "characterContext": execution["characterContext"],
            "scenarioOptions": execution["scenarioOptions"],
            "preparationLines": execution["preparationLines"],
        }


class AuthenticatedExactProfileMaterializer:
    """Reload one remote saved talent source without exposing raw profile text.

    The returned mapping is only the compiler's bounded Exact profile input.
    The saved template's raw text stays inside this request-scoped call and is
    never returned to the API envelope, job or snapshot owner.
    """

    _SOURCE_KEYS = frozenset({
        "ownerId", "templateId", "templateType", "remote", "configHash",
        "rawString", "simcLines", "classKey", "specKey", "heroKey",
    })
    _PROFILE_KEYS = frozenset({
        "talentProfileKey", "talentLines", "characterContext",
        "scenarioOptions", "preparationLines",
    })

    def __init__(
        self,
        *,
        authenticated_user_id: Any,
        personal_store: Any,
        profile_compiler: Callable[[Mapping[str, Any], Mapping[str, Any], Any], Mapping[str, Any]],
    ) -> None:
        if type(authenticated_user_id) is not str:
            raise ValueError("authenticated user id must be a canonical UUID")
        try:
            parsed = uuid.UUID(authenticated_user_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("authenticated user id must be a canonical UUID") from error
        self._authenticated_user_id = str(parsed)
        if self._authenticated_user_id != authenticated_user_id:
            raise ValueError("authenticated user id must be a canonical UUID")
        self._personal_store = personal_store
        self._profile_compiler = profile_compiler

    @staticmethod
    def _canonical_uuid(value: Any) -> str | None:
        if type(value) is not str:
            return None
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError):
            return None
        normalized = str(parsed)
        return normalized if normalized == value else None

    def __call__(self, request: Mapping[str, Any], gear_source: Any) -> dict[str, Any]:
        profile_ref = _profile_ref(request)
        execution_intent = _execution_intent(request)
        template_id = self._canonical_uuid(
            profile_ref["sourceId"] if profile_ref is not None else None,
        )
        if profile_ref is None or execution_intent is None or template_id is None:
            return _profile_authority_required()
        try:
            talent_source = self._personal_store.load_remote_talent_template_for_exact(
                self._authenticated_user_id,
                template_id,
            )
        except Exception:
            return _profile_authority_required()
        if (
            not isinstance(talent_source, Mapping)
            or set(talent_source) != self._SOURCE_KEYS
            or talent_source.get("ownerId") != self._authenticated_user_id
            or talent_source.get("templateId") != template_id
            or talent_source.get("templateType") != "talent"
            or talent_source.get("remote") is not True
        ):
            return _profile_authority_required()
        selection_intent = getattr(gear_source, "selection_intent", None)
        eligibility = (
            selection_intent.get("eligibilityContext")
            if isinstance(selection_intent, Mapping)
            else None
        )
        if (
            not isinstance(eligibility, Mapping)
            or talent_source.get("classKey") != eligibility.get("classKey")
            or talent_source.get("specKey") != eligibility.get("specKey")
        ):
            return _profile_authority_required()
        try:
            profile = self._profile_compiler(
                dict(talent_source),
                execution_intent,
                gear_source,
            )
        except Exception:
            return _profile_authority_required()
        if (
            not isinstance(profile, Mapping)
            or set(profile) != self._PROFILE_KEYS
            or _contains_private_result_key(profile)
        ):
            return _profile_authority_required()
        return dict(profile)


def _blocked_materialization(code: str = "EXACT_AUTHORITY_UNAVAILABLE") -> dict[str, Any]:
    return {"status": "blocked", "problems": [{"code": code}]}


def _not_ready_materialization(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and value.get("status") in {"blocked", "unsupported"}:
        return {
            "status": value["status"],
            "problems": _problems(value.get("problems")) or [
                {"code": "EXACT_AUTHORITY_UNAVAILABLE"},
            ],
        }
    return _blocked_materialization()


class ExactSimcMaterializer:
    """Materialize one source-bound V3 request from persisted authorities.

    This owner reads exactly one owner/binding-scoped Runtime Authority Release
    after 0033 source replay.  It has no Catalog/registry/latest fallback: the
    only item facts it may serialize come from the exact bundles recorded by
    that binding and the immutable V3 release closure.
    """

    def __init__(
        self,
        *,
        source_materializer: Callable[[Mapping[str, Any], str], Mapping[str, Any]],
        authenticated_user_id: str,
        runtime_authority_store: Any,
        profile_materializer: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
        snapshot_store: Any,
    ) -> None:
        try:
            parsed_user_id = uuid.UUID(authenticated_user_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("authenticated user id must be a canonical UUID") from error
        if str(parsed_user_id) != authenticated_user_id:
            raise ValueError("authenticated user id must be a canonical UUID")
        self._source_materializer = source_materializer
        self._authenticated_user_id = authenticated_user_id
        self._runtime_authority_store = runtime_authority_store
        self._profile_materializer = profile_materializer
        self._snapshot_store = snapshot_store

    @staticmethod
    def _source_closure(replay: Any) -> tuple[Any, list[dict[str, str]], dict[str, Any]] | None:
        if not isinstance(replay, Mapping) or replay.get("status") != "verified":
            return None
        source = replay.get("source")
        if not isinstance(getattr(source, "selection_intent", None), Mapping):
            return None
        try:
            payload = exact_template_authority_binding_payload(replay.get("binding"))
        except (TypeError, ValueError):
            return None
        pairs = payload.get("exactAuthorityBySlot")
        rows = replay.get("slotBundles")
        if not isinstance(pairs, list) or not isinstance(rows, tuple):
            return None
        bundles: dict[str, Any] = {}
        seen: list[dict[str, str]] = []
        for row in rows:
            relation = dict(row) if isinstance(row, Mapping) else {}
            slot = relation.get("slot")
            key = relation.get("exactAuthorityEnvelopeKey")
            bundle = relation.get("bundle")
            if not isinstance(slot, str) or not isinstance(key, str) or key in bundles:
                return None
            if getattr(getattr(bundle, "envelope", None), "content_key", None) != key:
                return None
            bundles[key] = bundle
            seen.append({"slot": slot, "exactAuthorityEnvelopeKey": key})
        if seen != pairs:
            return None
        return source, pairs, bundles

    def _runtime_closure(
        self,
        replay: Mapping[str, Any],
    ) -> tuple[Any, Any, dict[str, Any], dict[str, Any]] | None:
        """Load one exact owner/binding release and reject cross-closure drift."""
        binding = replay.get("binding")
        binding_key = getattr(binding, "content_key", None)
        if not isinstance(binding_key, str):
            return None
        try:
            membership = self._runtime_authority_store.read_unique_for_binding(
                self._authenticated_user_id,
                binding_key,
            )
            resolver_context = membership.resolver_context
            runtime_authority_release = membership.release
            context_payload = runtime_resolver_context_payload(resolver_context)
            release_payload = runtime_authority_release_payload(
                runtime_authority_release
            )
            binding_authority = exact_template_authority_binding_payload(
                binding,
            )["authority"]
        except Exception:
            return None
        dependency_vector = release_payload.get("dependencyVector")
        authority_context = context_payload.get("resolverAuthorityContext")
        if (
            not isinstance(dependency_vector, Mapping)
            or set(dependency_vector) != DEPENDENCY_VECTOR_KEYS
            or not isinstance(authority_context, Mapping)
            or release_payload.get("resolverContextKey")
            != getattr(resolver_context, "content_key", None)
            or binding_authority.get("gearRuleRevision")
            != dependency_vector.get("gearRuleRevision")
            or binding_authority.get("resolverRevision")
            != dependency_vector.get("resolverRevision")
            or binding_authority.get("simcRuntimeRevision")
            != dependency_vector.get("simcRuntimeRevision")
            or context_payload.get("seasonRevision")
            != dependency_vector.get("seasonRevision")
            or context_payload.get("gearRuleRevision")
            != dependency_vector.get("gearRuleRevision")
            or context_payload.get("resolverRevision")
            != dependency_vector.get("resolverRevision")
            or context_payload.get("simcRuntimeRevision")
            != dependency_vector.get("simcRuntimeRevision")
        ):
            return None
        return (
            resolver_context,
            runtime_authority_release,
            dict(authority_context),
            dict(dependency_vector),
        )

    @staticmethod
    def _requires_loadout_effect_authority(value: Any) -> bool:
        if not isinstance(value, Mapping):
            return False
        codes = value.get("problemCodes")
        if isinstance(codes, list) and "LOADOUT_EFFECT_AUTHORITY_REQUIRED" in codes:
            return True
        return any(
            problem.get("code") == "LOADOUT_EFFECT_AUTHORITY_REQUIRED"
            for problem in _problems(value.get("problems"))
        )

    @staticmethod
    def _exact_intent(
        source: Any,
        pairs: list[dict[str, str]],
        bundles: Mapping[str, Any],
        dependency_vector: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        selection = source.selection_intent
        eligibility = selection.get("eligibilityContext")
        if not isinstance(eligibility, Mapping):
            return None
        slots: dict[str, Any] = {}
        expected_fields = {
            "itemId", "declaredItemLevel", "bonusIds", "context", "gemIds",
            "gemBonusIds", "gemItemLevels", "enchantId", "craftedStats",
            "embellishmentIds", "redirectedBaseStats",
        }
        for relation in pairs:
            slot, key = relation["slot"], relation["exactAuthorityEnvelopeKey"]
            exact = getattr(bundles.get(key), "exact_item", None)
            raw = getattr(exact, "canonical_bytes", None)
            try:
                value = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            if not isinstance(value, Mapping) or set(value) != expected_fields:
                return None
            slots[slot] = dict(value)
        return {
            "schemaRevision": "exact-loadout-intent-v2",
            "authoredAgainst": {
                "seasonRevision": dependency_vector.get("seasonRevision"),
                "gameBuild": dependency_vector.get("gameBuild"),
            },
            "eligibilityContext": dict(eligibility),
            "slots": slots,
        }

    @staticmethod
    def _profile(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, Mapping):
            return None
        keys = {
            "talentProfileKey", "talentLines", "characterContext",
            "scenarioOptions", "preparationLines",
        }
        if set(value) != keys:
            return None
        return {key: value[key] for key in keys}

    def __call__(self, request: Mapping[str, Any], job_owner_key_hash: str) -> dict[str, Any]:
        try:
            replay = self._source_materializer(request, job_owner_key_hash)
        except Exception:
            return _blocked_materialization("EXACT_SOURCE_AUTHORITY_REQUIRED")
        closure = self._source_closure(replay)
        if closure is None:
            return _not_ready_materialization(replay)
        source, pairs, bundles = closure
        runtime = self._runtime_closure(replay)
        if runtime is None:
            return _blocked_materialization()
        (
            resolver_context,
            runtime_authority_release,
            authority_context,
            dependency_vector,
        ) = runtime
        resolver_snapshot = resolve_v2(
            source.selection_intent,
            authority_context,
        )
        loadout_effect_authority = None
        if self._requires_loadout_effect_authority(resolver_snapshot):
            try:
                binding_key = replay["binding"].content_key
                entries = self._runtime_authority_store.read_occurrences(
                    self._authenticated_user_id,
                    binding_key,
                    runtime_authority_release,
                )
                loaded_records = self._runtime_authority_store.load_effect_records(
                    runtime_authority_release,
                    entries,
                )
                records_by_key = {
                    record.content_key: record for record in loaded_records
                }
                release_records = resolve_release_effect_records(
                    runtime_authority_release,
                    resolver_snapshot=resolver_snapshot,
                    index_entries=entries,
                    record_loader=records_by_key.__getitem__,
                )
                aggregate = resolve_loadout_effect_authority(
                    resolver_snapshot,
                    records=release_records,
                )
            except Exception:
                return _not_ready_materialization(resolver_snapshot)
            if aggregate.status == "unsupported":
                return {
                    "status": "unsupported",
                    "problems": _problems([
                        {"code": issue.code, "path": issue.path}
                        for issue in aggregate.issues
                    ]) or [{"code": "LOADOUT_EFFECT_UNSUPPORTED"}],
                }
            if aggregate.status != "verified" or aggregate.document is None:
                return _blocked_materialization()
            loadout_effect_authority = aggregate.document
            resolver_snapshot = resolve_v2(
                source.selection_intent,
                authority_context,
                loadout_effect_authority=loadout_effect_authority,
            )
        if (
            not isinstance(resolver_snapshot, Mapping)
            or resolver_snapshot.get("status") != "verified"
        ):
            return _not_ready_materialization(resolver_snapshot)
        resolved_loadout = build_resolved_loadout_v3(
            resolver_snapshot=resolver_snapshot,
            exact_authority_by_slot=pairs,
            authority_bundles=bundles,
            resolver_context=resolver_context,
            runtime_authority_release=runtime_authority_release,
            loadout_effect_authority=loadout_effect_authority,
        )
        if not isinstance(resolved_loadout, Mapping) or resolved_loadout.get("status") != "ready":
            return _not_ready_materialization(resolved_loadout)
        try:
            profile = self._profile(self._profile_materializer(request, source))
        except Exception:
            profile = None
        if profile is None:
            return _blocked_materialization()
        snapshot = build_simulation_snapshot_v3(
            resolved_loadout=resolved_loadout,
            talent_profile_key=profile["talentProfileKey"],
            talent_lines=profile["talentLines"],
            character_context=profile["characterContext"],
            scenario_options=profile["scenarioOptions"],
            preparation_lines=profile["preparationLines"],
            compiler_revision=dependency_vector.get("compilerRevision"),
            simc_runtime_revision=dependency_vector.get("simcRuntimeRevision"),
            resolver_snapshot=resolver_snapshot,
            authority_bundles=bundles,
            resolver_context=resolver_context,
            runtime_authority_release=runtime_authority_release,
            loadout_effect_authority=loadout_effect_authority,
        )
        if not isinstance(snapshot, Mapping) or snapshot.get("status") != "ready":
            return _not_ready_materialization(snapshot)
        exact_intent = self._exact_intent(
            source,
            pairs,
            bundles,
            dependency_vector,
        )
        if exact_intent is None:
            return _blocked_materialization()
        try:
            sealed_loadout = self._snapshot_store.seal_loadout(
                resolved_loadout,
                resolver_snapshot=resolver_snapshot,
                authority_bundles=bundles,
                resolver_context=resolver_context,
                runtime_authority_release=runtime_authority_release,
                loadout_effect_authority=loadout_effect_authority,
            )
            sealed_snapshot = self._snapshot_store.seal_snapshot(
                snapshot,
                resolved_loadout=sealed_loadout,
                resolver_snapshot=resolver_snapshot,
                authority_bundles=bundles,
                compiler_revision=dependency_vector.get("compilerRevision"),
                resolver_context=resolver_context,
                runtime_authority_release=runtime_authority_release,
                loadout_effect_authority=loadout_effect_authority,
            )
        except Exception:
            return _blocked_materialization()
        if (
            not isinstance(sealed_loadout, Mapping)
            or not isinstance(sealed_snapshot, Mapping)
            or sealed_snapshot.get("status") != "ready"
            or sealed_loadout.get("resolvedLoadoutKey")
                != resolved_loadout.get("resolvedLoadoutKey")
            or sealed_snapshot.get("simulationSnapshotKey")
                != snapshot.get("simulationSnapshotKey")
            or sealed_snapshot.get("resolvedLoadoutKey")
                != sealed_loadout.get("resolvedLoadoutKey")
            or sealed_loadout.get("runtimeAuthorityReleaseKey")
                != runtime_authority_release.content_key
            or sealed_loadout.get("resolverContextKey")
                != resolver_context.content_key
            or sealed_snapshot.get("runtimeAuthorityReleaseKey")
                != runtime_authority_release.content_key
            or sealed_snapshot.get("resolverContextKey")
                != resolver_context.content_key
            or sealed_snapshot.get("dependencyVector") != dependency_vector
        ):
            return _blocked_materialization()
        try:
            job_request = build_exact_import_job_request(
                exact_intent,
                dict(dependency_vector),
                snapshot_reference={
                    "resolvedLoadoutKey": sealed_loadout["resolvedLoadoutKey"],
                    "simulationSnapshotKey": sealed_snapshot["simulationSnapshotKey"],
                    "snapshotRowHash": sealed_snapshot.get("rowHash"),
                    "runtimeAuthorityReleaseKey": runtime_authority_release.content_key,
                    "resolverContextKey": resolver_context.content_key,
                },
            )
        except Exception:
            return _blocked_materialization()
        return {
            "status": "ready",
            "confirmation": {
                "requestKey": job_request.request_key,
                "resolvedLoadoutKey": sealed_loadout["resolvedLoadoutKey"],
                "simulationSnapshotKey": sealed_snapshot["simulationSnapshotKey"],
                "dependencyVector": dict(dependency_vector),
            },
            "jobRequest": job_request,
        }


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
        request_problem = exact_simc_request_problem(request)
        if request_problem is not None or owner is None:
            if request_problem == "EXACT_PROFILE_AUTHORITY_REQUIRED":
                return {
                    "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                    "operation": "confirm",
                    "status": "blocked",
                    "data": {},
                    "problems": [{"code": request_problem}],
                }
            return _source_authority_required("confirm")
        try:
            materialized = self._materialize(request, owner)
        except Exception:
            materialized = _blocked_materialization()
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
        request_problem = exact_simc_request_problem(request)
        if request_problem is not None or owner is None:
            if request_problem == "EXACT_PROFILE_AUTHORITY_REQUIRED":
                return {
                    "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                    "operation": "submit",
                    "status": "blocked",
                    "data": {},
                    "problems": [{"code": request_problem}],
                }
            return _source_authority_required("submit")
        try:
            materialized = self._materialize(request, owner)
        except Exception:
            materialized = _blocked_materialization()
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
        snapshot_reference = getattr(job_request, "snapshot_reference", None)
        if (
            getattr(job_request, "request_key", None) != authoritative["requestKey"]
            or type(job_payload) is not dict
            or job_payload.get("schemaRevision") != REQUEST_V3_SCHEMA_REVISION
            or job_payload.get("dependencyVector")
            != authoritative["dependencyVector"]
            or snapshot_reference is None
            or getattr(snapshot_reference, "resolved_loadout_key", None)
            != authoritative["resolvedLoadoutKey"]
            or getattr(snapshot_reference, "simulation_snapshot_key", None)
            != authoritative["simulationSnapshotKey"]
            or getattr(snapshot_reference, "runtime_authority_release_key", None)
            != job_payload.get("runtimeAuthorityReleaseKey")
            or getattr(snapshot_reference, "resolver_context_key", None)
            != job_payload.get("resolverContextKey")
            or not isinstance(
                getattr(snapshot_reference, "snapshot_row_hash", None),
                str,
            )
        ):
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "submit",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
            }
        try:
            enqueued = self._job_store.enqueue(owner, job_request)
        except Exception:
            enqueued = None
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

    def read(
        self,
        job_id: Any,
        *,
        owner_key_hash: str,
    ) -> dict[str, Any]:
        """Expose one owner-scoped, bounded Exact job state.

        The store already enforces owner scope.  This additional projection
        refuses malformed rows and strips timings/internal fields so a route
        cannot accidentally publish a persistence row as its API contract.
        """

        owner = _owner_key_hash(owner_key_hash)
        if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0 or owner is None:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "read",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_JOB_NOT_FOUND"}],
            }
        try:
            row = self._job_store.read(owner, job_id)
        except Exception:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "read",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_JOB_READ_UNAVAILABLE"}],
            }
        if row is None:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "read",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_JOB_NOT_FOUND"}],
            }
        public = _public_job_read(row, job_id)
        if public is None:
            return {
                "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
                "operation": "read",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_JOB_READ_INVALID"}],
            }
        status, data, problems = public
        return {
            "contractRevision": EXACT_SIMC_ENVELOPE_REVISION,
            "operation": "read",
            "status": status,
            "data": data,
            "problems": problems,
        }


__all__ = (
    "EXACT_SIMC_ENVELOPE_REVISION",
    "EXACT_SIMC_EXECUTION_INTENT_REVISION",
    "EXACT_SIMC_PROFILE_REF_REVISION",
    "EXACT_SIMC_SOURCE_REF_REVISION",
    "AuthenticatedExactSourceMaterializer",
    "AuthenticatedExactProfileMaterializer",
    "ExactSimcApi",
    "ExactSimcMaterializer",
    "ServerExactProfileCompiler",
    "exact_simc_request_problem",
    "exact_simc_job_owner_key_hash_for_user_id",
)
