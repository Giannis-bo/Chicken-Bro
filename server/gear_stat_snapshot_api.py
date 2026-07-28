#!/usr/bin/env python3
"""Canonical asynchronous API orchestration for Gear stat snapshots."""

from __future__ import annotations

from typing import Any, Callable

try:
    from .gear_contracts import parse_selection_intent
    from .gear_result_envelope import gear_problem, http_status_for_envelope, result_envelope
    from .gear_runtime import PROFILE_CONTEXT_KEYS, resolve_selection_intent
    from .gear_stat_snapshot import build_stat_signature, client_key_hash
    from .gear_stat_snapshot_store import GearStatSnapshotQueueUnavailable
    from .websim_payload import (
        WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
        build_websim_profile_response_from_resolved_snapshot,
    )
except ImportError:
    from gear_contracts import parse_selection_intent
    from gear_result_envelope import gear_problem, http_status_for_envelope, result_envelope
    from gear_runtime import PROFILE_CONTEXT_KEYS, resolve_selection_intent
    from gear_stat_snapshot import build_stat_signature, client_key_hash
    from gear_stat_snapshot_store import GearStatSnapshotQueueUnavailable
    from websim_payload import (
        WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
        build_websim_profile_response_from_resolved_snapshot,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _problem_envelope(
    request_id: str,
    release_context: dict[str, Any],
    *,
    kind: str,
    code: str,
    title: str,
    retryable: bool,
    status: str = "unavailable",
) -> tuple[int, dict[str, Any]]:
    envelope = result_envelope(
        status,
        request_id,
        release_context,
        problems=[gear_problem(kind, code, title, retryable=retryable)],
    )
    return http_status_for_envelope(envelope), envelope


def _canonical_request(raw_request: Any) -> dict[str, Any]:
    request = raw_request if isinstance(raw_request, dict) else {}
    intent, issues = parse_selection_intent(request.get("selectionIntent"))
    if issues:
        raise ValueError("resolved request did not retain a valid Selection Intent")
    raw_context = request.get("profileContext")
    raw_context = raw_context if isinstance(raw_context, dict) else {}
    profile_context = {
        key: raw_context[key]
        for key in PROFILE_CONTEXT_KEYS
        if key in raw_context
    }
    return {"selectionIntent": intent, "profileContext": profile_context}


def prepare_stat_snapshot_request(
    raw_request: Any,
    *,
    authority_store: Any,
    simc_runtime_revision: str,
    request_id: str,
    resolver: Callable[..., tuple[int, dict[str, Any]]] = resolve_selection_intent,
    profile_builder: Callable[..., dict[str, Any]] = build_websim_profile_response_from_resolved_snapshot,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Resolve and serialize a canonical iterations=1 profile without executing SimC."""

    request = raw_request if isinstance(raw_request, dict) else {}
    http_status, resolved = resolver(
        request.get("selectionIntent"),
        store=authority_store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
    )
    if http_status != 200 or resolved.get("status") != "resolved":
        return http_status, resolved, {}
    release_context = resolved.get("releaseContext")
    release_context = release_context if isinstance(release_context, dict) else {}
    if release_context.get("formalActiveManifest") is not True:
        status, envelope = _problem_envelope(
            request_id,
            release_context,
            kind="AUTHORITY_UNAVAILABLE",
            code="GEAR_STAT_FORMAL_MANIFEST_REQUIRED",
            title="A formal active Gear Manifest is required for stat snapshots.",
            retryable=True,
        )
        return status, envelope, {}
    canonical_request = _canonical_request(request)
    try:
        profile = profile_builder(
            resolved.get("data") or {},
            source_context=canonical_request["profileContext"],
            execution_flavor=WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
            talent_store=authority_store,
        )
        profile_text = _text(profile.get("profile") if isinstance(profile, dict) else "")
        readiness = profile.get("profileReadiness") if isinstance(profile, dict) else {}
        if (
            not profile_text
            or not isinstance(readiness, dict)
            or readiness.get("simcReady") is not True
            or profile.get("status") != "resolved"
        ):
            raise ValueError("canonical stat profile is not ready")
        signature = build_stat_signature(resolved.get("data") or {}, profile_text, release_context)
    except ValueError:
        status, envelope = _problem_envelope(
            request_id,
            release_context,
            kind="ILLEGAL_SELECTION",
            code="GEAR_STAT_PROFILE_NOT_READY",
            title="Canonical stat profile is not ready.",
            retryable=False,
            status="blocked",
        )
        return status, envelope, {}
    except Exception:
        status, envelope = _problem_envelope(
            request_id,
            release_context,
            kind="INTERNAL_ERROR",
            code="GEAR_STAT_PROFILE_INTERNAL_ERROR",
            title="Canonical stat profile preparation failed unexpectedly.",
            retryable=True,
        )
        return status, envelope, {}
    return 200, resolved, {
        "request": canonical_request,
        "resolvedSnapshot": resolved.get("data") or {},
        "releaseContext": release_context,
        "profile": profile_text,
        "signature": signature,
    }


def _verified_response(
    request_id: str,
    release_context: dict[str, Any],
    stored: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    envelope = result_envelope(
        "resolved",
        request_id,
        release_context,
        data={
            "statSignature": _text(stored.get("statSignature")),
            "snapshotHash": _text(stored.get("snapshotHash")),
            "statSnapshot": stored.get("snapshot") if isinstance(stored.get("snapshot"), dict) else {},
            "verifiedAt": _text(stored.get("verifiedAt")),
        },
    )
    return 200, envelope


def get_or_start_stat_snapshot(
    raw_request: Any,
    *,
    authority_store: Any,
    snapshot_store: Any,
    simc_runtime_revision: str,
    request_id: str,
    client_id: str,
    now: str,
    resolver: Callable[..., tuple[int, dict[str, Any]]] = resolve_selection_intent,
    profile_builder: Callable[..., dict[str, Any]] = build_websim_profile_response_from_resolved_snapshot,
) -> tuple[int, dict[str, Any]]:
    """Return a verified snapshot, queue one job, or fail closed without running SimC."""

    status, resolved, prepared = prepare_stat_snapshot_request(
        raw_request,
        authority_store=authority_store,
        simc_runtime_revision=simc_runtime_revision,
        request_id=request_id,
        resolver=resolver,
        profile_builder=profile_builder,
    )
    if not prepared:
        return status, resolved
    release_context = prepared["releaseContext"]
    signature = prepared["signature"]["statSignature"]
    try:
        cached = snapshot_store.lookup_snapshot(signature, record_request=True)
    except Exception:
        return _problem_envelope(
            request_id,
            release_context,
            kind="AUTHORITY_UNAVAILABLE",
            code="GEAR_STAT_STORE_UNAVAILABLE",
            title="Stat snapshot storage is temporarily unavailable.",
            retryable=True,
        )
    if cached:
        return _verified_response(request_id, release_context, cached)

    try:
        worker = snapshot_store.worker_readiness(
            simc_runtime_revision=simc_runtime_revision,
            now=now,
            max_age_seconds=30,
        )
    except Exception:
        worker = {"ready": False}
    if worker.get("ready") is not True:
        return _problem_envelope(
            request_id,
            release_context,
            kind="SIMC_UNAVAILABLE",
            code="GEAR_STAT_WORKER_UNAVAILABLE",
            title="A matching stat snapshot worker is not available.",
            retryable=True,
        )

    try:
        result = snapshot_store.get_or_start(
            signature,
            request_payload=prepared["request"],
            release_context=release_context,
            client_key_hash=client_key_hash(client_id),
            now=now,
            record_request=False,
        )
    except GearStatSnapshotQueueUnavailable as error:
        return _problem_envelope(
            request_id,
            release_context,
            kind="SIMC_UNAVAILABLE",
            code=error.code,
            title="Stat snapshot capacity is temporarily unavailable.",
            retryable=True,
        )
    except Exception:
        return _problem_envelope(
            request_id,
            release_context,
            kind="AUTHORITY_UNAVAILABLE",
            code="GEAR_STAT_STORE_UNAVAILABLE",
            title="Stat snapshot storage is temporarily unavailable.",
            retryable=True,
        )
    result_status = result.get("status")
    if result_status == "verified":
        return _verified_response(request_id, release_context, result.get("snapshot") or {})
    if result_status == "pending":
        job = result.get("job") if isinstance(result.get("job"), dict) else {}
        envelope = result_envelope(
            "pending",
            request_id,
            release_context,
            data={
                "jobId": int(job.get("jobId") or 0),
                "statSignature": signature,
                "queuedAt": _text(job.get("queuedAt")),
                "status": "pending",
                "retryAfterMs": 1500,
            },
        )
        return 202, envelope
    problem = result.get("problem") if isinstance(result.get("problem"), dict) else {}
    if result_status == "blocked":
        return _problem_envelope(
            request_id,
            release_context,
            kind="ILLEGAL_SELECTION",
            code=_text(problem.get("code")) or "GEAR_STAT_BLOCKED",
            title="Stat snapshot generation is blocked for this exact configuration.",
            retryable=False,
            status="blocked",
        )
    return _problem_envelope(
        request_id,
        release_context,
        kind="SIMC_UNAVAILABLE",
        code=_text(problem.get("code")) or "GEAR_STAT_COOLDOWN",
        title="Stat snapshot generation is temporarily unavailable.",
        retryable=True,
    )


__all__ = ("get_or_start_stat_snapshot", "prepare_stat_snapshot_request")
