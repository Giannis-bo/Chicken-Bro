import unittest

from server.websim_journal_contract import (
    journal_discovery_state,
    require_complete_journal_discovery,
)


class WebsimJournalContractTest(unittest.TestCase):
    def test_explicit_complete_discovery_is_verified(self):
        state = journal_discovery_state(
            {
                "counts": {
                    "sourceStatus": "verified",
                    "membershipComplete": True,
                    "limits": {
                        "dungeonInstances": 20,
                        "raidInstances": 8,
                        "encounters": 200,
                        "items": 1000,
                    },
                    "truncation": {
                        "dungeonInstances": 0,
                        "raidInstances": 0,
                        "encounters": 0,
                        "items": 0,
                    },
                    "fetchFailureCount": 0,
                    "gaps": [],
                    "blockerCodes": [],
                    "blockers": [],
                    "errors": [],
                }
            }
        )

        self.assertEqual(state["sourceStatus"], "verified")
        self.assertTrue(state["membershipComplete"])
        self.assertEqual(state["errors"], [])

    def test_missing_counts_fail_closed(self):
        state = journal_discovery_state({})

        self.assertEqual(state["sourceStatus"], "blocked")
        self.assertFalse(state["membershipComplete"])
        self.assertIn(
            "SOURCE_DISCOVERY_COUNTS_MISSING",
            state["blockerCodes"],
        )
        self.assertIn(
            "SOURCE_MEMBERSHIP_COMPLETENESS_UNPROVEN",
            state["blockerCodes"],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "SOURCE_DISCOVERY_COUNTS_MISSING",
        ):
            require_complete_journal_discovery({})

    def test_success_flags_without_boundary_counts_fail_closed(self):
        state = journal_discovery_state(
            {
                "counts": {
                    "sourceStatus": "verified",
                    "membershipComplete": True,
                    "gaps": [],
                    "blockerCodes": [],
                    "blockers": [],
                    "errors": [],
                }
            }
        )

        self.assertEqual(state["sourceStatus"], "blocked")
        self.assertIn(
            "SOURCE_DISCOVERY_CONTRACT_INVALID",
            state["blockerCodes"],
        )

    def test_gap_blocks_even_when_source_claims_verified(self):
        state = journal_discovery_state(
            {
                "counts": {
                    "sourceStatus": "verified",
                    "membershipComplete": True,
                    "limits": {
                        "dungeonInstances": 20,
                        "raidInstances": 8,
                        "encounters": 200,
                        "items": 1000,
                    },
                    "truncation": {
                        "dungeonInstances": 0,
                        "raidInstances": 0,
                        "encounters": 0,
                        "items": 0,
                    },
                    "fetchFailureCount": 1,
                    "gaps": [
                        {
                            "kind": "fetch_failure",
                            "boundary": "item",
                            "identity": "250001",
                            "omittedCount": 0,
                            "evidenceRef": "blizzard:game-data:journal",
                        }
                    ],
                    "blockerCodes": [],
                    "blockers": [],
                    "errors": [],
                }
            }
        )

        self.assertEqual(state["sourceStatus"], "blocked")
        self.assertFalse(state["membershipComplete"])
        self.assertIn("SOURCE_FETCH_FAILED", state["blockerCodes"])


if __name__ == "__main__":
    unittest.main()
