from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from server.app.chickenbro.domain import AgentRun, AgentRunStatus, Conversation, Message, MessageRole


class ConversationRepository(Protocol):
    def list_for_user(self, user_id: UUID, *, limit: int, before: datetime | None) -> Sequence[Conversation]:
        raise NotImplementedError


class MessageRepository(Protocol):
    def list_for_conversation(self, user_id: UUID, conversation_id: UUID) -> Sequence[Message]:
        raise NotImplementedError


class AgentRunRepository(Protocol):
    def save(self, run: AgentRun) -> None:
        raise NotImplementedError


class CodexPort(Protocol):
    def stream(self, *, user_id: UUID, conversation_id: UUID, messages: Sequence[Message]):
        raise NotImplementedError


class ChatRepository(Protocol):
    def create_conversation(self, user_id: UUID, title: str, now: datetime) -> Any:
        raise NotImplementedError

    def get_conversation(self, user_id: UUID, conversation_id: UUID) -> Any | None:
        raise NotImplementedError

    def list_conversations(
        self,
        user_id: UUID,
        boundary: tuple[datetime, UUID] | None,
        limit: int,
    ) -> Sequence[Any]:
        raise NotImplementedError

    def list_messages(self, user_id: UUID, conversation_id: UUID) -> Sequence[Any]:
        raise NotImplementedError

    def find_message_by_client_id(
        self,
        user_id: UUID,
        conversation_id: UUID,
        client_message_id: str | None,
    ) -> Any | None:
        raise NotImplementedError

    def get_message_by_client_id(
        self,
        user_id: UUID,
        client_message_id: str,
    ) -> Any | None:
        raise NotImplementedError

    def get_run_for_user_message(
        self,
        user_id: UUID,
        user_message_id: UUID,
    ) -> Any | None:
        raise NotImplementedError

    def get_run_by_idempotency(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> Any | None:
        raise NotImplementedError

    def get_agent_run(self, user_id: UUID, run_id: UUID) -> Any | None:
        raise NotImplementedError

    def insert_message(
        self,
        user_id: UUID,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        client_message_id: str | None,
        now: datetime,
    ) -> Any:
        raise NotImplementedError

    def start_message_run(
        self,
        user_id: UUID,
        conversation_id: UUID,
        content: str,
        client_message_id: str | None,
        idempotency_key: str,
        now: datetime,
        *,
        runtime_revision: str,
    ) -> tuple[Any, Any]:
        raise NotImplementedError

    def complete_run_with_assistant(
        self,
        user_id: UUID,
        conversation_id: UUID,
        run_id: UUID,
        content: str,
        now: datetime,
    ) -> Any:
        raise NotImplementedError

    def start_agent_run(
        self,
        user_id: UUID,
        conversation_id: UUID,
        user_message_id: UUID,
        now: datetime,
        *,
        idempotency_key: str,
        runtime_revision: str = "codex:native:unversioned",
    ) -> Any:
        raise NotImplementedError

    def finish_agent_run(
        self,
        user_id: UUID,
        run_id: UUID,
        status: AgentRunStatus,
        assistant_message_id: UUID | None,
        public_error_code: str,
        finished_at: datetime,
    ) -> None:
        raise NotImplementedError


PrototypeChatRepository = ChatRepository
