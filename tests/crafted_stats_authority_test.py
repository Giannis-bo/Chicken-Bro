import unittest

from server import crafted_stats_authority


class CraftedStatsAuthorityTest(unittest.TestCase):
    def test_builds_stable_single_and_pair_option_identities(self):
        self.assertEqual(
            crafted_stats_authority.crafted_stats_option_identity(
                "36",
                expected_count=1,
            ),
            {
                "key": "haste",
                "optionId": "crafted-stats-haste",
                "label": "急速",
                "value": "36",
                "statIds": ["36"],
            },
        )
        self.assertEqual(
            crafted_stats_authority.crafted_stats_option_identity(
                "49/32",
                expected_count=2,
            ),
            {
                "key": "crit-mastery",
                "optionId": "crafted-stats-crit-mastery",
                "label": "暴击 + 精通",
                "value": "32/49",
                "statIds": ["32", "49"],
            },
        )

    def test_rejects_duplicate_unknown_or_wrong_arity_stats(self):
        self.assertIsNone(
            crafted_stats_authority.crafted_stats_option_identity("36/36")
        )
        self.assertIsNone(
            crafted_stats_authority.crafted_stats_option_identity("36/999")
        )
        self.assertIsNone(
            crafted_stats_authority.crafted_stats_option_identity(
                "36/49",
                expected_count=1,
            )
        )
