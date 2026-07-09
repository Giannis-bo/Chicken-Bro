#!/usr/bin/env python3
import unittest


class PgGearReadModelSelectorsTest(unittest.TestCase):
    def test_build_gear_mod_options_by_slot_read_model_groups_option_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_mod_options_by_slot_read_model
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        rows = [
            (
                301,
                "socket",
                "quick-ruby",
                "Quick Ruby",
                '["head", "neck"]',
                '{"gem_id": 213743, "ignored": "drop"}',
                "verified",
                '{"displayLabel": "Quick Ruby", "displayKind": "gem", "evidenceSource": "test", "iconUrl": "https://example.test/gem.png", "uniqueLimit": 1}',
                "2026-07-09T11:20:00Z",
            ),
            (
                302,
                "enchant",
                "any-slot-enchant",
                "Any Slot Enchant",
                '"*"',
                '{"enchant_id": "7418"}',
                "partial",
                '{"displayLabel": "Any Slot Enchant", "metadataStatus": "verified"}',
                None,
            ),
        ]

        read_model = build_gear_mod_options_by_slot_read_model(rows)

        self.assertEqual(sorted(read_model.keys()), sorted(CANONICAL_GEAR_SLOTS))
        socket_option = read_model["head"][0]
        self.assertEqual(socket_option["id"], "301")
        self.assertEqual(socket_option["type"], "socket")
        self.assertEqual(socket_option["optionType"], "socket")
        self.assertEqual(socket_option["rawName"], "Quick Ruby")
        self.assertEqual(socket_option["status"], "verified")
        self.assertEqual(socket_option["simcOptions"], {"gem_id": "213743"})
        self.assertEqual(socket_option["payload"]["displayLabel"], "Quick Ruby")
        self.assertEqual(socket_option["displayLabel"], "Quick Ruby")
        self.assertEqual(socket_option["displayKind"], "gem")
        self.assertEqual(socket_option["evidenceSource"], "test")
        self.assertEqual(socket_option["iconUrl"], "https://example.test/gem.png")
        self.assertEqual(socket_option["uniqueLimit"], 1)
        self.assertEqual(socket_option["updatedAt"], "2026-07-09T11:20:00Z")
        self.assertEqual(read_model["neck"][0]["id"], "301")

        enchant_option = next(option for option in read_model["head"] if option["id"] == "302")
        self.assertEqual(enchant_option["type"], "enchant")
        self.assertEqual(enchant_option["status"], "partial")
        self.assertEqual(enchant_option["simcOptions"], {"enchant_id": "7418"})
        self.assertEqual(enchant_option["metadataStatus"], "verified")
        self.assertEqual(enchant_option["updatedAt"], "")
        self.assertTrue(all(any(option["id"] == "302" for option in read_model[slot]) for slot in CANONICAL_GEAR_SLOTS))

    def test_build_gear_variants_by_item_read_model_groups_variant_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_variants_by_item_read_model
        from server.websim_payload import localized_difficulty_label

        rows = [
            (
                201,
                19019,
                "head",
                "mythic-710",
                "Mythic 710",
                "raid",
                "mythic",
                "710",
                '{"bonus_id": "123", "gem_id": 213743}',
                "verified",
                '["missing_stats", ""]',
                '{"simcIlevelOnly": true, "statSummary": "kept"}',
                "2026-07-09T11:10:00Z",
            ),
            (
                202,
                19019,
                "finger1",
                "heroic-bad-ilvl",
                "Heroic Bad",
                "dungeon",
                "heroic",
                "not-a-number",
                "{bad json",
                "",
                '"blocked_by_source"',
                '["not", "a", "dict"]',
                None,
            ),
        ]

        read_model = build_gear_variants_by_item_read_model(rows)

        self.assertEqual(list(read_model.keys()), ["19019"])
        self.assertEqual(len(read_model["19019"]), 2)
        first_variant = read_model["19019"][0]
        self.assertEqual(first_variant["id"], "201")
        self.assertEqual(first_variant["itemId"], "19019")
        self.assertEqual(first_variant["slot"], "head")
        self.assertEqual(first_variant["key"], "mythic-710")
        self.assertEqual(first_variant["variantKey"], "mythic-710")
        self.assertEqual(first_variant["label"], "Mythic 710")
        self.assertEqual(first_variant["difficultyLabel"], localized_difficulty_label("mythic", "Mythic 710", "raid"))
        self.assertEqual(first_variant["sourceType"], "raid")
        self.assertEqual(first_variant["difficultyKey"], "mythic")
        self.assertEqual(first_variant["itemLevel"], 710)
        self.assertEqual(first_variant["ilevel"], 710)
        self.assertEqual(first_variant["simcOptions"], {"bonus_id": "123", "gem_id": 213743})
        self.assertEqual(first_variant["status"], "verified")
        self.assertEqual(first_variant["blockers"], ["missing_stats"])
        self.assertEqual(first_variant["payload"], {"simcIlevelOnly": True, "statSummary": "kept"})
        self.assertTrue(first_variant["simcIlevelOnly"])
        self.assertEqual(first_variant["updatedAt"], "2026-07-09T11:10:00Z")

        fallback_variant = read_model["19019"][1]
        self.assertEqual(fallback_variant["slot"], "finger1")
        self.assertEqual(fallback_variant["itemLevel"], 0)
        self.assertEqual(fallback_variant["ilevel"], 0)
        self.assertEqual(fallback_variant["simcOptions"], {})
        self.assertEqual(fallback_variant["status"], "blocked")
        self.assertEqual(fallback_variant["blockers"], ["blocked_by_source"])
        self.assertEqual(fallback_variant["payload"], {})
        self.assertNotIn("simcIlevelOnly", fallback_variant)
        self.assertEqual(fallback_variant["updatedAt"], "")

    def test_build_gear_sources_by_item_read_model_groups_source_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_sources_by_item_read_model
        from server.websim_payload import localized_difficulty_label

        rows = [
            (
                101,
                19019,
                "dungeon",
                "the-stonevault",
                "The Stonevault",
                1278,
                2824,
                "mythic_plus",
                "season-1",
                '{"recommendationScore": 98, "observedProfiles": 40}',
                "2026-07-09T11:00:00Z",
            ),
            (
                102,
                19019,
                "raid",
                "liberation-of-undermine",
                "",
                None,
                None,
                "mythic",
                "season-1",
                "{bad json",
                None,
            ),
        ]

        read_model = build_gear_sources_by_item_read_model(rows)

        self.assertEqual(list(read_model.keys()), ["19019"])
        self.assertEqual(len(read_model["19019"]), 2)
        first_source = read_model["19019"][0]
        self.assertEqual(first_source["id"], "101")
        self.assertEqual(first_source["itemId"], "19019")
        self.assertEqual(first_source["sourceType"], "dungeon")
        self.assertEqual(first_source["sourceKey"], "the-stonevault")
        self.assertEqual(first_source["label"], "The Stonevault")
        self.assertEqual(first_source["sourceLabel"], "The Stonevault")
        self.assertEqual(first_source["instanceId"], 1278)
        self.assertEqual(first_source["encounterId"], 2824)
        self.assertEqual(first_source["difficultyKey"], "mythic_plus")
        self.assertEqual(
            first_source["difficultyLabel"],
            localized_difficulty_label("mythic_plus", "The Stonevault", "dungeon"),
        )
        self.assertEqual(first_source["seasonRevision"], "season-1")
        self.assertEqual(first_source["payload"], {"recommendationScore": 98, "observedProfiles": 40})
        self.assertEqual(first_source["recommendationScore"], 98)
        self.assertEqual(first_source["updatedAt"], "2026-07-09T11:00:00Z")

        fallback_source = read_model["19019"][1]
        self.assertEqual(fallback_source["label"], "liberation-of-undermine")
        self.assertEqual(fallback_source["sourceLabel"], "liberation-of-undermine")
        self.assertEqual(fallback_source["payload"], {})
        self.assertNotIn("recommendationScore", fallback_source)
        self.assertEqual(fallback_source["updatedAt"], "")

    def test_build_catalog_output_read_model_fragment_keeps_full_debug_fields_out_of_compact_payload(self):
        from server.pg_gear_read_model_selectors import build_catalog_output_read_model_fragment

        catalog_read_model = {
            "replacementCandidates": [{"slot": "head", "items": [{"itemId": "head-1"}]}],
            "catalogItems": [{"itemId": f"item-{idx}"} for idx in range(130)],
            "candidateLegalityAudit": {
                "excludedCandidateCount": 1,
                "excludedExamples": [{"itemId": "blocked-mail-head"}],
            },
        }

        compact_fragment = build_catalog_output_read_model_fragment(
            catalog_read_model,
            compact=True,
        )
        full_fragment = build_catalog_output_read_model_fragment(
            catalog_read_model,
            compact=False,
        )

        self.assertEqual(len(compact_fragment["catalogItems"]), 120)
        self.assertEqual(compact_fragment["catalogItems"][0]["itemId"], "item-0")
        self.assertEqual(compact_fragment["catalogItems"][-1]["itemId"], "item-119")
        self.assertNotIn("slotGroups", compact_fragment)
        self.assertNotIn("candidateLegalityAudit", compact_fragment)
        self.assertEqual(full_fragment["slotGroups"], catalog_read_model["replacementCandidates"])
        self.assertEqual(full_fragment["presets"], [])
        self.assertEqual(full_fragment["candidateItems"], [])
        self.assertEqual(full_fragment["candidateLegalityAudit"], catalog_read_model["candidateLegalityAudit"])
        self.assertEqual(len(full_fragment["catalogItems"]), 120)

    def test_build_common_gear_read_model_fragment_blocks_stat_snapshot(self):
        from server.pg_gear_read_model_selectors import build_common_gear_read_model_fragment

        readiness = {
            "status": "blocked",
            "selectedCount": 0,
            "itemLevel": {
                "key": "itemLevel",
                "label": "装备等级",
                "value": "0",
                "rawValue": 0,
                "selectedCount": 0,
                "source": "selected_gear",
            },
        }

        fragment = build_common_gear_read_model_fragment(
            "mage",
            "arcane",
            readiness,
            checked_at="2026-07-09T10:35:00Z",
        )

        self.assertEqual(fragment["weaponRule"]["mode"], "caster_1h_or_staff")
        self.assertEqual(len(fragment["slots"]), 16)
        self.assertEqual(fragment["slots"][0]["slot"], "head")
        self.assertIs(fragment["readiness"], readiness)
        self.assertEqual(fragment["maxLevel"], 90)
        self.assertEqual(fragment["checkedAt"], "2026-07-09T10:35:00Z")
        self.assertEqual(fragment["statSnapshot"]["statStatus"], "blocked")
        self.assertEqual(fragment["statSnapshot"]["classKey"], "mage")
        self.assertEqual(fragment["statSnapshot"]["specKey"], "arcane")
        self.assertEqual(
            fragment["statSnapshot"]["blockers"],
            ["Select complete SimC-ready gear and talents to calculate a verified stat snapshot."],
        )
        self.assertEqual(fragment["statSnapshot"]["gearReadiness"], readiness)

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
