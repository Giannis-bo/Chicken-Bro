"""Bounded terminal serialization for scheduled sync runners.

Full sync state belongs in PostgreSQL. This module deliberately keeps only
truthful status, identity, scalar counts, and diagnostic counts for
journald/syslog.
"""

from __future__ import annotations

import json
from typing import Any


MAX_SYNC_LOG_BYTES = 8192
MAX_COMPONENTS = 16
MAX_COUNT_FIELDS = 32
MAX_TEXT_CHARS = 160

VERIFIED_STATUSES = {
    "complete",
    "ok",
    "pass",
    "ready",
    "synced",
    "verified",
}
PARTIAL_STATUSES = {
    "missing",
    "missing_credentials",
    "partial",
    "pending",
    "skipped",
    "stale",
}
BLOCKED_STATUSES = {
    "blocked",
    "error",
    "fail",
    "failed",
    "unsupported",
}
STATUS_RANK = {
    "verified": 0,
    "partial": 1,
    "blocked": 2,
}


def _text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    return str(value or "").strip()[:limit]


def _diagnostic_count(value: Any) -> int:
    if value in (None, "", [], {}):
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return 1


def _normalize_status(value: Any) -> str:
    status = _text(value).lower()
    if status in BLOCKED_STATUSES:
        return "blocked"
    if status in PARTIAL_STATUSES:
        return "partial"
    if status in VERIFIED_STATUSES:
        return "verified"
    return ""


def _worst_status(statuses: list[str]) -> str:
    rows = [status for status in statuses if status in STATUS_RANK]
    if not rows:
        return "blocked"
    return max(rows, key=lambda status: STATUS_RANK[status])


def _component_status(component: dict[str, Any]) -> str:
    statuses = [
        _normalize_status(component.get(key))
        for key in ("status", "sourceStatus", "dataStatus")
    ]
    statuses = [status for status in statuses if status]
    if statuses:
        status = _worst_status(statuses)
        if (
            status == "verified"
            and _diagnostic_count(component.get("errors"))
        ):
            return "partial"
        return status
    if component.get("ok") is True:
        return (
            "partial"
            if _diagnostic_count(component.get("errors"))
            else "verified"
        )
    return "blocked"


def _count_field(key: str, value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    lowered = key.lower()
    return (
        key in {"errors", "warnings"}
        or lowered.endswith(
            (
                "bytes",
                "count",
                "durationseconds",
                "limit",
                "percent",
                "seconds",
                "total",
            )
        )
    )


def _component_summary(component: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": _component_status(component),
    }
    for key in (
        "runner",
        "schemaRevision",
        "revision",
        "catalogRevision",
        "gearCatalogRevision",
        "sourceRevision",
        "refreshedAt",
        "checkedAt",
    ):
        value = _text(component.get(key))
        if value:
            summary[key] = value
    error_count = _diagnostic_count(component.get("errors"))
    warning_count = _diagnostic_count(component.get("warnings"))
    if error_count:
        summary["errorCount"] = error_count
    if warning_count:
        summary["warningCount"] = warning_count
    counts = {
        key: value
        for key, value in sorted(component.items())
        if _count_field(key, value)
    }
    if counts:
        summary["counts"] = dict(
            list(counts.items())[:MAX_COUNT_FIELDS]
        )
        if len(counts) > MAX_COUNT_FIELDS:
            summary["countFieldsTruncated"] = True
    return summary


def sync_result_summary(
    payload: dict[str, Any],
    *,
    event: str,
) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    component_rows = [
        (str(key), value)
        for key, value in sorted(source.items())
        if isinstance(value, dict)
    ][:MAX_COMPONENTS]
    components = {
        _text(key, 80): _component_summary(value)
        for key, value in component_rows
    }
    statuses = [
        component.get("status")
        for component in components.values()
    ]
    return {
        "event": _text(event, 80) or "sync_complete",
        "status": _worst_status(statuses),
        "components": components,
        "diagnostics": {
            "componentCount": len(components),
            "componentsTruncated": len(
                [
                    value
                    for value in source.values()
                    if isinstance(value, dict)
                ]
            )
            > len(components),
        },
    }


def bounded_progress_event(event: dict[str, Any]) -> dict[str, Any]:
    source = event if isinstance(event, dict) else {}
    bounded: dict[str, Any] = {}
    for key in (
        "event",
        "stage",
        "status",
        "runner",
        "dataStatus",
        "sourceStatus",
    ):
        value = _text(source.get(key))
        if value:
            bounded[key] = value
    for key, value in sorted(source.items()):
        if key in bounded:
            continue
        if isinstance(value, bool) and key in {"includeBlizzard", "ok"}:
            bounded[key] = value
        elif _count_field(key, value):
            bounded[key] = value
    if "event" not in bounded:
        bounded["event"] = "sync_stage"
    if "status" not in bounded:
        bounded["status"] = "blocked"
    return bounded


def bounded_json_line(
    value: dict[str, Any],
    *,
    max_bytes: int = MAX_SYNC_LOG_BYTES,
) -> str:
    limit = max(512, min(int(max_bytes), MAX_SYNC_LOG_BYTES))
    line = json.dumps(
        value if isinstance(value, dict) else {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(line.encode("utf-8")) <= limit:
        return line
    components = value.get("components") if isinstance(value, dict) else {}
    minimal_components = {}
    if isinstance(components, dict):
        for key, component in list(sorted(components.items()))[:MAX_COMPONENTS]:
            if not isinstance(component, dict):
                continue
            minimal_components[_text(key, 80)] = {
                field: component.get(field)
                for field in ("status", "runner", "errorCount", "warningCount")
                if component.get(field) not in (None, "")
            }
    minimal = {
        "event": _text(value.get("event"), 80) or "sync_event",
        "status": _text(value.get("status"), 40) or "blocked",
        "components": minimal_components,
        "diagnostics": {
            "truncated": True,
            "maxBytes": limit,
        },
    }
    line = json.dumps(
        minimal,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(line.encode("utf-8")) <= limit:
        return line
    return json.dumps(
        {
            "event": _text(value.get("event"), 40) or "sync_event",
            "status": _text(value.get("status"), 20) or "blocked",
            "diagnostics": {
                "truncated": True,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
