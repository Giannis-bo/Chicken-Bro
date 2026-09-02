import unittest
from datetime import datetime, timezone
from uuid import UUID

from server.app.chickenbro.domain import AgentRunStatus, transition_agent_run
from server.app.identity.prototype import PrototypePrincipal


class ChickenbroDomainTest(unittest.TestCase):
    def test_successful_agent_run_requires_an_assistant_message(self):
        with self.assertRaisesRegex(ValueError, "assistant message"):
            transition_agent_run(
                AgentRunStatus.STREAMING,
                AgentRunStatus.SUCCEEDED,
                assistant_message_id=None,
            )

    def test_prototype_principal_is_explicitly_scoped(self):
        principal = PrototypePrincipal(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            session_id=UUID("00000000-0000-4000-8000-000000000002"),
        )
        self.assertEqual(principal.session_kind, "prototype")


if __name__ == "__main__":
    unittest.main()
