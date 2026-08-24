import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "capture-s2-limited-db2.py"
ALLOWLIST = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "db2-field-allowlist-v1.json"
)


class S2LimitedDb2CaptureCliTest(unittest.TestCase):
    def test_dry_run_derives_bounded_query_plan_without_network_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [
                            {"path": "/data/wow/item/237842"},
                            {"path": "/data/wow/recipe/52446"},
                            {"path": "/data/wow/mythic-keystone/season/18"},
                            {"path": "/data/wow/mythic-keystone/period/1076"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["status"], "dry_run")
        self.assertEqual(output["targets"]["itemIds"], ["237842"])
        self.assertEqual(output["targets"]["recipeIds"], ["52446"])
        self.assertEqual(output["targets"]["mythicPlusSeasonIds"], ["18"])
        self.assertGreater(output["initialRequestCount"], 0)
        self.assertEqual(output["networkCalls"], 0)

    def test_dry_run_can_capture_only_official_journal_encounter_items(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [
                            {"path": "/data/wow/journal-encounter/2172"},
                            {"path": "/data/wow/journal-encounter/2849"},
                            {"path": "/data/wow/item/158344"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-journal-encounter",
                    "--journal-encounter-id",
                    "2172",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["journalEncounterIds"], ["2172"])
        self.assertEqual(
            {(row["table"], row["targetValue"]) for row in output["requests"]},
            {("JournalEncounterItem", "2172")},
        )

    def test_live_requires_an_isolated_output_root(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--live",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--live requires --output-root", completed.stderr)

    def test_dry_run_can_restrict_to_verified_official_api_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [
                            {"path": "/data/wow/item/159317"},
                            {"path": "/data/wow/item/271481"},
                            {"path": "/data/wow/recipe/52446"},
                            {"path": "/data/wow/mythic-keystone/season/18"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--item-id",
                    "159317",
                    "--item-id",
                    "271481",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemIds"], ["159317", "271481"])
        self.assertEqual(output["targets"]["recipeIds"], [])
        self.assertEqual(output["targets"]["mythicPlusSeasonIds"], [])

    def test_dry_run_accepts_explicit_bounded_scaling_config_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [{"path": "/data/wow/item/271472"}],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--item-scaling-config-id",
                    "302",
                    "--item-scaling-config-id",
                    "302",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemScalingConfigIds"], ["302"])
        self.assertEqual(
            [
                row
                for row in output["requests"]
                if row["table"] == "ItemScalingConfig"
            ],
            [
                {
                    "filterField": "ID",
                    "operator": "exact",
                    "table": "ItemScalingConfig",
                    "targetKind": "allowlisted_foreign_key",
                    "targetValue": "302",
                }
            ],
        )

    def test_dry_run_can_capture_only_explicit_scaling_config_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [{"path": "/data/wow/item/271472"}],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-item-scaling-config",
                    "--item-scaling-config-id",
                    "302",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemIds"], [])
        self.assertEqual(output["targets"]["itemScalingConfigIds"], ["302"])
        self.assertEqual(len(output["requests"]), 1)

    def test_dry_run_can_capture_only_explicit_enchant_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-enchant",
                    "--enchant-id",
                    "8013",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["enchantIds"], ["8013"])
        self.assertEqual(
            output["requests"],
            [
                {
                    "filterField": "ID",
                    "operator": "exact",
                    "table": "SpellItemEnchantment",
                    "targetKind": "explicit_enchant_id",
                    "targetValue": "8013",
                }
            ],
        )

    def test_dry_run_can_capture_only_explicit_crafting_option_spells(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-spell",
                    "--spell-id",
                    "1246308",
                    "--spell-id",
                    "1246309",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["spellIds"], ["1246308", "1246309"])
        self.assertEqual(
            [
                (row["table"], row["filterField"], row["targetValue"])
                for row in output["requests"]
            ],
            [
                ("Spell", "ID", "1246308"),
                ("Spell", "ID", "1246309"),
                ("SpellEffect", "SpellID", "1246308"),
                ("SpellEffect", "SpellID", "1246309"),
            ],
        )

    def test_dry_run_can_capture_only_explicit_crafting_data_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-crafting-data",
                    "--crafting-data-id",
                    "2556",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["craftingDataIds"], ["2556"])
        self.assertEqual(
            [
                (row["table"], row["filterField"], row["targetValue"])
                for row in output["requests"]
            ],
            [
                ("CraftingData", "ID", "2556"),
                ("CraftingDataItemQuality", "CraftingDataID", "2556"),
            ],
        )

    def test_dry_run_can_capture_only_explicit_bonus_list_group_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-item-bonus-list-group",
                    "--item-bonus-list-group-id",
                    "614",
                    "--item-bonus-list-group-id",
                    "614",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemBonusListGroupIds"], ["614"])
        self.assertEqual(output["targets"]["itemIds"], [])
        self.assertEqual(
            [
                row
                for row in output["requests"]
                if row["table"] == "ItemBonusListGroup"
            ],
            [
                {
                    "filterField": "ID",
                    "operator": "exact",
                    "table": "ItemBonusListGroup",
                    "targetKind": "allowlisted_foreign_key",
                    "targetValue": "614",
                }
            ],
        )

    def test_dry_run_can_capture_only_explicit_bonus_tree_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-item-bonus-tree",
                    "--item-bonus-tree-id",
                    "5997",
                    "--item-bonus-tree-id",
                    "5997",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemBonusTreeIds"], ["5997"])
        self.assertEqual(output["targets"]["itemIds"], [])
        self.assertEqual(
            [
                row
                for row in output["requests"]
                if row["table"] == "ItemBonusTree"
            ],
            [
                {
                    "filterField": "ID",
                    "operator": "exact",
                    "table": "ItemBonusTree",
                    "targetKind": "allowlisted_foreign_key",
                    "targetValue": "5997",
                }
            ],
        )

    def test_dry_run_can_capture_only_explicit_item_creation_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-item-creation-context",
                    "--item-context",
                    "16",
                    "--item-context",
                    "33",
                    "--item-context",
                    "35",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["targets"]["itemContextValues"], ["16", "33", "35"])
        self.assertEqual(
            [
                row
                for row in output["requests"]
                if row["table"] == "ItemCreationContext"
            ],
            [
                {
                    "filterField": "ItemContext",
                    "operator": "exact",
                    "table": "ItemCreationContext",
                    "targetKind": "explicit_item_creation_context",
                    "targetValue": value,
                }
                for value in ("16", "33", "35")
            ],
        )

    def test_dry_run_can_capture_only_explicit_modified_reagent_items(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps({"status": "captured", "entries": []}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--only-modified-crafting-reagent-item",
                    "--modified-crafting-reagent-item-id",
                    "594",
                    "--modified-crafting-reagent-item-id",
                    "594",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(
            output["targets"]["modifiedCraftingReagentItemIds"], ["594"]
        )
        self.assertEqual(
            [
                row
                for row in output["requests"]
                if row["table"] == "ModifiedCraftingReagentItem"
            ],
            [
                {
                    "filterField": "ID",
                    "operator": "exact",
                    "table": "ModifiedCraftingReagentItem",
                    "targetKind": "allowlisted_foreign_key",
                    "targetValue": "594",
                }
            ],
        )

    def test_target_restriction_rejects_root_not_in_official_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "capture-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "captured",
                        "entries": [{"path": "/data/wow/item/159317"}],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--official-capture-manifest",
                    str(manifest_path),
                    "--allowlist",
                    str(ALLOWLIST),
                    "--item-id",
                    "271481",
                    "--dry-run-request-plan",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("not present in official capture", completed.stderr)


if __name__ == "__main__":
    unittest.main()
