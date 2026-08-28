import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-s2-crafted-output-targets.py"
SPEC = importlib.util.spec_from_file_location("s2_crafted_output_targets", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class S2CraftedOutputTargetsTest(unittest.TestCase):
    def test_classifies_non_equipment_roots_and_keeps_ambiguous_root_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            responses = [
                (
                    "SkillLineAbility",
                    [
                        {"ID": 101, "Spell": 1001},
                        {"ID": 102, "Spell": 1002},
                        {"ID": 103, "Spell": 1003},
                        {"ID": 104, "Spell": 1004},
                        {"ID": 105, "Spell": 1005},
                        {"ID": 106, "Spell": 1006},
                    ],
                ),
                (
                    "SpellEffect",
                    [
                        {"ID": 1, "SpellID": 1001, "Effect": 301, "EffectMiscValue_0": 77},
                        {"ID": 2, "SpellID": 1002, "Effect": 288, "EffectMiscValue_0": 2001},
                        {"ID": 3, "SpellID": 1003, "Effect": 288, "EffectMiscValue_0": 2999},
                        {"ID": 4, "SpellID": 1004, "Effect": 297, "EffectMiscValue_0": 0},
                        {"ID": 5, "SpellID": 1005, "Effect": 288, "EffectMiscValue_0": 2003},
                        {"ID": 6, "SpellID": 1006, "Effect": 288, "EffectMiscValue_0": 0},
                    ],
                ),
                (
                    "CraftingData",
                    [
                        {"ID": 2001, "CraftedItemID": 0},
                        {"ID": 2003, "CraftedItemID": 3001},
                    ],
                ),
            ]
            entries = []
            for index, (table, rows) in enumerate(responses, start=1):
                relative = Path("responses") / f"{index:02d}.json"
                _write(
                    root / relative,
                    {
                        "table": table,
                        "rows": rows,
                    },
                )
                entries.append({"table": table, "responsePath": relative.as_posix()})
            _write(
                root / "capture-manifest.json",
                {
                    "status": "captured",
                    "clientBuild": "12.1.0.69497",
                    "entries": entries,
                },
            )

            report = MODULE.derive_crafted_output_targets(root)

            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["sourceDb2Build"], "12.1.0.69497")
            self.assertEqual(report["craftedOutputItemCount"], 1)
            self.assertEqual(report["classifiedRecipeWithoutOutputCount"], 4)
            self.assertEqual(report["unresolvedRecipeWithoutOutputCount"], 1)
            by_recipe = {row["recipeId"]: row for row in report["recipeWithoutOutputRecords"]}
            self.assertEqual(by_recipe["101"]["reasonCode"], "OUT_OF_SCOPE_NON_EQUIPMENT_RECIPE")
            self.assertEqual(
                by_recipe["102"]["reasonCode"],
                "OFFICIAL_DB2_CRAFTING_DATA_HAS_NO_ITEM_OUTPUT",
            )
            self.assertEqual(
                by_recipe["103"]["reasonCode"],
                "OFFICIAL_DB2_RECIPE_OUTPUT_EDGE_UNRESOLVED",
            )
            self.assertEqual(by_recipe["104"]["reasonCode"], "OUT_OF_SCOPE_NON_EQUIPMENT_RECIPE")
            self.assertEqual(
                by_recipe["106"]["reasonCode"],
                "OFFICIAL_DB2_CREATE_ITEM_EFFECT_HAS_NO_OUTPUT_TARGET",
            )


if __name__ == "__main__":
    unittest.main()
