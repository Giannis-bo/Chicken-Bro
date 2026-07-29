import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
import weakref

from tests.gear_catalog_revision_test import (
    CURRENT_BINDING as CATALOG_BINDING,
    regular_rows,
)
from tests.gear_exact_item_instance_test import exact_row
from tests.gear_exact_item_registry_test import template


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gear-exact-item-instance.py"
SPEC = importlib.util.spec_from_file_location("gear_exact_item_cli", SCRIPT)
exact_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(exact_cli)


def snapshot():
    rows = regular_rows()
    rows["variants"].append(exact_row())
    pointer = {
        "generation": 32,
        "manifestRevision": CATALOG_BINDING["manifestRevision"],
        "pointerMode": "active",
    }
    return {
        "pointerBefore": pointer,
        "pointerAfter": dict(pointer),
        "activeBinding": {
            "manifest": {
                "manifestRevision": CATALOG_BINDING["manifestRevision"],
                "seasonRevision": CATALOG_BINDING["seasonRevision"],
                "dependencyVector": CATALOG_BINDING["dependencyVector"],
            },
            "gearRelease": {
                "releaseId": CATALOG_BINDING["gearReleaseId"],
                "schemaRevision": CATALOG_BINDING["gearReleaseSchemaRevision"],
                "contentHash": CATALOG_BINDING["gearReleaseContentHash"],
                "releaseStatus": "validated",
                "dependencyVector": CATALOG_BINDING["dependencyVector"],
                "source": {"sourceMode": "sealed_fixture"},
                "contentSummary": {"itemCount": 1, "variantCount": 2},
            },
        },
        "catalogRows": rows,
        "communityTemplates": [template()],
        "personalGearTemplates": [],
    }


class GearExactItemInstanceCliTest(unittest.TestCase):
    def test_exact_binding_prefers_explicit_requested_release_pair(self):
        current = snapshot()
        requested = copy.deepcopy(current["activeBinding"])
        requested["manifest"]["manifestRevision"] = ""
        requested["gearRelease"]["releaseId"] = (
            "gear-release:sha256:" + ("9" * 64)
        )
        requested["gearRelease"]["contentHash"] = (
            "sha256:" + ("8" * 64)
        )
        current["requestedBinding"] = requested

        binding = exact_cli._binding(current)

        self.assertEqual(
            binding["gearReleaseId"],
            requested["gearRelease"]["releaseId"],
        )
        self.assertEqual(
            binding["gearReleaseContentHash"],
            requested["gearRelease"]["contentHash"],
        )
        self.assertEqual(
            binding["bindingMode"],
            "validated_release_pair",
        )

    def test_cli_accepts_complete_requested_release_pair_only(self):
        gear_id = "gear-release:sha256:" + ("9" * 64)
        community_id = "community-release:sha256:" + ("8" * 64)

        parsed = exact_cli.parse_args([
            "--gear-release-id",
            gear_id,
            "--community-release-id",
            community_id,
        ])

        self.assertEqual(parsed.gear_release_id, gear_id)
        self.assertEqual(parsed.community_release_id, community_id)

    def test_streaming_hash_matches_canonical_hash(self):
        current = snapshot()
        binding = exact_cli._binding(current)
        registry = exact_cli.build_exact_item_registry(
            binding,
            catalog_revision=exact_cli.build_catalog_revision(
                binding,
                current["catalogRows"],
            )["catalogRevision"],
            exact_rows=[current["catalogRows"]["variants"][-1]],
            community_templates=current["communityTemplates"],
            personal_templates=current["personalGearTemplates"],
        )

        self.assertEqual(
            exact_cli._streaming_hash("sha256:", registry),
            exact_cli._hash("sha256:", registry),
        )

    def test_run_releases_first_full_registry_before_building_second_copy(self):
        original_build = exact_cli.build_exact_item_registry
        first_ref = []
        build_count = 0

        class TrackedRegistry(dict):
            pass

        def tracked_build(binding, **build_args):
            nonlocal build_count
            build_count += 1
            if build_count == 2:
                self.assertIsNone(first_ref[0]())
            registry = TrackedRegistry(
                original_build(binding, **build_args)
            )
            if build_count == 1:
                first_ref.append(weakref.ref(registry))
            return registry

        with mock.patch.object(
            exact_cli,
            "build_exact_item_registry",
            side_effect=tracked_build,
        ):
            report = exact_cli.run_migration(
                snapshot_reader=lambda **_: snapshot(),
                pointer_reader=lambda **_: snapshot()["pointerAfter"],
                catalog_reader=lambda revision: {
                    "catalogRevision": revision
                },
                seal_writer=lambda registry: registry,
                observed_at="2026-07-29T12:00:00+08:00",
                elapsed_seconds_reader=lambda: 2.5,
                peak_bytes_reader=lambda: 128_000_000,
            )

        self.assertEqual(report["status"], "verified")
        self.assertTrue(report["deterministicBuild"])

    def test_nondeterministic_registry_blocks_before_dormant_seal(self):
        original_build = exact_cli.build_exact_item_registry
        sealed = []
        build_count = 0

        def nondeterministic_build(binding, **build_args):
            nonlocal build_count
            build_count += 1
            registry = original_build(binding, **build_args)
            if build_count == 2:
                registry["schemaRevision"] = "unexpected-drift"
            return registry

        with mock.patch.object(
            exact_cli,
            "build_exact_item_registry",
            side_effect=nondeterministic_build,
        ):
            report = exact_cli.run_migration(
                snapshot_reader=lambda **_: snapshot(),
                pointer_reader=lambda **_: snapshot()["pointerAfter"],
                catalog_reader=lambda revision: {
                    "catalogRevision": revision
                },
                seal_writer=lambda registry: sealed.append(registry),
                observed_at="2026-07-29T12:00:00+08:00",
                elapsed_seconds_reader=lambda: 2.5,
                peak_bytes_reader=lambda: 128_000_000,
            )

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["deterministicBuild"])
        self.assertIn(
            "EXACT_SHADOW_BUILD_NONDETERMINISTIC",
            report["problemCodes"],
        )
        self.assertEqual(sealed, [])

    def test_run_releases_catalogs_before_building_exact_registry(self):
        original_catalog_build = exact_cli.build_catalog_revision
        original_registry_build = exact_cli.build_exact_item_registry
        catalog_refs = []

        class TrackedCatalog(dict):
            pass

        def tracked_catalog_build(binding, rows):
            catalog = TrackedCatalog(
                original_catalog_build(binding, rows)
            )
            catalog_refs.append(weakref.ref(catalog))
            return catalog

        def tracked_catalog_read(revision):
            catalog = TrackedCatalog({"catalogRevision": revision})
            catalog_refs.append(weakref.ref(catalog))
            return catalog

        def registry_after_catalog_release(binding, **build_args):
            self.assertEqual(len(catalog_refs), 2)
            self.assertTrue(all(ref() is None for ref in catalog_refs))
            return original_registry_build(binding, **build_args)

        with (
            mock.patch.object(
                exact_cli,
                "build_catalog_revision",
                side_effect=tracked_catalog_build,
            ),
            mock.patch.object(
                exact_cli,
                "build_exact_item_registry",
                side_effect=registry_after_catalog_release,
            ),
        ):
            report = exact_cli.run_migration(
                snapshot_reader=lambda **_: snapshot(),
                pointer_reader=lambda **_: snapshot()["pointerAfter"],
                catalog_reader=tracked_catalog_read,
                seal_writer=lambda registry: registry,
                observed_at="2026-07-29T12:00:00+08:00",
                elapsed_seconds_reader=lambda: 2.5,
                peak_bytes_reader=lambda: 128_000_000,
            )

        self.assertEqual(report["status"], "verified")

    def test_one_snapshot_builds_twice_seals_reloads_and_keeps_pointer(self):
        sealed = []

        def seal_writer(registry):
            sealed.append(copy.deepcopy(registry))
            return registry

        report = exact_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: snapshot()["pointerAfter"],
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=seal_writer,
            observed_at="2026-07-29T12:00:00+08:00",
            elapsed_seconds_reader=lambda: 2.5,
            peak_bytes_reader=lambda: 128_000_000,
        )

        self.assertEqual(report["status"], "verified")
        self.assertTrue(report["deterministicBuild"])
        self.assertTrue(report["pointerStable"])
        self.assertEqual(report["pointerBefore"]["generation"], 32)
        self.assertEqual(report["pointerAfter"]["generation"], 32)
        self.assertEqual(report["summary"]["sourceExactRowCount"], 1)
        self.assertEqual(report["summary"]["referencedExactRowCount"], 1)
        self.assertEqual(report["summary"]["unreferencedExactRowCount"], 0)
        self.assertEqual(report["summary"]["templateCount"], 1)
        self.assertEqual(report["summary"]["classifiedTemplateCount"], 1)
        self.assertEqual(report["summary"]["verifiedTemplateItemCount"], 1)
        self.assertEqual(len(sealed), 1)
        self.assertRegex(
            report["registryRevision"],
            r"^gear-exact-registry:sha256:[0-9a-f]{64}$",
        )
        self.assertRegex(
            report["reportId"],
            r"^gear-exact-shadow:sha256:[0-9a-f]{64}$",
        )

    def test_unreferenced_history_is_counted_but_not_materialized(self):
        current = snapshot()
        current["catalogRows"]["variants"].append(
            exact_row(itemId="2002", variantKey="unreferenced-hero-3")
        )

        report = exact_cli.run_migration(
            snapshot_reader=lambda **_: current,
            pointer_reader=lambda **_: current["pointerAfter"],
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=lambda registry: registry,
            elapsed_seconds_reader=lambda: 1.0,
            peak_bytes_reader=lambda: 1_000_000,
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["summary"]["sourceExactRowCount"], 2)
        self.assertEqual(report["summary"]["exactItemInstanceCount"], 1)
        self.assertEqual(report["summary"]["unreferencedExactRowCount"], 1)

    def test_allowed_evidence_gap_seals_partial_registry_and_passes_shadow(self):
        current = snapshot()
        exact = current["catalogRows"]["variants"][-1]
        exact["simcOptions"]["enchant_id"] = "7443/7444"
        current["communityTemplates"][0]["gearItems"][0].pop("enchantId")
        sealed = []

        report = exact_cli.run_migration(
            snapshot_reader=lambda **_: current,
            pointer_reader=lambda **_: current["pointerAfter"],
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=lambda registry: sealed.append(copy.deepcopy(registry))
            or registry,
            elapsed_seconds_reader=lambda: 1.0,
            peak_bytes_reader=lambda: 1_000_000,
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["registryStatus"], "partial")
        self.assertEqual(
            report["evidenceGapCodes"],
            ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        self.assertEqual(report["problemCodes"], [])
        self.assertEqual(len(sealed), 1)
        self.assertEqual(sealed[0]["status"], "partial")
        self.assertEqual(sealed[0]["summary"]["partialTemplateItemCount"], 1)

    def test_pointer_change_resource_overrun_and_enhancement_mismatch_block(self):
        changed = snapshot()["pointerAfter"]
        changed["generation"] = 33
        pointer_report = exact_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: changed,
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=lambda registry: registry,
            elapsed_seconds_reader=lambda: 1.0,
            peak_bytes_reader=lambda: 1_000_000,
        )
        resource_report = exact_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: snapshot()["pointerAfter"],
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=lambda registry: registry,
            elapsed_seconds_reader=lambda: 301.0,
            peak_bytes_reader=lambda: 2_000_000_001,
        )
        mismatch_snapshot = snapshot()
        mismatch_snapshot["communityTemplates"][0]["gearItems"][0][
            "enchantId"
        ] = "9999"
        mismatch_report = exact_cli.run_migration(
            snapshot_reader=lambda **_: mismatch_snapshot,
            pointer_reader=lambda **_: mismatch_snapshot["pointerAfter"],
            catalog_reader=lambda revision: {"catalogRevision": revision},
            seal_writer=lambda registry: registry,
            elapsed_seconds_reader=lambda: 1.0,
            peak_bytes_reader=lambda: 1_000_000,
        )

        self.assertEqual(pointer_report["status"], "blocked")
        self.assertIn("EXACT_SHADOW_POINTER_CHANGED", pointer_report["problemCodes"])
        self.assertEqual(resource_report["status"], "blocked")
        self.assertIn("EXACT_SHADOW_RESOURCE_BYTES_EXCEEDED", resource_report["problemCodes"])
        self.assertIn("EXACT_SHADOW_RESOURCE_SECONDS_EXCEEDED", resource_report["problemCodes"])
        self.assertEqual(mismatch_report["status"], "blocked")
        self.assertIn(
            "EXACT_ENHANCEMENT_SOURCE_MISMATCH",
            mismatch_report["problemCodes"],
        )


if __name__ == "__main__":
    unittest.main()
