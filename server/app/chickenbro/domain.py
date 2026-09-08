from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ChatAccountBusy(RuntimeError):
    """An account already owns a streaming reply."""


class ConversationUnavailable(RuntimeError):
    pass


class ConversationBusy(RuntimeError):
    pass


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AgentRunStatus(str, Enum):
    STREAMING = "streaming"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Conversation:
    id: UUID
    user_id: UUID
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: MessageRole
    content: str
    client_message_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class AgentRun:
    id: UUID
    user_id: UUID
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID | None
    status: AgentRunStatus
    runtime_revision: str
    public_error_code: str
    started_at: datetime
    finished_at: datetime | None
    idempotency_key: str = ""


def transition_agent_run(
    current: AgentRunStatus,
    target: AgentRunStatus,
    *,
    assistant_message_id: UUID | None,
) -> AgentRunStatus:
    if current is not AgentRunStatus.STREAMING or target not in {
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.FAILED,
    }:
        raise ValueError("illegal agent run transition")
    if target is AgentRunStatus.SUCCEEDED and assistant_message_id is None:
        raise ValueError("assistant message is required before success")
    return target
