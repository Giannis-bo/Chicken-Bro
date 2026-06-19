#!/usr/bin/env python3
import json
import os
import sqlite3
from pathlib import Path

try:
    from .raiderio_payload import sync_raiderio_cache
    from .websim_payload import sync_websim_cache
except ImportError:
    from raiderio_payload import sync_raiderio_cache
    from websim_payload import sync_websim_cache


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


def main():
    payload = {
        "websim": sync_websim_cache(DB_PATH, include_blizzard=os.environ.get("WOW_WEBSIM_SKIP_BLIZZARD", "0") != "1")
    }
    try:
        with sqlite3.connect(DB_PATH) as conn:
            payload["raiderio"] = sync_raiderio_cache(conn)
            conn.commit()
    except Exception as error:
        payload["raiderio"] = {
            "sourceStatus": "blocked",
            "errors": [str(error)],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
