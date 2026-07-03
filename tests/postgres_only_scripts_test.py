import io
import json
import os
import runpy
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from server import community_template_sync
from server import crafted_gear_backfill
from server import gear_observed_backfill
from server import stat_weights_sync
from server import websim_payload
from server import websim_sync


class PostgresOnlyScriptGuardTest(unittest.TestCase):
    def test_websim_sync_uses_postgres_native_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        def fake_websim(*args, **kwargs):
            self.assertIn("stage_callback", kwargs)
            kwargs["stage_callback"]({"stage": "websim", "status": "complete"})
            return {"ok": True, "dataStatus": "verified", "runner": "postgres"}

        def fake_raiderio(*args, **kwargs):
            return {"sourceStatus": "synced", "runner": "postgres"}

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            websim_sync.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(websim_sync, "sync_websim_cache_postgres", side_effect=fake_websim) as websim_runner, patch.object(
            websim_sync, "sync_raiderio_cache_postgres", side_effect=fake_raiderio
        ) as raiderio_runner, redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = websim_sync.main()

        payload = json.loads(stdout.getvalue())
        progress = [json.loads(line) for line in stderr.getvalue().splitlines() if line.strip()]
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["websim"]["runner"], "postgres")
        self.assertEqual(payload["raiderio"]["runner"], "postgres")
        self.assertTrue(any(item.get("stage") == "websim" for item in progress))
        websim_runner.assert_called_once()
        raiderio_runner.assert_called_once()

    def test_stat_weights_sync_uses_postgres_native_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            stat_weights_sync.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            stat_weights_sync,
            "sync_raiderio_cache_postgres",
            return_value={"sourceStatus": "synced", "runner": "postgres"},
        ) as raiderio_runner, patch.object(
            stat_weights_sync,
            "sync_stat_weight_cache_postgres",
            return_value={"sourceStatus": "partial", "runner": "postgres"},
        ) as stat_runner, redirect_stdout(stdout):
            exit_code = stat_weights_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["raiderio"]["runner"], "postgres")
        self.assertEqual(payload["statWeights"]["runner"], "postgres")
        raiderio_runner.assert_called_once()
        stat_runner.assert_called_once()

    def test_community_template_sync_uses_postgres_native_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            community_template_sync.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            return_value={"status": "completed", "sourceStatus": "synced", "runner": "postgres"},
        ) as runner, redirect_stdout(stdout):
            exit_code = community_template_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        runner.assert_called_once_with(mode="scheduled")

    def test_backfill_connectors_use_postgres_in_postgres_only_mode(self):
        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ):
            for module, function_name in (
                (crafted_gear_backfill, "connect_backfill_db"),
                (gear_observed_backfill, "connect_backfill_db"),
                (gear_observed_backfill, "connect_readonly_backfill_db"),
            ):
                fake_conn = object()
                with self.subTest(module=module.__name__, function=function_name), patch.object(
                    module.sqlite3,
                    "connect",
                    side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
                ), patch.object(module, "connect_postgres", return_value=fake_conn) as connect_pg:
                    self.assertIs(getattr(module, function_name)(), fake_conn)
                    connect_pg.assert_called_once()

    def test_observed_backfill_main_uses_postgres_native_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            gear_observed_backfill.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            gear_observed_backfill,
            "run_gear_observed_backfill_postgres",
            return_value={"status": "blocked", "runner": "postgres", "errors": ["writer pending"]},
        ) as runner, redirect_stdout(stdout):
            exit_code = gear_observed_backfill.main(["--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        runner.assert_called_once()

    def test_crafted_backfill_main_uses_postgres_native_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            crafted_gear_backfill.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            crafted_gear_backfill,
            "run_crafted_gear_backfill_postgres",
            return_value={"status": "blocked", "runner": "postgres", "errors": ["writer pending"]},
        ) as runner, redirect_stdout(stdout):
            exit_code = crafted_gear_backfill.main(["--from-metadata"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        runner.assert_called_once()

    def test_direct_websim_and_stat_weight_entrypoints_reject_sqlite_in_postgres_only_mode(self):
        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            websim_payload.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot use SQLite"):
                websim_payload.sync_websim_cache("server/data/wow_news.sqlite3")

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot use SQLite"):
                runpy.run_module("server.stat_weights_payload", run_name="__main__")

    def test_sqlite_migration_source_flag_allows_explicit_offline_sqlite_read(self):
        class FakeConnection:
            def __init__(self):
                self.statements = []

            def execute(self, statement):
                self.statements.append(statement)
                return self

        fake_conn = FakeConnection()
        calls = []

        def fake_connect(*args, **kwargs):
            calls.append((args, kwargs))
            return fake_conn

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
                "WOW_SQLITE_MIGRATION_SOURCE": "1",
            },
            clear=False,
        ), patch.object(gear_observed_backfill.sqlite3, "connect", side_effect=fake_connect):
            conn = gear_observed_backfill.connect_readonly_backfill_db()

        self.assertIs(conn, fake_conn)
        self.assertTrue(calls)
