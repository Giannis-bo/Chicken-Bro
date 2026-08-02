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
            },
        }

    def test_eval_runner_accepts_only_revisioned_deidentified_cases(self):
        cases = load_chickenbro_eval_cases(FIXTURE)

        self.assertEqual(4, len(cases))
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


if __name__ == "__main__":
    unittest.main()
