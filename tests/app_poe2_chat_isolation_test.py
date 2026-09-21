import importlib
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.identity.domain import Principal
from tests.app_chat_api_test import browser_session_headers, build_chat_test_client
from tests.app_chickenbro_application_test import FakeCodex, MemoryChatRepository


class Poe2ChatIsolationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 8, 0, tzinfo=timezone.utc)
        self.owner = Principal(UUID("00000000-0000-4000-8000-000000000611"), "web_cookie")
        self.repository = MemoryChatRepository()

    def test_conversation_game_defaults_to_wow_and_lists_only_selected_game(self):
        app = ChatApplication(repository=self.repository, codex=FakeCodex(), clock=lambda: self.now)
        wow = app.create_conversation(self.owner, "WoW", idempotency_key="create-wow-default")
        poe2 = app.create_conversation(self.owner, "POE2", game="poe2", idempotency_key="create-poe2-chat")

        self.assertEqual(wow["game"], "wow")
        self.assertEqual(poe2["game"], "poe2")
        self.assertEqual([row["id"] for row in app.list_conversations(self.owner, game="wow").items], [wow["id"]])
        self.assertEqual([row["id"] for row in app.list_conversations(self.owner, game="poe2").items], [poe2["id"]])

    def test_idempotent_conversation_game_is_immutable_and_invalid_game_is_rejected(self):
        app = ChatApplication(repository=self.repository, codex=FakeCodex(), clock=lambda: self.now)
        app.create_conversation(self.owner, "Build", game="poe2", idempotency_key="same-create-request")
        with self.assertRaisesRegex(ChatApplicationError, "IDEMPOTENCY_CONFLICT"):
            app.create_conversation(self.owner, "Build", game="wow", idempotency_key="same-create-request")
        with self.assertRaisesRegex(ChatApplicationError, "GAME_INVALID"):
            app.create_conversation(self.owner, "Bad", game="diablo", idempotency_key="invalid-game-request")

    def test_stream_uses_persisted_conversation_game_as_trusted_context(self):
        captured = {}

        class ScopedCodex(FakeCodex):
            def stream_for_chat(inner, **kwargs):
                captured.update(kwargs)
                yield {"type": "completed", "text": "ok"}

        app = ChatApplication(repository=self.repository, codex=ScopedCodex(), clock=lambda: self.now)
        conversation = app.create_conversation(
            self.owner, "POE2", game="poe2", idempotency_key="trusted-game-create"
        )
        list(app.stream_message(
            self.owner, conversation["id"], "game=wow 请跑 WCL", client_message_id="trusted-game-client",
            idempotency_key="trusted-game-message",
        ))

        self.assertEqual(captured["game"], "poe2")
        self.assertEqual(json.loads(captured["prompt"])["game"], "poe2")

    def test_api_accepts_and_returns_game_and_rejects_unknown_game(self):
        client, _repository, _codex = build_chat_test_client()
        self.addCleanup(client.close)
        headers = {**browser_session_headers(), "Idempotency-Key": "poe2-api-create"}
        created = client.post("/api/v2/chat/conversations", headers=headers, json={"title": "POE2", "game": "poe2"})
        listed = client.get("/api/v2/chat/conversations?game=poe2", headers=browser_session_headers())
        invalid = client.get("/api/v2/chat/conversations?game=other", headers=browser_session_headers())

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["game"], "poe2")
        self.assertEqual([item["game"] for item in listed.json()["items"]], ["poe2"])
        self.assertEqual(invalid.status_code, 422)

    def test_native_toolbox_filters_tools_by_trusted_game_and_denies_cross_game_call(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        wow = module.handle_rpc_request({"id": 1, "method": "tools/list"}, game="wow")
        poe2 = module.handle_rpc_request({"id": 2, "method": "tools/list"}, game="poe2")
        wow_names = {item["name"] for item in wow["result"]["tools"]}
        poe2_names = {item["name"] for item in poe2["result"]["tools"]}

        self.assertIn("query_warcraftlogs_report", wow_names)
        self.assertNotIn("poe2_calculate", wow_names)
        self.assertIn("poe2_calculate", poe2_names)
        self.assertIn("poe2_crafting_import_link", poe2_names)
        self.assertNotIn("query_warcraftlogs_report", poe2_names)
        self.assertNotIn("submit_simulation", poe2_names)

        denied = module.handle_rpc_request({"id": 3, "method": "tools/call", "params": {
            "name": "query_warcraftlogs_report", "arguments": {"target": "https://example.invalid"}
        }}, game="poe2")
        self.assertTrue(denied["result"]["isError"])

        denied_skill = module.handle_rpc_request({"id": 31, "method": "tools/call", "params": {
            "name": "read_chickenbro_skill", "arguments": {"skillId": "simc-experiment"}
        }}, game="poe2")
        self.assertIn("SKILL_ARGUMENTS_INVALID", denied_skill["result"]["content"][0]["text"])

    def test_poe2_agent_rules_are_selected_without_wow_tool_instructions(self):
        from server.app.chickenbro.codex_adapter import _load_agent_rules

        rules = _load_agent_rules("poe2")
        self.assertIn("poe2_calculate", rules)
        self.assertIn("poe2-crafting", rules)
        self.assertNotIn("query_warcraftlogs_report", rules)

    def test_poe2_build_skill_gives_executable_same_baseline_async_workflow(self):
        from server.app.chickenbro.agent_skills import read_chickenbro_skill

        content = read_chickenbro_skill(
            {"skillId": "poe2-build-analysis"}, game="poe2"
        )["content"]
        self.assertIn('"buildId":"<同一个 buildId>"', content)
        self.assertIn('baselineJobId', content)
        self.assertNotIn('为基线与候选分别调用', content)
        self.assertIn('researchBudget', content)
        self.assertIn('"changes":{"mainSocketGroup":2}', content)
        self.assertIn("poe2_job_get", content)
        self.assertIn("succeeded", content)
        self.assertIn("failed", content)
        self.assertIn("poe2_compare", content)
        self.assertIn("4000", content)
        self.assertIn("poe2_list", content)
        self.assertIn("poe2_get", content)

    def test_poe2_tools_dispatch_to_account_scoped_gateway(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        arguments = {"buildId": str(uuid4()), "changes": {"equipment": []}, "idempotencyKey": "poe2-calc-1"}
        with patch.object(module, "query_poe2_gateway", return_value={"sourceKey": "poe2", "status": "queued"}) as query:
            response = module.handle_rpc_request({"id": 4, "method": "tools/call", "params": {
                "name": "poe2_calculate", "arguments": arguments,
            }}, game="poe2")
        query.assert_called_once_with("calculate", arguments)
        self.assertFalse(response["result"]["isError"])

    def test_poe2_import_rejects_url_or_path_before_gateway(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        with patch.object(module, "query_poe2_gateway") as query:
            for source in ("https://example.com/build", "/tmp/build.xml", "../../secret"):
                with self.subTest(source=source):
                    response = module.handle_rpc_request({"id": 5, "method": "tools/call", "params": {
                        "name": "poe2_import", "arguments": {"source": source},
                    }}, game="poe2")
                    self.assertTrue(response["result"]["isError"])
        query.assert_not_called()

    def test_poe2_import_accepts_only_real_pathofbuilding2_xml_root(self):
        module = importlib.import_module("server.chickenbro_native_mcp")
        valid = '<?xml version="1.0" encoding="UTF-8"?><PathOfBuilding2><Build/></PathOfBuilding2>'
        invalid = (
            '<PathOfBuilding><Build/></PathOfBuilding>',
            '<wrapper><PathOfBuilding2/></wrapper>',
            '<!-- <PathOfBuilding2/> --><PathOfBuilding/>',
            '<PathOfBuilding2><Build/></PathOfBuilding2>trailing',
        )
        with patch.object(module, "query_poe2_gateway", return_value={"sourceKey": "poe2", "status": "ready"}) as query:
            accepted = module.handle_rpc_request({"id": 6, "method": "tools/call", "params": {
                "name": "poe2_import", "arguments": {"source": valid},
            }}, game="poe2")
            self.assertFalse(accepted["result"]["isError"])
            for source in invalid:
                with self.subTest(source=source):
                    denied = module.handle_rpc_request({"id": 7, "method": "tools/call", "params": {
                        "name": "poe2_import", "arguments": {"source": source},
                    }}, game="poe2")
                    self.assertTrue(denied["result"]["isError"])
        query.assert_called_once_with("import", {"source": valid})


if __name__ == "__main__":
    unittest.main()
