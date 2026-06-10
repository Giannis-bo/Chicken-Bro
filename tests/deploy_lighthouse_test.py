import unittest
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

    def test_systemd_service_exposes_codex_worker_environment(self):
        service = Path("server/wow-backend.service").read_text(encoding="utf-8")

        self.assertIn("Environment=WOW_CODEX_BIN=/usr/local/bin/codex", service)
        self.assertIn("Environment=WOW_CODEX_HOME=/home/ubuntu/.codex", service)
        self.assertIn("Environment=WOW_CODEX_JOBS_DIR=/var/lib/wow-backend/codex-jobs", service)
        self.assertIn("Environment=WOW_CODEX_SANDBOX=workspace-write", service)
        self.assertIn("/home/ubuntu/.local/bin", service)


if __name__ == "__main__":
    unittest.main()
