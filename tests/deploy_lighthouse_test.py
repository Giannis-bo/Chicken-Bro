import unittest
import re
from pathlib import Path


class DeployLighthouseScriptTest(unittest.TestCase):
    def test_stat_snapshot_worker_is_one_long_lived_hardened_service_enabled_by_deploy(self):
        service = Path("server/wow-gear-stat-snapshot-worker.service").read_text(encoding="utf-8")
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")

        self.assertIn("python3 -m server.gear_stat_snapshot_worker", service)
        self.assertIn("Restart=always", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("ProtectHome=read-only", service)
        self.assertIn("PrivateTmp=true", service)
        self.assertIn('wow-gear-stat-snapshot-worker.service"', script)
        self.assertIn("enable wow-gear-stat-snapshot-worker.service", script)
        self.assertIn("restart wow-gear-stat-snapshot-worker.service", script)

    def test_deploy_script_prepares_codex_cli_worker_without_danger_full_access(self):
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")

        self.assertIn("https://chatgpt.com/codex/install.sh", script)
        self.assertIn("https://api.github.com/repos/openai/codex/releases/latest", script)
        self.assertIn('target = "x86_64-unknown-linux-musl"', script)
        self.assertIn('package_asset = f"codex-package-{target}.tar.gz"', script)
        self.assertIn("WOW_CODEX_JOBS_DIR", script)
        self.assertIn("/var/lib/wow-backend/codex-jobs", script)
        self.assertIn("cli_auth_credentials_store = \"file\"", script)
        self.assertIn('CODEX_JOBS_DIR="${WOW_CODEX_JOBS_DIR:-/var/lib/wow-backend/codex-jobs}"', script)
        self.assertIn('[projects."${CODEX_JOBS_DIR}"]', script)
        self.assertNotIn("WOW_CODEX_SANDBOX=danger-full-access", script)

    def test_deploy_script_rejects_traversal_in_remote_paths(self):
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")

        self.assertIn("reject_path_traversal REMOTE_DIR", script)
        self.assertIn("reject_path_traversal CODEX_JOBS_DIR", script)
        self.assertIn("reject_path_traversal CODEX_HOME_DIR", script)

    def test_deploy_script_can_reuse_existing_simc_when_github_lookup_fails(self):
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")

        self.assertIn("latest_simc_commit=\"\"", script)
        self.assertIn("if ! latest_simc_commit=", script)
        self.assertIn("Reusing existing SimulationCraft binary", script)
        self.assertIn("SimulationCraft is not installed and GitHub version lookup failed.", script)
        self.assertIn("SimulationCraft source download failed", script)

    def test_systemd_service_exposes_codex_worker_environment(self):
        service = Path("server/wow-backend.service").read_text(encoding="utf-8")

        self.assertIn("Environment=WOW_CODEX_BIN=/usr/local/bin/codex", service)
        self.assertIn("Environment=WOW_CODEX_HOME=/home/ubuntu/.codex", service)
        self.assertIn("Environment=WOW_CODEX_JOBS_DIR=/var/lib/wow-backend/codex-jobs", service)
        self.assertIn("Environment=WOW_CODEX_SANDBOX=workspace-write", service)
        self.assertIn("/home/ubuntu/.local/bin", service)

    def test_websim_sync_service_budget_covers_full_season_gear_catalog(self):
        service = Path("server/wow-websim-sync.service").read_text(encoding="utf-8")
        env = dict(re.findall(r"^Environment=([^=]+)=(.+)$", service, flags=re.MULTILINE))
        exec_start_match = re.search(r"^ExecStart=(.+)$", service, flags=re.MULTILINE)
        self.assertIsNotNone(exec_start_match)
        exec_start = exec_start_match.group(1)
        self.assertIn("/usr/bin/env", exec_start)

        expected_budgets = {
            "WOW_WEBSIM_SYNC_INSTANCE_LIMIT": 20,
            "WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT": 8,
            "WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT": 200,
            "WOW_WEBSIM_SYNC_ITEM_LIMIT": 1000,
            "WOW_WEBSIM_SYNC_ITEM_SET_LIMIT": 40,
            "WOW_WEBSIM_SYNC_OBSERVED_ITEM_LIMIT": 300,
            "WOW_RAIDERIO_RUN_PAGES": 20,
            "WOW_RAIDERIO_PROFILE_LIMIT": 160,
            "WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC": 4,
            "WOW_RAIDERIO_TARGET_ITEM_LIMIT": 500,
            "WOW_RAIDERIO_TARGET_PROFILE_LIMIT": 800,
            "WOW_RAIDERIO_TIMEOUT_SECONDS": 45,
        }
        for key, minimum in expected_budgets.items():
            self.assertGreaterEqual(int(env[key]), minimum)
            runtime_match = re.search(rf"\b{key}=(\d+)\b", exec_start)
            self.assertIsNotNone(runtime_match)
            self.assertGreaterEqual(int(runtime_match.group(1)), minimum)

    def test_observed_backfill_service_uses_independent_runner_with_short_timeout(self):
        service = Path("server/wow-gear-observed-backfill.service").read_text(encoding="utf-8")
        timer = Path("server/wow-gear-observed-backfill.timer").read_text(encoding="utf-8")
        env = dict(re.findall(r"^Environment=([^=]+)=(.+)$", service, flags=re.MULTILINE))
        exec_start_match = re.search(r"^ExecStart=(.+)$", service, flags=re.MULTILINE)

        self.assertIsNotNone(exec_start_match)
        exec_start = exec_start_match.group(1)
        self.assertIn("/usr/bin/flock", exec_start)
        self.assertIn("wow-gear-observed-backfill.lock", exec_start)
        self.assertIn("/opt/wow-mini-program/server/gear_observed_backfill.py", exec_start)
        self.assertIn("--simc-stats", exec_start)
        self.assertIn("--full-profile-gear", exec_start)
        self.assertIn("--simc-timeout-seconds 90", exec_start)
        self.assertNotIn("/opt/wow-mini-program/server/websim_sync.py", exec_start)
        self.assertEqual(env["WOW_GEAR_OBSERVED_BACKFILL_TARGET_LIMIT"], "80")
        self.assertEqual(env["WOW_GEAR_OBSERVED_BACKFILL_PROFILE_LIMIT"], "40")
        self.assertEqual(env["WOW_GEAR_OBSERVED_BACKFILL_TIMEOUT_SECONDS"], "600")
        self.assertEqual(env["WOW_GEAR_OBSERVED_BACKFILL_SIMC_STATS"], "1")
        self.assertEqual(env["WOW_GEAR_OBSERVED_BACKFILL_SIMC_TIMEOUT_SECONDS"], "90")
        timeout_match = re.search(r"^TimeoutStartSec=(\d+)min$", service, flags=re.MULTILINE)
        self.assertIsNotNone(timeout_match)
        self.assertLessEqual(int(timeout_match.group(1)), 15)
        self.assertIn("OnUnitActiveSec=45min", timer)
        self.assertIn("Persistent=true", timer)

    def test_deploy_script_installs_observed_backfill_timer_without_enabling_or_starting(self):
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")

        self.assertIn('wow-gear-observed-backfill.service"', script)
        self.assertIn('wow-gear-observed-backfill.timer"', script)
        self.assertNotIn("enable --now wow-gear-observed-backfill.timer", script)
        self.assertNotIn("start --no-block wow-gear-observed-backfill.service", script)
        self.assertNotIn("start wow-gear-observed-backfill.service", script)

    def test_deploy_script_installs_season_recommended_gear_service_without_autostart(self):
        service = Path("server/wow-season-recommended-gear-sync.service").read_text(encoding="utf-8")
        script = Path("server/deploy_lighthouse.sh").read_text(encoding="utf-8")
        exec_start_match = re.search(r"^ExecStart=(.+)$", service, flags=re.MULTILINE)

        self.assertIsNotNone(exec_start_match)
        exec_start = exec_start_match.group(1)
        self.assertIn("/usr/bin/flock", exec_start)
        self.assertIn("/run/lock/wow-mini-program-sync.lock", exec_start)
        self.assertIn("/opt/wow-mini-program/server/season_recommended_gear_sync.py", exec_start)
        self.assertIn('wow-season-recommended-gear-sync.service"', script)
        self.assertNotIn("enable --now wow-season-recommended-gear-sync.service", script)
        self.assertNotIn("start --no-block wow-season-recommended-gear-sync.service", script)


if __name__ == "__main__":
    unittest.main()
