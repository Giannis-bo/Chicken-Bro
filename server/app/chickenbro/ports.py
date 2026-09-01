from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from server.app.chickenbro.domain import AgentRun, Conversation, Message


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
