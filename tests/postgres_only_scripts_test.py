import io
import json
import os
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from server import community_best_guard_sync
from server import community_template_sync
from server import crafted_gear_backfill
from server import gear_observed_backfill
from server import recommended_bis_guard_sync
from server import season_recommended_gear_sync
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
        self.assertEqual(payload["event"], "websim_sync_complete")
        self.assertEqual(
            payload["components"]["websim"]["runner"],
            "postgres",
        )
        self.assertEqual(
            payload["components"]["raiderio"]["runner"],
            "postgres",
        )
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
            return_value={
                "sourceStatus": "synced",
                "runner": "postgres",
                "profiles": [
                    {
                        "raw": "must-not-reach-stat-weight-stdout",
                    }
                ]
                * 500,
            },
        ) as raiderio_runner, patch.object(
            stat_weights_sync,
            "sync_stat_weight_cache_postgres",
            return_value={"sourceStatus": "partial", "runner": "postgres"},
        ) as stat_runner, redirect_stdout(stdout):
            exit_code = stat_weights_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["event"], "stat_weights_sync_complete")
        self.assertEqual(
            payload["components"]["raiderio"]["runner"],
            "postgres",
        )
        self.assertEqual(
            payload["components"]["statWeights"]["runner"],
            "postgres",
        )
        self.assertNotIn(
            "must-not-reach-stat-weight-stdout",
            stdout.getvalue(),
        )
        self.assertLessEqual(
            len(stdout.getvalue().encode("utf-8")),
            8193,
        )
        raiderio_runner.assert_called_once()
        stat_runner.assert_called_once()

    def test_season_recommended_gear_sync_uses_postgres_native_runner(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            season_recommended_gear_sync,
            "sync_season_recommended_gear_postgres",
            return_value={
                "runner": "postgres",
                "sourceKey": "season_recommendation",
                "completeSpecCount": 40,
                "status": "verified",
            },
        ) as runner, redirect_stdout(stdout):
            exit_code = season_recommended_gear_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["sourceKey"], "season_recommendation")
        runner.assert_called_once_with(mode="scheduled")

    def test_recommended_bis_guard_sync_uses_postgres_native_runner(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            recommended_bis_guard_sync,
            "sync_recommended_bis_guard_postgres",
            return_value={
                "runner": "postgres",
                "schemaRevision": "recommended-bis-v1-guard-state-v1",
                "status": "partial",
                "guardMode": "readiness_only",
            },
        ) as runner, redirect_stdout(stdout):
            exit_code = recommended_bis_guard_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["schemaRevision"], "recommended-bis-v1-guard-state-v1")
        runner.assert_called_once_with(mode="scheduled")

    def test_community_best_guard_sync_uses_postgres_native_runner(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            community_best_guard_sync,
            "sync_community_best_guard_postgres",
            return_value={
                "runner": "postgres",
                "schemaRevision": "community-best-v2-guard-state-v1",
                "status": "partial",
                "guardMode": "readiness_only",
            },
        ) as runner, redirect_stdout(stdout):
            exit_code = community_best_guard_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["schemaRevision"], "community-best-v2-guard-state-v1")
        runner.assert_called_once_with(mode="scheduled")

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

    def test_community_template_sync_uses_daily_incremental_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
                "WOW_COMMUNITY_TEMPLATE_SYNC_MODE": "daily_incremental",
            },
            clear=False,
        ), patch.object(
            community_template_sync.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            side_effect=AssertionError("daily_incremental must use the daily orchestrator"),
        ), patch.object(
            community_template_sync,
            "sync_community_template_daily_incremental_postgres",
            return_value={
                "schemaRevision": "community-template-daily-incremental-v1",
                "status": "completed",
                "sourceStatus": "verified",
                "runner": "postgres-daily-incremental",
            },
            create=True,
        ) as runner, redirect_stdout(stdout):
            exit_code = community_template_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres-daily-incremental")
        runner.assert_called_once_with(mode="daily_incremental")

    def test_community_template_sync_uses_availability_restore_runner_in_postgres_only_mode(self):
        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
                "WOW_COMMUNITY_TEMPLATE_SYNC_MODE": "restore_availability",
            },
            clear=False,
        ), patch.object(
            community_template_sync.sqlite3,
            "connect",
            side_effect=AssertionError("sqlite3.connect must not be reached in PG-only mode"),
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            side_effect=AssertionError("restore_availability must not run full sync"),
        ), patch.object(
            community_template_sync,
            "restore_community_template_availability_postgres",
            return_value={
                "schemaRevision": "community-template-availability-repair-v1",
                "status": "completed",
                "sourceStatus": "verified",
                "runner": "postgres-availability-repair",
            },
            create=True,
        ) as runner, redirect_stdout(stdout):
            exit_code = community_template_sync.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres-availability-repair")
        runner.assert_called_once_with(mode="restore_availability")

    def test_daily_incremental_restores_availability_before_refreshing_targets(self):
        calls = []
        saved_states = []
        complete_preflight = {
            "status": "verified",
            "targetQueue": [],
            "communityBest": {"completeSpecCount": 40, "partialSpecCount": 0, "pendingSpecCount": 0, "blockedSpecCount": 0},
            "baseline": {"availableSpecCount": 40, "blockedSpecCount": 0},
            "canonicalSlotMatrix": {"totalSlotCount": 640, "readySlotCount": 640, "missingSlotCount": 0},
            "realCommunityTemplates": {"coveredSpecCount": 40, "missingSpecCount": 0},
        }

        class FakeStore:
            def restore_community_template_availability(self, checked_at=""):
                calls.append(("restore_availability", checked_at))
                return {
                    "status": "completed",
                    "availabilityExpiresAt": "2026-07-20T00:00:00+00:00",
                    "talentRestored": 80,
                    "gearRestored": 40,
                }

            def save_sync_state(self, key, value, updated_at=""):
                saved_states.append((key, value, updated_at))

            def community_gear_template_counts(self):
                return {"total": 80, "verified": 40, "partial": 0, "blocked": 0}

        def fake_sync(**kwargs):
            calls.append(("sync", kwargs.get("mode")))
            return {
                "scanRunId": "talent-missing-slots-run",
                "runner": "postgres",
                "mode": kwargs.get("mode"),
                "status": "completed",
                "sourceStatus": "verified",
                "scanCoverage": {"totalHeroSlotCount": 80, "verifiedHeroSlotCount": 80},
                "talents": {"templates": {"total": 80, "verified": 80, "blocked": 0}},
                "stageTimings": {"stages": [{"stage": "source_collection", "targetSlotCount": 0}]},
            }

        with patch.dict(
            os.environ,
            {"WOW_COMMUNITY_DAILY_GEAR_SKIP_WHEN_NO_TARGETS": "1"},
            clear=False,
        ), patch.object(
            community_template_sync,
            "cache_store_from_env",
            return_value=FakeStore(),
            create=True,
        ), patch.object(
            community_template_sync,
            "_community_gear_template_coverage_rows",
            return_value=[],
            create=True,
        ), patch.object(
            community_template_sync,
            "build_community_gear_template_preflight",
            return_value=complete_preflight,
            create=True,
        ), patch.object(
            community_template_sync,
            "_gear_first_sync_target_specs",
            return_value=[],
            create=True,
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            side_effect=fake_sync,
        ):
            payload = community_template_sync.sync_community_template_daily_incremental_postgres()

        self.assertEqual(calls[0][0], "restore_availability")
        self.assertEqual(calls[1], ("sync", "missing_slots"))
        self.assertEqual(payload["availabilityRepair"]["talentRestored"], 80)
        self.assertEqual(payload["availabilityRepair"]["gearRestored"], 40)
        self.assertEqual(saved_states[0][0], websim_payload.COMMUNITY_TEMPLATE_SYNC_RUN_KEY)

    def test_daily_incremental_skips_gear_collection_when_preflight_has_no_targets(self):
        calls = []
        saved_states = []
        complete_preflight = {
            "status": "verified",
            "targetQueue": [],
            "communityBest": {"completeSpecCount": 40, "partialSpecCount": 0, "pendingSpecCount": 0, "blockedSpecCount": 0},
            "baseline": {"availableSpecCount": 40, "blockedSpecCount": 0},
            "canonicalSlotMatrix": {"totalSlotCount": 640, "readySlotCount": 640, "missingSlotCount": 0},
            "realCommunityTemplates": {"coveredSpecCount": 40, "missingSpecCount": 0},
        }

        class FakeStore:
            def save_sync_state(self, key, value, updated_at=""):
                saved_states.append((key, value, updated_at))

            def community_gear_template_counts(self):
                return {"total": 77, "verified": 75, "partial": 2, "blocked": 0}

        def fake_sync(**kwargs):
            calls.append(kwargs)
            return {
                "scanRunId": "talent-missing-slots-run",
                "runner": "postgres",
                "mode": kwargs.get("mode"),
                "status": "completed",
                "sourceStatus": "verified",
                "scanCoverage": {"totalHeroSlotCount": 80, "verifiedHeroSlotCount": 80},
                "talents": {"templates": {"total": 80, "verified": 80, "blocked": 0}},
                "stageTimings": {"stages": [{"stage": "source_collection", "targetSlotCount": 0}]},
            }

        with patch.dict(
            os.environ,
            {"WOW_COMMUNITY_DAILY_GEAR_SKIP_WHEN_NO_TARGETS": "1"},
            clear=False,
        ), patch.object(
            community_template_sync,
            "cache_store_from_env",
            return_value=FakeStore(),
            create=True,
        ), patch.object(
            community_template_sync,
            "_community_gear_template_coverage_rows",
            return_value=[],
            create=True,
        ), patch.object(
            community_template_sync,
            "build_community_gear_template_preflight",
            return_value=complete_preflight,
            create=True,
        ), patch.object(
            community_template_sync,
            "_gear_first_sync_target_specs",
            return_value=[],
            create=True,
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            side_effect=fake_sync,
        ):
            payload = community_template_sync.sync_community_template_daily_incremental_postgres()

        self.assertEqual([call["mode"] for call in calls], ["missing_slots"])
        self.assertTrue(payload["gear"]["skipped"])
        self.assertEqual(payload["gear"]["skipReason"], "no_gear_template_targets")
        self.assertEqual(payload["changeReport"]["summary"]["unchanged"], 160)
        self.assertIn("blocked", payload["changeReport"]["summary"])
        self.assertEqual(saved_states[0][0], websim_payload.COMMUNITY_TEMPLATE_SYNC_RUN_KEY)

    def test_daily_incremental_runs_targeted_gear_refresh_when_preflight_has_targets(self):
        calls = []
        target_preflight = {
            "status": "partial",
            "targetQueue": [
                {
                    "targetType": "gear_template",
                    "templateSlot": "community_best",
                    "specId": "mage:frost",
                    "targetKey": "gear-template:mage:frost:community_best",
                    "status": "partial",
                }
            ],
            "communityBest": {"completeSpecCount": 39, "partialSpecCount": 1, "pendingSpecCount": 0, "blockedSpecCount": 0},
            "baseline": {"availableSpecCount": 40, "blockedSpecCount": 0},
            "canonicalSlotMatrix": {"totalSlotCount": 640, "readySlotCount": 638, "missingSlotCount": 2},
            "realCommunityTemplates": {"coveredSpecCount": 39, "missingSpecCount": 1},
        }

        class FakeStore:
            def save_sync_state(self, key, value, updated_at=""):
                return None

            def community_gear_template_counts(self):
                return {"total": 77, "verified": 74, "partial": 3, "blocked": 0}

        def fake_sync(**kwargs):
            calls.append(kwargs)
            if kwargs.get("mode") == "gear_template_targeted_refresh":
                return {
                    "scanRunId": "gear-targeted-run",
                    "runner": "postgres",
                    "mode": kwargs.get("mode"),
                    "status": "completed",
                    "sourceStatus": "partial",
                    "gear": {
                        "preflight": target_preflight,
                        "observedBackfill": {"variantCount": 4, "verifiedCount": 2, "partialCount": 2},
                    },
                    "stageTimings": {"stages": [{"stage": "gear_observed_backfill", "variantCount": 4}]},
                }
            return {
                "scanRunId": "talent-missing-slots-run",
                "runner": "postgres",
                "mode": kwargs.get("mode"),
                "status": "completed",
                "sourceStatus": "verified",
                "talents": {"templates": {"total": 80, "verified": 80, "blocked": 0}},
                "stageTimings": {"stages": [{"stage": "source_collection", "targetSlotCount": 0}]},
            }

        with patch.object(
            community_template_sync,
            "cache_store_from_env",
            return_value=FakeStore(),
            create=True,
        ), patch.object(
            community_template_sync,
            "_community_gear_template_coverage_rows",
            return_value=[],
            create=True,
        ), patch.object(
            community_template_sync,
            "build_community_gear_template_preflight",
            return_value=target_preflight,
            create=True,
        ), patch.object(
            community_template_sync,
            "_gear_first_sync_target_specs",
            return_value=["mage:frost"],
            create=True,
        ), patch.object(
            community_template_sync,
            "sync_community_template_cache_postgres",
            side_effect=fake_sync,
        ):
            payload = community_template_sync.sync_community_template_daily_incremental_postgres()

        self.assertEqual([call["mode"] for call in calls], ["missing_slots", "gear_template_targeted_refresh"])
        self.assertTrue(calls[1]["refresh_raiderio"])
        self.assertEqual(payload["gear"]["targetSpecIds"], ["mage:frost"])
        self.assertEqual(payload["changeReport"]["summary"]["candidate_only"], 4)

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

    def test_item_metadata_refresh_main_uses_postgres_gap_runner(self):
        from server import item_metadata_refresh

        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            item_metadata_refresh,
            "refresh_websim_item_metadata_gaps_postgres",
            return_value={"runner": "postgres", "items": 1, "errors": [], "gapCount": 1},
        ) as runner, redirect_stdout(stdout):
            exit_code = item_metadata_refresh.main(["--from-community-template-gaps", "--limit", "3"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["items"], 1)
        runner.assert_called_once()

    def test_item_metadata_refresh_main_uses_postgres_item_gap_runner(self):
        from server import item_metadata_refresh

        stdout = io.StringIO()

        with patch.dict(
            os.environ,
            {"WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test", "WOW_DATABASE_RUNTIME": "postgres_only"},
            clear=False,
        ), patch.object(
            item_metadata_refresh,
            "refresh_websim_item_metadata_item_gaps_postgres",
            return_value={"runner": "postgres", "items": 1, "errors": [], "gapCount": 1},
        ) as runner, redirect_stdout(stdout):
            exit_code = item_metadata_refresh.main(["--from-websim-item-gaps", "--limit", "3"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["items"], 1)
        runner.assert_called_once()

    def test_item_metadata_refresh_main_loads_env_file_before_postgres_check(self):
        from server import item_metadata_refresh

        stdout = io.StringIO()

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as env_file:
            env_file.write("WOW_DATABASE_RUNTIME=postgres_only\n")
            env_file.write("WOW_DATABASE_URL=postgresql://wow_app@localhost/wow_test\n")
            env_path = env_file.name
        self.addCleanup(lambda: os.path.exists(env_path) and os.unlink(env_path))

        with patch.dict(os.environ, {}, clear=True), patch.object(
            item_metadata_refresh,
            "refresh_websim_item_metadata_gaps_postgres",
            return_value={"runner": "postgres", "items": 1, "errors": [], "gapCount": 1},
        ) as runner, redirect_stdout(stdout):
            exit_code = item_metadata_refresh.main(["--env-file", env_path, "--from-community-template-gaps"])

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
