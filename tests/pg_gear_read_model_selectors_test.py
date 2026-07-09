#!/usr/bin/env python3
import unittest


class PgGearReadModelSelectorsTest(unittest.TestCase):
    def test_build_initial_gear_read_model_fragment_compacts_baseline_template(self):
        from server.pg_gear_read_model_selectors import build_initial_gear_read_model_fragment

        baseline_template = {
            "gearItems": [
                {
                    "id": "cloth-head",
                    "itemId": "cloth-head",
                    "slot": "head",
                    "simcSlot": "head",
                    "name": "Cloth Head",
                    "displayName": "Cloth Head",
                    "itemLevel": 707,
                    "ilevel": 707,
                    "bonusIds": [123],
                    "simcReady": True,
                    "socketOptions": [{"id": "socket-hidden"}],
                },
                {
                    "id": "duplicate-head",
                    "itemId": "duplicate-head",
                    "slot": "head",
                    "simcSlot": "head",
                    "name": "Duplicate Head",
                    "itemLevel": 700,
                    "simcReady": True,
                },
                {
                    "id": "bad-slot",
                    "itemId": "bad-slot",
                    "slot": "invalid",
                    "name": "Bad Slot",
                    "simcReady": True,
                },
            ]
        }

        read_model = build_initial_gear_read_model_fragment(
            baseline_template,
            "mage",
            "arcane",
            compact=True,
        )

        head_group = next(group for group in read_model["replacementCandidates"] if group["slot"] == "head")
        self.assertEqual(len(read_model["replacementCandidates"]), 16)
        self.assertEqual(head_group["label"], "头部")
        self.assertEqual(head_group["detailMode"], "partial")
        self.assertEqual(head_group["fullItemCount"], 1)
        self.assertEqual([item["itemId"] for item in head_group["items"]], ["cloth-head"])
        self.assertNotIn("socketOptions", head_group["items"][0])
        self.assertTrue(read_model["equippedSet"]["head"]["slotDetailAvailable"])
        self.assertEqual(read_model["equippedSet"]["head"]["detailMode"], "summary")
        self.assertEqual([item["itemId"] for item in read_model["baselineSet"]], ["cloth-head", "duplicate-head", "bad-slot"])
        self.assertEqual(read_model["catalogItems"], read_model["baselineSet"][:120])
        self.assertEqual(read_model["readiness"]["selectedCount"], 3)
        self.assertEqual(read_model["slotReadiness"]["head"]["status"], "verified")
        self.assertEqual(read_model["slotReadiness"]["neck"]["status"], "blocked")

    def test_build_catalog_state_read_model_fragment_exposes_health_and_coverage_envelope(self):
        from server.pg_gear_read_model_selectors import build_catalog_state_read_model_fragment

        catalog_state = {
            "schemaRevision": "catalog-rev-test",
            "status": "verified",
            "checkedAt": "2026-07-09T08:30:00Z",
            "updatedAt": "2026-07-09T08:00:00Z",
            "itemDatabaseRevision": "items-rev-test",
            "variantRevision": "variants-rev-test",
            "slotCoverage": {"head": {"verified": 3}},
            "sourceCoverage": {"raid": {"verified": 4}},
            "observedVariantCount": 40,
            "verifiedObservedVariantCount": 39,
            "verifiedCount": 120,
            "partialCount": 8,
            "blockedCount": 2,
            "blockers": ["state blocker"],
        }
        catalog_blockers = ["sample blocker"]

        read_model = build_catalog_state_read_model_fragment(catalog_state, catalog_blockers)

        self.assertEqual(read_model["gearSchemaRevision"], "websim-gear-simulator-v1")
        self.assertEqual(read_model["gearCatalogRevision"], "catalog-rev-test")
        self.assertEqual(read_model["catalogStatus"], "verified")
        self.assertEqual(read_model["catalogHealthSummary"]["status"], "verified")
        self.assertEqual(read_model["catalogHealthSummary"]["verifiedVariantCount"], 120)
        self.assertEqual(read_model["catalogHealthSummary"]["blockers"], ["state blocker"])
        self.assertEqual(
            read_model["catalogCoverage"],
            {
                "slotCoverage": {"head": {"verified": 3}},
                "sourceCoverage": {"raid": {"verified": 4}},
                "observedVariantCount": 40,
                "verifiedObservedVariantCount": 39,
                "verifiedVariantCount": 120,
                "partialVariantCount": 8,
                "blockedVariantCount": 2,
            },
        )
        self.assertEqual(read_model["itemDatabaseRevision"], "items-rev-test")
        self.assertEqual(read_model["variantRevision"], "variants-rev-test")
        self.assertEqual(read_model["catalogCheckedAt"], "2026-07-09T08:30:00Z")
        self.assertEqual(read_model["catalogBlockers"], ["sample blocker"])

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
