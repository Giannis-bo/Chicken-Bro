import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest


class FakeCursor:
    def __init__(self):
        self.statements = []

    def execute(self, statement, *_args, **_kwargs):
        self.statements.append(str(statement))
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.session_calls = []
        self.read_only = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)
        self.read_only = kwargs.get("readonly") is True

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


class FakeStore:
    def __init__(self, pointers):
        self.pointers = list(pointers)

    def get_active_pointer(self):
        return self.pointers.pop(0)


def gear_release_descriptor(release_id="gear-release:sha256:" + ("1" * 64)):
    return {
        "releaseId": release_id,
        "releaseKind": "gear",
        "seasonRevision": "season-17",
        "dependencyRevisions": {
            "simcRuntimeRevision": "simc-r1",
            "capabilityRevision": "gear-capability-v1",
        },
    }


def prepared_result():
    return {
        "release": {
            "releaseId": "community-release:sha256:" + ("2" * 64),
            "releaseStatus": "validated",
            "contentHash": "sha256:" + ("3" * 64),
        },
        "gate": {
            "status": "validated",
            "stagingTemplateCount": 3253,
            "winnerSpecCount": 40,
            "winnerHeroSlotCount": 80,
        },
        "rows": [{"templateId": "private-player-template"}],
    }


class GearReleaseResourceProbeTest(unittest.TestCase):
    def test_peak_rss_measurement_is_available_on_the_current_platform(self):
        from server.gear_release_resource_probe import current_peak_rss_bytes

        observed = current_peak_rss_bytes()

        self.assertIsInstance(observed, int)
        self.assertGreater(observed, 0)

    def test_postgres_only_environment_and_read_only_connection_are_mandatory(self):
        from server.gear_release_resource_probe import (
            ReadOnlyConnectionFactory,
            ResourceProbeError,
            require_postgres_only_environment,
        )

        with self.assertRaises(ResourceProbeError):
            require_postgres_only_environment({})
        with self.assertRaises(ResourceProbeError):
            require_postgres_only_environment({
                "WOW_DATABASE_RUNTIME": "sqlite",
                "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
            })

        require_postgres_only_environment({
            "WOW_DATABASE_RUNTIME": "postgres_only",
            "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
        })
        raw = FakeConnection()
        factory = ReadOnlyConnectionFactory(lambda: raw)
        connection = factory()
        self.assertEqual(raw.session_calls, [{
            "readonly": True,
            "autocommit": False,
        }])
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            with self.assertRaises(ResourceProbeError):
                cursor.execute("UPDATE cache.example SET value = 1")
            with self.assertRaises(ResourceProbeError):
                cursor.execute(
                    "WITH changed AS (UPDATE cache.example SET value = 2) SELECT 1"
                )
        self.assertEqual(factory.metrics["writeStatements"], 2)

        psycopg3 = FakeConnection()
        psycopg3.set_session = None
        psycopg3_factory = ReadOnlyConnectionFactory(lambda: psycopg3)
        psycopg3_factory()
        self.assertTrue(psycopg3.read_only)

    def test_probe_measures_resources_without_exposing_template_identity(self):
        from server.gear_release_resource_probe import run_resource_probe

        pointer = {
            "environment": "retail",
            "pointerMode": "active",
            "manifestRevision": "season-manifest:sha256:" + ("4" * 64),
            "generation": 24,
            "rollbackManifestRevision": "season-manifest:sha256:" + ("5" * 64),
            "updatedBy": "private-operator",
        }
        clock = iter((1_000_000_000, 2_500_000_000))

        def prepare(_store, **_kwargs):
            Path(os.environ["TMPDIR"], "probe.tmp").write_bytes(b"x" * 128)
            return prepared_result()

        report = run_resource_probe(
            FakeStore([pointer, pointer]),
            gear_release_descriptor=gear_release_descriptor(),
            gear_snapshot={"items": [], "sources": [], "variants": [], "options": []},
            dependency_revisions=gear_release_descriptor()["dependencyRevisions"],
            expected_specs=[("mage", "arcane")],
            simc_runtime_revision="simc-r1",
            now="2026-07-28T10:00:00+00:00",
            prepare_fn=prepare,
            monotonic_ns=lambda: next(clock),
            peak_rss_bytes=lambda: 1_500_000_000,
        )

        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["metrics"], {
            "elapsedMilliseconds": 1500,
            "peakRssObservedBytes": 1_500_000_000,
            "temporaryBytesObserved": 128,
            "writeStatementCount": 0,
        })
        self.assertEqual(report["prepared"], {
            "communityReleaseStatus": "validated",
            "communityContentHash": "sha256:" + ("3" * 64),
            "stagingTemplateCount": 3253,
            "winnerSpecCount": 40,
            "winnerHeroSlotCount": 80,
        })
        self.assertNotIn("private-player-template", serialized)
        self.assertNotIn("private-operator", serialized)
        self.assertRegex(
            report["reportId"],
            r"^gear-release-resource-probe:sha256:[0-9a-f]{64}$",
        )

    def test_pointer_change_and_resource_caps_fail_closed(self):
        from server.gear_release_resource_probe import run_resource_probe

        before = {
            "pointerMode": "active",
            "manifestRevision": "manifest-a",
            "generation": 24,
            "rollbackManifestRevision": "manifest-z",
        }
        after = {**before, "generation": 25, "manifestRevision": "manifest-b"}
        clock = iter((0, 301_000_000_000))

        def prepare(_store, **_kwargs):
            Path(os.environ["TMPDIR"], "large.tmp").write_bytes(b"x" * 129)
            return prepared_result()

        report = run_resource_probe(
            FakeStore([before, after]),
            gear_release_descriptor=gear_release_descriptor(),
            gear_snapshot={},
            dependency_revisions=gear_release_descriptor()["dependencyRevisions"],
            expected_specs=[("mage", "arcane")],
            simc_runtime_revision="simc-r1",
            now="2026-07-28T10:00:00+00:00",
            prepare_fn=prepare,
            monotonic_ns=lambda: next(clock),
            peak_rss_bytes=lambda: 201,
            limits={
                "elapsedMilliseconds": 300_000,
                "peakRssObservedBytes": 200,
                "temporaryBytesObserved": 128,
            },
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["problemCodes"], [
            "RESOURCE_ELAPSED_EXCEEDED",
            "RESOURCE_PEAK_RSS_EXCEEDED",
            "RESOURCE_POINTER_CHANGED",
            "RESOURCE_TEMPORARY_BYTES_EXCEEDED",
        ])

    def test_report_identity_is_bound_to_gear_simc_and_builder_revisions(self):
        from server.gear_release_resource_probe import build_resource_report

        arguments = {
            "gear_release_id": "gear-a",
            "season_revision": "season-17",
            "simc_runtime_revision": "simc-a",
            "builder_revision": "builder-a",
            "pointer_before": {"generation": 24},
            "pointer_after": {"generation": 24},
            "metrics": {
                "elapsedMilliseconds": 1,
                "peakRssObservedBytes": 2,
                "temporaryBytesObserved": 3,
                "writeStatementCount": 0,
            },
            "limits": {
                "elapsedMilliseconds": 300_000,
                "peakRssObservedBytes": 2_000_000_000,
                "temporaryBytesObserved": 268_435_456,
            },
            "prepared": {
                "communityReleaseStatus": "validated",
                "communityContentHash": "sha256:" + ("3" * 64),
                "stagingTemplateCount": 3253,
                "winnerSpecCount": 40,
                "winnerHeroSlotCount": 80,
            },
        }
        baseline = build_resource_report(**arguments)
        for field, value in (
            ("gear_release_id", "gear-b"),
            ("simc_runtime_revision", "simc-b"),
            ("builder_revision", "builder-b"),
        ):
            changed = build_resource_report(**{**arguments, field: value})
            self.assertNotEqual(changed["reportId"], baseline["reportId"])

    def test_temporary_directory_is_removed_when_prepare_fails(self):
        from server.gear_release_resource_probe import (
            ResourceProbeError,
            run_resource_probe,
        )

        pointer = {"pointerMode": "active", "manifestRevision": "manifest-a", "generation": 24}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fail(_store, **_kwargs):
                Path(os.environ["TMPDIR"], "partial.tmp").write_text(
                    "partial",
                    encoding="utf-8",
                )
                raise RuntimeError("private player failure")

            with self.assertRaisesRegex(ResourceProbeError, "prepare failed"):
                run_resource_probe(
                    FakeStore([pointer]),
                    gear_release_descriptor=gear_release_descriptor(),
                    gear_snapshot={},
                    dependency_revisions=gear_release_descriptor()["dependencyRevisions"],
                    expected_specs=[("mage", "arcane")],
                    simc_runtime_revision="simc-r1",
                    now="2026-07-28T10:00:00+00:00",
                    prepare_fn=fail,
                    temporary_root=root,
                )
            self.assertEqual(list(root.iterdir()), [])

    def test_cli_writes_one_bounded_aggregate_report_inside_repository(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "gear-release-resource-probe.py"
        )
        spec = importlib.util.spec_from_file_location(
            "gear_release_resource_probe_cli",
            script,
        )
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)

        report = {
            "schemaRevision": "gear-release-resource-probe-v1",
            "reportId": "gear-release-resource-probe:sha256:" + ("9" * 64),
            "status": "pass",
            "gearReleaseId": "gear-release:exact",
            "metrics": {
                "elapsedMilliseconds": 100,
                "peakRssObservedBytes": 1000,
                "temporaryBytesObserved": 0,
                "writeStatementCount": 0,
            },
        }

        class Store:
            def get_release(self, release_id):
                self.release_id = release_id
                return gear_release_descriptor(release_id)

            def snapshot_gear_release_for_community_builder(self, release_id):
                self.snapshot_release_id = release_id
                return {"items": [], "sources": [], "variants": [], "options": []}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "artifacts" / "resource.json"
            stdout = io.StringIO()
            captured = []
            with contextlib.redirect_stdout(stdout):
                status = module.main(
                    [
                        "--gear-release-id",
                        "gear-release:exact",
                        "--simc-runtime-revision",
                        "simc-r1",
                        "--output",
                        "artifacts/resource.json",
                    ],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
                    },
                    repo_root=root,
                    store_factory=lambda: Store(),
                    run_probe_fn=lambda *_args, **kwargs: (
                        captured.append(kwargs) or report
                    ),
                )

            summary = json.loads(stdout.getvalue())
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(status, 0)
            self.assertEqual(written, report)
            self.assertEqual(
                summary,
                {
                    "output": "artifacts/resource.json",
                    "reportId": report["reportId"],
                    "status": "pass",
                },
            )
            self.assertEqual(
                captured[0]["gear_release_descriptor"]["releaseId"],
                "gear-release:exact",
            )
            with self.assertRaisesRegex(Exception, "already exists"):
                module.main(
                    [
                        "--gear-release-id",
                        "gear-release:exact",
                        "--simc-runtime-revision",
                        "simc-r1",
                        "--output",
                        "artifacts/resource.json",
                    ],
                    environ={
                        "WOW_DATABASE_RUNTIME": "postgres_only",
                        "WOW_DATABASE_URL": "postgresql://example.invalid/wow",
                    },
                    repo_root=root,
                    store_factory=lambda: Store(),
                    run_probe_fn=lambda *_args, **_kwargs: report,
                )


if __name__ == "__main__":
    unittest.main()
