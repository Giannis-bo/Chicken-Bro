import copy
import json
import unittest

from server.simc_support_policy import SIMC_SPECIALIZATION_UNSUPPORTED_CODE

try:
    from server.gear_variant_simc_matrix import (
        GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION,
        build_gear_variant_simc_matrix,
        build_s2_variant_identity_report,
    )
except ModuleNotFoundError:
    GEAR_VARIANT_SIMC_MATRIX_SCHEMA_REVISION = None
    build_gear_variant_simc_matrix = None
    build_s2_variant_identity_report = None


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
    def s2_variant(self, **overrides):
        row = {
            "seasonRevision": "season-midnight-season-2:fixture",
            "simcRuntimeRevision": "simc:12.1.0.69214:fixture",
            "itemId": "s2-1001",
            "variantKey": "variant-a",
            "rowFamily": "browse",
            "progressionState": {
                "kind": "upgrade_track",
                "trackKey": "hero",
                "rank": 1,
                "maxRank": 6,
            },
            "itemLevel": 305,
            "bonus_id": "21001/21002",
            "staticStats": {
                "stamina": 200,
                "intellect": 100,
                "haste_rating": 40,
                "leech_rating": 2,
            },
        }
        row.update(overrides)
        return row

    def test_s2_variant_missing_runtime_or_core_facts_is_blocked(self):
        self.assertIsNotNone(build_s2_variant_identity_report)
        report = build_s2_variant_identity_report(
            [self.s2_variant(itemLevel=None)],
            season_revision="season-midnight-season-2:fixture",
            simc_runtime_revision="",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "GEAR_VARIANT_SIMC_RUNTIME_REVISION_MISSING",
            report["failureCodes"],
        )
        self.assertIn("GEAR_VARIANT_ITEM_LEVEL_MISSING", report["failureCodes"])

    def test_s2_variant_rejects_s1_row_without_normalizing_it(self):
        self.assertIsNotNone(build_s2_variant_identity_report)
        report = build_s2_variant_identity_report(
            [
                self.s2_variant(
                    seasonRevision="season-midnight-season-1:legacy"
                )
            ],
            season_revision="season-midnight-season-2:fixture",
            simc_runtime_revision="simc:12.1.0.69214:fixture",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "GEAR_VARIANT_IDENTITY_MIXED_REVISION",
            report["failureCodes"],
        )
        self.assertEqual(report["rows"], [])

    def test_s2_variant_collapses_tertiary_only_equivalent_observations(self):
        self.assertIsNotNone(build_s2_variant_identity_report)
        first = self.s2_variant()
        second = self.s2_variant(
            variantKey="variant-b",
            staticStats={
                "stamina": 200,
                "intellect": 100,
                "haste_rating": 40,
                "leech_rating": 9,
            },
        )

        report = build_s2_variant_identity_report(
            [first, second],
            season_revision="season-midnight-season-2:fixture",
            simc_runtime_revision="simc:12.1.0.69214:fixture",
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["uniqueVariantCount"], 1)
        self.assertEqual(report["rows"][0]["observationCount"], 2)

    def test_s2_variant_conflicting_core_facts_is_blocked_without_first_row_wins(self):
        self.assertIsNotNone(build_s2_variant_identity_report)
        report = build_s2_variant_identity_report(
            [
                self.s2_variant(),
                self.s2_variant(
                    variantKey="variant-b",
                    itemLevel=308,
                ),
            ],
            season_revision="season-midnight-season-2:fixture",
            simc_runtime_revision="simc:12.1.0.69214:fixture",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "GEAR_VARIANT_CANONICAL_DUPLICATE",
            report["failureCodes"],
        )
        self.assertEqual(report["rows"], [])

    def assert_report_contract(self, report, *, expected_failure_code):
        self.assertEqual(
            set(report),
            {
                "schemaRevision",
                "status",
                "expected_supported_variant_smoke_count",
                "passed_supported_variant_smoke_count",
                "supported_variant_simc_smoke_count",
                "failureCodes",
                "failureSamples",
                "ledger",
                "reportId",
            },
        )
        self.assertEqual(
            report["schemaRevision"],
            "gear-variant-simc-matrix-v1",
        )
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["failureCodes"],
            [expected_failure_code],
        )
        self.assertEqual(
            report["supported_variant_simc_smoke_count"],
            report["passed_supported_variant_smoke_count"],
        )
        self.assertGreaterEqual(
            report["expected_supported_variant_smoke_count"],
            report["passed_supported_variant_smoke_count"],
        )
        self.assertEqual(
            [sample["code"] for sample in report["failureSamples"]],
            [expected_failure_code],
        )
        self.assertEqual(
            report["failureSamples"],
            [
                {
                    "code": expected_failure_code,
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                }
            ],
        )
        self.assertEqual(
            json.loads(json.dumps(report, ensure_ascii=False, sort_keys=True)),
            report,
        )

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

    def test_smoke_callback_exception_is_deterministic_blocker_with_zero_passes(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        materialization = self.materialization_report(
            ledger={
                "browse-a": self.materialization_entry(
                    item_id="1001",
                    class_key="mage",
                    spec_key="frost",
                    slot="head",
                    materialized_browse_variant_key="browse-a",
                )
            }
        )

        first_smoke = RecordingSmoke({"browse-a": RuntimeError("simc failed")})
        second_smoke = RecordingSmoke({"browse-a": RuntimeError("simc failed")})
        first = build_gear_variant_simc_matrix(materialization, first_smoke)
        second = build_gear_variant_simc_matrix(materialization, second_smoke)

        self.assertEqual(first, second)
        self.assert_report_contract(
            first,
            expected_failure_code="GEAR_VARIANT_SIMC_CALLBACK_EXCEPTION",
        )
        self.assertEqual(first["expected_supported_variant_smoke_count"], 1)
        self.assertEqual(first["passed_supported_variant_smoke_count"], 0)
        self.assertEqual(first["supported_variant_simc_smoke_count"], 0)
        self.assertEqual(first_smoke.calls, [
            {
                "itemId": "1001",
                "browseVariantKey": "browse-a",
                "classKey": "mage",
                "specKey": "frost",
                "slot": "head",
            }
        ])
        self.assertEqual(first["ledger"]["browse-a"]["status"], "blocked")
        self.assertEqual(
            first["ledger"]["browse-a"]["failureCodes"],
            ["GEAR_VARIANT_SIMC_CALLBACK_EXCEPTION"],
        )

    def test_invalid_real_run_fields_have_exact_deterministic_blockers(self):
        self.assertIsNotNone(build_gear_variant_simc_matrix)
        cases = [
            (
                "ran-false",
                {"ran": False},
                None,
                "GEAR_VARIANT_SIMC_RAN_NOT_TRUE",
            ),
            (
                "timed-out",
                {"timed_out": True},
                None,
                "GEAR_VARIANT_SIMC_TIMED_OUT",
            ),
            (
                "runtime-revision-missing",
                {},
                "simcRuntimeRevision",
                "GEAR_VARIANT_SIMC_RUNTIME_REVISION_MISSING",
            ),
            (
                "runtime-revision-empty",
                {"simc_runtime_revision": ""},
                None,
                "GEAR_VARIANT_SIMC_RUNTIME_REVISION_MISSING",
            ),
        ]

        for name, overrides, missing_field, expected_failure_code in cases:
            with self.subTest(name=name):
                smoke_report = self.smoke_report(
                    item_id="1001",
                    browse_variant_key="browse-a",
                    class_key="mage",
                    spec_key="frost",
                    **overrides,
                )
                if missing_field:
                    smoke_report.pop(missing_field)
                materialization = self.materialization_report(
                    ledger={
                        "browse-a": self.materialization_entry(
                            item_id="1001",
                            class_key="mage",
                            spec_key="frost",
                            slot="head",
                            materialized_browse_variant_key="browse-a",
                        )
                    }
                )
                first = build_gear_variant_simc_matrix(
                    materialization,
                    RecordingSmoke({"browse-a": smoke_report}),
                )
                second = build_gear_variant_simc_matrix(
                    materialization,
                    RecordingSmoke({"browse-a": smoke_report}),
                )

                self.assertEqual(first, second)
                self.assert_report_contract(
                    first,
                    expected_failure_code=expected_failure_code,
                )
                self.assertEqual(first["expected_supported_variant_smoke_count"], 1)
                self.assertEqual(first["passed_supported_variant_smoke_count"], 0)
                self.assertEqual(first["supported_variant_simc_smoke_count"], 0)
                self.assertEqual(
                    first["ledger"]["browse-a"]["failureCodes"],
                    [expected_failure_code],
                )
                self.assertEqual(first["ledger"]["browse-a"]["status"], "blocked")

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
