from datetime import datetime, timedelta, timezone
from uuid import UUID
import unittest

from server.app.identity.domain import (
    WebLoginSession,
    WebLoginSessionStatus,
    digest,
    new_opaque_token,
)


class AppAuthDomainTest(unittest.TestCase):
    def test_digest_and_opaque_tokens_never_use_plaintext_identity_state(self):
        self.assertEqual(digest("scene-ticket"), "8a3858703bd2aaf3dc4234c7bbbdf667f80bc5a67966b2170eba553becc7b372")
        token = new_opaque_token()
        self.assertGreaterEqual(len(token), 32)
        self.assertNotEqual(token, digest(token))

    def test_web_login_session_accepts_only_digest_idempotency_state(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        session = WebLoginSession(
            id=UUID("00000000-0000-4000-8000-000000000020"),
            scene_ticket_sha256="a" * 64,
            browser_verifier_sha256="b" * 64,
            idempotency_key_sha256="c" * 64,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now + timedelta(minutes=5),
            exchanged_at=None,
        )
        self.assertEqual(session.idempotency_key_sha256, "c" * 64)
        self.assertFalse(hasattr(session, "scene_ticket"))
        self.assertFalse(hasattr(session, "browser_verifier"))
