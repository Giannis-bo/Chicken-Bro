#!/usr/bin/env python3
import json


ADMIN_GATE_QUEUE_STATUSES = {
    "partial",
    "stale",
    "blocked",
    "missing_credentials",
    "pending_official_audit",
    "source_reference",
}


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def build_raiderio_cache_read_model(row):
    if not row:
        return {
            "sourceStatus": "blocked",
            "status": "blocked",
            "errors": ["PostgreSQL Raider.IO cache is missing"],
        }
    payload = _json_value(row[0], {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("checkedAt", str(row[1] or ""))
    payload.setdefault("updatedAt", str(row[1] or ""))
    payload.setdefault("expiresAt", str(row[2] or ""))
    payload.setdefault("sourceStatus", payload.get("status") or "blocked")
    return payload


def build_stat_weight_cache_read_model(row, *, class_key, spec_key, scenario_key):
    if not row:
        return None
    payload = _json_value(row[0], {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("classKey", class_key)
    payload.setdefault("specKey", spec_key)
    payload.setdefault("scenarioKey", scenario_key)
    payload.setdefault("sourceStatus", row[1] or payload.get("status") or "blocked")
    payload.setdefault("status", payload.get("sourceStatus") or "blocked")
    payload.setdefault("checkedAt", str(row[2] or ""))
    payload.setdefault("updatedAt", str(row[2] or ""))
    return payload


def build_stat_weight_latest_run_read_model(rows):
    if not rows:
        return {
            "refreshMode": "",
            "refreshedAt": "",
            "status": "blocked",
            "sourceStatus": "blocked",
            "acceptedCount": 0,
            "blockedCount": 0,
            "errors": ["PostgreSQL stat weight cache is empty"],
        }
    accepted_statuses = {"verified", "partial", "stale"}
    accepted = sum(1 for row in rows if str(row[0] or "").strip() in accepted_statuses)
    blocked = len(rows) - accepted
    status = "verified" if accepted and not blocked else ("partial" if accepted else "blocked")
    latest = max((str(row[1] or "") for row in rows), default="")
    return {
        "refreshMode": "postgres_cache",
        "refreshedAt": latest,
        "status": status,
        "sourceStatus": status,
        "acceptedCount": accepted,
        "blockedCount": blocked,
        "specCount": 0,
        "scenarioCount": len(rows),
        "errors": [],
    }


def build_admin_gate_queue_summary_read_model(rows):
    total = 0
    domain_counts = {}
    blocker_counts = {}
    for domain, status, row_blockers in rows:
        blockers = [str(item or "").strip() for item in (row_blockers or []) if str(item or "").strip()]
        if status not in ADMIN_GATE_QUEUE_STATUSES and not blockers:
            continue
        domain_key = str(domain or "unknown")
        total += 1
        domain_counts[domain_key] = domain_counts.get(domain_key, 0) + 1
        for blocker in blockers:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    return {
        "count": total,
        "domainCounts": domain_counts,
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }
