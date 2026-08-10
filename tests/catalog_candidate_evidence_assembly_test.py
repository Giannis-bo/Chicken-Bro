import copy
import re
import unittest

try:
    from server.catalog_candidate_evidence_assembly import (
        CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION,
        assemble_catalog_candidate_evidence,
    )
except ModuleNotFoundError:
    CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION = None
    assemble_catalog_candidate_evidence = None


class CatalogCandidateEvidenceAssemblyTest(unittest.TestCase):
    def expected_identity(self, **overrides):
        identity = {
            "manifestRevision": "manifest:sha256:" + "1" * 64,
            "pointerGeneration": 35,
            "gearCatalogRevision": "gear-catalog:sha256:" + "2" * 64,
            "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "3" * 64,
            "simcRuntimeRevision": "simc:" + "4" * 40,
        }
        identity.update(overrides)
        return identity

    def catalog(self, **overrides):
        report = {
            "status": "verified",
            "catalogRevision": self.expected_identity()["gearCatalogRevision"],
            "contentSummary": {
                "exactDerivedVariantCount": 0,
            },
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def catalog_http_report(self, **overrides):
        report = {
            "status": "pass",
            "failureCount": 0,
            "problemCodes": [],
            "gearCatalogRevision": self.expected_identity()["gearCatalogRevision"],
        }
        report.update(overrides)
        return report

    def raw_catalog_http_report(self, **overrides):
        identity = self.expected_identity()
        report = {
            "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
            "status": "pass",
            "bindingMode": "candidate_preview",
            "manifestRevision": identity["manifestRevision"],
            "pointerGeneration": identity["pointerGeneration"],
            "gearReleaseId": "gear-release:sha256:" + "5" * 64,
            "communityReleaseId": "community-release:sha256:" + "6" * 64,
            "catalogRevision": identity["gearCatalogRevision"],
            "exactRegistryRevision": identity["gearExactRegistryRevision"],
            "failureCount": 0,
            "failureCodes": {},
            "failureSamples": [],
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "type_unknown_nonportable_visible_count": 0,
            "progression_conflict_count": 0,
            "mixed_revision_count": 0,
            "missing_provenance_count": 0,
        }
        report.update(overrides)
        return report

    def catalog_gate_counts(self, **overrides):
        report = {
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "type_unknown_nonportable_visible_count": 0,
            "progression_conflict_count": 0,
            "mixed_revision_count": 0,
            "missing_provenance_count": 0,
            "manifestRevision": self.expected_identity()["manifestRevision"],
            "pointerGeneration": self.expected_identity()["pointerGeneration"],
            "gearCatalogRevision": self.expected_identity()["gearCatalogRevision"],
        }
        report.update(overrides)
        return report

    def materialization_report(self, **overrides):
        report = {
            "schemaRevision": "gear-variant-materialization-matrix-v1",
            "status": "verified",
            "expected_unique_variant_count": 4,
            "materialized_unique_variant_count": 4,
            "unique_variant_materialization_count": 4,
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "missing_provenance_count": 0,
            "failureCodes": [],
            "failureSamples": [],
            "ledger": {},
        }
        report.update(overrides)
        return report

    def variant_simc_report(self, **overrides):
        report = {
            "schemaRevision": "gear-variant-simc-matrix-v1",
            "status": "verified",
            "expected_supported_variant_smoke_count": 4,
            "passed_supported_variant_smoke_count": 4,
            "supported_variant_simc_smoke_count": 4,
            "failureCodes": [],
            "failureSamples": [],
            "ledger": {},
            "gearCatalogRevision": self.expected_identity()["gearCatalogRevision"],
            "gearExactRegistryRevision": self.expected_identity()[
                "gearExactRegistryRevision"
            ],
            "simcRuntimeRevision": self.expected_identity()["simcRuntimeRevision"],
        }
        report.update(overrides)
        return report

    def simc_execution_matrix_report(self, **overrides):
        identity = self.expected_identity()
        report = {
            "status": "pass",
            "manifestRevision": identity["manifestRevision"],
            "pointerGeneration": identity["pointerGeneration"],
            "gearCatalogRevision": identity["gearCatalogRevision"],
            "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
            "simcRuntimeRevision": identity["simcRuntimeRevision"],
            "supported": {
                "expectedSpecCount": 26,
                "profileReadySpecCount": 26,
                "executedSpecCount": 26,
                "dpsMetricSpecCount": 26,
            },
            "unsupported": {
                "expectedSpecCount": 14,
                "deterministicallyBlockedSpecCount": 14,
            },
            "failureCount": 0,
            "failureCodes": {},
            "failureSamples": [],
        }
        report.update(overrides)
        return report

    def exact_registry_report(self, **overrides):
        report = {
            "schemaRevision": "gear-exact-item-registry-v1",
            "status": "verified",
            "registryRevision": self.expected_identity()["gearExactRegistryRevision"],
            "gearExactRegistryRevision": self.expected_identity()[
                "gearExactRegistryRevision"
            ],
            "problemCodes": [],
        }
        report.update(overrides)
        return report

    def pointer(self, **overrides):
        pointer = {
            "generation": self.expected_identity()["pointerGeneration"],
            "manifestRevision": self.expected_identity()["manifestRevision"],
            "gearCatalogRevision": self.expected_identity()["gearCatalogRevision"],
            "gearExactRegistryRevision": self.expected_identity()[
                "gearExactRegistryRevision"
            ],
        }
        pointer.update(overrides)
        return pointer

    def assemble(self, **overrides):
        payload = {
            "catalog": self.catalog(),
            "catalog_http_report": self.catalog_http_report(),
            "catalog_gate_counts": self.catalog_gate_counts(),
            "materialization_report": self.materialization_report(),
            "variant_simc_report": self.variant_simc_report(),
            "simc_execution_matrix_report": self.simc_execution_matrix_report(),
            "exact_registry_report": self.exact_registry_report(),
            "expected_identity": self.expected_identity(),
            "pointer_before": self.pointer(),
            "pointer_after": self.pointer(),
        }
        payload.update(overrides)
        return assemble_catalog_candidate_evidence(**payload)

    def test_happy_assembly_returns_verified_report_with_nine_machine_fields(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)
        self.assertEqual(
            CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION,
            "gear-catalog-candidate-evidence-v1",
        )

        report = self.assemble()

        self.assertEqual(report["schemaRevision"], CATALOG_CANDIDATE_EVIDENCE_SCHEMA_REVISION)
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["problems"], [])
        self.assertEqual(
            {
                "exact_derived_browse_count": report["exact_derived_browse_count"],
                "catalog_non_simulatable_count": report["catalog_non_simulatable_count"],
                "silent_default_fill_count": report["silent_default_fill_count"],
                "type_unknown_nonportable_visible_count": report[
                    "type_unknown_nonportable_visible_count"
                ],
                "progression_conflict_count": report["progression_conflict_count"],
                "mixed_revision_count": report["mixed_revision_count"],
                "missing_provenance_count": report["missing_provenance_count"],
                "unique_variant_materialization_count": report[
                    "unique_variant_materialization_count"
                ],
                "supported_variant_simc_smoke_count": report[
                    "supported_variant_simc_smoke_count"
                ],
            },
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
        self.assertEqual(report["expectedIdentity"], self.expected_identity())
        self.assertTrue(report["pointerStable"])
        self.assertEqual(report["componentStatuses"]["catalog_http_report"], "pass")
        self.assertEqual(
            report["componentStatuses"]["simc_execution_matrix_report"], "pass"
        )
        self.assertEqual(
            report["componentEvidence"]["catalog_http_report"]["status"],
            "pass",
        )
        self.assertEqual(
            report["componentEvidence"]["simc_execution_matrix_report"]["status"],
            "pass",
        )
        self.assertRegex(
            report["reportId"],
            r"^gear-catalog-candidate-evidence:sha256:[0-9a-f]{64}$",
        )

    def test_missing_explicit_count_blocks_instead_of_inferring_zero(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        counts = self.catalog_gate_counts()
        counts.pop("missing_provenance_count")

        report = self.assemble(catalog_gate_counts=counts)

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            {
                "code": "CANDIDATE_GATE_FIELD_MISSING",
                "message": "Missing required field catalog_http_report.missing_provenance_count",
                "field": "catalog_http_report.missing_provenance_count",
            },
            report["problems"],
        )

    def test_http_pass_is_translated_only_when_failure_count_is_zero(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report = self.assemble(
            catalog_http_report=self.catalog_http_report(
                status="pass",
                failureCount=0,
            )
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["componentStatuses"]["catalog_http_report"], "pass")
        self.assertEqual(
            report["componentEvidence"]["catalog_http_report"]["failureCount"],
            0,
        )

    def test_raw_http_matrix_exact_registry_alias_blocks_mismatch_and_preserves_failure_codes(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        raw_report = self.raw_catalog_http_report(
            failureCodes={"CATALOG_HTTP_RAW_EVIDENCE": 1}
        )
        assembled = self.assemble(catalog_http_report=raw_report)

        self.assertEqual(
            assembled["componentEvidence"]["catalog_http_report"]["failureCodes"],
            {"CATALOG_HTTP_RAW_EVIDENCE": 1},
        )

        mismatched_report = copy.deepcopy(raw_report)
        mismatched_report["exactRegistryRevision"] = (
            "gear-exact-registry:sha256:" + "9" * 64
        )
        blocked = self.assemble(catalog_http_report=mismatched_report)

        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(
            any(
                problem["code"] == "CANDIDATE_EVIDENCE_IDENTITY_MISMATCH"
                and problem["component"] == "catalog_http_report"
                and problem["field"] == "gearExactRegistryRevision"
                and problem["actual"] == mismatched_report["exactRegistryRevision"]
                for problem in blocked["problems"]
            )
        )

    def test_raw_failure_codes_are_forwarded_as_deterministic_component_problem_codes(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        raw_report = self.raw_catalog_http_report(
            status="blocked",
            failureCount=1,
            failureCodes={
                "CATALOG_MANIFEST_MISMATCH": 1,
                "CATALOG_EXACT_REGISTRY_MISMATCH": 1,
            },
        )
        reordered_report = copy.deepcopy(raw_report)
        reordered_report["failureCodes"] = {
            "CATALOG_EXACT_REGISTRY_MISMATCH": 1,
            "CATALOG_MANIFEST_MISMATCH": 1,
        }

        report = self.assemble(catalog_http_report=raw_report)
        reordered = self.assemble(catalog_http_report=reordered_report)

        self.assertEqual(report["reportId"], reordered["reportId"])
        self.assertIn(
            {
                "code": "CANDIDATE_GATE_IDENTITY_PROBLEM",
                "message": "catalog_http_report reports an identity blocker",
                "report": "catalog_http_report",
                "problemCode": "CATALOG_EXACT_REGISTRY_MISMATCH",
            },
            report["problems"],
        )
        self.assertEqual(
            report["componentEvidence"]["catalog_http_report"]["failureCodes"],
            raw_report["failureCodes"],
        )

    def test_partial_exact_registry_preserves_literal_status(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        exact = self.exact_registry_report(
            status="partial",
            problemCodes=["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
        )
        original = copy.deepcopy(exact)

        report = self.assemble(exact_registry_report=exact)

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["componentStatuses"]["exact_registry_report"], "partial")
        self.assertEqual(report["componentEvidence"]["exact_registry_report"], original)
        self.assertIn(
            "CANDIDATE_GATE_REPORT_STATUS_NOT_VERIFIED",
            {problem["code"] for problem in report["problems"]},
        )

    def test_nonzero_gate_count_blocks_candidate(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report = self.assemble(
            catalog_gate_counts=self.catalog_gate_counts(
                progression_conflict_count=1
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            {
                "code": "CANDIDATE_GATE_METRIC_NONZERO",
                "message": "progression_conflict_count must be zero for a verified candidate",
                "field": "progression_conflict_count",
                "value": 1,
            },
            report["problems"],
        )

    def test_existing_26_14_simc_mismatch_blocks_assembly(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report = self.assemble(
            simc_execution_matrix_report=self.simc_execution_matrix_report(
                supported={
                    "expectedSpecCount": 26,
                    "profileReadySpecCount": 25,
                    "executedSpecCount": 26,
                    "dpsMetricSpecCount": 26,
                }
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "CANDIDATE_EVIDENCE_SIMC_26_14_SUPPORTED_COUNT_MISMATCH",
            {problem["code"] for problem in report["problems"]},
        )

    def test_pointer_drift_blocks_and_marks_pointer_unstable(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report = self.assemble(
            pointer_after=self.pointer(generation=36),
        )

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["pointerStable"])
        self.assertIn(
            "CANDIDATE_EVIDENCE_POINTER_DRIFT",
            {problem["code"] for problem in report["problems"]},
        )

    def test_mixed_identity_blocks_even_when_counts_are_zero(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report = self.assemble(
            simc_execution_matrix_report=self.simc_execution_matrix_report(
                gearCatalogRevision="gear-catalog:sha256:" + "9" * 64
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "CANDIDATE_EVIDENCE_IDENTITY_MISMATCH",
            {problem["code"] for problem in report["problems"]},
        )

    def test_report_id_is_deterministic_and_literal_statuses_are_preserved(self):
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        report_a = self.assemble(
            exact_registry_report=self.exact_registry_report(status="UNVERIFIED")
        )
        report_b = self.assemble(
            exact_registry_report=self.exact_registry_report(status="UNVERIFIED")
        )
        pending_report = self.assemble(
            exact_registry_report=self.exact_registry_report(status="pending")
        )

        self.assertEqual(report_a["reportId"], report_b["reportId"])
        self.assertEqual(report_a["status"], "UNVERIFIED")
        self.assertEqual(
            report_a["componentStatuses"]["exact_registry_report"],
            "UNVERIFIED",
        )
        self.assertEqual(pending_report["status"], "pending")
        self.assertEqual(
            pending_report["componentStatuses"]["exact_registry_report"],
            "pending",
        )


if __name__ == "__main__":
    unittest.main()
