import copy
import importlib.util
from pathlib import Path
import unittest

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
