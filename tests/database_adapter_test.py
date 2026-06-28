import importlib
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DatabaseAdapterTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("WOW_DATABASE_URL", None)
        os.environ.pop("WOW_DATABASE_RUNTIME", None)
        os.environ.pop("WOW_NEWS_DB", None)

    def test_sqlite_is_default_backend(self):
        from server import db

        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("WOW_DATABASE_URL", None)
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "wow.sqlite3")

            config = db.database_config_from_env()

            self.assertEqual(config.backend, "sqlite")
            self.assertTrue(str(config.sqlite_path).endswith("wow.sqlite3"))
            self.assertEqual(config.database_url, "")

    def test_postgres_requires_explicit_database_url(self):
        from server import db

        os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"

        config = db.database_config_from_env()

        self.assertEqual(config.backend, "postgres")
        self.assertIn("wow_test", config.database_url)
        self.assertIsNone(config.sqlite_path)

    def test_sqlite_connection_enables_required_pragmas(self):
        from server import db

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pragma.sqlite3"
            with db.sqlite_connection(path) as conn:
                busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
                foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

        self.assertEqual(busy_timeout, 30000)
        self.assertEqual(foreign_keys, 1)
        self.assertEqual(journal_mode.lower(), "wal")

    def test_news_backend_rejects_postgres_runtime_until_cutover(self):
        import server.news_backend as backend

        os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"
        os.environ.pop("WOW_DATABASE_RUNTIME", None)
        backend = importlib.reload(backend)

        with self.assertRaisesRegex(RuntimeError, "PostgreSQL runtime is not enabled"):
            with backend.db_connection():
                pass

    def test_postgres_personal_runtime_keeps_sqlite_cache_connection_available(self):
        import server.news_backend as backend

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"
            os.environ["WOW_DATABASE_RUNTIME"] = "postgres_personal"
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "hybrid.sqlite3")
            backend = importlib.reload(backend)

            with backend.db_connection() as conn:
                foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

        self.assertEqual(foreign_keys, 1)

    def test_news_backend_db_connection_uses_sqlite_fallback(self):
        import server.news_backend as backend

        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("WOW_DATABASE_URL", None)
            os.environ.pop("WOW_DATABASE_RUNTIME", None)
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "news.sqlite3")
            backend = importlib.reload(backend)
            backend.init_db()

            with backend.db_connection() as conn:
                foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

        self.assertEqual(foreign_keys, 1)

    def test_news_backend_imports_as_direct_script_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("WOW_DATABASE_URL", None)
            env["WOW_NEWS_DB"] = str(Path(tmp) / "direct.sqlite3")
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.path.insert(0, 'server'); import news_backend; print(news_backend.DB_CONFIG.backend)",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sqlite")

    def test_news_backend_routes_identity_calls_to_postgres_personal_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def upsert_wechat_user(self, openid, unionid="", now=""):
                self.calls.append(("upsert", openid, unionid, now))
                return {
                    "id": "pg-user-1",
                    "openid": openid,
                    "unionid": unionid,
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def create_auth_token(self, user_id, token, issued_at, expires_at):
                self.calls.append(("token", user_id, token, issued_at, expires_at))
                return token

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            user = backend.upsert_wechat_user("openid-pg", "union-pg")
            token, expires_at = backend.create_auth_token(user["id"])
            authed = backend.authenticate_token(token)
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(user["id"], "pg-user-1")
        self.assertEqual(authed["id"], "pg-user-1")
        self.assertTrue(token.startswith("wow_"))
        self.assertTrue(expires_at)
        self.assertEqual([call[0] for call in fake.calls], ["upsert", "token", "auth"])

    def test_news_backend_routes_profile_update_to_postgres_personal_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def update_user_profile(self, user_id, nickname, avatar_url, now):
                self.calls.append(("profile", user_id, nickname, avatar_url, now))
                return {
                    "id": user_id,
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": nickname,
                    "avatarUrl": avatar_url,
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": now,
                }

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            user = backend.update_user_profile("token-pg", {"nickname": "Arcane", "avatarUrl": "avatar.png"})
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(user["nickname"], "Arcane")
        self.assertEqual(user["avatarUrl"], "avatar.png")
        self.assertEqual([call[0] for call in fake.calls], ["auth", "profile"])

    def test_news_backend_routes_build_template_crud_to_postgres_personal_store(self):
        import server.news_backend as backend

        template = {
            "id": "template-pg-1",
            "clientId": "local-a",
            "type": "talent",
            "title": "Arcane",
            "classKey": "mage",
            "className": "法师",
            "specKey": "arcane",
            "specName": "奥术",
            "heroKey": "",
            "heroLabel": "",
            "scenarioKey": "",
            "scenarioTitle": "",
            "rawString": "websim:abc",
            "simcLines": [],
            "status": "saved",
            "statusLabel": "已保存",
            "source": "local",
            "metadata": {},
            "schemaVersion": 1,
            "createdAt": "2026-06-27T00:00:00+00:00",
            "updatedAt": "2026-06-27T00:00:00+00:00",
            "remote": True,
        }

        class FakeStore:
            def __init__(self):
                self.calls = []

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def save_build_template(self, user_id, normalized):
                self.calls.append(("save_template", user_id, normalized["template_type"], normalized["raw_string"]))
                return dict(template)

            def list_build_templates(self, user_id, template_type=""):
                self.calls.append(("list_templates", user_id, template_type))
                return [dict(template)]

            def delete_build_template(self, user_id, template_id):
                self.calls.append(("delete_template", user_id, template_id))
                return {"id": template_id, "deleted": True}

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            saved = backend.save_user_build_template(
                "token-pg",
                {
                    "type": "talent",
                    "title": "Arcane",
                    "rawString": "websim:abc",
                    "classKey": "mage",
                    "specKey": "arcane",
                },
            )
            listed = backend.list_user_build_templates("token-pg", "talent")
            deleted = backend.delete_user_build_template("token-pg", "template-pg-1")
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(saved["id"], "template-pg-1")
        self.assertEqual(listed["templates"][0]["id"], "template-pg-1")
        self.assertEqual(deleted, {"id": "template-pg-1", "deleted": True})
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["auth", "save_template", "auth", "list_templates", "auth", "delete_template"],
        )

    def test_safe_json_loads_accepts_postgres_jsonb_values(self):
        import server.news_backend as backend

        self.assertEqual(backend.safe_json_loads({"state": "queued"}, {}, "jsonb dict"), {"state": "queued"})
        self.assertEqual(backend.safe_json_loads(["a"], [], "jsonb list"), ["a"])

    def test_news_backend_routes_simulator_task_reads_to_postgres_personal_store(self):
        import server.news_backend as backend

        request_payload = {
            "templateContext": {
                "talent": {"id": "talent-pg", "title": "Submit Snapshot", "specName": "奥术"},
                "gear": {"id": "gear-pg", "title": "Gear Snapshot", "specName": "奥术"},
            }
        }
        analysis_payload = {
            "mode": "simcraft_template",
            "status": "queued",
            "simcReport": {
                "state": "queued",
                "build": {"specName": "changed-after-submit"},
                "timing": {"queuedAt": "2026-06-27T00:00:00+00:00"},
            },
        }
        summary_payload = {
            "state": "queued",
            "build": {"specName": "奥术"},
            "timing": {"queuedAt": "2026-06-27T00:00:00+00:00"},
        }
        list_row = (
            "task-pg-1",
            "simcraft_template",
            "queued",
            request_payload,
            analysis_payload,
            summary_payload,
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T00:01:00+00:00",
        )
        detail_row = (
            "task-pg-1",
            "simcraft_template",
            "queued",
            request_payload,
            analysis_payload,
            "2026-06-27T00:00:00+00:00",
            "2026-06-27T00:01:00+00:00",
        )

        class FakeStore:
            def __init__(self):
                self.calls = []

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def list_simulator_task_rows(self, user_id):
                self.calls.append(("list_tasks", user_id))
                return [list_row]

            def get_simulator_task_row(self, user_id, task_id):
                self.calls.append(("get_task", user_id, task_id))
                return detail_row

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            listed = backend.list_simulator_tasks("token-pg")
            detail = backend.get_simulator_task("token-pg", "task-pg-1")
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(listed["tasks"][0]["taskId"], "task-pg-1")
        self.assertEqual(listed["tasks"][0]["simcReportSummary"]["build"]["specName"], "奥术")
        self.assertEqual(detail["task"]["request"]["templateContext"]["talent"]["title"], "Submit Snapshot")
        self.assertEqual([call[0] for call in fake.calls], ["auth", "list_tasks", "auth", "get_task"])

    def test_news_backend_serializes_postgres_simulator_task_uuid_and_timestamps(self):
        import server.news_backend as backend

        task_uuid = uuid.uuid4()
        created_at = datetime(2026, 6, 28, 3, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2026, 6, 28, 3, 1, 0, tzinfo=timezone.utc)
        request_payload = {"mode": "simcraft_agent", "prompt": "PG UUID"}
        analysis_payload = {"mode": "simcraft_agent", "status": "queued", "recommendations": []}
        list_row = (
            task_uuid,
            "simcraft_agent",
            "queued",
            request_payload,
            analysis_payload,
            {"state": "queued"},
            created_at,
            updated_at,
        )
        detail_row = (
            task_uuid,
            "simcraft_agent",
            "queued",
            request_payload,
            analysis_payload,
            created_at,
            updated_at,
        )

        class FakeStore:
            def authenticate_token(self, token, now):
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def list_simulator_task_rows(self, user_id):
                return [list_row]

            def get_simulator_task_row(self, user_id, task_id):
                return detail_row

        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: FakeStore()
        try:
            listed = backend.list_simulator_tasks("token-pg")
            detail = backend.get_simulator_task("token-pg", str(task_uuid))
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(listed["tasks"][0]["taskId"], str(task_uuid))
        self.assertEqual(listed["tasks"][0]["createdAt"], created_at.isoformat())
        self.assertEqual(detail["task"]["taskId"], str(task_uuid))
        self.assertEqual(detail["task"]["updatedAt"], updated_at.isoformat())

    def test_news_backend_routes_simcraft_template_enqueue_to_postgres_personal_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []
                self.inserted = None

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def active_simulator_task_rows(self, user_id):
                self.calls.append(("active_tasks", user_id))
                return []

            def insert_simulator_task(self, task):
                self.calls.append(("insert_task", task["user_id"], task["mode"], task["status"]))
                self.inserted = task

        fake = FakeStore()
        originals = {
            "personal_data_store": getattr(backend, "personal_data_store", None),
            "prepare_simcraft_template_request": backend.prepare_simcraft_template_request,
            "analyze_simulator_request": backend.analyze_simulator_request,
            "simcraft_template_task_fingerprint": backend.simcraft_template_task_fingerprint,
            "start_simcraft_template_task_runner": backend.start_simcraft_template_task_runner,
        }
        backend.personal_data_store = lambda: fake
        backend.prepare_simcraft_template_request = lambda payload: dict(payload)
        backend.simcraft_template_task_fingerprint = lambda payload: "fingerprint-pg"
        backend.start_simcraft_template_task_runner = lambda task_id: False

        def fake_analyze(payload):
            return {
                "mode": "simcraft_template",
                "status": "ready",
                "request": dict(payload),
                "agent": {"status": "template_ready", "canSubmitTask": True},
                "simulation": {"ran": False, "metrics": {}},
                "stages": [],
            }

        backend.analyze_simulator_request = fake_analyze
        try:
            result = backend.enqueue_simcraft_template_task(
                {
                    "mode": "simcraft_template",
                    "confirmOnly": False,
                    "saveTask": True,
                    "guestId": "guest-should-not-persist",
                    "templateContext": {
                        "talent": {"id": "talent-pg", "title": "Talent Snapshot", "specName": "奥术"},
                        "gear": {"id": "gear-pg", "title": "Gear Snapshot", "specName": "奥术"},
                    },
                },
                access_token="token-pg",
            )
        finally:
            if originals["personal_data_store"] is not None:
                backend.personal_data_store = originals["personal_data_store"]
            else:
                delattr(backend, "personal_data_store")
            backend.prepare_simcraft_template_request = originals["prepare_simcraft_template_request"]
            backend.analyze_simulator_request = originals["analyze_simulator_request"]
            backend.simcraft_template_task_fingerprint = originals["simcraft_template_task_fingerprint"]
            backend.start_simcraft_template_task_runner = originals["start_simcraft_template_task_runner"]

        self.assertEqual([call[0] for call in fake.calls], ["auth", "active_tasks", "insert_task"])
        self.assertEqual(fake.inserted["user_id"], "pg-user-1")
        self.assertEqual(fake.inserted["status"], "queued")
        self.assertEqual(fake.inserted["summary_json"]["state"], "queued")
        self.assertNotIn("guestId", fake.inserted["request_json"])
        self.assertEqual(result["status"], "queued")

    def test_news_backend_routes_saved_generic_simulator_task_to_postgres_personal_store(self):
        import server.news_backend as backend

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"
            os.environ["WOW_DATABASE_RUNTIME"] = "postgres_personal"
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "hybrid.sqlite3")
            backend = importlib.reload(backend)

            class FakeStore:
                def __init__(self):
                    self.calls = []
                    self.inserted = None

                def authenticate_token(self, token, now):
                    self.calls.append(("auth", token, now))
                    return {
                        "id": "pg-user-1",
                        "openid": "openid-pg",
                        "unionid": "",
                        "nickname": "",
                        "avatarUrl": "",
                        "createdAt": "2026-06-28T00:00:00+00:00",
                        "updatedAt": "2026-06-28T00:00:00+00:00",
                    }

                def insert_simulator_task(self, task):
                    self.calls.append(("insert_task", task["user_id"], task["mode"], task["status"]))
                    self.inserted = task

            fake = FakeStore()
            originals = {
                "personal_data_store": getattr(backend, "personal_data_store", None),
                "analyze_simulator_request": backend.analyze_simulator_request,
            }
            backend.personal_data_store = lambda: fake
            backend.analyze_simulator_request = lambda payload: {
                "mode": "simcraft_agent",
                "status": "completed",
                "recommendations": ["queued generic task"],
            }
            try:
                analysis = backend.analyze_and_store_simulator_task(
                    {"mode": "simcraft_agent", "prompt": "generic save", "saveTask": True},
                    access_token="token-pg",
                )
            finally:
                if originals["personal_data_store"] is not None:
                    backend.personal_data_store = originals["personal_data_store"]
                else:
                    delattr(backend, "personal_data_store")
                backend.analyze_simulator_request = originals["analyze_simulator_request"]

        self.assertEqual(analysis["taskId"], fake.inserted["id"])
        self.assertEqual(fake.inserted["user_id"], "pg-user-1")
        self.assertEqual(fake.inserted["mode"], "simcraft_agent")
        self.assertEqual(fake.inserted["request_json"]["prompt"], "generic save")
        self.assertEqual([call[0] for call in fake.calls], ["auth", "insert_task"])

    def test_news_backend_runs_simcraft_template_task_from_postgres_personal_store(self):
        import server.news_backend as backend

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["WOW_DATABASE_URL"] = "postgresql://wow_app@localhost/wow_test"
            os.environ["WOW_DATABASE_RUNTIME"] = "postgres_personal"
            os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "hybrid.sqlite3")
            backend = importlib.reload(backend)

            class FakeStore:
                def __init__(self):
                    self.calls = []
                    self.running_summary = None
                    self.final_summary = None

                def get_simcraft_template_task_for_runner(self, task_id):
                    self.calls.append(("get_task", task_id))
                    return (
                        task_id,
                        "pg-user-1",
                        "simcraft_template",
                        "queued",
                        {
                            "mode": "simcraft_template",
                            "confirmOnly": False,
                            "saveTask": True,
                            "simcTaskFingerprint": "fingerprint-pg",
                            "templateContext": {
                                "talent": {"title": "Submit Snapshot", "specName": "Arcane"},
                                "gear": {"title": "Gear Snapshot", "specName": "Arcane"},
                            },
                        },
                        {
                            "mode": "simcraft_template",
                            "status": "queued",
                            "owner": {"id": "pg-user-1", "openid": "openid-pg"},
                            "agent": {"status": "simc_queued", "canSubmitTask": False},
                            "simulation": {"ran": False, "metrics": {}, "status": "queued"},
                            "stages": [],
                        },
                        "2026-06-28T00:00:00+00:00",
                        "2026-06-28T00:00:00+00:00",
                    )

                def mark_simcraft_template_task_running(self, task_id, running_analysis, running_summary, started_at):
                    self.calls.append(("mark_running", task_id, running_analysis["status"], started_at))
                    self.running_summary = running_summary

                def finish_simcraft_template_task(
                    self,
                    task_id,
                    final_status,
                    analysis,
                    final_summary,
                    finished_at,
                    final_error="",
                ):
                    self.calls.append(("finish_task", task_id, final_status, finished_at, final_error))
                    self.final_summary = final_summary

            fake = FakeStore()
            seen_request = {}
            originals = {
                "personal_data_store": getattr(backend, "personal_data_store", None),
                "analyze_simulator_request": backend.analyze_simulator_request,
            }
            backend.personal_data_store = lambda: fake

            def fake_analyze(payload):
                seen_request.update(payload)
                return {
                    "mode": "simcraft_template",
                    "status": "ready",
                    "request": dict(payload),
                    "agent": {"status": "simc_complete", "canSubmitTask": False},
                    "simulation": {"ran": True, "metrics": {"dps": 12345}, "summary": "12345 DPS"},
                    "stages": [],
                }

            backend.analyze_simulator_request = fake_analyze
            try:
                completed = backend.run_simcraft_template_task("task-pg-1")
            finally:
                if originals["personal_data_store"] is not None:
                    backend.personal_data_store = originals["personal_data_store"]
                else:
                    delattr(backend, "personal_data_store")
                backend.analyze_simulator_request = originals["analyze_simulator_request"]

        self.assertTrue(seen_request["_executeSimcTask"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["owner"]["id"], "pg-user-1")
        self.assertEqual([call[0] for call in fake.calls], ["get_task", "mark_running", "finish_task"])
        self.assertEqual(fake.running_summary["state"], "running")
        self.assertEqual(fake.final_summary["state"], "completed")

    def test_news_backend_routes_chickenbro_session_and_job_reads_to_postgres_personal_store(self):
        import server.news_backend as backend

        session = {
            "sessionId": "session-pg-1",
            "title": "Arcane help",
            "productPhase": "retail",
            "metadata": {"title": "Arcane help"},
            "createdAt": "2026-06-27T00:00:00+00:00",
            "updatedAt": "2026-06-27T00:00:00+00:00",
        }
        job = {
            "jobId": "job-pg-1",
            "sessionId": "session-pg-1",
            "kind": "chickenbro",
            "status": "succeeded",
            "request": {},
            "boundedContext": {},
            "result": {},
            "error": "",
            "createdAt": "2026-06-27T00:00:00+00:00",
            "updatedAt": "2026-06-27T00:00:00+00:00",
            "startedAt": "",
            "finishedAt": "",
        }

        class FakeStore:
            def __init__(self):
                self.calls = []

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def create_chickenbro_session(self, user_id, title, product_phase, metadata, now):
                self.calls.append(("create_session", user_id, title, product_phase, metadata, now))
                return dict(session, title=title, productPhase=product_phase, metadata=metadata)

            def get_chickenbro_session(self, user_id, session_id):
                self.calls.append(("get_session", user_id, session_id))
                return {"session": dict(session), "messages": []}

            def get_chickenbro_job(self, user_id, job_id):
                self.calls.append(("get_job", user_id, job_id))
                return dict(job, jobId=job_id)

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            created = backend.create_chickenbro_session(
                "token-pg",
                metadata={"title": "Arcane help", "productPhase": "retail"},
            )
            fetched = backend.get_chickenbro_session("token-pg", "session-pg-1")
            fetched_job = backend.get_chickenbro_job("token-pg", "job-pg-1")
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(created["session"]["sessionId"], "session-pg-1")
        self.assertEqual(fetched["session"]["sessionId"], "session-pg-1")
        self.assertEqual(fetched_job["job"]["jobId"], "job-pg-1")
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["auth", "create_session", "auth", "get_session", "auth", "get_job"],
        )

    def test_news_backend_routes_chickenbro_message_runtime_to_postgres_personal_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []
                self.result = {}

            def authenticate_token(self, token, now):
                self.calls.append(("auth", token, now))
                return {
                    "id": "pg-user-1",
                    "openid": "openid-pg",
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

            def create_chickenbro_session(self, user_id, title, product_phase, metadata, now):
                self.calls.append(("create_session", user_id, title, product_phase, metadata, now))
                return {
                    "sessionId": "session-pg-1",
                    "title": title,
                    "productPhase": product_phase,
                    "metadata": metadata,
                    "createdAt": now,
                    "updatedAt": now,
                }

            def load_chickenbro_user_profile(self, user_id):
                self.calls.append(("load_profile", user_id))
                return {}

            def upsert_chickenbro_user_profile(self, user_id, profile, now):
                self.calls.append(("upsert_profile", user_id, profile, now))
                return profile

            def insert_chickenbro_message(self, user_id, session_id, role, content, payload=None, agent_job_id="", now=""):
                self.calls.append(("insert_message", user_id, session_id, role, content, payload, agent_job_id, now))
                return {
                    "messageId": f"{role}-message-pg",
                    "sessionId": session_id,
                    "role": role,
                    "content": content,
                    "payload": payload or {},
                    "agentJobId": agent_job_id,
                    "createdAt": now,
                }

            def insert_agent_job(self, user_id, session_id, request_payload, bounded_context, now):
                self.calls.append(("insert_job", user_id, session_id, request_payload, bounded_context, now))
                return "job-pg-1"

            def update_agent_job(
                self,
                user_id,
                job_id,
                status,
                result=None,
                error="",
                started_at=None,
                finished_at=None,
                now="",
            ):
                self.calls.append(("update_job", user_id, job_id, status, result, error, started_at, finished_at, now))
                if result:
                    self.result = result

            def touch_chickenbro_session(self, user_id, session_id, updated_at):
                self.calls.append(("touch_session", user_id, session_id, updated_at))

            def get_chickenbro_job(self, user_id, job_id):
                self.calls.append(("get_job", user_id, job_id))
                return {
                    "jobId": job_id,
                    "sessionId": "session-pg-1",
                    "kind": "chickenbro",
                    "status": "succeeded",
                    "request": {"message": "Arcane opener?"},
                    "boundedContext": {},
                    "result": self.result,
                    "error": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                    "startedAt": "2026-06-27T00:00:00+00:00",
                    "finishedAt": "2026-06-27T00:00:01+00:00",
                }

        fake = FakeStore()
        originals = {
            "personal_data_store": getattr(backend, "personal_data_store", None),
            "load_chickenbro_profiles": backend.load_chickenbro_profiles,
        }
        backend.personal_data_store = lambda: fake
        backend.load_chickenbro_profiles = lambda context: []
        try:
            result = backend.send_chickenbro_message(
                {
                    "message": "Arcane opener?",
                    "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
                },
                access_token="token-pg",
            )
        finally:
            if originals["personal_data_store"] is not None:
                backend.personal_data_store = originals["personal_data_store"]
            else:
                delattr(backend, "personal_data_store")
            backend.load_chickenbro_profiles = originals["load_chickenbro_profiles"]

        self.assertEqual(result["mode"], "chickenbro")
        self.assertEqual(result["session"]["sessionId"], "session-pg-1")
        self.assertEqual(result["job"]["jobId"], "job-pg-1")
        self.assertEqual(result["assistantMessage"]["agentJobId"], "job-pg-1")
        self.assertEqual(
            [call[0] for call in fake.calls],
            [
                "auth",
                "create_session",
                "load_profile",
                "upsert_profile",
                "insert_message",
                "insert_job",
                "update_job",
                "update_job",
                "insert_message",
                "touch_session",
                "get_job",
            ],
        )

    def test_news_backend_routes_guest_lookup_to_postgres_personal_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def find_wechat_user_by_openid(self, openid):
                self.calls.append(("find_openid", openid))
                return {
                    "id": "pg-guest-1",
                    "openid": openid,
                    "unionid": "",
                    "nickname": "",
                    "avatarUrl": "",
                    "createdAt": "2026-06-27T00:00:00+00:00",
                    "updatedAt": "2026-06-27T00:00:00+00:00",
                }

        fake = FakeStore()
        original_store = getattr(backend, "personal_data_store", None)
        backend.personal_data_store = lambda: fake
        try:
            user = backend.find_guest_simulator_user("guest-pg-device")
        finally:
            if original_store is not None:
                backend.personal_data_store = original_store
            else:
                delattr(backend, "personal_data_store")

        self.assertEqual(user["id"], "pg-guest-1")
        self.assertTrue(user["openid"].startswith("guest-simulator-"))
        self.assertEqual(fake.calls[0][0], "find_openid")

    def test_news_backend_routes_analytics_recording_to_postgres_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def record_events(self, payload, user_id=None, client_id="", session_id="", platform="miniprogram"):
                self.calls.append(("record", payload, user_id, client_id, session_id, platform))
                return {"ok": True, "inserted": 1, "ignored": 0}

        class FakeHandler:
            headers = {
                "X-Wow-Client-Id": "client-pg",
                "X-Wow-Session-Id": "session-pg",
                "X-Wow-Platform": "miniprogram",
            }

        fake = FakeStore()
        original_store = getattr(backend, "analytics_data_store", None)
        backend.analytics_data_store = lambda: fake
        try:
            result = backend.record_analytics_request(
                FakeHandler(),
                {"events": [{"eventId": "evt-pg-1", "eventName": "page_view", "page": "pages/news/news"}]},
            )
        finally:
            if original_store is not None:
                backend.analytics_data_store = original_store
            else:
                delattr(backend, "analytics_data_store")

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(fake.calls[0][0], "record")
        self.assertEqual(fake.calls[0][3], "client-pg")
        self.assertEqual(fake.calls[0][4], "session-pg")

    def test_news_backend_routes_admin_analytics_summary_to_postgres_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def analytics_summary(self, query):
                self.calls.append(("summary", query))
                return {"summary": {"pv": 2, "uv": 1}, "topEvents": []}

        class FakeHandler:
            headers = {"Authorization": "Bearer admin-token"}

        fake = FakeStore()
        captured = []
        originals = {
            "analytics_data_store": getattr(backend, "analytics_data_store", None),
            "json_response": backend.json_response,
        }
        os.environ["WOW_ANALYTICS_ADMIN_TOKEN"] = "admin-token"
        backend.analytics_data_store = lambda: fake
        backend.json_response = lambda handler, status, payload: captured.append((status, payload))
        try:
            backend.admin_analytics_response(
                FakeHandler(),
                "/api/admin/analytics/summary",
                {"from": ["2026-06-12"], "to": ["2026-06-12"]},
            )
        finally:
            if originals["analytics_data_store"] is not None:
                backend.analytics_data_store = originals["analytics_data_store"]
            else:
                delattr(backend, "analytics_data_store")
            backend.json_response = originals["json_response"]
            os.environ.pop("WOW_ANALYTICS_ADMIN_TOKEN", None)

        self.assertEqual(captured[0][0], 200)
        self.assertEqual(captured[0][1]["summary"]["pv"], 2)
        self.assertEqual(fake.calls[0][0], "summary")

    def test_news_backend_routes_admin_analytics_simulator_to_postgres_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def analytics_simulator(self, query):
                self.calls.append(("simulator", query))
                return {"summary": {"taskCount": 1}, "tasks": [{"mode": "simcraft_agent"}]}

        class FakeHandler:
            headers = {"Authorization": "Bearer admin-token"}

        fake = FakeStore()
        captured = []
        originals = {
            "analytics_data_store": getattr(backend, "analytics_data_store", None),
            "json_response": backend.json_response,
        }
        os.environ["WOW_ANALYTICS_ADMIN_TOKEN"] = "admin-token"
        backend.analytics_data_store = lambda: fake
        backend.json_response = lambda handler, status, payload: captured.append((status, payload))
        try:
            backend.admin_analytics_response(
                FakeHandler(),
                "/api/admin/analytics/simulator",
                {"from": ["2026-06-12"], "to": ["2026-06-12"]},
            )
        finally:
            if originals["analytics_data_store"] is not None:
                backend.analytics_data_store = originals["analytics_data_store"]
            else:
                delattr(backend, "analytics_data_store")
            backend.json_response = originals["json_response"]
            os.environ.pop("WOW_ANALYTICS_ADMIN_TOKEN", None)

        self.assertEqual(captured[0][0], 200)
        self.assertEqual(captured[0][1]["summary"]["taskCount"], 1)
        self.assertEqual(fake.calls[0][0], "simulator")

    def test_news_backend_data_health_prefers_postgres_cache_sync_state(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def get_sync_state(self, key):
                self.calls.append(("get_sync_state", key))
                if key == "websim_sync":
                    return {
                        "ok": True,
                        "dataStatus": "verified",
                        "checkedAt": "2026-06-28T01:00:00+00:00",
                        "simc": {"talents": 10, "presets": 2},
                        "gearCatalog": {"status": "partial", "itemCount": 1},
                    }
                if key == "gearCatalog":
                    return {
                        "status": "partial",
                        "checkedAt": "2026-06-28T01:01:00+00:00",
                        "itemCount": 756,
                        "sourceCount": 1200,
                        "variantCount": 2000,
                        "verifiedCount": 1500,
                        "partialCount": 500,
                        "observedVariantCount": 2388,
                        "itemDatabaseRevision": "pg-cache-items-rev",
                        "variantRevision": "pg-cache-variants-rev",
                        "blockers": ["missing deterministic SimC variant preset"],
                    }
                return {}

        fake = FakeStore()
        original_store = getattr(backend, "cache_data_store", None)
        backend.cache_data_store = lambda: fake
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["WOW_NEWS_DB"] = str(Path(tmp) / "health.sqlite3")
                payload = backend.build_data_health_payload()
        finally:
            if original_store is not None:
                backend.cache_data_store = original_store
            else:
                delattr(backend, "cache_data_store")

        components = {item["key"]: item for item in payload["components"]}
        self.assertEqual(components["websim_sync"]["status"], "verified")
        self.assertEqual(components["websim_sync"]["details"]["gearItemCount"], 756)
        self.assertEqual(components["websim_sync"]["details"]["observedVariantCount"], 2388)
        self.assertEqual(components["gear_catalog"]["details"]["itemCount"], 756)
        self.assertEqual(components["gear_catalog"]["details"]["itemDatabaseRevision"], "pg-cache-items-rev")
        self.assertEqual([call[1] for call in fake.calls], ["websim_sync", "gearCatalog"])

    def test_news_backend_routes_websim_season_and_loot_reads_to_postgres_cache_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def get_active_season_payload(self):
                self.calls.append("season")
                return {
                    "seasonId": "season-pg",
                    "seasonLabel": "Season PG",
                    "seasonRevision": "season-pg-1",
                    "dataStatus": "verified",
                    "dungeons": [{"instanceId": "1300", "name": "Dungeon A"}],
                }

            def get_websim_loot(self, filters):
                self.calls.append("loot")
                return {
                    "items": [{"itemId": "item-a", "instanceId": filters.get("instanceId")}],
                    "instances": [],
                    "seasonRevision": "season-pg-1",
                    "dataStatus": "verified",
                }

        fake = FakeStore()
        originals = {
            "cache_data_store": getattr(backend, "cache_data_store", None),
            "init_db": backend.init_db,
        }
        backend.cache_data_store = lambda: fake
        backend.init_db = lambda: (_ for _ in ()).throw(AssertionError("SQLite fallback should not be used for PG season/loot reads"))
        try:
            season = backend.runtime_season_payload()
            loot = backend.runtime_websim_loot_payload({"instanceId": "1300"})
        finally:
            if originals["cache_data_store"] is not None:
                backend.cache_data_store = originals["cache_data_store"]
            else:
                delattr(backend, "cache_data_store")
            backend.init_db = originals["init_db"]

        self.assertEqual(season["seasonRevision"], "season-pg-1")
        self.assertEqual(loot["items"][0]["itemId"], "item-a")
        self.assertEqual(fake.calls, ["season", "loot"])

    def test_news_backend_routes_websim_gear_reads_to_postgres_cache_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def get_websim_gear(self, class_key, spec_key, compact=False):
                self.calls.append((class_key, spec_key, compact))
                return {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "catalogStatus": "verified",
                    "dataStatus": "verified",
                    "replacementCandidates": [
                        {"slot": "trinket1", "items": [{"itemId": "item-a"}]},
                    ],
                }

        fake = FakeStore()
        originals = {
            "cache_data_store": getattr(backend, "cache_data_store", None),
            "init_db": backend.init_db,
        }
        backend.cache_data_store = lambda: fake
        backend.init_db = lambda: (_ for _ in ()).throw(AssertionError("SQLite fallback should not be used for PG gear reads"))
        try:
            gear = backend.runtime_websim_gear_payload("mage", "arcane", compact=True)
        finally:
            if originals["cache_data_store"] is not None:
                backend.cache_data_store = originals["cache_data_store"]
            else:
                delattr(backend, "cache_data_store")
            backend.init_db = originals["init_db"]

        self.assertEqual(gear["replacementCandidates"][0]["items"][0]["itemId"], "item-a")
        self.assertEqual(fake.calls, [("mage", "arcane", True)])

    def test_news_backend_routes_websim_talent_reads_to_postgres_cache_store(self):
        import server.news_backend as backend

        class FakeStore:
            def __init__(self):
                self.calls = []

            def get_websim_talents(self, class_key, spec_key, hero_key=""):
                self.calls.append((class_key, spec_key, hero_key))
                return {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": hero_key,
                    "talentStatus": "verified",
                    "dataStatus": "verified",
                    "nodes": [{"id": "talent-a"}],
                }

        fake = FakeStore()
        originals = {
            "cache_data_store": getattr(backend, "cache_data_store", None),
            "init_db": backend.init_db,
        }
        backend.cache_data_store = lambda: fake
        backend.init_db = lambda: (_ for _ in ()).throw(AssertionError("SQLite fallback should not be used for PG talent reads"))
        try:
            talents = backend.runtime_websim_talents_payload("mage", "frost", "spellslinger")
        finally:
            if originals["cache_data_store"] is not None:
                backend.cache_data_store = originals["cache_data_store"]
            else:
                delattr(backend, "cache_data_store")
            backend.init_db = originals["init_db"]

        self.assertEqual(talents["nodes"][0]["id"], "talent-a")
        self.assertEqual(fake.calls, [("mage", "frost", "spellslinger")])

    def test_news_backend_routes_public_content_reads_to_postgres_store(self):
        import server.news_backend as backend

        article = {
            "id": "pg-news-1",
            "title": "Patch notes",
            "summary": "Summary",
            "channel": backend.CHANNELS[0]["title"],
            "category": "update",
            "tags": ["content-update"],
            "importance": 90,
            "sourceName": "Blizzard News",
            "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/123",
            "publishedAt": "2026-06-28T01:00:00+00:00",
            "sourceNote": "Official source",
            "bodyZh": "Translated full body",
            "originalTitle": "Patch Notes",
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

        class FakeStore:
            def __init__(self):
                self.calls = []

            def load_articles(self):
                self.calls.append(("load_articles",))
                return [dict(article)]

            def get_article(self, article_id):
                self.calls.append(("get_article", article_id))
                return dict(article)

            def latest_refresh_state(self):
                self.calls.append(("latest_state",))
                return {"refreshMode": "scheduled", "lastRefreshedAt": "2026-06-28T01:05:00+00:00"}

            def latest_refresh_run_payload(self):
                self.calls.append(("latest_payload",))
                return {"refreshMode": "scheduled", "publishedCount": 1}

        fake = FakeStore()
        original_store = getattr(backend, "content_data_store", None)
        backend.content_data_store = lambda: fake
        try:
            articles = backend.load_articles()
            detail = backend.get_article_detail("pg-news-1")
            state = backend.latest_refresh_state()
            payload = backend.latest_refresh_run_payload()
        finally:
            if original_store is not None:
                backend.content_data_store = original_store
            else:
                delattr(backend, "content_data_store")

        self.assertEqual(articles[0]["id"], "pg-news-1")
        self.assertEqual(detail["id"], "pg-news-1")
        self.assertEqual(state["refreshMode"], "scheduled")
        self.assertEqual(payload["publishedCount"], 1)
        self.assertEqual([call[0] for call in fake.calls], ["load_articles", "get_article", "latest_state", "latest_payload"])

    def test_news_backend_routes_content_refresh_writes_to_postgres_store(self):
        import server.news_backend as backend

        article = {
            "id": "pg-news-refresh-1",
            "title": "Patch notes",
            "summary": "Summary",
            "channel": backend.CHANNELS[0]["title"],
            "category": "update",
            "tags": ["content-update"],
            "importance": 90,
            "sourceName": "Blizzard News",
            "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/456",
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
            "canonicalTopicId": "news:456",
            "readingMeta": {"estimatedReadingMinutes": 1},
            "translationFidelity": "source_translation",
        }

        class FakeStore:
            def __init__(self):
                self.calls = []

            def seed_sources(self, sources, now):
                self.calls.append(("seed_sources", len(sources), now))

            def persist_news_raw_article(self, article_payload, fetched_at):
                self.calls.append(("raw", article_payload["id"], fetched_at))

            def persist_news_evidence(self, article_payload, checked_at):
                self.calls.append(("evidence", article_payload["id"], checked_at))

            def save_public_article(self, article_payload, updated_at):
                self.calls.append(("save", article_payload["id"], updated_at))

            def delete_public_articles_not_in(self, accepted_ids):
                self.calls.append(("delete_not_in", tuple(accepted_ids)))

            def audit_existing_public_articles(self, quality_issue):
                self.calls.append(("audit", quality_issue.__name__))
                return []

            def queue_summary(self, collector_errors=None):
                self.calls.append(("queue_summary", tuple(collector_errors or [])))
                return {
                    "queuedCount": 0,
                    "retryableCount": 0,
                    "publishedQueueCount": 0,
                    "blockedQueueCount": 0,
                    "oldestBacklogAge": 0,
                    "sourceCoverage": {},
                }

            def record_refresh_run(self, refresh_mode, refreshed_at, accepted_count, rejected_count, message):
                self.calls.append(("refresh_run", refresh_mode, accepted_count, rejected_count, message["publishedCount"]))

        fake = FakeStore()
        originals = {
            "content_data_store": getattr(backend, "content_data_store", None),
            "load_seed_articles": backend.load_seed_articles,
        }
        backend.content_data_store = lambda: fake
        backend.load_seed_articles = lambda: [dict(article)]
        try:
            result = backend.refresh_articles("scheduled", collector_enabled=False)
        finally:
            if originals["content_data_store"] is not None:
                backend.content_data_store = originals["content_data_store"]
            else:
                delattr(backend, "content_data_store")
            backend.load_seed_articles = originals["load_seed_articles"]

        self.assertEqual(result["refreshMode"], "scheduled")
        self.assertEqual(
            [call[0] for call in fake.calls],
            ["seed_sources", "raw", "evidence", "save", "delete_not_in", "audit", "queue_summary", "refresh_run"],
        )
