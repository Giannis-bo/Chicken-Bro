import json
import subprocess
import unittest
from pathlib import Path


class SimcGearImportTest(unittest.TestCase):
    @staticmethod
    def complete_profile(*extra_lines):
        slots = (
            "head", "neck", "shoulder", "back", "chest", "wrist", "hands",
            "waist", "legs", "feet", "finger1", "finger2", "trinket1",
            "trinket2", "main_hand",
        )
        return "\n".join([
            'warrior="Fixture"', "spec=fury", "race=orc", "talents=ABC", "fight_style=Patchwerk",
            *extra_lines,
            *[f"{slot}=Fixture_{slot},id={225574 + index}" for index, slot in enumerate(slots)],
        ])

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

    def test_unknown_option_key_and_value_never_echo_into_serialized_result(self):
        from server.simc_gear_import import parse_simc_exact_import

        secret = "task3a_privacy_secret_805_unique"
        raw = self.complete_profile().replace(
            "head=Fixture_head,id=225574",
            f"head=Fixture_head,id=225574,{secret}={secret}",
            1,
        )
        result = parse_simc_exact_import(
            raw,
            class_key="warrior",
            spec_key="fury",
            level=80,
            season_revision="season-r1",
            game_build="build-r1",
        )

        self.assertEqual(result["status"], "blocked")
        unknown = [
            problem
            for problem in result["problems"]
            if problem["code"] == "UNKNOWN_GEAR_OPTION"
        ]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["path"], "profile.lines.5.options.unknown")
        self.assertEqual(
            unknown[0]["message"],
            "Gear option is not supported by Exact import.",
        )
        self.assertNotIn(
            secret,
            json.dumps(result, sort_keys=True, ensure_ascii=False),
        )

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

    # Catches treating standard SimulationCraft character metadata as a second
    # character section instead of ignoring it as non-gear input.
    def test_extracts_complete_plugin_export_with_region_server_and_professions(self):
        from server.simc_gear_import import parse_simc_exact_import

        result = parse_simc_exact_import(
            self.complete_profile("region=us", "server=area_52", "professions=alchemy=100/engineering=100"),
            class_key="warrior", spec_key="fury", level=80,
            season_revision="season-r1", game_build="build-r1",
        )

        self.assertEqual(result["status"], "parsed")
        self.assertEqual(result["problems"], [])

    # Catches truncating an ambiguous off-hand `ilevel` to its first value.
    def test_blocks_ambiguous_off_hand_item_level_at_declared_item_level_path(self):
        from server.simc_gear_import import parse_simc_exact_import

        result = parse_simc_exact_import(
            self.complete_profile("off_hand=Fixture Shield,id=225590,ilevel=700/701"),
            class_key="warrior", spec_key="fury", level=80,
            season_revision="season-r1", game_build="build-r1",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("intent.slots.off_hand.declaredItemLevel", [problem["path"] for problem in result["problems"]])

    # Catches a release requirement that is valid JSON but cannot pass the
    # Harness Strict validator or drifts back to the stopped four-slice plan.
    def test_exact_first_requirement_passes_harness_and_freezes_task3a_slice(self):
        root = Path(__file__).resolve().parents[1]
        requirement = root / "artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json"
        plan = root / "docs/plans/2026-08-04-equipment-simulator-exact-first-persistence-resequence.md"
        completed = subprocess.run(
            ["node", "scripts/project-harness.js", "--json", "--check-requirement", "--requirement-file", str(requirement)],
            cwd=root, text=True, capture_output=True, check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "project_harness_requirement_check_passed")
        requirement_payload = json.loads(requirement.read_text())
        self.assertEqual(
            [slice_["planHeading"] for slice_ in requirement_payload["releaseSlices"]],
            ["Task 3A：完整 Canonical Authority Bundle 持久化"],
        )
        plan_text = plan.read_text()
        for slice_ in requirement_payload["releaseSlices"]:
            self.assertIn(f"## {slice_['planHeading']}", plan_text)

    def test_reachable_canonical_plan_summaries_require_fourth_candidate(self):
        root = Path(__file__).resolve().parents[1]
        plan_index = (root / "docs/plans/README.md").read_text(encoding="utf-8")
        summaries = (
            root / "docs/plans/2026-08-04-equipment-simulator-canonical-kernel-implementation.md",
            root / "docs/plans/2026-08-04-equipment-simulator-canonical-owner-change-control.md",
            root / "docs/plans/2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md",
        )

        for summary in summaries:
            with self.subTest(summary=summary.name):
                self.assertIn(summary.name, plan_index)
                top_level = "\n".join(
                    summary.read_text(encoding="utf-8").splitlines()[:10]
                )
                self.assertIn(
                    "candidate_rerun_required / evidence_promotion_blocked",
                    top_level,
                )
                self.assertIn("t3a260805113656", top_level)
                self.assertNotIn("candidate_pending", top_level)


if __name__ == "__main__":
    unittest.main()
