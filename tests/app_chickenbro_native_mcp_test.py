import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FormalChickenbroNativeMcpTest(unittest.TestCase):
    def test_poe2_calculate_schema_exposes_only_engine_supported_changes(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        definitions = {item["name"]: item for item in module.handle_rpc_request(
            {"id": 1, "method": "tools/list"}, game="poe2")["result"]["tools"]}
        changes = definitions["poe2_calculate"]["inputSchema"]["properties"]["changes"]
        self.assertFalse(changes["additionalProperties"])
        self.assertEqual(set(changes["properties"]), {
            "level", "mainSocketGroup", "skillGroups", "items", "config",
            "allocateNodes", "deallocateNodes",
        })
        self.assertEqual(changes["properties"]["level"], {"type": "integer", "minimum": 1, "maximum": 100})
        group = changes["properties"]["skillGroups"]["items"]
        self.assertEqual(group["required"], ["index", "gems"])
        self.assertFalse(group["additionalProperties"])
        gem = group["properties"]["gems"]["items"]
        self.assertEqual(gem["required"], ["name", "level", "quality"])
        self.assertEqual(gem["properties"]["level"]["maximum"], 40)
        self.assertEqual(gem["properties"]["quality"]["maximum"], 30)
        item = changes["properties"]["items"]["items"]
        self.assertEqual(item["properties"]["slot"]["enum"], [
            "Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves",
            "Boots", "Amulet", "Ring 1", "Ring 2", "Belt",
        ])
        config = changes["properties"]["config"]
        self.assertFalse(config["additionalProperties"])
        self.assertEqual(set(config["properties"]), {
            "enemyLevel", "enemyIsBoss", "enemyPhysicalReduction", "enemyFireResist",
            "enemyColdResist", "enemyLightningResist", "enemyChaosResist",
            "conditionEnemyShocked", "conditionEnemyChilled", "conditionEnemyIgnited",
            "conditionFullLife", "conditionLowLife", "conditionStationary",
            "usePowerCharges", "useFrenzyCharges", "useEnduranceCharges",
        })
        self.assertEqual(config["properties"]["enemyIsBoss"]["enum"], ["None", "Boss", "Pinnacle"])
        self.assertEqual(config["properties"]["conditionEnemyShocked"], {"type": "boolean"})
        self.assertEqual(config["properties"]["enemyFireResist"], {
            "type": "number", "minimum": -200, "maximum": 1000,
        })
        self.assertTrue(changes["properties"]["allocateNodes"]["uniqueItems"])

    def test_poe2_import_does_not_claim_idempotency_for_uuid_creation(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        definitions = {item["name"]: item for item in module.handle_rpc_request(
            {"id": 1, "method": "tools/list"}, game="poe2")["result"]["tools"]}
        self.assertFalse(definitions["poe2_import"]["annotations"]["idempotentHint"])
        self.assertTrue(definitions["poe2_calculate"]["annotations"]["idempotentHint"])

    def test_report_and_batch_advertise_bounded_statistics_views(self):
        module = importlib.import_module('server.chickenbro_native_mcp')
        definitions = {t['name']:t for t in module.handle_rpc_request({'id':1,'method':'tools/list'})['result']['tools']}
        report = definitions['query_warcraftlogs_report']['inputSchema']['properties']['options']['properties']
        self.assertIn('view', report)
        self.assertEqual(report['view']['enum'], ['full','overview','events','statistics','healing'])
        self.assertEqual(report['maxPages']['maximum'], 5)
        batch = definitions['query_warcraftlogs_batch']['inputSchema']['properties']['queries']['items']['properties']['options']['properties']
        self.assertEqual(batch['view'], report['view'])

    def test_oversized_tool_result_returns_valid_bounded_partial_instead_of_breaking_stdio(self):
        native_mcp = importlib.import_module('server.chickenbro_native_mcp')
        result = native_mcp._tool_text({'sourceKey':'warcraftlogs','status':'verified',
            'facts':[{'events':['x'*1000 for _ in range(1500)]}]})
        self.assertLess(len(result.encode()),200000)
        packet = json.loads(result)
        self.assertEqual(packet['status'],'partial')
        self.assertEqual(packet['facts'],[])

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
        for port in [8790, 8791, 8792, 8796]:
            self.assertTrue(module._source_gateway_target_is_local(
                f"http://127.0.0.1:{port}/api/v2/internal/chickenbro/source-query"))
        for target in [
            "http://127.0.0.1:6379/api/v2/internal/chickenbro/source-query",
            "https://example.com/api/v2/internal/chickenbro/source-query",
            "http://127.0.0.1:8792/unrelated", "http://user@127.0.0.1:8792/api/v2/internal/chickenbro/source-query",
        ]:
            self.assertFalse(module._source_gateway_target_is_local(target))

    def test_toolbox_exposes_sources_and_account_scoped_simulation_tools(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        listed = module.handle_rpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )

        self.assertEqual(
            {
                "research_public_web",
                "read_chickenbro_skill",
                "query_warcraftlogs_report",
                "query_warcraftlogs_batch",
                "query_warcraftlogs_character",
                "query_warcraftlogs_rankings",
                "query_raiderio_character",
                "query_raiderio_rankings",
                "query_raiderio_characters",
                "prepare_simulation", "submit_simulation", "get_simulation_job", "list_simulation_jobs",
                "preview_simulation", "query_simulation_options", "compare_simulation_jobs",
            },
            {item["name"] for item in listed["result"]["tools"]},
        )
        self.assertTrue(
            all(item["annotations"]["readOnlyHint"] for item in listed["result"]["tools"]
                if item['name'] not in {'prepare_simulation', 'submit_simulation'})
        )

    def test_simc_tools_dispatch_without_model_identity(self):
        module = importlib.import_module('server.chickenbro_native_mcp')
        for name, operation in [('prepare_simulation', 'prepare'), ('submit_simulation', 'submit'),
                                ('get_simulation_job', 'get'), ('list_simulation_jobs', 'list'),
                                ('preview_simulation', 'preview'), ('query_simulation_options', 'options'), ('compare_simulation_jobs', 'compare')]:
            with self.subTest(name=name), patch.object(module, 'query_simulation_gateway', return_value={
                    'sourceKey': 'simc', 'status': 'queued', 'facts': [{'jobId': 'safe-job'}]}) as query:
                module.handle_rpc_request({'id': 2, 'method': 'tools/call',
                    'params': {'name': name, 'arguments': {'jobId': 'safe-job'}}})
                query.assert_called_once_with(operation, {'jobId': 'safe-job'})

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
        with patch.object(module, "query_source_gateway", return_value=packet) as read:
            module.handle_rpc_request({"id": 1, "method": "tools/call", "params": {
                "name": "research_public_web", "arguments": arguments}}, observation_writer=observations.append)
        read.assert_called_once_with("public_web", arguments["target"], options={"start":6000, "match":"Overcharge"})
        self.assertGreaterEqual(observations[0]["elapsedMs"], 0)
        self.assertEqual(observations[0]["reasonCode"], "JS_SHELL")
        self.assertEqual(observations[0]["factCount"], 0)
        self.assertEqual(len(observations[0]["argumentsSha256"]), 64)
        self.assertNotIn("Overcharge", json.dumps(observations))

    def test_toolbox_has_no_legacy_news_or_cached_mythic_plus_dependency(self):
        source = (ROOT / "server/chickenbro_native_mcp.py").read_text(encoding="utf-8")

        self.assertNotIn("news_backend", source)
        self.assertNotIn("inspect_current_mythic_plus_snapshot", source)

    def test_runtime_toolbox_and_profile_sources_are_retained(self):
        for relative_path in (
            "server/chickenbro_native_mcp.py",
            "server/chickenbro_public_web_research.py",
            "scripts/chickenbro-native-agent/chickenbro-native.config.toml.template",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

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
