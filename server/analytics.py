import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone


EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
MAX_EVENTS_PER_BATCH = 50
MAX_PROPERTY_TEXT_LENGTH = 240
SENSITIVE_PROPERTY_KEYS = {
    "accessToken",
    "authorization",
    "code",
    "draftProfile",
    "message",
    "openid",
    "profile",
    "prompt",
    "rawProfile",
    "sessionKey",
    "simcProfile",
    "token",
    "unionid",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_analytics_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_events (
            event_id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            user_id INTEGER,
            client_id_hash TEXT NOT NULL,
            session_id_hash TEXT NOT NULL,
            platform TEXT NOT NULL,
            page TEXT NOT NULL,
            properties_json TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES wechat_users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_user_links (
            client_id_hash TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY(client_id_hash, user_id),
            FOREIGN KEY(user_id) REFERENCES wechat_users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_daily_metrics (
            metric_date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_key TEXT NOT NULL DEFAULT '',
            value INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(metric_date, metric_name, metric_key)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_occurred ON analytics_events(occurred_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_name_time ON analytics_events(event_name, occurred_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_user_time ON analytics_events(user_id, occurred_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_client_time ON analytics_events(client_id_hash, occurred_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_page_time ON analytics_events(page, occurred_at)")


def analytics_hash(value):
    text = str(value or "").strip()
    if not text:
        return ""
    salt = os.environ.get("WOW_ANALYTICS_HASH_SALT", "wow-analytics")
    return hashlib.sha256(f"{salt}:{text}".encode("utf-8")).hexdigest()


def parse_iso_datetime(value, fallback=None):
    if not value:
        return fallback or datetime.now(timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return fallback or datetime.now(timezone.utc)


def date_bounds(query):
    today = datetime.now(timezone.utc).date()
    date_from = str((query.get("from") or [""])[0] or "").strip()
    date_to = str((query.get("to") or [""])[0] or "").strip()
    if not date_to:
        date_to = today.isoformat()
    if not date_from:
        date_from = (today - timedelta(days=6)).isoformat()
    start = parse_iso_datetime(f"{date_from}T00:00:00+00:00")
    end = parse_iso_datetime(f"{date_to}T00:00:00+00:00") + timedelta(days=1)
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), date_from, date_to


def masked_openid(openid):
    value = str(openid or "")
    if not value:
        return ""
    if value.startswith("guest-simulator-"):
        return "guest-simulator-***"
    if len(value) <= 8:
        return f"{value[:2]}***"
    return f"{value[:4]}***{value[-4:]}"


def sanitize_property_value(value, depth=0):
    if depth > 4:
        return ""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_PROPERTY_TEXT_LENGTH]
    if isinstance(value, list):
        return [sanitize_property_value(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return sanitize_properties(value, depth + 1)
    return str(value)[:MAX_PROPERTY_TEXT_LENGTH]


def sanitize_properties(properties, depth=0):
    if not isinstance(properties, dict):
        return {}
    sanitized = {}
    for key, value in properties.items():
        name = str(key or "")[:80]
        if not name or name in SENSITIVE_PROPERTY_KEYS:
            continue
        sanitized[name] = sanitize_property_value(value, depth)
        if len(sanitized) >= 40:
            break
    return sanitized


def normalize_event(raw_event, defaults, received_at):
    if not isinstance(raw_event, dict):
        return None
    event_name = str(raw_event.get("eventName") or raw_event.get("name") or "").strip()
    if not EVENT_NAME_RE.match(event_name):
        return None
    event_id = str(raw_event.get("eventId") or raw_event.get("id") or "").strip()[:96] or uuid.uuid4().hex
    occurred_at = parse_iso_datetime(raw_event.get("occurredAt"), fallback=received_at).isoformat(timespec="seconds")
    page = str(raw_event.get("page") or defaults.get("page") or "").strip()[:160]
    platform = str(raw_event.get("platform") or defaults.get("platform") or "miniprogram").strip()[:40]
    client_hash = analytics_hash(raw_event.get("clientId") or defaults.get("clientId"))
    session_hash = analytics_hash(raw_event.get("sessionId") or defaults.get("sessionId") or defaults.get("clientId"))
    if not client_hash:
        return None
    return {
        "event_id": event_id,
        "event_name": event_name,
        "occurred_at": occurred_at,
        "received_at": received_at.isoformat(timespec="seconds"),
        "user_id": defaults.get("userId"),
        "client_id_hash": client_hash,
        "session_id_hash": session_hash or client_hash,
        "platform": platform,
        "page": page,
        "properties": sanitize_properties(raw_event.get("properties") or {}),
    }


def record_events(conn, payload, user_id=None, client_id="", session_id="", platform="miniprogram"):
    ensure_analytics_tables(conn)
    received_at = datetime.now(timezone.utc)
    raw_events = payload.get("events") if isinstance(payload, dict) else None
    if raw_events is None and isinstance(payload, dict):
        raw_events = [payload]
    if not isinstance(raw_events, list):
        raw_events = []
    defaults = {
        "clientId": client_id or (payload.get("clientId") if isinstance(payload, dict) else ""),
        "sessionId": session_id or (payload.get("sessionId") if isinstance(payload, dict) else ""),
        "platform": platform or (payload.get("platform") if isinstance(payload, dict) else "") or "miniprogram",
        "page": payload.get("page") if isinstance(payload, dict) else "",
        "userId": user_id,
    }
    inserted = 0
    ignored = 0
    for raw_event in raw_events[:MAX_EVENTS_PER_BATCH]:
        event = normalize_event(raw_event, defaults, received_at)
        if not event:
            ignored += 1
            continue
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO analytics_events (
                event_id, event_name, occurred_at, received_at, user_id,
                client_id_hash, session_id_hash, platform, page, properties_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["event_name"],
                event["occurred_at"],
                event["received_at"],
                event["user_id"],
                event["client_id_hash"],
                event["session_id_hash"],
                event["platform"],
                event["page"],
                json.dumps(event["properties"], ensure_ascii=False, sort_keys=True),
            ),
        )
        if cursor.rowcount:
            inserted += 1
        else:
            ignored += 1
        if user_id:
            conn.execute(
                """
                INSERT INTO analytics_user_links (client_id_hash, user_id, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id_hash, user_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at
                """,
                (event["client_id_hash"], user_id, event["received_at"], event["received_at"]),
            )
    return {"ok": True, "inserted": inserted, "ignored": ignored}


def unique_actor_sql():
    return "COALESCE(CAST(user_id AS TEXT), client_id_hash)"


def analytics_summary(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    actor = unique_actor_sql()
    row = conn.execute(
        f"""
        SELECT
            SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END),
            COUNT(DISTINCT CASE WHEN event_name = 'page_view' THEN {actor} END),
            COUNT(DISTINCT CASE WHEN event_name = 'page_view' AND user_id IS NOT NULL THEN user_id END),
            COUNT(DISTINCT CASE WHEN event_name = 'page_view' AND user_id IS NULL THEN client_id_hash END),
            COUNT(DISTINCT session_id_hash),
            COUNT(DISTINCT {actor})
        FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ?
        """,
        (start, end),
    ).fetchone()
    features = conn.execute(
        """
        SELECT event_name, COUNT(*) FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ?
          AND event_name NOT IN ('page_view', 'page_leave')
        GROUP BY event_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
        """,
        (start, end),
    ).fetchall()
    return {
        "range": {"from": date_from, "to": date_to},
        "summary": {
            "pv": int(row[0] or 0),
            "uv": int(row[1] or 0),
            "loginUv": int(row[2] or 0),
            "guestUv": int(row[3] or 0),
            "sessions": int(row[4] or 0),
            "activeUsers": int(row[5] or 0),
        },
        "topEvents": [{"eventName": name, "count": count} for name, count in features],
    }


def analytics_pages(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    actor = unique_actor_sql()
    rows = conn.execute(
        f"""
        SELECT page, COUNT(*), COUNT(DISTINCT {actor})
        FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ? AND event_name = 'page_view'
        GROUP BY page
        ORDER BY COUNT(*) DESC
        LIMIT 50
        """,
        (start, end),
    ).fetchall()
    trend = conn.execute(
        f"""
        SELECT substr(occurred_at, 1, 10), COUNT(*), COUNT(DISTINCT {actor})
        FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ? AND event_name = 'page_view'
        GROUP BY substr(occurred_at, 1, 10)
        ORDER BY substr(occurred_at, 1, 10)
        """,
        (start, end),
    ).fetchall()
    return {
        "range": {"from": date_from, "to": date_to},
        "pages": [{"page": page or "(unknown)", "pv": pv, "uv": uv} for page, pv, uv in rows],
        "trend": [{"date": date, "pv": pv, "uv": uv} for date, pv, uv in trend],
    }


FEATURE_GROUPS = {
    "news": ("news_",),
    "builds": ("builds_",),
    "pve": ("pve_",),
    "simc": ("simc_", "simulator_", "task_"),
    "wcl": ("wcl_",),
    "websim": ("websim_",),
}


def feature_group_for(event_name):
    for group, prefixes in FEATURE_GROUPS.items():
        if any(event_name.startswith(prefix) for prefix in prefixes):
            return group
    return "other"


def analytics_features(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    rows = conn.execute(
        """
        SELECT event_name, COUNT(*)
        FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ?
          AND event_name NOT IN ('page_view', 'page_leave')
        GROUP BY event_name
        ORDER BY COUNT(*) DESC
        """,
        (start, end),
    ).fetchall()
    groups = {}
    events = []
    for event_name, count in rows:
        group = feature_group_for(event_name)
        groups[group] = groups.get(group, 0) + count
        events.append({"eventName": event_name, "group": group, "count": count})
    return {
        "range": {"from": date_from, "to": date_to},
        "groups": [{"group": group, "count": count} for group, count in sorted(groups.items())],
        "events": events,
    }


def safe_json(value):
    try:
        return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def json_get(payload, *keys):
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current if current is not None else ""


def analytics_simulator(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    mode_filter = str((query.get("mode") or [""])[0] or "").strip()
    spec_filter = str((query.get("specId") or [""])[0] or "").strip()
    task_rows = conn.execute(
        """
        SELECT mode, status, request_json, analysis_json, created_at
        FROM simulator_tasks
        WHERE created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
        LIMIT 1000
        """,
        (start, end),
    ).fetchall()
    tasks = []
    by_spec = {}
    by_mode = {}
    completed = 0
    failed = 0
    for mode, status, request_json, analysis_json, created_at in task_rows:
        request = safe_json(request_json)
        analysis = safe_json(analysis_json)
        request_context = request.get("buildContext") if isinstance(request.get("buildContext"), dict) else {}
        analysis_request = analysis.get("request") if isinstance(analysis.get("request"), dict) else {}
        analysis_context = analysis_request.get("buildContext") if isinstance(analysis_request.get("buildContext"), dict) else {}
        context = analysis_context or request_context or {}
        spec_id = str(context.get("specId") or json_get(analysis_request, "scenario", "specKey") or "")
        profile_source = str(analysis_request.get("profileSource") or request.get("profileSource") or "")
        simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
        agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
        ran = bool(simulation.get("ran"))
        dps = (simulation.get("metrics") or {}).get("dps") if isinstance(simulation.get("metrics"), dict) else ""
        agent_status = str(agent.get("status") or status or "")
        if mode_filter and mode != mode_filter:
            continue
        if spec_filter and spec_id != spec_filter:
            continue
        if ran and dps:
            completed += 1
        if simulation.get("error") or agent_status.endswith("failed"):
            failed += 1
        by_mode[mode] = by_mode.get(mode, 0) + 1
        if spec_id:
            by_spec[spec_id] = by_spec.get(spec_id, 0) + 1
        tasks.append(
            {
                "mode": mode,
                "status": status,
                "agentStatus": agent_status,
                "profileSource": profile_source,
                "specId": spec_id,
                "simulationRan": ran,
                "dps": dps or "",
                "createdAt": created_at,
            }
        )
    event_rows = conn.execute(
        """
        SELECT event_name, COUNT(*)
        FROM analytics_events
        WHERE occurred_at >= ? AND occurred_at < ?
          AND (event_name LIKE 'simc_%' OR event_name LIKE 'wcl_%' OR event_name LIKE 'websim_%')
        GROUP BY event_name
        ORDER BY COUNT(*) DESC
        """,
        (start, end),
    ).fetchall()
    return {
        "range": {"from": date_from, "to": date_to},
        "summary": {
            "taskCount": len(tasks),
            "completedSimulations": completed,
            "failedTasks": failed,
        },
        "byMode": [{"mode": key, "count": value} for key, value in sorted(by_mode.items())],
        "bySpec": [{"specId": key, "count": value} for key, value in sorted(by_spec.items(), key=lambda item: item[1], reverse=True)[:30]],
        "events": [{"eventName": name, "count": count} for name, count in event_rows],
        "tasks": tasks[:100],
    }


def analytics_events(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    filters = ["e.occurred_at >= ? AND e.occurred_at < ?"]
    params = [start, end]
    event_name = str((query.get("eventName") or [""])[0] or "").strip()
    page = str((query.get("page") or [""])[0] or "").strip()
    user_id = str((query.get("userId") or [""])[0] or "").strip()
    if event_name:
        filters.append("e.event_name = ?")
        params.append(event_name)
    if page:
        filters.append("e.page = ?")
        params.append(page)
    if user_id:
        filters.append("e.user_id = ?")
        params.append(user_id)
    rows = conn.execute(
        f"""
        SELECT e.event_id, e.event_name, e.occurred_at, e.user_id, u.openid, u.nickname,
               e.client_id_hash, e.session_id_hash, e.platform, e.page, e.properties_json
        FROM analytics_events e
        LEFT JOIN wechat_users u ON u.id = e.user_id
        WHERE {' AND '.join(filters)}
        ORDER BY e.occurred_at DESC
        LIMIT 200
        """,
        params,
    ).fetchall()
    return {
        "range": {"from": date_from, "to": date_to},
        "events": [
            {
                "eventId": row[0],
                "eventName": row[1],
                "occurredAt": row[2],
                "userId": row[3],
                "openidMasked": masked_openid(row[4]),
                "nickname": row[5] or "",
                "clientHash": row[6][:12],
                "sessionHash": row[7][:12],
                "platform": row[8],
                "page": row[9],
                "properties": safe_json(row[10]),
            }
            for row in rows
        ],
    }


def analytics_users(conn, query):
    ensure_analytics_tables(conn)
    start, end, date_from, date_to = date_bounds(query)
    rows = conn.execute(
        """
        SELECT e.user_id, u.openid, u.nickname, u.avatar_url, COUNT(*), MAX(e.occurred_at),
               COUNT(DISTINCT e.session_id_hash)
        FROM analytics_events e
        LEFT JOIN wechat_users u ON u.id = e.user_id
        WHERE e.occurred_at >= ? AND e.occurred_at < ? AND e.user_id IS NOT NULL
        GROUP BY e.user_id, u.openid, u.nickname, u.avatar_url
        ORDER BY MAX(e.occurred_at) DESC
        LIMIT 100
        """,
        (start, end),
    ).fetchall()
    return {
        "range": {"from": date_from, "to": date_to},
        "users": [
            {
                "userId": row[0],
                "openidMasked": masked_openid(row[1]),
                "nickname": row[2] or "",
                "avatarUrl": row[3] or "",
                "eventCount": row[4],
                "lastSeenAt": row[5],
                "sessions": row[6],
            }
            for row in rows
        ],
    }


def rollup_daily_metrics(conn, date_value):
    ensure_analytics_tables(conn)
    metric_date = str(date_value or datetime.now(timezone.utc).date().isoformat())[:10]
    start = f"{metric_date}T00:00:00+00:00"
    end = (parse_iso_datetime(start) + timedelta(days=1)).isoformat(timespec="seconds")
    actor = unique_actor_sql()
    metrics = conn.execute(
        f"""
        SELECT 'pv', '', SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END)
        FROM analytics_events WHERE occurred_at >= ? AND occurred_at < ?
        UNION ALL
        SELECT 'uv', '', COUNT(DISTINCT CASE WHEN event_name = 'page_view' THEN {actor} END)
        FROM analytics_events WHERE occurred_at >= ? AND occurred_at < ?
        UNION ALL
        SELECT 'event', event_name, COUNT(*)
        FROM analytics_events WHERE occurred_at >= ? AND occurred_at < ?
        GROUP BY event_name
        """,
        (start, end, start, end, start, end),
    ).fetchall()
    updated_at = utc_now()
    for metric_name, metric_key, value in metrics:
        conn.execute(
            """
            INSERT INTO analytics_daily_metrics (metric_date, metric_name, metric_key, value, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(metric_date, metric_name, metric_key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at
            """,
            (metric_date, metric_name, metric_key or "", int(value or 0), updated_at),
        )
    return {"ok": True, "date": metric_date, "metrics": len(metrics)}

