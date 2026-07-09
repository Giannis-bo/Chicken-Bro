#!/usr/bin/env python3
import unittest


class PgGearReadModelSelectorsTest(unittest.TestCase):
    def test_build_catalog_gear_read_model_fragment_groups_candidates_and_audits_blocked_items(self):
        from server.pg_gear_read_model_selectors import build_catalog_gear_read_model_fragment

        legal_head = {
            "id": "cloth-head",
            "itemId": "cloth-head",
            "slot": "head",
            "simcSlot": "head",
            "name": "Cloth Head",
            "displayName": "Cloth Head",
            "sourceType": "raid",
            "itemLevel": 707,
            "ilevel": 707,
            "armorType": "Cloth",
            "simcReady": True,
        }
        blocked_head = {
            **legal_head,
            "id": "mail-head",
            "itemId": "mail-head",
            "name": "Mail Head",
            "displayName": "Mail Head",
            "armorType": "Mail",
        }
        raw_options_by_slot = {
            "socket": {
                "head": [
                    {
                        "id": "socket-head",
                        "optionType": "socket",
                        "name": "Head Socket",
                        "simcOptions": {"gem_id": "213743"},
                        "status": "verified",
                    }
                ]
            },
            "enchant": {},
            "embellishment": {},
        }

        read_model = build_catalog_gear_read_model_fragment(
            [legal_head, blocked_head],
            raw_options_by_slot,
            "mage",
            "arcane",
            compact=True,
        )

        head_group = next(group for group in read_model["replacementCandidates"] if group["slot"] == "head")
        self.assertEqual([item["itemId"] for item in head_group["items"]], ["cloth-head"])
        self.assertNotIn("socketOptions", head_group["items"][0])
        self.assertEqual(
            head_group["socketOptions"],
            [
                {
                    "id": "socket-head",
                    "optionType": "socket",
                    "name": "Head Socket",
                    "simcOptions": {"gem_id": "213743"},
                    "status": "verified",
                }
            ],
        )
        self.assertEqual(read_model["readiness"]["simcReadyCount"], 1)
        self.assertEqual(read_model["slotReadiness"]["head"]["status"], "partial")
        self.assertEqual(read_model["slotReadiness"]["head"]["missingFields"], ["bonus_id/gem_id/enchant_id"])
        self.assertEqual(read_model["catalogItems"][0]["itemId"], "cloth-head")
        self.assertEqual(read_model["candidateLegalityAudit"]["excludedCandidateCount"], 1)
        self.assertEqual(read_model["candidateLegalityAudit"]["excludedExamples"][0]["itemId"], "mail-head")


if __name__ == "__main__":
    unittest.main()
