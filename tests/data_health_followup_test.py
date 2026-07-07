import unittest
from unittest.mock import patch


class DataHealthFollowupTest(unittest.TestCase):
    def test_default_health_url_uses_backend_port_not_nginx(self):
        from server.data_health_followup import DEFAULT_HEALTH_URL

        self.assertEqual(DEFAULT_HEALTH_URL, "http://127.0.0.1:8787/api/data/health")

    def test_plans_followup_actions_for_retriable_blockers(self):
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
                            "simcRuntime": {"status": "partial", "updateAvailable": True},
                        }
                    },
                    "blockers": ["gearCatalogRevision is missing"],
                },
            ]
        }

        plan = plan_followup_actions(health)

        self.assertEqual(
            [action["key"] for action in plan["actions"]],
            ["news_refresh", "simc_runtime_update"],
        )
        self.assertTrue(plan["actions"][1]["noBlock"])
        self.assertEqual(plan["actions"][1]["unit"], "wow-simc-runtime-update.service")
        self.assertEqual(plan["manualBlockers"], [])

    def test_plans_regular_followup_actions_when_simc_runtime_is_current(self):
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

        self.assertEqual(
            [action["key"] for action in plan["actions"]],
            ["news_refresh", "gear_observed_backfill", "websim_sync", "stat_weights_sync"],
        )
        self.assertNotIn("noBlock", plan["actions"][1])
        self.assertTrue(plan["actions"][2]["noBlock"])
        self.assertTrue(plan["actions"][3]["noBlock"])
        self.assertEqual(plan["manualBlockers"], [])

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
