from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from server.app.chickenbro.domain import (
    AgentRun,
    AgentRunStatus,
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
)


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict):
        return row[key]
    return row[index]


class PostgresChatRepository:
    """Owner-scoped repository for the additive v2 chat tables."""

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def create_conversation(self, user_id: UUID, title: str, now: datetime) -> Conversation:
        conversation_id = uuid4()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat.conversations (id, user_id, title, status, created_at, updated_at)
                    VALUES (%s, %s, %s, 'active', %s, %s)
                    """,
                    (conversation_id, user_id, title, now, now),
                )
        return Conversation(
            id=conversation_id,
            user_id=user_id,
            title=title,
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def get_conversation(self, user_id: UUID, conversation_id: UUID) -> Conversation | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, title, status, created_at, updated_at
                    FROM chat.conversations
                    WHERE user_id = %s AND id = %s
                    """,
                    (user_id, conversation_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._conversation_from_row(row)

    def list_conversations(
        self,
        user_id: UUID,
        boundary: tuple[datetime, UUID] | None,
        limit: int,
    ) -> Sequence[Conversation]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                if boundary is None:
                    cursor.execute(
                        """
                        SELECT id, user_id, title, status, created_at, updated_at
                        FROM chat.conversations
                        WHERE user_id = %s
                        ORDER BY updated_at DESC, id DESC LIMIT %s
                        """,
                        (user_id, limit),
                    )
                else:
                    updated_at, conversation_id = boundary
                    cursor.execute(
                        """
                        SELECT id, user_id, title, status, created_at, updated_at
                        FROM chat.conversations
                        WHERE user_id = %s
                          AND (updated_at, id) < (%s, %s)
                        ORDER BY updated_at DESC, id DESC LIMIT %s
                        """,
                        (user_id, updated_at, conversation_id, limit),
                    )
                rows = cursor.fetchall()
        return [self._conversation_from_row(row) for row in rows]

    def list_messages(self, user_id: UUID, conversation_id: UUID) -> Sequence[Message]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, conversation_id, user_id, role, content, client_message_id, created_at
                    FROM chat.messages
                    WHERE user_id = %s AND conversation_id = %s
                    ORDER BY created_at, id
                    """,
                    (user_id, conversation_id),
                )
                rows = cursor.fetchall()
        return [self._message_from_row(row) for row in rows]

    def find_message_by_client_id(
        self,
        user_id: UUID,
        conversation_id: UUID,
        client_message_id: str,
    ) -> Message | None:
        if not client_message_id:
            return None
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, conversation_id, user_id, role, content, client_message_id, created_at
                    FROM chat.messages
                    WHERE user_id = %s AND conversation_id = %s AND client_message_id = %s
                    """,
                    (user_id, conversation_id, client_message_id),
                )
                row = cursor.fetchone()
        return self._message_from_row(row) if row is not None else None

    def insert_message(
        self,
        user_id: UUID,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        client_message_id: str | None,
        now: datetime,
    ) -> Message:
        message_id = uuid4()
        role_value = role.value if isinstance(role, MessageRole) else str(role)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat.messages (
                        id, conversation_id, user_id, role, content, client_message_id, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (message_id, conversation_id, user_id, role_value, content, client_message_id, now),
                )
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
            role=MessageRole(role_value),
            content=content,
            client_message_id=client_message_id,
            created_at=now,
        )

    def start_agent_run(self, user_id: UUID, conversation_id: UUID, user_message_id: UUID, now: datetime) -> AgentRun:
        run_id = uuid4()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat.agent_runs (
                        id, user_id, conversation_id, user_message_id, status, started_at
                    )
                    VALUES (%s, %s, %s, %s, 'streaming', %s)
                    """,
                    (run_id, user_id, conversation_id, user_message_id, now),
                )
        return AgentRun(
            id=run_id,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=None,
            status=AgentRunStatus.STREAMING,
            runtime_revision="",
            public_error_code="",
            started_at=now,
            finished_at=None,
        )

    def finish_agent_run(
        self,
        user_id: UUID,
        run_id: UUID,
        status: AgentRunStatus,
        assistant_message_id: UUID | None,
        public_error_code: str,
        finished_at: datetime,
    ) -> None:
        status_value = status.value if isinstance(status, AgentRunStatus) else str(status)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE chat.agent_runs
                    SET status = %s,
                        assistant_message_id = %s,
                        public_error_code = %s,
                        finished_at = %s
                    WHERE id = %s AND user_id = %s AND status = 'streaming'
                    """,
                    (status_value, assistant_message_id, public_error_code[:160], finished_at, run_id, user_id),
                )

    @staticmethod
    def _message_from_row(row: Any) -> Message:
        return Message(
            id=UUID(str(_row_value(row, "id", 0))),
            conversation_id=UUID(str(_row_value(row, "conversation_id", 1))),
            user_id=UUID(str(_row_value(row, "user_id", 2))),
            role=MessageRole(str(_row_value(row, "role", 3))),
            content=str(_row_value(row, "content", 4) or ""),
            client_message_id=_row_value(row, "client_message_id", 5),
            created_at=_row_value(row, "created_at", 6),
        )

    @staticmethod
    def _conversation_from_row(row: Any) -> Conversation:
        return Conversation(
            id=UUID(str(_row_value(row, "id", 0))),
            user_id=UUID(str(_row_value(row, "user_id", 1))),
            title=str(_row_value(row, "title", 2) or ""),
            status=ConversationStatus(str(_row_value(row, "status", 3))),
            created_at=_row_value(row, "created_at", 4),
            updated_at=_row_value(row, "updated_at", 5),
        )


__all__ = ("PostgresChatRepository",)
