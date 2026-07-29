"""Fail-closed completeness contract for PostgreSQL Journal replacement."""

from __future__ import annotations

from typing import Any


JOURNAL_DISCOVERY_CONTRACT_REVISION = "websim-journal-discovery-v1"
JOURNAL_DISCOVERY_BOUNDARIES = (
    "dungeonInstances",
    "raidInstances",
    "encounters",
    "items",
)


def _unique_text(values: Any) -> list[str]:
    rows = []
    seen = set()
    for value in values if isinstance(values, (list, tuple, set)) else []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            rows.append(text)
    return rows


def journal_discovery_state(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    gaps = counts.get("gaps") if isinstance(counts.get("gaps"), list) else []
    blocker_codes = _unique_text(counts.get("blockerCodes") or [])
    blockers = _unique_text(
        [
            *(counts.get("blockers") or []),
            *(counts.get("errors") or []),
        ]
    )
    if not counts:
        blocker_codes.append("SOURCE_DISCOVERY_COUNTS_MISSING")
        blockers.append(
            "SOURCE_DISCOVERY_COUNTS_MISSING: Journal discovery counts are required"
        )
    limits = counts.get("limits") if isinstance(counts.get("limits"), dict) else {}
    truncation = (
        counts.get("truncation")
        if isinstance(counts.get("truncation"), dict)
        else {}
    )
    boundary_counts_valid = all(
        isinstance(limits.get(boundary), int)
        and not isinstance(limits.get(boundary), bool)
        and isinstance(truncation.get(boundary), int)
        and not isinstance(truncation.get(boundary), bool)
        and truncation[boundary] >= 0
        for boundary in JOURNAL_DISCOVERY_BOUNDARIES
    )
    list_fields_valid = all(
        isinstance(counts.get(field), list)
        for field in ("gaps", "blockerCodes", "blockers", "errors")
    )
    fetch_failure_count = counts.get("fetchFailureCount")
    fetch_failure_count_valid = (
        isinstance(fetch_failure_count, int)
        and not isinstance(fetch_failure_count, bool)
        and fetch_failure_count >= 0
    )
    contract_shape_valid = (
        boundary_counts_valid
        and list_fields_valid
        and fetch_failure_count_valid
    )
    if counts and not contract_shape_valid:
        blocker_codes.append("SOURCE_DISCOVERY_CONTRACT_INVALID")
        blockers.append(
            "SOURCE_DISCOVERY_CONTRACT_INVALID: Journal boundary counts and diagnostics are required"
        )
    if boundary_counts_valid and any(truncation.values()):
        blocker_codes.append("SOURCE_CAP_TRUNCATED")
        blockers.append(
            "SOURCE_CAP_TRUNCATED: Journal discovery reports omitted capped relations"
        )
    if fetch_failure_count_valid and fetch_failure_count:
        blocker_codes.append("SOURCE_FETCH_FAILED")
        blockers.append(
            "SOURCE_FETCH_FAILED: Journal discovery reports source fetch failures"
        )
    if counts.get("membershipComplete") is not True:
        blocker_codes.append("SOURCE_MEMBERSHIP_COMPLETENESS_UNPROVEN")
        blockers.append(
            "SOURCE_MEMBERSHIP_COMPLETENESS_UNPROVEN: Journal discovery is incomplete"
        )
    if gaps and not blocker_codes:
        blocker_codes.append("SOURCE_DISCOVERY_GAP")
    if gaps and not blockers:
        blockers.append(
            f"SOURCE_DISCOVERY_GAP: {len(gaps)} Journal discovery gap(s)"
        )
    blocker_codes = _unique_text(blocker_codes)
    blockers = _unique_text(blockers)
    verified = (
        counts.get("sourceStatus") == "verified"
        and counts.get("membershipComplete") is True
        and not gaps
        and not blocker_codes
        and not blockers
        and contract_shape_valid
    )
    return {
        **counts,
        "contractRevision": JOURNAL_DISCOVERY_CONTRACT_REVISION,
        "sourceStatus": "verified" if verified else "blocked",
        "membershipComplete": verified,
        "gaps": gaps,
        "blockerCodes": blocker_codes,
        "blockers": blockers,
        "errors": blockers,
    }


def require_complete_journal_discovery(data: Any) -> dict[str, Any]:
    state = journal_discovery_state(data)
    if state["sourceStatus"] != "verified":
        reason = ",".join(state["blockerCodes"]) or "SOURCE_DISCOVERY_BLOCKED"
        raise RuntimeError(f"Journal discovery replacement blocked: {reason}")
    return state
