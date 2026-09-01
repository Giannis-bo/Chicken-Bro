import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.app.chickenbro.domain import AgentRunStatus, transition_agent_run
from server.app.identity.domain import (
    Principal,
    WebLoginSession,
    WebLoginSessionStatus,
    cancel_web_login_session,
    confirm_web_login_session,
    exchange_web_login_session,
)
from server.app.simulation.domain import (
    SimulationJobStatus,
    SourceReadiness,
    transition_simulation_job,
)


class AppDomainTest(unittest.TestCase):
    def test_principal_is_internal_user_only(self):
        principal = Principal(user_id=UUID("00000000-0000-0000-0000-000000000001"), session_kind="mini_bearer")
        self.assertEqual(principal.session_kind, "mini_bearer")
        self.assertFalse(hasattr(principal, "openid"))
        self.assertFalse(hasattr(principal, "unionid"))

    def test_agent_run_requires_persisted_message_before_success(self):
        with self.assertRaisesRegex(ValueError, "assistant message"):
            transition_agent_run(AgentRunStatus.STREAMING, AgentRunStatus.SUCCEEDED, assistant_message_id=None)

    def test_simulation_job_rejects_queued_to_succeeded(self):
        with self.assertRaisesRegex(ValueError, "illegal simulation job transition"):
            transition_simulation_job(SimulationJobStatus.QUEUED, SimulationJobStatus.SUCCEEDED)

    def test_readiness_literals_match_the_parent_spec(self):
        self.assertEqual(
            {value.value for value in SourceReadiness},
            {
                "INVALID_LINK",
                "CHARACTER_NOT_FOUND",
                "ACCESS_RESTRICTED",
                "SNAPSHOT_UNAVAILABLE",
                "INCOMPLETE_FOR_SIMC",
                "READY_FOR_SIMC",
            },
        )

    def test_web_qr_login_requires_explicit_mini_confirmation_and_one_time_verifier(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        session = WebLoginSession(
            id=UUID("00000000-0000-4000-8000-000000000002"),
            scene_ticket_sha256="b" * 64,
            browser_verifier_sha256="a" * 64,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now + timedelta(minutes=2),
            exchanged_at=None,
        )
        self.assertFalse(hasattr(session, "scene_ticket"))
        self.assertFalse(hasattr(session, "browser_verifier"))
        with self.assertRaisesRegex(ValueError, "scene ticket"):
            confirm_web_login_session(
                session,
                scene_ticket_sha256="0" * 64,
                user_id=UUID("00000000-0000-0000-0000-000000000003"),
                now=now,
            )
        confirmed = confirm_web_login_session(
            session,
            scene_ticket_sha256="b" * 64,
            user_id=UUID("00000000-0000-0000-0000-000000000003"),
            now=now,
        )
        self.assertEqual(confirmed.status, WebLoginSessionStatus.CONFIRMED)
        exchanged = exchange_web_login_session(confirmed, verifier_sha256="a" * 64, now=now)
        self.assertEqual(exchanged.status, WebLoginSessionStatus.EXCHANGED)
        with self.assertRaisesRegex(ValueError, "already exchanged"):
            exchange_web_login_session(exchanged, verifier_sha256="a" * 64, now=now)

    def test_web_qr_login_rejects_wrong_verifier_and_expired_confirmation(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        session = WebLoginSession(
            id=UUID("00000000-0000-4000-8000-000000000004"),
            scene_ticket_sha256="d" * 64,
            browser_verifier_sha256="c" * 64,
            user_id=UUID("00000000-0000-0000-0000-000000000005"),
            status=WebLoginSessionStatus.CONFIRMED,
            expires_at=now + timedelta(minutes=2),
            exchanged_at=None,
        )
        with self.assertRaisesRegex(ValueError, "verifier"):
            exchange_web_login_session(session, verifier_sha256="e" * 64, now=now)
        cancelled = cancel_web_login_session(session, now=now)
        self.assertEqual(cancelled.status, WebLoginSessionStatus.CANCELLED)
        with self.assertRaisesRegex(ValueError, "cannot be cancelled"):
            cancel_web_login_session(cancelled, now=now)

        expired = WebLoginSession(
            id=UUID("00000000-0000-4000-8000-000000000006"),
            scene_ticket_sha256="f" * 64,
            browser_verifier_sha256="1" * 64,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now - timedelta(seconds=1),
            exchanged_at=None,
        )
        with self.assertRaisesRegex(ValueError, "expired"):
            confirm_web_login_session(
                expired,
                scene_ticket_sha256="f" * 64,
                user_id=UUID("00000000-0000-0000-0000-000000000007"),
                now=now,
            )
        expired_cancelled = cancel_web_login_session(expired, now=now)
        self.assertEqual(expired_cancelled.status, WebLoginSessionStatus.EXPIRED)
