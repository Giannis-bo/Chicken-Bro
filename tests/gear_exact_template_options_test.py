import copy
import unittest
from unittest.mock import patch

from server import gear_exact_template_options
from server.gear_exact_template_options import (
    bind_exact_template_authority,
    has_exact_template_option,
    project_exact_template_intent,
)
from tests.gear_resolved_loadout_test import (
    CATALOG_REVISION,
    ENCHANT_SELECTION,
    HEAD_KEY,
    MAIN_KEY,
    TEMPLATE_AUTHORITY_IDENTITY,
    exact_registry,
)


HEAD_BROWSE = "browse-variant:sha256:" + ("1" * 64)
MAIN_BROWSE = "browse-variant:sha256:" + ("2" * 64)


def catalog():
    return {
        "schemaRevision": "gear-catalog-revision-v2",
        "status": "verified",
        "catalogRevision": CATALOG_REVISION,
        "browseVariants": [
            {
                "browseVariantKey": HEAD_BROWSE,
                "itemId": "1001",
                "sourceVariantKeys": ["variant-head"],
                "canonicalSourceVariantKey": "variant-head",
                "evidenceStatus": "verified",
            },
            {
                "browseVariantKey": MAIN_BROWSE,
                "itemId": "1002",
                "sourceVariantKeys": ["variant-main_hand"],
                "canonicalSourceVariantKey": "variant-main_hand",
                "evidenceStatus": "verified",
            },
        ],
    }


def intent():
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": "season-17",
            "gearCatalogRevision": CATALOG_REVISION,
        },
        "eligibilityContext": {
            "classKey": "mage",
            "specKey": "arcane",
            "level": 90,
        },
        "slots": {
            "head": {
                "itemId": "1001",
                "variantKey": HEAD_BROWSE,
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
            "main_hand": {
                "itemId": "1002",
                "variantKey": MAIN_BROWSE,
                "gemOptionIds": [],
                # Community Release already decided this observed value is
                # editor-managed. Exact projection may replace that public
                # option identity, but may not invent occupancy from raw
                # source-only Exact facts.
                "enchantOptionId": "catalog-enchant-placeholder",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
        },
    }


def authority_context(projected_intent):
    option_ids = [
        value
        for selection in projected_intent["slots"].values()
        for value in (
            *selection["gemOptionIds"],
            selection["enchantOptionId"],
            selection["embellishmentOptionId"],
            selection["craftedOptionId"],
            selection["catalystOptionId"],
        )
        if value
    ]
    return {
        "contractRevision": "gear-authority-context-v1",
        "manifest": {
            "seasonRevision": "season-17",
            "gearCatalogReleaseId": "gear-release:sha256:" + ("4" * 64),
            "gearCatalogRevision": CATALOG_REVISION,
            "communityTemplateReleaseId": "community-release:sha256:" + ("5" * 64),
            "gearExactRegistryRevision": exact_registry()["registryRevision"],
        },
        "dependencyVector": {
            "seasonRevision": "season-17",
            "gearCatalogReleaseId": "gear-release:sha256:" + ("4" * 64),
            "gearCatalogRevision": CATALOG_REVISION,
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-runtime-v1",
            "statPolicyRevision": "gear-stat-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": "gear-socket-authority-v2",
        },
        "itemsById": {
            "1001": {
                "itemId": "1001",
                "baseCapabilities": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
            },
            "1002": {
                "itemId": "1002",
                "baseCapabilities": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
            },
        },
        "variantsByKey": {
            HEAD_BROWSE: {
                "variantKey": HEAD_BROWSE,
                "capabilityOverrides": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
            },
            MAIN_BROWSE: {
                "variantKey": MAIN_BROWSE,
                "capabilityOverrides": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
            },
        },
        "optionsById": {},
        "ruleParameters": {},
        "capabilities": {},
        "evidenceRecordsById": {},
        "missingFields": [f"optionsById.{option_id}" for option_id in option_ids],
    }


class GearExactTemplateOptionsTest(unittest.TestCase):
    def test_project_replaces_public_enhancements_with_registry_signed_options(self):
        first = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        second = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "verified")
        projected = first["selectionIntent"]
        option_id = projected["slots"]["main_hand"]["enchantOptionId"]
        self.assertRegex(option_id, r"^exact-option:sha256:[0-9a-f]{64}$")
        self.assertTrue(has_exact_template_option(projected))
        self.assertEqual(
            first["optionsById"][option_id]["simcOptions"],
            {"enchant_id": "7443"},
        )
        self.assertEqual(
            first["optionsById"][option_id]["attributeStaticFactsStatus"],
            "not_applicable",
        )
        self.assertNotIn("7443", str(projected))
        self.assertEqual(
            projected["slots"]["head"]["enchantOptionId"],
            "",
        )

    def test_project_does_not_promote_source_only_exact_enhancements_into_editor_state(self):
        source_only = intent()
        source_only["slots"]["main_hand"]["enchantOptionId"] = ""
        registry = exact_registry()
        for reference in registry["templateReferences"]:
            reference["editorManagedEnhancementFields"] = []

        result = project_exact_template_intent(
            source_only,
            registry,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["selectionIntent"]["slots"]["main_hand"]["enchantOptionId"],
            "",
        )
        self.assertEqual(result["optionsById"], {})
        self.assertEqual(result["evidenceRecordsById"], {})
        self.assertEqual(result["visibleOptionsBySlot"], {})
        self.assertFalse(has_exact_template_option(result["selectionIntent"]))

    def test_projection_blocks_partial_or_one_identity_to_many_content_groups(self):
        partial = exact_registry()
        partial["templateReferences"][0]["validationStatus"] = "partial"
        partial["templateReferences"][0]["exactItemInstanceKey"] = ""
        partial["templateReferences"][0]["problemCodes"] = [
            "ENHANCEMENT_SINGLE_VALUE_MALFORMED"
        ]
        ambiguous = exact_registry()
        duplicate = copy.deepcopy(ambiguous["templateReferences"])
        for row in duplicate:
            row["templateContentHash"] = "sha256:" + ("0" * 64)
        ambiguous["templateReferences"].extend(duplicate)

        partial_result = project_exact_template_intent(
            intent(),
            partial,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        ambiguous_result = project_exact_template_intent(
            intent(),
            ambiguous,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(partial_result["status"], "blocked")
        self.assertIn(
            "EXACT_TEMPLATE_REFERENCE_NOT_VERIFIED",
            partial_result["problemCodes"],
        )
        self.assertEqual(ambiguous_result["status"], "blocked")
        self.assertIn(
            "EXACT_TEMPLATE_AUTHORITY_AMBIGUOUS",
            ambiguous_result["problemCodes"],
        )

    def test_community_template_readiness_hides_partial_exact_evidence_before_import(self):
        verified = gear_exact_template_options.community_template_exact_import_readiness(
            exact_registry(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        partial_registry = exact_registry()
        partial_registry["templateReferences"][0]["validationStatus"] = "partial"
        partial_registry["templateReferences"][0]["exactItemInstanceKey"] = ""
        partial_registry["templateReferences"][0]["problemCodes"] = [
            "ENHANCEMENT_SINGLE_VALUE_MALFORMED"
        ]
        partial = gear_exact_template_options.community_template_exact_import_readiness(
            partial_registry,
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["problemCodes"], [])
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(
            partial["problemCodes"],
            ["EXACT_TEMPLATE_REFERENCE_NOT_VERIFIED"],
        )

    def test_project_keeps_a_verified_exact_source_variant_outside_public_browse(self):
        """Exact import may use verified source evidence without publishing a BrowseVariant."""
        exact = exact_registry()
        import_intent = intent()
        import_intent["slots"]["head"]["variantKey"] = "variant-head"
        browse_catalog = catalog()
        browse_catalog["browseVariants"] = [
            row
            for row in browse_catalog["browseVariants"]
            if row["itemId"] != "1001"
        ]

        result = project_exact_template_intent(
            import_intent,
            exact,
            browse_catalog,
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["selectionIntent"]["slots"]["head"]["variantKey"],
            "variant-head",
        )
        self.assertEqual(
            browse_catalog["browseVariants"],
            [catalog()["browseVariants"][1]],
        )

    def test_exact_only_import_resolves_and_compiles_without_becoming_browse_visible(self):
        from server import gear_resolver
        from server.gear_resolved_loadout import (
            build_resolved_loadout_from_registry,
        )
        from server.simulation_snapshot import (
            build_simulation_snapshot,
            talent_profile_key,
        )

        exact = exact_registry()
        import_intent = intent()
        import_intent["slots"]["head"]["variantKey"] = "variant-head"
        browse_catalog = catalog()
        browse_catalog["browseVariants"] = [
            row
            for row in browse_catalog["browseVariants"]
            if row["itemId"] != "1001"
        ]
        projection = project_exact_template_intent(
            import_intent,
            exact,
            browse_catalog,
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        projected = projection["selectionIntent"]
        context = authority_context(projected)
        context["itemsById"] = {
            "1001": {
                "itemId": "1001",
                "displayName": "Exact Head",
                "allowedSlots": ["head"],
                "inventoryType": "head",
                "allowedClassKeys": ["mage"],
                "allowedSpecKeys": ["arcane"],
                "armorType": "cloth",
                "weaponType": "",
                "handedness": "",
                "uniqueGroupId": "",
                "uniqueLimit": 0,
                "itemSetId": "",
                "baseStats": {"intellect": 400, "stamina": 700},
                "baseCapabilities": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
                "sourceRefIds": [],
            },
            "1002": {
                "itemId": "1002",
                "displayName": "Exact Staff",
                "allowedSlots": ["main_hand"],
                "inventoryType": "weapon",
                "allowedClassKeys": ["mage"],
                "allowedSpecKeys": ["arcane"],
                "armorType": "",
                "weaponType": "staff",
                "handedness": "two_hand",
                "uniqueGroupId": "",
                "uniqueLimit": 0,
                "itemSetId": "",
                "baseStats": {"intellect": 600, "haste": 250},
                "baseCapabilities": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
                "sourceRefIds": [],
            },
        }
        context["variantsByKey"] = {
            "variant-head": {
                "variantKey": "variant-head",
                "itemId": "1001",
                "status": "verified",
                "itemLevel": 266,
                "resolvedStats": {"intellect": 400, "stamina": 700},
                "statDeltas": {},
                "simcOptions": {
                    "ilevel": "266",
                    "bonus_id": "9001/9002",
                },
                "capabilityOverrides": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
                "sourceRefIds": [],
            },
            MAIN_BROWSE: {
                "variantKey": MAIN_BROWSE,
                "itemId": "1002",
                "status": "verified",
                "itemLevel": 272,
                "resolvedStats": {"intellect": 600, "haste": 250},
                "statDeltas": {},
                "simcOptions": {"ilevel": "272", "bonus_id": "9010"},
                "capabilityOverrides": {
                    "socketCount": 0,
                    "canEnchant": False,
                    "canEmbellish": False,
                },
                "sourceRefIds": [],
            },
        }
        context["ruleParameters"] = {
            "inventoryTypesBySlot": {
                "head": ["head"],
                "main_hand": ["weapon"],
            },
            "allowedArmorTypesByClass": {"mage": ["cloth"]},
            "armorRestrictedSlots": ["head"],
            "allowedWeaponTypesByClassSpec": {
                "mage:arcane": ["staff"],
            },
            "dualWieldByClassSpec": {"mage:arcane": False},
            "weaponModesByClassSpec": {"mage:arcane": "two_hand"},
            "requiredSlots": ["head", "main_hand"],
            "uniqueLimits": {},
            "uniqueGemLimits": {},
            "runeforgeAllowedClassSpecs": [],
            "embellishmentLimit": 2,
            "catalystRevision": "catalyst-proof-v1",
            "crossSlotBlockers": [],
            "setAggregationInputs": [],
            "sourceRefIds": [],
        }
        context["capabilities"] = {
            "serializer": {
                "enabled": True,
                "revision": "websim-profile-compat-v1",
            },
            "catalyst": {
                "enabled": False,
                "revision": "catalyst-proof-v1",
            },
        }

        bound = bind_exact_template_authority(
            projected,
            context,
            exact,
            browse_catalog,
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        resolver_snapshot = gear_resolver.resolve(
            bound["selectionIntent"],
            bound["authorityContext"],
        )
        loadout = build_resolved_loadout_from_registry(
            resolver_snapshot=resolver_snapshot,
            exact_registry=exact,
            template_scope="community",
            template_authority_identity=TEMPLATE_AUTHORITY_IDENTITY,
        )
        talent_lines = ["talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"]
        snapshot = build_simulation_snapshot(
            resolved_loadout=loadout,
            talent_profile_key=talent_profile_key(talent_lines),
            talent_lines=talent_lines,
            character_context={
                "classKey": "mage",
                "specKey": "arcane",
                "name": "Exact Import",
                "race": "troll",
                "level": 90,
                "role": "spell",
                "position": "back",
            },
            scenario_options={
                "scenarioKey": "single",
                "fightStyle": "Patchwerk",
                "desiredTargets": 1,
                "maxTime": 300,
                "iterations": 1000,
                "varyCombatLength": "0.2",
                "calculateScaleFactors": 0,
            },
            preparation_lines=["optimal_raid=0"],
            compiler_revision="simc-profile-compiler-v1",
            simc_runtime_revision="simc-runtime-v1",
        )

        self.assertEqual(projection["status"], "verified")
        self.assertEqual(bound["status"], "verified")
        self.assertEqual(resolver_snapshot["status"], "verified")
        self.assertEqual(loadout["status"], "ready")
        self.assertEqual(snapshot["status"], "ready")
        self.assertNotIn(
            "1001",
            {row["itemId"] for row in browse_catalog["browseVariants"]},
        )
        self.assertIn(
            "head=item_1001,id=1001,ilevel=266,bonus_id=9001/9002",
            snapshot["canonicalSimcInput"],
        )

    def test_bind_infers_unique_exact_only_template_from_source_variants(self):
        """Profile re-resolve must recover one exact template without publishing it."""
        exact = exact_registry()
        import_intent = intent()
        import_intent["slots"]["head"]["variantKey"] = "variant-head"
        browse_catalog = catalog()
        browse_catalog["browseVariants"] = [
            row
            for row in browse_catalog["browseVariants"]
            if row["itemId"] != "1001"
        ]
        projected = project_exact_template_intent(
            import_intent,
            exact,
            browse_catalog,
            TEMPLATE_AUTHORITY_IDENTITY,
        )["selectionIntent"]

        result = bind_exact_template_authority(
            projected,
            authority_context(projected),
            exact,
            browse_catalog,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["templateAuthorityIdentity"],
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        self.assertNotIn(
            "1001",
            {row["itemId"] for row in browse_catalog["browseVariants"]},
        )

    def test_project_accepts_server_rebound_exact_source_without_publishing_its_alias(self):
        """A server-only fallback mapping may bind exact evidence to one verified Browse row."""
        import_intent = intent()
        import_intent["slots"]["head"]["_catalogSourceVariantKey"] = "variant-head"
        browse_catalog = catalog()
        browse_catalog["browseVariants"][0]["sourceVariantKeys"] = [
            "catalog-head"
        ]

        result = project_exact_template_intent(
            import_intent,
            exact_registry(),
            browse_catalog,
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["selectionIntent"]["slots"]["head"]["variantKey"],
            HEAD_BROWSE,
        )
        self.assertEqual(
            result["selectionIntent"]["slots"]["head"][
                "_catalogSourceVariantKey"
            ],
            "variant-head",
        )

    def test_bind_injects_only_the_unique_exact_template_authority(self):
        projection = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        projected = projection["selectionIntent"]
        context = authority_context(projected)
        context["itemsById"]["1002"]["baseCapabilities"].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": [
                "catalog-enchant-placeholder",
                "official-main-enchant",
            ],
        })
        context["variantsByKey"][MAIN_BROWSE]["capabilityOverrides"].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": [
                "catalog-enchant-placeholder",
                "official-main-enchant",
            ],
        })
        context["optionsById"]["official-main-enchant"] = {
            "optionId": "official-main-enchant",
            "optionType": "enchant",
            "displayName": "Official Main Hand Enchant",
            "applicableSlots": ["main_hand"],
            "statDeltas": {},
            "simcOptions": {"enchant_id": "official"},
            "sourceRefIds": [],
        }

        result = bind_exact_template_authority(
            projected,
            context,
            exact_registry(),
            catalog(),
        )

        self.assertEqual(result["status"], "verified")
        bound = result["authorityContext"]
        option_id = projected["slots"]["main_hand"]["enchantOptionId"]
        self.assertEqual(
            bound["dependencyVector"]["templateOriginSignature"],
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        self.assertEqual(
            bound["dependencyVector"]["communityTemplateRevision"],
            bound["manifest"]["communityTemplateReleaseId"],
        )
        self.assertEqual(bound["missingFields"], [])
        self.assertIn(option_id, bound["optionsById"])
        self.assertIn(
            option_id,
            bound["itemsById"]["1002"]["baseCapabilities"][
                "allowedEnchantOptionIds"
            ],
        )
        self.assertEqual(
            bound["itemsById"]["1002"]["baseCapabilities"][
                "allowedEnchantOptionIds"
            ],
            [option_id, "official-main-enchant"],
        )
        self.assertTrue(
            bound["itemsById"]["1002"]["baseCapabilities"]["canEnchant"]
        )
        self.assertTrue(
            bound["variantsByKey"][MAIN_BROWSE][
                "capabilityOverrides"
            ]["canEnchant"]
        )
        self.assertIn(
            option_id,
            bound["variantsByKey"][MAIN_BROWSE][
                "capabilityOverrides"
            ]["allowedEnchantOptionIds"],
        )
        self.assertEqual(
            bound["variantsByKey"][MAIN_BROWSE][
                "capabilityOverrides"
            ]["allowedEnchantOptionIds"],
            [option_id, "official-main-enchant"],
        )
        source_ref = bound["optionsById"][option_id]["sourceRefIds"][0]
        self.assertIn(source_ref, bound["evidenceRecordsById"])

    def test_exact_managed_enhancement_publishes_verified_slot_options_for_replacement(self):
        projection = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        projected = projection["selectionIntent"]
        context = authority_context(projected)
        context["optionsById"]["official-main-enchant"] = {
            "optionId": "official-main-enchant",
            "optionType": "enchant",
            "displayName": "Official Main Hand Enchant",
            "applicableSlots": ["main_hand"],
            "statDeltas": {},
            "simcOptions": {"enchant_id": "official"},
            "sourceRefIds": [],
        }

        result = bind_exact_template_authority(
            projected,
            context,
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        bound = result["authorityContext"]
        exact_option_id = projected["slots"]["main_hand"]["enchantOptionId"]
        expected = [exact_option_id, "official-main-enchant"]
        self.assertEqual(
            bound["itemsById"]["1002"]["baseCapabilities"][
                "allowedEnchantOptionIds"
            ],
            expected,
        )
        self.assertEqual(
            bound["variantsByKey"][MAIN_BROWSE]["capabilityOverrides"][
                "allowedEnchantOptionIds"
            ],
            expected,
        )

    def test_exact_managed_socket_publishes_canonical_gem_replacements(self):
        registry = exact_registry()
        registry["templateReferences"][0]["editorManagedEnhancementFields"] = [
            "gemOptionIds"
        ]
        registry["enhancementSelections"][0]["selection"]["gemIds"] = [
            "240908"
        ]
        projection = project_exact_template_intent(
            intent(),
            registry,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        projected = projection["selectionIntent"]
        context = authority_context(projected)
        context["optionsById"]["official-head-gem"] = {
            "optionId": "official-head-gem",
            "optionType": "gem",
            "displayName": "Official Head Gem",
            "applicableSlots": ["head"],
            "statDeltas": {},
            "simcOptions": {"gem_id": "240888"},
            "sourceRefIds": [],
        }

        result = bind_exact_template_authority(
            projected,
            context,
            registry,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        bound = result["authorityContext"]
        exact_option_id = projected["slots"]["head"]["gemOptionIds"][0]
        expected = [exact_option_id, "official-head-gem"]
        self.assertEqual(
            bound["itemsById"]["1001"]["baseCapabilities"]["socketCount"],
            1,
        )
        self.assertEqual(
            bound["itemsById"]["1001"]["baseCapabilities"][
                "allowedGemOptionIds"
            ],
            expected,
        )
        self.assertEqual(
            bound["variantsByKey"][HEAD_BROWSE]["capabilityOverrides"][
                "allowedGemOptionIds"
            ],
            expected,
        )

    def test_forged_or_stale_exact_option_fails_closed(self):
        projection = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        forged = copy.deepcopy(projection["selectionIntent"])
        forged["slots"]["main_hand"]["enchantOptionId"] = (
            "exact-option:sha256:" + ("f" * 64)
        )

        result = bind_exact_template_authority(
            forged,
            authority_context(forged),
            exact_registry(),
            catalog(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "EXACT_TEMPLATE_OPTION_NOT_AUTHORIZED",
            result["problemCodes"],
        )

    def test_binding_preserves_exact_options_and_allows_official_edit_on_an_empty_field(self):
        projected = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )["selectionIntent"]
        edited = copy.deepcopy(projected)
        edited["slots"]["head"]["enchantOptionId"] = "official-head-enchant"
        context = authority_context(projected)
        context["optionsById"]["official-head-enchant"] = {
            "optionId": "official-head-enchant",
            "optionType": "enchant",
            "displayName": "Official Head Enchant",
            "applicableSlots": ["head"],
            "statDeltas": {},
            "simcOptions": {"enchant_id": "official"},
            "sourceRefIds": [],
        }
        context["itemsById"]["1001"]["baseCapabilities"].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": ["official-head-enchant"],
        })
        context["variantsByKey"][HEAD_BROWSE]["capabilityOverrides"].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": ["official-head-enchant"],
        })

        result = bind_exact_template_authority(
            edited,
            context,
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["selectionIntent"]["slots"]["head"]["enchantOptionId"],
            "official-head-enchant",
        )
        self.assertRegex(
            result["selectionIntent"]["slots"]["main_hand"]["enchantOptionId"],
            r"^exact-option:sha256:[0-9a-f]{64}$",
        )

    def test_binding_allows_official_option_to_replace_an_exact_import_option(self):
        projected = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )["selectionIntent"]
        edited = copy.deepcopy(projected)
        edited["slots"]["main_hand"]["enchantOptionId"] = (
            "official-main-enchant"
        )
        context = authority_context(projected)
        context["optionsById"]["official-main-enchant"] = {
            "optionId": "official-main-enchant",
            "optionType": "enchant",
            "displayName": "Official Main Hand Enchant",
            "applicableSlots": ["main_hand"],
            "statDeltas": {},
            "simcOptions": {"enchant_id": "official"},
            "sourceRefIds": [],
        }
        context["itemsById"]["1002"]["baseCapabilities"].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": ["official-main-enchant"],
        })
        context["variantsByKey"][MAIN_BROWSE][
            "capabilityOverrides"
        ].update({
            "canEnchant": True,
            "allowedEnchantOptionIds": ["official-main-enchant"],
        })

        result = bind_exact_template_authority(
            edited,
            context,
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["selectionIntent"]["slots"]["main_hand"][
                "enchantOptionId"
            ],
            "official-main-enchant",
        )
        self.assertEqual(
            result["authorityContext"]["dependencyVector"][
                "templateOriginSignature"
            ],
            TEMPLATE_AUTHORITY_IDENTITY,
        )

    def test_unique_empty_enhancement_loadout_still_binds_template_identity(self):
        registry = exact_registry()
        registry["exactItemInstances"] = [
            row for row in registry["exactItemInstances"] if row["exactItemInstanceKey"] == HEAD_KEY
        ]
        registry["validations"] = [
            row for row in registry["validations"] if row["exactItemInstanceKey"] == HEAD_KEY
        ]
        registry["enhancementSelections"] = [
            row
            for row in registry["enhancementSelections"]
            if row["enhancementSelectionKey"] != ENCHANT_SELECTION
        ]
        registry["templateReferences"] = [
            row for row in registry["templateReferences"] if row["slot"] == "head"
        ]
        head_only = intent()
        head_only["slots"] = {"head": head_only["slots"]["head"]}

        result = bind_exact_template_authority(
            head_only,
            authority_context(head_only),
            registry,
            catalog(),
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["authorityContext"]["dependencyVector"][
                "templateOriginSignature"
            ],
            TEMPLATE_AUTHORITY_IDENTITY,
        )

    def test_binding_prefilters_unrelated_template_groups_before_projection(self):
        registry = exact_registry()
        unrelated_identity = "sha256:" + ("1" * 64)
        unrelated = copy.deepcopy(registry["templateReferences"])
        for row in unrelated:
            row["templateAuthorityIdentity"] = unrelated_identity
            row["templateContentHash"] = "sha256:" + ("2" * 64)
            row["itemId"] = "9999"
            row["sourceVariantKey"] = "variant-unrelated"
        registry["templateReferences"].extend(unrelated)
        projected = project_exact_template_intent(
            intent(),
            registry,
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )["selectionIntent"]
        original_projector = (
            gear_exact_template_options._project_identity
        )

        with patch(
            "server.gear_exact_template_options._project_identity",
            wraps=original_projector,
        ) as projector:
            result = bind_exact_template_authority(
                projected,
                authority_context(intent()),
                registry,
                catalog(),
            )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(projector.call_count, 1)


if __name__ == "__main__":
    unittest.main()
