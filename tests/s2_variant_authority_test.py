import unittest

from server.s2_variant_authority import classify_variant_upgrade


class S2VariantAuthorityTest(unittest.TestCase):
    def test_current_group_is_verified_from_currency_and_extended_cost(self):
        variant = {
            "bonusListGroupId": "615",
            "bonusListIds": ["12826"],
            "bonusListGroupEntry": {
                "ID": 4423,
                "ItemBonusListGroupID": 615,
                "ItemBonusListID": 12826,
                "ItemExtendedCostID": 11462,
                "SequenceValue": 2,
            },
            "itemScalingEvidence": [
                {"type": 49, "itemLevel": 282, "status": "verified"}
            ],
            "upgradeGroupEvidence": {
                "groupId": "615",
                "groupFact": {
                    "ID": 615,
                    "ItemGroupIlvlScalingID": 12,
                    "PlayerConditionID": 143187,
                },
                "status": "observed",
            },
        }
        result = classify_variant_upgrade(
            variant,
            db2_rows={
                "ItemBonusListGroupEntry": [
                    {
                        **variant["bonusListGroupEntry"],
                        "ID": 4422 + rank - 1,
                        "ItemBonusListID": 12825 + rank - 1,
                        "ItemExtendedCostID": 11462 if rank > 1 else 0,
                        "SequenceValue": rank,
                    }
                    for rank in range(1, 9)
                ],
                "ItemExtendedCost": [
                    {
                        "ID": 11462,
                        "CurrencyID_0": 3443,
                        "CurrencyCount_0": 20,
                    }
                ],
                "CurrencyTypes": [
                    {
                        "ID": 3443,
                        "Name_lang": "Veteran Mistcrest",
                        "Description_lang": (
                            "Used to upgrade Veteran equipment in Midnight Season 2 "
                            "up to item levels 282-295."
                        ),
                    }
                ],
            },
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["trackKey"], "veteran")
        self.assertEqual(result["rank"], 2)
        self.assertEqual(result["maxRank"], 8)
        self.assertEqual(result["itemLevel"], 282)
        self.assertEqual(result["sourceEligibilityStatus"], "verified")

    def test_historical_group_is_explicitly_excluded(self):
        variant = {
            "bonusListGroupId": "609",
            "bonusListIds": ["12794"],
            "bonusListGroupEntry": {
                "ID": 4391,
                "ItemBonusListGroupID": 609,
                "ItemBonusListID": 12794,
                "ItemExtendedCostID": 10999,
                "SequenceValue": 2,
            },
            "itemScalingEvidence": [
                {"type": 49, "itemLevel": 237, "status": "verified"}
            ],
            "upgradeGroupEvidence": {
                "groupId": "609",
                "groupFact": {"ID": 609, "ItemGroupIlvlScalingID": 11},
                "status": "observed",
            },
        }
        result = classify_variant_upgrade(
            variant,
            db2_rows={
                "ItemBonusListGroupEntry": [variant["bonusListGroupEntry"]],
                "ItemExtendedCost": [
                    {"ID": 10999, "CurrencyID_0": 3341, "CurrencyCount_0": 20}
                ],
                "CurrencyTypes": [
                    {
                        "ID": 3341,
                        "Name_lang": "Veteran Dawncrest",
                        "Description_lang": (
                            "Used to upgrade Veteran equipment in Midnight Season 1."
                        ),
                    }
                ],
            },
        )

        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["reasonCode"], "OUT_OF_SCOPE_NON_S2_VARIANT_GROUP")
        self.assertEqual(result["trackStatus"], "excluded")

    def test_unqualified_branch_remains_unverified(self):
        result = classify_variant_upgrade(
            {
                "bonusListGroupId": None,
                "bonusListIds": ["13663"],
                "itemScalingEvidence": [],
            },
            db2_rows={},
        )

        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertEqual(result["reasonCode"], "VARIANT_TRACK_AUTHORITY_UNVERIFIED")
        self.assertEqual(result["trackStatus"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
