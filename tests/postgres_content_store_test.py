import json
import unittest


class FakeCursor:
    def __init__(self, rows=None, rowcounts=None):
        self.rows = list(rows or [])
        self.rowcounts = list(rowcounts or [])
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
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, rows=None, rowcounts=None):
        self.cursor_instance = FakeCursor(rows=rows, rowcounts=rowcounts)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def valid_article():
    return {
        "id": "pg-news-1",
        "title": "Patch notes",
        "summary": "Summary",
        "channel": "retail",
        "category": "update",
        "tags": ["content-update"],
        "importance": 90,
        "sourceName": "Blizzard News",
        "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/123",
        "publishedAt": "2026-06-28T01:00:00+00:00",
        "sourceNote": "Official source",
        "bodyZh": "Translated full body",
        "originalTitle": "Patch Notes",
        "originalSummary": "Original summary",
        "originalBody": "Original body",
        "translationStatus": "llm",
        "contentStatus": "ready",
        "tagItems": [{"id": "content-update", "label": "Content update"}],
        "blockedReason": "",
        "sourceId": "blizzard",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "verificationStatus": "official_verified",
        "sourceBadges": ["official"],
        "bodyBlocksZh": [{"type": "paragraph", "text": "Translated full body"}],
        "canonicalTopicId": "news:123",
        "readingMeta": {"estimatedReadingMinutes": 1},
        "translationFidelity": "source_translation",
    }


class PostgresContentStoreTest(unittest.TestCase):
    def test_save_public_article_uses_content_schema_runtime_fields(self):
        from server.postgres_content_store import PostgresContentStore

        conn = FakeConnection()
        store = PostgresContentStore(lambda: conn)

        store.save_public_article(valid_article(), "2026-06-28T01:05:00+00:00")

        sql = "\n".join(conn.cursor_instance.statements)
        params_json = json.dumps(conn.cursor_instance.params, ensure_ascii=False)
        self.assertIn("INSERT INTO content.articles", sql)
        self.assertIn("content_status", sql)
        self.assertIn("tag_items_json", sql)
        self.assertIn("payload_json", sql)
        self.assertIn("%s::jsonb", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("source_translation", params_json)

    def test_list_and_detail_articles_read_jsonb_runtime_fields(self):
        from server.postgres_content_store import PostgresContentStore

        row = (
            "pg-news-1",
            "Patch notes",
            "Summary",
            "retail",
            "update",
            ["content-update"],
            90,
            "Blizzard News",
            "https://worldofwarcraft.blizzard.com/en-us/news/123",
            "2026-06-28T01:00:00+00:00",
            "Official source",
            "Translated full body",
            "Patch Notes",
            "llm",
            "ready",
            [{"id": "content-update", "label": "Content update"}],
            "",
            "blizzard",
            "official",
            "approved",
            "official_verified",
            ["official"],
            [{"type": "paragraph", "text": "Translated full body"}],
            "news:123",
            {"estimatedReadingMinutes": 1},
            "source_translation",
        )
        detail_conn = FakeConnection(rows=[row])
        connections = [FakeConnection(rows=[row]), detail_conn]
        store = PostgresContentStore(lambda: connections.pop(0))

        articles = store.load_articles()
        detail = store.get_article("pg-news-1")

        self.assertEqual(articles[0]["id"], "pg-news-1")
        self.assertEqual(articles[0]["tags"], ["content-update"])
        self.assertEqual(detail["tagItems"][0]["id"], "content-update")
        self.assertIn("FROM content.articles", detail_conn.cursor_instance.statements[0])

    def test_queue_and_refresh_runs_use_content_tables(self):
        from server.postgres_content_store import PostgresContentStore

        queue_conn = FakeConnection()
        run_conn = FakeConnection()
        state_conn = FakeConnection(rows=[("scheduled", "2026-06-28T01:05:00+00:00")])
        payload_conn = FakeConnection(
            rows=[
                (
                    "scheduled",
                    "2026-06-28T01:05:00+00:00",
                    1,
                    0,
                    {"processedCount": 1, "publishedCount": 1, "sourceCoverage": {}},
                )
            ]
        )
        connections = [queue_conn, run_conn, state_conn, payload_conn]
        store = PostgresContentStore(lambda: connections.pop(0))

        store.enqueue_discovered_articles([valid_article()], "2026-06-28T01:00:00+00:00")
        store.record_refresh_run(
            "scheduled",
            "2026-06-28T01:05:00+00:00",
            1,
            0,
            {"processedCount": 1, "publishedCount": 1, "sourceCoverage": {}},
        )
        state = store.latest_refresh_state()
        payload = store.latest_refresh_run_payload()

        self.assertIn("INSERT INTO content.discovery_queue", "\n".join(queue_conn.cursor_instance.statements))
        self.assertIn("INSERT INTO content.refresh_runs", run_conn.cursor_instance.statements[0])
        self.assertEqual(state["refreshMode"], "scheduled")
        self.assertEqual(payload["publishedCount"], 1)


if __name__ == "__main__":
    unittest.main()
