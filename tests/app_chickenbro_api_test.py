import json
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from server.app.chickenbro.stream import ChatEvent
from server.app.identity.prototype import PrototypeIdentityApplication
from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry


class MemoryPrototypeIdentityRepository:
    def __init__(self):
        self.users = set()
        self.sessions = {}

    def create_prototype_user(self, *, user_id, now):
        self.users.add(user_id)

    def insert_prototype_session(self, session, *, now):
        self.sessions[session.id] = session

    def get_prototype_session_by_token_hash(self, *, token_sha256, for_update=False):
        return next((item for item in self.sessions.values() if item.token_sha256 == token_sha256), None)

    def get_prototype_session(self, *, session_id, for_update=False):
        return self.sessions.get(session_id)

    def save_prototype_session(self, session, *, now):
        self.sessions[session.id] = session


class FakeChatApplication:
    conversation_id = UUID("00000000-0000-4000-8000-000000000101")

    def create_conversation(self, principal, title):
        return {
            "id": self.conversation_id,
            "user_id": principal.user_id,
            "title": title,
            "status": "active",
            "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }

    def load_conversation(self, principal, conversation_id):
        if conversation_id != self.conversation_id:
            raise AssertionError("unexpected conversation id")
        return {
            "conversation": self.create_conversation(principal, "测试会话"),
            "messages": [],
        }

    def stream_message(self, principal, conversation_id, content, *, client_message_id, idempotency_key):
        self.seen_owner = principal.user_id
        yield ChatEvent("started", "00000000-0000-4000-8000-000000000102", str(conversation_id), 1)
        yield ChatEvent("delta", "00000000-0000-4000-8000-000000000102", str(conversation_id), 2, text="回答")
        yield ChatEvent("completed", "00000000-0000-4000-8000-000000000102", str(conversation_id), 3, text="回答")


class ChickenbroApiTest(unittest.TestCase):
    def setUp(self):
        repository = MemoryPrototypeIdentityRepository()
        identity = PrototypeIdentityApplication(
            repository=repository,
            ttl=timedelta(hours=1),
            clock=lambda: datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
        self.chat = FakeChatApplication()
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            prototype_enabled=True,
        )
        self.client = TestClient(
            create_app(
                settings=settings,
                readiness_registry=ReadinessRegistry({}),
                web_auth_application=object(),
                prototype_identity_application=identity,
                prototype_chat_application=self.chat,
            )
        )
        self.token = self.client.post("/api/v2/prototype/sessions").json()["sessionToken"]

    def test_conversation_is_owner_bound_and_does_not_expose_internal_owner(self):
        response = self.client.post(
            "/api/v2/prototype/conversations",
            headers={"X-Prototype-Session": self.token},
            json={"title": "我的会话"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["title"], "我的会话")
        self.assertNotIn("userId", payload)
        self.assertNotIn("user_id", payload)

    def test_message_stream_has_only_public_sse_fields(self):
        response = self.client.post(
            f"/api/v2/prototype/conversations/{self.chat.conversation_id}/messages/stream",
            headers={
                "X-Prototype-Session": self.token,
                "Idempotency-Key": "request-1",
            },
            json={"content": "你好", "clientMessageId": "client-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        frames = [frame for frame in response.text.split("\n\n") if frame]
        self.assertEqual([frame.splitlines()[0] for frame in frames], [
            "event: started",
            "event: delta",
            "event: completed",
        ])
        for frame in frames:
            payload = json.loads(frame.split("data: ", 1)[1])
            self.assertNotIn("userId", payload)
            self.assertNotIn("thread", payload)

    def test_stream_requires_prototype_capability(self):
        response = self.client.post(
            f"/api/v2/prototype/conversations/{self.chat.conversation_id}/messages/stream",
            headers={"Idempotency-Key": "request-2"},
            json={"content": "你好"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "PROTOTYPE_SESSION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
