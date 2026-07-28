import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


class GearItemLevelStatBackfillTest(unittest.TestCase):
    @staticmethod
    def report():
        items = []
        for index in range(11):
            item_id = f"268{282 + index}"
            items.append(
                {
                    "itemId": item_id,
                    "levels": [
                        {"itemLevel": level, "status": "exact"}
                        for level in (263, 276, 289, 298)
                    ],
                }
            )
        report = {
            "schemaRevision": "gear-item-level-stat-probe-v2",
            "status": "pass",
            "instanceId": "1305",
            "sourceType": "raid",
            "simcRuntime": {
                "revision": "a" * 40,
                "binarySha256": "b" * 64,
            },
            "sourceItemCount": 12,
            "targetItemCount": 11,
            "excludedItemCount": 1,
            "excludedItems": [
                {
                    "itemId": "268280",
                    "reasonCode": "NON_COMBAT_COSMETIC",
                    "status": "excluded",
                }
            ],
            "targetPairCount": 44,
            "exactPairCount": 44,
            "failedPairCount": 0,
            "items": items,
            "problemCodes": [],
        }
        report["reportId"] = "gear-item-level-stat-probe:sha256:" + hashlib.sha256(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return report

    @staticmethod
    def original_rows(pairs):
        return [
            {
                "id": f"variant-{item_id}-{item_level}",
                "itemId": item_id,
                "itemLevel": item_level,
                "readiness": "partial",
                "status": "partial",
                "blockers": ["SimC JSON did not include target item stats"],
                "payload": {
                    "derivedVariantSource": "simulationcraft_item_level_probe",
                    "error": "SimC JSON did not include target item stats",
                },
                "updatedAt": f"before-{item_id}-{item_level}",
            }
            for item_id, item_level in pairs
        ]

    @staticmethod
    def resolved(pairs):
        return {
            (item_id, item_level): {
                "statSource": "simulationcraft",
                "statSourceDetail": "SimulationCraft JSON gear output",
                "statDisplayStatus": "verified_variant",
                "itemStats": [
                    {"key": "stamina", "label": "Stamina", "value": item_level}
                ],
                "statSummary": f"Stamina {item_level}",
                "simcItemId": item_id,
                "simcItemLevel": item_level,
                "simcProfile": "must-not-persist",
                "probeClassKey": "mage",
                "probeSpecKey": "frost",
            }
            for item_id, item_level in pairs
        }

    def test_target_contract_is_exact_44_plus_one_cosmetic_exclusion(self):
        from server.gear_item_level_stat_backfill import target_pairs

        pairs = target_pairs(
            self.report(),
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertEqual(len(pairs), 44)
        self.assertNotIn(("268280", 263), pairs)
        self.assertEqual(pairs[0][1], 263)
        self.assertEqual(pairs[-1][1], 298)

        blocked = self.report()
        blocked["excludedItems"][0]["reasonCode"] = "UNKNOWN"
        with self.assertRaisesRegex(Exception, "probe report"):
            target_pairs(
                blocked,
                simc_revision="a" * 40,
                simc_binary_sha256="b" * 64,
            )

    def test_prepare_updates_requires_all_rows_and_persists_only_exact_stats(self):
        from server.gear_item_level_stat_backfill import prepare_variant_updates

        pairs = [
            (row["itemId"], level)
            for row in self.report()["items"]
            for level in (263, 276, 289, 298)
        ]
        updates = prepare_variant_updates(
            self.original_rows(pairs),
            self.resolved(pairs),
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
        )

        self.assertEqual(len(updates), 44)
        first = updates[0]
        self.assertEqual(first["readiness"], "verified")
        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["blockers"], [])
        self.assertEqual(first["payload"]["statDisplayStatus"], "verified_variant")
        self.assertEqual(first["payload"]["simcRuntimeRevision"], "a" * 40)
        self.assertNotIn("error", first["payload"])
        self.assertNotIn("simcProfile", first["payload"])

        with self.assertRaisesRegex(Exception, "44 exact staging rows"):
            prepare_variant_updates(
                self.original_rows(pairs)[:-1],
                self.resolved(pairs),
                simc_revision="a" * 40,
                simc_binary_sha256="b" * 64,
            )

    def test_backfill_backs_up_before_updates_and_rolls_back_on_pointer_drift(self):
        from server.gear_item_level_stat_backfill import backfill_exact_rows

        report = self.report()
        pairs = [
            (row["itemId"], level)
            for row in report["items"]
            for level in (263, 276, 289, 298)
        ]
        original_rows = self.original_rows(pairs)
        events = []

        class Connection:
            def __init__(self):
                self.committed = False
                self.rolled_back = False

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

        connection = Connection()
        pointer = {
            "generation": 24,
            "manifestRevision": "manifest-active",
            "pointerMode": "active",
            "rollbackManifestRevision": "manifest-rollback",
        }
        result = backfill_exact_rows(
            connection,
            report=report,
            resolved_by_pair=self.resolved(pairs),
            simc_revision="a" * 40,
            simc_binary_sha256="b" * 64,
            transaction_starter=lambda _connection: events.append(("begin",)),
            pointer_reader=lambda _connection: dict(pointer),
            row_loader=lambda _connection, _pairs: list(original_rows),
            backup_writer=lambda rows, observed_pointer: (
                events.append(("backup", len(rows), observed_pointer["generation"]))
                or {"path": "backup.json", "sha256": "d" * 64}
            ),
            row_updater=lambda _connection, update: events.append(
                ("update", update["id"])
            ),
            row_verifier=lambda _connection, _pairs: set(pairs),
        )

        self.assertEqual(events[0], ("begin",))
        self.assertEqual(events[1], ("backup", 44, 24))
        self.assertEqual(len([event for event in events if event[0] == "update"]), 44)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertEqual(result["updatedVariantCount"], 44)

        drifting_connection = Connection()
        pointer_reads = iter(
            [
                pointer,
                {**pointer, "generation": 25},
            ]
        )
        with self.assertRaisesRegex(Exception, "pointer changed"):
            backfill_exact_rows(
                drifting_connection,
                report=report,
                resolved_by_pair=self.resolved(pairs),
                simc_revision="a" * 40,
                simc_binary_sha256="b" * 64,
                transaction_starter=lambda _connection: None,
                pointer_reader=lambda _connection: next(pointer_reads),
                row_loader=lambda _connection, _pairs: list(original_rows),
                backup_writer=lambda *_args: {
                    "path": "backup.json",
                    "sha256": "d" * 64,
                },
                row_updater=lambda *_args: None,
                row_verifier=lambda _connection, _pairs: set(pairs),
            )
        self.assertFalse(drifting_connection.committed)
        self.assertTrue(drifting_connection.rolled_back)

    def test_cli_binds_probe_identity_and_writes_backup_before_result(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "gear-item-level-stat-backfill.py"
        )
        spec = importlib.util.spec_from_file_location(
            "gear_item_level_stat_backfill_cli",
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

            def execute(self, *_args, **_kwargs):
                return None

        class Connection:
            def __init__(self):
                self.readonly = False
                self.closed = False
                self.rolled_back = False

            def set_session(self, *, readonly, autocommit):
                self.readonly = readonly is True and autocommit is False

            def cursor(self):
                return Cursor()

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        report = self.report()
        read_connection = Connection()
        write_connection = Connection()
        items = [
            {
                "itemId": row["itemId"],
                "slot": "head",
                "armorType": "cloth",
            }
            for row in report["items"]
        ]
        items.append(
            {
                "itemId": "268280",
                "slot": "head",
                "armorType": "cosmetic",
            }
        )

        def fake_backfill(_connection, **kwargs):
            pairs = sorted(kwargs["resolved_by_pair"])
            backup = kwargs["backup_writer"](
                self.original_rows(pairs),
                {
                    "generation": 24,
                    "manifestRevision": "manifest-active",
                    "pointerMode": "active",
                    "rollbackManifestRevision": "manifest-rollback",
                },
            )
            return {
                "schemaRevision": "gear-item-level-stat-backfill-v1",
                "status": "pass",
                "updatedVariantCount": 44,
                "targetItemCount": 11,
                "excludedItemCount": 1,
                "pointerBefore": {"generation": 24},
                "pointerAfter": {"generation": 24},
                "backup": backup,
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probe_path = root / "probe.json"
            probe_path.write_text(
                json.dumps(report, ensure_ascii=False),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = module.main(
                    [
                        "--probe-report",
                        "probe.json",
                        "--backup-output",
                        "artifacts/backup.json",
                        "--output",
                        "artifacts/result.json",
                    ],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
                    },
                    repo_root=root,
                    read_connection_factory=lambda: read_connection,
                    write_connection_factory=lambda: write_connection,
                    simc_identity_fn=lambda *_args: ("a" * 40, "b" * 64),
                    item_loader=lambda *_args: items,
                    profile_loader=lambda *_args: [],
                    resolver=lambda item, level, _track, _profiles: {
                        "itemStats": [{"key": "stamina", "value": level}],
                        "simcItemId": item["itemId"],
                        "simcItemLevel": level,
                    },
                    backfill_runner=fake_backfill,
                )

            result = json.loads(
                (root / "artifacts" / "result.json").read_text(encoding="utf-8")
            )
            backup = json.loads(
                (root / "artifacts" / "backup.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status, 0)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["updatedVariantCount"], 44)
            self.assertEqual(len(backup["rows"]), 44)
            self.assertEqual(
                backup["sourceProbeReportId"],
                report["reportId"],
            )
            self.assertTrue(read_connection.readonly)
            self.assertTrue(read_connection.rolled_back)
            self.assertTrue(read_connection.closed)
            self.assertTrue(write_connection.closed)
            self.assertEqual(
                json.loads(stdout.getvalue())["reportId"],
                result["reportId"],
            )


if __name__ == "__main__":
    unittest.main()
