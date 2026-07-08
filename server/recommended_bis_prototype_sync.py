#!/usr/bin/env python3
import json
import os
import sys

try:
    from .postgres_cache_sync import sync_recommended_bis_prototype_postgres
except ImportError:
    from postgres_cache_sync import sync_recommended_bis_prototype_postgres


def main():
    mode = os.environ.get("WOW_RECOMMENDED_BIS_PROTOTYPE_SYNC_MODE", "manual")
    payload = sync_recommended_bis_prototype_postgres(mode=mode)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("errors") == [] else 1


if __name__ == "__main__":
    sys.exit(main())
