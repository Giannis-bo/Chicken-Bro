import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FormalChickenbroNativeMcpTest(unittest.TestCase):
    def test_event_options_are_forwarded_to_server_gateway(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        options = {"dataType": "Casts", "startTime": 500, "endTime": 900, "limit": 1000}
        with patch.object(module, "query_source_gateway", return_value={"status": "verified"}) as query:
            module.handle_rpc_request({"id": 1, "method": "tools/call", "params": {
                "name": "query_warcraftlogs_report", "arguments": {
                    "target": "https://cn.warcraftlogs.com/reports/abc123?fight=4", "options": options}}})
        self.assertEqual(query.call_args.kwargs["options"], options)

    def test_gateway_accepts_managed_test_port_but_rejects_other_targets(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        for port in [8790, 8791, 8792]:
            self.assertTrue(module._source_gateway_target_is_local(
                f"http://127.0.0.1:{port}/api/v2/internal/chickenbro/source-query"))
        for target in [
            "http://127.0.0.1:6379/api/v2/internal/chickenbro/source-query",
            "https://example.com/api/v2/internal/chickenbro/source-query",
            "http://127.0.0.1:8792/unrelated", "http://user@127.0.0.1:8792/api/v2/internal/chickenbro/source-query",
        ]:
            self.assertFalse(module._source_gateway_target_is_local(target))

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
                "query_raiderio_rankings",
                "query_raiderio_characters",
            },
            {item["name"] for item in listed["result"]["tools"]},
        )
        self.assertTrue(
            all(item["annotations"]["readOnlyHint"] for item in listed["result"]["tools"])
        )

    def test_discovery_and_batch_use_capability_gateway_without_user_character_link(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        cases = [
            ("query_raiderio_rankings", {"className": "shaman", "spec": "enhancement", "offset": 10},
             "raiderio_rankings", "rankings"),
            ("query_raiderio_characters", {"targets": ["https://raider.io/characters/eu/draenor/Example"]},
             "raiderio_batch", "characters"),
        ]
        for name, arguments, provider, target in cases:
            with self.subTest(name=name), patch.object(module, "query_source_gateway", return_value={"status": "source_reference"}) as query:
                module.handle_rpc_request({"id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
                query.assert_called_once_with(provider, target, options=arguments)

    def test_web_continuation_and_observation_preserve_scope_without_raw_query(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        arguments = {"target": "https://example.com/guide", "start": 6000, "match": "Overcharge"}
        observations = []
        packet = {"status": "partial", "reasonCode": "JS_SHELL", "facts": [], "evidence": [], "evidenceRefs": []}
        with patch.object(module, "build_public_web_research_tool_result", return_value=packet) as read:
            module.handle_rpc_request({"id": 1, "method": "tools/call", "params": {
                "name": "research_public_web", "arguments": arguments}}, observation_writer=observations.append)
        read.assert_called_once_with(arguments)
        self.assertGreaterEqual(observations[0]["elapsedMs"], 0)
        self.assertEqual(observations[0]["reasonCode"], "JS_SHELL")
        self.assertEqual(observations[0]["factCount"], 0)
        self.assertEqual(len(observations[0]["argumentsSha256"]), 64)
        self.assertNotIn("Overcharge", json.dumps(observations))

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
