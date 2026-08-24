import unittest

from server.s2_enhancement_authority import build_s2_enhancement_authority


class S2EnhancementAuthorityTest(unittest.TestCase):
    def _authority(self):
        relationships = [
            {
                "itemId": "200",
                "itemSlot": "feet",
                "scopeStatus": "included",
                "secondaryStatCompatibility": {
                    "status": "verified",
                    "options": [
                        {
                            "categoryId": "809",
                            "itemId": "9001",
                            "name": "Quickblade Missive",
                            "evidenceStatus": "verified",
                            "evidenceRefs": ["official-api:/data/wow/item/9001#/id"],
                        },
                        {
                            "categoryId": "869",
                            "itemId": "9006",
                            "name": "Flux Cogwheel",
                            "evidenceStatus": "verified",
                        },
                    ],
                },
                "embellishmentCompatibility": {
                    "status": "verified",
                    "options": [
                        {
                            "categoryId": "769",
                            "itemId": "9002",
                            "name": "Arcanoweave Lining",
                            "evidenceStatus": "verified",
                            "evidenceRefs": ["official-api:/data/wow/item/9002#/id"],
                        },
                        {
                            "categoryId": "856",
                            "itemId": "9007",
                            "name": "B1P, Scorcher of Souls",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "918",
                            "itemId": "9008",
                            "name": "Polished Ammolite",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "815",
                            "itemId": "9003",
                            "name": "Profession-only Missive",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "999",
                            "itemId": "9004",
                            "name": "Unknown Optional Reagent",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "855",
                            "itemId": "9005",
                            "name": "Kinetic Ankle Primers",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "854",
                            "itemId": "9010",
                            "name": "Lucky Keychain",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "857",
                            "itemId": "9013",
                            "name": "M3DDY, Travel-Sized",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "873",
                            "itemId": "9011",
                            "name": "HU5H, Nonchalant Pup",
                            "evidenceStatus": "verified",
                        },
                        {
                            "categoryId": "919",
                            "itemId": "9012",
                            "name": "Coiled Snake-Eye",
                            "evidenceStatus": "verified",
                        },
                    ],
                },
                "enhancementCompatibility": {
                    "status": "verified",
                    "options": [],
                },
            }
        ]
        official_items = {
            "9001": {
                "id": 9001,
                "name": "Quickblade Missive",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 809}},
                "description": "Guarantee Versatility and Critical Strike.",
            },
            "9002": {
                "id": 9002,
                "name": "Arcanoweave Lining",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 769}},
            },
            "9006": {
                "id": 9006,
                "name": "Flux Cogwheel",
                "item_class": {"id": 7},
                "modified_crafting": {
                    "category": {"id": 869},
                    "description": "Allocate the secondary stat to Critical Strike.",
                },
            },
            "9007": {
                "id": 9007,
                "name": "B1P, Scorcher of Souls",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 856}},
            },
            "9008": {
                "id": 9008,
                "name": "Polished Ammolite",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 918}},
            },
            "9003": {
                "id": 9003,
                "name": "Profession-only Missive",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 815}},
            },
            "9004": {
                "id": 9004,
                "name": "Unknown Optional Reagent",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 999}},
            },
            "9005": {
                "id": 9005,
                "name": "Kinetic Ankle Primers",
                "item_class": {"id": 7},
                "modified_crafting": {
                    "category": {"id": 855},
                    "description": "$@spelldesc1246308",
                },
            },
            "9010": {
                "id": 9010,
                "name": "Lucky Keychain",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 854}},
            },
            "9013": {
                "id": 9013,
                "name": "M3DDY, Travel-Sized",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 857}},
            },
            "9011": {
                "id": 9011,
                "name": "HU5H, Nonchalant Pup",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 873}},
            },
            "9012": {
                "id": 9012,
                "name": "Coiled Snake-Eye",
                "item_class": {"id": 7},
                "modified_crafting": {"category": {"id": 919}},
            },
            "240888": {
                "id": 240888,
                "name": "Flawless Quick Peridot",
                "item_class": {"id": 3},
                "preview_item": {
                    "gem_properties": {"effect": "+15 Haste"}
                },
            },
        }
        enchant_rows = [
            {
                "ID": 8013,
                "Name_lang": "Enchant Chest - Mark of the Magister",
                "Effect_0": 5,
                "EffectArg_0": 5,
            },
            {"ID": 8158, "Name_lang": "Forest Hunter's Armor Kit"},
            {"ID": 8159, "Name_lang": "Forest Hunter's Armor Kit"},
            {"ID": 8163, "Name_lang": "Blood Knight's Armor Kit"},
        ]
        item_definitions = [
            {
                "itemId": "200",
                "itemSlot": "feet",
                "db2StaticFacts": {"socketCount": 1},
            },
            {
                "itemId": "201",
                "itemSlot": "chest",
                "db2StaticFacts": {"socketCount": 0},
            },
            {
                "itemId": "202",
                "itemSlot": "legs",
                "db2StaticFacts": {"socketCount": 0},
            },
        ]
        variants = [
            {
                "itemId": "200",
                "itemSlot": "feet",
                "variantKey": "v-feet",
                "status": "verified",
                "canonicalSimcInput": {
                    "status": "verified",
                    "line": "feet=base,id=200,ilevel=300,bonus_id=1",
                },
            },
            {
                "itemId": "201",
                "itemSlot": "chest",
                "variantKey": "v-chest",
                "status": "verified",
                "canonicalSimcInput": {
                    "status": "verified",
                    "line": "chest=base,id=201,ilevel=300,bonus_id=1",
                },
            },
            {
                "itemId": "202",
                "itemSlot": "legs",
                "variantKey": "v-legs",
                "status": "verified",
                "canonicalSimcInput": {
                    "status": "verified",
                    "line": "legs=base,id=202,ilevel=300,bonus_id=1",
                },
            },
        ]
        templates = [
            {
                "itemId": "200",
                "itemSlot": "feet",
                "variantKey": "crafted-feet",
                "status": "verified",
                "selectionContract": {
                    "secondaryStats": {
                        "status": "verified",
                        "options": relationships[0]["secondaryStatCompatibility"]["options"],
                    },
                    "embellishment": {
                        "status": "verified",
                        "options": relationships[0]["embellishmentCompatibility"]["options"],
                    },
                },
                "canonicalSimcInput": {
                    "status": "verified",
                    "line": "feet=crafted,id=200,ilevel=300,bonus_id=1",
                },
            }
        ]
        return build_s2_enhancement_authority(
            crafted_relationships=relationships,
            variants=variants,
            crafted_variant_templates=templates,
            item_definitions=item_definitions,
            official_option_items=official_items,
            enchant_rows=enchant_rows,
            official_option_refs={
                "240888": ["official-api:/data/wow/item/240888#/id"]
            },
            enchant_refs={"8013": ["db2-response:enchant-db2-v1#/rows/0"]},
            spell_rows=[
                {
                    "ID": 1246308,
                    "Name_lang": "Kinetic Ankle Primers",
                    "Description_lang": "Prime your boots for engagement.",
                }
            ],
            spell_effect_rows=[
                {
                    "ID": 1,
                    "SpellID": 1246308,
                    "EffectIndex": 0,
                    "Effect": 6,
                }
            ],
            spell_refs={"1246308": ["db2-response:spell-option-db2-v1#/Spell/1246308"]},
            spell_effect_refs={
                "1246308": ["db2-response:spell-option-db2-v1#/SpellEffect/1246308"]
            },
        )

    def test_preserves_known_option_identity_and_canonical_simc_fields(self):
        result = self._authority()
        options = {row["optionKey"]: row for row in result["options"]}

        self.assertEqual(options["gem-240888"]["simcOptions"], {"gem_id": "240888"})
        self.assertEqual(options["crafted-stats-32-40"]["simcOptions"], {"crafted_stats": "32/40"})
        self.assertEqual(options["embellishment-arcanoweave_lining"]["simcOptions"], {"embellishment": "arcanoweave_lining"})
        self.assertEqual(options["enchant-8013"]["simcOptions"], {"enchant_id": "8013"})
        self.assertEqual(options["crafted-stats-32"]["simcOptions"], {"crafted_stats": "32"})
        self.assertEqual(options["crafted-stats-32"]["applicableSlots"], ["feet", "head", "main_hand", "wrist"])
        self.assertEqual(options["embellishment-b1p_scorcher_of_souls"]["simcOptions"], {"embellishment": "b1p_scorcher_of_souls"})
        self.assertEqual(options["embellishment-polished_ammolite"]["simcOptions"], {"embellishment": "polished_ammolite"})
        self.assertEqual(options["embellishment-kinetic_ankle_primers"]["simcOptions"], {"embellishment": "kinetic_ankle_primers"})
        self.assertEqual(options["embellishment-lucky_keychain"]["simcOptions"], {"embellishment": "lucky_keychain"})
        self.assertEqual(options["embellishment-hu5h_nonchalant_pup"]["simcOptions"], {"embellishment": "hu5h_nonchalant_pup"})
        self.assertEqual(options["embellishment-coiled_snakeeye"]["simcOptions"], {"embellishment": "coiled_snakeeye"})
        self.assertEqual(options["embellishment-m3ddy_travel_sized"]["simcOptions"], {"embellishment": "m3ddy_travel_sized"})
        self.assertEqual(options["embellishment-m3ddy_travel_sized"]["status"], "verified")
        for enchant_id, token in (
            ("8158", "forest_hunters_armor_kit"),
            ("8159", "forest_hunters_armor_kit"),
            ("8163", "blood_knights_armor_kit"),
        ):
            self.assertEqual(options[f"enchant-{enchant_id}"]["status"], "verified")
            self.assertEqual(options[f"enchant-{enchant_id}"]["applicableSlots"], ["legs"])
            self.assertEqual(
                options[f"enchant-{enchant_id}"]["simcSerializerCompatibility"]["tokenizedName"],
                token,
            )
        self.assertEqual(options["embellishment-kinetic_ankle_primers"]["status"], "verified")

        selection_lines = {
            row["optionKey"]: row["canonicalSimcInput"]["line"]
            for row in result["canonicalSelections"]
            if row.get("status") == "verified"
        }
        self.assertIn("gem_id=240888", selection_lines["gem-240888"])
        self.assertIn("crafted_stats=32/40", selection_lines["crafted-stats-32-40"])
        self.assertIn("embellishment=arcanoweave_lining", selection_lines["embellishment-arcanoweave_lining"])
        self.assertIn("embellishment=m3ddy_travel_sized", selection_lines["embellishment-m3ddy_travel_sized"])
        self.assertIn("enchant_id=8013", selection_lines["enchant-8013"])
        for enchant_id in ("8158", "8159", "8163"):
            self.assertIn(f"enchant_id={enchant_id}", selection_lines[f"enchant-{enchant_id}"])

    def test_does_not_silently_promote_unknown_or_out_of_scope_categories(self):
        result = self._authority()
        options = {row["optionKey"]: row for row in result["options"]}

        self.assertEqual(options["embellishment-unknown-999"]["status"], "UNVERIFIED")
        self.assertIn("CRAFTED_EMBELLISHMENT_SIMC_TOKEN_UNVERIFIED", result["blockerCodes"])
        self.assertTrue(
            any(
                row["categoryId"] == "815"
                and row["reasonCode"] == "OUT_OF_SCOPE_PROFESSION_ONLY_CRAFTING_STAT"
                for row in result["exclusions"]
            )
        )


if __name__ == "__main__":
    unittest.main()
