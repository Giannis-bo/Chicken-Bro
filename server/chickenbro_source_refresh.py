#!/usr/bin/env python3
"""Refresh the non-personal sources used by Chickenbro chat.

This deliberately does not compile or promote observed builds.  A Gear Release
integrity failure must stay visible in its own job instead of preventing the
source cache used by ordinary chat from refreshing.
"""

import json

try:
    from .db import postgres_only_runtime_enabled
    from .postgres_cache_sync import sync_raiderio_cache_postgres
except ImportError:
    from db import postgres_only_runtime_enabled
    from postgres_cache_sync import sync_raiderio_cache_postgres


SUCCESS_STATUSES = {"synced", "verified", "partial"}


def compact_errors(values):
    return [str(value).strip()[:240] for value in (values or []) if str(value).strip()][:3]


def run_refresh(*, postgres_enabled=postgres_only_runtime_enabled, sync_raiderio=sync_raiderio_cache_postgres):
    if not postgres_enabled():
        return {
            "event": "chickenbro_source_refresh",
            "sourceKey": "raiderio",
            "sourceStatus": "blocked",
            "errors": ["PostgreSQL-only runtime is required."],
        }, 1
    try:
        payload = sync_raiderio(force=True) or {}
    except Exception as error:
        payload = {"sourceStatus": "blocked", "errors": [str(error)]}

    source_status = str(payload.get("sourceStatus") or payload.get("status") or "blocked").strip().lower()
    summary = {
        "event": "chickenbro_source_refresh",
        "sourceKey": "raiderio",
        "sourceStatus": source_status,
        "checkedAt": str(payload.get("checkedAt") or ""),
        "expiresAt": str(payload.get("expiresAt") or ""),
        "profileCount": int(payload.get("profileCount") or 0),
        "errors": compact_errors(payload.get("errors")),
    }
    return summary, 0 if source_status in SUCCESS_STATUSES else 1


def main():
    summary, exit_code = run_refresh()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
