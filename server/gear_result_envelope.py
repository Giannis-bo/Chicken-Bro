#!/usr/bin/env python3
"""Pure result-envelope semantics for future equipment resolver routes."""

from __future__ import annotations

import json
from typing import Any, Iterable


RESULT_ENVELOPE_CONTRACT_REVISION = "gear-result-envelope-v1"
PROBLEM_KINDS = {
    "INVALID_INTENT",
    "ILLEGAL_SELECTION",
    "REVISION_CONFLICT",
    "AUTHORITY_UNAVAILABLE",
    "SIMC_UNAVAILABLE",
    "INTERNAL_ERROR",
}
RESULT_STATUSES = {"resolved", "blocked", "pending", "unavailable"}

_PROBLEM_KIND_ORDER = {
    "INVALID_INTENT": 0,
    "ILLEGAL_SELECTION": 1,
    "REVISION_CONFLICT": 2,
    "AUTHORITY_UNAVAILABLE": 3,
    "SIMC_UNAVAILABLE": 4,
    "INTERNAL_ERROR": 5,
}


def _canonical_json_value(value: Any) -> Any:
    """Return a detached JSON value with recursively sorted object keys."""

    return json.loads(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def gear_problem(
    kind: str,
    code: str,
    title: str,
    *,
    detail: str = "",
    path: str = "",
    retryable: bool = False,
    meta: Any = None,
) -> dict[str, Any]:
    """Build one structured problem using the closed Phase 1 kind allowlist."""

    if kind not in PROBLEM_KINDS:
        raise ValueError(f"Unsupported gear problem kind: {kind}")
    return {
        "kind": kind,
        "code": str(code),
        "title": str(title),
        "detail": str(detail),
        "path": str(path),
        "retryable": bool(retryable),
        "meta": _canonical_json_value({} if meta is None else meta),
    }


def _normalize_problem(problem: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(problem, dict):
        raise ValueError("Gear problems must be objects.")
    return gear_problem(
        problem.get("kind"),
        problem.get("code", ""),
        problem.get("title", ""),
        detail=problem.get("detail", ""),
        path=problem.get("path", ""),
        retryable=problem.get("retryable", False),
        meta=problem.get("meta", {}),
    )


def _problem_sort_key(problem: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _PROBLEM_KIND_ORDER[problem["kind"]],
        problem["code"],
        problem["path"],
        problem["title"],
        problem["detail"],
        json.dumps(problem["meta"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def result_envelope(
    status: str,
    request_id: str,
    release_context: dict[str, Any],
    *,
    data: Any = None,
    problems: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the fixed v1 envelope without importing any route or store."""

    if status not in RESULT_STATUSES:
        raise ValueError(f"Unsupported gear result status: {status}")
    if not isinstance(release_context, dict):
        raise ValueError("release_context must be an object.")
    normalized_problems = sorted(
        (_normalize_problem(problem) for problem in (problems or [])),
        key=_problem_sort_key,
    )
    return {
        "contractRevision": RESULT_ENVELOPE_CONTRACT_REVISION,
        "requestId": str(request_id),
        "status": status,
        "releaseContext": _canonical_json_value(release_context),
        "data": _canonical_json_value({} if data is None else data),
        "problems": normalized_problems,
    }


def http_status_for_envelope(envelope: dict[str, Any]) -> int:
    """Map a future resolver envelope to the approved HTTP semantics."""

    status = envelope.get("status") if isinstance(envelope, dict) else None
    if status == "resolved":
        return 200
    if status == "pending":
        return 202

    kinds = {
        problem.get("kind")
        for problem in envelope.get("problems", [])
        if isinstance(problem, dict)
    }
    if "INTERNAL_ERROR" in kinds:
        return 500
    if kinds.intersection({"AUTHORITY_UNAVAILABLE", "SIMC_UNAVAILABLE"}):
        return 503
    if "REVISION_CONFLICT" in kinds:
        return 409
    if "INVALID_INTENT" in kinds:
        return 400
    if status == "unavailable":
        return 503
    if status == "blocked" or "ILLEGAL_SELECTION" in kinds:
        return 200
    raise ValueError(f"Envelope has unsupported status: {status}")


__all__ = (
    "gear_problem",
    "result_envelope",
    "http_status_for_envelope",
)
