import copy
import unittest

from server.simc_support_policy import SIMC_SPECIALIZATION_UNSUPPORTED_CODE

try:
    from server.gear_variant_simc_matrix import (
        GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION,
        build_gear_variant_simc_matrix,
    )
except ModuleNotFoundError:
    GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION = None
    build_gear_variant_simc_matrix = None


class RecordingSmoke:
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
    ):
        self.calls.append(
            {
                "itemId": item_id,
                "browseVariantKey": browse_variant_key,
                "classKey": class_key,
                "specKey": spec_key,
                "slot": slot,
            }
        )
        response = self.reports[browse_variant_key]
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class GearVariantSimcMatrixTest(unittest.TestCase):
    def materialization_entry(
        self,
        *,
        item_id,
        class_key,
        spec_key,
        slot,
        status="verified",
        materialized_item_id=None,
        materialized_browse_variant_key=None,
        failure_codes=None,
    ):
        return {
            "status": status,
            "itemId": item_id,
            "classKey": class_key,
            "specKey": spec_key,
            "slot": slot,
            "materializedItemId": materialized_item_id or item_id,
            "materializedBrowseVariantKey": materialized_browse_variant_key,
            "failureCodes": list(failure_codes or []),
        }

    def materialization_report(
        self,
        *,
        status="verified",
        ledger=None,
        expected_unique_variant_count=None,
        unique_variant_materialization_count=None,
    ):
        safe_ledger = copy.deepcopy(
            ledger
            or {
                "browse-b": self.materialization_entry(
                    item_id="1002",
                    class_key="mage",
                    spec_key="fire",
                    slot="neck",
                    materialized_browse_variant_key="browse-b",
                ),
                "browse-a": self.materialization_entry(
                    item_id="1001",
                    class_key="mage",
                    spec_key="frost",
                    slot="head",
                    materialized_browse_variant_key="browse-a",
                ),
            }
        )
        count = len(safe_ledger)
        return {
            "schemaRevision": "gear-variant-materialization-matrix-v1",
            "status": status,
            "expected_unique_variant_count": (
                count
                if expected_unique_variant_count is None
                else expected_unique_variant_count
            ),
            "materialized_unique_variant_count": (
                count
                if unique_variant_materialization_count is None
                else unique_variant_materialization_count
            ),
            "unique_variant_materialization_count": (
                count
                if unique_variant_materialization_count is None
                else unique_variant_materialization_count
            ),
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "missing_provenance_count": 0,
            "failureCodes": [],
            "failureSamples": [],
            "ledger": safe_ledger,
        }

    def smoke_report(
        self,
        *,
        item_id,
        browse_variant_key,
        class_key,
        spec_key,
        status="verified",
        ran=True,
        timed_out=False,
        has_dps=True,
        execution_mode="real",
        simc_runtime_revision="simc-r1",
        iterations=1,
        max_time_seconds=5,
    ):
        return {
            "status": status,
            "itemId": item_id,
            "browseVariantKey": browse_variant_key,
            "classKey": class_key,
            "specKey": spec_key,
            "ran": ran,
            "timedOut": timed_out,
            "hasDps": has_dps,
            "executionMode": execution_mode,
            "simcRuntimeRevision": simc_runtime_revision,
            "iterations": iterations,
            "maxTimeSeconds": max_time_seconds,
        }

    def test_supported_verified_variants_run_once_and_report_verified(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        self.assertEqual(
            GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION,
            "gear-variant-simc-matrix-v1",
        )
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                ),
                "browse-b": self.smoke_report(
                    item_id="1002",
                    browse_variant_key="browse-b",
                    class_key="mage",
                    spec_key="fire",
                ),
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(),
            smoke,
        )

        self.assertEqual(
            report["schemaRevision"],
            GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION,
        )
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 2)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 2)
        self.assertEqual(report["supported_variant_simc_smoke_count"], 2)
        self.assertEqual(report["failureCodes"], [])
        self.assertEqual(list(report["ledger"]), ["browse-a", "browse-b"])
        self.assertTrue(
            report["reportId"].startswith("gear-variant-simc-matrix:sha256:")
        )
        self.assertEqual(
            smoke.calls,
            [
                {
                    "itemId": "1001",
                    "browseVariantKey": "browse-a",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                },
                {
                    "itemId": "1002",
                    "browseVariantKey": "browse-b",
                    "classKey": "mage",
                    "specKey": "fire",
                    "slot": "neck",
                },
            ],
        )

    def test_non_real_or_long_or_missing_dps_fields_block_and_do_not_count(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                    execution_mode="cached",
                    has_dps=False,
                    iterations=2,
                    max_time_seconds=6,
                )
            }
        )
        report = build_gear_variant_simc_matrix(
            self.materialization_report(
                ledger={
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        materialized_browse_variant_key="browse-a",
                    )
                }
            ),
            smoke,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 1)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 0)
        self.assertEqual(report["supported_variant_simc_smoke_count"], 0)
        self.assertIn(
            "GEAR_VARIANT_SIMC_EXECUTION_MODE_NOT_REAL",
            report["failureCodes"],
        )
        self.assertIn(
            "GEAR_VARIANT_SIMC_HAS_DPS_NOT_TRUE",
            report["failureCodes"],
        )
        self.assertIn(
            "GEAR_VARIANT_SIMC_ITERATIONS_INVALID",
            report["failureCodes"],
        )
        self.assertIn(
            "GEAR_VARIANT_SIMC_MAX_TIME_INVALID",
            report["failureCodes"],
        )

    def test_blocked_materialization_report_short_circuits_without_smoke(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                )
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(
                status="blocked",
                ledger={
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        status="blocked",
                        materialized_browse_variant_key="browse-a",
                        failure_codes=["MATERIALIZATION_MATRIX_SIMC_READINESS_NOT_TRUE"],
                    )
                },
            ),
            smoke,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 0)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 0)
        self.assertEqual(report["supported_variant_simc_smoke_count"], 0)
        self.assertIn(
            "GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY",
            report["failureCodes"],
        )
        self.assertEqual(smoke.calls, [])

    def test_unsupported_specialization_is_blocked_before_smoke_and_not_counted(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                )
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(
                ledger={
                    "browse-b": self.materialization_entry(
                        item_id="1002",
                        class_key="paladin",
                        spec_key="holy",
                        slot="neck",
                        materialized_browse_variant_key="browse-b",
                    ),
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        materialized_browse_variant_key="browse-a",
                    ),
                }
            ),
            smoke,
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 1)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 1)
        self.assertEqual(report["supported_variant_simc_smoke_count"], 1)
        self.assertEqual(len(smoke.calls), 1)
        self.assertEqual(
            report["ledger"]["browse-b"]["failureCodes"],
            [SIMC_SPECIALIZATION_UNSUPPORTED_CODE],
        )
        self.assertEqual(report["ledger"]["browse-b"]["status"], "blocked")

    def test_smoke_identity_mismatch_blocks_variant(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="9999",
                    browse_variant_key="browse-z",
                    class_key="mage",
                    spec_key="arcane",
                )
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(
                ledger={
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        materialized_browse_variant_key="browse-a",
                    )
                }
            ),
            smoke,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 1)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 0)
        self.assertEqual(report["supported_variant_simc_smoke_count"], 0)
        self.assertIn(
            "GEAR_VARIANT_SIMC_IDENTITY_MISMATCH",
            report["failureCodes"],
        )

    def test_partial_and_pending_smoke_statuses_stay_literal(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                    status="partial",
                ),
                "browse-b": self.smoke_report(
                    item_id="1002",
                    browse_variant_key="browse-b",
                    class_key="mage",
                    spec_key="fire",
                    status="pending",
                ),
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(),
            smoke,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["ledger"]["browse-a"]["status"],
            "partial",
        )
        self.assertEqual(
            report["ledger"]["browse-b"]["status"],
            "pending",
        )
        self.assertEqual(report["passed_supported_variant_smoke_count"], 0)
        self.assertIn(
            "GEAR_VARIANT_SIMC_STATUS_NOT_READY",
            report["failureCodes"],
        )

    def test_duplicate_or_extra_ledger_count_mismatch_blocks_before_smoke(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        smoke = RecordingSmoke(
            {
                "browse-a": self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                ),
                "browse-b": self.smoke_report(
                    item_id="1002",
                    browse_variant_key="browse-b",
                    class_key="mage",
                    spec_key="fire",
                ),
            }
        )

        report = build_gear_variant_simc_matrix(
            self.materialization_report(
                expected_unique_variant_count=1,
                unique_variant_materialization_count=1,
            ),
            smoke,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["expected_supported_variant_smoke_count"], 0)
        self.assertEqual(report["passed_supported_variant_smoke_count"], 0)
        self.assertIn(
            "GEAR_VARIANT_SIMC_MATRIX_LEDGER_COUNT_MISMATCH",
            report["failureCodes"],
        )
        self.assertEqual(smoke.calls, [])

    def test_report_ids_are_deterministic(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)

        first = build_gear_variant_simc_matrix(
            self.materialization_report(
                ledger={
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        materialized_browse_variant_key="browse-a",
                    )
                }
            ),
            RecordingSmoke(
                {
                    "browse-a": self.smoke_report(
                        item_id="1001",
                        browse_variant_key="browse-a",
                        class_key="mage",
                        spec_key="frost",
                    )
                }
            ),
        )
        second = build_gear_variant_simc_matrix(
            self.materialization_report(
                ledger={
                    "browse-a": self.materialization_entry(
                        item_id="1001",
                        class_key="mage",
                        spec_key="frost",
                        slot="head",
                        materialized_browse_variant_key="browse-a",
                    )
                }
            ),
            RecordingSmoke(
                {
                    "browse-a": self.smoke_report(
                        item_id="1001",
                        browse_variant_key="browse-a",
                        class_key="mage",
                        spec_key="frost",
                    )
                }
            ),
        )

        self.assertEqual(first["reportId"], second["reportId"])


if __name__ == "__main__":
    unittest.main()
