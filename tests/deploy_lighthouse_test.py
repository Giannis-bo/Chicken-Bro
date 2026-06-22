import unittest
import re
from pathlib import Path


class DeployLighthouseScriptTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
