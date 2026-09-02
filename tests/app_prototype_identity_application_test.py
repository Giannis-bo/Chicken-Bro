import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.app.identity.prototype import (
    PrototypeIdentityApplication,
    PrototypeSession,
)


class MemoryPrototypeIdentityRepository:
    def __init__(self):
        self.users = []
        self.sessions = {}

    def create_prototype_user(self, *, user_id, now):
        self.users.append((user_id, now))

    def insert_prototype_session(self, session, *, now):
        self.sessions[session.id] = session

    def get_prototype_session_by_token_hash(self, *, token_sha256, for_update=False):
        return next(
            (session for session in self.sessions.values() if session.token_sha256 == token_sha256),
            None,
        )

    def get_prototype_session(self, *, session_id, for_update=False):
        return self.sessions.get(session_id)

    def save_prototype_session(self, session, *, now):
        self.sessions[session.id] = session


class PrototypeIdentityApplicationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        self.repository = MemoryPrototypeIdentityRepository()
        self.application = PrototypeIdentityApplication(
            repository=self.repository,
            ttl=timedelta(minutes=30),
            clock=lambda: self.now,
        )

    def test_create_returns_opaque_token_and_internal_prototype_owner(self):
        issued = self.application.create_session()

        self.assertEqual(len(self.repository.users), 1)
        self.assertEqual(issued.principal.session_kind, "prototype")
        self.assertEqual(issued.principal.user_id, self.repository.users[0][0])
        self.assertNotIn(str(issued.principal.user_id), issued.token)
        self.assertNotEqual(issued.token, issued.session.token_sha256)
        self.assertEqual(issued.session.expires_at, self.now + timedelta(minutes=30))

    def test_resolve_and_revoke_are_owner_scoped(self):
        issued = self.application.create_session()

        resolved = self.application.resolve(issued.token)
        self.assertEqual(resolved, issued.principal)

        self.application.revoke(issued.principal)

        self.assertIsNone(self.application.resolve(issued.token))

    def test_expired_token_is_not_resolvable(self):
        issued = self.application.create_session()
        self.now = self.now + timedelta(minutes=30)

        self.assertIsNone(self.application.resolve(issued.token))


if __name__ == "__main__":
    unittest.main()
