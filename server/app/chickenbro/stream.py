import json
from dataclasses import dataclass
from typing import Any, Iterable, Iterator


class CodexStreamError(ValueError):
    def __init__(self, code: str, message: str = "Codex output was not usable"):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ChatEvent:
    event_type: str
    request_id: str
    conversation_id: str
    sequence: int
    run_id: str = ""
    text: str = ""
    error_code: str = ""
    retryable: bool = False

    def public_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.event_type,
            "requestId": self.request_id,
            "conversationId": self.conversation_id,
            "sequence": self.sequence,
        }
        if self.run_id:
            payload["runId"] = self.run_id
        if self.text:
            payload["text"] = self.text
        if self.error_code:
            payload["errorCode"] = self.error_code
            payload["retryable"] = self.retryable
        return payload


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _event_type(value: Any) -> str:
    return _text(value).strip().lower()


def iter_codex_deltas(events: Iterable[dict[str, Any]], *, max_chars: int) -> Iterable[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    total = 0
    yielded = False
    for raw in events:
        if not isinstance(raw, dict):
            continue
        event_type = _event_type(raw.get("type"))
        if event_type in {"item.delta", "message.delta", "delta"}:
            text = _text(raw.get("delta") or raw.get("text"))
            if not text:
                continue
            remaining = max_chars - total
            if remaining <= 0:
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            bounded = text[:remaining]
            if len(bounded) != len(text):
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            total += len(bounded)
            yielded = True
            yield bounded
        elif event_type in {"turn.failed", "error", "failed"}:
            raise CodexStreamError("CODEX_OUTPUT_INVALID")
    if not yielded:
        raise CodexStreamError("CODEX_OUTPUT_INVALID")


def serialize_sse_event(event: ChatEvent) -> str:
    payload = json.dumps(event.public_payload(), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.event_type}\ndata: {payload}\n\n"


def iter_sse_frames(first: ChatEvent, events: Iterator[ChatEvent]) -> Iterator[str]:
    try:
        yield serialize_sse_event(first)
        for event in events:
            yield serialize_sse_event(event)
    finally:
        close = getattr(events, "close", None)
        if callable(close):
            close()


__all__ = (
    "ChatEvent",
    "CodexStreamError",
    "iter_codex_deltas",
    "iter_sse_frames",
    "serialize_sse_event",
)
