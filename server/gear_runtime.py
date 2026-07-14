#!/usr/bin/env python3
"""Runtime orchestration for canonical gear Resolve and profile requests."""

from __future__ import annotations

from typing import Any, Callable

try:
    from . import gear_resolver
    from .gear_contracts import parse_selection_intent
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
    envelope = result_envelope(
        status,
        request_id,
        _release_context(authority_context),
        data=snapshot,
        problems=problems,
    )
    return http_status_for_envelope(envelope), envelope


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
    "PROFILE_CONTEXT_KEYS",
    "build_candidate_profile_from_selection_intent",
    "build_profile_from_selection_intent",
    "is_canonical_profile_request",
    "resolve_candidate_selection_intent",
    "resolve_selection_intent",
)
