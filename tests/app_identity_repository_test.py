from datetime import datetime, timedelta, timezone
from uuid import UUID
import json
import unittest

from server.app.identity.domain import Principal, WebLoginSession, WebLoginSessionStatus
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
    def test_web_login_insert_reports_an_idempotency_conflict_without_raising(self):
        now = datetime(2026, 9, 2, 15, 27, tzinfo=timezone.utc)
        session = WebLoginSession(
            id=UUID("00000000-0000-4000-8000-000000000047"),
            scene_ticket_sha256="a" * 64,
            browser_verifier_sha256="b" * 64,
            idempotency_key_sha256="c" * 64,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now + timedelta(minutes=5),
            consumed_at=None,
        )
        connection = FakeConnection(rows=[None])
        repository = PostgresIdentityRepository(lambda: connection)

        inserted = repository.insert_web_login_session(session, now=now)

        self.assertIs(inserted, False)
        sql, _ = connection.cursor_value.statements[0]
        self.assertIn("ON CONFLICT DO NOTHING", sql)
        self.assertIn("RETURNING id", sql)

    def test_web_expiry_only_advances_live_states_after_the_deadline(self):
        """Catches a stale expiry write overwriting a consumed or cancelled ticket."""
        now = datetime(2026, 9, 2, 15, 26, tzinfo=timezone.utc)
        session_id = UUID("00000000-0000-4000-8000-000000000046")
        connection = FakeConnection(rows=[(session_id,)])
        repository = PostgresIdentityRepository(lambda: connection)

        expired = repository.expire_web_login_session(session_id=session_id, now=now)

        self.assertTrue(expired)
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("status = 'expired'", sql)
        self.assertIn("status IN ('pending', 'confirmed')", sql)
        self.assertIn("expires_at <= %s", sql)
        self.assertIn("RETURNING id", sql)
        self.assertIn(session_id, params)

    def test_web_cancel_is_conditional_on_the_live_verifier_bound_state(self):
        """Catches cancellation overwriting a consumed or concurrently confirmed state."""
        now = datetime(2026, 9, 2, 15, 25, tzinfo=timezone.utc)
        session_id = UUID("00000000-0000-4000-8000-000000000045")
        connection = FakeConnection(rows=[(session_id,)])
        repository = PostgresIdentityRepository(lambda: connection)

        cancelled = repository.cancel_web_login_session(
            session_id=session_id,
            browser_verifier_sha256="d" * 64,
            now=now,
        )

        self.assertTrue(cancelled)
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("status = 'cancelled'", sql)
        self.assertIn("status IN ('pending', 'confirmed')", sql)
        self.assertIn("browser_verifier_sha256 = %s", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertIn("RETURNING id", sql)
        self.assertIn(session_id, params)
        self.assertIn("d" * 64, params)

    def test_web_confirmation_claims_only_one_live_pending_ticket(self):
        """Catches two Mini users racing to overwrite the owner of one QR login."""
        now = datetime(2026, 9, 2, 15, 20, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-4000-8000-000000000043")
        connection = FakeConnection(rows=[(UUID("00000000-0000-4000-8000-000000000044"),)])
        repository = PostgresIdentityRepository(lambda: connection)

        claimed = repository.confirm_web_login_session(
            scene_ticket_sha256="c" * 64,
            user_id=user_id,
            now=now,
        )

        self.assertTrue(claimed)
        self.assertEqual(len(connection.cursor_value.statements), 1)
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("status = 'confirmed'", sql)
        self.assertIn("status = 'pending'", sql)
        self.assertIn("user_id IS NULL", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertIn("RETURNING id", sql)
        self.assertIn("c" * 64, params)
        self.assertIn(user_id, params)

    def test_web_exchange_consumes_ticket_and_issues_session_in_one_atomic_statement(self):
        """Catches releasing the row lock before issuing the single-use Web session."""
        now = datetime(2026, 9, 2, 15, 30, tzinfo=timezone.utc)
        session_id = UUID("00000000-0000-4000-8000-000000000041")
        user_id = UUID("00000000-0000-4000-8000-000000000042")
        connection = FakeConnection(rows=[(user_id,)])
        repository = PostgresIdentityRepository(lambda: connection)

        resolved_user_id = repository.consume_web_login_session_and_issue_auth_session(
            session_id=session_id,
            browser_verifier_sha256="a" * 64,
            expected_user_id=user_id,
            token_hash="b" * 64,
            now=now,
            expires_at=now + timedelta(hours=1),
        )

        self.assertEqual(resolved_user_id, user_id)
        self.assertEqual(len(connection.cursor_value.statements), 1)
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("WITH consumed AS", sql)
        self.assertIn("status = 'confirmed'", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertIn("INSERT INTO identity.auth_sessions", sql)
        self.assertIn("SELECT %s, user_id, 'web_cookie'", sql)
        self.assertIn(session_id, params)
        self.assertIn(user_id, params)
        self.assertIn("a" * 64, params)
        self.assertIn("b" * 64, params)

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

    def test_existing_provider_identity_rejects_conflicting_union_metadata(self):
        """Catches treating optional UnionID metadata as permission to relink an owner."""
        now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-4000-8000-000000000032")
        connection = FakeConnection(rows=[(user_id, "union-first")])
        repository = PostgresIdentityRepository(lambda: connection)

        with self.assertRaisesRegex(ValueError, "identity conflict"):
            repository.upsert_wechat_mini_identity(
                app_context="wx-app-a",
                provider_subject="provider-subject",
                union_id="union-second",
                now=now,
            )

    def test_identity_insert_path_does_not_require_runtime_delete_privilege(self):
        """Catches explicit owner cleanup instead of transaction rollback on insert conflict."""
        now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        existing_user_id = UUID("00000000-0000-4000-8000-000000000033")
        connection = FakeConnection(rows=[None, (existing_user_id, "union-second")])
        repository = PostgresIdentityRepository(lambda: connection)

        resolved = repository.upsert_wechat_mini_identity(
            app_context="wx-app-a",
            provider_subject="provider-subject",
            union_id="union-second",
            now=now,
        )

        self.assertEqual(resolved, existing_user_id)
        self.assertTrue(all(
            "DELETE FROM identity.users" not in sql
            for sql, _ in connection.cursor_value.statements
        ))

    def test_wechat_identity_lookup_and_upsert_use_the_exact_app_context_key(self):
        """Catches reverting to provider-subject-only lookup or ignoring UnionID metadata."""
        now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        user_id = UUID("00000000-0000-4000-8000-000000000031")
        connection = FakeConnection(rows=[None, (user_id, "optional-union")])
        repository = PostgresIdentityRepository(lambda: connection)

        resolved = repository.upsert_wechat_mini_identity(
            app_context="wx-app-a",
            provider_subject="provider-subject",
            union_id="optional-union",
            now=now,
        )

        self.assertEqual(resolved, user_id)
        statements = connection.cursor_value.statements
        advisory_sql, advisory_params = statements[0]
        self.assertIn("pg_advisory_xact_lock", advisory_sql)
        self.assertEqual(
            advisory_params,
            ("wechat_mini:wx-app-a:provider-subject",),
        )
        lookup_sql, lookup_params = statements[1]
        self.assertIn("provider = %s", lookup_sql)
        self.assertIn("app_context = %s", lookup_sql)
        self.assertIn("provider_subject = %s", lookup_sql)
        self.assertEqual(lookup_params, ("wechat_mini", "wx-app-a", "provider-subject"))
        upsert_sql, upsert_params = next(
            (sql, params)
            for sql, params in statements
            if "INSERT INTO identity.user_identities" in sql
        )
        self.assertIn("app_context", upsert_sql)
        self.assertIn("union_id", upsert_sql)
        self.assertNotIn("ON CONFLICT", upsert_sql)
        self.assertIn("RETURNING user_id", upsert_sql)
        self.assertIn("wx-app-a", upsert_params)
        self.assertIn("optional-union", upsert_params)

    def test_web_session_read_maps_only_digest_columns_and_owner_identity(self):
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
            "consumed_at": None,
        }])
        repository = PostgresIdentityRepository(lambda: connection)

        session = repository.get_web_login_session(session_id=session_id)

        self.assertIsNotNone(session)
        self.assertEqual(session.id, session_id)
        self.assertEqual(session.status, WebLoginSessionStatus.PENDING)
        self.assertEqual(session.idempotency_key_sha256, "c" * 64)
        self.assertFalse(hasattr(session, "scene_ticket"))
        sql, params = connection.cursor_value.statements[0]
        self.assertIn("WHERE id = %s", sql)
        self.assertNotIn("FOR UPDATE", sql)
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
        self.assertIn("JOIN identity.users", sql)
        self.assertIn("status = 'active'", sql)
        self.assertIn("kind = %s", sql)
        self.assertIn("revoked_at IS NULL", sql)
        self.assertIn("expires_at > %s", sql)
        self.assertEqual(params, ("d" * 64, "mini_bearer", now))
