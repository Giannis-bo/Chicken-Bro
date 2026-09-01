import unittest
from uuid import UUID

from server.app.chickenbro.domain import AgentRunStatus, transition_agent_run
from server.app.identity.domain import Principal
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
