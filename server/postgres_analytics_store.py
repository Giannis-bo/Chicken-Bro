#!/usr/bin/env python3
from contextlib import contextmanager
import json
import uuid
from datetime import datetime, timedelta, timezone

try:
    from .analytics import date_bounds, feature_group_for, normalize_event, parse_iso_datetime
except ImportError:
    from analytics import date_bounds, feature_group_for, normalize_event, parse_iso_datetime


ANALYTICS_NAMESPACE = uuid.UUID("27f2d9c4-1f6b-40f6-8c0f-4b9fbf62b055")


def json_param(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def analytics_uuid(kind, key):
    return str(uuid.uuid5(ANALYTICS_NAMESPACE, f"{kind}:{key}"))


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _actor_sql():
    return "COALESCE(user_id::text, anonymous_id)"


def _event_payload(event):
    return {
        "eventId": event["event_id"],
        "eventName": event["event_name"],
        "receivedAt": event["received_at"],
        "clientIdHash": event["client_id_hash"],
        "sessionIdHash": event["session_id_hash"],
        "platform": event["platform"],
        "page": event["page"],
        "properties": event["properties"],
    }


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _json_get(payload, *keys):
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current if current is not None else ""


class PostgresAnalyticsStore:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @contextmanager
    def connection(self):
        conn = self.connection_factory()
        try:
            yield conn
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise

    def record_events(self, payload, user_id=None, client_id="", session_id="", platform="miniprogram"):
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
        with self.connection() as conn:
            with conn.cursor() as cur:
                for raw_event in raw_events[:50]:
                    event = normalize_event(raw_event, defaults, received_at)
                    if not event:
                        ignored += 1
                        continue
                    cur.execute(
                        """
                        INSERT INTO analytics.events (
                            id, user_id, anonymous_id, event_name, payload_json, occurred_at
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            analytics_uuid("analytics.events", event["event_id"]),
                            user_id,
                            event["client_id_hash"],
                            event["event_name"],
                            json_param(_event_payload(event)),
                            event["occurred_at"],
                        ),
                    )
                    if getattr(cur, "rowcount", 0):
                        inserted += 1
                    else:
                        ignored += 1
                    if user_id:
                        cur.execute(
                            """
                            INSERT INTO analytics.user_links (id, user_id, anonymous_id, linked_at)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (user_id, anonymous_id) DO UPDATE SET
                                linked_at = EXCLUDED.linked_at
                            """,
                            (
                                analytics_uuid("analytics.user_links", f"{user_id}:{event['client_id_hash']}"),
                                user_id,
                                event["client_id_hash"],
                                event["received_at"],
                            ),
                        )
        return {"ok": True, "inserted": inserted, "ignored": ignored}

    def analytics_summary(self, query):
        start, end, date_from, date_to = date_bounds(query)
        actor = _actor_sql()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END),
                        COUNT(DISTINCT CASE WHEN event_name = 'page_view' THEN {actor} END),
                        COUNT(DISTINCT CASE WHEN event_name = 'page_view' AND user_id IS NOT NULL THEN user_id END),
                        COUNT(DISTINCT CASE WHEN event_name = 'page_view' AND user_id IS NULL THEN anonymous_id END),
                        COUNT(DISTINCT payload_json->>'sessionIdHash'),
                        COUNT(DISTINCT {actor})
                    FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s
                    """,
                    (start, end),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0, 0)
                cur.execute(
                    """
                    SELECT event_name, COUNT(*) FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s
                      AND event_name NOT IN ('page_view', 'page_leave')
                    GROUP BY event_name
                    ORDER BY COUNT(*) DESC
                    LIMIT 20
                    """,
                    (start, end),
                )
                features = cur.fetchall()
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

    def analytics_pages(self, query):
        start, end, date_from, date_to = date_bounds(query)
        actor = _actor_sql()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(payload_json->>'page', ''), COUNT(*), COUNT(DISTINCT {actor})
                    FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s AND event_name = 'page_view'
                    GROUP BY COALESCE(payload_json->>'page', '')
                    ORDER BY COUNT(*) DESC
                    LIMIT 50
                    """,
                    (start, end),
                )
                rows = cur.fetchall()
                cur.execute(
                    f"""
                    SELECT to_char(occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD'), COUNT(*), COUNT(DISTINCT {actor})
                    FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s AND event_name = 'page_view'
                    GROUP BY to_char(occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                    ORDER BY to_char(occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                    """,
                    (start, end),
                )
                trend = cur.fetchall()
        return {
            "range": {"from": date_from, "to": date_to},
            "pages": [{"page": page or "(unknown)", "pv": pv, "uv": uv} for page, pv, uv in rows],
            "trend": [{"date": date, "pv": pv, "uv": uv} for date, pv, uv in trend],
        }

    def analytics_features(self, query):
        start, end, date_from, date_to = date_bounds(query)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_name, COUNT(*)
                    FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s
                      AND event_name NOT IN ('page_view', 'page_leave')
                    GROUP BY event_name
                    ORDER BY COUNT(*) DESC
                    """,
                    (start, end),
                )
                rows = cur.fetchall()
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

    def analytics_simulator(self, query):
        start, end, date_from, date_to = date_bounds(query)
        mode_filter = str((query.get("mode") or [""])[0] or "").strip()
        spec_filter = str((query.get("specId") or [""])[0] or "").strip()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mode, status, request_json, analysis_json, summary_json, created_at
                    FROM app.simulator_tasks
                    WHERE created_at >= %s AND created_at < %s
                    ORDER BY created_at DESC
                    LIMIT 1000
                    """,
                    (start, end),
                )
                task_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT event_name, COUNT(*)
                    FROM analytics.events
                    WHERE occurred_at >= %s AND occurred_at < %s
                      AND (event_name LIKE 'simc_%%' OR event_name LIKE 'wcl_%%' OR event_name LIKE 'websim_%%')
                    GROUP BY event_name
                    ORDER BY COUNT(*) DESC
                    """,
                    (start, end),
                )
                event_rows = cur.fetchall()

        tasks = []
        by_spec = {}
        by_mode = {}
        completed = 0
        failed = 0
        for mode, status, request_json, analysis_json, summary_json, created_at in task_rows:
            request = _json_value(request_json, {})
            analysis = _json_value(analysis_json, {})
            summary = _json_value(summary_json, {})
            summary_build = summary.get("build") if isinstance(summary.get("build"), dict) else {}
            request_context = request.get("buildContext") if isinstance(request.get("buildContext"), dict) else {}
            analysis_request = analysis.get("request") if isinstance(analysis.get("request"), dict) else {}
            analysis_context = analysis_request.get("buildContext") if isinstance(analysis_request.get("buildContext"), dict) else {}
            context = summary_build or analysis_context or request_context or {}
            spec_id = str(
                context.get("specId")
                or _json_get(analysis_request, "scenario", "specKey")
                or _json_get(summary, "scenario", "specKey")
                or ""
            )
            profile_source = str(
                summary.get("profileSource")
                or analysis_request.get("profileSource")
                or request.get("profileSource")
                or ""
            )
            summary_simulation = summary.get("simulation") if isinstance(summary.get("simulation"), dict) else {}
            analysis_simulation = analysis.get("simulation") if isinstance(analysis.get("simulation"), dict) else {}
            simulation = summary_simulation or analysis_simulation
            summary_agent = summary.get("agent") if isinstance(summary.get("agent"), dict) else {}
            analysis_agent = analysis.get("agent") if isinstance(analysis.get("agent"), dict) else {}
            agent = summary_agent or analysis_agent
            ran = bool(simulation.get("ran"))
            metrics = simulation.get("metrics") if isinstance(simulation.get("metrics"), dict) else {}
            dps = metrics.get("dps") or ""
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
                    "dps": dps,
                    "createdAt": str(created_at or ""),
                }
            )
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

    def analytics_events(self, query):
        start, end, date_from, date_to = date_bounds(query)
        filters = ["occurred_at >= %s AND occurred_at < %s"]
        params = [start, end]
        event_name = str((query.get("eventName") or [""])[0] or "").strip()
        page = str((query.get("page") or [""])[0] or "").strip()
        user_id = str((query.get("userId") or [""])[0] or "").strip()
        if event_name:
            filters.append("event_name = %s")
            params.append(event_name)
        if page:
            filters.append("payload_json->>'page' = %s")
            params.append(page)
        if user_id:
            filters.append("user_id = %s")
            params.append(user_id)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, event_name, occurred_at, user_id, anonymous_id, payload_json
                    FROM analytics.events
                    WHERE {' AND '.join(filters)}
                    ORDER BY occurred_at DESC
                    LIMIT 200
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        events = []
        for row in rows:
            payload = _json_value(row[5], {})
            events.append(
                {
                    "eventId": payload.get("eventId") or str(row[0]),
                    "eventName": row[1],
                    "occurredAt": str(row[2] or ""),
                    "userId": str(row[3] or ""),
                    "openidMasked": "",
                    "nickname": "",
                    "clientHash": str(row[4] or "")[:12],
                    "sessionHash": str(payload.get("sessionIdHash") or "")[:12],
                    "platform": payload.get("platform") or "",
                    "page": payload.get("page") or "",
                    "properties": payload.get("properties") if isinstance(payload.get("properties"), dict) else {},
                }
            )
        return {"range": {"from": date_from, "to": date_to}, "events": events}

    def analytics_users(self, query):
        start, end, date_from, date_to = date_bounds(query)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.user_id, u.display_name, COUNT(*), MAX(e.occurred_at),
                           COUNT(DISTINCT e.payload_json->>'sessionIdHash')
                    FROM analytics.events e
                    LEFT JOIN identity.users u ON u.id = e.user_id
                    WHERE e.occurred_at >= %s AND e.occurred_at < %s AND e.user_id IS NOT NULL
                    GROUP BY e.user_id, u.display_name
                    ORDER BY MAX(e.occurred_at) DESC
                    LIMIT 100
                    """,
                    (start, end),
                )
                rows = cur.fetchall()
        return {
            "range": {"from": date_from, "to": date_to},
            "users": [
                {
                    "userId": str(row[0]),
                    "openidMasked": "",
                    "nickname": row[1] or "",
                    "avatarUrl": "",
                    "eventCount": row[2],
                    "lastSeenAt": str(row[3] or ""),
                    "sessions": row[4],
                }
                for row in rows
            ],
        }

    def rollup_daily_metrics(self, date_value):
        metric_date = str(date_value or datetime.now(timezone.utc).date().isoformat())[:10]
        start = f"{metric_date}T00:00:00+00:00"
        end = (parse_iso_datetime(start) + timedelta(days=1)).isoformat(timespec="seconds")
        actor = _actor_sql()
        updated_at = utc_now()
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT 'pv', SUM(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END)
                    FROM analytics.events WHERE occurred_at >= %s AND occurred_at < %s
                    UNION ALL
                    SELECT 'uv', COUNT(DISTINCT CASE WHEN event_name = 'page_view' THEN {actor} END)
                    FROM analytics.events WHERE occurred_at >= %s AND occurred_at < %s
                    """,
                    (start, end, start, end),
                )
                metrics = cur.fetchall()
                for metric_key, value in metrics:
                    cur.execute(
                        """
                        INSERT INTO analytics.daily_metrics (
                            metric_date, metric_key, dimensions_json, value, updated_at
                        ) VALUES (%s, %s, '{}'::jsonb, %s, %s)
                        ON CONFLICT (metric_date, metric_key, dimensions_json) DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (metric_date, metric_key, int(value or 0), updated_at),
                    )
        return {"ok": True, "date": metric_date, "metrics": len(metrics)}
