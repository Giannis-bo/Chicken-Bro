import json
import unittest


class FakeCursor:
    def __init__(self, rows=None, rowcounts=None, fetchall_results=None):
        self.rows = list(rows or [])
        self.rowcounts = list(rowcounts or [])
        self.fetchall_results = [list(result) for result in (fetchall_results or [])]
        self.rowcount = 0
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append(" ".join(sql.split()))
        self.params.append(tuple(params or ()))
        self.rowcount = self.rowcounts.pop(0) if self.rowcounts else 1

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self):
        if self.fetchall_results:
            return self.fetchall_results.pop(0)
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, rows=None, rowcounts=None, fetchall_results=None):
        self.cursor_instance = FakeCursor(rows=rows, rowcounts=rowcounts, fetchall_results=fetchall_results)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PostgresAnalyticsStoreTest(unittest.TestCase):
    def test_record_events_uses_jsonb_payload_hashes_and_user_links(self):
        from server.postgres_analytics_store import PostgresAnalyticsStore

        conn = FakeConnection(rowcounts=[1, 1, 0, 1])
        store = PostgresAnalyticsStore(lambda: conn)

        result = store.record_events(
            {
                "events": [
                    {
                        "eventId": "evt-pg-analytics-1",
                        "eventName": "page_view",
                        "occurredAt": "2026-06-12T01:00:00+00:00",
                        "page": "pages/news/news",
                        "properties": {
                            "source": "tab",
                            "prompt": "should not be stored",
                            "openid": "openid-sensitive",
                        },
                    },
                    {
                        "eventId": "evt-pg-analytics-1",
                        "eventName": "page_view",
                        "occurredAt": "2026-06-12T01:00:01+00:00",
                        "page": "pages/news/news",
                    },
                ]
            },
            user_id="11111111-1111-4111-8111-111111111111",
            client_id="client-a",
            session_id="session-a",
            platform="miniprogram",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        params_json = json.dumps(conn.cursor_instance.params, ensure_ascii=False)
        self.assertEqual(result, {"ok": True, "inserted": 1, "ignored": 1})
        self.assertIn("INSERT INTO analytics.events", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertIn("payload_json", sql)
        self.assertIn("INSERT INTO analytics.user_links", sql)
        self.assertIn("ON CONFLICT (user_id, anonymous_id) DO UPDATE", sql)
        self.assertNotIn("should not be stored", params_json)
        self.assertNotIn("openid-sensitive", params_json)
        self.assertIn("clientIdHash", params_json)
        self.assertIn("sessionIdHash", params_json)

    def test_summary_pages_features_events_and_users_read_jsonb_payload(self):
        from server.postgres_analytics_store import PostgresAnalyticsStore

        rows = [
            (2, 1, 1, 0, 1, 1),
            ("simc_task_saved", 1),
        ]
        conn = FakeConnection(rows=rows)
        store = PostgresAnalyticsStore(lambda: conn)

        summary = store.analytics_summary({"from": ["2026-06-12"], "to": ["2026-06-12"]})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(summary["summary"]["pv"], 2)
        self.assertEqual(summary["topEvents"][0]["eventName"], "simc_task_saved")
        self.assertIn("FROM analytics.events", sql)
        self.assertIn("payload_json->>'sessionIdHash'", sql)
        self.assertIn("COALESCE(user_id::text, anonymous_id)", sql)

    def test_simulator_report_reads_app_tasks_snapshots_and_event_jsonb(self):
        from server.postgres_analytics_store import PostgresAnalyticsStore

        task_rows = [
            (
                "simcraft_agent",
                "completed",
                {"buildContext": {"specId": "arcane"}},
                {
                    "request": {
                        "buildContext": {"specId": "arcane"},
                        "profileSource": "profile-raw",
                    },
                    "simulation": {"ran": True, "metrics": {"dps": 123456}},
                    "agent": {"status": "completed"},
                },
                {
                    "state": "completed",
                    "build": {"specId": "arcane"},
                    "profileSource": "summary-profile",
                    "simulation": {"ran": True, "metrics": {"dps": 123456}},
                    "agent": {"status": "completed"},
                },
                "2026-06-12T01:00:00+00:00",
            ),
            (
                "websim",
                "failed",
                {},
                {"simulation": {"error": "boom"}, "agent": {"status": "sim_failed"}},
                {"build": {"specId": "frost"}},
                "2026-06-12T02:00:00+00:00",
            ),
        ]
        event_rows = [("simc_task_saved", 2), ("websim_run", 1)]
        conn = FakeConnection(fetchall_results=[task_rows, event_rows])
        store = PostgresAnalyticsStore(lambda: conn)

        report = store.analytics_simulator({"from": ["2026-06-12"], "to": ["2026-06-12"], "specId": ["arcane"]})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(report["summary"]["taskCount"], 1)
        self.assertEqual(report["summary"]["completedSimulations"], 1)
        self.assertEqual(report["tasks"][0]["specId"], "arcane")
        self.assertEqual(report["tasks"][0]["profileSource"], "summary-profile")
        self.assertEqual(report["events"][0], {"eventName": "simc_task_saved", "count": 2})
        self.assertIn("FROM app.simulator_tasks", sql)
        self.assertIn("summary_json", sql)
        self.assertIn("FROM analytics.events", sql)
        self.assertIn("event_name LIKE 'simc_%%'", sql)


if __name__ == "__main__":
    unittest.main()
