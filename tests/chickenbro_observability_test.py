import json
import unittest

from server.chickenbro_observability import (
    PROJECTION_SCHEMA_REVISION,
    TRACE_SCHEMA_REVISION,
    build_chickenbro_agent_trace,
    deidentify_chickenbro_agent_trace,
    validate_chickenbro_agent_trace,
)


class ChickenbroObservabilityTest(unittest.TestCase):
    def successful_result(self):
        return {
            "answer": {"answer": "SECRET ASSISTANT ANSWER"},
            "validation": {"status": "passed"},
            "model": {"status": "succeeded"},
        }

    def bounded_context(self, *, source_evidence=None, message="SECRET RAW USER MESSAGE"):
        return {
            "message": message,
            "conversationHistory": [{"role": "user", "content": "SECRET HISTORY"}],
            "topic": {"status": "in_scope", "reason": "wow_topic"},
            "requestContext": {
                "productPhase": "retail",
                "region": "cn",
                "classKey": "deathknight",
                "specKey": "frost",
                "scenarioKey": "mythic_plus",
                "characterName": "SECRET CHARACTER",
                "realm": "SECRET REALM",
            },
            "sourceEvidence": source_evidence
            if source_evidence is not None
            else [
                {
                    "sourceKey": "raiderio",
                    "status": "source_reference",
                    "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
                    "facts": [{"summary": "SECRET SOURCE FACT"}],
                    "sourceUrl": "https://example.invalid/private",
                }
            ],
        }

    def build_trace(self, **overrides):
        values = {
            "bounded_context": self.bounded_context(),
            "agent_result": self.successful_result(),
            "error": "",
            "latency_ms": 1200,
            "created_at": "2026-08-02T00:00:00+00:00",
        }
        values.update(overrides)
        return build_chickenbro_agent_trace(**values)

    def test_builds_structured_trace_without_copying_chat_or_answer_text(self):
        trace = self.build_trace()

        encoded = json.dumps(trace, ensure_ascii=False)
        self.assertEqual(TRACE_SCHEMA_REVISION, trace["schemaRevision"])
        self.assertEqual("succeeded", trace["answerStatus"])
        self.assertEqual(["source:raiderio:v1"], trace["selectedCapabilityIds"])
        self.assertEqual(
            ["raiderio:deathknight:frost:mythic_plus"],
            trace["evidenceRefs"],
        )
        for forbidden in (
            "SECRET RAW USER MESSAGE",
            "SECRET HISTORY",
            "SECRET SOURCE FACT",
            "SECRET ASSISTANT ANSWER",
            "SECRET CHARACTER",
            "SECRET REALM",
            "https://example.invalid/private",
        ):
            self.assertNotIn(forbidden, encoded)
        for identity_key in (
            "traceId",
            "ownerId",
            "userId",
            "sessionId",
            "userMessageId",
            "agentJobId",
        ):
            self.assertNotIn(identity_key, trace)

    def test_maps_tool_and_validation_failures_to_bounded_signal_codes(self):
        trace = self.build_trace(
            bounded_context=self.bounded_context(
                source_evidence=[
                    {
                        "sourceKey": "raiderio",
                        "status": "blocked",
                        "evidenceRefs": [],
                    }
                ]
            ),
            agent_result={
                "validation": {"status": "failed"},
                "model": {"status": "failed"},
            },
            error="chickenbro model output rejected: model_output_invalid: unknown evidence ref",
        )

        codes = {item["code"] for item in trace["outcomeSignals"]}
        self.assertEqual("failed", trace["answerStatus"])
        self.assertTrue(
            {
                "model_failed",
                "tool_failed",
                "evidence_missing",
                "schema_invalid",
                "verification_conflict",
            }.issubset(codes)
        )

    def test_does_not_infer_explicit_correction_from_user_text(self):
        trace = self.build_trace(
            bounded_context=self.bounded_context(
                source_evidence=[],
                message="不对，现在明确是 12.0.7",
            )
        )

        codes = {item["code"] for item in trace["outcomeSignals"]}
        self.assertNotIn("explicit_correction", codes)
        self.assertEqual({"answer_succeeded"}, codes)

    def test_deidentified_projection_removes_direct_references_and_exact_time(self):
        trace = self.build_trace()
        projection = deidentify_chickenbro_agent_trace(trace)

        encoded = json.dumps(projection, ensure_ascii=False)
        self.assertEqual(PROJECTION_SCHEMA_REVISION, projection["schemaRevision"])
        self.assertEqual("le_5s", projection["latencyBucket"])
        self.assertNotIn("evidenceRefs", projection)
        self.assertNotIn("createdAt", projection)
        self.assertNotIn("raiderio:deathknight:frost:mythic_plus", encoded)
        self.assertNotIn("2026-08-02T00:00:00+00:00", encoded)
        self.assertNotIn("SECRET", encoded)

    def test_unknown_scope_slugs_cannot_become_deidentified_dimensions(self):
        bounded_context = self.bounded_context()
        bounded_context["topic"]["status"] = "secret_topic_slug"
        bounded_context["requestContext"].update(
            {
                "productPhase": "secret_phase_slug",
                "region": "secret_region_slug",
                "classKey": "secret_player_name",
                "specKey": "secret_character_name",
                "scenarioKey": "secret_scenario_slug",
            }
        )

        trace = self.build_trace(bounded_context=bounded_context)
        projection = deidentify_chickenbro_agent_trace(trace)
        encoded = json.dumps(projection, ensure_ascii=False)

        self.assertEqual(
            {
                "topicStatus": "",
                "productPhase": "",
                "region": "",
                "classKey": "",
                "specKey": "",
                "scenarioKey": "",
            },
            trace["requestScope"],
        )
        self.assertNotIn("secret_", encoded)

    def test_rejects_unknown_fields_and_free_text_signal_payloads(self):
        trace = self.build_trace()
        trace["rawAnswer"] = "must not persist"
        with self.assertRaisesRegex(ValueError, "trace keys"):
            validate_chickenbro_agent_trace(trace)

        trace = self.build_trace()
        trace["outcomeSignals"] = [
            {"code": "model_failed", "severity": "error", "detail": "raw exception"}
        ]
        with self.assertRaisesRegex(ValueError, "outcome signal"):
            validate_chickenbro_agent_trace(trace)

    def test_drops_unknown_evidence_shapes_and_wcl_report_identity(self):
        trace = self.build_trace(
            bounded_context=self.bounded_context(
                source_evidence=[
                    {
                        "sourceKey": "warcraftlogs",
                        "status": "verified",
                        "evidenceRefs": [
                            "wcl.report",
                            "wcl:ABC123",
                            "https://www.warcraftlogs.com/reports/ABC123",
                            "template:private-template-id",
                        ],
                    }
                ]
            )
        )

        self.assertEqual(["wcl.report"], trace["evidenceRefs"])
        self.assertEqual(1, trace["toolStatuses"][0]["evidenceCount"])

    def test_rejects_naive_created_at_and_invalid_capability_id(self):
        trace = self.build_trace()
        trace["createdAt"] = "2026-08-02T00:00:00"
        with self.assertRaisesRegex(ValueError, "createdAt"):
            validate_chickenbro_agent_trace(trace)

        trace = self.build_trace()
        trace["selectedCapabilityIds"] = ["source:unknown:v1"]
        with self.assertRaisesRegex(ValueError, "capability"):
            validate_chickenbro_agent_trace(trace)


if __name__ == "__main__":
    unittest.main()
