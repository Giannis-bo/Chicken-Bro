#!/usr/bin/env python3
"""Pure contract tests for the atomic community-template import projector."""

from __future__ import annotations

import copy
import json
import unittest


class CommunityTemplateImportTest(unittest.TestCase):
    def setUp(self):
        self.winner = {
            "templateId": "frost-observed-a",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "payload": {"name": "Frost observed"},
            "selectionIntent": {
                "schemaRevision": "selection-intent-v1",
                "authoredAgainst": {
                    "seasonRevision": "season-17",
                    "gearCatalogRevision": "gear-release:sha256:frost",
                },
                "eligibilityContext": {"classKey": "mage", "specKey": "frost", "level": 90},
                "slots": {
                    "head": {
                        "itemId": "item-head",
                        "variantKey": "myth-289",
                        "gemOptionIds": ["gem-a", "gem-a", "forged-raw-gem"],
                        "enchantOptionId": "enchant-a",
                        "embellishmentOptionId": "hidden-embellishment",
                        "craftedOptionId": "",
                        "catalystOptionId": "",
                    }
                },
            },
        }
        self.variants = [
            {
                "id": "variant-head",
                "itemId": "item-head",
                "variantKey": "myth-289",
                "slot": "head",
                "label": "Observed head",
                "itemLevel": 289,
                "status": "verified",
            },
            {
                "id": "unselected-variant",
                "itemId": "item-other",
                "variantKey": "hero-276",
                "slot": "chest",
                "label": "Must not project",
                "itemLevel": 276,
                "status": "verified",
            },
        ]
        self.options = [
            {
                "optionKey": "gem-a",
                "optionType": "gem",
                "name": "Gem A",
                "status": "verified",
                "isVisible": True,
                "applicableSlots": ["head"],
                "simcOptions": {"gem_id": "raw-value-must-not-leak"},
            },
            {
                "optionKey": "enchant-a",
                "optionType": "enchant",
                "name": "Enchant A",
                "status": "verified",
                "isVisible": True,
                "applicableSlots": ["head"],
            },
            {
                "optionKey": "hidden-embellishment",
                "optionType": "embellishment",
                "name": "Hidden embellishment",
                "status": "verified",
                "isVisible": False,
                "applicableSlots": ["head"],
            },
            {
                "optionKey": "unselected-visible-option",
                "optionType": "gem",
                "name": "Must not project",
                "status": "verified",
                "isVisible": True,
                "applicableSlots": ["head"],
            },
        ]

    def build_source(self, winner=None, variants=None, options=None):
        from server.community_template_import import build_community_template_import_source

        return build_community_template_import_source(
            winner if winner is not None else self.winner,
            variants if variants is not None else self.variants,
            options if options is not None else self.options,
        )

    def test_observed_winner_projects_only_bound_variants_and_visible_options(self):
        from server.community_template_import import build_community_template_selection_intent

        source = self.build_source()

        self.assertEqual(source["status"], "partial")
        self.assertEqual(source["template"], {
            "id": "frost-observed-a",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "name": "Frost observed",
        })
        self.assertEqual(source["selectedGearBySlot"], {
            "head": {
                "variantId": "variant-head",
                "itemId": "item-head",
                "variantKey": "myth-289",
                "slot": "head",
                "label": "Observed head",
                "itemLevel": 289,
            }
        })
        self.assertEqual(source["visibleOptionsBySlot"], {
            "head": {
                "gem-a": {"optionKey": "gem-a", "optionType": "gem", "name": "Gem A"},
                "enchant-a": {"optionKey": "enchant-a", "optionType": "enchant", "name": "Enchant A"},
            }
        })
        self.assertEqual(
            build_community_template_selection_intent(source)["slots"]["head"],
            {
                "itemId": "item-head",
                "variantKey": "myth-289",
                "gemOptionIds": ["gem-a", "gem-a"],
                "enchantOptionId": "enchant-a",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
        )

    def test_non_observed_or_non_winner_source_is_blocked_before_intent_creation(self):
        from server.community_template_import import build_community_template_selection_intent

        for change in ({"role": "standby"}, {"sourceKey": "season_recommendation"}):
            with self.subTest(change=change):
                winner = {**self.winner, **change}
                source = self.build_source(winner=winner)
                self.assertEqual(source["status"], "blocked")
                self.assertEqual(source["problems"][0]["code"], "template_not_active")
                self.assertIsNone(build_community_template_selection_intent(source))

    def test_duplicate_gem_option_ids_preserve_source_order(self):
        from server.community_template_import import build_community_template_selection_intent

        source = self.build_source()

        self.assertEqual(
            build_community_template_selection_intent(source)["slots"]["head"]["gemOptionIds"],
            ["gem-a", "gem-a"],
        )

    def test_unknown_raw_enhancement_values_become_counts_not_output_values(self):
        from server.community_template_import import community_template_import_public_data

        source = self.build_source()
        public = community_template_import_public_data(
            source,
            {"status": "verified", "slots": {}},
            {"manifestRevision": "manifest-a", "pointerGeneration": 7},
        )
        encoded = json.dumps(public, ensure_ascii=False, sort_keys=True)

        self.assertEqual(source["unresolvedBySlot"]["head"], {
            "gemCount": 1,
            "embellishmentCount": 1,
        })
        self.assertNotIn("forged-raw-gem", encoded)
        self.assertNotIn("raw-value-must-not-leak", encoded)
        self.assertNotIn("hidden-embellishment", encoded)

    def test_forged_template_option_identity_is_not_copied_to_selection_intent(self):
        from server.community_template_import import build_community_template_selection_intent

        source = self.build_source()
        intent = build_community_template_selection_intent(source)
        encoded = json.dumps(intent, ensure_ascii=False, sort_keys=True)

        self.assertNotIn("forged-raw-gem", encoded)
        self.assertNotIn("hidden-embellishment", encoded)

    def test_slot_inapplicable_or_hidden_option_is_reported_as_unresolved(self):
        source = self.build_source()

        self.assertEqual(source["status"], "partial")
        self.assertEqual(source["unresolvedBySlot"]["head"]["gemCount"], 1)
        self.assertEqual(source["unresolvedBySlot"]["head"]["embellishmentCount"], 1)

    def test_projector_has_no_database_or_http_side_effects(self):
        winner = copy.deepcopy(self.winner)
        variants = copy.deepcopy(self.variants)
        options = copy.deepcopy(self.options)
        before = json.dumps([winner, variants, options], ensure_ascii=False, sort_keys=True)

        self.build_source(winner=winner, variants=variants, options=options)

        self.assertEqual(
            json.dumps([winner, variants, options], ensure_ascii=False, sort_keys=True),
            before,
        )


if __name__ == "__main__":
    unittest.main()
