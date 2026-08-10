import copy
import unittest

try:
    from server.gear_variant_materialization_matrix import (
        GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION,
        build_gear_variant_materialization_matrix,
        validate_gear_variant_materialization_matrix_report,
    )
except ModuleNotFoundError:
    GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION = None
    build_gear_variant_materialization_matrix = None
    validate_gear_variant_materialization_matrix_report = None


class RecordingMaterializer:
    def __init__(self, reports):
        self.reports = copy.deepcopy(reports)
        self.calls = []

    def __call__(
        self,
        *,
        item_id,
        browse_variant_key,
        class_key,
        spec_key,
        slot,
        selection_intent,
    ):
        self.calls.append(
            {
                "itemId": item_id,
                "browseVariantKey": browse_variant_key,
                "classKey": class_key,
                "specKey": spec_key,
                "slot": slot,
                "selectionIntent": copy.deepcopy(selection_intent),
            }
        )
        return copy.deepcopy(self.reports[browse_variant_key])


class GearVariantMaterializationMatrixTest(unittest.TestCase):
    def catalog(self):
        return {
            "status": "verified",
            "catalogRevision": "gear-catalog:sha256:" + "a" * 64,
            "browseVariants": [
                {"browseVariantKey": "browse-b", "itemId": "1002"},
                {"browseVariantKey": "browse-a", "itemId": "1001"},
            ],
        }

    def relation_contexts(self):
        return [
            {
                "browseVariantKey": "browse-b",
                "itemId": "1002",
                "classKey": "mage",
                "specKey": "frost",
                "slot": "neck",
                "selectionIntent": {
                    "schemaRevision": "selection-intent-v1",
                    "slots": {
                        "neck": {
                            "itemId": "1002",
                            "variantKey": "browse-b",
                        }
                    },
                },
            },
            {
                "browseVariantKey": "browse-a",
                "itemId": "1001",
                "classKey": "mage",
                "specKey": "frost",
                "slot": "head",
                "selectionIntent": {
                    "schemaRevision": "selection-intent-v1",
                    "slots": {
                        "head": {
                            "itemId": "1001",
                            "variantKey": "browse-a",
                        }
                    },
                },
            },
        ]

    def verified_materializer_reports(self):
        contexts = {
            row["browseVariantKey"]: row["selectionIntent"]
            for row in self.relation_contexts()
        }
        return {
            "browse-a": {
                "status": "verified",
                "materializedItemId": "1001",
                "materializedBrowseVariantKey": "browse-a",
                "selectionIntent": contexts["browse-a"],
                "usedDefaultVariant": False,
                "resolverStatus": "resolved",
                "profileStatus": "resolved",
                "simcReady": True,
            },
            "browse-b": {
                "status": "verified",
                "materializedItemId": "1002",
                "materializedBrowseVariantKey": "browse-b",
                "selectionIntent": contexts["browse-b"],
                "usedDefaultVariant": False,
                "resolverStatus": "verified",
                "profileStatus": "verified",
                "simcReady": True,
            },
        }

    def test_verified_matrix_materializes_each_unique_variant_exactly_once(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)
        self.assertEqual(
            GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION,
            "gear-variant-materialization-matrix-v1",
        )

        materializer = RecordingMaterializer(self.verified_materializer_reports())

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            materializer,
        )

        self.assertEqual(report["schemaRevision"], GEAR_VARIANT_MATERIALIZATION_MATRIX_SCHEMA_REVISION)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["expected_unique_variant_count"], 2)
        self.assertEqual(report["materialized_unique_variant_count"], 2)
        self.assertEqual(report["unique_variant_materialization_count"], 2)
        self.assertEqual(report["catalog_non_simulatable_count"], 0)
        self.assertEqual(report["silent_default_fill_count"], 0)
        self.assertEqual(report["missing_provenance_count"], 0)
        self.assertEqual(report["failureCodes"], [])
        self.assertEqual(list(report["ledger"]), ["browse-a", "browse-b"])
        self.assertTrue(
            report["reportId"].startswith(
                "gear-variant-materialization-matrix:sha256:"
            )
        )
        self.assertEqual(
            materializer.calls,
            [
                {
                    "itemId": "1001",
                    "browseVariantKey": "browse-a",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                },
                {
                    "itemId": "1002",
                    "browseVariantKey": "browse-b",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "neck",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "slots": {
                            "neck": {
                                "itemId": "1002",
                                "variantKey": "browse-b",
                            }
                        },
                    },
                },
            ],
        )
        self.assertEqual(
            validate_gear_variant_materialization_matrix_report(report),
            [],
        )

    def test_missing_relation_context_blocks_and_counts_missing_provenance(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)

        contexts = self.relation_contexts()
        materializer = RecordingMaterializer(self.verified_materializer_reports())

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            [contexts[0]],
            materializer,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["expected_unique_variant_count"], 2)
        self.assertEqual(report["materialized_unique_variant_count"], 1)
        self.assertEqual(report["unique_variant_materialization_count"], 1)
        self.assertEqual(report["catalog_non_simulatable_count"], 1)
        self.assertEqual(report["missing_provenance_count"], 1)
        self.assertIn(
            "MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT",
            report["failureCodes"],
        )
        self.assertEqual(len(materializer.calls), 1)
        self.assertEqual(
            report["ledger"]["browse-a"]["failureCodes"],
            ["MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT"],
        )

    def test_default_substitution_never_counts_as_materialized_success(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)

        reports = self.verified_materializer_reports()
        reports["browse-a"]["usedDefaultVariant"] = True
        materializer = RecordingMaterializer(reports)

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            materializer,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["materialized_unique_variant_count"], 1)
        self.assertEqual(report["unique_variant_materialization_count"], 1)
        self.assertEqual(report["catalog_non_simulatable_count"], 1)
        self.assertEqual(report["silent_default_fill_count"], 1)
        self.assertEqual(report["missing_provenance_count"], 0)
        self.assertIn(
            "MATERIALIZATION_MATRIX_USED_DEFAULT_VARIANT",
            report["failureCodes"],
        )
        self.assertEqual(
            report["ledger"]["browse-a"]["usedDefaultVariant"],
            True,
        )

    def test_materialized_item_or_key_mismatch_is_rejected(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)

        reports = self.verified_materializer_reports()
        reports["browse-a"]["materializedItemId"] = "9999"
        reports["browse-a"]["materializedBrowseVariantKey"] = "browse-z"
        materializer = RecordingMaterializer(reports)

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            materializer,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["materialized_unique_variant_count"], 1)
        self.assertEqual(report["catalog_non_simulatable_count"], 1)
        self.assertEqual(report["missing_provenance_count"], 1)
        self.assertIn(
            "MATERIALIZATION_MATRIX_MATERIALIZED_PAIR_MISMATCH",
            report["failureCodes"],
        )

    def test_partial_resolver_or_profile_readiness_stays_literal_and_blocks(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)

        reports = self.verified_materializer_reports()
        reports["browse-a"].update(
            {
                "status": "partial",
                "resolverStatus": "partial",
                "profileStatus": "verified",
                "simcReady": True,
            }
        )
        reports["browse-b"].update(
            {
                "status": "blocked",
                "resolverStatus": "resolved",
                "profileStatus": "blocked",
                "simcReady": False,
            }
        )
        materializer = RecordingMaterializer(reports)

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            materializer,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["materialized_unique_variant_count"], 0)
        self.assertEqual(report["catalog_non_simulatable_count"], 2)
        self.assertEqual(
            report["ledger"]["browse-a"]["status"],
            "partial",
        )
        self.assertEqual(
            report["ledger"]["browse-b"]["status"],
            "blocked",
        )
        self.assertIn(
            "MATERIALIZATION_MATRIX_RESOLVER_STATUS_NOT_READY",
            report["failureCodes"],
        )
        self.assertIn(
            "MATERIALIZATION_MATRIX_PROFILE_STATUS_NOT_READY",
            report["failureCodes"],
        )
        self.assertIn(
            "MATERIALIZATION_MATRIX_SIMC_READINESS_NOT_TRUE",
            report["failureCodes"],
        )

    def test_duplicate_and_extra_contexts_are_rejected_without_extra_materialization(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)

        contexts = self.relation_contexts()
        duplicate = copy.deepcopy(contexts[0])
        duplicate["slot"] = "waist"
        extra = {
            "browseVariantKey": "browse-extra",
            "itemId": "9999",
            "classKey": "mage",
            "specKey": "frost",
            "slot": "waist",
            "selectionIntent": {
                "schemaRevision": "selection-intent-v1",
                "slots": {
                    "waist": {
                        "itemId": "9999",
                        "variantKey": "browse-extra",
                    }
                },
            },
        }
        materializer = RecordingMaterializer(self.verified_materializer_reports())

        report = build_gear_variant_materialization_matrix(
            self.catalog(),
            [contexts[0], duplicate, contexts[1], extra],
            materializer,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["materialized_unique_variant_count"], 2)
        self.assertIn(
            "MATERIALIZATION_MATRIX_DUPLICATE_VARIANT_CONTEXT",
            report["failureCodes"],
        )
        self.assertIn(
            "MATERIALIZATION_MATRIX_EXTRA_RELATION_CONTEXT",
            report["failureCodes"],
        )
        self.assertEqual(len(materializer.calls), 2)

    def test_report_ids_are_deterministic_and_validator_rejects_unordered_ledger(self):
        self.assertIsNotNone(build_gear_variant_materialization_matrix)
        self.assertIsNotNone(validate_gear_variant_materialization_matrix_report)

        materializer = RecordingMaterializer(self.verified_materializer_reports())
        first = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            materializer,
        )
        second = build_gear_variant_materialization_matrix(
            self.catalog(),
            self.relation_contexts(),
            RecordingMaterializer(self.verified_materializer_reports()),
        )

        self.assertEqual(first["reportId"], second["reportId"])
        self.assertEqual(
            validate_gear_variant_materialization_matrix_report(first),
            [],
        )

        tampered = copy.deepcopy(first)
        tampered["ledger"] = {
            "browse-b": copy.deepcopy(first["ledger"]["browse-b"]),
            "browse-a": copy.deepcopy(first["ledger"]["browse-a"]),
        }
        self.assertEqual(
            validate_gear_variant_materialization_matrix_report(tampered),
            ["MATERIALIZATION_MATRIX_LEDGER_ORDER_INVALID"],
        )


if __name__ == "__main__":
    unittest.main()
