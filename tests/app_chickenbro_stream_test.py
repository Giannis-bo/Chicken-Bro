import json
import unittest
from uuid import UUID

from server.app.chickenbro.stream import (
    CodexStreamError,
    ChatEvent,
    iter_codex_deltas,
    iter_sse_frames,
    serialize_sse_event,
)


class ChickenbroStreamTest(unittest.TestCase):
    def test_codex_jsonl_deltas_are_bounded_and_ignore_untrusted_metadata(self):
        events = [
            {"type": "thread.started", "thread_id": "secret-thread"},
            {"type": "item.delta", "delta": "先给结论"},
            {"type": "item.delta", "delta": "，再说依据"},
            {"type": "turn.completed"},
        ]

        self.assertEqual(list(iter_codex_deltas(events, max_chars=100)), ["先给结论", "，再说依据"])

    def test_empty_or_error_codex_output_is_a_public_stream_error(self):
        with self.assertRaises(CodexStreamError) as context:
            list(iter_codex_deltas([{"type": "turn.failed", "error": "raw provider secret"}], max_chars=100))
        self.assertEqual(context.exception.code, "CODEX_OUTPUT_INVALID")
        self.assertNotIn("raw provider secret", str(context.exception))

    def test_sse_frame_contains_only_allowlisted_public_fields(self):
        event = ChatEvent(
            event_type="delta",
            request_id="00000000-0000-4000-8000-000000000003",
            conversation_id="00000000-0000-4000-8000-000000000004",
            sequence=2,
            run_id="00000000-0000-4000-8000-000000000007",
            text="hello",
        )

        frame = serialize_sse_event(event)
        self.assertTrue(frame.startswith("event: delta\ndata: "))
        payload = json.loads(frame.split("data: ", 1)[1].split("\n\n", 1)[0])
        self.assertEqual(payload, {
            "type": "delta",
            "requestId": "00000000-0000-4000-8000-000000000003",
            "conversationId": "00000000-0000-4000-8000-000000000004",
            "sequence": 2,
            "runId": "00000000-0000-4000-8000-000000000007",
            "text": "hello",
        })
        self.assertNotIn("thread", frame)

    def test_failed_sse_frame_uses_typed_error_code_field(self):
        event = ChatEvent(
            event_type="failed",
            request_id="00000000-0000-0000-0000-000000000005",
            conversation_id="00000000-0000-0000-0000-000000000006",
            sequence=2,
            error_code="CODEX_UNAVAILABLE",
            retryable=True,
        )

        payload = json.loads(serialize_sse_event(event).split("data: ", 1)[1].split("\n\n", 1)[0])

        self.assertEqual(payload, {
            "type": "failed",
            "requestId": "00000000-0000-0000-0000-000000000005",
            "conversationId": "00000000-0000-0000-0000-000000000006",
            "sequence": 2,
            "errorCode": "CODEX_UNAVAILABLE",
            "retryable": True,
        })
        self.assertNotIn("\"code\"", json.dumps(payload))

    def test_closing_http_frames_closes_the_application_event_stream(self):
        closed = []

        class RemainingEvents:
            def __iter__(self):
                return self

            def __next__(self):
                return ChatEvent("delta", "request", "conversation", 2, text="partial")

            def close(self):
                closed.append(True)

        events = RemainingEvents()
        frames = iter_sse_frames(
            ChatEvent("started", "request", "conversation", 1),
            events,
        )

        self.assertTrue(next(frames).startswith("event: started"))
        frames.close()

        self.assertEqual([True], closed)


if __name__ == "__main__":
    unittest.main()
