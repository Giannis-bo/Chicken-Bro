#!/usr/bin/env python3
import json
import os

try:
    from .db import postgres_only_runtime_enabled
    from .postgres_cache_sync import sync_season_recommended_gear_postgres
except ImportError:
    from db import postgres_only_runtime_enabled
    from postgres_cache_sync import sync_season_recommended_gear_postgres


def main(mode=None):
    mode = mode or os.environ.get("WOW_SEASON_RECOMMENDED_GEAR_SYNC_MODE", "scheduled")
    if not postgres_only_runtime_enabled():
        payload = {
            "runner": "sqlite",
            "sourceKey": "season_recommendation",
            "status": "blocked",
            "errors": ["season recommended gear sync requires PostgreSQL runtime"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    payload = sync_season_recommended_gear_postgres(mode=mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
