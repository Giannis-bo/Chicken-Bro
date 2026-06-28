import unittest


def minimal_plan():
    return {
        "schemaRevision": "postgres-data-copy-plan-v1",
        "tables": {
            "identity.users": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "display_name": "Mage",
                    "status": "active",
                    "created_at": "2026-06-27T12:00:00+00:00",
                    "updated_at": "2026-06-27T12:00:00+00:00",
                }
            ],
            "identity.user_identities": [
                {
                    "id": "22222222-2222-4222-8222-222222222222",
                    "user_id": "11111111-1111-4111-8111-111111111111",
                    "provider": "wechat_openid",
                    "provider_subject": "openid-shadow",
                    "profile_json": {"nickname": "Mage"},
                    "created_at": "2026-06-27T12:00:00+00:00",
                    "updated_at": "2026-06-27T12:00:00+00:00",
                }
            ],
            "app.simulator_tasks": [
                {
                    "id": "33333333-3333-4333-8333-333333333333",
                    "user_id": "11111111-1111-4111-8111-111111111111",
                    "mode": "simcraft_template",
                    "status": "queued",
                    "request_json": {"snapshot": {"templateId": "template-a"}},
                    "analysis_json": {},
                    "summary_json": {"state": "queued"},
                    "queued_at": "2026-06-27T12:00:00+00:00",
                    "started_at": None,
                    "finished_at": None,
                    "attempt": 0,
                    "locked_by": "",
                    "heartbeat_at": None,
                    "cancel_requested": False,
                    "last_error": "",
                    "created_at": "2026-06-27T12:00:00+00:00",
                    "updated_at": "2026-06-27T12:00:00+00:00",
                }
            ],
            "content.sources": [
                {
                    "id": "44444444-4444-4444-8444-444444444444",
                    "source_key": "blizzard",
                    "name": "Blizzard News",
                    "url": "https://worldofwarcraft.blizzard.com/news",
                    "source_type": "rss",
                    "status": "active",
                    "metadata_json": {"licenseStatus": "approved"},
                    "created_at": "2026-06-27T12:00:00+00:00",
                    "updated_at": "2026-06-27T12:00:00+00:00",
                }
            ],
            "content.refresh_runs": [
                {
                    "id": 3,
                    "refresh_mode": "scheduled",
                    "refreshed_at": "2026-06-27T12:00:00+00:00",
                    "accepted_count": 1,
                    "rejected_count": 0,
                    "message_json": {"publishedCount": 1},
                    "created_at": "2026-06-27T12:00:00+00:00",
                }
            ],
            "cache.raiderio_cache": [
                {
                    "cache_key": "raiderio:season",
                    "payload_json": {"sourceStatus": "verified"},
                    "fetched_at": "2026-06-27T12:00:00+00:00",
                    "expires_at": "2026-06-27T18:00:00+00:00",
                }
            ],
        },
        "totals": {"rowsByTable": {"identity.users": 1, "identity.user_identities": 1, "app.simulator_tasks": 1}},
        "skipped": {"guestUsers": [], "guestOwnedRows": 0, "authTokens": 0},
        "errors": [],
    }


class FakeCursor:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.statements = []
        self.params = []
        self._last_count = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append(" ".join(sql.split()))
        self.params.append(tuple(params or ()))
        if sql.lstrip().upper().startswith("SELECT COUNT(*) FROM"):
            table = sql.split("FROM", 1)[1].split("WHERE", 1)[0].strip()
            expected = len(params or ())
            self._last_count = self.counts.get(table, expected)

    def fetchone(self):
        return (self._last_count,)


class FakeConnection:
    def __init__(self, counts=None):
        self.cursor_instance = FakeCursor(counts=counts)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PostgresShadowMigrationTest(unittest.TestCase):
    def test_production_database_name_is_blocked_without_explicit_approval(self):
        from server.migrations.postgres import shadow_migrate

        with self.assertRaises(shadow_migrate.ProductionMigrationBlocked):
            shadow_migrate.ensure_dsn_allowed("postgresql://wow_migrator@localhost/wow_prod")
        with self.assertRaises(shadow_migrate.ProductionMigrationBlocked):
            shadow_migrate.ensure_dsn_allowed("dbname=wow_prod user=wow_migrator")

    def test_copy_plan_inserts_ordered_rows_and_verifies_target_counts(self):
        from server.migrations.postgres import shadow_migrate

        conn = FakeConnection()
        result = shadow_migrate.execute_copy_plan(conn, minimal_plan(), source_sqlite_path="local.sqlite3")

        statements = conn.cursor_instance.statements
        insert_statements = [item for item in statements if item.startswith("INSERT INTO")]
        self.assertTrue(insert_statements[0].startswith("INSERT INTO identity.users"))
        self.assertTrue(insert_statements[1].startswith("INSERT INTO identity.user_identities"))
        self.assertTrue(insert_statements[2].startswith("INSERT INTO app.simulator_tasks"))
        self.assertTrue(all("ON CONFLICT (id) DO NOTHING" in item for item in insert_statements[:3]))
        self.assertTrue(any("INSERT INTO content.sources" in item and "ON CONFLICT (source_key) DO NOTHING" in item for item in insert_statements))
        self.assertTrue(any("INSERT INTO cache.raiderio_cache" in item and "ON CONFLICT (cache_key) DO NOTHING" in item for item in insert_statements))
        self.assertTrue(any("SELECT COUNT(*) FROM identity.users" in item for item in statements))
        self.assertTrue(any("SELECT COUNT(*) FROM app.simulator_tasks" in item for item in statements))
        self.assertTrue(
            any(
                "setval" in item and "pg_get_serial_sequence('content.refresh_runs', 'id')" in item
                for item in statements
            )
        )
        self.assertEqual(result["verifiedRows"], 6)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)

    def test_copy_plan_rolls_back_when_target_counts_do_not_match(self):
        from server.migrations.postgres import shadow_migrate

        conn = FakeConnection(counts={"app.simulator_tasks": 0})

        with self.assertRaises(shadow_migrate.CountMismatch):
            shadow_migrate.execute_copy_plan(conn, minimal_plan(), source_sqlite_path="local.sqlite3")

        self.assertFalse(conn.committed)
        self.assertTrue(conn.rolled_back)

    def test_reconcile_public_cache_upserts_content_and_cache_without_overwriting_personal_assets(self):
        from server.migrations.postgres import shadow_migrate

        conn = FakeConnection()
        result = shadow_migrate.execute_copy_plan(
            conn,
            minimal_plan(),
            source_sqlite_path="fresh.sqlite3",
            reconcile_public_cache=True,
        )

        statements = conn.cursor_instance.statements
        insert_statements = [item for item in statements if item.startswith("INSERT INTO")]
        self.assertTrue(all("ON CONFLICT (id) DO NOTHING" in item for item in insert_statements[:3]))
        self.assertTrue(
            any(
                "INSERT INTO content.sources" in item
                and "ON CONFLICT (source_key) DO UPDATE SET" in item
                and "metadata_json = EXCLUDED.metadata_json" in item
                for item in insert_statements
            )
        )
        self.assertTrue(
            any(
                "INSERT INTO cache.raiderio_cache" in item
                and "ON CONFLICT (cache_key) DO UPDATE SET" in item
                and "payload_json = EXCLUDED.payload_json" in item
                for item in insert_statements
            )
        )
        self.assertEqual(result["verifiedRows"], 6)
        self.assertEqual(result["reconcileMode"], "public_cache")
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)


if __name__ == "__main__":
    unittest.main()
