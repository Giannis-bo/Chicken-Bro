import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FormalChickenbroNativeMcpTest(unittest.TestCase):
    def test_toolbox_exposes_only_chat_owned_read_only_sources(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        listed = module.handle_rpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )

        self.assertEqual(
            {
                "research_public_web",
                "query_warcraftlogs_report",
                "query_raiderio_character",
            },
            {item["name"] for item in listed["result"]["tools"]},
        )
        self.assertTrue(
            all(item["annotations"]["readOnlyHint"] for item in listed["result"]["tools"])
        )

    def test_toolbox_has_no_legacy_news_or_cached_mythic_plus_dependency(self):
        source = (ROOT / "server/chickenbro_native_mcp.py").read_text(encoding="utf-8")

        self.assertNotIn("news_backend", source)
        self.assertNotIn("inspect_current_mythic_plus_snapshot", source)

    def test_candidate_and_cutover_packages_own_the_toolbox_and_profile(self):
        for relative_path, profile_name in (
            (
                "server/deploy_chickenbro_candidate_lighthouse.sh",
                "chickenbro-candidate",
            ),
            (
                "server/cutover_chickenbro_lighthouse.sh",
                "chickenbro-production",
            ),
        ):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("server/chickenbro_native_mcp.py", source, relative_path)
            self.assertIn("server/chickenbro_public_web_research.py", source, relative_path)
            self.assertIn(
                "scripts/chickenbro-native-agent/chickenbro-native.config.toml.template",
                source,
                relative_path,
            )
            self.assertIn(f"{profile_name}.config.toml", source, relative_path)
            self.assertIn("CODEX_PROFILE_IDENTITY", source, relative_path)

    def test_candidate_and_production_services_use_isolated_profiles(self):
        candidate = (ROOT / "server/chickenbro-api-candidate.service").read_text(
            encoding="utf-8"
        )
        production = (ROOT / "server/chickenbro-api.service").read_text(
            encoding="utf-8"
        )

        self.assertIn("Environment=WOW_CODEX_PROFILE=chickenbro-candidate", candidate)
        self.assertIn("Environment=WOW_CODEX_PROFILE=chickenbro-production", production)
        self.assertNotIn("WOW_CODEX_PROFILE=chickenbro-production", candidate)
        self.assertNotIn("WOW_CODEX_PROFILE=chickenbro-candidate", production)


if __name__ == "__main__":
    unittest.main()
