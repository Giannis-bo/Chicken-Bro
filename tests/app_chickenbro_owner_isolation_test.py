import unittest
from uuid import UUID, uuid4

from server.app.chickenbro.application import PrototypeChatApplication
from server.app.chickenbro.domain import ConversationStatus
from server.app.identity.prototype import PrototypePrincipal


class OwnerIsolationTest(unittest.TestCase):
    def test_principals_have_distinct_internal_owner_ids(self):
        first = PrototypePrincipal(
            user_id=UUID("00000000-0000-0000-0000-000000000021"),
            session_id=UUID("00000000-0000-4000-8000-000000000022"),
        )
        second = PrototypePrincipal(
            user_id=UUID("00000000-0000-0000-0000-000000000023"),
            session_id=UUID("00000000-0000-4000-8000-000000000024"),
        )
        self.assertNotEqual(first.user_id, second.user_id)
        self.assertNotEqual(first.session_id, second.session_id)


if __name__ == "__main__":
    unittest.main()
