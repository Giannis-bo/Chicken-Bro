import unittest


class SeasonRecommendedGearTest(unittest.TestCase):
    def setUp(self):
        import server.websim_payload as websim_payload
        self.websim_payload = websim_payload

    def gear_items(self, missing_slot=""):
        items = []
        for index, slot in enumerate(self.websim_payload.CANONICAL_GEAR_SLOTS, start=1):
            if slot == missing_slot:
                continue
            items.append(
                {
                    "slot": slot,
                    "simcSlot": slot,
                    "itemId": str(300000 + index),
                    "id": str(300000 + index),
                    "name": f"recommended_{slot}",
                    "ilevel": "707",
                    "bonus_id": "1808",
                    "simcReady": True,
                }
            )
        return items

    def test_builds_complete_recommended_baseline_template(self):
        from server.season_recommended_gear import build_season_recommended_gear_template

        template = build_season_recommended_gear_template(
            class_key="mage",
            spec_key="frost",
            gear_items=self.gear_items(),
            evidence={
                "optimizerRunId": "season-rec-test",
                "scenarioKey": "mplus_aoe",
                "talentAnchor": {"sourceKey": "raiderio", "evidenceTier": "verified"},
                "gearCatalogRevision": "gear-catalog-test",
                "simcRuntimeRevision": "simc-test",
                "candidateCount": 3,
                "simcRunCount": 3,
                "role": "damage",
                "score": {"primaryMetric": "dps", "primaryValue": 1000.0},
            },
        )

        self.assertEqual(template["sourceKey"], "season_recommendation")
        self.assertEqual(template["sourceName"], "当前赛季大秘境 AOE 推荐模板")
        self.assertEqual(template["payload"]["templateSlot"], "baseline")
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["sourceStatus"], "synced")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["payload"]["templateEvidence"]["recommendationConfidence"], "verified")
        self.assertTrue(template["canApplyGear"])

    def test_missing_slot_blocks_template(self):
        from server.season_recommended_gear import build_season_recommended_gear_template

        with self.assertRaises(ValueError) as error:
            build_season_recommended_gear_template(
                class_key="mage",
                spec_key="frost",
                gear_items=self.gear_items(missing_slot="trinket2"),
                evidence={"optimizerRunId": "season-rec-test"},
            )

        self.assertIn("missing canonical gear slots", str(error.exception))
        self.assertIn("trinket2", str(error.exception))

    def test_non_dps_policy_is_provisional(self):
        from server.season_recommended_gear import build_season_recommended_gear_template

        template = build_season_recommended_gear_template(
            class_key="priest",
            spec_key="discipline",
            gear_items=self.gear_items(),
            evidence={"optimizerRunId": "season-rec-test", "role": "healer"},
        )

        evidence = template["payload"]["templateEvidence"]
        self.assertEqual(evidence["recommendationConfidence"], "provisional")
        self.assertEqual(evidence["rolePolicy"]["objectiveKey"], "community_consensus_plus_simc_sanity")
