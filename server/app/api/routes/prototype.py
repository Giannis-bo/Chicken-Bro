from collections.abc import Iterator, Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import (
    prototype_chat_application,
    prototype_identity_application,
    prototype_simulation_application,
    require_prototype_principal,
    chickenbro_source_gateway,
)
from server.app.api.errors import ApiProblem
from server.app.chickenbro.application import ChatApplicationError, PrototypeChatApplication
from server.app.chickenbro.stream import ChatEvent, serialize_sse_event
from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    SourceGatewayUnauthorized,
)
from server.app.identity.prototype import (
    PrototypeIdentityApplication,
    PrototypePrincipal,
)
from server.app.simulation.application import (
    PrototypeSimulationApplication,
    SimulationApplicationError,
    SimulationJobView,
)
from server.app.simulation.domain import SimulationResult, SourceSnapshot


router = APIRouter()


class ConversationCreateBody(BaseModel):
    title: str = "炸鸡队长对话"


class ChatMessageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content: str
    client_message_id: str | None = Field(default=None, alias="clientMessageId")


class SourceSnapshotCreateBody(BaseModel):
    source_url: str = Field(alias="sourceUrl")

    model_config = ConfigDict(populate_by_name=True)


class SimulationCreateBody(BaseModel):
    snapshot_id: UUID = Field(alias="snapshotId")
    scenario: dict[str, object]

    model_config = ConfigDict(populate_by_name=True)


class SourceGatewayQueryBody(BaseModel):
    provider: str
    target: str

    model_config = ConfigDict(extra="forbid")


def _value(row: object, key: str, default: object = None) -> object:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _iso(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _conversation_payload(view: object, request: Request) -> dict[str, object]:
    if isinstance(view, dict) and "conversation" in view:
        conversation = view["conversation"]
        messages = view.get("messages", [])
    else:
        conversation = view
        messages = []
    status = _value(conversation, "status", "")
    return {
        "conversationId": str(_value(conversation, "id", "")),
        "title": str(_value(conversation, "title", "")),
        "status": str(getattr(status, "value", status)),
        "createdAt": _iso(_value(conversation, "created_at", "")),
        "updatedAt": _iso(_value(conversation, "updated_at", "")),
        "messages": [
            {
                "messageId": str(_value(message, "id", "")),
                "role": str(getattr(_value(message, "role", ""), "value", _value(message, "role", ""))),
                "content": str(_value(message, "content", "")),
                "createdAt": _iso(_value(message, "created_at", "")),
            }
            for message in messages
        ],
        "requestId": request.state.request_id,
    }


def _raise_chat_error(error: ChatApplicationError) -> None:
    status_code = {
        "CONVERSATION_NOT_FOUND": 404,
        "MESSAGE_REQUIRED": 422,
        "MESSAGE_TOO_LONG": 422,
        "IDEMPOTENCY_KEY_REQUIRED": 422,
        "CLIENT_MESSAGE_ID_INVALID": 422,
        "IDEMPOTENCY_KEY_INVALID": 422,
        "MESSAGE_ALREADY_EXISTS": 409,
    }.get(error.code, 500)
    raise ApiProblem(status_code=status_code, code=error.code, message=error.message) from error


def _raise_simulation_error(error: SimulationApplicationError) -> None:
    status_code = {
        "INVALID_LINK": 422,
        "SIMULATION_NOT_FOUND": 404,
        "SNAPSHOT_NOT_FOUND": 404,
        "SNAPSHOT_NOT_READY": 409,
        "IDEMPOTENCY_KEY_REQUIRED": 422,
        "IDEMPOTENCY_KEY_INVALID": 422,
        "SCENARIO_INVALID": 422,
        "TALENTS_INVALID": 422,
        "PROFILE_TOO_LARGE": 422,
        "COMPILER_UNAVAILABLE": 503,
        "RUNTIME_UNAVAILABLE": 503,
    }.get(error.code, 500)
    raise ApiProblem(status_code=status_code, code=error.code, message=error.message) from error


def _snapshot_payload(snapshot: SourceSnapshot, request: Request) -> dict[str, object]:
    blockers = snapshot.snapshot.get("readinessBlockers", []) if isinstance(snapshot.snapshot, Mapping) else []
    return {
        "snapshotId": str(snapshot.id),
        "provider": snapshot.provider.value,
        "sourceUrl": snapshot.source_url,
        "sourceKey": snapshot.source_key,
        "revision": snapshot.revision,
        "readiness": snapshot.readiness.value,
        "blockers": list(blockers) if isinstance(blockers, list) else [],
        "snapshot": dict(snapshot.snapshot),
        "provenance": dict(snapshot.provenance),
        "rawSha256": snapshot.raw_sha256,
        "fetchedAt": snapshot.fetched_at.isoformat(),
        "requestId": request.state.request_id,
    }


def _job_payload(view: SimulationJobView, request: Request) -> dict[str, object]:
    job = view.job
    result = view.result
    payload: dict[str, object] = {
        "jobId": str(job.id),
        "snapshotId": str(job.snapshot_id),
        "status": job.status.value,
        "scenarioHash": job.scenario_hash,
        "compilerRevision": job.compiler_revision,
        "runtimeRevision": job.runtime_revision,
        "errorCode": job.public_error_code or None,
        "createdAt": job.created_at.isoformat(),
        "updatedAt": job.updated_at.isoformat(),
        "requestId": request.state.request_id,
    }
    if isinstance(result, SimulationResult):
        payload["result"] = {
            "profileSha256": result.profile_sha256,
            "metric": {
                "name": result.primary_metric_name,
                "value": result.primary_metric_value,
            },
            "compilerRevision": result.compiler_revision,
            "runtimeRevision": result.runtime_revision,
            "provenance": dict(result.result.get("provenance", {})),
            "createdAt": result.created_at.isoformat(),
        }
    return payload


@router.post("/api/v2/prototype/sessions", status_code=201)
def create_prototype_session(
    request: Request,
    application: PrototypeIdentityApplication = Depends(prototype_identity_application),
) -> dict[str, object]:
    if not request.app.state.settings.prototype_enabled:
        raise ApiProblem(
            status_code=503,
            code="PROTOTYPE_DISABLED",
            message="Web prototype is not enabled",
        )
    issued = application.create_session()
    return {
        "mode": "prototype",
        "sessionToken": issued.token,
        "expiresAt": issued.session.expires_at.isoformat(),
        "requestId": request.state.request_id,
    }


@router.post("/api/v2/prototype/sessions/revoke")
def revoke_prototype_session(
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeIdentityApplication = Depends(prototype_identity_application),
) -> dict[str, object]:
    application.revoke(principal)
    return {"revoked": True, "requestId": request.state.request_id}


@router.post("/api/v2/internal/chickenbro/source-query")
def query_chickenbro_source_gateway(
    body: SourceGatewayQueryBody,
    request: Request,
    capability: str | None = Header(default=None, alias="X-Chickenbro-Source-Gateway"),
    gateway: ChickenbroSourceGateway = Depends(chickenbro_source_gateway),
) -> dict[str, object]:
    try:
        result = gateway.query(capability or "", body.provider, body.target)
    except SourceGatewayUnauthorized as error:
        raise ApiProblem(
            status_code=401,
            code=SourceGatewayUnauthorized.code,
            message="source gateway capability is required",
        ) from error
    return {**dict(result), "requestId": request.state.request_id}


@router.post("/api/v2/prototype/conversations", status_code=201)
def create_conversation(
    body: ConversationCreateBody | None,
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeChatApplication = Depends(prototype_chat_application),
) -> dict[str, object]:
    try:
        conversation = application.create_conversation(principal, body.title if body else "炸鸡队长对话")
    except ChatApplicationError as error:
        _raise_chat_error(error)
    return _conversation_payload(conversation, request)


@router.get("/api/v2/prototype/conversations/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeChatApplication = Depends(prototype_chat_application),
) -> dict[str, object]:
    try:
        view = application.load_conversation(principal, conversation_id)
    except ChatApplicationError as error:
        _raise_chat_error(error)
    return _conversation_payload(view, request)


@router.post("/api/v2/prototype/conversations/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: UUID,
    body: ChatMessageBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeChatApplication = Depends(prototype_chat_application),
) -> StreamingResponse:
    if not idempotency_key or any(character.isspace() for character in idempotency_key):
        raise ApiProblem(status_code=422, code="IDEMPOTENCY_KEY_REQUIRED", message="Idempotency-Key is required")
    events: Iterator[ChatEvent] = application.stream_message(
        principal,
        conversation_id,
        body.content,
        client_message_id=body.client_message_id,
        idempotency_key=idempotency_key,
    )
    try:
        first = next(events)
    except ChatApplicationError as error:
        _raise_chat_error(error)
    except StopIteration:
        raise ApiProblem(status_code=500, code="CODEX_EXECUTION_FAILED", message="stream did not start") from None

    def frames() -> Iterator[str]:
        yield serialize_sse_event(first)
        for event in events:
            yield serialize_sse_event(event)

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/v2/prototype/source-snapshots", status_code=201)
def resolve_source_snapshot(
    body: SourceSnapshotCreateBody,
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeSimulationApplication = Depends(prototype_simulation_application),
) -> dict[str, object]:
    try:
        snapshot = application.resolve_source(principal, body.source_url)
    except SimulationApplicationError as error:
        _raise_simulation_error(error)
    return _snapshot_payload(snapshot, request)


@router.get("/api/v2/prototype/source-snapshots/{snapshot_id}")
def get_source_snapshot(
    snapshot_id: UUID,
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeSimulationApplication = Depends(prototype_simulation_application),
) -> dict[str, object]:
    try:
        snapshot = application.read_snapshot(principal, snapshot_id)
    except SimulationApplicationError as error:
        _raise_simulation_error(error)
    return _snapshot_payload(snapshot, request)


@router.post("/api/v2/prototype/simulations", status_code=202)
def submit_simulation(
    body: SimulationCreateBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeSimulationApplication = Depends(prototype_simulation_application),
) -> dict[str, object]:
    if not idempotency_key:
        raise ApiProblem(status_code=422, code="IDEMPOTENCY_KEY_REQUIRED", message="Idempotency-Key is required")
    try:
        job = application.submit(principal, body.snapshot_id, body.scenario, idempotency_key)
        view = application.read_job(principal, job.id)
    except SimulationApplicationError as error:
        _raise_simulation_error(error)
    return _job_payload(view, request)


@router.get("/api/v2/prototype/simulations/{job_id}")
def get_simulation(
    job_id: UUID,
    request: Request,
    principal: PrototypePrincipal = Depends(require_prototype_principal),
    application: PrototypeSimulationApplication = Depends(prototype_simulation_application),
) -> dict[str, object]:
    try:
        view = application.read_job(principal, job_id)
    except SimulationApplicationError as error:
        _raise_simulation_error(error)
    return _job_payload(view, request)


__all__ = ["router"]
