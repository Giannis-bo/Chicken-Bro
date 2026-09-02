import importlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import server.news_backend as backend


class ChickenbroNativeAgentTest(unittest.TestCase):
    def test_native_agent_receives_the_configured_runtime_model_for_a_direct_identity_question(self):
        with mock.patch.dict(os.environ, {"WOW_CHICKENBRO_NATIVE_AGENT_MODEL": "gpt-5.6-luna"}, clear=False):
            prompt = json.loads(backend.chickenbro_native_agent_prompt({"message": "你现在是啥模型呢？"}))

        self.assertEqual("gpt-5.6-luna", prompt.get("runtime", {}).get("model"))
        self.assertTrue(any("当前模型" in item for item in prompt["instructions"]))
        self.assertTrue(any("inspect_current_mythic_plus_snapshot" in item for item in prompt["instructions"]))
        self.assertFalse(any("优先自主调用 research_public_web" in item for item in prompt["instructions"]))

    def test_native_agent_keeps_a_natural_answer_and_uses_only_actual_tool_observations_for_citations(self):
        captured = {}

        def runner(prompt, **kwargs):
            captured["prompt"] = prompt
            captured["kwargs"] = kwargs
            return {
                "status": "succeeded",
                "lastMessage": "熊德在高层大秘境里是当前值得优先考虑的坦克；下面的结论来自本轮公开样本，不等同于所有队伍和所有层数。",
                "model": "gpt-5.6-luna",
                "nativeToolObservations": [{
                    "tool": "research_public_web",
                    "status": "source_reference",
                    "evidenceRefs": ["public-web:example-com-bear"],
                    "evidence": [{
                        "id": "public-web:example-com-bear",
                        "sourceName": "example.com",
                        "sourceUrl": "https://example.com/bear",
                    }],
                    "limitations": ["snapshot_only"],
                }],
            }

        with mock.patch.dict(os.environ, {"WOW_CHICKENBRO_NATIVE_AGENT_ENABLED": "1"}, clear=False):
            try:
                result = backend.run_chickenbro_agent(
                    {
                        "message": "现在版本熊T强度如何？在大秘境里",
                        "conversationHistory": [],
                        "topic": {"status": "in_scope", "reason": "wow_topic"},
                    },
                    codex_runner=runner,
                )
            except backend.ChickenbroGenerationUnavailable:
                result = {}

        self.assertEqual(
            "熊德在高层大秘境里是当前值得优先考虑的坦克；下面的结论来自本轮公开样本，不等同于所有队伍和所有层数。",
            result.get("answer", {}).get("answer"),
        )
        self.assertEqual("native_codex_agent", result.get("answer", {}).get("answerSource"))
        self.assertEqual(["public-web:example-com-bear"], result.get("answer", {}).get("evidenceRefs"))
        self.assertIsNone(captured.get("kwargs", {}).get("schema"))
        self.assertIn("research_public_web", captured.get("prompt", ""))
        self.assertNotIn("先接住问题", captured.get("prompt", ""))
        self.assertNotIn("claimRefs", captured.get("prompt", ""))

    def test_native_agent_stream_returns_the_same_natural_answer_without_the_json_stream_validator(self):
        answer = "酒仙适合高层，但这轮先按你的队伍和副本把结论拆开说。"
        runner_result = {
            "status": "succeeded",
            "lastMessage": answer,
            "nativeToolObservations": [],
        }
        with mock.patch.dict(os.environ, {"WOW_CHICKENBRO_NATIVE_AGENT_ENABLED": "1"}, clear=False), mock.patch.object(
            backend,
            "default_chickenbro_native_agent_runner",
            return_value=runner_result,
        ):
            stream = backend.run_chickenbro_agent_stream(
                {"message": "酒仙大秘境怎么样", "conversationHistory": [], "topic": {}},
                stream_runner=lambda *_args, **_kwargs: self.fail("native path must not use the legacy JSON stream runner"),
            )
            first = next(stream)
            with self.assertRaises(StopIteration) as completed:
                next(stream)

        self.assertEqual({"type": "delta", "text": answer}, first)
        self.assertEqual(answer, completed.exception.value["answer"]["answer"])


class ChickenbroNativeMcpTest(unittest.TestCase):
    def test_native_profile_forwards_the_standard_proxy_and_source_gateway_environment(self):
        profile_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "scripts",
            "chickenbro-native-agent",
            "chickenbro-native.config.toml.template",
        )
        with open(profile_path, encoding="utf-8") as handle:
            profile = handle.read()

        for variable in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "CHICKENBRO_SOURCE_GATEWAY_URL",
            "CHICKENBRO_SOURCE_GATEWAY_TOKEN",
        ):
            self.assertIn(f'"{variable}"', profile)
        self.assertIn('web_search = "live"', profile)

    def test_stdio_mcp_exposes_read_only_public_and_server_source_tools(self):
        spec = importlib.util.find_spec("server.chickenbro_native_mcp")
        self.assertIsNotNone(spec)
        if spec is None:
            return
        module = importlib.import_module("server.chickenbro_native_mcp")
        observed = []

        listed = module.handle_rpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            observation_writer=observed.append,
        )
        self.assertEqual(
            {
                "research_public_web",
                "inspect_current_mythic_plus_snapshot",
                "query_warcraftlogs_report",
                "query_raiderio_character",
            },
            {item["name"] for item in listed["result"]["tools"]},
        )
        self.assertTrue(all(item["annotations"]["readOnlyHint"] for item in listed["result"]["tools"]))

        with mock.patch.object(module, "build_public_web_research_tool_result", return_value={
            "sourceKey": "public_web_research",
            "status": "source_reference",
            "facts": [{"summary": "Current high-key sample"}],
            "evidence": [{"id": "public-web:example-com-bear", "sourceUrl": "https://example.com/bear"}],
            "evidenceRefs": ["public-web:example-com-bear"],
            "limitations": [],
            "nextActions": [],
        }):
            called = module.handle_rpc_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "research_public_web", "arguments": {"target": "current bear tank high key"}},
                },
                observation_writer=observed.append,
            )

        self.assertFalse(called["result"].get("isError", False))
        self.assertEqual("source_reference", observed[0]["status"])
        self.assertEqual(["public-web:example-com-bear"], observed[0]["evidenceRefs"])

    def test_stdio_mcp_routes_wcl_and_raiderio_tools_to_the_server_source_gateway(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        observed = []
        with mock.patch.object(module, "query_source_gateway", return_value={
            "sourceKey": "warcraftlogs",
            "status": "verified",
            "facts": [{"reportCode": "KfVp6AQ8GMHYFN42"}],
            "evidence": [{"id": "wcl:KfVp6AQ8GMHYFN42:1"}],
            "evidenceRefs": ["wcl.report"],
            "limitations": [],
            "nextActions": [],
        }) as gateway:
            response = module.handle_rpc_request(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "query_warcraftlogs_report",
                        "arguments": {
                            "target": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
                        },
                    },
                },
                observation_writer=observed.append,
            )

        gateway.assert_called_once_with(
            "warcraftlogs",
            "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
        )
        self.assertFalse(response["result"].get("isError", False))
        self.assertEqual("verified", observed[0]["status"])
        self.assertEqual(["wcl.report"], observed[0]["evidenceRefs"])

    def test_current_mythic_plus_snapshot_is_an_optional_role_comparison_not_a_fixed_answer(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        payload = {
            "sourceName": "Community cache",
            "sourceStatus": "synced",
            "leaderboardUrl": "https://community.example/mythic-plus",
            "checkedAt": "2026-08-05T12:00:00+00:00",
            "seasonSlug": "season-current",
            "region": "global",
            "specAggregates": [
                {"role": "healer", "classKey": "druid", "specKey": "restoration", "fullName": "Restoration Druid", "bestScore": 3210.5, "maxKeyLevel": 25, "sampleCount": 48},
                {"role": "healer", "classKey": "paladin", "specKey": "holy", "fullName": "Holy Paladin", "bestScore": 3190, "maxKeyLevel": 24, "sampleCount": 41},
                {"role": "tank", "classKey": "druid", "specKey": "guardian", "fullName": "Guardian Druid", "bestScore": 3300, "maxKeyLevel": 26, "sampleCount": 51},
            ],
        }

        result = module.build_current_mythic_plus_snapshot_tool_result(
            {"role": "healer"},
            payload_loader=lambda: payload,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual("healer", result["facts"][0]["role"])
        self.assertEqual(
            ["Restoration Druid", "Holy Paladin"],
            [row["fullName"] for row in result["facts"][0]["rankedSpecs"]],
        )
        self.assertEqual(1, result["facts"][0]["rankedSpecs"][0]["placement"])
        self.assertIn("snapshot", " ".join(result["limitations"]).lower())

    def test_stdio_mcp_converts_a_reader_exception_into_a_literal_partial_observation(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        observed = []
        with mock.patch.object(module, "build_public_web_research_tool_result", side_effect=RuntimeError("reader offline")):
            try:
                response = module.handle_rpc_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "research_public_web", "arguments": {"target": "current tank ranking"}},
                    },
                    observation_writer=observed.append,
                )
            except RuntimeError:
                response = {}

        self.assertFalse(response.get("result", {}).get("isError", True))
        self.assertEqual("partial", observed[0]["status"])
        self.assertEqual([], observed[0]["evidenceRefs"])

    def test_stdio_server_writes_only_the_actual_tool_observation_to_the_job_file(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {"CHICKENBRO_NATIVE_OBSERVATIONS_PATH": f"{tmp}/observations.jsonl"},
            clear=False,
        ), mock.patch.object(module, "build_public_web_research_tool_result", return_value={
            "sourceKey": "public_web_research",
            "status": "partial",
            "facts": [],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["no readable page"],
            "nextActions": [],
        }):
            source = io.StringIO(json.dumps({
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "research_public_web", "arguments": {"target": "current healing mplus"}},
            }) + "\n")
            destination = io.StringIO()
            module.main(source, destination)
            with open(f"{tmp}/observations.jsonl", encoding="utf-8") as handle:
                observation = json.loads(handle.readline())

        self.assertEqual("research_public_web", observation["tool"])
        self.assertEqual("partial", observation["status"])


if __name__ == "__main__":
    unittest.main()
