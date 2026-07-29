import importlib.util
from pathlib import Path
import unittest

from tests.gear_catalog_revision_test import (
    CURRENT_BINDING,
    crafted_rows,
    regular_rows,
)


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
    def test_snapshot_shadow_reader_reuses_one_projection_without_public_payload_cache(self):
        calls = []

        class FakeSelectors:
            @staticmethod
            def build_gear_sources_by_item_read_model(rows):
                calls.append(("sources", len(rows)))
                return {"1001": rows}

            @staticmethod
            def build_gear_variants_by_item_read_model(rows):
                calls.append(("variants", len(rows)))
                return {"1001": rows}

            @staticmethod
            def build_gear_mod_options_by_type_read_model(rows):
                calls.append(("options", len(rows)))
                return {}

            @staticmethod
            def build_gear_catalog_items_read_model(
                item_rows,
                sources_by_item,
                variants_by_item,
                options_by_slot,
                class_key,
                spec_key,
                season,
            ):
                calls.append(("catalog", class_key, spec_key, len(item_rows)))
                return [
                    {
                        "itemId": "1001",
                        "variants": [{"id": "hero-6"}],
                    }
                ]

            @staticmethod
            def build_catalog_gear_read_model_fragment(
                catalog_items,
                options_by_slot,
                class_key,
                spec_key,
                *,
                compact,
            ):
                calls.append(("fragment", class_key, spec_key, compact))
                return {
                    "replacementCandidates": [
                        {"slot": "head", "items": catalog_items}
                    ]
                }

        rows = regular_rows()
        rows["variants"].append(
            {
                "variantId": "observed-exact",
                "variantKey": "observed-exact",
                "itemId": "1001",
                "rowFamily": "exact_instance",
                "itemLevel": 276,
                "slot": "head",
                "sourceType": "observed_profile",
                "bonusIds": [],
                "staticStats": {"haste_rating": 120},
                "status": "verified",
            }
        )
        reader = revision_cli._snapshot_spec_payload_reader(
            rows,
            {
                "generation": 32,
                "manifestRevision": CURRENT_BINDING["manifestRevision"],
            },
            CURRENT_BINDING["seasonRevision"],
            selectors=FakeSelectors,
        )
        payload = reader("mage", "arcane")

        self.assertNotIn("replacementCandidates", payload)
        self.assertEqual(
            payload["catalogShadowVisibleCandidates"],
            [["1001", "hero-6"]],
        )
        self.assertEqual(payload["pointerGeneration"], 32)
        self.assertEqual(
            [call[0] for call in calls].count("sources"),
            1,
        )
        self.assertEqual(
            [call[0] for call in calls].count("variants"),
            1,
        )
        self.assertIn(("variants", 1), calls)
        self.assertIn(("catalog", "mage", "arcane", 1), calls)

    def test_snapshot_shadow_reader_projects_actual_pg_selector_contract(self):
        rows = regular_rows()
        rows["items"][0]["payload"]["armorType"] = "Plate"
        rows["variants"][0]["payload"] = {
            "itemStats": [
                {
                    "key": "intellect",
                    "label": "Intellect",
                    "value": 120,
                },
                {
                    "key": "stamina",
                    "label": "Stamina",
                    "value": 180,
                },
                {
                    "key": "haste_rating",
                    "label": "Haste",
                    "value": 80,
                },
            ],
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
        }
        reader = revision_cli._snapshot_spec_payload_reader(
            rows,
            {
                "generation": 32,
                "manifestRevision": CURRENT_BINDING["manifestRevision"],
            },
            CURRENT_BINDING["seasonRevision"],
        )

        payload = reader("paladin", "holy")

        self.assertEqual(payload["catalogStatus"], "verified")
        self.assertEqual(
            payload["catalogShadowVisibleCandidates"],
            [["1001", "hero-6"]],
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

    def test_compact_crafted_identity_maps_to_collapsed_catalog_variant(self):
        crafted_snapshot = snapshot()
        crafted_snapshot["catalogRows"] = crafted_rows()

        def crafted_payload(class_key, spec_key):
            payload = spec_payload(class_key, spec_key)
            payload["replacementCandidates"][0]["items"] = [
                {
                    "itemId": "crafted-1",
                    "variantKey": "crafted-1-stats-0",
                    "variants": [{"id": "crafted-myth-285"}],
                }
            ]
            return payload

        report = revision_cli.run_migration(
            snapshot_reader=lambda **_: crafted_snapshot,
            pointer_reader=lambda **_: crafted_snapshot["pointerAfter"],
            seal_writer=lambda catalog: catalog,
            spec_payload_reader=crafted_payload,
            class_spec_matrix=class_spec_matrix(),
            observed_at="2026-07-29T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(
            report["specShadow"]["unmappedCandidateCount"],
            0,
        )
        self.assertEqual(
            report["specShadow"]["rows"][0][
                "legacyVisibleCandidateCount"
            ],
            1,
        )
        self.assertEqual(
            report["specShadow"]["rows"][0][
                "dormantBrowseVariantCount"
            ],
            1,
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

    def test_many_legacy_identities_to_one_dormant_variant_blocks_shadow(self):
        def duplicate_alias_payload(class_key, spec_key):
            payload = spec_payload(class_key, spec_key)
            payload["replacementCandidates"][0]["items"][0][
                "variants"
            ] = [
                {"id": "hero-6"},
                {"id": "variant-hero-6"},
            ]
            return payload

        report = revision_cli.run_migration(
            snapshot_reader=lambda **_: snapshot(),
            pointer_reader=lambda **_: snapshot()["pointerAfter"],
            seal_writer=lambda catalog: catalog,
            spec_payload_reader=duplicate_alias_payload,
            class_spec_matrix=class_spec_matrix(),
            observed_at="2026-07-29T10:00:00+08:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "CATALOG_SHADOW_VISIBLE_CARDINALITY_MISMATCH",
            report["problemCodes"],
        )

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
