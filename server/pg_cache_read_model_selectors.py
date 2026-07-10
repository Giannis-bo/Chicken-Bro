#!/usr/bin/env python3
import json


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
