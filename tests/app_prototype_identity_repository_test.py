import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.app.identity.prototype import issue_prototype_session
from server.app.identity.repository import PostgresIdentityRepository


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_value = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_value


class PrototypeIdentityRepositoryTest(unittest.TestCase):
    def test_lookup_requires_active_prototype_owner(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-0000-0000-000000000022")
        session_id = UUID("00000000-0000-4000-8000-000000000021")
        connection = FakeConnection(rows=[{
            "id": session_id,
            "user_id": user_id,
            "token_sha256": "a" * 64,
            "expires_at": now + timedelta(minutes=30),
            "revoked_at": None,
        }])
        repository = PostgresIdentityRepository(lambda: connection)

        session = repository.get_prototype_session_by_token_hash(
            token_sha256="a" * 64,
            for_update=True,
        )

        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, user_id)
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("account_kind = 'prototype'", sql)
        self.assertIn("status = 'active'", sql)
        self.assertIn("FOR UPDATE", sql)
        self.assertEqual(params, ("a" * 64,))

    def test_create_user_and_session_are_marked_prototype_and_store_digest(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-0000-0000-000000000022")
        session_id = UUID("00000000-0000-4000-8000-000000000021")
        issued = issue_prototype_session(
            user_id=user_id,
            session_id=session_id,
            now=now,
            ttl=timedelta(minutes=30),
        )
        connection = FakeConnection()
        repository = PostgresIdentityRepository(lambda: connection)

        repository.create_prototype_user(user_id=user_id, now=now)
        repository.insert_prototype_session(issued.session, now=now)

        user_sql, user_params = connection.cursor_value.statements[0]
        session_sql, session_params = connection.cursor_value.statements[1]
        self.assertIn("account_kind", user_sql)
        self.assertIn("'prototype'", user_sql)
        self.assertEqual(user_params[0], user_id)
        self.assertIn("token_sha256", session_sql)
        self.assertNotIn(issued.token, session_sql)
        self.assertNotIn(issued.token, session_params)
        self.assertEqual(session_params[2], issued.session.token_sha256)


if __name__ == "__main__":
    unittest.main()
