import unittest


class SimcGearImportTest(unittest.TestCase):
    # Catches a parser that silently drops plugin-only exact fields or fills in
    # item level from an unrelated catalog/default.
    def test_extracts_complete_plugin_export_without_catalog_defaults(self):
        from server.simc_gear_import import parse_simc_exact_import

        slots = (
            "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
            "waist", "legs", "feet", "finger1", "finger2", "trinket1",
            "trinket2", "main_hand",
        )
        raw = "\n".join([
            'warrior="Fixture"', "spec=fury", "race=orc", "talents=ABC", "fight_style=Patchwerk",
            *[f"{slot}=Fixture_{slot},id={225574 + index}" for index, slot in enumerate(slots)],
        ])

        result = parse_simc_exact_import(
            raw, class_key="warrior", spec_key="fury", level=80,
            season_revision="season-revision-fixture-v1", game_build="game-build-fixture-v1",
        )

        self.assertEqual(result["schemaRevision"], "exact-import-parse-v1")
        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["problems"], [])
        self.assertNotIn("raw", result)
        self.assertEqual(list(result["intent"]["slots"]), list(slots))
        self.assertEqual(result["intent"]["slots"]["head"], {
            "itemId": "225574", "declaredItemLevel": None, "bonusIds": [], "context": "",
            "gemIds": [], "gemBonusIds": [], "gemItemLevels": [], "enchantId": "",
            "craftedStats": [], "embellishmentIds": [], "redirectedBaseStats": [],
        })
        with_off_hand = parse_simc_exact_import(
            raw + "\noff_hand=Fixture Shield,id=225590", class_key="warrior", spec_key="fury", level=80,
            season_revision="season-revision-fixture-v1", game_build="game-build-fixture-v1",
        )
        self.assertEqual(list(with_off_hand["intent"]["slots"]), [*slots, "off_hand"])
        self.assertEqual(with_off_hand["intent"]["slots"]["off_hand"]["declaredItemLevel"], None)

    # Catches accepting a second character profile or a profile whose declared
    # identity conflicts with the caller-bound identity.
    def test_blocks_multiple_or_conflicting_character_sections_with_paths(self):
        from server.simc_gear_import import parse_simc_exact_import

        cases = (
            ('warrior="One"\nmage="Two"', "profile.characters.1.classKey"),
            ('mage="Wrong"\nspec=fury', "profile.characters.0.classKey"),
            ('warrior="Right"\nspec=arms', "profile.characters.0.specKey"),
        )
        for raw, path in cases:
            with self.subTest(path=path):
                result = parse_simc_exact_import(
                    raw, class_key="warrior", spec_key="fury", level=80,
                    season_revision="season-r1", game_build="build-r1",
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn(path, [problem["path"] for problem in result["problems"]])
                self.assertNotIn("raw", result)

    # Catches permissive token parsing: accepting duplicate/unknown slots,
    # options, auxiliary gem arrays that no longer align, or line injection.
    def test_blocks_ambiguous_or_untrusted_gear_syntax_at_its_specific_path(self):
        from server.simc_gear_import import parse_simc_exact_import

        cases = (
            ("head=Item,id=1\nhead=Other,id=2", "intent.slots.head"),
            ("helm=Item,id=1", "profile.lines.0.slot"),
            ("head=Item,id=1,unknown=2", "profile.lines.0.options.unknown"),
            ("head=Item,id=1,gem_id=10/11,gem_bonus_id=12", "intent.slots.head.gemBonusIds"),
            ("head=Item,id=1\nlevel=80\nhead=Injected,id=2", "intent.slots.head"),
            ("head=Item,ilevel=700", "intent.slots.head.itemId"),
        )
        for raw, path in cases:
            with self.subTest(path=path):
                result = parse_simc_exact_import(
                    raw, class_key="warrior", spec_key="fury", level=80,
                    season_revision="season-r1", game_build="build-r1",
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn(path, [problem["path"] for problem in result["problems"]])

    # Catches a character-count bound that lets an over-limit UTF-8 import
    # enter parsing or a newline-bearing caller identity enter output.
    def test_blocks_oversized_utf8_profile_and_injected_input_identity(self):
        from server.simc_gear_import import parse_simc_exact_import

        oversized = "#" + "装" * 21846
        result = parse_simc_exact_import(
            oversized, class_key="warrior", spec_key="fury", level=80,
            season_revision="season-r1", game_build="build-r1",
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("rawProfile", [problem["path"] for problem in result["problems"]])

        injected = parse_simc_exact_import(
            "", class_key="warrior\nname=inject", spec_key="fury", level=80,
            season_revision="season-r1", game_build="build-r1",
        )
        self.assertEqual(injected["status"], "blocked")
        self.assertIn("intent.eligibilityContext.classKey", [problem["path"] for problem in injected["problems"]])


if __name__ == "__main__":
    unittest.main()
