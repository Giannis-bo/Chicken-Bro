from datetime import datetime, timedelta, timezone
from uuid import UUID
import unittest

from server.app.identity.domain import Principal, WebLoginSessionStatus
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


class AppIdentityRepositoryTest(unittest.TestCase):
    def test_locked_web_session_maps_only_digest_columns_and_owner_identity(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        session_id = UUID("00000000-0000-4000-8000-000000000021")
        user_id = UUID("00000000-0000-0000-0000-000000000022")
        connection = FakeConnection(rows=[{
            "id": session_id,
            "scene_ticket_sha256": "a" * 64,
            "browser_verifier_sha256": "b" * 64,
            "idempotency_key_sha256": "c" * 64,
            "user_id": user_id,
            "status": "pending",
            "expires_at": now + timedelta(minutes=5),
            "exchanged_at": None,
        }])
        repository = PostgresIdentityRepository(lambda: connection)

        session = repository.get_web_login_session(session_id=session_id, for_update=True)

        self.assertIsNotNone(session)
        self.assertEqual(session.id, session_id)
        self.assertEqual(session.status, WebLoginSessionStatus.PENDING)
        self.assertEqual(session.idempotency_key_sha256, "c" * 64)
        self.assertFalse(hasattr(session, "scene_ticket"))
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("WHERE id = %s", sql)
        self.assertIn("FOR UPDATE", sql)
        self.assertEqual(params, (session_id,))

    def test_auth_session_lookup_is_scoped_to_kind_and_expiry(self):
        connection = FakeConnection(rows=[("00000000-0000-0000-0000-000000000022",)])
        repository = PostgresIdentityRepository(lambda: connection)
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)

        principal = repository.resolve_auth_session(
            token_hash="d" * 64,
            kind="mini_bearer",
            now=now,
        )

        self.assertEqual(principal, Principal(
            user_id=UUID("00000000-0000-0000-0000-000000000022"),
            session_kind="mini_bearer",
        ))
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("kind = %s", sql)
        self.assertIn("revoked_at IS NULL", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertEqual(params, ("d" * 64, "mini_bearer", now))
