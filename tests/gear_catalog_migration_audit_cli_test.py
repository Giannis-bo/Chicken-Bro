import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gear-catalog-migration-audit.py"
SPEC = importlib.util.spec_from_file_location(
    "gear_catalog_migration_audit_cli",
    SCRIPT,
)
audit_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit_cli)


MANIFEST_REVISION = "season-manifest:sha256:" + ("1" * 64)
GEAR_RELEASE_ID = "gear-release:sha256:" + ("2" * 64)
COMMUNITY_RELEASE_ID = "community-release:sha256:" + ("3" * 64)


def caller_report():
    return {
        "schemaRevision": "gear-catalog-callers-v2",
        "reportId": "gear-catalog-callers:sha256:" + ("4" * 64),
        "status": "verified",
        "runtimeCallerCount": 167,
        "unresolvedCount": 0,
        "categories": {
            "activeBackend": [{"path": "server/news_backend.py"}],
            "taro": [{"path": "apps/mini-taro/src/api.ts"}],
            "compatibility": [{"path": "pages/builds/websim-api.js"}],
            "runtimeTooling": [{"path": "scripts/perf_probe.py"}],
            "testsDocs": [{"path": "tests/example.test.js"}],
            "unresolved": [],
        },
    }


def audit_snapshot():
    pointer = {
        "generation": 17,
        "manifestRevision": MANIFEST_REVISION,
        "pointerMode": "active",
        "rollbackManifestRevision": "season-manifest:sha256:" + ("0" * 64),
    }
    return {
        "pointerBefore": pointer,
        "pointerAfter": dict(pointer),
        "activeBinding": {
            "manifest": {
                "manifestRevision": MANIFEST_REVISION,
                "seasonRevision": "season-17-f131dd36ddf1",
                "dependencyVector": {
                    "gearRuleRevision": "gear-rule-matrix-v1",
                    "seasonRevision": "season-17-f131dd36ddf1",
                    "simcRuntimeRevision": "simc-r1",
                },
            },
            "gearRelease": {"releaseId": GEAR_RELEASE_ID},
            "communityRelease": {"releaseId": COMMUNITY_RELEASE_ID},
        },
        "catalogRows": {
            "items": [
                {
                    "itemId": "1001",
                    "slot": "head",
                    "payload": {"sourceStatus": "verified"},
                }
            ],
            "variants": [
                {
                    "variantId": "hero-6",
                    "itemId": "1001",
                    "rowFamily": "browse",
                    "trackKey": "hero",
                    "trackRank": 0,
                    "rank": 527,
                    "itemLevel": 276,
                    "slot": "head",
                    "sourceType": "raid",
                    "bonusIds": ["9001", "9002"],
                    "staticStats": {"haste_rating": 120},
                }
            ],
            "options": [
                {
                    "optionId": "gem-1",
                    "optionKey": "gem:240892",
                    "optionType": "gem",
                    "status": "verified",
                }
            ],
        },
        "communityTemplates": [
            {
                "templateIdentity": "sha256:" + ("5" * 64),
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": "1001",
                        "bonusIds": ["9001", "9002"],
                        "trackKey": "hero",
                        "rank": 3,
                        "ilevel": 278,
                        "gemIds": [],
                        "enchantId": "",
                        "craftedStats": [],
                        "embellishmentIds": [],
                    }
                ],
            }
        ],
        "personalGearTemplates": [],
        "relationSizes": [
            {
                "relation": "cache.websim_release_registry",
                "totalBytes": 4096,
                "activeLogicalBytes": 1024,
                "rollbackLogicalBytes": 512,
            }
        ],
        "releaseEvents": [
            {
                "eventType": "refresh_no_change",
                "count": 2,
                "latestAt": "2026-07-28T09:00:00+08:00",
            }
        ],
        "queryMetrics": {"total": 12, "reads": 9, "writes": 0},
    }


def resource_report(
    *,
    gear_release_id=GEAR_RELEASE_ID,
    simc_runtime_revision="simc-r1",
    peak_rss=1_500_000_000,
):
    from server.gear_release_resource_probe import build_resource_report

    pointer = {
        "environment": "retail",
        "pointerMode": "active",
        "manifestRevision": MANIFEST_REVISION,
        "generation": 17,
        "rollbackManifestRevision": "season-manifest:sha256:" + ("0" * 64),
    }
    return build_resource_report(
        gear_release_id=gear_release_id,
        season_revision="season-17-f131dd36ddf1",
        simc_runtime_revision=simc_runtime_revision,
        builder_revision="community-release-prepared-index-v1",
        pointer_before=pointer,
        pointer_after=pointer,
        metrics={
            "elapsedMilliseconds": 1_500,
            "peakRssObservedBytes": peak_rss,
            "temporaryBytesObserved": 128,
            "writeStatementCount": 0,
        },
        limits={
            "elapsedMilliseconds": 300_000,
            "peakRssObservedBytes": 2_000_000_000,
            "temporaryBytesObserved": 268_435_456,
        },
        prepared={
            "communityReleaseStatus": "validated",
            "communityContentHash": "sha256:" + ("8" * 64),
            "stagingTemplateCount": 3253,
            "winnerSpecCount": 40,
            "winnerHeroSlotCount": 80,
        },
    )


def class_matrix():
    return [
        {
            "key": f"class-{class_index}",
            "specs": [
                f"spec-{class_index}-{spec_index}"
                for spec_index in range(4)
            ],
        }
        for class_index in range(10)
    ]


def spec_payload(class_key, spec_key, *, changed=False):
    return {
        "classKey": class_key,
        "specKey": spec_key,
        "catalogStatus": "verified",
        "catalogBlockers": [],
        "replacementCandidates": [
            {"slot": "head", "items": [{"itemId": "1001"}]},
        ],
        "manifestRevision": MANIFEST_REVISION,
        "pointerGeneration": 18 if changed else 17,
    }


class FakeStatvfs:
    f_blocks = 1000
    f_bavail = 400
    f_frsize = 4096


def write_callers(root):
    path = root / "artifacts" / "caller-inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(caller_report(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


class FakeCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.statements.append(" ".join(str(sql).split()))


class FakeConnection:
    def __init__(self):
        self.read_only = False
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class GearCatalogMigrationAuditCliTest(unittest.TestCase):
    def test_compact_slot_payloads_count_as_specialization_candidates(self):
        payload = {
            "replacementCandidates": [
                {
                    "slot": "head",
                    "fullItemCount": 2,
                    "items": [],
                },
                {
                    "slot": "neck",
                    "fullItemCount": 1,
                    "items": [],
                },
            ],
            "slots": [
                {"slot": "head"},
                {"slot": "neck"},
            ],
        }

        self.assertEqual(audit_cli._candidate_count(payload), 3)

    def test_resource_rows_consume_only_an_exact_validated_probe_binding(self):
        exact = audit_cli._resource_rows(
            audit_snapshot(),
            caller_bytes=64,
            filesystem_roots=[],
            statvfs_fn=lambda _path: FakeStatvfs(),
            resource_report=resource_report(),
        )
        mismatch = audit_cli._resource_rows(
            audit_snapshot(),
            caller_bytes=64,
            filesystem_roots=[],
            statvfs_fn=lambda _path: FakeStatvfs(),
            resource_report=resource_report(gear_release_id="gear-release:other"),
        )

        self.assertEqual(exact["peakRssObservedBytes"], 1_500_000_000)
        self.assertEqual(exact["temporaryBytesObserved"], 128)
        self.assertEqual(exact["resourceProbeStatus"], "pass")
        self.assertIsNone(mismatch["peakRssObservedBytes"])
        self.assertIsNone(mismatch["temporaryBytesObserved"])
        self.assertEqual(mismatch["resourceProbeStatus"], "mismatched")

    def test_missing_pg_only_runtime_exits_before_connecting(self):
        called = []
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            status = audit_cli.main(
                ["--callers-json", "missing.json", "--output", "output.json"],
                environ={},
                repo_root=ROOT,
                run_audit_fn=lambda **kwargs: called.append(kwargs),
            )

        self.assertNotEqual(status, 0)
        self.assertEqual(called, [])
        self.assertIn("postgres_only", stderr.getvalue())

    def test_output_must_stay_in_repository_and_cannot_replace_control_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers = write_callers(root)
            environment = {
                "WOW_DATABASE_RUNTIME": "postgres_only",
                "WOW_DATABASE_URL": "postgresql://audit.invalid/wow",
            }
            for output in (
                "../outside.json",
                "artifacts/releases/phase0/requirement.json",
                "artifacts/releases/phase0/evidence.json",
                "artifacts/releases/phase0/manifest.json",
            ):
                with self.subTest(output=output):
                    called = []
                    status = audit_cli.main(
                        [
                            "--callers-json",
                            str(callers.relative_to(root)),
                            "--output",
                            output,
                        ],
                        environ=environment,
                        repo_root=root,
                        run_audit_fn=lambda **kwargs: called.append(kwargs),
                    )
                    self.assertNotEqual(status, 0)
                    self.assertEqual(called, [])

    def test_caller_input_and_result_have_hard_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers = root / "callers.json"
            callers.write_bytes(b" " * (audit_cli.MAX_CALLER_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                audit_cli.load_caller_report(root, callers)

            output = root / "output.json"
            with self.assertRaisesRegex(ValueError, "8 MiB"):
                audit_cli.atomic_write_json(
                    output,
                    {"payload": "x" * audit_cli.MAX_REPORT_BYTES},
                    repo_root=root,
                )
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".output.json.*.tmp")), [])

    def test_temporary_output_is_removed_on_replace_error_and_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output.json"
            with self.assertRaisesRegex(OSError, "replace failed"):
                audit_cli.atomic_write_json(
                    output,
                    {"status": "partial"},
                    repo_root=root,
                    replace_fn=lambda source, target: (_ for _ in ()).throw(
                        OSError("replace failed")
                    ),
                )
            self.assertEqual(list(root.glob(".output.json.*.tmp")), [])

            signal_temp = root / ".signal.tmp"
            signal_temp.write_text("partial", encoding="utf-8")
            audit_cli._ACTIVE_TEMP_PATHS.add(signal_temp)
            with self.assertRaises(SystemExit):
                audit_cli._cleanup_on_signal(signal.SIGTERM, None)
            self.assertFalse(signal_temp.exists())

    def test_fixed_limits_are_bounded(self):
        for arguments in (
            ["--statement-timeout-ms", "30001"],
            ["--batch-size", "1001"],
            ["--sample-limit", "21"],
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit):
                    audit_cli.parse_args([
                        "--callers-json",
                        "callers.json",
                        "--output",
                        "output.json",
                        *arguments,
                    ])

    def test_read_only_wrapper_sets_session_mode_rejects_writes_and_caps_reads(self):
        connection = FakeConnection()
        metrics = audit_cli.ReadOnlyQueryMetrics(max_reads=1)
        wrapped = audit_cli.read_only_connection_factory(
            lambda: connection,
            metrics,
        )()

        self.assertTrue(connection.read_only)
        with wrapped.cursor() as cursor:
            cursor.execute("SELECT 1")
            with self.assertRaisesRegex(RuntimeError, "write statement"):
                cursor.execute("UPDATE cache.table SET value = 1")
            with self.assertRaisesRegex(RuntimeError, "query budget"):
                cursor.execute("SELECT 2")
        self.assertEqual(metrics.reads, 2)
        self.assertEqual(metrics.writes, 1)

    def test_unchanged_pointer_produces_stable_aggregate_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers_path = write_callers(root)
            loaded_callers, caller_bytes = audit_cli.load_caller_report(
                root,
                callers_path,
            )

            keyword_arguments = {
                "caller_report": loaded_callers,
                "caller_bytes": caller_bytes,
                "snapshot_reader": lambda **kwargs: audit_snapshot(),
                "spec_payload_reader": (
                    lambda class_key, spec_key: spec_payload(class_key, spec_key)
                ),
                "class_spec_matrix": class_matrix(),
                "filesystem_roots": [root],
                "statvfs_fn": lambda path: FakeStatvfs(),
            }
            first = audit_cli.run_audit(
                observed_at="2026-07-28T10:00:00+08:00",
                **keyword_arguments,
            )
            second = audit_cli.run_audit(
                observed_at="2026-07-28T11:00:00+08:00",
                **keyword_arguments,
            )

        self.assertEqual(first["reportId"], second["reportId"])
        self.assertEqual(first["specCoverage"]["specTotal"], 40)
        self.assertEqual(first["specCoverage"]["verifiedSpecCount"], 40)
        self.assertNotIn("replacementCandidates", json.dumps(first))
        runtime_identity = first["catalogMapping"]["runtimeSnapshotIdentity"]
        self.assertEqual(runtime_identity["pointerBefore"]["generation"], 17)
        self.assertEqual(
            runtime_identity["communityReleaseId"],
            COMMUNITY_RELEASE_ID,
        )
        self.assertRegex(
            runtime_identity["dependencyVectorHash"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertTrue(runtime_identity["pointerStable"])
        self.assertRegex(
            runtime_identity["releaseEventsHash"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            runtime_identity["trackAuthorityRuleRevision"],
            "midnight-season-1-track-authority-v1",
        )
        self.assertEqual(runtime_identity["trackAuthorityStatus"], "verified")
        self.assertEqual(
            first["catalogMapping"]["trackAuthority"]["seasonRevision"],
            "season-17-f131dd36ddf1",
        )
        self.assertEqual(first["catalogMapping"]["status"], "verified")
        self.assertEqual(
            first["resources"]["temporaryBytes"]["status"],
            "unknown",
        )

    def test_wrong_gear_rule_revision_remains_explicitly_blocked(self):
        snapshot = audit_snapshot()
        snapshot["activeBinding"]["manifest"]["dependencyVector"][
            "gearRuleRevision"
        ] = "gear-rule-matrix-unknown"

        report = audit_cli.run_audit(
            caller_report=caller_report(),
            caller_bytes=1024,
            snapshot_reader=lambda **kwargs: snapshot,
            spec_payload_reader=(
                lambda class_key, spec_key: spec_payload(class_key, spec_key)
            ),
            class_spec_matrix=class_matrix(),
            filesystem_roots=[ROOT],
            statvfs_fn=lambda path: FakeStatvfs(),
            observed_at="2026-07-28T10:00:00+08:00",
        )

        self.assertEqual(report["catalogMapping"]["status"], "blocked")
        self.assertEqual(
            report["catalogMapping"]["trackAuthority"]["status"],
            "blocked",
        )
        self.assertEqual(
            report["catalogMapping"]["runtimeSnapshotIdentity"][
                "trackAuthorityStatus"
            ],
            "blocked",
        )

    def test_success_prints_the_written_report_identity_and_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers_path = write_callers(root)
            loaded_callers, caller_bytes = audit_cli.load_caller_report(
                root,
                callers_path,
            )
            report = audit_cli.run_audit(
                caller_report=loaded_callers,
                caller_bytes=caller_bytes,
                snapshot_reader=lambda **kwargs: audit_snapshot(),
                spec_payload_reader=(
                    lambda class_key, spec_key: spec_payload(class_key, spec_key)
                ),
                class_spec_matrix=class_matrix(),
                filesystem_roots=[root],
                statvfs_fn=lambda path: FakeStatvfs(),
                observed_at="2026-07-28T10:00:00+08:00",
            )
            output = root / "artifacts" / "runtime-readonly-audit.json"
            resource_path = root / "artifacts" / "resource-probe.json"
            exact_resource_report = resource_report()
            resource_path.write_text(
                json.dumps(exact_resource_report),
                encoding="utf-8",
            )
            captured = []
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = audit_cli.main(
                    [
                        "--callers-json",
                        str(callers_path.relative_to(root)),
                        "--output",
                        str(output.relative_to(root)),
                        "--resource-report",
                        str(resource_path.relative_to(root)),
                    ],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://audit.invalid/wow",
                    },
                    repo_root=root,
                    run_audit_fn=lambda **kwargs: (
                        captured.append(kwargs) or report
                    ),
                )

            summary = json.loads(stdout.getvalue())
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertEqual(summary["reportId"], report["reportId"])
        self.assertEqual(written["reportId"], report["reportId"])
        self.assertEqual(
            captured[0]["resource_report"]["reportId"],
            exact_resource_report["reportId"],
        )
        self.assertEqual(
            summary["output"],
            "artifacts/runtime-readonly-audit.json",
        )

    def test_changed_pointer_fails_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers_path = write_callers(root)
            loaded_callers, caller_bytes = audit_cli.load_caller_report(
                root,
                callers_path,
            )
            output = root / "runtime-readonly-audit.json"

            with self.assertRaisesRegex(
                audit_cli.GearCatalogAuditPointerChanged,
                "AUDIT_POINTER_CHANGED",
            ):
                audit_cli.run_audit(
                    caller_report=loaded_callers,
                    caller_bytes=caller_bytes,
                    snapshot_reader=lambda **kwargs: audit_snapshot(),
                    spec_payload_reader=(
                        lambda class_key, spec_key: spec_payload(
                            class_key,
                            spec_key,
                            changed=(class_key, spec_key) == ("class-9", "spec-9-3"),
                        )
                    ),
                    class_spec_matrix=class_matrix(),
                    filesystem_roots=[root],
                    statvfs_fn=lambda path: FakeStatvfs(),
                    observed_at="2026-07-28T10:00:00+08:00",
                )

            self.assertFalse(output.exists())

    def test_database_url_never_appears_in_output_or_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callers = write_callers(root)
            output = root / "runtime-readonly-audit.json"
            database_url = "postgresql://user:secret@audit.invalid/wow"
            stdout = io.StringIO()
            stderr = io.StringIO()

            def failing_runner(**kwargs):
                raise RuntimeError(f"connection failed for {database_url}")

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = audit_cli.main(
                    [
                        "--callers-json",
                        str(callers.relative_to(root)),
                        "--output",
                        str(output.relative_to(root)),
                    ],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": database_url,
                    },
                    repo_root=root,
                    run_audit_fn=failing_runner,
                )

            combined = stdout.getvalue() + stderr.getvalue()
            self.assertNotEqual(status, 0)
            self.assertNotIn(database_url, combined)
            self.assertNotIn("secret", combined)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
