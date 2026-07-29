import copy
import unittest

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
                "enchantOptionId": "",
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

    def test_bind_injects_only_the_unique_exact_template_authority(self):
        projection = project_exact_template_intent(
            intent(),
            exact_registry(),
            catalog(),
            TEMPLATE_AUTHORITY_IDENTITY,
        )
        projected = projection["selectionIntent"]
        context = authority_context(projected)

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
        source_ref = bound["optionsById"][option_id]["sourceRefIds"][0]
        self.assertIn(source_ref, bound["evidenceRecordsById"])

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


if __name__ == "__main__":
    unittest.main()
