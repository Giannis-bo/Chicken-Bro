import importlib.util
from pathlib import Path
import unittest

from tests.gear_catalog_revision_test import CURRENT_BINDING, regular_rows


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gear-catalog-revision.py"
SPEC = importlib.util.spec_from_file_location(
    "gear_catalog_revision_cli",
    SCRIPT,
)
revision_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(revision_cli)


def class_spec_matrix():
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


def snapshot():
    pointer = {
        "generation": 32,
        "manifestRevision": CURRENT_BINDING["manifestRevision"],
        "pointerMode": "active",
        "rollbackManifestRevision": "season-manifest:sha256:" + ("0" * 64),
    }
    return {
        "pointerBefore": pointer,
        "pointerAfter": dict(pointer),
        "activeBinding": {
            "manifest": {
                "manifestRevision": CURRENT_BINDING["manifestRevision"],
                "seasonRevision": CURRENT_BINDING["seasonRevision"],
                "dependencyVector": CURRENT_BINDING["dependencyVector"],
            },
            "gearRelease": {
                "releaseId": CURRENT_BINDING["gearReleaseId"],
                "schemaRevision": CURRENT_BINDING["gearReleaseSchemaRevision"],
                "contentHash": CURRENT_BINDING["gearReleaseContentHash"],
                "releaseStatus": "validated",
                "dependencyVector": CURRENT_BINDING["dependencyVector"],
                "source": {"sourceMode": "sealed_fixture"},
                "contentSummary": {"itemCount": 1, "variantCount": 1},
            },
        },
        "catalogRows": regular_rows(),
    }


def spec_payload(class_key, spec_key):
    return {
        "manifestRevision": CURRENT_BINDING["manifestRevision"],
        "pointerGeneration": 32,
        "catalogStatus": "verified",
        "replacementCandidates": [
            {
                "slot": "head",
                "items": [
                    {
                        "itemId": "1001",
                        "variants": [
                            {
                                "id": "hero-6",
                                "status": "verified",
                            }
                        ],
                    }
                ],
            }
        ],
    }


class GearCatalogRevisionCliTest(unittest.TestCase):
    def test_full_spec_reader_requests_catalog_payload_not_initial_preview(self):
        calls = []

        class FakeCacheStore:
            def get_websim_gear(self, **kwargs):
                calls.append(kwargs)
                return {"catalogStatus": "verified"}

        payload = revision_cli._full_spec_catalog_payload(
            FakeCacheStore(),
            "mage",
            "arcane",
        )

        self.assertEqual(payload, {"catalogStatus": "verified"})
        self.assertEqual(
            calls,
            [
                {
                    "class_key": "mage",
                    "spec_key": "arcane",
                    "compact": True,
                    "mode": "",
                }
            ],
        )

    def test_run_builds_twice_seals_and_proves_40_spec_shadow_without_pointer_change(self):
        sealed = []

        def seal_writer(catalog):
            sealed.append(catalog)
            return catalog

        report = revision_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: snapshot()["pointerAfter"],
            seal_writer=seal_writer,
            spec_payload_reader=spec_payload,
            class_spec_matrix=class_spec_matrix(),
            observed_at="2026-07-29T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "verified")
        self.assertTrue(report["deterministicBuild"])
        self.assertTrue(report["pointerStable"])
        self.assertEqual(report["pointerBefore"]["generation"], 32)
        self.assertEqual(report["pointerAfter"]["generation"], 32)
        self.assertEqual(report["specShadow"]["specCount"], 40)
        self.assertEqual(report["specShadow"]["verifiedSpecCount"], 40)
        self.assertEqual(report["specShadow"]["unmappedCandidateCount"], 0)
        self.assertEqual(len(sealed), 1)
        self.assertEqual(
            sealed[0]["catalogRevision"],
            report["catalogRevision"],
        )
        self.assertRegex(
            report["reportId"],
            r"^gear-catalog-shadow:sha256:[0-9a-f]{64}$",
        )

    def test_unmapped_visible_candidate_blocks_shadow(self):
        def unmatched_payload(class_key, spec_key):
            payload = spec_payload(class_key, spec_key)
            payload["replacementCandidates"][0]["items"][0]["variants"][0][
                "id"
            ] = "unknown-variant"
            return payload

        report = revision_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: snapshot()["pointerAfter"],
            seal_writer=lambda catalog: catalog,
            spec_payload_reader=unmatched_payload,
            class_spec_matrix=class_spec_matrix(),
            observed_at="2026-07-29T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "CATALOG_SHADOW_VISIBLE_CANDIDATE_UNMAPPED",
            report["problemCodes"],
        )
        self.assertEqual(report["specShadow"]["verifiedSpecCount"], 0)

    def test_pointer_change_after_seal_blocks_report(self):
        changed = snapshot()["pointerAfter"]
        changed["generation"] = 33

        report = revision_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: changed,
            seal_writer=lambda catalog: catalog,
            spec_payload_reader=spec_payload,
            class_spec_matrix=class_spec_matrix(),
            observed_at="2026-07-29T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["pointerStable"])
        self.assertIn(
            "CATALOG_SHADOW_POINTER_CHANGED",
            report["problemCodes"],
        )


if __name__ == "__main__":
    unittest.main()
