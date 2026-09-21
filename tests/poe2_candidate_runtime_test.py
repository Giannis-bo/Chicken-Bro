import unittest
from unittest.mock import patch

from server import poe2_candidate_runtime


class Poe2CandidateRuntimeTest(unittest.TestCase):
    def source(self):
        return {
            "WOW_DATABASE_URL": "postgresql://wow_app@127.0.0.1:5432/chickenbro_prod",
            "PGPASSFILE": "/run/credentials/production.pgpass",
            "WOW_APP_ENV": "production",
            "WOW_TEST_LOGIN_ENABLED": "1",
            "WOW_TEST_LOGIN_A_SHA256": "a" * 64,
            "WOW_TEST_LOGIN_B_SHA256": "b" * 64,
            "WOW_QQ_APPID": "123",
            "WOW_QQ_APP_KEY": "secret",
            "WOW_QQ_REDIRECT_URI": "https://www.chickenbro.cloud/api/v2/auth/qq/callback",
            "WOW_API_V2_PORT": "8790",
            "WOW_CODEX_JOBS_DIR": "/var/lib/chickenbro/codex-jobs",
        }

    def prepare(self):
        return poe2_candidate_runtime.prepare_environment(
            self.source(),
            read_text=lambda _path: "127.0.0.1:5432:chickenbro_prod:wow_app:memory\\:only\n",
        )

    def test_reuses_pgpass_password_only_in_memory_and_targets_exact_database(self):
        source = self.source()
        env = poe2_candidate_runtime.prepare_environment(
            source,
            read_text=lambda path: (
                self.assertEqual(path, "/run/credentials/production.pgpass")
                or "127.0.0.1:5432:chickenbro_prod:wow_app:memory\\:only\n"
            ),
        )
        self.assertEqual(env["PGPASSWORD"], "memory:only")
        self.assertEqual(env["WOW_DATABASE_URL"],
                         "postgresql://wow_app@127.0.0.1:5432/chickenbro_poe2_candidate")
        self.assertEqual(source["WOW_DATABASE_URL"],
                         "postgresql://wow_app@127.0.0.1:5432/chickenbro_prod")

    def test_rejects_password_in_source_url_instead_of_bypassing_pgpass(self):
        source = self.source()
        source["WOW_DATABASE_URL"] = "postgresql://wow_app:embedded@127.0.0.1/chickenbro_prod"
        with self.assertRaisesRegex(ValueError, "PGPASSFILE"):
            poe2_candidate_runtime.prepare_environment(
                source, read_text=lambda _path: self.fail("must not read after invalid source URL"),
            )

    def test_forces_all_candidate_isolation_after_inherited_environment(self):
        from server.app.platform.config import AppSettings

        env = self.prepare()
        expected = {
            "WOW_APP_ENV": "test",
            "WOW_API_V2_HOST": "127.0.0.1",
            "WOW_API_V2_PORT": "8796",
            "WOW_WEB_ORIGIN": "https://www.chickenbro.cloud",
            "WOW_WEB_COOKIE_NAME": "__Host-chickenbro-poe2-candidate-session",
            "WOW_WEB_CSRF_COOKIE_NAME": "__Host-chickenbro-poe2-candidate-csrf",
            "WOW_WEB_SESSION_TTL_SECONDS": "86400",
            "WOW_TEST_LOGIN_ENABLED": "1",
            "WOW_CHAT_DURABLE_ENABLED": "1",
            "WOW_CHAT_WORKER_TOOL_PORT": "18794",
            "WOW_WORKER_V2_HEARTBEAT_PATH": "/var/lib/chickenbro/poe2-candidate-worker-heartbeat.json",
            "WOW_CODEX_JOBS_DIR": "/var/lib/chickenbro/poe2-candidate-codex-jobs",
            "WOW_CODEX_PROFILE": "chickenbro-production",
            "POE2_ENGINE_VERSION": "v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41",
            "POE2_ENGINE_LOCK": "/var/lib/chickenbro/poe2-candidate-engine.lock",
        }
        for key, value in expected.items():
            self.assertEqual(env[key], value, key)
        self.assertEqual(env["WOW_TEST_LOGIN_A_SHA256"], "a" * 64)
        self.assertEqual(env["WOW_TEST_LOGIN_B_SHA256"], "b" * 64)
        for key in ("WOW_QQ_APPID", "WOW_QQ_APP_KEY", "WOW_QQ_REDIRECT_URI"):
            self.assertEqual(env[key], "")
        settings = AppSettings.from_env(env)
        self.assertEqual(settings.environment, "test")
        self.assertEqual(settings.port, 8796)
        self.assertEqual(settings.worker_heartbeat_path,
                         "/var/lib/chickenbro/poe2-candidate-worker-heartbeat.json")

    def test_forces_engine_runtime_and_loopback_proxy_bypass(self):
        env = self.prepare()
        root = "/opt/chickenbro-candidates/poe2-20260918"
        self.assertEqual(env["POE2_POB_ROOT"], root + "/upstream/pob")
        self.assertEqual(env["POE2_LUAJIT"], root + "/runtime/root/usr/bin/luajit")
        self.assertEqual(env["LD_LIBRARY_PATH"], root + "/runtime/root/usr/lib/x86_64-linux-gnu")
        self.assertEqual(env["LUA_CPATH"], root + "/runtime/root/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;;")
        self.assertEqual(env["LUA_PATH"], root + "/upstream/pob/runtime/lua/?.lua;" +
                         root + "/upstream/pob/runtime/lua/?/init.lua;;")
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            self.assertEqual(env[key], "http://127.0.0.1:7890")
        for host in ("127.0.0.1", "localhost", "::1"):
            self.assertIn(host, env["NO_PROXY"].split(","))

    def test_api_and_worker_exec_contracts_are_fixed(self):
        self.assertEqual(poe2_candidate_runtime.exec_args("api"), [
            "-m", "uvicorn", "server.app.main:app", "--host", "127.0.0.1", "--port", "8796",
        ])
        self.assertEqual(poe2_candidate_runtime.exec_args("worker"), [
            "-m", "server.app.worker.main", "--worker-id", "chickenbro-poe2-candidate-worker",
        ])
        with self.assertRaises(ValueError):
            poe2_candidate_runtime.exec_args("other")

    def test_main_fails_closed_without_exec_and_never_logs_configuration(self):
        with patch.object(poe2_candidate_runtime, "prepare_environment", side_effect=ValueError("secret")), \
             patch.object(poe2_candidate_runtime.os, "execv") as execute:
            with self.assertRaisesRegex(SystemExit, "configuration failed") as caught:
                poe2_candidate_runtime.main(["api"])
        execute.assert_not_called()
        self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
