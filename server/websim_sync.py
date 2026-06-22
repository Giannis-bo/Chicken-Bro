#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    from .raiderio_payload import sync_raiderio_cache
    from .websim_payload import sync_websim_cache
except ImportError:
    from raiderio_payload import sync_raiderio_cache
    from websim_payload import sync_websim_cache


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


def emit_progress(event):
    payload = {"event": "websim_sync_stage", **event}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def progress_event(stage, status, started_at=None, **details):
    event = {
        "stage": stage,
        "status": status,
    }
    if started_at is not None:
        event["durationSeconds"] = round(max(0.0, time.monotonic() - started_at), 3)
    if details:
        event.update(details)
    emit_progress(event)
    return time.monotonic()


def main():
    include_blizzard = os.environ.get("WOW_WEBSIM_SKIP_BLIZZARD", "0") != "1"
    websim_started = progress_event("websim", "start", includeBlizzard=include_blizzard)
    payload = {
        "websim": sync_websim_cache(DB_PATH, include_blizzard=include_blizzard, stage_callback=emit_progress)
    }
    progress_event(
        "websim",
        "complete",
        websim_started,
        ok=payload["websim"].get("ok"),
        errors=len(payload["websim"].get("errors") or []),
        dataStatus=payload["websim"].get("dataStatus") or "",
    )
    raiderio_started = progress_event("raiderio", "start")
    if os.environ.get("WOW_WEBSIM_SKIP_RAIDERIO", "0") == "1":
        payload["raiderio"] = {
            "sourceStatus": "skipped",
            "skipped": "WOW_WEBSIM_SKIP_RAIDERIO",
        }
        progress_event("raiderio", "skipped", raiderio_started, sourceStatus="skipped")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            payload["raiderio"] = sync_raiderio_cache(conn, stage_callback=emit_progress)
            conn.commit()
        progress_event(
            "raiderio",
            "complete",
            raiderio_started,
            sourceStatus=payload["raiderio"].get("sourceStatus") or "",
            profileCount=payload["raiderio"].get("profileCount") or 0,
        )
    except Exception as error:
        payload["raiderio"] = {
            "sourceStatus": "blocked",
            "errors": [str(error)],
        }
        progress_event("raiderio", "blocked", raiderio_started, errors=1)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
