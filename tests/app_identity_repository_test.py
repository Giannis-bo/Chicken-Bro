from datetime import datetime, timedelta, timezone
from uuid import UUID
import json
import unittest

from server.app.identity.domain import Principal
from server.app.identity.audit import AuthAuditEvent
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


    def test_auth_audit_insert_uses_only_the_validated_redacted_payload(self):
        now = datetime(2026, 9, 2, 15, 0, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-4000-8000-000000000034")
        event = AuthAuditEvent(
            event_type="auth.decision",
            request_id="00000000-0000-4000-8000-000000000035",
            user_id=user_id,
            session_kind="web_cookie",
            status_code=200,
            timestamp=now,
            reason_code="AUTHENTICATED",
        )
        connection = FakeConnection()
        repository = PostgresIdentityRepository(lambda: connection)

        repository.record_auth_audit(event)

        sql, params = connection.cursor_value.statements[-1]
        self.assertIn("INSERT INTO ops.audit_events", sql)
        self.assertIn("ON CONFLICT (event_type, subject_key) DO NOTHING", sql)
        serialized_payload = params[4]
        payload = json.loads(serialized_payload)
        self.assertIn("requestId", payload)
        for key in payload:
            self.assertNotRegex(key, r"(?i)token|cookie|openid|session_key|verifier|ticket|secret")


    def test_auth_session_lookup_is_scoped_to_kind_and_expiry(self):
        connection = FakeConnection(rows=[("00000000-0000-0000-0000-000000000022",)])
        repository = PostgresIdentityRepository(lambda: connection)
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)

        principal = repository.resolve_auth_session(
            token_hash="d" * 64,
            kind="web_cookie",
            now=now,
        )

        self.assertEqual(principal, Principal(
            user_id=UUID("00000000-0000-0000-0000-000000000022"),
            session_kind="web_cookie",
        ))
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("JOIN identity.users", sql)
        self.assertIn("status = 'active'", sql)
        self.assertIn("kind = %s", sql)
        self.assertIn("revoked_at IS NULL", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertEqual(params, ("d" * 64, "web_cookie", now))
