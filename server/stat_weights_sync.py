#!/usr/bin/env python3
import json
import os
import sqlite3
from pathlib import Path

try:
    from .raiderio_payload import get_raiderio_payload, sync_raiderio_cache
    from .stat_weights_payload import sync_stat_weight_cache
except ImportError:
    from raiderio_payload import get_raiderio_payload, sync_raiderio_cache
    from stat_weights_payload import sync_stat_weight_cache


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def main():
    payload = {"raiderio": {}, "statWeights": {}}
    with connect_db() as conn:
        try:
            payload["raiderio"] = sync_raiderio_cache(conn)
        except Exception as error:
            payload["raiderio"] = get_raiderio_payload(conn, allow_sync=False)
            payload["raiderio"]["syncError"] = str(error)
        payload["statWeights"] = sync_stat_weight_cache(
            conn,
            raiderio_payload=payload["raiderio"],
            refresh_mode=os.environ.get("WOW_STAT_WEIGHTS_REFRESH_MODE", "scheduled"),
        )
        conn.commit()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
