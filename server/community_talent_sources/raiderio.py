import os
import sqlite3
from pathlib import Path


def default_db_path():
    return Path(os.environ.get("WOW_NEWS_DB", Path(__file__).resolve().parents[1] / "data" / "wow_news.sqlite3"))


def load_templates(conn=None):
    try:
        from ..raiderio_payload import get_raiderio_payload
    except ImportError:
        from raiderio_payload import get_raiderio_payload

    owns_connection = conn is None
    if owns_connection:
        conn = sqlite3.connect(default_db_path())
    try:
        payload = get_raiderio_payload(conn)
        status = payload.get("sourceStatus") or "blocked"
        return {
            "status": status,
            "sourceName": "Raider.IO",
            "templates": payload.get("communityTemplates") or [],
            "errors": payload.get("errors") or [],
        }
    finally:
        if owns_connection:
            conn.close()

