import unittest

from server.season_set_membership import build_set_membership, validate_set_membership


S2_BINDING = {
    "seasonId": "midnight-season-2",
    "scope": "end_game",
    "seasonRevision": "season-midnight-season-2:fixture",
    "status": "verified",
}


def _set_row(**overrides):
    row = {
        "setId": "1983",
        "setName": "Abyssal Regalia",
        "classKeys": ["mage"],
        "itemIds": ["1001", "1002"],
        "sourceRefs": ["blizzard:s2-tier-set"],
        "setBonusEvidence": [
            {
                "pieces": 2,
                "effectId": "s2-mage-2pc",
                "sourceRefs": ["simc:s2-tier-set"],
            }
        ],
    }
    row.update(overrides)
    return row


class SeasonSetMembershipTest(unittest.TestCase):
    def test_builds_one_verified_class_set_and_item_index(self):
        membership = build_set_membership(S2_BINDING, [_set_row()])

        self.assertEqual(membership["status"], "verified")
        self.assertTrue(membership["setMembershipRevision"].startswith("s2-sets:sha256:"))
        self.assertEqual(membership["sets"][0]["setId"], "1983")
        self.assertEqual(membership["itemsById"]["1001"]["itemSetId"], "1983")
        self.assertEqual(membership["itemsById"]["1001"]["classKeys"], ["mage"])
        self.assertEqual(validate_set_membership(membership), [])

    def test_missing_set_id_blocks_before_projection(self):
        membership = build_set_membership(S2_BINDING, [_set_row(setId="")])

        self.assertEqual(membership["status"], "blocked")
        self.assertEqual(
            [problem["code"] for problem in membership["problems"]],
            ["SET_ID_MISSING"],
        )
        self.assertEqual(membership["sets"], [])

    def test_conflicting_set_ids_block_the_shared_item(self):
        membership = build_set_membership(
            S2_BINDING,
            [
                _set_row(),
                _set_row(
                    setId="1984",
                    setName="Conflicting Regalia",
                    itemIds=["1002", "1003"],
                ),
            ],
        )

        self.assertEqual(membership["status"], "blocked")
        self.assertIn(
            "SET_MEMBERSHIP_CONFLICT",
            [problem["code"] for problem in membership["problems"]],
        )
        self.assertNotIn("1002", membership["itemsById"])
        self.assertIn("1001", membership["itemsById"])


if __name__ == "__main__":
    unittest.main()
