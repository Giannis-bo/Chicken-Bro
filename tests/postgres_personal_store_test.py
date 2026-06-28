import json
import unittest


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append(" ".join(sql.split()))
        self.params.append(tuple(params or ()))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows=rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PostgresPersonalStoreTest(unittest.TestCase):
    def test_upsert_wechat_user_writes_identity_and_provider_rows(self):
        from server.postgres_personal_store import PostgresPersonalStore

        row = (
            "user-pg-1",
            "openid-main",
            "union-main",
            "",
            "",
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T01:00:00+00:00",
        )
        conn = FakeConnection(rows=[row])
        store = PostgresPersonalStore(lambda: conn)

        user = store.upsert_wechat_user("openid-main", "union-main", now="2026-06-27T01:00:00+00:00")

        statements = conn.cursor_instance.statements
        self.assertTrue(any("INSERT INTO identity.users" in statement for statement in statements))
        self.assertTrue(any("INSERT INTO identity.user_identities" in statement for statement in statements))
        self.assertTrue(any("provider = 'wechat_openid'" in statement for statement in statements))
        self.assertEqual(user["id"], "user-pg-1")
        self.assertEqual(user["openid"], "openid-main")
        self.assertEqual(user["unionid"], "union-main")

    def test_auth_tokens_are_hashed_for_insert_and_lookup(self):
        from server.postgres_personal_store import PostgresPersonalStore, auth_token_hash

        token = "wow_plain_secret"
        expected_hash = auth_token_hash(token)
        rows = [
            (
                "user-pg-1",
                "openid-main",
                "union-main",
                "Mage",
                "avatar.png",
                "2026-06-27T00:00:00+00:00",
                "2026-06-27T01:00:00+00:00",
            )
        ]
        conn = FakeConnection(rows=rows)
        store = PostgresPersonalStore(lambda: conn)

        store.create_auth_token("user-pg-1", token, "2026-06-27T00:00:00+00:00", "2026-07-27T00:00:00+00:00")
        user = store.authenticate_token(token, now="2026-06-27T00:30:00+00:00")

        params = conn.cursor_instance.params
        self.assertIn(expected_hash, params[0])
        self.assertNotIn(token, json.dumps(params, ensure_ascii=False))
        self.assertIn("INSERT INTO identity.auth_tokens", conn.cursor_instance.statements[0])
        self.assertIn("WHERE t.token_hash = %s", conn.cursor_instance.statements[1])
        self.assertEqual(user["id"], "user-pg-1")
        self.assertEqual(user["openid"], "openid-main")

    def test_update_user_profile_casts_avatar_parameter_for_jsonb_build_object(self):
        from server.postgres_personal_store import PostgresPersonalStore

        row = (
            "user-pg-1",
            "openid-main",
            "",
            "Codex",
            "avatar.png",
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T01:00:00+00:00",
        )
        conn = FakeConnection(rows=[row])
        store = PostgresPersonalStore(lambda: conn)

        user = store.update_user_profile("user-pg-1", "Codex", "avatar.png", "2026-06-27T01:00:00+00:00")

        update_identity_sql = " ".join(conn.cursor_instance.statements[1].split())
        self.assertIn("jsonb_build_object('avatarUrl', %s::text)", update_identity_sql)
        self.assertEqual(user["nickname"], "Codex")

    def test_build_template_upsert_uses_config_hash_conflict_key(self):
        from server.postgres_personal_store import PostgresPersonalStore, build_template_config_hash

        normalized = {
            "client_id": "local-a",
            "template_type": "talent",
            "title": "Same visible name",
            "class_key": "mage",
            "class_name": "法师",
            "spec_key": "arcane",
            "spec_name": "奥术",
            "hero_key": "spellslinger",
            "hero_label": "急咒师",
            "scenario_key": "",
            "scenario_title": "",
            "raw_string": "websim:talent-a",
            "simc_lines_json": "[]",
            "status": "saved",
            "status_label": "已保存",
            "source": "local",
            "metadata_json": "{\"source\":\"test\"}",
            "schema_version": 1,
            "created_at": "2026-06-27T00:00:00+00:00",
            "updated_at": "2026-06-27T01:00:00+00:00",
        }
        expected_hash = build_template_config_hash("talent", "websim:talent-a")
        row = (
            "template-pg-1",
            "local-a",
            "talent",
            "Same visible name",
            "mage",
            "法师",
            "arcane",
            "奥术",
            "spellslinger",
            "急咒师",
            "",
            "",
            "websim:talent-a",
            [],
            "saved",
            "已保存",
            "local",
            {"source": "test"},
            1,
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T01:00:00+00:00",
        )
        conn = FakeConnection(rows=[row])
        store = PostgresPersonalStore(lambda: conn)

        template = store.save_build_template("user-pg-1", normalized)

        insert_sql = conn.cursor_instance.statements[0]
        self.assertIn("INSERT INTO app.build_templates", insert_sql)
        self.assertIn("ON CONFLICT (user_id, template_type, config_hash) DO UPDATE", insert_sql)
        self.assertIn(expected_hash, conn.cursor_instance.params[0])
        self.assertEqual(template["id"], "template-pg-1")
        self.assertEqual(template["rawString"], "websim:talent-a")
        self.assertEqual(template["metadata"], {"source": "test"})

    def test_simulator_task_insert_preserves_request_analysis_and_summary_jsonb(self):
        from server.postgres_personal_store import PostgresPersonalStore

        conn = FakeConnection()
        store = PostgresPersonalStore(lambda: conn)
        store.insert_simulator_task(
            {
                "id": "task-pg-1",
                "user_id": "user-pg-1",
                "mode": "simcraft_template",
                "status": "queued",
                "request_json": {"templateContext": {"talent": {"id": "talent-a"}}},
                "analysis_json": {"mode": "simcraft_template", "status": "queued"},
                "summary_json": {"state": "queued", "build": {"specName": "奥术"}},
                "queued_at": "2026-06-27T00:00:00+00:00",
                "created_at": "2026-06-27T00:00:00+00:00",
                "updated_at": "2026-06-27T00:00:00+00:00",
            }
        )

        sql = conn.cursor_instance.statements[0]
        self.assertIn("INSERT INTO app.simulator_tasks", sql)
        self.assertIn("%s::jsonb", sql)
        params = conn.cursor_instance.params[0]
        self.assertTrue(any('"state": "queued"' in str(param) for param in params))
        self.assertNotIn("guestId", json.dumps(params, ensure_ascii=False))

    def test_simcraft_template_runner_methods_use_postgres_task_table(self):
        from server.postgres_personal_store import PostgresPersonalStore

        row = (
            "task-pg-1",
            "user-pg-1",
            "simcraft_template",
            "queued",
            {"mode": "simcraft_template"},
            {"status": "queued"},
            "2026-06-28T00:00:00+00:00",
            "2026-06-28T00:00:00+00:00",
        )
        connections = [FakeConnection(rows=[row]), FakeConnection(), FakeConnection()]
        used = []

        def connection_factory():
            conn = connections.pop(0)
            used.append(conn)
            return conn

        store = PostgresPersonalStore(connection_factory)

        fetched = store.get_simcraft_template_task_for_runner("task-pg-1")
        store.mark_simcraft_template_task_running(
            "task-pg-1",
            {"status": "running"},
            {"state": "running"},
            "2026-06-28T00:01:00+00:00",
        )
        store.finish_simcraft_template_task(
            "task-pg-1",
            "completed",
            {"status": "completed"},
            {"state": "completed"},
            "2026-06-28T00:02:00+00:00",
        )

        self.assertEqual(fetched[0], "task-pg-1")
        sql = "\n".join(statement for conn in used for statement in conn.cursor_instance.statements)
        self.assertIn("FROM app.simulator_tasks", sql)
        self.assertIn("WHERE id = %s AND mode = 'simcraft_template'", sql)
        self.assertIn("SET status = 'running'", sql)
        self.assertIn("attempt = attempt + 1", sql)
        self.assertIn("SET status = %s", sql)
        self.assertIn("last_error = %s", sql)
        self.assertTrue(used[1].committed)
        self.assertTrue(used[2].committed)

    def test_chickenbro_user_profile_uses_user_context_summary(self):
        from server.postgres_personal_store import PostgresPersonalStore

        load_conn = FakeConnection(rows=[({"characters": [{"classKey": "mage"}]},)])
        upsert_conn = FakeConnection()
        connections = [load_conn, upsert_conn]
        store = PostgresPersonalStore(lambda: connections.pop(0))

        profile = store.load_chickenbro_user_profile("user-pg-1")
        store.upsert_chickenbro_user_profile(
            "user-pg-1",
            {"characters": [{"classKey": "mage", "specKey": "arcane"}]},
            now="2026-06-27T01:00:00+00:00",
        )

        self.assertEqual(profile["characters"][0]["classKey"], "mage")
        load_sql = load_conn.cursor_instance.statements[0]
        upsert_sql = upsert_conn.cursor_instance.statements[0]
        self.assertIn("FROM knowledge.user_context_summaries", load_sql)
        self.assertIn("context_type = %s", load_sql)
        self.assertIn("INSERT INTO knowledge.user_context_summaries", upsert_sql)
        self.assertIn("ON CONFLICT (user_id, context_type) DO UPDATE", upsert_sql)
        self.assertIn("chickenbro_user_profile", upsert_conn.cursor_instance.params[0])

    def test_chickenbro_session_message_and_job_methods_use_owner_bound_tables(self):
        from server.postgres_personal_store import PostgresPersonalStore

        session_id = "11111111-1111-4111-8111-111111111111"
        message_id = "22222222-2222-4222-8222-222222222222"
        job_id = "33333333-3333-4333-8333-333333333333"
        session_row = (
            session_id,
            "user-pg-1",
            "Arcane help",
            "active",
            {"productPhase": "retail", "metadata": {"source": "test"}},
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T01:00:00+00:00",
        )
        message_row = (
            message_id,
            session_id,
            "user-pg-1",
            "assistant",
            "Answer text",
            {"answer": "Answer text", "evidenceRefs": ["profile.summary"]},
            job_id,
            "2026-06-27T01:02:00+00:00",
        )
        job_row = (
            job_id,
            "user-pg-1",
            session_id,
            "chickenbro",
            "succeeded",
            {"message": "How should Arcane play?"},
            {"schemaRevision": "chickenbro-bounded-context-v1"},
            {"answer": {"answer": "Answer text"}},
            "",
            "2026-06-27T01:00:00+00:00",
            "2026-06-27T01:03:00+00:00",
            "2026-06-27T01:01:00+00:00",
            "2026-06-27T01:03:00+00:00",
        )
        connections = [
            FakeConnection(rows=[session_row]),
            FakeConnection(),
            FakeConnection(),
            FakeConnection(),
            FakeConnection(),
            FakeConnection(rows=[session_row, message_row]),
            FakeConnection(rows=[job_row]),
        ]
        used = []

        def connection_factory():
            conn = connections.pop(0)
            used.append(conn)
            return conn

        store = PostgresPersonalStore(connection_factory)

        session = store.create_chickenbro_session(
            "user-pg-1",
            "Arcane help",
            "retail",
            {"source": "test"},
            now="2026-06-27T00:00:00+00:00",
        )
        message = store.insert_chickenbro_message(
            "user-pg-1",
            session_id,
            "assistant",
            "Answer text",
            {"answer": "Answer text", "evidenceRefs": ["profile.summary"]},
            agent_job_id=job_id,
            now="2026-06-27T01:02:00+00:00",
        )
        created_job_id = store.insert_agent_job(
            "user-pg-1",
            session_id,
            {"message": "How should Arcane play?"},
            {"schemaRevision": "chickenbro-bounded-context-v1"},
            now="2026-06-27T01:00:00+00:00",
        )
        store.update_agent_job(
            "user-pg-1",
            job_id,
            "succeeded",
            result={"answer": {"answer": "Answer text"}},
            finished_at="2026-06-27T01:03:00+00:00",
            now="2026-06-27T01:03:00+00:00",
        )
        store.touch_chickenbro_session("user-pg-1", session_id, "2026-06-27T01:03:00+00:00")
        session_payload = store.get_chickenbro_session("user-pg-1", session_id)
        job = store.get_chickenbro_job("user-pg-1", job_id)

        self.assertEqual(session["sessionId"], session_id)
        self.assertEqual(session["productPhase"], "retail")
        self.assertEqual(message["agentJobId"], job_id)
        self.assertTrue(created_job_id)
        self.assertEqual(session_payload["messages"][0]["payload"]["evidenceRefs"], ["profile.summary"])
        self.assertEqual(job["boundedContext"]["schemaRevision"], "chickenbro-bounded-context-v1")

        sql = "\n".join(statement for conn in used for statement in conn.cursor_instance.statements)
        self.assertIn("INSERT INTO app.chickenbro_sessions", sql)
        self.assertIn("INSERT INTO app.chickenbro_messages", sql)
        self.assertIn("evidence_refs_json", sql)
        self.assertIn("agent_job_id", sql)
        self.assertIn("INSERT INTO app.agent_jobs", sql)
        self.assertIn("bounded_context_json", sql)
        self.assertIn("WHERE user_id = %s AND id = %s", sql)
        self.assertIn("WHERE user_id = %s AND id = %s AND job_type = 'chickenbro'", sql)


if __name__ == "__main__":
    unittest.main()
