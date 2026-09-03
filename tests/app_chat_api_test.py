import json
import unittest
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from server.app.chickenbro.application import ChatApplication
from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry
from tests.app_chickenbro_application_test import FakeCodex, MemoryChatRepository


OWNER_ID = UUID("00000000-0000-4000-8000-000000000201")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000202")
SESSION_COOKIE = "__Host-chickenbro-session"
CSRF_COOKIE = "__Host-chickenbro-csrf"
CSRF_TOKEN = "formal-chat-csrf"


class FakeFormalAuthApplication:
    def resolve_principal(self, credential, kind):
        from server.app.identity.domain import Principal

        identities = {
            ("mini-owner", "mini_bearer"): OWNER_ID,
            ("web-owner", "web_cookie"): OWNER_ID,
            ("mini-other", "mini_bearer"): OTHER_ID,
            ("web-other", "web_cookie"): OTHER_ID,
        }
        user_id = identities.get((credential, kind))
        return Principal(user_id=user_id, session_kind=kind) if user_id else None


def mini_headers(*, other=False):
    return {"Authorization": f"Bearer {'mini-other' if other else 'mini-owner'}"}


def web_cookies(*, other=False, csrf=False):
    cookies = {SESSION_COOKIE: "web-other" if other else "web-owner"}
    if csrf:
        cookies[CSRF_COOKIE] = CSRF_TOKEN
    return cookies


def web_write_headers(*, csrf=True):
    headers = {
        "Origin": "https://www.chickenbro.cloud",
        "Host": "www.chickenbro.cloud",
    }
    if csrf:
        headers["X-CSRF-Token"] = CSRF_TOKEN
    return headers


def build_chat_test_client():
    now = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
    repository = MemoryChatRepository()
    codex = FakeCodex([
        {"type": "delta", "text": "跨端回答"},
        {"type": "completed", "text": "跨端回答"},
    ])
    chat = ChatApplication(repository=repository, codex=codex, clock=lambda: now)
    settings = AppSettings(
        environment="test",
        database_url="postgresql://redacted",
        web_origin="https://www.chickenbro.cloud",
    )
    app = create_app(
        settings=settings,
        readiness_registry=ReadinessRegistry({}),
        web_auth_application=FakeFormalAuthApplication(),
        chat_application=chat,
        simulation_application=object(),
    )
    return (
        TestClient(app, base_url="https://www.chickenbro.cloud"),
        repository,
        codex,
    )


class FormalChatApiTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, self.codex = build_chat_test_client()

    def tearDown(self):
        self.client.close()

    def test_formal_chat_routes_are_registered(self):
        paths = set(self.client.app.openapi()["paths"])

        self.assertIn("/api/v2/chat/conversations", paths)
        self.assertIn("/api/v2/chat/conversations/{conversation_id}", paths)
        self.assertIn(
            "/api/v2/chat/conversations/{conversation_id}/messages/stream",
            paths,
        )

    def test_mini_bearer_can_create_and_list_bounded_public_conversations(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers={**mini_headers(), "Idempotency-Key": "mini-create-1"},
            json={"title": "跨端会话"},
        )
        listed = self.client.get(
            "/api/v2/chat/conversations?limit=20",
            headers=mini_headers(),
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["title"], "跨端会话")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"][0]["id"], created.json()["id"])
        self.assertIsNone(listed.json()["nextCursor"])
        for payload in (created.json(), listed.json()):
            encoded = json.dumps(payload)
            self.assertNotIn("user_id", encoded)
            self.assertNotIn("userId", encoded)

    def test_conversation_creation_requires_and_replays_one_idempotent_request(self):
        missing_key = self.client.post(
            "/api/v2/chat/conversations",
            headers=mini_headers(),
            json={"title": "幂等会话"},
        )
        headers = {**mini_headers(), "Idempotency-Key": "mini-create-replay-1"}
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers=headers,
            json={"title": "幂等会话"},
        )
        replayed = self.client.post(
            "/api/v2/chat/conversations",
            headers=headers,
            json={"title": "幂等会话"},
        )
        conflicting = self.client.post(
            "/api/v2/chat/conversations",
            headers=headers,
            json={"title": "另一个会话"},
        )

        self.assertEqual(missing_key.status_code, 422)
        self.assertEqual(missing_key.json()["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(replayed.status_code, 201)
        self.assertEqual(replayed.json()["id"], created.json()["id"])
        self.assertEqual(conflicting.status_code, 409)
        self.assertEqual(conflicting.json()["error"]["code"], "IDEMPOTENCY_CONFLICT")

    def test_web_cookie_can_read_but_cannot_write_without_origin_and_csrf(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers={**mini_headers(), "Idempotency-Key": "mini-create-2"},
            json={"title": "只读检查"},
        )

        readable = self.client.get(
            f"/api/v2/chat/conversations/{created.json()['id']}",
            cookies=web_cookies(),
        )
        missing_origin = self.client.post(
            "/api/v2/chat/conversations",
            headers={"Idempotency-Key": "web-create-no-origin"},
            cookies=web_cookies(csrf=True),
            json={"title": "不应创建"},
        )
        missing_csrf = self.client.post(
            "/api/v2/chat/conversations",
            headers={
                **web_write_headers(csrf=False),
                "Idempotency-Key": "web-create-no-csrf",
            },
            cookies=web_cookies(),
            json={"title": "仍不应创建"},
        )

        self.assertEqual(readable.status_code, 200)
        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(missing_origin.json()["error"]["code"], "ORIGIN_REJECTED")
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"]["code"], "CSRF_REJECTED")

    def test_stream_is_no_store_unbuffered_and_contains_only_public_events(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers={**mini_headers(), "Idempotency-Key": "mini-create-3"},
            json={"title": "流式会话"},
        ).json()

        response = self.client.post(
            f"/api/v2/chat/conversations/{created['id']}/messages/stream",
            headers={**mini_headers(), "Idempotency-Key": "formal-stream-1"},
            json={"content": "你好", "clientMessageId": "formal-client-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        frames = [frame for frame in response.text.split("\n\n") if frame]
        self.assertEqual(
            [frame.splitlines()[0] for frame in frames],
            ["event: started", "event: delta", "event: completed"],
        )
        for frame in frames:
            payload = json.loads(frame.split("data: ", 1)[1])
            self.assertLessEqual(
                set(payload),
                {
                    "type",
                    "requestId",
                    "conversationId",
                    "runId",
                    "sequence",
                    "text",
                    "errorCode",
                    "retryable",
                },
            )
            self.assertNotIn("userId", payload)
            self.assertNotIn("user_id", payload)

    def test_stream_requires_a_single_formal_transport_and_idempotency_key(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers={**mini_headers(), "Idempotency-Key": "mini-create-4"},
            json={"title": "认证边界"},
        ).json()
        path = f"/api/v2/chat/conversations/{created['id']}/messages/stream"

        missing_key = self.client.post(
            path,
            headers=mini_headers(),
            json={"content": "你好", "clientMessageId": "formal-client-2"},
        )
        ambiguous = self.client.post(
            path,
            headers={**mini_headers(), "Idempotency-Key": "formal-stream-2"},
            cookies=web_cookies(),
            json={"content": "你好", "clientMessageId": "formal-client-2"},
        )

        self.assertEqual(missing_key.status_code, 422)
        self.assertEqual(missing_key.json()["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")
        self.assertEqual(ambiguous.status_code, 400)
        self.assertEqual(ambiguous.json()["error"]["code"], "AMBIGUOUS_AUTH")


if __name__ == "__main__":
    unittest.main()
