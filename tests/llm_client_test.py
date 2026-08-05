import json
import os
import unittest
from unittest.mock import patch


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(self.lines)


class LlmClientStreamTest(unittest.TestCase):
    def stream_env(self):
        return {
            "WOW_CHICKENBRO_STREAM_ENABLED": "1",
            "WOW_CHICKENBRO_STREAM_API_URL": "https://model.example.test/v1/chat/completions",
            "WOW_CHICKENBRO_STREAM_API_KEY": "test-secret-must-not-leak",
            "WOW_CHICKENBRO_STREAM_MODEL": "test-stream-model",
        }

    def test_requires_explicit_complete_dedicated_config(self):
        from server.llm_client import chickenbro_stream_config

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(chickenbro_stream_config(), {"enabled": False, "model": ""})
        with patch.dict(os.environ, {"WOW_CHICKENBRO_STREAM_ENABLED": "1"}, clear=True):
            self.assertEqual(chickenbro_stream_config(), {"enabled": False, "model": ""})
        with patch.dict(os.environ, self.stream_env(), clear=True):
            config = chickenbro_stream_config()
        self.assertEqual(config, {"enabled": True, "model": "test-stream-model"})
        self.assertNotIn("secret", json.dumps(config))

    def test_posts_json_object_mode_and_yields_only_nonempty_sse_content_deltas(self):
        from server.llm_client import stream_chat_completion

        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeStreamResponse(
                [
                    ': keepalive\n',
                    'data: {"choices":[{"delta":{"content":"你好"}}]}\n',
                    'data: {"choices":[{"delta":{}}]}\n',
                    'data: {"choices":[{"delta":{"content":"世界"}}]}\n',
                    'data: [DONE]\n',
                ]
            )

        with patch.dict(os.environ, self.stream_env(), clear=True):
            chunks = list(stream_chat_completion("system", "user", {"type": "object"}, opener=opener))

        self.assertEqual(chunks, ["你好", "世界"])
        self.assertTrue(captured["body"]["stream"])
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["headers"]["Accept"], "text/event-stream")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-secret-must-not-leak")

    def test_rejects_malformed_sse_data(self):
        from server.llm_client import ChickenbroStreamProtocolError, stream_chat_completion

        with patch.dict(os.environ, self.stream_env(), clear=True):
            with self.assertRaises(ChickenbroStreamProtocolError):
                list(stream_chat_completion("system", "user", {"type": "object"}, opener=lambda *_, **__: FakeStreamResponse(['data: nope\n'])))

    def test_stops_a_keepalive_only_stream_at_the_configured_end_to_end_deadline(self):
        from server.llm_client import ChickenbroStreamUnavailable, stream_chat_completion

        clock_values = iter([0.0, 1.0, 4.0])
        environment = {**self.stream_env(), "WOW_CHICKENBRO_STREAM_TIMEOUT_SECONDS": "3"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ChickenbroStreamUnavailable, "exceeded 3 seconds"):
                list(
                    stream_chat_completion(
                        "system",
                        "user",
                        {"type": "object"},
                        opener=lambda *_, **__: FakeStreamResponse([": keepalive\n", ": keepalive\n"]),
                        clock=lambda: next(clock_values),
                    )
                )


if __name__ == "__main__":
    unittest.main()
