import json
import unittest

from server.chickenbro_observability import (
    PROJECTION_SCHEMA_REVISION,
    PROJECTION_SCHEMA_REVISION_V3,
    PROJECTION_SCHEMA_REVISION_V1,
    RUNTIME_VERSION,
    RUNTIME_VERSION_V3,
    RUNTIME_VERSION_V1,
    TRACE_SCHEMA_REVISION,
    TRACE_SCHEMA_REVISION_V3,
    TRACE_SCHEMA_REVISION_V1,
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

    def bounded_context(
        self,
        *,
        source_evidence=None,
        message="SECRET RAW USER MESSAGE",
        registry_context=None,
    ):
        sources = source_evidence if source_evidence is not None else [
            {
                "sourceKey": "raiderio",
                "status": "source_reference",
                "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
                "facts": [{"summary": "SECRET SOURCE FACT"}],
                "sourceUrl": "https://example.invalid/private",
            }
        ]
        selected = [
            {
                "raiderio": "source:raiderio:v1",
                "warcraftlogs": "source:warcraftlogs:v1",
                "current_wow_sources": "source:current-wow-sources:v1",
            }[row["sourceKey"]]
            for row in sources
            if row.get("sourceKey") in {"raiderio", "warcraftlogs", "current_wow_sources"}
        ]
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
            "sourceEvidence": sources,
            "registryContext": registry_context or {
                "status": "verified",
                "registryVersion": "chickenbro-tools-1",
                "registryReleaseHash": "sha256:c9d49f00695540052d69d8aea15653ffb227dbed4ecdb6db1ebd01f734e4734a",
                "registrySource": "postgres",
                "discoveredCapabilityIds": selected,
                "selectedCapabilityIds": selected,
            },
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
        self.assertEqual(RUNTIME_VERSION, trace["runtimeVersion"])
        self.assertEqual("registry", trace["selectionMode"])
        self.assertEqual("verified", trace["registryStatus"])
        self.assertEqual("chickenbro-tools-1", trace["registryVersion"])
        self.assertEqual("postgres", trace["registrySource"])
        self.assertEqual(["source:raiderio:v1"], trace["discoveredCapabilityIds"])
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

    def test_v5_trace_keeps_only_semantic_question_plan_and_current_source_outcome(self):
        bounded_context = self.bounded_context(
            source_evidence=[
                {
                    "sourceKey": "current_wow_sources",
                    "status": "failed",
                    "evidenceRefs": [],
                    "facts": [{"summary": "SECRET OFFICIAL SOURCE BODY"}],
                }
            ],
            registry_context={
                "status": "verified",
                "registryVersion": "chickenbro-tools-2",
                "registryReleaseHash": "sha256:a25340f6fe51dfa01d956b7d944891de39771694e4fd3b33fb41b4fba2d9a102",
                "registrySource": "postgres",
                "discoveredCapabilityIds": ["source:current-wow-sources:v1"],
                "selectedCapabilityIds": ["source:current-wow-sources:v1"],
            },
        )
        bounded_context["questionFrame"] = {
            "schemaRevision": "chickenbro-question-frame-v1",
            "questionType": "current_research",
            "subject": {"classKey": "paladin", "specKey": "holy", "resolution": "resolved"},
            "scope": {"productPhase": "ptr", "patchVersion": "12.1", "region": "cn", "scenarioKey": ""},
            "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
            "unresolvedFields": ["scenarioKey"],
        }
        bounded_context["capabilityPlan"] = {
            "questionType": "current_research",
            "requestedEvidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
            "selectedCapabilityIds": ["source:current-wow-sources:v1"],
            "unmetEvidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
        }

        trace = self.build_trace(bounded_context=bounded_context)
        projection = deidentify_chickenbro_agent_trace(trace)
        encoded = json.dumps({"trace": trace, "projection": projection}, ensure_ascii=False)

        self.assertEqual("chickenbro-agent-trace-v5", trace["schemaRevision"])
        self.assertEqual("chickenbro-agentic-research-runtime-v1", trace["runtimeVersion"])
        self.assertEqual("current_research", trace["questionType"])
        self.assertEqual("resolved", trace["subjectResolution"])
        self.assertEqual(["official_current_changes", "comparative_strength_signal"], trace["requestedEvidenceNeeds"])
        self.assertEqual(["official_current_changes", "comparative_strength_signal"], trace["unmetEvidenceNeeds"])
        self.assertIn("tool_failed", {signal["code"] for signal in trace["outcomeSignals"]})
        self.assertEqual("chickenbro-trace-projection-v5", projection["schemaRevision"])
        self.assertNotIn("SECRET OFFICIAL SOURCE BODY", encoded)

    def test_trace_v5_keeps_only_allowlisted_evidence_plan_projection(self):
        bounded_context = self.bounded_context(source_evidence=[])
        bounded_context["questionFrame"] = {
            "questionType": "current_research",
            "subject": {"resolution": "resolved"},
            "comparisonScope": "cross_spec",
            "evidenceNeeds": ["comparative_strength_signal"],
        }
        bounded_context["capabilityPlan"] = {
            "requestedEvidenceNeeds": ["comparative_strength_signal"],
            "unmetEvidenceNeeds": ["comparative_strength_signal"],
        }
        bounded_context["evidencePlan"] = {
            "comparisonScope": "cross_spec",
            "facets": [{
                "key": "cross_spec_performance",
                "status": "unavailable",
                "note": "全职业 DPS 横向排名",
            }],
            "outcome": "partial",
        }

        trace = self.build_trace(bounded_context=bounded_context)
        projection = deidentify_chickenbro_agent_trace(trace)
        encoded = json.dumps({"trace": trace, "projection": projection}, ensure_ascii=False)

        self.assertEqual("chickenbro-agent-trace-v5", trace["schemaRevision"])
        self.assertEqual("cross_spec", trace["comparisonScope"])
        self.assertEqual(["cross_spec_performance"], trace["evidenceFacetKeys"])
        self.assertEqual(["unavailable"], trace["evidenceFacetStatuses"])
        self.assertEqual("partial", trace["evidenceOutcome"])
        self.assertEqual("chickenbro-trace-projection-v5", projection["schemaRevision"])
        self.assertNotIn("全职业 DPS 横向排名", encoded)

    def test_trace_v5_projects_only_agentic_execution_metadata(self):
        bounded_context = self.bounded_context(source_evidence=[])
        bounded_context["agenticResearch"] = {
            "status": "completed",
            "turns": [{"turn": 0, "decision": "answer", "toolIds": ["source:raiderio:v1"]}],
            "observations": [{
                "toolId": "source:raiderio:v1",
                "sourceKey": "raiderio",
                "status": "source_reference",
                "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
                "scope": {"scenarioKey": "mythic_plus"},
                "facts": [{"summary": "SECRET AGENTIC FACT"}],
                "limitations": ["SECRET AGENTIC LIMITATION"],
            }],
        }

        trace = self.build_trace(bounded_context=bounded_context)
        projection = deidentify_chickenbro_agent_trace(trace)
        encoded = json.dumps({"trace": trace, "projection": projection}, ensure_ascii=False)

        self.assertEqual("chickenbro-agent-trace-v5", trace["schemaRevision"])
        self.assertEqual("completed", trace["researchStatus"])
        self.assertEqual(1, trace["researchTurnCount"])
        self.assertEqual(["source:raiderio:v1"], trace["plannedToolIds"])
        self.assertEqual(["source_reference"], trace["observationStatuses"])
        self.assertEqual("chickenbro-trace-projection-v5", projection["schemaRevision"])
        self.assertNotIn("SECRET AGENTIC FACT", encoded)
        self.assertNotIn("SECRET AGENTIC LIMITATION", encoded)

    def test_literal_historical_v1_trace_still_validates_and_projects_unchanged(self):
        historical = {
            "schemaRevision": TRACE_SCHEMA_REVISION_V1,
            "runtimeVersion": RUNTIME_VERSION_V1,
            "selectionMode": "fixed_allowlist",
            "requestScope": {
                "topicStatus": "in_scope",
                "productPhase": "retail",
                "region": "cn",
                "classKey": "deathknight",
                "specKey": "frost",
                "scenarioKey": "mythic_plus",
            },
            "discoveredCapabilityIds": ["source:raiderio:v1"],
            "selectedCapabilityIds": ["source:raiderio:v1"],
            "toolStatuses": [
                {
                    "capabilityId": "source:raiderio:v1",
                    "status": "source_reference",
                    "freshnessState": "fresh",
                    "evidenceCount": 1,
                }
            ],
            "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
            "answerStatus": "succeeded",
            "validationStatus": "passed",
            "outcomeSignals": [{"code": "answer_succeeded", "severity": "info"}],
            "latencyMs": 1200,
            "boundedCost": {"status": "not_available"},
            "createdAt": "2026-08-02T00:00:00+00:00",
        }

        validated = validate_chickenbro_agent_trace(historical)
        projection = deidentify_chickenbro_agent_trace(historical)

        self.assertEqual(historical, validated)
        self.assertEqual(PROJECTION_SCHEMA_REVISION_V1, projection["schemaRevision"])
        self.assertNotIn("registryVersion", projection)

    def test_historical_v3_trace_still_validates_and_projects_unchanged(self):
        historical = self.build_trace()
        historical["schemaRevision"] = TRACE_SCHEMA_REVISION_V3
        historical["runtimeVersion"] = RUNTIME_VERSION_V3
        for key in (
            "comparisonScope",
            "evidenceFacetKeys",
            "evidenceFacetStatuses",
            "evidenceOutcome",
            "researchStatus",
            "researchTurnCount",
            "plannedToolIds",
            "observationStatuses",
        ):
            historical.pop(key)

        validated = validate_chickenbro_agent_trace(historical)
        projection = deidentify_chickenbro_agent_trace(historical)

        self.assertEqual(historical, validated)
        self.assertEqual(PROJECTION_SCHEMA_REVISION_V3, projection["schemaRevision"])
        self.assertNotIn("evidenceOutcome", projection)

    def test_v2_rejects_unknown_registry_source_hash_and_selection_drift(self):
        trace = self.build_trace()
        trace["registrySource"] = "client_payload"
        with self.assertRaisesRegex(ValueError, "registry source"):
            validate_chickenbro_agent_trace(trace)

        trace = self.build_trace()
        trace["registryReleaseHash"] = "sha256:" + "0" * 63
        with self.assertRaisesRegex(ValueError, "release hash"):
            validate_chickenbro_agent_trace(trace)

        trace = self.build_trace()
        trace["selectedCapabilityIds"] = ["source:unknown:v1"]
        with self.assertRaisesRegex(ValueError, "undiscovered"):
            validate_chickenbro_agent_trace(trace)

    def test_v2_unavailable_registry_requires_empty_identity_and_selection(self):
        trace = self.build_trace(
            bounded_context=self.bounded_context(
                source_evidence=[],
                registry_context={
                    "status": "unavailable",
                    "registryVersion": "",
                    "registryReleaseHash": "",
                    "registrySource": "",
                    "discoveredCapabilityIds": [],
                    "selectedCapabilityIds": [],
                },
            )
        )
        self.assertEqual("unavailable", trace["registryStatus"])

        trace["registryVersion"] = "stale-client-version"
        with self.assertRaisesRegex(ValueError, "unverified registry identity"):
            validate_chickenbro_agent_trace(trace)

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
