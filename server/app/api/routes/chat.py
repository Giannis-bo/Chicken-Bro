from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import (
    chat_application,
    require_mutating_principal,
    require_principal,
)
from server.app.api.errors import ApiProblem
from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.chickenbro.stream import ChatEvent, iter_sse_frames
from server.app.identity.domain import Principal


router = APIRouter(prefix="/api/v2/chat")


class ConversationCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="炸鸡队长对话", max_length=256)


class ChatMessageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    client_message_id: str | None = Field(
        default=None,
        alias="clientMessageId",
        min_length=1,
        max_length=128,
    )


def _value(row: object, key: str, default: object = None) -> object:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _iso(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _conversation_payload(conversation: object) -> dict[str, object]:
    status = _value(conversation, "status", "")
    return {
        "id": str(_value(conversation, "id", "")),
        "title": str(_value(conversation, "title", "")),
        "status": str(getattr(status, "value", status)),
        "createdAt": _iso(_value(conversation, "created_at", "")),
        "updatedAt": _iso(_value(conversation, "updated_at", "")),
    }


def _message_payload(message: object) -> dict[str, object]:
    role = _value(message, "role", "")
    return {
        "id": str(_value(message, "id", "")),
        "role": str(getattr(role, "value", role)),
        "content": str(_value(message, "content", "")),
        "createdAt": _iso(_value(message, "created_at", "")),
    }


def _detail_payload(view: object) -> dict[str, object]:
    if not isinstance(view, dict):
        raise ChatApplicationError(
            "CHAT_PERSISTENCE_FAILED",
            "conversation detail is unavailable",
        )
    conversation = view.get("conversation")
    messages = view.get("messages")
    if conversation is None or not isinstance(messages, (list, tuple)):
        raise ChatApplicationError(
            "CHAT_PERSISTENCE_FAILED",
            "conversation detail is unavailable",
        )
    return {
        **_conversation_payload(conversation),
        "messages": [_message_payload(message) for message in messages],
    }


def _raise_chat_error(error: ChatApplicationError) -> None:
    status_code = {
        "CONVERSATION_NOT_FOUND": 404,
        "INVALID_CURSOR": 422,
        "MESSAGE_REQUIRED": 422,
        "MESSAGE_TOO_LONG": 422,
        "IDEMPOTENCY_KEY_REQUIRED": 422,
        "IDEMPOTENCY_KEY_INVALID": 422,
        "CLIENT_MESSAGE_ID_INVALID": 422,
        "IDEMPOTENCY_CONFLICT": 409,
        "CHAT_RUN_IN_PROGRESS": 409,
        "CHAT_RUN_NOT_REPLAYABLE": 409,
        "CODEX_UNAVAILABLE": 503,
    }.get(error.code, 500)
    raise ApiProblem(
        status_code=status_code,
        code=error.code,
        message=error.message,
    ) from error


@router.get("/conversations")
def list_conversations(
    principal: Principal = Depends(require_principal),
    application: ChatApplication = Depends(chat_application),
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    try:
        page = application.list_conversations(principal, cursor, limit)
    except (ChatApplicationError, TypeError, ValueError) as error:
        if isinstance(error, ChatApplicationError):
            _raise_chat_error(error)
        raise ApiProblem(
            status_code=422,
            code="INVALID_LIMIT",
            message="conversation limit is invalid",
        ) from error
    return {
        "items": [_conversation_payload(row) for row in page.items],
        "nextCursor": page.next_cursor,
    }


@router.post("/conversations", status_code=201)
def create_conversation(
    body: ConversationCreateBody | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_mutating_principal),
    application: ChatApplication = Depends(chat_application),
) -> dict[str, object]:
    try:
        conversation = application.create_conversation(
            principal,
            body.title if body is not None else "炸鸡队长对话",
            idempotency_key=idempotency_key or "",
        )
    except ChatApplicationError as error:
        _raise_chat_error(error)
    return _conversation_payload(conversation)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    principal: Principal = Depends(require_principal),
    application: ChatApplication = Depends(chat_application),
) -> dict[str, object]:
    try:
        view = application.load_conversation(principal, conversation_id)
        return _detail_payload(view)
    except ChatApplicationError as error:
        _raise_chat_error(error)


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: UUID,
    body: ChatMessageBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_mutating_principal),
    application: ChatApplication = Depends(chat_application),
) -> StreamingResponse:
    events: Iterator[ChatEvent] = application.stream_message(
        principal,
        conversation_id,
        body.content,
        client_message_id=body.client_message_id,
        idempotency_key=idempotency_key or "",
    )
    try:
        first = next(events)
    except ChatApplicationError as error:
        _raise_chat_error(error)
    except StopIteration:
        raise ApiProblem(
            status_code=500,
            code="CODEX_EXECUTION_FAILED",
            message="stream did not start",
        ) from None

    return StreamingResponse(
        iter_sse_frames(first, events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
