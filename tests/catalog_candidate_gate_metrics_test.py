import copy
import unittest

try:
    from server.catalog_candidate_gate_metrics import (
        REQUIRED_CANDIDATE_GATE_FIELDS,
        build_candidate_gate_metrics,
    )
except ModuleNotFoundError:
    REQUIRED_CANDIDATE_GATE_FIELDS = None
    build_candidate_gate_metrics = None


class CatalogCandidateGateMetricsTest(unittest.TestCase):
    def catalog(self, exact_derived_browse_count=0, status="verified"):
        return {
            "status": status,
            "contentSummary": {
                "exactDerivedVariantCount": exact_derived_browse_count,
            },
            "problemCodes": [],
        }

    def catalog_http_report(self, **overrides):
        report = {
            "status": "verified",
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "type_unknown_nonportable_visible_count": 0,
            "progression_conflict_count": 0,
            "mixed_revision_count": 0,
            "missing_provenance_count": 0,
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def materialization_report(self, **overrides):
        report = {
            "status": "verified",
            "unique_variant_materialization_count": 4,
            "expected_unique_variant_count": 4,
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def simc_report(self, **overrides):
        report = {
            "status": "verified",
            "passed_supported_variant_smoke_count": 4,
            "expected_supported_variant_smoke_count": 4,
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def exact_registry_report(self, **overrides):
        report = {
            "status": "verified",
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def test_verified_candidate_returns_nine_machine_gate_metrics(self):
        self.assertIsNotNone(build_candidate_gate_metrics)
        self.assertEqual(
            REQUIRED_CANDIDATE_GATE_FIELDS,
            (
                "exact_derived_browse_count",
                "catalog_non_simulatable_count",
                "silent_default_fill_count",
                "type_unknown_nonportable_visible_count",
                "progression_conflict_count",
                "mixed_revision_count",
                "missing_provenance_count",
                "unique_variant_materialization_count",
                "supported_variant_simc_smoke_count",
            ),
        )

        result = build_candidate_gate_metrics(
            self.catalog(),
            self.catalog_http_report(),
            self.materialization_report(),
            self.simc_report(),
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["metrics"],
            {
                "exact_derived_browse_count": 0,
                "catalog_non_simulatable_count": 0,
                "silent_default_fill_count": 0,
                "type_unknown_nonportable_visible_count": 0,
                "progression_conflict_count": 0,
                "mixed_revision_count": 0,
                "missing_provenance_count": 0,
                "unique_variant_materialization_count": 4,
                "supported_variant_simc_smoke_count": 4,
            },
        )
        self.assertEqual(result["problems"], [])
        self.assertEqual(
            result["reportStatuses"],
            {
                "catalog": "verified",
                "catalog_http_report": "verified",
                "materialization_report": "verified",
                "simc_report": "verified",
            },
        )

    def test_missing_explicit_report_field_is_blocked_instead_of_zero_filled(self):
        self.assertIsNotNone(build_candidate_gate_metrics)

        materialization_report = self.materialization_report()
        materialization_report.pop("expected_unique_variant_count")

        result = build_candidate_gate_metrics(
            self.catalog(),
            self.catalog_http_report(),
            materialization_report,
            self.simc_report(),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["metrics"], {})
        self.assertEqual(
            result["problems"][0]["code"],
            "CANDIDATE_GATE_FIELD_MISSING",
        )
        self.assertEqual(
            result["problems"][0]["field"],
            "materialization_report.expected_unique_variant_count",
        )

    def test_coverage_count_mismatch_blocks_verification(self):
        self.assertIsNotNone(build_candidate_gate_metrics)

        result = build_candidate_gate_metrics(
            self.catalog(),
            self.catalog_http_report(),
            self.materialization_report(
                unique_variant_materialization_count=3,
                expected_unique_variant_count=4,
            ),
            self.simc_report(
                passed_supported_variant_smoke_count=2,
                expected_supported_variant_smoke_count=4,
            ),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            {problem["code"] for problem in result["problems"]},
            {
                "CANDIDATE_GATE_MATERIALIZATION_COVERAGE_MISMATCH",
                "CANDIDATE_GATE_SIMC_COVERAGE_MISMATCH",
            },
        )
        self.assertEqual(
            result["metrics"]["unique_variant_materialization_count"],
            3,
        )
        self.assertEqual(
            result["metrics"]["supported_variant_simc_smoke_count"],
            2,
        )

    def test_exact_registry_partial_status_and_problem_codes_are_preserved(self):
        self.assertIsNotNone(build_candidate_gate_metrics)

        report = self.exact_registry_report(
            status="partial",
            problemCodes=["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        original = copy.deepcopy(report)

        result = build_candidate_gate_metrics(
            self.catalog(),
            self.catalog_http_report(),
            self.materialization_report(),
            self.simc_report(),
            exact_registry_report=report,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["reportStatuses"]["exact_registry_report"],
            "partial",
        )
        self.assertEqual(
            result["reportProblemCodes"]["exact_registry_report"],
            ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        self.assertEqual(
            result["problems"][0]["code"],
            "CANDIDATE_GATE_REPORT_STATUS_NOT_VERIFIED",
        )
        self.assertEqual(report, original)


if __name__ == "__main__":
    unittest.main()
