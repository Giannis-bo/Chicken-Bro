import unittest
from datetime import datetime, timezone
from uuid import UUID

from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal


class RecordingCursor:
    def __init__(self, rows, *, fail_on_execute=None):
        self.rows = rows
        self.executed = []
        self.fail_on_execute = fail_on_execute
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters):
        self.executed.append((" ".join(statement.split()), parameters))
        if self.fail_on_execute == len(self.executed):
            raise RuntimeError("recorded statement failure")

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class RecordingConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.enter_count = 0
        self.exit_exception_type = None

    def __enter__(self):
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.exit_exception_type = exc_type
        return False

    def cursor(self):
        return self._cursor


class OwnerIsolationTest(unittest.TestCase):
    def test_postgres_conversation_create_uses_the_supplied_idempotent_identity(self):
        owner_id = UUID("00000000-0000-4000-8000-000000000031")
        conversation_id = UUID("00000000-0000-5000-8000-000000000032")
        now = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
        cursor = RecordingCursor([
            (
                conversation_id,
                owner_id,
                "跨端会话",
                "active",
                now,
                now,
                "wow",
            ),
        ])
        repository = PostgresChatRepository(lambda: RecordingConnection(cursor))

        conversation = repository.create_conversation(
            owner_id,
            conversation_id,
            "跨端会话",
            now,
        )

        self.assertEqual(conversation.id, conversation_id)
        statement, parameters = cursor.executed[0]
        self.assertIn("ON CONFLICT (id) DO NOTHING", statement)
        self.assertIn("RETURNING id, user_id, title, status, created_at, updated_at", statement)
        self.assertEqual(parameters[0], conversation_id)

    def test_postgres_conversation_page_uses_owner_scoped_keyset_query(self):
        owner = Principal(
            user_id=UUID("00000000-0000-0000-0000-000000000041"),
            session_kind="web_cookie",
        )
        boundary_time = datetime(2026, 9, 3, 10, 30, tzinfo=timezone.utc)
        boundary_id = UUID("00000000-0000-4000-8000-000000000042")
        row_id = UUID("00000000-0000-4000-8000-000000000043")
        cursor = RecordingCursor([
            (
                row_id,
                owner.user_id,
                "跨端历史",
                "active",
                boundary_time,
                boundary_time,
                "wow",
            ),
        ])
        repository = PostgresChatRepository(
            lambda: RecordingConnection(cursor),
        )
        self.assertTrue(
            hasattr(repository, "list_conversations"),
            "owner-scoped keyset repository method is missing",
        )

        rows = repository.list_conversations(
            owner.user_id,
            (boundary_time, boundary_id),
            21,
        )

        self.assertEqual([row.id for row in rows], [row_id])
        self.assertEqual(len(cursor.executed), 1)
        statement, parameters = cursor.executed[0]
        self.assertIn("WHERE user_id = %s", statement)
        self.assertIn("(updated_at, id) < (%s, %s)", statement)
        self.assertIn("ORDER BY updated_at DESC, id DESC LIMIT %s", statement)
        self.assertEqual(
            parameters,
            (owner.user_id, "wow", boundary_time, boundary_id, 21),
        )

    def test_postgres_idempotent_message_lookup_is_owner_scoped(self):
        owner_id = UUID("00000000-0000-0000-0000-000000000051")
        conversation_id = UUID("00000000-0000-4000-8000-000000000052")
        message_id = UUID("00000000-0000-4000-8000-000000000053")
        now = datetime(2026, 9, 3, 11, 0, tzinfo=timezone.utc)
        cursor = RecordingCursor([(
            message_id,
            conversation_id,
            owner_id,
            "user",
            "同一问题",
            "client-idempotent",
            now,
            [],
        )])
        repository = PostgresChatRepository(lambda: RecordingConnection(cursor))

        message = repository.get_message_by_client_id(owner_id, "client-idempotent")

        self.assertEqual(message.id, message_id)
        statement, parameters = cursor.executed[0]
        self.assertIn("WHERE user_id = %s AND client_message_id = %s", statement)
        self.assertEqual(parameters, (owner_id, "client-idempotent"))

    def test_postgres_agent_run_lookup_is_bound_to_owner_and_user_message(self):
        owner_id = UUID("00000000-0000-0000-0000-000000000061")
        conversation_id = UUID("00000000-0000-4000-8000-000000000062")
        user_message_id = UUID("00000000-0000-4000-8000-000000000063")
        run_id = UUID("00000000-0000-4000-8000-000000000064")
        assistant_id = UUID("00000000-0000-4000-8000-000000000065")
        now = datetime(2026, 9, 3, 11, 5, tzinfo=timezone.utc)
        cursor = RecordingCursor([
            (
                run_id,
                owner_id,
                conversation_id,
                user_message_id,
                assistant_id,
                "succeeded",
                "codex-test",
                "",
                now,
                now,
                "request-user-message",
            ),
        ])
        repository = PostgresChatRepository(
            lambda: RecordingConnection(cursor),
        )
        self.assertTrue(
            hasattr(repository, "get_run_for_user_message"),
            "owner-scoped AgentRun lookup is missing",
        )

        run = repository.get_run_for_user_message(owner_id, user_message_id)

        self.assertEqual(run.id, run_id)
        self.assertEqual(run.assistant_message_id, assistant_id)
        statement, parameters = cursor.executed[0]
        self.assertIn("WHERE user_id = %s AND user_message_id = %s", statement)
        self.assertEqual(parameters, (owner_id, user_message_id))

    def test_postgres_agent_run_idempotency_lookup_is_owner_scoped(self):
        owner_id = UUID("00000000-0000-0000-0000-000000000091")
        conversation_id = UUID("00000000-0000-4000-8000-000000000092")
        user_message_id = UUID("00000000-0000-4000-8000-000000000093")
        run_id = UUID("00000000-0000-4000-8000-000000000094")
        now = datetime(2026, 9, 3, 11, 20, tzinfo=timezone.utc)
        cursor = RecordingCursor([
            (
                run_id,
                owner_id,
                conversation_id,
                user_message_id,
                None,
                "streaming",
                "codex-test",
                "",
                now,
                None,
                "request-owner-scoped",
            ),
        ])
        repository = PostgresChatRepository(
            lambda: RecordingConnection(cursor),
        )
        self.assertTrue(
            hasattr(repository, "get_run_by_idempotency"),
            "owner-scoped idempotency lookup is missing",
        )

        run = repository.get_run_by_idempotency(
            owner_id,
            "request-owner-scoped",
        )

        self.assertEqual(run.id, run_id)
        self.assertEqual(run.idempotency_key, "request-owner-scoped")
        statement, parameters = cursor.executed[0]
        self.assertIn("WHERE user_id = %s AND idempotency_key = %s", statement)
        self.assertEqual(parameters, (owner_id, "request-owner-scoped"))

    def test_postgres_stale_run_recovery_is_owner_conversation_and_deadline_scoped(self):
        owner_id = UUID("00000000-0000-0000-0000-000000000095")
        conversation_id = UUID("00000000-0000-4000-8000-000000000096")
        stale_before = datetime(2026, 9, 3, 11, 18, tzinfo=timezone.utc)
        finished_at = datetime(2026, 9, 3, 11, 20, tzinfo=timezone.utc)
        cursor = RecordingCursor([])
        repository = PostgresChatRepository(lambda: RecordingConnection(cursor))

        recovered = repository.recover_stale_agent_runs(
            owner_id,
            conversation_id,
            stale_before,
            finished_at,
        )

        self.assertEqual(recovered, 1)
        statement, parameters = cursor.executed[0]
        self.assertIn("UPDATE chat.agent_runs", statement)
        self.assertIn("status = 'streaming'", statement)
        self.assertIn("started_at <= %s", statement)
        self.assertIn("user_id = %s", statement)
        self.assertIn("conversation_id = %s", statement)
        self.assertEqual(
            parameters,
            (
                finished_at,
                owner_id,
                conversation_id,
                stale_before,
            ),
        )

    def test_postgres_message_and_run_start_share_one_rollback_boundary(self):
        owner_id = UUID("00000000-0000-0000-0000-0000000000a1")
        conversation_id = UUID("00000000-0000-4000-8000-0000000000a2")
        now = datetime(2026, 9, 3, 11, 25, tzinfo=timezone.utc)
        cursor = RecordingCursor([(conversation_id,)], fail_on_execute=3)
        connection = RecordingConnection(cursor)
        repository = PostgresChatRepository(lambda: connection)
        self.assertTrue(
            hasattr(repository, "start_message_run"),
            "atomic message/run start is missing",
        )

        with self.assertRaisesRegex(RuntimeError, "recorded statement failure"):
            repository.start_message_run(
                owner_id,
                conversation_id,
                "原子消息",
                "client-atomic-repository",
                "request-atomic-repository",
                now,
                runtime_revision="codex:native:test-revision",
            )

        self.assertEqual(connection.enter_count, 1)
        self.assertIs(connection.exit_exception_type, RuntimeError)
        self.assertEqual(len(cursor.executed), 3)
        self.assertIn("INSERT INTO chat.messages", cursor.executed[1][0])
        self.assertIn("INSERT INTO chat.agent_runs", cursor.executed[2][0])

    def test_postgres_atomic_start_persists_codex_runtime_revision(self):
        owner_id = UUID("00000000-0000-0000-0000-0000000000b1")
        conversation_id = UUID("00000000-0000-4000-8000-0000000000b2")
        now = datetime(2026, 9, 3, 11, 30, tzinfo=timezone.utc)
        cursor = RecordingCursor([(conversation_id,)])
        repository = PostgresChatRepository(
            lambda: RecordingConnection(cursor),
        )

        try:
            _, run = repository.start_message_run(
                owner_id,
                conversation_id,
                "记录版本",
                "client-runtime-repository",
                "request-runtime-repository",
                now,
                runtime_revision="codex:native:test-revision",
            )
        except TypeError as error:
            self.fail(f"atomic start rejected runtime revision: {error}")

        self.assertEqual(run.runtime_revision, "codex:native:test-revision")
        statement, parameters = cursor.executed[2]
        self.assertIn("runtime_revision", statement)
        self.assertIn("codex:native:test-revision", parameters)

    def test_postgres_message_start_advances_conversation_order_in_the_same_transaction(self):
        owner_id = UUID("00000000-0000-0000-0000-0000000000d1")
        conversation_id = UUID("00000000-0000-4000-8000-0000000000d2")
        now = datetime(2026, 9, 3, 11, 32, tzinfo=timezone.utc)
        cursor = RecordingCursor([(conversation_id,)])
        connection = RecordingConnection(cursor)
        repository = PostgresChatRepository(lambda: connection)

        repository.start_message_run(
            owner_id,
            conversation_id,
            "刷新会话顺序",
            "client-order-repository",
            "request-order-repository",
            now,
            runtime_revision="codex:native:test-revision",
        )

        self.assertEqual(connection.enter_count, 1)
        statement, parameters = cursor.executed[-1]
        self.assertIn("UPDATE chat.conversations", statement)
        self.assertIn("status = 'active'", statement)
        self.assertEqual(parameters, (now, conversation_id, owner_id))

    def test_postgres_assistant_and_success_terminal_share_one_rollback_boundary(self):
        owner_id = UUID("00000000-0000-0000-0000-0000000000c1")
        conversation_id = UUID("00000000-0000-4000-8000-0000000000c2")
        run_id = UUID("00000000-0000-4000-8000-0000000000c3")
        now = datetime(2026, 9, 3, 11, 35, tzinfo=timezone.utc)
        cursor = RecordingCursor([], fail_on_execute=2)
        connection = RecordingConnection(cursor)
        repository = PostgresChatRepository(lambda: connection)
        self.assertTrue(
            hasattr(repository, "complete_run_with_assistant"),
            "atomic assistant/run completion is missing",
        )

        with self.assertRaisesRegex(RuntimeError, "recorded statement failure"):
            repository.complete_run_with_assistant(
                owner_id,
                conversation_id,
                run_id,
                "原子回答",
                now,
            )

        self.assertEqual(connection.enter_count, 1)
        self.assertIs(connection.exit_exception_type, RuntimeError)
        self.assertEqual(len(cursor.executed), 2)
        self.assertIn("INSERT INTO chat.messages", cursor.executed[0][0])
        self.assertIn("UPDATE chat.agent_runs", cursor.executed[1][0])

    def test_postgres_assistant_completion_advances_conversation_order_in_the_same_transaction(self):
        owner_id = UUID("00000000-0000-0000-0000-0000000000e1")
        conversation_id = UUID("00000000-0000-4000-8000-0000000000e2")
        run_id = UUID("00000000-0000-4000-8000-0000000000e3")
        now = datetime(2026, 9, 3, 11, 40, tzinfo=timezone.utc)
        cursor = RecordingCursor([])
        connection = RecordingConnection(cursor)
        repository = PostgresChatRepository(lambda: connection)

        repository.complete_run_with_assistant(
            owner_id,
            conversation_id,
            run_id,
            "完成后刷新顺序",
            now,
        )

        self.assertEqual(connection.enter_count, 1)
        self.assertEqual(len(cursor.executed), 3)
        statement, parameters = cursor.executed[2]
        self.assertIn("UPDATE chat.conversations", statement)
        self.assertIn("status = 'active'", statement)
        self.assertEqual(parameters, (now, conversation_id, owner_id))


if __name__ == "__main__":
    unittest.main()
