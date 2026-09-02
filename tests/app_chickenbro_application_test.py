import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server.app.chickenbro.application import ChatApplicationError, PrototypeChatApplication
from server.app.chickenbro.domain import AgentRunStatus, ConversationStatus, MessageRole
from server.app.identity.prototype import PrototypePrincipal


class MemoryChatRepository:
    def __init__(self):
        self.conversations = {}
        self.messages = []
        self.runs = {}

    def create_conversation(self, user_id, title, now):
        conversation = {
            "id": uuid4(),
            "user_id": user_id,
            "title": title,
            "status": ConversationStatus.ACTIVE,
            "created_at": now,
            "updated_at": now,
        }
        self.conversations[(user_id, conversation["id"])] = conversation
        return conversation

    def get_conversation(self, user_id, conversation_id):
        return self.conversations.get((user_id, conversation_id))

    def list_messages(self, user_id, conversation_id):
        return [
            item for item in self.messages
            if item["user_id"] == user_id and item["conversation_id"] == conversation_id
        ]

    def find_message_by_client_id(self, user_id, conversation_id, client_message_id):
        return next(
            (
                item for item in self.messages
                if item["user_id"] == user_id
                and item["conversation_id"] == conversation_id
                and item["client_message_id"] == client_message_id
            ),
            None,
        )

    def insert_message(self, user_id, conversation_id, role, content, client_message_id, now):
        message = {
            "id": uuid4(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "client_message_id": client_message_id,
            "created_at": now,
        }
        self.messages.append(message)
        return message

    def start_agent_run(self, user_id, conversation_id, user_message_id, now):
        run = {
            "id": uuid4(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "assistant_message_id": None,
            "status": AgentRunStatus.STREAMING,
            "public_error_code": "",
            "started_at": now,
            "finished_at": None,
        }
        self.runs[run["id"]] = run
        return run

    def finish_agent_run(self, user_id, run_id, status, assistant_message_id, public_error_code, finished_at):
        run = self.runs[run_id]
        self.assert_owner(run, user_id)
        run.update({
            "status": status,
            "assistant_message_id": assistant_message_id,
            "public_error_code": public_error_code,
            "finished_at": finished_at,
        })

    @staticmethod
    def assert_owner(row, user_id):
        if row["user_id"] != user_id:
            raise AssertionError("owner mismatch")


class FakeCodex:
    def __init__(self, events=None, error=None):
        self.events = events or []
        self.error = error

    def stream(self, *, prompt, timeout_seconds):
        if self.error:
            raise self.error
        yield from self.events


class CapturingCodex(FakeCodex):
    def __init__(self, events=None, error=None):
        super().__init__(events=events, error=error)
        self.prompt = ""
        self.timeout_seconds = None

    def stream(self, *, prompt, timeout_seconds):
        self.prompt = prompt
        self.timeout_seconds = timeout_seconds
        yield from super().stream(prompt=prompt, timeout_seconds=timeout_seconds)


class PrototypeChatApplicationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        self.user_id = UUID("00000000-0000-0000-0000-000000000011")
        self.principal = PrototypePrincipal(
            user_id=self.user_id,
            session_id=UUID("00000000-0000-4000-8000-000000000012"),
        )
        self.repository = MemoryChatRepository()
        conversation = self.repository.create_conversation(self.user_id, "测试会话", self.now)
        self.conversation_id = conversation["id"]

    def test_completed_codex_stream_persists_assistant_only_after_completion(self):
        application = PrototypeChatApplication(
            repository=self.repository,
            codex=FakeCodex([
                {"type": "delta", "text": "先给结论"},
                {"type": "completed", "text": "先给结论"},
            ]),
            clock=lambda: self.now,
        )

        events = list(application.stream_message(
            self.principal,
            self.conversation_id,
            "怎么看？",
            client_message_id="client-1",
            idempotency_key="request-1",
        ))

        self.assertEqual([event.event_type for event in events], ["started", "delta", "completed"])
        self.assertEqual([event.sequence for event in events], [1, 2, 3])
        self.assertEqual([item["role"] for item in self.repository.messages], [MessageRole.USER, MessageRole.ASSISTANT])
        self.assertEqual(next(iter(self.repository.runs.values()))["status"], AgentRunStatus.SUCCEEDED)

    def test_native_codex_prompt_bounds_public_research_and_uses_aligned_timeout(self):
        codex = CapturingCodex(events=[{"type": "completed", "text": "已给出结论"}])
        application = PrototypeChatApplication(
            repository=self.repository,
            codex=codex,
            clock=lambda: self.now,
        )

        events = list(application.stream_message(
            self.principal,
            self.conversation_id,
            "分析这场战斗",
            client_message_id="client-bounded-research",
            idempotency_key="request-bounded-research",
        ))

        self.assertEqual(events[-1].event_type, "completed")
        self.assertEqual(codex.timeout_seconds, 180)
        self.assertIn("最多进行 2 次公开来源检索", codex.prompt)
        self.assertIn("来源被拒绝、不可读或无法验证，立即停止检索", codex.prompt)
        self.assertIn("本轮必须输出最终回答", codex.prompt)

    def test_native_codex_prompt_routes_wcl_and_raiderio_links_to_server_source_api_tools(self):
        codex = CapturingCodex(events=[{"type": "completed", "text": "已给出结论"}])
        application = PrototypeChatApplication(
            repository=self.repository,
            codex=codex,
            clock=lambda: self.now,
        )

        list(application.stream_message(
            self.principal,
            self.conversation_id,
            "请用这个 WCL https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1 分析 Giannis，必要时再看 Raider.IO。",
            client_message_id="client-source-api-routing",
            idempotency_key="request-source-api-routing",
        ))

        self.assertIn("query_warcraftlogs_report", codex.prompt)
        self.assertIn("query_raiderio_character", codex.prompt)
        self.assertIn("云端 API", codex.prompt)
        self.assertIn("不要用 web_search 或 research_public_web 打开这些链接", codex.prompt)

    def test_codex_failure_never_persists_assistant_or_fallback_model(self):
        from server.app.chickenbro.codex_adapter import CodexUnavailable

        application = PrototypeChatApplication(
            repository=self.repository,
            codex=FakeCodex(error=CodexUnavailable("Codex is not configured")),
            clock=lambda: self.now,
        )

        events = list(application.stream_message(
            self.principal,
            self.conversation_id,
            "模拟一下",
            client_message_id="client-2",
            idempotency_key="request-2",
        ))

        self.assertEqual([event.event_type for event in events], ["started", "failed"])
        self.assertEqual(events[-1].error_code, "CODEX_UNAVAILABLE")
        self.assertEqual([item["role"] for item in self.repository.messages], [MessageRole.USER])
        self.assertEqual(next(iter(self.repository.runs.values()))["status"], AgentRunStatus.FAILED)

    def test_history_failure_after_stream_start_becomes_public_failed_event(self):
        original_list_messages = self.repository.list_messages

        def fail_history(user_id, conversation_id):
            if any(item["role"] is MessageRole.USER for item in self.repository.messages):
                raise RuntimeError("database details must stay private")
            return original_list_messages(user_id, conversation_id)

        self.repository.list_messages = fail_history
        application = PrototypeChatApplication(
            repository=self.repository,
            codex=FakeCodex([
                {"type": "completed", "text": "不应执行"},
            ]),
            clock=lambda: self.now,
        )

        events = list(application.stream_message(
            self.principal,
            self.conversation_id,
            "历史故障也不能泄露",
            client_message_id="client-history-failure",
            idempotency_key="request-history-failure",
        ))

        self.assertEqual([event.event_type for event in events], ["started", "failed"])
        self.assertEqual(events[-1].error_code, "CODEX_EXECUTION_FAILED")
        self.assertEqual([item["role"] for item in self.repository.messages], [MessageRole.USER])

    def test_other_owner_cannot_read_or_write_conversation(self):
        other = PrototypePrincipal(
            user_id=UUID("00000000-0000-0000-0000-000000000013"),
            session_id=UUID("00000000-0000-4000-8000-000000000014"),
        )
        application = PrototypeChatApplication(
            repository=self.repository,
            codex=FakeCodex(),
            clock=lambda: self.now,
        )

        with self.assertRaisesRegex(ChatApplicationError, "CONVERSATION_NOT_FOUND"):
            list(application.stream_message(
                other,
                self.conversation_id,
                "不该读到",
                client_message_id="client-3",
                idempotency_key="request-3",
            ))
        self.assertEqual(self.repository.messages, [])


if __name__ == "__main__":
    unittest.main()
