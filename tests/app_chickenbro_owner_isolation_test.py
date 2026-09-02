import unittest
from datetime import datetime, timezone
from uuid import UUID

from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal


class RecordingCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters):
        self.executed.append((" ".join(statement.split()), parameters))

    def fetchall(self):
        return list(self.rows)


class RecordingConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return self._cursor


class OwnerIsolationTest(unittest.TestCase):
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
            (owner.user_id, boundary_time, boundary_id, 21),
        )


if __name__ == "__main__":
    unittest.main()
