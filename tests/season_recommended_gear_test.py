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
        self.assertEqual(template["payload"]["templateEvidence"]["recommendationConfidence"], "provisional")
        self.assertEqual(template["payload"]["templateEvidence"]["simcReview"]["status"], "not_run")
        self.assertTrue(template["canApplyGear"])

    def test_dps_recommendation_only_becomes_verified_after_simc_review_passes(self):
        from server.season_recommended_gear import build_season_recommended_gear_template

        template = build_season_recommended_gear_template(
            class_key="mage",
            spec_key="frost",
            gear_items=self.gear_items(),
            evidence={
                "optimizerRunId": "season-rec-test",
                "scenarioKey": "mplus_aoe",
                "role": "damage",
                "simcReview": {
                    "triggered": True,
                    "status": "passed",
                    "result": {"winnerDps": 1000000, "runnerUpDps": 970000},
                },
            },
        )

        evidence = template["payload"]["templateEvidence"]
        self.assertEqual(evidence["recommendationConfidence"], "verified")
        self.assertEqual(evidence["finalConfidence"], "verified")

    def test_recommended_bis_template_does_not_keep_simc_blocker_after_passed_compare(self):
        from server.season_recommended_gear import build_recommended_bis_gear_template

        template = build_recommended_bis_gear_template(
            class_key="shaman",
            spec_key="elemental",
            gear_items=self.gear_items(),
            evidence={
                "status": "projected_bis",
                "scenarioKey": "mplus_aoe",
                "simc": {
                    "status": "passed",
                    "lowIterationRuns": 0,
                    "highIterationRuns": 1,
                    "pairwiseCompares": 0,
                    "winnerDps": 188418.99,
                    "winnerErrorPct": 0.031889607114364595,
                },
                "blockers": [
                    "pairwise gear compare has not run",
                    "observed anchor validation is pending",
                ],
            },
        )

        evidence = template["payload"]["templateEvidence"]
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["simc"]["status"], "passed")
        self.assertEqual(evidence["simc"]["highIterationRuns"], 1)
        self.assertNotIn("high-iteration SimC compare has not run", evidence["blockers"])
        self.assertIn("pairwise gear compare has not run", evidence["blockers"])
        self.assertIn("observed anchor validation is pending", evidence["blockers"])

    def test_elemental_shaman_low_versatility_is_strongly_penalized(self):
        from server.season_recommended_gear import select_season_recommended_gear

        selected, evidence = select_season_recommended_gear(
            "shaman",
            "elemental",
            {
                "head": [
                    {
                        "slot": "head",
                        "simcSlot": "head",
                        "itemId": "400001",
                        "id": "400001",
                        "name": "versatility_helm",
                        "ilevel": 715,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "intellect", "value": 1200},
                            {"key": "versatility", "value": 600},
                        ],
                    },
                    {
                        "slot": "head",
                        "simcSlot": "head",
                        "itemId": "400002",
                        "id": "400002",
                        "name": "mastery_haste_helm",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "intellect", "value": 1100},
                            {"key": "mastery", "value": 300},
                            {"key": "haste", "value": 300},
                        ],
                    },
                ],
            },
            scenario_key="mplus_aoe",
        )

        self.assertEqual(selected[0]["itemId"], "400002")
        head_decision = evidence["slotDecisions"]["head"]
        self.assertEqual(head_decision["selectedItemId"], "400002")
        self.assertTrue(head_decision["lowYieldStatPenalty"]["applied"])
        self.assertEqual(head_decision["lowYieldStatPenalty"]["stats"][0]["key"], "versatility")
        self.assertGreater(head_decision["lowYieldStatPenalty"]["stats"][0]["penalty"], 0)

    def test_elemental_shaman_default_priority_prefers_mastery_crit_over_haste_stack(self):
        from server.season_recommended_gear import select_season_recommended_gear

        selected, evidence = select_season_recommended_gear(
            "shaman",
            "elemental",
            {
                "neck": [
                    {
                        "slot": "neck",
                        "simcSlot": "neck",
                        "itemId": "405001",
                        "id": "405001",
                        "name": "haste_stack_neck",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [{"key": "haste", "value": 600}],
                    },
                    {
                        "slot": "neck",
                        "simcSlot": "neck",
                        "itemId": "405002",
                        "id": "405002",
                        "name": "mastery_crit_neck",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "mastery", "value": 350},
                            {"key": "crit", "value": 250},
                        ],
                    },
                ],
            },
            scenario_key="mplus_aoe",
        )

        self.assertEqual(selected[0]["itemId"], "405002")
        weights = evidence["statWeights"]["weights"]
        self.assertGreater(weights["mastery"], weights["crit"])
        self.assertGreater(weights["crit"], weights["haste"])
        self.assertGreater(weights["haste"], weights["versatility"])
        self.assertEqual(evidence["statWeights"]["priorityOrder"][:4], ["mastery", "crit", "haste", "versatility"])

    def test_blocked_stat_weight_payload_is_not_used_for_recommendation(self):
        from server.season_recommended_gear import select_season_recommended_gear

        selected, evidence = select_season_recommended_gear(
            "mage",
            "frost",
            {
                "head": [
                    {
                        "slot": "head",
                        "simcSlot": "head",
                        "itemId": "407001",
                        "id": "407001",
                        "name": "default_haste_head",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [{"key": "haste", "value": 500}],
                    },
                    {
                        "slot": "head",
                        "simcSlot": "head",
                        "itemId": "407002",
                        "id": "407002",
                        "name": "blocked_weight_mastery_head",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [{"key": "mastery", "value": 350}],
                    },
                ],
            },
            stat_weights={
                "scenarioKey": "mplus_aoe_pack",
                "sourceStatus": "blocked",
                "weights": [
                    {"key": "mastery", "value": 2.0},
                    {"key": "haste", "value": 0.1},
                    {"key": "crit", "value": 0.8},
                    {"key": "versatility", "value": 0.2},
                ],
            },
            scenario_key="mplus_aoe",
        )

        self.assertEqual(selected[0]["itemId"], "407001")
        self.assertEqual(evidence["statWeights"]["sourceStatus"], "blocked")
        self.assertEqual(evidence["statWeights"]["ignoredReason"], "stat weight source is not accepted for recommendation")

    def test_low_yield_gray_zone_marks_simc_review_required(self):
        from server.season_recommended_gear import select_season_recommended_gear

        selected, evidence = select_season_recommended_gear(
            "shaman",
            "elemental",
            {
                "neck": [
                    {
                        "slot": "neck",
                        "simcSlot": "neck",
                        "itemId": "410001",
                        "id": "410001",
                        "name": "slightly_better_vers_neck",
                        "ilevel": 720,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "versatility", "value": 100},
                            {"key": "haste", "value": 750},
                        ],
                    },
                    {
                        "slot": "neck",
                        "simcSlot": "neck",
                        "itemId": "410002",
                        "id": "410002",
                        "name": "clean_haste_mastery_neck",
                        "ilevel": 718,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "haste", "value": 650},
                            {"key": "mastery", "value": 100},
                        ],
                    },
                ],
            },
            scenario_key="mplus_aoe",
            gray_zone_pct=0.02,
        )

        self.assertEqual(selected[0]["itemId"], "410002")
        self.assertTrue(evidence["simcReview"]["triggered"])
        self.assertEqual(evidence["simcReview"]["status"], "required")
        self.assertIn("low_yield_stat_gray_zone", evidence["simcReview"]["reasons"])
        self.assertEqual(evidence["slotDecisions"]["neck"]["lowYieldGrayZoneFallback"]["blockedItemId"], "410001")
        self.assertEqual(evidence["slotDecisions"]["neck"]["lowYieldGrayZoneFallback"]["selectedItemId"], "410002")
        self.assertEqual(evidence["recommendationConfidence"], "provisional")

    def test_tier_five_piece_can_use_off_piece_for_low_yield_slot(self):
        from server.season_recommended_gear import select_season_recommended_gear

        def tier(slot, index, stats):
            return {
                "slot": slot,
                "simcSlot": slot,
                "itemId": f"42000{index}",
                "id": f"42000{index}",
                "name": f"tier_{slot}",
                "ilevel": 707,
                "bonus_id": "1808",
                "simcReady": True,
                "itemSetName": "Stormbringer Tier",
                "itemStats": stats,
            }

        selected, evidence = select_season_recommended_gear(
            "shaman",
            "elemental",
            {
                "head": [tier("head", 1, [{"key": "intellect", "value": 1000}, {"key": "haste", "value": 300}])],
                "shoulders": [tier("shoulders", 2, [{"key": "intellect", "value": 1000}, {"key": "mastery", "value": 300}])],
                "chest": [tier("chest", 3, [{"key": "intellect", "value": 1000}, {"key": "crit", "value": 300}])],
                "hands": [tier("hands", 4, [{"key": "intellect", "value": 1000}, {"key": "haste", "value": 300}])],
                "legs": [
                    tier("legs", 5, [{"key": "intellect", "value": 1000}, {"key": "versatility", "value": 600}]),
                    {
                        "slot": "legs",
                        "simcSlot": "legs",
                        "itemId": "429999",
                        "id": "429999",
                        "name": "haste_mastery_offpiece",
                        "ilevel": 707,
                        "bonus_id": "1808",
                        "simcReady": True,
                        "itemStats": [
                            {"key": "intellect", "value": 1000},
                            {"key": "haste", "value": 300},
                            {"key": "mastery", "value": 300},
                        ],
                    },
                ],
            },
            scenario_key="mplus_aoe",
        )

        by_slot = {item["slot"]: item for item in selected}
        self.assertEqual(by_slot["legs"]["itemId"], "429999")
        self.assertEqual(evidence["tierSetDecision"]["selectedTierCount"], 4)
        self.assertEqual(evidence["tierSetDecision"]["replacements"][0]["slot"], "legs")
        self.assertEqual(evidence["tierSetDecision"]["replacements"][0]["reason"], "replace_fifth_tier_low_yield_or_lower_score")

    def test_equivalent_slots_do_not_reuse_same_item_id(self):
        from server.season_recommended_gear import select_season_recommended_gear

        def item(slot, item_id, name, ilevel):
            return {
                "slot": slot,
                "simcSlot": slot,
                "itemId": item_id,
                "id": item_id,
                "name": name,
                "ilevel": ilevel,
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [
                    {"key": "intellect", "value": 1000},
                    {"key": "haste", "value": 300},
                ],
            }

        selected, evidence = select_season_recommended_gear(
            "shaman",
            "elemental",
            {
                "finger1": [
                    item("finger1", "430001", "best_ring", 715),
                    item("finger1", "430002", "second_ring", 714),
                ],
                "finger2": [
                    item("finger2", "430001", "best_ring", 715),
                    item("finger2", "430002", "second_ring", 714),
                ],
                "trinket1": [
                    item("trinket1", "440001", "best_trinket", 715),
                    item("trinket1", "440002", "second_trinket", 714),
                ],
                "trinket2": [
                    item("trinket2", "440001", "best_trinket", 715),
                    item("trinket2", "440002", "second_trinket", 714),
                ],
            },
            scenario_key="mplus_aoe",
        )

        by_slot = {row["slot"]: row for row in selected}
        self.assertEqual(by_slot["finger1"]["itemId"], "430001")
        self.assertEqual(by_slot["finger2"]["itemId"], "430002")
        self.assertEqual(by_slot["trinket1"]["itemId"], "440001")
        self.assertEqual(by_slot["trinket2"]["itemId"], "440002")
        self.assertEqual(evidence["slotDecisions"]["finger2"]["selectedItemId"], "430002")
        self.assertEqual(evidence["slotDecisions"]["trinket2"]["selectedItemId"], "440002")

    def test_two_hand_main_hand_removes_off_hand_selection(self):
        from server.season_recommended_gear import (
            build_season_recommended_gear_template,
            select_season_recommended_gear,
        )

        gear = {slot: [item] for slot, item in ((item["slot"], item) for item in self.gear_items())}
        gear["main_hand"] = [
            {
                "slot": "main_hand",
                "simcSlot": "main_hand",
                "itemId": "450001",
                "id": "450001",
                "name": "best_staff",
                "ilevel": 715,
                "bonus_id": "1808",
                "weaponType": "Staff",
                "simcReady": True,
                "itemStats": [
                    {"key": "intellect", "value": 1400},
                    {"key": "haste", "value": 300},
                ],
            }
        ]
        gear["off_hand"] = [
            {
                "slot": "off_hand",
                "simcSlot": "off_hand",
                "itemId": "450002",
                "id": "450002",
                "name": "held_offhand",
                "ilevel": 715,
                "bonus_id": "1808",
                "weaponType": "Held In Off-hand",
                "simcReady": True,
                "itemStats": [
                    {"key": "intellect", "value": 900},
                    {"key": "haste", "value": 200},
                ],
            }
        ]

        selected, evidence = select_season_recommended_gear(
            "mage",
            "fire",
            gear,
            scenario_key="mplus_aoe",
        )

        by_slot = {row["slot"]: row for row in selected}
        self.assertEqual(by_slot["main_hand"]["itemId"], "450001")
        self.assertNotIn("off_hand", by_slot)
        self.assertEqual(
            evidence["weaponRuleDecision"]["removedSlots"][0]["reason"],
            "two_hand_main_hand_occupies_off_hand",
        )
        template = build_season_recommended_gear_template(
            "mage",
            "fire",
            selected,
            evidence={"optimizerRunId": "season-rec-test", "role": "damage"},
        )
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["occupiedSlots"]["off_hand"]["reason"], "two_hand_main_hand")

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
