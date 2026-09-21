from fastapi import Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from collections.abc import Iterator
from dataclasses import replace
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from server.app.api.dependencies import (
    chat_application,
    require_mutating_principal,
    require_principal,
)
from server.app.api.errors import ApiProblem
from server.app.chickenbro.images import ImageError, MAX_DATA_URL
from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.chickenbro.stream import ChatEvent, iter_sse_frames
from server.app.identity.domain import Principal


router = APIRouter(prefix="/api/v2/chat")


class ConversationCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="炸鸡队长对话", max_length=256)
    game: Literal["wow", "poe2"] = "wow"


class ChatMessageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    content: str = Field(default="", max_length=4000)
    image_ids: tuple[UUID, ...] = Field(default=(), alias="imageIds", max_length=3)
    client_message_id: str | None = Field(
        default=None,
        alias="clientMessageId",
        min_length=1,
        max_length=128,
    )


class ChatFeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved: StrictBool


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
        "game": str(getattr(_value(conversation, "game", "wow"), "value", _value(conversation, "game", "wow"))),
        "status": str(getattr(status, "value", status)),
        "createdAt": _iso(_value(conversation, "created_at", "")),
        "updatedAt": _iso(_value(conversation, "updated_at", "")),
    }


def _message_payload(message: object) -> dict[str, object]:
    role = _value(message, "role", "")
    payload = {
        "id": str(_value(message, "id", "")),
        "role": str(getattr(role, "value", role)),
        "content": str(_value(message, "content", "")),
        "createdAt": _iso(_value(message, "created_at", "")),
    }

    if _value(message, "images"):
        payload["images"] = _value(message, "images")
    status = _value(message, "reply_status")
    if status == "completed":
        payload["resolved"] = _value(message, "resolved")
    if status in {"completed", "failed"}:
        payload["progress"] = {
            "text": str(_value(message, "progress_text", "")),
            "status": status,
            "completedAt": _iso(_value(message, "completed_at")),
            "durationMs": _value(message, "duration_ms"),
        }
    return payload


def _detail_payload(view: object, include_progress: bool = False, include_feedback: bool = False, include_images: bool = False) -> dict[str, object]:
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
    if not include_images:
        # Older clients require nonempty text and do not understand attachments.
        messages = [dict(row, content="[图片]") if isinstance(row, dict)
                    and row.get("images") and not row.get("content") else row for row in messages]
    return {
        **_conversation_payload(conversation),
        "messages": [
            {key: value for key, value in _message_payload(message).items()
             if (include_progress or key != "progress") and (include_feedback or key != "resolved") and (include_images or key != "images")}
            for message in messages if include_progress or _value(message, "reply_status") != "failed"
        ],
    }


def _raise_chat_error(error: ChatApplicationError) -> None:
    status_code = {
        "CONVERSATION_NOT_FOUND": 404,
        "FEEDBACK_MESSAGE_NOT_FOUND": 404,
        "FEEDBACK_INVALID": 422,
        "FEEDBACK_ALREADY_SUBMITTED": 409,
        "INVALID_CURSOR": 422,
        "GAME_INVALID": 422,
        "MESSAGE_REQUIRED": 422,
        "MESSAGE_TOO_LONG": 422,
        "IDEMPOTENCY_KEY_REQUIRED": 422,
        "IDEMPOTENCY_KEY_INVALID": 422,
        "CLIENT_MESSAGE_ID_INVALID": 422,
        "IDEMPOTENCY_CONFLICT": 409,
        "CHAT_RUN_IN_PROGRESS": 409,
        "CHAT_ACCOUNT_BUSY": 409,
        "CHAT_CONVERSATION_BUSY": 409,
        "CHAT_RUN_NOT_REPLAYABLE": 409,
        "CODEX_UNAVAILABLE": 503,
        "CHAT_IMAGE_INVALID": 422,
        "CHAT_IMAGE_UNAVAILABLE": 404,
        "CHAT_IMAGE_QUOTA": 409,
        "CHAT_IMAGES_DISABLED": 503,
    }.get(error.code, 500)
    raise ApiProblem(
        status_code=status_code,
        code=error.code,
        message=error.message,
    ) from error


@router.post("/conversations/{conversation_id}/messages/{message_id}/feedback")
def set_feedback(
    conversation_id: UUID,
    message_id: UUID,
    body: ChatFeedbackBody,
    principal: Principal = Depends(require_mutating_principal),
    application: ChatApplication = Depends(chat_application),
) -> dict[str, bool]:
    try:
        return {"resolved": application.set_feedback(principal, conversation_id, message_id, body.resolved)}
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)


@router.get("/conversations")
def list_conversations(
    principal: Principal = Depends(require_principal),
    application: ChatApplication = Depends(chat_application),
    cursor: str | None = None,
    limit: int = 20,
    game: Literal["wow", "poe2"] = "wow",
) -> dict[str, object]:
    try:
        page = application.list_conversations(principal, cursor, limit, game)
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
            game=body.game if body is not None else "wow",
            idempotency_key=idempotency_key or "",
        )
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)
    return _conversation_payload(conversation)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    include_progress: bool = Query(default=False, alias="includeProgress"),
    include_feedback: bool = Query(default=False, alias="includeFeedback"),
    include_images: bool = Query(default=False, alias="includeImages"),
    principal: Principal = Depends(require_principal),
    application: ChatApplication = Depends(chat_application),
) -> dict[str, object]:
    try:
        view = application.load_conversation(principal, conversation_id)
        return _detail_payload(view, include_progress, include_feedback, include_images)
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)


def _client_events(events: Iterator[ChatEvent], include_progress: bool) -> Iterator[ChatEvent]:
    sequence = 0
    try:
        for event in events:
            if not include_progress and event.event_type == "progress":
                continue
            sequence += 1
            yield event if include_progress else replace(event, sequence=sequence, completed_at="", duration_ms=None)
    finally:
        events.close()


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: UUID,
    body: ChatMessageBody,
    include_progress: bool = Query(default=False, alias="includeProgress"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_mutating_principal),
    application: ChatApplication = Depends(chat_application),
) -> StreamingResponse:
    try:
        events: Iterator[ChatEvent] = application.start_delivery(
            principal,
            conversation_id,
            body.content,
            client_message_id=body.client_message_id,
            idempotency_key=idempotency_key or "",
            **({"image_ids": body.image_ids} if body.image_ids else {}),
        )
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)
    events = _client_events(events, include_progress)
    try:
        first = next(events)
    except (ChatApplicationError, ImageError) as error:
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


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: UUID,
    principal: Principal = Depends(require_mutating_principal),
    application: ChatApplication = Depends(chat_application),
) -> dict[str, bool]:
    try:
        application.delete_conversation(principal, conversation_id)
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)
    return {"deleted": True}


@router.get("/image-capabilities")
def image_capabilities(principal: Principal = Depends(require_principal),
                       application: ChatApplication = Depends(chat_application)):
    return application.image_capabilities()


class ImageUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataUrl: str = Field(max_length=MAX_DATA_URL)


@router.post("/images", status_code=201)
async def upload_image(request: Request,
                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                 principal: Principal = Depends(require_mutating_principal),
                 application: ChatApplication = Depends(chat_application)):
    try:
        limit = MAX_DATA_URL + 128
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > limit:
                raise ApiProblem(status_code=413, code="CHAT_IMAGE_INVALID", message="图片过大，每张不超过 5 MiB。")
            raw.extend(chunk)
        try:
            body = ImageUploadBody.model_validate_json(bytes(raw))
        except ValidationError:
            raise ImageError() from None
        return await run_in_threadpool(application.upload_image, principal, body.dataUrl, idempotency_key or "")
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)


@router.get("/images/{image_id}")
def read_image(image_id: UUID, principal: Principal = Depends(require_principal),
               application: ChatApplication = Depends(chat_application)):
    from fastapi.responses import JSONResponse
    try:
        return JSONResponse(application.get_image(principal, image_id),
                            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)


@router.delete("/images/{image_id}")
def remove_image(image_id: UUID, principal: Principal = Depends(require_mutating_principal),
                 application: ChatApplication = Depends(chat_application)):
    try:
        application.remove_image(principal, image_id)
        return {"deleted": True}
    except (ChatApplicationError, ImageError) as error:
        _raise_chat_error(error)
