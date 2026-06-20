#!/usr/bin/env python3
import json
import os
import sqlite3
from pathlib import Path

try:
    from .raiderio_payload import sync_raiderio_cache
    from .websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ensure_websim_tables,
        get_active_season_payload,
        get_sync_state,
        set_sync_state,
        sync_community_gear_templates,
        sync_community_talent_templates,
        sync_websim_gear_catalog,
        utc_now,
    )
except ImportError:
    from raiderio_payload import sync_raiderio_cache
    from websim_payload import (
        COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
        COMMUNITY_TALENT_SYNC_KEY,
        ensure_websim_tables,
        get_active_season_payload,
        get_sync_state,
        set_sync_state,
        sync_community_gear_templates,
        sync_community_talent_templates,
        sync_websim_gear_catalog,
        utc_now,
    )


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WOW_NEWS_DB", BASE_DIR / "data" / "wow_news.sqlite3"))


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def source_status_from_parts(parts):
    statuses = [str(item.get("sourceStatus") or item.get("status") or "") for item in parts if isinstance(item, dict)]
    if any(status == "blocked" for status in statuses):
        return "partial" if any(status in {"synced", "verified", "partial"} for status in statuses) else "blocked"
    if any(status == "missing_credentials" for status in statuses):
        return "partial" if any(status in {"synced", "verified", "partial"} for status in statuses) else "missing_credentials"
    if any(status == "partial" for status in statuses):
        return "partial"
    if statuses and all(status in {"synced", "verified"} for status in statuses):
        return "synced"
    return "blocked"


def record_sync_run(conn, payload):
    conn.execute(
        """
        INSERT INTO community_template_sync_runs (
            id, mode, status, source_status, started_at, finished_at,
            scan_coverage_json, talent_counts_json, gear_counts_json,
            source_refs_json, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            mode=excluded.mode,
            status=excluded.status,
            source_status=excluded.source_status,
            started_at=excluded.started_at,
            finished_at=excluded.finished_at,
            scan_coverage_json=excluded.scan_coverage_json,
            talent_counts_json=excluded.talent_counts_json,
            gear_counts_json=excluded.gear_counts_json,
            source_refs_json=excluded.source_refs_json,
            payload_json=excluded.payload_json
        """,
        (
            payload["scanRunId"],
            payload["mode"],
            payload["status"],
            payload["sourceStatus"],
            payload["startedAt"],
            payload["finishedAt"],
            json.dumps(payload.get("scanCoverage") or {}, ensure_ascii=False),
            json.dumps((payload.get("talents") or {}).get("templates") or {}, ensure_ascii=False),
            json.dumps((payload.get("gear") or {}).get("templates") or {}, ensure_ascii=False),
            json.dumps(payload.get("sourceRefs") or [], ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    set_sync_state(conn, COMMUNITY_TEMPLATE_SYNC_RUN_KEY, payload)


def sync_community_template_cache(conn, mode="scheduled"):
    ensure_websim_tables(conn)
    started_at = utc_now()
    scan_run_id = f"community-template-{started_at.replace(':', '').replace('+', 'z')}"
    errors = []

    try:
        raiderio = sync_raiderio_cache(conn)
    except Exception as error:
        raiderio = {"sourceStatus": "blocked", "errors": [str(error)]}
        errors.append(f"Raider.IO cache failed: {error}")

    try:
        talents = sync_community_talent_templates(conn)
    except Exception as error:
        talents = {
            "sourceStatus": "blocked",
            "sources": {},
            "templates": {"total": 0, "verified": 0, "blocked": 0},
            "errors": [str(error)],
        }
        set_sync_state(conn, COMMUNITY_TALENT_SYNC_KEY, talents)
        errors.append(f"community talent templates failed: {error}")

    try:
        gear_catalog = sync_websim_gear_catalog(conn, get_active_season_payload(conn))
    except Exception as error:
        gear_catalog = {"status": "blocked", "errors": [str(error)]}
        errors.append(f"gear catalog observed variants failed: {error}")

    try:
        gear = sync_community_gear_templates(conn, scan_run_id=scan_run_id)
    except Exception as error:
        gear = {
            "sourceStatus": "blocked",
            "templates": {"total": 0, "verified": 0, "partial": 0, "blocked": 0},
            "errors": [str(error)],
        }
        errors.append(f"community gear templates failed: {error}")

    source_status = source_status_from_parts([
        raiderio,
        talents,
        gear_catalog,
        gear,
    ])
    scan_coverage = talents.get("scanCoverage") or {}
    raiderio_coverage = raiderio.get("specCoverage") if isinstance(raiderio.get("specCoverage"), dict) else {}
    if raiderio_coverage:
        scan_coverage = {**scan_coverage, "raiderio": raiderio_coverage}
    payload = {
        "scanRunId": scan_run_id,
        "mode": mode,
        "status": "blocked" if source_status == "blocked" else "completed",
        "sourceStatus": source_status,
        "startedAt": started_at,
        "finishedAt": utc_now(),
        "scanCoverage": scan_coverage,
        "raiderio": {
            "sourceStatus": raiderio.get("sourceStatus") or raiderio.get("status") or "",
            "runCount": raiderio.get("runCount") or 0,
            "profileCount": raiderio.get("profileCount") or 0,
            "specCoverage": raiderio_coverage,
            "checkedAt": raiderio.get("checkedAt") or "",
        },
        "talents": talents,
        "gearCatalog": gear_catalog,
        "gear": gear,
        "sourceRefs": [
            {"sourceKey": "raiderio", "sourceName": "Raider.IO", "sourceStatus": raiderio.get("sourceStatus") or ""},
            {"sourceKey": "warcraftlogs", "sourceName": "Warcraft Logs", "sourceStatus": ((talents.get("sources") or {}).get("warcraftlogs") or {}).get("status") or ""},
            {"sourceKey": "simc", "sourceName": "SimulationCraft", "sourceStatus": "source_reference"},
        ],
        "errors": errors,
    }
    record_sync_run(conn, payload)
    return payload


def main():
    mode = os.environ.get("WOW_COMMUNITY_TEMPLATE_SYNC_MODE", "scheduled").strip() or "scheduled"
    with connect_db() as conn:
        payload = sync_community_template_cache(conn, mode=mode)
        conn.commit()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
