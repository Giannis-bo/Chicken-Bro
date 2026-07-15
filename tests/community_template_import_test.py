#!/usr/bin/env python3
"""Pure contract tests for the atomic community-template import projector."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch


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

    def test_selected_gear_rows_include_only_bounded_display_facts_from_bound_item_and_source(self):
        from server.community_template_import import build_community_template_import_source

        source = build_community_template_import_source(
            self.winner,
            self.variants,
            self.options,
            items=[{
                "itemId": "item-head",
                "name": "Observed Headpiece",
                "slot": "head",
                "itemLevel": 289,
                "payload": {"rawInternalValue": "must-not-leak"},
            }],
            sources=[{
                "itemId": "item-head",
                "sourceType": "raid",
                "sourceLabel": "测试首领 - 测试团本",
                "payload": {"rawSourceValue": "must-not-leak"},
            }],
        )

        row = source["selectedGearBySlot"]["head"]
        self.assertEqual(row["displayName"], "Observed Headpiece")
        self.assertEqual(row["ilevel"], 289)
        self.assertEqual(row["sourceType"], "raid")
        self.assertEqual(row["sources"], [{"label": "测试首领 - 测试团本", "sourceType": "raid"}])
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("must-not-leak", encoded)

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

    def verified_import_source(self):
        winner = copy.deepcopy(self.winner)
        winner["selectionIntent"]["slots"]["head"].update({
            "gemOptionIds": ["gem-a", "gem-a"],
            "embellishmentOptionId": "",
        })
        options = [option for option in self.options if option["optionKey"] in {"gem-a", "enchant-a"}]
        return self.build_source(winner=winner, options=options)

    def test_import_runtime_preserves_duplicate_gems_and_resolver_signature(self):
        from server import gear_runtime

        source = self.verified_import_source()
        authority = {
            "manifest": {
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": "gear-release:sha256:frost",
                "gearCatalogRevision": "gear-release:sha256:frost",
                "manifestRevision": "manifest-a",
                "pointerGeneration": 7,
                "formalActiveManifest": True,
            },
            "dependencyVector": {"simcRuntimeRevision": "simc-r1"},
        }

        class ImportStore:
            def __init__(self):
                self.calls = []
                self.cached = []

            def get_community_template_import_context(self, **kwargs):
                self.calls.append(copy.deepcopy(kwargs))
                return {
                    "cache": {"hit": False},
                    "source": copy.deepcopy(source),
                    "authorityContext": copy.deepcopy(authority),
                    "releaseReadMs": 1.25,
                    "cacheIdentity": "manifest-a:7:mage:frost:frost-observed-a",
                }

            def cache_community_template_import_verified(self, cache_identity, payload):
                self.cached.append((cache_identity, copy.deepcopy(payload)))

        store = ImportStore()
        resolver_calls = []
        snapshot = {
            "status": "verified",
            "resolvedGearSignature": "sha256:resolved-frost",
            "problems": [],
        }
        with patch.object(gear_runtime.gear_resolver, "resolve", side_effect=lambda intent, context: resolver_calls.append((intent, context)) or snapshot):
            status, envelope, timings = gear_runtime.import_community_template(
                {"classKey": "mage", "specKey": "frost", "templateId": "frost-observed-a"},
                store=store,
                simc_runtime_revision="simc-r1",
                request_id="import-duplicate-gems",
            )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["contractRevision"], "community-template-import-envelope-v1")
        self.assertEqual(envelope["status"], "verified")
        self.assertEqual(envelope["data"]["status"], "verified")
        self.assertEqual(resolver_calls[0][0]["slots"]["head"]["gemOptionIds"], ["gem-a", "gem-a"])
        self.assertEqual(envelope["data"]["resolvedSnapshot"]["resolvedGearSignature"], "sha256:resolved-frost")
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(len(store.cached), 1)
        self.assertEqual(set(timings), {"queueMs", "releaseReadMs", "reconcileMs", "resolveMs", "serializeMs", "cache"})
        self.assertEqual(timings["cache"], "miss")

    def test_expected_manifest_mismatch_returns_structured_blocked_problem(self):
        from server import gear_runtime
        from server.postgres_cache_store import CommunityTemplateImportError

        class MismatchStore:
            def get_community_template_import_context(self, **_kwargs):
                raise CommunityTemplateImportError(
                    "manifest_mismatch",
                    "The requested Manifest revision is no longer active.",
                    release_context={"manifestRevision": "manifest-b", "pointerGeneration": 8},
                )

        status, envelope, _timings = gear_runtime.import_community_template(
            {
                "classKey": "mage",
                "specKey": "frost",
                "templateId": "frost-observed-a",
                "expectedManifestRevision": "manifest-a",
            },
            store=MismatchStore(),
            simc_runtime_revision="simc-r1",
            request_id="import-stale-manifest",
        )

        self.assertEqual(status, 409)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["data"], {})
        self.assertEqual(envelope["problems"][0]["code"], "manifest_mismatch")
        self.assertNotIn("mode", json.dumps(envelope))

    def test_blocked_unavailable_and_malformed_imports_are_not_cached(self):
        from server import gear_runtime

        class BlockedStore:
            def __init__(self):
                self.cache_calls = 0

            def get_community_template_import_context(self, **_kwargs):
                return {
                    "cache": {"hit": False},
                    "source": {"status": "blocked", "problems": [{"code": "template_not_active", "title": "Not active", "retryable": False}]},
                    "authorityContext": {},
                    "releaseReadMs": 0.5,
                    "cacheIdentity": "never-cache",
                }

            def cache_community_template_import_verified(self, *_args):
                self.cache_calls += 1

        store = BlockedStore()
        status, envelope, _timings = gear_runtime.import_community_template(
            {"classKey": "mage", "specKey": "frost", "templateId": "blocked"},
            store=store,
            simc_runtime_revision="simc-r1",
            request_id="blocked-import",
        )
        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(store.cache_calls, 0)

        malformed_status, malformed, _timings = gear_runtime.import_community_template(
            {"classKey": "mage", "specKey": "frost", "templateId": "blocked", "mode": "slot"},
            store=store,
            simc_runtime_revision="simc-r1",
            request_id="malformed-import",
        )
        self.assertEqual(malformed_status, 400)
        self.assertEqual(malformed["problems"][0]["code"], "invalid_import_request")
        self.assertEqual(store.cache_calls, 0)


if __name__ == "__main__":
    unittest.main()
