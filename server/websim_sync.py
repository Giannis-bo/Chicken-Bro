#!/usr/bin/env python3
import json
import os
from pathlib import Path

try:
    from .websim_payload import sync_websim_cache
except ImportError:
    from websim_payload import sync_websim_cache


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


def main():
    payload = sync_websim_cache(DB_PATH, include_blizzard=os.environ.get("WOW_WEBSIM_SKIP_BLIZZARD", "0") != "1")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
