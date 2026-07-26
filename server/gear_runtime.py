#!/usr/bin/env python3
"""Runtime orchestration for canonical gear Resolve and profile requests."""

from __future__ import annotations

import copy
import time
from typing import Any, Callable

try:
    from . import gear_resolver
    from .gear_contracts import parse_selection_intent
    from .community_template_import import (
        COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        community_template_import_public_data,
        community_template_import_problem,
    )
    from .postgres_cache_store import CommunityTemplateImportError
    from .gear_result_envelope import (
        gear_problem,
        http_status_for_envelope,
        result_envelope,
    )
    from .websim_payload import (
        build_websim_profile_response_from_resolved_snapshot,
        gear_resolver_runtime_authority,
    )
except ImportError:
    import gear_resolver
    from gear_contracts import parse_selection_intent
    from community_template_import import (
        COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
        community_template_import_public_data,
        community_template_import_problem,
    )
    from postgres_cache_store import CommunityTemplateImportError
    from gear_result_envelope import (
        gear_problem,
        http_status_for_envelope,
        result_envelope,
    )
    from websim_payload import (
        build_websim_profile_response_from_resolved_snapshot,
        gear_resolver_runtime_authority,
    )


PROFILE_CONTEXT_KEYS = (
    "name",
    "race",
    "scenarioKey",
    "heroKey",
    "talents",
    "talentImport",
    "websimExportCode",
    "talentState",
)

COMMUNITY_TEMPLATE_IMPORT_ENVELOPE_REVISION = "community-template-import-envelope-v1"
_COMMUNITY_TEMPLATE_IMPORT_REQUIRED_KEYS = {"classKey", "specKey", "templateId"}
_COMMUNITY_TEMPLATE_IMPORT_ALLOWED_KEYS = _COMMUNITY_TEMPLATE_IMPORT_REQUIRED_KEYS | {
    "expectedManifestRevision"
}


def _release_context(authority_context: Any) -> dict[str, Any]:
    authority = authority_context if isinstance(authority_context, dict) else {}
    manifest = authority.get("manifest") if isinstance(authority.get("manifest"), dict) else {}
    vector = (
        authority.get("dependencyVector")
        if isinstance(authority.get("dependencyVector"), dict)
        else {}
    )
    fields = (
        "seasonRevision",
        "gearCatalogReleaseId",
        "gearCatalogRevision",
        "gearRuleRevision",
        "resolverContractRevision",
        "serializerRevision",
        "simcRuntimeRevision",
        "statPolicyRevision",
        "selectionSchemaRevision",
        "capabilityRevision",
    )
    output = {
        field: vector.get(field) or manifest.get(field) or ""
        for field in fields
    }
    output.update(
        {
            "manifestRevision": manifest.get("manifestRevision") or "",
            "pointerGeneration": manifest.get("pointerGeneration"),
            "communityTemplateRevision": (
                manifest.get("communityTemplateRevision")
                or manifest.get("communityTemplateReleaseId")
                or ""
            ),
            "talentCatalogRevision": manifest.get("talentCatalogRevision") or "",
        }
    )
    output["formalActiveManifest"] = manifest.get("formalActiveManifest") is True
    return {key: value for key, value in output.items() if value not in (None, "")}


def _invalid_intent_envelope(raw_intent: Any, request_id: str) -> tuple[int, dict[str, Any]]:
    snapshot = gear_resolver.resolve(raw_intent, {})
    envelope = result_envelope(
        "blocked",
        request_id,
        {},
        data=snapshot,
        problems=snapshot.get("problems") or [],
    )
    return http_status_for_envelope(envelope), envelope


def _error_envelope(
    kind: str,
    code: str,
    title: str,
    request_id: str,
    *,
    release_context: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    status = "unavailable" if kind in {"AUTHORITY_UNAVAILABLE", "SIMC_UNAVAILABLE", "INTERNAL_ERROR"} else "blocked"
    problem = gear_problem(kind, code, title, retryable=kind != "INVALID_INTENT")
    envelope = result_envelope(
        status,
        request_id,
        release_context or {},
        problems=[problem],
    )
    return http_status_for_envelope(envelope), envelope


_INTERNAL_RESOLUTION_PROOF_KEYS = frozenset(
    {
        "canonicalfactrefids",
        "canonicalfactrefs",
        "factkey",
        "factkeys",
        "factrefids",
        "factrefs",
        "observationrefs",
        "problemcode",
        "problemcodes",
        "sourcerefids",
    }
)


def _public_resolution_value(value: Any, *, key: str = "") -> Any:
    """Recursively remove proof-layer identifiers from public Resolve data."""

    normalized_key = str(key or "").replace("_", "").lower()
    if normalized_key == "evidenceledger":
        ledger = value if isinstance(value, dict) else {}
        contract_revision = ledger.get("contractRevision")
        return (
            {"contractRevision": contract_revision}
            if isinstance(contract_revision, str) and contract_revision
            else {}
        )
    if normalized_key in _INTERNAL_RESOLUTION_PROOF_KEYS or any(
        token in normalized_key
        for token in ("artifact", "observation", "hash", "worker")
    ):
        return None
    if isinstance(value, dict):
        projected = {}
        for child_key, child_value in value.items():
            child = _public_resolution_value(child_value, key=child_key)
            normalized_child_key = str(child_key).replace("_", "").lower()
            if child is None and (
                normalized_child_key in _INTERNAL_RESOLUTION_PROOF_KEYS
                or any(
                    token in normalized_child_key
                    for token in ("artifact", "observation", "hash", "worker")
                )
            ):
                continue
            projected[child_key] = child
        return projected
    if isinstance(value, list):
        return [
            projected
            for entry in value
            if (projected := _public_resolution_value(entry)) is not None
        ]
    return copy.deepcopy(value)


def _snapshot_envelope(
    snapshot: dict[str, Any],
    authority_context: Any,
    request_id: str,
) -> tuple[int, dict[str, Any]]:
    problems = snapshot.get("problems") if isinstance(snapshot.get("problems"), list) else []
    kinds = {
        problem.get("kind")
        for problem in problems
        if isinstance(problem, dict)
    }
    if snapshot.get("status") == "verified" and not problems:
        status = "resolved"
    elif kinds.intersection({"AUTHORITY_UNAVAILABLE", "SIMC_UNAVAILABLE", "INTERNAL_ERROR"}):
        status = "unavailable"
    else:
        status = "blocked"
    public_snapshot = _public_resolution_value(snapshot)
    public_problems = _public_resolution_value(problems)
    envelope = result_envelope(
        status,
        request_id,
        _release_context(authority_context),
        data=public_snapshot,
        problems=public_problems,
    )
    return http_status_for_envelope(envelope), envelope


def _import_problem(code: str, title: str, *, retryable: bool = False) -> dict[str, Any]:
    return community_template_import_problem(code, title, retryable=retryable)


def _import_envelope(
    status: str,
    request_id: str,
    release_context: Any,
    *,
    data: Any = None,
    problems: Any = None,
) -> dict[str, Any]:
    return {
        "contractRevision": COMMUNITY_TEMPLATE_IMPORT_ENVELOPE_REVISION,
        "status": status,
        "requestId": str(request_id),
        "releaseContext": copy.deepcopy(release_context) if isinstance(release_context, dict) else {},
        "problems": copy.deepcopy(problems) if isinstance(problems, list) else [],
        "data": copy.deepcopy(data) if isinstance(data, dict) else {},
    }


def _import_http_status(status: str, problems: Any) -> int:
    codes = {
        str(problem.get("code") or "")
        for problem in problems if isinstance(problem, dict)
    } if isinstance(problems, list) else set()
    if status == "unavailable":
        return 503
    if "manifest_mismatch" in codes:
        return 409
    if "invalid_import_request" in codes:
        return 400
    return 200


def _import_timings(
    *,
    queue_ms: float = 0.0,
    release_read_ms: float = 0.0,
    reconcile_ms: float = 0.0,
    resolve_ms: float = 0.0,
    serialize_ms: float = 0.0,
    cache: str = "miss",
) -> dict[str, Any]:
    return {
        "queueMs": round(max(0.0, float(queue_ms)), 3),
        "releaseReadMs": round(max(0.0, float(release_read_ms)), 3),
        "reconcileMs": round(max(0.0, float(reconcile_ms)), 3),
        "resolveMs": round(max(0.0, float(resolve_ms)), 3),
        "serializeMs": round(max(0.0, float(serialize_ms)), 3),
        "cache": "hit" if cache == "hit" else "miss",
    }


def _valid_import_request(raw_request: Any) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    request = raw_request if isinstance(raw_request, dict) else {}
    if (
        not isinstance(raw_request, dict)
        or not _COMMUNITY_TEMPLATE_IMPORT_REQUIRED_KEYS.issubset(request)
        or set(request).difference(_COMMUNITY_TEMPLATE_IMPORT_ALLOWED_KEYS)
    ):
        return None, _import_problem(
            "invalid_import_request",
            "Community template import request has unsupported or missing fields.",
        )
    normalized = {}
    for key in _COMMUNITY_TEMPLATE_IMPORT_REQUIRED_KEYS | {"expectedManifestRevision"}:
        value = request.get(key, "")
        if key == "expectedManifestRevision" and key not in request:
            normalized[key] = ""
            continue
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 240:
            return None, _import_problem(
                "invalid_import_request",
                "Community template import identifiers must be bounded strings.",
            )
        normalized[key] = value.strip()
    return normalized, None


def import_community_template(
    raw_request: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
    clock: Callable[[], float] = time.perf_counter,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Resolve one sealed observed template atomically without slot-request fan-out."""

    request, invalid_problem = _valid_import_request(raw_request)
    if invalid_problem is not None:
        timings = _import_timings()
        envelope = _import_envelope("blocked", request_id, {}, problems=[invalid_problem])
        return _import_http_status("blocked", envelope["problems"]), envelope, timings
    if not str(simc_runtime_revision or "").strip():
        problem = _import_problem(
            "template_import_unavailable",
            "Current SimulationCraft runtime revision is unavailable.",
            retryable=True,
        )
        envelope = _import_envelope("unavailable", request_id, {}, problems=[problem])
        return 503, envelope, _import_timings()

    try:
        runtime_authority = gear_resolver_runtime_authority(
            request["classKey"],
            request["specKey"],
            simc_runtime_revision=simc_runtime_revision,
        )
    except ValueError:
        problem = _import_problem(
            "template_inapplicable",
            "Community template specialization is not currently playable.",
        )
        envelope = _import_envelope("blocked", request_id, {}, problems=[problem])
        return 200, envelope, _import_timings()

    try:
        context = store.get_community_template_import_context(
            class_key=request["classKey"],
            spec_key=request["specKey"],
            template_id=request["templateId"],
            runtime_authority=runtime_authority,
            expected_manifest_revision=request["expectedManifestRevision"],
        )
    except CommunityTemplateImportError as error:
        problem = _import_problem(error.code, error.title, retryable=error.unavailable)
        status = "unavailable" if error.unavailable else "blocked"
        envelope = _import_envelope(status, request_id, error.release_context, problems=[problem])
        return _import_http_status(status, envelope["problems"]), envelope, _import_timings()
    except Exception:
        problem = _import_problem(
            "template_import_unavailable",
            "Community template import is temporarily unavailable.",
            retryable=True,
        )
        envelope = _import_envelope("unavailable", request_id, {}, problems=[problem])
        return 503, envelope, _import_timings()

    release_read_ms = context.get("releaseReadMs", 0.0) if isinstance(context, dict) else 0.0
    reconcile_ms = context.get("reconcileMs", 0.0) if isinstance(context, dict) else 0.0
    cache_state = context.get("cache") if isinstance(context, dict) else {}
    if isinstance(cache_state, dict) and cache_state.get("hit") is True:
        cached = context.get("cachedPayload") if isinstance(context.get("cachedPayload"), dict) else {}
        cached_data = cached.get("data") if isinstance(cached.get("data"), dict) else {}
        if (
            cached.get("status") != "verified"
            or cached_data.get("status") != "verified"
            or cached_data.get("contractRevision") != COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION
            or not isinstance(cached_data.get("importedGearBySlot"), dict)
        ):
            problem = _import_problem(
                "template_import_evidence_incomplete",
                "The cached template import does not have complete sealed evidence.",
            )
            envelope = _import_envelope("blocked", request_id, cached.get("releaseContext"), problems=[problem])
            return 200, envelope, _import_timings(
                release_read_ms=release_read_ms,
                reconcile_ms=reconcile_ms,
                cache="hit",
            )
        envelope = _import_envelope(
            "verified",
            request_id,
            cached.get("releaseContext"),
            data=cached_data,
            problems=[],
        )
        return 200, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
            cache="hit",
        )

    source = context.get("source") if isinstance(context, dict) and isinstance(context.get("source"), dict) else {}
    source_status = source.get("status")
    authority_context = context.get("authorityContext") if isinstance(context, dict) else {}
    release_context = _release_context(authority_context)
    if (
        source_status != "verified"
        or source.get("contractRevision") != COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION
    ):
        problems = source.get("problems") if isinstance(source.get("problems"), list) else []
        if not problems:
            problems = [_import_problem(
                "template_import_evidence_incomplete",
                "The requested template does not have complete sealed import evidence.",
            )]
        envelope = _import_envelope("blocked", request_id, release_context, problems=problems)
        return 200, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
        )

    selection_intent = source.get("selectionIntent") if isinstance(source.get("selectionIntent"), dict) else None
    if selection_intent is None or not isinstance(authority_context, dict) or not authority_context:
        problem = _import_problem(
            "template_import_unavailable",
            "Community template authority is temporarily unavailable.",
            retryable=True,
        )
        envelope = _import_envelope("unavailable", request_id, release_context, problems=[problem])
        return 503, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
        )

    resolve_started = clock()
    try:
        snapshot = gear_resolver.resolve(selection_intent, authority_context)
    except Exception:
        problem = _import_problem(
            "template_import_unavailable",
            "Community template resolution failed unexpectedly.",
            retryable=True,
        )
        envelope = _import_envelope("unavailable", request_id, release_context, problems=[problem])
        return 503, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
            resolve_ms=(clock() - resolve_started) * 1000,
        )
    resolve_ms = (clock() - resolve_started) * 1000
    if not isinstance(snapshot, dict):
        problem = _import_problem(
            "template_import_unavailable",
            "Community template resolution returned an invalid response.",
            retryable=True,
        )
        envelope = _import_envelope("unavailable", request_id, release_context, problems=[problem])
        return 503, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
            resolve_ms=resolve_ms,
        )

    serialize_started = clock()
    if source_status == "verified" and snapshot.get("status") == "verified" and not snapshot.get("problems"):
        data = community_template_import_public_data(
            source,
            snapshot,
            release_context,
            authority_context=authority_context,
        )
        if data is None:
            problem = _import_problem(
                "template_import_evidence_incomplete",
                "The requested template does not have complete verified display evidence.",
            )
            envelope = _import_envelope("blocked", request_id, release_context, problems=[problem])
            return 200, envelope, _import_timings(
                release_read_ms=release_read_ms,
                reconcile_ms=reconcile_ms,
                resolve_ms=resolve_ms,
                serialize_ms=(clock() - serialize_started) * 1000,
            )
        payload = {
            "status": "verified",
            "releaseContext": release_context,
            "data": data,
        }
        cache_writer = getattr(store, "cache_community_template_import_verified", None)
        if callable(cache_writer) and (
            not isinstance(cache_state, dict)
            or cache_state.get("write") is not False
        ):
            try:
                cache_writer(context.get("cacheIdentity", ""), payload)
            except Exception:
                pass
        envelope = _import_envelope("verified", request_id, release_context, data=data, problems=[])
        return 200, envelope, _import_timings(
            release_read_ms=release_read_ms,
            reconcile_ms=reconcile_ms,
            resolve_ms=resolve_ms,
            serialize_ms=(clock() - serialize_started) * 1000,
        )

    problem = _import_problem(
        "template_import_blocked",
        "The template could not be resolved as verified gear.",
    )
    envelope = _import_envelope("blocked", request_id, release_context, problems=[problem])
    return 200, envelope, _import_timings(
        release_read_ms=release_read_ms,
        reconcile_ms=reconcile_ms,
        resolve_ms=resolve_ms,
        serialize_ms=(clock() - serialize_started) * 1000,
    )


def _resolve_selection_intent(
    raw_intent: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
    gear_release_id: str = "",
) -> tuple[int, dict[str, Any]]:
    """Resolve one untrusted Intent through current backend-owned authority."""

    intent, issues = parse_selection_intent(raw_intent)
    if issues:
        return _invalid_intent_envelope(raw_intent, request_id)
    if not str(simc_runtime_revision or "").strip():
        return _error_envelope(
            "AUTHORITY_UNAVAILABLE",
            "GEAR_SIMC_RUNTIME_REVISION_UNAVAILABLE",
            "Current SimulationCraft runtime revision is unavailable.",
            request_id,
        )

    eligibility = intent["eligibilityContext"]
    try:
        runtime_authority = gear_resolver_runtime_authority(
            eligibility["classKey"],
            eligibility["specKey"],
            simc_runtime_revision=simc_runtime_revision,
        )
    except ValueError:
        return _error_envelope(
            "INVALID_INTENT",
            "GEAR_ELIGIBILITY_UNKNOWN",
            "Selection Intent eligibility is not a current playable specialization.",
            request_id,
        )

    try:
        if gear_release_id:
            authority_context = store.get_candidate_gear_authority_context(
                intent,
                runtime_authority,
                gear_release_id,
            )
        else:
            authority_context = store.get_gear_authority_context(intent, runtime_authority)
    except Exception:
        return _error_envelope(
            "AUTHORITY_UNAVAILABLE",
            "GEAR_AUTHORITY_READ_UNAVAILABLE",
            "Current gear authority is temporarily unavailable.",
            request_id,
        )

    try:
        snapshot = gear_resolver.resolve(intent, authority_context)
    except Exception:
        return _error_envelope(
            "INTERNAL_ERROR",
            "GEAR_RESOLVER_INTERNAL_ERROR",
            "Gear resolution failed unexpectedly.",
            request_id,
            release_context=_release_context(authority_context),
        )
    return _snapshot_envelope(snapshot, authority_context, request_id)


def resolve_selection_intent(
    raw_intent: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
) -> tuple[int, dict[str, Any]]:
    """Resolve one untrusted Intent through the transitional public authority."""

    return _resolve_selection_intent(
        raw_intent,
        store=store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
    )


def resolve_candidate_selection_intent(
    raw_intent: Any,
    *,
    store: Any,
    gear_release_id: str,
    simc_runtime_revision: str,
    request_id: str,
) -> tuple[int, dict[str, Any]]:
    """Resolve one Intent through an exact inactive Gear Release for shadow only."""

    release_id = str(gear_release_id or "").strip()
    if not release_id:
        return _error_envelope(
            "AUTHORITY_UNAVAILABLE",
            "GEAR_RELEASE_ID_UNAVAILABLE",
            "Candidate Gear Release is unavailable.",
            request_id,
        )
    return _resolve_selection_intent(
        raw_intent,
        store=store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
        gear_release_id=release_id,
    )


def is_canonical_profile_request(raw_request: Any) -> bool:
    return isinstance(raw_request, dict) and "selectionIntent" in raw_request


def _profile_context(raw_request: Any) -> dict[str, Any]:
    request = raw_request if isinstance(raw_request, dict) else {}
    source = request.get("profileContext")
    source = source if isinstance(source, dict) else {}
    return {
        key: source[key]
        for key in PROFILE_CONTEXT_KEYS
        if key in source
    }


def _canonical_profile_ready(profile: Any, problems: list[dict[str, Any]]) -> bool:
    if not isinstance(profile, dict) or profile.get("status") != "resolved" or problems:
        return False
    talent_encoding = profile.get("talentEncoding")
    readiness = profile.get("profileReadiness")
    return (
        bool(str(profile.get("profile") or "").strip())
        and isinstance(talent_encoding, dict)
        and talent_encoding.get("status") in {"encoded", "external"}
        and isinstance(readiness, dict)
        and readiness.get("simcReady") is True
    )


def _blocked_profile_data(profile: Any, problems: list[dict[str, Any]]) -> dict[str, Any]:
    data = dict(profile) if isinstance(profile, dict) else {}
    readiness = data.get("profileReadiness")
    readiness = dict(readiness) if isinstance(readiness, dict) else {}
    readiness.update(
        {
            "status": "blocked",
            "simcReady": False,
            "problems": problems,
        }
    )
    data.update(
        {
            "status": "blocked",
            "profile": "",
            "profileReadiness": readiness,
            "problems": problems,
        }
    )
    return data


def _build_profile_from_selection_intent(
    raw_request: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
    profile_builder: Callable[..., dict[str, Any]] = build_websim_profile_response_from_resolved_snapshot,
    gear_release_id: str = "",
) -> tuple[int, dict[str, Any]]:
    """Re-resolve canonical profile input and serialize only the server snapshot."""

    request = raw_request if isinstance(raw_request, dict) else {}
    if gear_release_id:
        http_status, resolved_envelope = resolve_candidate_selection_intent(
            request.get("selectionIntent"),
            store=store,
            gear_release_id=gear_release_id,
            simc_runtime_revision=simc_runtime_revision,
            request_id=request_id,
        )
    else:
        http_status, resolved_envelope = resolve_selection_intent(
            request.get("selectionIntent"),
            store=store,
            simc_runtime_revision=simc_runtime_revision,
            request_id=request_id,
        )
    if http_status != 200 or resolved_envelope.get("status") != "resolved":
        return http_status, resolved_envelope

    snapshot = resolved_envelope["data"]
    try:
        profile = profile_builder(snapshot, source_context=_profile_context(request))
    except Exception:
        return _error_envelope(
            "INTERNAL_ERROR",
            "GEAR_PROFILE_SERIALIZER_INTERNAL_ERROR",
            "Canonical profile serialization failed unexpectedly.",
            request_id,
            release_context=resolved_envelope.get("releaseContext") or {},
        )
    profile_problems = profile.get("problems") if isinstance(profile, dict) else None
    profile_problems = profile_problems if isinstance(profile_problems, list) else []
    if not _canonical_profile_ready(profile, profile_problems):
        if not profile_problems:
            profile_problems = [
                gear_problem(
                    "ILLEGAL_SELECTION",
                    "GEAR_PROFILE_NOT_READY",
                    "Canonical profile is not ready.",
                )
            ]
        envelope = result_envelope(
            "blocked",
            request_id,
            resolved_envelope.get("releaseContext") or {},
            data=_blocked_profile_data(profile, profile_problems),
            problems=profile_problems,
        )
        return http_status_for_envelope(envelope), envelope

    envelope = result_envelope(
        "resolved",
        request_id,
        resolved_envelope.get("releaseContext") or {},
        data=profile,
        problems=[],
    )
    return http_status_for_envelope(envelope), envelope


def build_profile_from_selection_intent(
    raw_request: Any,
    *,
    store: Any,
    simc_runtime_revision: str,
    request_id: str,
    profile_builder: Callable[..., dict[str, Any]] = build_websim_profile_response_from_resolved_snapshot,
) -> tuple[int, dict[str, Any]]:
    """Build a canonical Profile through the transitional public authority."""

    return _build_profile_from_selection_intent(
        raw_request,
        store=store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
        profile_builder=profile_builder,
    )


def build_candidate_profile_from_selection_intent(
    raw_request: Any,
    *,
    store: Any,
    gear_release_id: str,
    simc_runtime_revision: str,
    request_id: str,
    profile_builder: Callable[..., dict[str, Any]] = build_websim_profile_response_from_resolved_snapshot,
) -> tuple[int, dict[str, Any]]:
    """Build a canonical Profile through an exact inactive Gear Release."""

    release_id = str(gear_release_id or "").strip()
    if not release_id:
        return _error_envelope(
            "AUTHORITY_UNAVAILABLE",
            "GEAR_RELEASE_ID_UNAVAILABLE",
            "Candidate Gear Release is unavailable.",
            request_id,
        )
    return _build_profile_from_selection_intent(
        raw_request,
        store=store,
        gear_release_id=release_id,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
        profile_builder=profile_builder,
    )


__all__ = (
    "COMMUNITY_TEMPLATE_IMPORT_ENVELOPE_REVISION",
    "PROFILE_CONTEXT_KEYS",
    "build_candidate_profile_from_selection_intent",
    "build_profile_from_selection_intent",
    "import_community_template",
    "is_canonical_profile_request",
    "resolve_candidate_selection_intent",
    "resolve_selection_intent",
)
