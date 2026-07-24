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
            "profileHash": "profile-frost",
            "gearHash": "gear-frost",
            "payload": {
                "name": "Frost observed",
                "importEvidence": {
                    "schemaRevision": "community-template-import-evidence-v1",
                    "sourceFingerprint": "sha256:" + "a" * 64,
                    "slots": {
                        "head": {
                            "itemId": "item-head",
                            "variantKey": "myth-289",
                            "observedItemLevel": 292,
                            "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                        },
                    },
                },
            },
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
                        "gemOptionIds": ["gem-a", "gem-a"],
                        "enchantOptionId": "enchant-a",
                        "embellishmentOptionId": "",
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
                "itemLevel": 292,
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
        self.items = [{
            "itemId": "item-head",
            "name": "Observed Headpiece",
            "itemLevel": 197,
            "payload": {
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
            },
        }]

    def build_source(self, winner=None, variants=None, options=None, *, items=None, sources=None):
        from server.community_template_import import build_community_template_import_source

        return build_community_template_import_source(
            winner if winner is not None else self.winner,
            variants if variants is not None else self.variants,
            options if options is not None else self.options,
            items=self.items if items is None else items,
            sources=sources,
        )

    def test_observed_winner_projects_only_bound_variants_and_visible_options(self):
        from server.community_template_import import build_community_template_selection_intent

        source = self.build_source()

        self.assertEqual(source["status"], "verified")
        self.assertEqual(source["template"], {
            "id": "frost-observed-a",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "name": "Frost observed",
            "profileHash": "profile-frost",
            "gearHash": "gear-frost",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "attributeCharacterContext": {
                "schemaRevision": "gear-attribute-character-v1",
                "raceKey": "human",
                "origin": "default_human",
            },
        })

        self.assertEqual(source["importedGearBySlot"], {
            "head": {
                "variantId": "variant-head",
                "itemId": "item-head",
                "variantKey": "myth-289",
                "slot": "head",
                "label": "Observed head",
                "displayName": "Observed Headpiece",
                "name": "Observed Headpiece",
                "itemLevel": 292,
                "ilevel": 292,
                "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                "gameAsset": {
                    "source": "blizzard",
                    "status": "verified",
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                },
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

    def test_v2_evidence_projects_its_sealed_source_race(self):
        winner = copy.deepcopy(self.winner)
        winner["payload"]["importEvidence"].update({
            "schemaRevision": "community-template-import-evidence-v2",
            "sourceRaceKey": "night_elf",
            "sourceRaceOrigin": "source_profile",
        })

        source = self.build_source(winner=winner)

        self.assertEqual(source["template"]["attributeCharacterContext"], {
            "schemaRevision": "gear-attribute-character-v1",
            "raceKey": "night_elf",
            "origin": "source_profile",
        })

    def test_v3_evidence_projects_only_its_sealed_stable_effect_context(self):
        winner = copy.deepcopy(self.winner)
        stable_effect_context = {
            "schemaRevision": "gear-attribute-stable-effects-v1",
            "status": "verified",
            "origin": "source_profile",
            "effectIds": ["mage:inspired_intellect"],
            "loadoutSignature": "sha256:" + "c" * 64,
        }
        winner["payload"]["importEvidence"].update({
            "schemaRevision": "community-template-import-evidence-v3",
            "sourceRaceKey": "dwarf",
            "sourceRaceOrigin": "source_profile",
            "sourceStableEffects": stable_effect_context,
            "rawImportCode": "CAE_SOURCE_LOADOUT_MUST_NOT_LEAK",
        })

        source = self.build_source(winner=winner)

        self.assertEqual(
            source["template"].get("attributeStableEffectContext"),
            stable_effect_context,
        )
        self.assertNotIn("CAE_SOURCE_LOADOUT_MUST_NOT_LEAK", json.dumps(source, sort_keys=True))

    def test_verified_projection_uses_sealed_observed_level_and_icon_not_generic_item(self):
        from server.community_template_import import (
            COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION,
            community_template_import_public_data,
        )

        winner = copy.deepcopy(self.winner)
        winner.update({"profileHash": "profile-frost", "gearHash": "gear-frost"})
        winner["payload"]["importEvidence"] = {
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "myth-289",
                    "observedItemLevel": 292,
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                },
            },
        }
        winner["selectionIntent"]["slots"]["head"].update({
            "gemOptionIds": ["gem-a", "gem-a"],
            "embellishmentOptionId": "",
        })
        variants = copy.deepcopy(self.variants)
        variants[0]["itemLevel"] = 292
        items = [{
            "itemId": "item-head",
            "name": "Observed Headpiece",
            "itemLevel": 197,
            "payload": {
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
            },
        }]
        options = [option for option in self.options if option["optionKey"] in {"gem-a", "enchant-a"}]

        source = self.build_source(
            winner=winner,
            variants=variants,
            options=options,
            items=items,
        )

        self.assertEqual(source["contractRevision"], COMMUNITY_TEMPLATE_IMPORT_CONTRACT_REVISION)
        self.assertEqual(source["status"], "verified")
        self.assertEqual(source["importedGearBySlot"]["head"], {
            "variantId": "variant-head",
            "itemId": "item-head",
            "variantKey": "myth-289",
            "slot": "head",
            "label": "Observed head",
            "displayName": "Observed Headpiece",
            "name": "Observed Headpiece",
            "itemLevel": 292,
            "ilevel": 292,
            "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
            "gameAsset": {
                "source": "blizzard",
                "status": "verified",
                "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
            },
        })
        self.assertNotIn("197", json.dumps(source, ensure_ascii=False, sort_keys=True))
        public = community_template_import_public_data(
            source,
            {"status": "verified", "resolvedGearSignature": "sha256:resolved-frost"},
            {"manifestRevision": "manifest-a", "pointerGeneration": 7},
        )
        self.assertEqual(public["importedGearBySlot"]["head"]["itemLevel"], 292)
        self.assertNotIn("selectedGearBySlot", public)
        self.assertNotIn("unresolvedBySlot", public)

    def test_public_import_hydrates_missing_observed_display_from_exact_authority(self):
        from server.community_template_import import community_template_import_public_data

        source = {
            "contractRevision": "websim-community-template-import-v2",
            "status": "verified",
            "template": {"id": "active-observed-a"},
            "importedGearBySlot": {
                "finger1": {
                    "slot": "finger1",
                    "itemId": "ring-a",
                    "variantKey": "observed-ring-a",
                    "itemLevel": 289,
                },
                "trinket1": {
                    "slot": "trinket1",
                    "itemId": "trinket-a",
                    "variantKey": "observed-trinket-a",
                    "itemLevel": 298,
                },
            },
        }
        icon_root = "https://render.worldofwarcraft.com/us/icons/56/"
        authority = {
            "itemsById": {
                "ring-a": {
                    "displayName": "权威戒指",
                    "iconUrl": f"{icon_root}inv_jewelry_ring_01.jpg",
                    "gameAsset": {
                        "status": "verified",
                        "source": "blizzard",
                        "iconUrl": f"{icon_root}inv_jewelry_ring_01.jpg",
                    },
                },
                "trinket-a": {
                    "displayName": "权威饰品",
                    "iconUrl": f"{icon_root}inv_misc_orb_01.jpg",
                    "gameAsset": {
                        "status": "verified",
                        "source": "blizzard",
                        "iconUrl": f"{icon_root}inv_misc_orb_01.jpg",
                    },
                },
            }
        }
        snapshot = {
            "status": "verified",
            "resolvedSlots": {
                "finger1": {
                    "slot": "finger1",
                    "itemId": "ring-a",
                    "variantKey": "observed-ring-a",
                    "displayName": "权威戒指",
                },
                "trinket1": {
                    "slot": "trinket1",
                    "itemId": "trinket-a",
                    "variantKey": "observed-trinket-a",
                    "displayName": "权威饰品",
                },
            },
        }

        public = community_template_import_public_data(
            source,
            snapshot,
            {"manifestRevision": "manifest-a", "pointerGeneration": 7},
            authority_context=authority,
        )

        self.assertEqual(public["importedGearBySlot"]["finger1"], {
            "slot": "finger1",
            "itemId": "ring-a",
            "variantKey": "observed-ring-a",
            "itemLevel": 289,
            "name": "权威戒指",
            "displayName": "权威戒指",
            "iconUrl": f"{icon_root}inv_jewelry_ring_01.jpg",
            "gameAsset": {
                "status": "verified",
                "source": "blizzard",
                "iconUrl": f"{icon_root}inv_jewelry_ring_01.jpg",
            },
        })
        self.assertEqual(
            public["importedGearBySlot"]["trinket1"]["name"],
            "权威饰品",
        )

    def test_public_import_blocks_an_incomplete_observed_display_projection(self):
        from server.community_template_import import community_template_import_public_data

        public = community_template_import_public_data(
            {
                "contractRevision": "websim-community-template-import-v2",
                "status": "verified",
                "template": {"id": "active-observed-a"},
                "importedGearBySlot": {
                    "finger1": {
                        "slot": "finger1",
                        "itemId": "ring-a",
                        "variantKey": "observed-ring-a",
                    }
                },
            },
            {
                "status": "verified",
                "resolvedSlots": {
                    "finger1": {
                        "slot": "finger1",
                        "itemId": "ring-a",
                        "variantKey": "observed-ring-a",
                        "displayName": "权威戒指",
                    }
                },
            },
            {"manifestRevision": "manifest-a", "pointerGeneration": 7},
            authority_context={"itemsById": {"ring-a": {"displayName": "权威戒指"}}},
        )

        self.assertIsNone(public)

    def test_verified_projection_uses_sealed_observed_icon_when_catalog_image_is_missing(self):
        items = [{
            "itemId": "item-head",
            "name": "Observed Headpiece",
            "itemLevel": 197,
            "payload": {},
        }]

        source = self.build_source(items=items)

        self.assertEqual(source["status"], "verified")
        self.assertEqual(
            source["importedGearBySlot"]["head"]["iconUrl"],
            "https://render.worldofwarcraft.com/icons/observed-head.jpg",
        )
        self.assertEqual(
            source["importedGearBySlot"]["head"]["gameAsset"],
            {
                "source": "sealed_observed_profile",
                "status": "verified",
                "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
            },
        )

    def test_projection_blocks_if_any_sealed_fact_or_enhancement_is_incomplete(self):
        winner = copy.deepcopy(self.winner)
        winner["payload"]["importEvidence"] = {
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {
                "head": {
                    "itemId": "item-head",
                    "variantKey": "myth-289",
                    "observedItemLevel": 289,
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                },
            },
        }
        winner["selectionIntent"]["slots"]["head"].update({
            "gemOptionIds": ["gem-a"],
            "embellishmentOptionId": "",
        })
        items = [{
            "itemId": "item-head",
            "name": "Observed Headpiece",
            "itemLevel": 197,
            "payload": {
                "_metadata": {
                    "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                    "gameAsset": {"source": "blizzard", "status": "verified"},
                },
            },
        }]
        options = [option for option in self.options if option["optionKey"] in {"gem-a", "enchant-a"}]
        mutations = {
            "missing_evidence": lambda value, variants, items, options: value["payload"].pop("importEvidence"),
            "variant_level_mismatch": lambda value, variants, items, options: variants[0].__setitem__("itemLevel", 292),
            "item_icon_mismatch": lambda value, variants, items, options: items[0]["payload"]["_metadata"].__setitem__("iconUrl", "https://render.worldofwarcraft.com/icons/other.jpg"),
            "unmapped_gem": lambda value, variants, items, options: value["selectionIntent"]["slots"]["head"].__setitem__("gemOptionIds", ["missing-gem"]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                case_winner = copy.deepcopy(winner)
                case_variants = copy.deepcopy(self.variants)
                case_items = copy.deepcopy(items)
                case_options = copy.deepcopy(options)
                mutate(case_winner, case_variants, case_items, case_options)
                source = self.build_source(
                    winner=case_winner,
                    variants=case_variants,
                    options=case_options,
                    items=case_items,
                )
                self.assertEqual(source["status"], "blocked")
                self.assertEqual(source["importedGearBySlot"], {})

    def test_source_display_rows_do_not_replace_winner_template_identity(self):
        source = self.build_source(sources=[{
            "itemId": "item-head",
            "sourceLabel": "Observed raid",
            "sourceType": "raid",
        }])

        self.assertEqual(source["template"]["id"], "frost-observed-a")
        self.assertEqual(source["template"]["name"], "Frost observed")

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

    def test_socket_typed_release_option_reconciles_as_a_canonical_gem(self):
        from server.community_template_import import build_community_template_selection_intent

        options = copy.deepcopy(self.options)
        options[0]["optionType"] = "socket"

        source = self.build_source(options=options)

        self.assertEqual(
            build_community_template_selection_intent(source)["slots"]["head"]["gemOptionIds"],
            ["gem-a", "gem-a"],
        )
        self.assertEqual(source["visibleOptionsBySlot"]["head"]["gem-a"]["optionType"], "gem")

    def test_normalized_variant_alias_is_blocked_without_exact_sealed_variant(self):
        from server.community_template_import import build_community_template_selection_intent

        variants = copy.deepcopy(self.variants)
        variants[0]["variantKey"] = "myth-289!"
        variants[0]["requestedVariantKey"] = "myth-289"

        source = self.build_source(variants=variants)

        self.assertEqual(source["status"], "blocked")
        self.assertIsNone(build_community_template_selection_intent(source))

    def test_unknown_raw_enhancement_values_block_without_output_values(self):
        from server.community_template_import import community_template_import_public_data

        winner = copy.deepcopy(self.winner)
        winner["selectionIntent"]["slots"]["head"].update({
            "gemOptionIds": ["gem-a", "forged-raw-gem"],
            "embellishmentOptionId": "hidden-embellishment",
        })
        source = self.build_source(winner=winner)
        public = community_template_import_public_data(
            source,
            {"status": "verified", "slots": {}},
            {"manifestRevision": "manifest-a", "pointerGeneration": 7},
        )
        encoded = json.dumps(public, ensure_ascii=False, sort_keys=True)

        self.assertEqual(source["status"], "blocked")
        self.assertEqual(public["status"], "blocked")
        self.assertEqual(public["importedGearBySlot"], {})
        self.assertNotIn("forged-raw-gem", encoded)
        self.assertNotIn("raw-value-must-not-leak", encoded)
        self.assertNotIn("hidden-embellishment", encoded)

    def test_forged_template_option_identity_is_not_copied_to_selection_intent(self):
        from server.community_template_import import build_community_template_selection_intent

        winner = copy.deepcopy(self.winner)
        winner["selectionIntent"]["slots"]["head"]["gemOptionIds"] = ["forged-raw-gem"]
        source = self.build_source(winner=winner)
        intent = build_community_template_selection_intent(source)
        encoded = json.dumps([intent, source], ensure_ascii=False, sort_keys=True)

        self.assertIsNone(intent)
        self.assertNotIn("forged-raw-gem", encoded)
        self.assertNotIn("hidden-embellishment", encoded)

    def test_slot_inapplicable_or_hidden_option_blocks_atomic_import(self):
        winner = copy.deepcopy(self.winner)
        winner["selectionIntent"]["slots"]["head"]["embellishmentOptionId"] = "hidden-embellishment"
        source = self.build_source(winner=winner)

        self.assertEqual(source["status"], "blocked")
        self.assertEqual(source["importedGearBySlot"], {})

    def test_imported_gear_rows_include_only_sealed_bounded_display_facts(self):
        from server.community_template_import import build_community_template_import_source

        source = build_community_template_import_source(
            self.winner,
            self.variants,
            self.options,
            items=[{
                "itemId": "item-head",
                "name": "Observed Headpiece",
                "slot": "head",
                "itemLevel": 197,
                "payload": {
                    "rawInternalValue": "must-not-leak",
                    "_metadata": {
                        "iconUrl": "https://render.worldofwarcraft.com/icons/observed-head.jpg",
                        "gameAsset": {"source": "blizzard", "status": "verified"},
                    },
                },
            }],
            sources=[{
                "itemId": "item-head",
                "sourceType": "raid",
                "sourceLabel": "测试首领 - 测试团本",
                "payload": {"rawSourceValue": "must-not-leak"},
            }],
        )

        row = source["importedGearBySlot"]["head"]
        self.assertEqual(row["displayName"], "Observed Headpiece")
        self.assertEqual(row["ilevel"], 292)
        self.assertEqual(row["itemLevel"], 292)
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

    def test_partial_or_legacy_import_source_is_returned_as_blocked_without_data(self):
        from server import gear_runtime

        class LegacyStore:
            def __init__(self, source):
                self.source = source
                self.cache_calls = 0

            def get_community_template_import_context(self, **_kwargs):
                return {
                    "cache": {"hit": False},
                    "source": copy.deepcopy(self.source),
                    "authorityContext": {},
                    "releaseReadMs": 0.5,
                    "cacheIdentity": "never-cache",
                }

            def cache_community_template_import_verified(self, *_args):
                self.cache_calls += 1

        sources = (
            {
                "contractRevision": "websim-community-template-import-v1",
                "status": "verified",
                "selectedGearBySlot": {"head": {"itemLevel": 197}},
            },
            {
                "contractRevision": "websim-community-template-import-v2",
                "status": "partial",
                "importedGearBySlot": {"head": {"itemLevel": 292}},
            },
        )
        for source in sources:
            with self.subTest(source=source["contractRevision"], status=source["status"]):
                store = LegacyStore(source)
                status, envelope, _timings = gear_runtime.import_community_template(
                    {"classKey": "mage", "specKey": "frost", "templateId": "legacy"},
                    store=store,
                    simc_runtime_revision="simc-r1",
                    request_id="legacy-import",
                )
                self.assertEqual(status, 200)
                self.assertEqual(envelope["status"], "blocked")
                self.assertEqual(envelope["data"], {})
                self.assertEqual(store.cache_calls, 0)


if __name__ == "__main__":
    unittest.main()
