#!/usr/bin/env python3
import json
import os

try:
    from .db import postgres_only_runtime_enabled
    from .postgres_cache_sync import sync_recommended_bis_guard_postgres
except ImportError:
    from db import postgres_only_runtime_enabled
    from postgres_cache_sync import sync_recommended_bis_guard_postgres


def main(mode=None):
    mode = mode or os.environ.get("WOW_RECOMMENDED_BIS_GUARD_SYNC_MODE", "scheduled")
    if not postgres_only_runtime_enabled():
        payload = {
            "runner": "sqlite",
            "schemaRevision": "recommended-bis-v1-guard-state-v1",
            "status": "blocked",
            "errors": ["recommended_bis_v1 guard sync requires PostgreSQL runtime"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    payload = sync_recommended_bis_guard_postgres(mode=mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
