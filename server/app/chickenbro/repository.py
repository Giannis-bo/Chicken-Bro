from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from server.app.chickenbro.domain import (
    AgentRun,
    ChatAccountBusy,
    AgentRunStatus,
    Conversation,
    ConversationUnavailable,
    ConversationBusy,
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

    def create_conversation(
        self,
        user_id: UUID,
        conversation_id: UUID,
        title: str,
        now: datetime,
    ) -> Conversation:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat.conversations (id, user_id, title, status, created_at, updated_at)
                    VALUES (%s, %s, %s, 'active', %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id, user_id, title, status, created_at, updated_at
                    """,
                    (conversation_id, user_id, title, now, now),
                )
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        """
                        SELECT id, user_id, title, status, created_at, updated_at
                        FROM chat.conversations
                        WHERE user_id = %s AND id = %s
                        FOR SHARE
                        """,
                        (user_id, conversation_id),
                    )
                    row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("idempotent conversation identity is owned by another user")
        return self._conversation_from_row(row)

    def archive_conversation(self, user_id: UUID, conversation_id: UUID) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status FROM chat.conversations WHERE user_id = %s AND id = %s FOR UPDATE",
                               (user_id, conversation_id))
                row = cursor.fetchone()
                if row is None:
                    raise ConversationUnavailable()
                if _row_value(row, "status", 0) == "archived":
                    return
                cursor.execute("SELECT 1 FROM chat.agent_runs WHERE user_id = %s AND conversation_id = %s AND status = 'streaming' LIMIT 1",
                               (user_id, conversation_id))
                if cursor.fetchone() is not None:
                    raise ConversationBusy()
                cursor.execute("UPDATE chat.conversations SET status = 'archived' WHERE user_id = %s AND id = %s",
                               (user_id, conversation_id))

    def get_conversation(self, user_id: UUID, conversation_id: UUID) -> Conversation | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, title, status, created_at, updated_at
                    FROM chat.conversations
                    WHERE user_id = %s AND id = %s AND status = 'active'
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
                        WHERE user_id = %s AND status = 'active'
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
                        WHERE user_id = %s AND status = 'active'
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

    def append_public_progress(self, user_id: UUID, run_id: UUID, text: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE chat.agent_runs SET public_progress = public_progress || %s
                       WHERE user_id = %s AND id = %s AND status = 'streaming'""",
                    (text, user_id, run_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("agent run was not streaming for progress")

    def list_run_presentations(self, user_id: UUID, conversation_id: UUID) -> list[dict[str, Any]]:
        keys = ("id", "assistant_message_id", "status", "started_at", "finished_at", "public_progress")
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id, assistant_message_id, status, started_at, finished_at, public_progress
                       FROM chat.agent_runs WHERE user_id = %s AND conversation_id = %s
                       ORDER BY started_at, id""", (user_id, conversation_id),
                )
                return [{key: _row_value(row, key, index) for index, key in enumerate(keys)}
                        for row in cursor.fetchall()]

    def get_message_by_client_id(
        self,
        user_id: UUID,
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
                    WHERE user_id = %s AND client_message_id = %s
                    """,
                    (user_id, client_message_id),
                )
                row = cursor.fetchone()
        return self._message_from_row(row) if row is not None else None

    def get_run_for_user_message(
        self,
        user_id: UUID,
        user_message_id: UUID,
    ) -> AgentRun | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, conversation_id, user_message_id,
                           assistant_message_id, status, runtime_revision,
                           public_error_code, started_at, finished_at,
                           idempotency_key
                    FROM chat.agent_runs
                    WHERE user_id = %s AND user_message_id = %s
                    """,
                    (user_id, user_message_id),
                )
                row = cursor.fetchone()
        return self._agent_run_from_row(row) if row is not None else None

    def get_run_by_idempotency(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> AgentRun | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id, conversation_id, user_message_id,
                           assistant_message_id, status, runtime_revision,
                           public_error_code, started_at, finished_at,
                           idempotency_key
                    FROM chat.agent_runs
                    WHERE user_id = %s AND idempotency_key = %s
                    """,
                    (user_id, idempotency_key),
                )
                row = cursor.fetchone()
        return self._agent_run_from_row(row) if row is not None else None

    def recover_stale_agent_runs(
        self,
        user_id: UUID,
        conversation_id: UUID | None,
        stale_before: datetime,
        finished_at: datetime,
    ) -> int:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE chat.agent_runs
                    SET status = 'failed',
                        assistant_message_id = NULL,
                        public_error_code = 'CODEX_EXECUTION_FAILED',
                        finished_at = %s
                    WHERE user_id = %s
                      {"AND conversation_id = %s" if conversation_id is not None else ""}
                      AND status = 'streaming'
                      AND started_at <= %s
                    """,
                    (finished_at, user_id, *((conversation_id,) if conversation_id is not None else ()), stale_before),
                )
                return int(cursor.rowcount)

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
    ) -> tuple[Message, AgentRun]:
        message_id = uuid4()
        run_id = uuid4()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                # Serialize message admission with soft deletion of this conversation.
                cursor.execute("SELECT id FROM chat.conversations WHERE user_id = %s AND id = %s AND status = 'active' FOR UPDATE",
                               (user_id, conversation_id))
                if cursor.fetchone() is None:
                    raise ConversationUnavailable()
                cursor.execute(
                    """
                    INSERT INTO chat.messages (
                        id, conversation_id, user_id, role, content, client_message_id, created_at
                    )
                    VALUES (%s, %s, %s, 'user', %s, %s, %s)
                    """,
                    (message_id, conversation_id, user_id, content, client_message_id, now),
                )
                try:
                    cursor.execute(
                        """
                        INSERT INTO chat.agent_runs (
                            id, user_id, conversation_id, user_message_id, status,
                            runtime_revision, started_at, idempotency_key
                        )
                        VALUES (%s, %s, %s, %s, 'streaming', %s, %s, %s)
                        """,
                        (
                            run_id,
                            user_id,
                            conversation_id,
                            message_id,
                            runtime_revision,
                            now,
                            idempotency_key,
                        ),
                    )
                except Exception as error:
                    if getattr(getattr(error, "diag", None), "constraint_name", None) == "agent_runs_one_streaming_per_user":
                        raise ChatAccountBusy("account already has a streaming reply") from error
                    raise
                cursor.execute(
                    """
                    UPDATE chat.conversations
                    SET updated_at = GREATEST(updated_at, %s)
                    WHERE id = %s AND user_id = %s AND status = 'active'
                    """,
                    (now, conversation_id, user_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("conversation was not active for message start")
        return (
            Message(
                id=message_id,
                conversation_id=conversation_id,
                user_id=user_id,
                role=MessageRole.USER,
                content=content,
                client_message_id=client_message_id,
                created_at=now,
            ),
            AgentRun(
                id=run_id,
                user_id=user_id,
                conversation_id=conversation_id,
                user_message_id=message_id,
                assistant_message_id=None,
                status=AgentRunStatus.STREAMING,
                runtime_revision=runtime_revision,
                public_error_code="",
                started_at=now,
                finished_at=None,
                idempotency_key=idempotency_key,
            ),
        )

    def complete_run_with_assistant(
        self,
        user_id: UUID,
        conversation_id: UUID,
        run_id: UUID,
        content: str,
        now: datetime,
    ) -> Message:
        assistant_id = uuid4()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat.messages (
                        id, conversation_id, user_id, role, content, client_message_id, created_at
                    )
                    VALUES (%s, %s, %s, 'assistant', %s, NULL, %s)
                    """,
                    (assistant_id, conversation_id, user_id, content, now),
                )
                cursor.execute(
                    """
                    UPDATE chat.agent_runs
                    SET status = 'succeeded',
                        assistant_message_id = %s,
                        public_error_code = '',
                        finished_at = %s
                    WHERE id = %s
                      AND user_id = %s
                      AND conversation_id = %s
                      AND status = 'streaming'
                    """,
                    (assistant_id, now, run_id, user_id, conversation_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("agent run was not streaming for completion")
                cursor.execute(
                    """
                    UPDATE chat.conversations
                    SET updated_at = GREATEST(updated_at, %s)
                    WHERE id = %s AND user_id = %s AND status = 'active'
                    """,
                    (now, conversation_id, user_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("conversation was not active for assistant completion")
        return Message(
            id=assistant_id,
            conversation_id=conversation_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=content,
            client_message_id=None,
            created_at=now,
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

    @staticmethod
    def _agent_run_from_row(row: Any) -> AgentRun:
        assistant_message_id = _row_value(row, "assistant_message_id", 4)
        finished_at = _row_value(row, "finished_at", 9)
        return AgentRun(
            id=UUID(str(_row_value(row, "id", 0))),
            user_id=UUID(str(_row_value(row, "user_id", 1))),
            conversation_id=UUID(str(_row_value(row, "conversation_id", 2))),
            user_message_id=UUID(str(_row_value(row, "user_message_id", 3))),
            assistant_message_id=(
                UUID(str(assistant_message_id))
                if assistant_message_id is not None
                else None
            ),
            status=AgentRunStatus(str(_row_value(row, "status", 5))),
            runtime_revision=str(_row_value(row, "runtime_revision", 6) or ""),
            public_error_code=str(_row_value(row, "public_error_code", 7) or ""),
            started_at=_row_value(row, "started_at", 8),
            finished_at=finished_at,
            idempotency_key=str(_row_value(row, "idempotency_key", 10) or ""),
        )


__all__ = ("PostgresChatRepository",)
