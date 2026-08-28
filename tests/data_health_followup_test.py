import unittest
from unittest.mock import patch


class DataHealthFollowupTest(unittest.TestCase):
    def gear_followup_health(self, revision="gear-r1", *, refresh_needed=False):
        details = {
            "catalogContract": {"revision": revision},
            "variantRevision": revision,
            "refreshNeeded": refresh_needed,
        }
        if not revision:
            details = {"refreshNeeded": refresh_needed}
        return {
            "components": [
                {
                    "key": "gear_catalog",
                    "status": "partial",
                    "details": details,
                    "blockers": ["observed variants remain partial"],
                },
                {
                    "key": "websim_sync",
                    "status": "blocked",
                    "details": {},
                    "blockers": ["gear catalog is partial"],
                },
            ]
        }

    def test_first_seen_gear_revision_records_baseline_without_starting_sync(self):
        from server.data_health_followup import followup_state_after_plan, plan_followup_actions

        plan = plan_followup_actions(self.gear_followup_health("gear-r1"), prior_state={})

        self.assertEqual(plan["actions"], [])
        self.assertIn("gear_observed_backfill:baseline_recorded", plan["reportOnly"])
        state = followup_state_after_plan({}, plan)
        self.assertEqual(state["actions"]["gear_observed_backfill"]["lastSeenRevision"], "gear-r1")
        self.assertEqual(state["actions"]["gear_observed_backfill"]["lastReportOnlyReason"], "baseline_recorded")
        self.assertTrue(state["actions"]["gear_observed_backfill"]["lastDecisionAt"].endswith("+00:00"))
        self.assertNotIn("websim_sync", state["actions"])

    def test_changed_gear_revision_starts_only_observed_backfill_once(self):
        from server.data_health_followup import plan_followup_actions

        plan = plan_followup_actions(
            self.gear_followup_health("gear-r2"),
            prior_state={
                "actions": {
                    "gear_observed_backfill": {
                        "lastSeenRevision": "gear-r1",
                        "lastAttemptedRevision": "gear-r1",
                    }
                }
            },
        )

        self.assertEqual([action["key"] for action in plan["actions"]], ["gear_observed_backfill"])
        self.assertEqual(plan["actions"][0]["inputRevision"], "gear-r2")
        self.assertEqual(plan["actions"][0]["decision"], "revision_changed")
        self.assertNotIn("websim_sync", [action["key"] for action in plan["actions"]])

    def test_unchanged_gear_revision_stays_report_only_after_attempt(self):
        from server.data_health_followup import plan_followup_actions

        plan = plan_followup_actions(
            self.gear_followup_health("gear-r1"),
            prior_state={
                "actions": {
                    "gear_observed_backfill": {
                        "lastSeenRevision": "gear-r1",
                        "lastAttemptedRevision": "gear-r1",
                    }
                }
            },
        )

        self.assertEqual(plan["actions"], [])
        self.assertIn("gear_observed_backfill:unchanged_revision", plan["reportOnly"])

    def test_explicit_refresh_starts_unattempted_current_revision_once(self):
        from server.data_health_followup import plan_followup_actions

        plan = plan_followup_actions(
            self.gear_followup_health("gear-r1", refresh_needed=True),
            prior_state={"actions": {"gear_observed_backfill": {"lastSeenRevision": "gear-r1"}}},
        )

        self.assertEqual([action["key"] for action in plan["actions"]], ["gear_observed_backfill"])
        self.assertEqual(plan["actions"][0]["decision"], "refresh_requested")

    def test_talent_graph_recovery_requires_explicit_manual_force_action(self):
        from server.data_health_followup import plan_followup_actions

        plan = plan_followup_actions({}, force_actions=("talent_graph_recovery",))

        self.assertEqual([action["key"] for action in plan["actions"]], ["talent_graph_recovery"])
        self.assertTrue(plan["actions"][0]["manualOnly"])
        self.assertEqual(plan["actions"][0]["unit"], "wow-talent-graph-recovery.service")

    def test_unknown_force_action_is_rejected_before_reading_or_writing_the_ledger(self):
        from server import data_health_followup

        with patch.object(data_health_followup, "followup_state_store") as state_store:
            with self.assertRaises(SystemExit) as raised:
                data_health_followup.main(["--force-action", "unknown_recovery"])

        self.assertEqual(raised.exception.code, 2)
        state_store.assert_not_called()

    def test_forced_talent_recovery_claims_the_ledger_before_starting_the_manual_unit(self):
        from server import data_health_followup

        class FakeStore:
            def __init__(self):
                self.saved = []

            def get_sync_state(self, key):
                return {}

            def save_sync_state(self, key, value):
                self.saved.append((key, value))

        store = FakeStore()

        def execute_after_claim(action):
            self.assertTrue(store.saved)
            self.assertEqual(store.saved[0][1]["actions"]["talent_graph_recovery"]["lastDecision"], "forced")
            return {"key": action["key"], "status": "ok", "exitCode": 0}

        with patch.object(data_health_followup, "fetch_health", return_value={"components": []}), patch.object(
            data_health_followup, "followup_state_store", return_value=store
        ), patch.object(data_health_followup, "execute_action", side_effect=execute_after_claim) as execute_action:
            self.assertEqual(data_health_followup.main(["--execute", "--force-action", "talent_graph_recovery"]), 0)

        self.assertEqual([call.args[0]["key"] for call in execute_action.call_args_list], ["talent_graph_recovery"])

    def test_execute_persists_baseline_before_any_followup_action(self):
        from server import data_health_followup

        class FakeStore:
            def __init__(self):
                self.saved = []

            def get_sync_state(self, key):
                self.read_key = key
                return {}

            def save_sync_state(self, key, value):
                self.saved.append((key, value))
                return {"ok": True}

        store = FakeStore()
        with patch.object(data_health_followup, "fetch_health", return_value=self.gear_followup_health("gear-r1")), patch.object(
            data_health_followup,
            "followup_state_store",
            return_value=store,
        ):
            self.assertEqual(data_health_followup.main(["--execute"]), 0)

        self.assertEqual(store.read_key, "data_health_followup_v1")
        self.assertEqual(store.saved[0][0], "data_health_followup_v1")
        self.assertEqual(store.saved[0][1]["actions"]["gear_observed_backfill"]["lastSeenRevision"], "gear-r1")

    def test_state_store_failure_is_report_only_and_executes_no_action(self):
        from server import data_health_followup

        health = {
            "components": [
                {"key": "news", "status": "partial", "details": {"retryableCount": 1}},
                {
                    "key": "gear_catalog",
                    "status": "partial",
                    "details": {"catalogContract": {"revision": "gear-r1"}, "refreshNeeded": True},
                },
            ]
        }
        with patch.object(data_health_followup, "fetch_health", return_value=health), patch.object(
            data_health_followup, "followup_state_store", return_value=None
        ), patch.object(data_health_followup, "execute_action") as execute_action:
            self.assertEqual(data_health_followup.main(["--execute"]), 1)

        execute_action.assert_not_called()

    def test_malformed_health_payload_is_report_only_without_reading_or_writing_state(self):
        from server import data_health_followup

        with patch.object(data_health_followup, "fetch_health", return_value=["not a health payload"]), patch.object(
            data_health_followup, "followup_state_store"
        ) as state_store, patch.object(data_health_followup, "execute_action") as execute_action:
            self.assertEqual(data_health_followup.main(["--execute"]), 1)

        state_store.assert_not_called()
        execute_action.assert_not_called()

    def test_state_store_failure_is_nonzero_only_for_execute_mode(self):
        from server import data_health_followup

        with patch.object(data_health_followup, "fetch_health", return_value={"components": []}), patch.object(
            data_health_followup, "followup_state_store", return_value=None
        ):
            self.assertEqual(data_health_followup.main([]), 0)

    def test_read_only_plan_does_not_claim_or_write_the_followup_ledger(self):
        from server import data_health_followup

        class FakeStore:
            def __init__(self):
                self.saved = []

            def get_sync_state(self, key):
                return {}

            def save_sync_state(self, key, value):
                self.saved.append((key, value))

        store = FakeStore()
        with patch.object(data_health_followup, "fetch_health", return_value=self.gear_followup_health("gear-r1")), patch.object(
            data_health_followup, "followup_state_store", return_value=store
        ):
            self.assertEqual(data_health_followup.main([]), 0)
        self.assertEqual(store.saved, [])

    def test_stat_weight_revision_keeps_all_available_input_revisions(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "stat_weights",
                    "status": "partial",
                    "details": {
                        "blockedCount": 1,
                        "gearCatalogRevision": "gear-r2",
                        "raiderioRevision": "rio-r4",
                        "simcRuntimeRevision": "simc-r3",
                    },
                }
            ]
        }
        plan = plan_followup_actions(
            health,
            prior_state={"actions": {"stat_weights_sync": {"lastSeenRevision": "gearCatalogRevision:gear-r1"}}},
        )

        self.assertEqual([action["key"] for action in plan["actions"]], ["stat_weights_sync"])
        self.assertEqual(
            plan["actions"][0]["inputRevision"],
            "gearCatalogRevision:gear-r2|raiderioRevision:rio-r4|simcRuntimeRevision:simc-r3",
        )

    def test_formal_active_manifest_blocks_automatic_simc_runtime_upgrade(self):
        from server.data_health_followup import followup_state_after_plan, plan_followup_actions

        health = {
            "components": [
                {
                    "key": "active_manifest",
                    "status": "verified",
                    "details": {
                        "formalActiveManifest": True,
                        "simcRuntimeRevision": "simc-r1",
                    },
                },
                {
                    "key": "template_simc_bridge",
                    "status": "partial",
                    "details": {
                        "simcraftVersion": {
                            "simcRuntimeRevision": "simc-r1",
                            "latestCommit": "simc-r2",
                            "updateAvailable": True,
                        }
                    },
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual(plan["actions"], [])
        self.assertIn(
            "simc_runtime_update:active_manifest_cutover_required",
            plan["reportOnly"],
        )
        state = followup_state_after_plan({}, plan)
        self.assertEqual(
            state["actions"]["simc_runtime_update"]["lastReportOnlyReason"],
            "active_manifest_cutover_required",
        )

    def test_missing_active_manifest_blocks_automatic_simc_runtime_upgrade(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "template_simc_bridge",
                    "status": "partial",
                    "details": {
                        "simcraftVersion": {
                            "latestCommit": "simc-r2",
                            "updateAvailable": True,
                        }
                    },
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual(plan["actions"], [])
        self.assertIn(
            "simc_runtime_update:active_manifest_state_unavailable",
            plan["reportOnly"],
        )
        self.assertIn(
            "simc_runtime_update_active_manifest_state_unavailable",
            plan["manualBlockers"],
        )

    def test_invalid_active_manifest_blocks_automatic_simc_runtime_upgrade(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "active_manifest",
                    "status": "blocked",
                    "details": {
                        "formalActiveManifest": False,
                        "pointerMode": "invalid",
                    },
                },
                {
                    "key": "template_simc_bridge",
                    "status": "partial",
                    "details": {
                        "simcraftVersion": {
                            "latestCommit": "simc-r2",
                            "updateAvailable": True,
                        }
                    },
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual(plan["actions"], [])
        self.assertIn(
            "simc_runtime_update:active_manifest_state_unavailable",
            plan["reportOnly"],
        )

    def test_simc_update_uses_revision_from_component_reporting_the_update(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "active_manifest",
                    "status": "partial",
                    "details": {
                        "formalActiveManifest": False,
                        "pointerMode": "pre_cutover",
                    },
                },
                {
                    "key": "template_simc_bridge",
                    "status": "verified",
                    "details": {
                        "simcraftVersion": {
                            "latestCommit": "simc-old",
                            "updateAvailable": False,
                        }
                    },
                },
                {
                    "key": "season_cutover_readiness",
                    "status": "partial",
                    "details": {
                        "gates": {
                            "simcRuntime": {
                                "latestCommit": "simc-new",
                                "updateAvailable": True,
                            }
                        }
                    },
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual([action["key"] for action in plan["actions"]], ["simc_runtime_update"])
        self.assertEqual(plan["actions"][0]["inputRevision"], "simc-new")

    def test_default_health_url_uses_backend_port_not_nginx(self):
        from server.data_health_followup import DEFAULT_HEALTH_URL

        self.assertEqual(DEFAULT_HEALTH_URL, "http://127.0.0.1:8787/api/data/health")

    def test_missing_heavy_input_revisions_are_report_only(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "active_manifest",
                    "status": "partial",
                    "details": {
                        "formalActiveManifest": False,
                        "pointerMode": "pre_cutover",
                    },
                },
                {
                    "key": "news",
                    "status": "partial",
                    "details": {"retryableCount": 2, "queuedCount": 0},
                    "blockers": [],
                },
                {
                    "key": "gear_catalog",
                    "status": "partial",
                    "details": {"partialCount": 568, "verifiedCount": 0},
                    "blockers": [],
                },
                {
                    "key": "websim_sync",
                    "status": "blocked",
                    "details": {},
                    "blockers": ["gear catalog is partial"],
                },
                {
                    "key": "stat_weights",
                    "status": "partial",
                    "details": {"blockedCount": 87},
                    "blockers": [],
                },
                {
                    "key": "season_cutover_readiness",
                    "status": "blocked",
                    "details": {
                        "gates": {
                            "simcRuntime": {"status": "partial", "updateAvailable": True},
                        }
                    },
                    "blockers": ["gearCatalogRevision is missing"],
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual([action["key"] for action in plan["actions"]], ["news_refresh"])
        self.assertEqual(
            plan["manualBlockers"],
            [
                "simc_runtime_update_input_revision_missing",
                "gear_observed_backfill_input_revision_missing",
                "stat_weights_sync_input_revision_missing",
            ],
        )
        self.assertNotIn("websim_sync", [action["key"] for action in plan["actions"]])

    def test_unchanged_partial_health_does_not_start_full_sync_chain(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "news",
                    "status": "partial",
                    "details": {"retryableCount": 2, "queuedCount": 0},
                    "blockers": [],
                },
                {
                    "key": "gear_catalog",
                    "status": "partial",
                    "details": {"partialCount": 568, "verifiedCount": 0},
                    "blockers": [],
                },
                {
                    "key": "websim_sync",
                    "status": "blocked",
                    "details": {},
                    "blockers": ["gear catalog is partial"],
                },
                {
                    "key": "stat_weights",
                    "status": "partial",
                    "details": {"blockedCount": 87},
                    "blockers": [],
                },
                {
                    "key": "season_cutover_readiness",
                    "status": "blocked",
                    "details": {
                        "gates": {
                            "simcRuntime": {"status": "ready", "updateAvailable": False},
                        }
                    },
                    "blockers": ["gearCatalogRevision is missing"],
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual([action["key"] for action in plan["actions"]], ["news_refresh"])
        self.assertEqual(
            plan["manualBlockers"],
            ["gear_observed_backfill_input_revision_missing", "stat_weights_sync_input_revision_missing"],
        )
        self.assertNotIn("websim_sync", [action["key"] for action in plan["actions"]])

    def test_wcl_no_target_slots_is_report_only_when_templates_are_verified(self):
        from server.data_health_followup import plan_followup_actions

        health = {
            "components": [
                {
                    "key": "community_templates",
                    "status": "partial",
                    "blockers": ["Warcraft Logs ranking extraction has no target slots for this sync run."],
                    "details": {"templates": {"verified": 80, "blocked": 0, "partial": 0}},
                }
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["reportOnly"], ["community_templates_wcl_no_target_slots"])

    def test_systemd_actions_use_sudo_and_preserve_no_block_flag(self):
        from server.data_health_followup import execute_action

        calls = []

        class Completed:
            returncode = 0

        def fake_run(command, check=False):
            calls.append(command)
            return Completed()

        with patch("server.data_health_followup._unit_active", return_value=False), patch(
            "server.data_health_followup.subprocess.run", side_effect=fake_run
        ):
            result = execute_action(
                {
                    "key": "websim_sync",
                    "kind": "systemd",
                    "unit": "wow-websim-sync.service",
                    "noBlock": True,
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls, [["sudo", "systemctl", "--no-block", "start", "wow-websim-sync.service"]])

    def test_systemd_active_check_treats_activating_units_as_running(self):
        from server.data_health_followup import _unit_active

        class Completed:
            returncode = 3
            stdout = "activating\n"

        with patch("server.data_health_followup.subprocess.run", return_value=Completed()) as run:
            self.assertTrue(_unit_active("wow-simc-runtime-update.service"))

        run.assert_called_once_with(
            ["systemctl", "is-active", "wow-simc-runtime-update.service"],
            check=False,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
