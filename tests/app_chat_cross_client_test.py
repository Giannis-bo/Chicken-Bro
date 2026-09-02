import unittest

from tests.app_chat_api_test import (
    build_chat_test_client,
    mini_headers,
    web_cookies,
    web_write_headers,
)


class FormalChatCrossClientTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, self.codex = build_chat_test_client()

    def tearDown(self):
        self.client.close()

    def test_conversation_created_by_mini_is_visible_to_web_same_user(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers=mini_headers(),
            json={"title": "小程序创建"},
        )
        listed = self.client.get(
            "/api/v2/chat/conversations",
            cookies=web_cookies(),
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            created.json()["id"],
            [row["id"] for row in listed.json()["items"]],
        )

    def test_conversation_created_by_web_is_visible_to_mini_same_user(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers=web_write_headers(),
            cookies=web_cookies(csrf=True),
            json={"title": "Web 创建"},
        )
        listed = self.client.get(
            "/api/v2/chat/conversations",
            headers=mini_headers(),
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            created.json()["id"],
            [row["id"] for row in listed.json()["items"]],
        )

    def test_message_sent_by_mini_is_persisted_for_web_history(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers=mini_headers(),
            json={"title": "跨端消息"},
        ).json()

        streamed = self.client.post(
            f"/api/v2/chat/conversations/{created['id']}/messages/stream",
            headers={**mini_headers(), "Idempotency-Key": "cross-stream-1"},
            json={"content": "跨端问题", "clientMessageId": "cross-client-1"},
        )
        history = self.client.get(
            f"/api/v2/chat/conversations/{created['id']}",
            cookies=web_cookies(),
        )

        self.assertEqual(streamed.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            [(row["role"], row["content"]) for row in history.json()["messages"]],
            [("user", "跨端问题"), ("assistant", "跨端回答")],
        )

    def test_other_user_gets_not_found_and_cannot_enumerate_owner_history(self):
        created = self.client.post(
            "/api/v2/chat/conversations",
            headers=mini_headers(),
            json={"title": "仅 owner 可见"},
        ).json()

        detail = self.client.get(
            f"/api/v2/chat/conversations/{created['id']}",
            headers=mini_headers(other=True),
        )
        listed = self.client.get(
            "/api/v2/chat/conversations",
            headers=mini_headers(other=True),
        )
        streamed = self.client.post(
            f"/api/v2/chat/conversations/{created['id']}/messages/stream",
            headers={
                **mini_headers(other=True),
                "Idempotency-Key": "cross-other-stream",
            },
            json={"content": "越权", "clientMessageId": "cross-other-client"},
        )

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(detail.json()["error"]["code"], "CONVERSATION_NOT_FOUND")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"], [])
        self.assertEqual(streamed.status_code, 404)
        self.assertEqual(streamed.json()["error"]["code"], "CONVERSATION_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
