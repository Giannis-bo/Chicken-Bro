import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


class GearItemLevelStatProbeTest(unittest.TestCase):
    def item(self, index):
        item = {
            "itemId": f"25{index:04d}",
            "name": f"Item {index}",
            "slot": "head",
            "instanceId": "1305",
            "sourceType": "raid",
            "metadataPayload": {},
        }
        if index == 0:
            item["metadataPayload"] = {
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 5, "name": "Cosmetic"},
            }
            item["armorType"] = "cosmetic"
        return item

    def test_exact_11_by_4_report_passes_with_one_cosmetic_exclusion(self):
        from server.gear_item_level_stat_probe import build_probe_report

        items = [self.item(index) for index in range(12)]
        resolved_item_ids = []

        def resolver(item, item_level, _track):
            resolved_item_ids.append(item["itemId"])
            return {
                "itemStats": [
                    {"key": "stamina", "label": "Stamina", "value": item_level}
                ],
                "statSummary": f"Stamina {item_level}",
                "simcItemId": item["itemId"],
                "simcItemLevel": item_level,
                "simcProfile": "private profile must not enter the report",
            }

        report = build_probe_report(
            items,
            resolver=resolver,
            instance_id="1305",
            source_type="raid",
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["sourceItemCount"], 12)
        self.assertEqual(report["targetItemCount"], 11)
        self.assertEqual(report["excludedItemCount"], 1)
        self.assertEqual(
            report["excludedItems"],
            [
                {
                    "itemId": "250000",
                    "reasonCode": "NON_COMBAT_COSMETIC",
                    "status": "excluded",
                }
            ],
        )
        self.assertEqual(report["targetPairCount"], 44)
        self.assertEqual(report["exactPairCount"], 44)
        self.assertEqual(report["failedPairCount"], 0)
        self.assertEqual(report["problemCodes"], [])
        self.assertEqual(len(report["items"]), 11)
        self.assertNotIn("250000", resolved_item_ids)
        self.assertEqual(
            [row["itemLevel"] for row in report["items"][0]["levels"]],
            [263, 276, 289, 298],
        )
        self.assertNotIn("itemStats", str(report))
        self.assertNotIn("private profile", str(report))
        self.assertRegex(
            report["reportId"],
            r"^gear-item-level-stat-probe:sha256:[0-9a-f]{64}$",
        )

    def test_missing_or_mismatched_exact_stats_fail_with_bounded_codes_only(self):
        from server.gear_item_level_stat_probe import build_probe_report

        items = [self.item(index) for index in range(12)]

        def resolver(item, item_level, _track):
            if item["itemId"] == "250002" and item_level == 263:
                return {"error": "secret-bearing SimC output"}
            if item["itemId"] == "250001" and item_level == 276:
                return {
                    "itemStats": [{"key": "stamina", "value": 1}],
                    "simcItemId": "wrong-item",
                    "simcItemLevel": item_level,
                }
            return {
                "itemStats": [{"key": "stamina", "value": 1}],
                "simcItemId": item["itemId"],
                "simcItemLevel": item_level,
            }

        report = build_probe_report(
            items,
            resolver=resolver,
            instance_id="1305",
            source_type="raid",
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["exactPairCount"], 42)
        self.assertEqual(report["failedPairCount"], 2)
        self.assertEqual(
            report["problemCodes"],
            ["SIMC_ITEM_ID_MISMATCH", "SIMC_TARGET_STATS_MISSING"],
        )
        self.assertNotIn("secret-bearing", str(report))

    def test_wrong_source_shape_blocks_before_simc_execution(self):
        from server.gear_item_level_stat_probe import build_probe_report

        calls = []
        report = build_probe_report(
            [self.item(index) for index in range(11)],
            resolver=lambda *args: calls.append(args),
            instance_id="1305",
            source_type="raid",
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["problemCodes"], ["SOURCE_ITEM_COUNT_MISMATCH"])
        self.assertEqual(calls, [])

    def test_report_validation_is_bound_to_simc_identity(self):
        from server.gear_item_level_stat_probe import (
            build_probe_report,
            validate_probe_report,
        )

        report = build_probe_report(
            [self.item(index) for index in range(12)],
            resolver=lambda item, level, _track: {
                "itemStats": [{"key": "stamina", "value": 1}],
                "simcItemId": item["itemId"],
                "simcItemLevel": level,
            },
            instance_id="1305",
            source_type="raid",
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertTrue(
            validate_probe_report(
                report,
                instance_id="1305",
                simc_revision="a" * 40,
                simc_binary_sha256="b" * 64,
            )
        )
        self.assertFalse(
            validate_probe_report(
                report,
                instance_id="1305",
                simc_revision="c" * 40,
                simc_binary_sha256="b" * 64,
            )
        )

    def test_instance_loader_is_read_only_and_returns_probe_context(self):
        from server.gear_item_level_stat_probe import load_instance_items

        class Cursor:
            def __init__(self):
                self.statements = []
                self.params = []
                self.rows = [
                    (
                        "250001",
                        "Probe Helm",
                        "head",
                        "Epic",
                        {
                            "item_class": {"name": "Armor"},
                            "item_subclass": {"name": "Cloth"},
                        },
                    )
                ]

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement, params=()):
                self.statements.append(" ".join(statement.split()))
                self.params.append(tuple(params))

            def fetchall(self):
                return list(self.rows)

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()
        rows = load_instance_items(connection, "1305", "raid")
        sql = "\n".join(connection.cursor_instance.statements)

        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertIn("FROM cache.websim_gear_sources", sql)
        self.assertIn("JOIN cache.websim_loot", sql)
        self.assertNotRegex(sql, r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b")
        self.assertEqual(connection.cursor_instance.params[-1], ("1305", "raid"))
        self.assertEqual(rows[0]["itemId"], "250001")
        self.assertEqual(rows[0]["slot"], "head")
        self.assertEqual(rows[0]["armorType"], "cloth")

    def test_cli_writes_one_immutable_sanitized_report(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "gear-item-level-stat-probe.py"
        )
        spec = importlib.util.spec_from_file_location(
            "gear_item_level_stat_probe_cli",
            script,
        )
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, _statement, _params=()):
                return None

        class Connection:
            def __init__(self):
                self.readonly = False
                self.rolled_back = False
                self.closed = False

            def set_session(self, *, readonly, autocommit):
                self.readonly = readonly is True and autocommit is False

            def cursor(self):
                return Cursor()

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        connection = Connection()
        items = [self.item(index) for index in range(12)]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = module.main(
                    ["--output", "artifacts/probe.json"],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
                    },
                    repo_root=root,
                    connection_factory=lambda: connection,
                    simc_identity_fn=lambda *_args: ("a" * 40, "b" * 64),
                    item_loader=lambda *_args: items,
                    resolver=lambda item, level, _track: {
                        "itemStats": [{"key": "stamina", "value": 1}],
                        "simcItemId": item["itemId"],
                        "simcItemLevel": level,
                    },
                )

            report = json.loads(
                (root / "artifacts" / "probe.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status, 0)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(json.loads(stdout.getvalue())["reportId"], report["reportId"])
            self.assertTrue(connection.readonly)
            self.assertTrue(connection.rolled_back)
            self.assertTrue(connection.closed)
            with self.assertRaisesRegex(Exception, "already exists"):
                module.main(
                    ["--output", "artifacts/probe.json"],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
                    },
                    repo_root=root,
                    connection_factory=lambda: Connection(),
                    simc_identity_fn=lambda *_args: ("a" * 40, "b" * 64),
                    item_loader=lambda *_args: items,
                    resolver=lambda *_args: {},
                )

    def test_pg_profile_loader_and_probe_profile_use_exact_cache_source(self):
        from server.gear_item_level_stat_probe import (
            build_item_level_probe_profile,
            load_profile_presets,
        )

        class Cursor:
            def __init__(self):
                self.statements = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement):
                self.statements.append(" ".join(statement.split()))

            def fetchall(self):
                return [
                    (
                        "mage",
                        "frost",
                        "Frost",
                        'mage="Frost"\nspec=frost\nhead=old,id=1\njson=old.json\n',
                    )
                ]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()

            def cursor(self):
                return self.cursor_instance

        connection = Connection()
        profiles = load_profile_presets(connection)
        profile, class_key, spec_key, item_line = build_item_level_probe_profile(
            {
                **self.item(1),
                "name": "Probe Helm",
                "slot": "head",
                "armorType": "cloth",
            },
            263,
            {"difficultyKey": "champion", "itemLevel": 263},
            profiles,
        )
        sql = "\n".join(connection.cursor_instance.statements)

        self.assertIn("FROM cache.websim_profile_presets", sql)
        self.assertNotIn("head=old,id=1", profile)
        self.assertNotIn("json=old.json", profile)
        self.assertIn("iterations=1", profile)
        self.assertIn("head=probe_helm,id=250001,ilevel=263", profile)
        self.assertNotIn("bonus_id=", profile)
        self.assertEqual(item_line, "head=probe_helm,id=250001,ilevel=263")
        self.assertEqual((class_key, spec_key), ("mage", "frost"))

    def test_exact_resolver_reads_target_stats_from_simc_json(self):
        from server.gear_item_level_stat_probe import resolve_item_level_stat

        observed_profiles = []
        result = resolve_item_level_stat(
            {
                **self.item(1),
                "name": "Probe Helm",
                "slot": "head",
                "armorType": "cloth",
            },
            276,
            {"difficultyKey": "hero", "itemLevel": 276, "bonusId": "999"},
            [
                (
                    "mage",
                    "frost",
                    "Frost",
                    'mage="Frost"\nspec=frost\nhead=old,id=1\n',
                )
            ],
            run_simc=lambda profile: (
                observed_profiles.append(profile)
                or {
                    "ok": True,
                    "checkedAt": "2026-07-28T12:00:00Z",
                    "durationMs": 42,
                    "payload": {
                        "sim": {
                            "players": [
                                {
                                    "gear": {
                                        "head": {
                                            "id": "250001",
                                            "ilevel": 276,
                                            "stats": {
                                                "intellect": 100,
                                                "stamina": 200,
                                                "haste_rating": 50,
                                            },
                                        }
                                    }
                                }
                            ]
                        }
                    },
                }
            ),
        )

        self.assertEqual(len(observed_profiles), 1)
        self.assertIn("head=probe_helm,id=250001,ilevel=276", observed_profiles[0])
        self.assertNotIn("bonus_id=", observed_profiles[0])
        self.assertEqual(result["statSource"], "simulationcraft")
        self.assertEqual(result["simcItemId"], "250001")
        self.assertEqual(result["simcItemLevel"], 276)
        self.assertEqual(result["probeClassKey"], "mage")
        self.assertEqual(result["probeSpecKey"], "frost")
        self.assertEqual(result["simcDurationMs"], 42)
        self.assertEqual(
            [stat["key"] for stat in result["itemStats"]],
            ["intellect", "stamina", "haste_rating"],
        )


if __name__ == "__main__":
    unittest.main()
