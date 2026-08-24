import unittest

from server.s2_crafted_compatibility_evidence import (
    build_crafted_compatibility_evidence,
)


class S2CraftedCompatibilityEvidenceTest(unittest.TestCase):
    def test_joins_category_items_and_marks_secondary_and_embellishment_options(self):
        targets = {
            "status": "verified",
            "categoryIds": ["809", "854", "902"],
            "categories": {
                "809": {"id": "809", "name": "Quickblade", "roleIds": ["393"], "recipeIds": ["100"]},
                "854": {"id": "854", "name": "Lucky Keychain", "roleIds": ["502"], "recipeIds": ["100"]},
                "902": {"id": "902", "name": "Outdoor Upgrade Dungeon", "roleIds": ["469"], "recipeIds": ["101"]},
            },
            "roles": [
                {"id": "393", "name": "Customize Secondary Stats", "recipeIds": ["100"], "categoryIds": ["809"]},
                {"id": "502", "name": "Add Embellishment", "recipeIds": ["100"], "categoryIds": ["854"]},
                {"id": "469", "name": "Empower", "recipeIds": ["101"], "categoryIds": ["902"]},
            ],
            "equipmentRecipes": [
                {"recipeId": "100", "itemIds": ["200"], "roleIds": ["393", "502"]},
                {"recipeId": "101", "itemIds": ["201"], "roleIds": ["469"]},
            ],
        }
        rows = {
            "ModifiedCraftingCategory": [
                {"ID": 809, "DisplayName_lang": "Quickblade"},
                {"ID": 854, "DisplayName_lang": "Lucky Keychain"},
                {"ID": 902, "DisplayName_lang": "Outdoor Upgrade Dungeon"},
            ],
            "ModifiedCraftingReagentItem": [
                {"ID": 1, "ModifiedCraftingCategoryID": 809},
                {"ID": 2, "ModifiedCraftingCategoryID": 854},
                {"ID": 3, "ModifiedCraftingCategoryID": 902},
            ],
            "ModifiedCraftingItem": [
                {"ItemID": 300, "ModifiedCraftingReagentItemID": 1, "CraftingQualityID": 0},
                {"ItemID": 301, "ModifiedCraftingReagentItemID": 2, "CraftingQualityID": 0},
                {"ItemID": 302, "ModifiedCraftingReagentItemID": 3, "CraftingQualityID": 0},
            ],
            "CraftingReagentQuality": [],
        }
        result = build_crafted_compatibility_evidence(
            targets,
            db2_rows=rows,
            db2_refs={},
            official_items={
                "300": {"id": 300, "name": "Missive", "is_equippable": False, "modified_crafting": {"category": {"id": 809}}},
                "301": {"id": 301, "name": "Lucky Keychain", "is_equippable": False, "modified_crafting": {"category": {"id": 854}}},
                "302": {"id": 302, "name": "Dungeon Crest", "is_equippable": False, "modified_crafting": {"category": {"id": 902}}},
            },
            official_refs={},
            official_missing=[],
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["categories"]["809"]["status"], "verified")
        self.assertEqual(result["categories"]["809"]["optionItems"][0]["itemId"], "300")
        recipe = next(row for row in result["recipes"] if row["recipeId"] == "100")
        self.assertEqual(recipe["secondaryStatCompatibility"]["status"], "verified")
        self.assertEqual(recipe["secondaryStatCompatibility"]["options"][0]["itemId"], "300")
        self.assertEqual(recipe["embellishmentCompatibility"]["status"], "verified")
        dungeon = next(row for row in result["recipes"] if row["recipeId"] == "101")
        self.assertEqual(
            dungeon["enhancementCompatibility"]["status"],
            "excluded",
        )
        self.assertEqual(
            dungeon["enhancementCompatibility"]["reasonCode"],
            "OUT_OF_SCOPE_DUNGEON_UPGRADE_CATEGORY",
        )

    def test_currency_quality_is_a_verified_crafted_option_without_fabricating_item_id(self):
        targets = {
            "status": "verified",
            "categoryIds": ["911"],
            "categories": {
                "911": {
                    "id": "911",
                    "name": "S2 Crests",
                    "roleIds": ["392"],
                    "recipeIds": ["100"],
                }
            },
            "roles": [
                {
                    "id": "392",
                    "name": "Infuse with Power",
                    "recipeIds": ["100"],
                    "categoryIds": ["911"],
                }
            ],
            "equipmentRecipes": [
                {"recipeId": "100", "itemIds": ["200"], "roleIds": ["392"]}
            ],
        }
        result = build_crafted_compatibility_evidence(
            targets,
            db2_rows={
                "ModifiedCraftingCategory": [{"ID": 911, "DisplayName_lang": "S2 Crests"}],
                "ModifiedCraftingReagentItem": [],
                "ModifiedCraftingItem": [],
                "CraftingReagentQuality": [
                    {
                        "ID": 2034,
                        "ModifiedCraftingCategoryID": 911,
                        "CurrencyTypesID": 3445,
                        "OrderIndex": 0,
                        "MaxDifficultyAdjustment": 10,
                        "ReagentEffectPct": 0,
                    },
                    {
                        "ID": 2035,
                        "ModifiedCraftingCategoryID": 911,
                        "CurrencyTypesID": 3446,
                        "OrderIndex": 1,
                        "MaxDifficultyAdjustment": 20,
                        "ReagentEffectPct": 0,
                    },
                ],
                "CurrencyTypes": [
                    {"ID": 3445, "Name_lang": "Hero Mistcrest", "Quality": 4},
                    {"ID": 3446, "Name_lang": "Myth Mistcrest", "Quality": 4},
                ],
            },
            db2_refs={},
            official_items={},
            official_refs={},
            official_missing=[],
        )

        category = result["categories"]["911"]
        self.assertEqual(category["status"], "verified")
        self.assertEqual(category["optionItemIds"], [])
        self.assertEqual(
            [row["currencyTypeId"] for row in category["currencyOptions"]],
            ["3445", "3446"],
        )
        recipe = result["recipes"][0]
        self.assertEqual(recipe["enhancementCompatibility"]["status"], "verified")
        self.assertEqual(
            [row["kind"] for row in recipe["enhancementCompatibility"]["options"]],
            ["currency", "currency"],
        )

    def test_missing_official_item_keeps_category_unverified(self):
        targets = {
            "status": "verified",
            "categoryIds": ["809"],
            "categories": {"809": {"id": "809", "name": "Quickblade", "roleIds": ["393"], "recipeIds": ["100"]}},
            "roles": [{"id": "393", "name": "Customize Secondary Stats", "recipeIds": ["100"], "categoryIds": ["809"]}],
            "equipmentRecipes": [{"recipeId": "100", "itemIds": ["200"], "roleIds": ["393"]}],
        }
        result = build_crafted_compatibility_evidence(
            targets,
            db2_rows={
                "ModifiedCraftingCategory": [{"ID": 809}],
                "ModifiedCraftingReagentItem": [{"ID": 1, "ModifiedCraftingCategoryID": 809}],
                "ModifiedCraftingItem": [{"ItemID": 300, "ModifiedCraftingReagentItemID": 1}],
                "CraftingReagentQuality": [],
            },
            db2_refs={},
            official_items={},
            official_refs={},
            official_missing=[{"itemId": "300", "status": "not_found", "httpStatus": 404}],
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["categories"]["809"]["status"], "UNVERIFIED")
        self.assertEqual(result["recipes"][0]["secondaryStatCompatibility"]["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
