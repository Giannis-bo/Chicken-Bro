import json
import unittest
from pathlib import Path

from server.chickenbro_eval import (
    evaluate_chickenbro_trace_case,
    evaluate_chickenbro_trace_cases,
    load_chickenbro_eval_cases,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chickenbro_trace_eval_cases.json"


class ChickenbroEvalTest(unittest.TestCase):
    def successful_case(self):
        return {
            "schemaRevision": "chickenbro-trace-eval-case-v1",
            "caseId": "synthetic_success",
            "input": {
                "boundedContext": {
                    "topic": {"status": "in_scope"},
                    "requestContext": {
                        "productPhase": "retail",
                        "region": "cn",
                        "classKey": "mage",
                        "specKey": "arcane",
                        "scenarioKey": "mythic_plus",
                    },
                    "sourceEvidence": [],
                    "registryContext": {
                        "status": "verified",
                        "registryVersion": "chickenbro-tools-1",
                        "registryReleaseHash": "sha256:c9d49f00695540052d69d8aea15653ffb227dbed4ecdb6db1ebd01f734e4734a",
                        "registrySource": "postgres",
                        "discoveredCapabilityIds": [],
                        "selectedCapabilityIds": [],
                    },
                },
                "agentResult": {
                    "validation": {"status": "passed"},
                    "model": {"status": "succeeded"},
                },
                "errorCode": "",
                "latencyMs": 200,
            },
            "expect": {
                "answerStatus": "succeeded",
                "requiredSignals": ["answer_succeeded"],
                "forbiddenSignals": ["explicit_correction"],
                "selectedCapabilityIds": [],
                "registryVersion": "chickenbro-tools-1",
            },
        }

    def current_source_failure_case(self):
        return {
            "schemaRevision": "chickenbro-trace-eval-case-v1",
            "caseId": "current_source_failure",
            "input": {
                "boundedContext": {
                    "topic": {"status": "in_scope"},
                    "requestContext": {
                        "productPhase": "ptr",
                        "region": "cn",
                        "classKey": "paladin",
                        "specKey": "holy",
                        "scenarioKey": "",
                    },
                    "sourceEvidence": [
                        {"sourceKey": "current_wow_sources", "status": "failed", "evidenceRefs": []}
                    ],
                    "registryContext": {
                        "status": "verified",
                        "registryVersion": "chickenbro-tools-2",
                        "registryReleaseHash": "sha256:a25340f6fe51dfa01d956b7d944891de39771694e4fd3b33fb41b4fba2d9a102",
                        "registrySource": "postgres",
                        "discoveredCapabilityIds": ["source:current-wow-sources:v1"],
                        "selectedCapabilityIds": ["source:current-wow-sources:v1"],
                    },
                    "questionFrame": {
                        "schemaRevision": "chickenbro-question-frame-v1",
                        "questionType": "current_research",
                        "subject": {"classKey": "paladin", "specKey": "holy", "resolution": "resolved"},
                        "scope": {"productPhase": "ptr", "patchVersion": "12.1", "region": "cn", "scenarioKey": ""},
                        "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
                        "unresolvedFields": ["scenarioKey"],
                    },
                    "capabilityPlan": {
                        "questionType": "current_research",
                        "requestedEvidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
                        "selectedCapabilityIds": ["source:current-wow-sources:v1"],
                        "unmetEvidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
                    },
                },
                "agentResult": {
                    "validation": {"status": "passed"},
                    "model": {"status": "succeeded"},
                },
                "errorCode": "",
                "latencyMs": 2200,
            },
            "expect": {
                "answerStatus": "succeeded",
                "requiredSignals": ["answer_succeeded", "tool_failed", "evidence_missing"],
                "forbiddenSignals": ["explicit_correction"],
                "selectedCapabilityIds": ["source:current-wow-sources:v1"],
                "registryVersion": "chickenbro-tools-2",
            },
        }

    def test_eval_runner_accepts_only_revisioned_deidentified_cases(self):
        cases = load_chickenbro_eval_cases(FIXTURE)

        self.assertEqual(6, len(cases))
        self.assertTrue(
            all(
                case["schemaRevision"] == "chickenbro-trace-eval-case-v1"
                for case in cases
            )
        )
        self.assertEqual(
            {
                "verified_source_success",
                "blocked_source_emits_evidence_missing",
                "invalid_model_schema_emits_schema_invalid",
                "unknown_evidence_emits_verification_conflict",
                "current_official_change_keeps_comparative_gap",
                "current_source_failed_marks_official_gap",
            },
            {case["caseId"] for case in cases},
        )

    def test_eval_summary_fails_when_required_signal_is_missing(self):
        case = self.successful_case()
        case["expect"]["requiredSignals"] = ["evidence_missing"]

        result = evaluate_chickenbro_trace_cases([case])

        self.assertEqual("failed", result["status"])
        self.assertEqual(1, result["failedCount"])
        self.assertEqual(["required_signals"], result["cases"][0]["failures"])

    def test_eval_current_source_failure_preserves_only_semantic_gap_signals(self):
        result = evaluate_chickenbro_trace_case(self.current_source_failure_case())

        self.assertEqual({"caseId", "status", "failures"}, set(result))
        self.assertEqual("passed", result["status"])

    def test_eval_agentic_packet_accepts_only_deidentified_execution_metadata(self):
        case = self.successful_case()
        context = case["input"]["boundedContext"]
        context["registryContext"]["discoveredCapabilityIds"] = ["source:raiderio:v1"]
        context["registryContext"]["selectedCapabilityIds"] = ["source:raiderio:v1"]
        context["questionFrame"] = {
            "schemaRevision": "chickenbro-question-frame-v1",
            "questionType": "current_research",
            "subject": {"classKey": "mage", "specKey": "arcane", "resolution": "resolved"},
            "scope": {"productPhase": "retail", "patchVersion": "", "region": "cn", "scenarioKey": "mythic_plus"},
            "evidenceNeeds": ["comparative_strength_signal"],
            "unresolvedFields": [],
        }
        context["capabilityPlan"] = {
            "questionType": "current_research",
            "requestedEvidenceNeeds": ["comparative_strength_signal"],
            "selectedCapabilityIds": ["source:raiderio:v1"],
            "unmetEvidenceNeeds": [],
        }
        context["agenticResearch"] = {
            "status": "completed",
            "turns": [{"turn": 0, "decision": "answer", "toolIds": ["source:raiderio:v1"]}],
            "observations": [{
                "toolId": "source:raiderio:v1",
                "status": "source_reference",
                "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
            }],
        }
        case["expect"]["selectedCapabilityIds"] = ["source:raiderio:v1"]

        result = evaluate_chickenbro_trace_case(case)

        self.assertEqual("passed", result["status"])

    def test_eval_results_do_not_echo_inputs_or_trace_payloads(self):
        case = self.successful_case()
        result = evaluate_chickenbro_trace_case(case)
        encoded = json.dumps(result, ensure_ascii=False)

        self.assertEqual(
            {"caseId", "status", "failures"},
            set(result),
        )
        self.assertNotIn("boundedContext", encoded)
        self.assertNotIn("requestScope", encoded)
        self.assertNotIn("mage", encoded)

    def test_eval_case_rejects_unknown_keys_and_missing_expectations(self):
        case = self.successful_case()
        case["rawMessage"] = "must not enter eval"
        with self.assertRaisesRegex(ValueError, "eval case keys"):
            evaluate_chickenbro_trace_case(case)

        case = self.successful_case()
        del case["expect"]["forbiddenSignals"]
        with self.assertRaisesRegex(ValueError, "eval expectation keys"):
            evaluate_chickenbro_trace_case(case)

    def test_eval_case_rejects_free_text_input_fields(self):
        case = self.successful_case()
        case["input"]["boundedContext"]["message"] = "raw user text"

        with self.assertRaisesRegex(ValueError, "bounded context keys"):
            evaluate_chickenbro_trace_case(case)

    def test_eval_summary_rejects_empty_or_duplicate_case_sets(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            evaluate_chickenbro_trace_cases([])

        case = self.successful_case()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_chickenbro_trace_cases([case, case])


if __name__ == "__main__":
    unittest.main()
