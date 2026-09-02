import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.app.identity.prototype import (
    PrototypePrincipal,
    issue_prototype_session,
    revoke_prototype_session,
    resolve_prototype_principal,
)


class PrototypeIdentityDomainTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

    def test_issue_stores_only_token_digest_and_resolves_scoped_principal(self):
        issued = issue_prototype_session(
            user_id=UUID("11111111-1111-4111-8111-111111111111"),
            session_id=UUID("22222222-2222-4222-8222-222222222222"),
            now=self.now,
            ttl=timedelta(hours=1),
        )

        self.assertNotEqual(issued.token, issued.session.token_sha256)
        self.assertNotIn(issued.token, repr(issued.session))
        principal = resolve_prototype_principal(issued.session, issued.token, now=self.now)
        self.assertIsInstance(principal, PrototypePrincipal)
        self.assertEqual(principal.user_id, issued.session.user_id)
        self.assertEqual(principal.session_id, issued.session.id)
        self.assertEqual(principal.session_kind, "prototype")

    def test_expired_or_wrong_token_does_not_resolve(self):
        issued = issue_prototype_session(
            user_id=UUID("11111111-1111-4111-8111-111111111111"),
            session_id=UUID("22222222-2222-4222-8222-222222222222"),
            now=self.now,
            ttl=timedelta(minutes=5),
        )

        self.assertIsNone(resolve_prototype_principal(issued.session, "wrong-token", now=self.now))
        self.assertIsNone(
            resolve_prototype_principal(
                issued.session,
                issued.token,
                now=self.now + timedelta(minutes=5),
            )
        )

    def test_revoked_session_does_not_resolve(self):
        issued = issue_prototype_session(
            user_id=UUID("11111111-1111-4111-8111-111111111111"),
            session_id=UUID("22222222-2222-4222-8222-222222222222"),
            now=self.now,
            ttl=timedelta(hours=1),
        )

        revoked = revoke_prototype_session(issued.session, now=self.now)

        self.assertIsNotNone(revoked.revoked_at)
        self.assertIsNone(resolve_prototype_principal(revoked, issued.token, now=self.now))


if __name__ == "__main__":
    unittest.main()
