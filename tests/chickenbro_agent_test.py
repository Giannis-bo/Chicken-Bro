import inspect
import os
import unittest

import server.news_backend as backend
import server.chickenbro_agent as agent
from server.chickenbro_tool_runtime import ChickenbroRegistryRuntime
from tests.chickenbro_registry_test import current_sources_manifest, signed_release


class ChickenbroAgentIntentTest(unittest.TestCase):
    def test_registry_discovery_preserves_raiderio_tool_result(self):
        intent = backend.classify_chickenbro_request("protection warrior build", [])
        payload = {
            "sourceName": "Raider.IO",
            "sourceStatus": "synced",
            "checkedAt": "2099-08-01T10:00:00+00:00",
            "expiresAt": "2099-08-01T16:00:00+00:00",
            "region": "cn",
            "specAggregates": [
                {"classKey": "warrior", "specKey": "protection", "fullName": "Protection Warrior"}
            ],
            "communityTemplates": [],
        }
        expected = agent.build_raiderio_chickenbro_tool_result(payload, intent)
        original_payload = backend.chickenbro_cached_raiderio_payload
        backend.chickenbro_cached_raiderio_payload = lambda: payload
        try:
            loaded = backend.load_chickenbro_source_tool_results(
                "protection warrior build",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: signed_release(),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            backend.chickenbro_cached_raiderio_payload = original_payload

        self.assertEqual([expected], loaded["sourceToolResults"])
        self.assertEqual("verified", loaded["registryContext"]["status"])
        self.assertEqual(["source:raiderio:v1"], loaded["registryContext"]["selectedCapabilityIds"])

    def test_registry_discovery_preserves_wcl_and_general_paths(self):
        log_evidence = {
            "sourceStatus": "verified",
            "reportCode": "ABC123",
            "sourceUrl": "https://www.warcraftlogs.com/reports/ABC123?fight=7",
            "fightId": "7",
            "evidenceRefs": ["wcl.report", "wcl.fight"],
        }
        original_builder = backend.build_wcl_log_evidence
        backend.build_wcl_log_evidence = lambda request: log_evidence
        try:
            loaded = backend.load_chickenbro_source_tool_results(
                "review https://www.warcraftlogs.com/reports/ABC123?fight=7",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: signed_release(),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            backend.build_wcl_log_evidence = original_builder
        general = backend.load_chickenbro_source_tool_results(
            "hello",
            {"region": "cn"},
            include_registry=True,
            registry_loader=lambda: signed_release(),
            registry_runtime=ChickenbroRegistryRuntime(60),
        )

        self.assertEqual(
            [agent.build_wcl_chickenbro_tool_result(log_evidence)],
            loaded["sourceToolResults"],
        )
        self.assertEqual(["source:warcraftlogs:v1"], loaded["registryContext"]["selectedCapabilityIds"])
        self.assertEqual([], general["sourceToolResults"])
        self.assertEqual([], general["registryContext"]["selectedCapabilityIds"])

    def test_current_research_executes_only_the_registered_official_source_adapter(self):
        captured = {}
        expected = {
            "sourceKey": "current_wow_sources",
            "status": "source_reference",
            "facts": [{"kind": "official_change", "summary": "Official holy paladin PTR change."}],
            "evidence": [{"id": "current.blizzard-forums.holy-paladin-121"}],
            "evidenceRefs": ["current.blizzard-forums.holy-paladin-121"],
            "limitations": ["comparative_strength_signal_missing"],
            "nextActions": [],
        }
        original_builder = getattr(backend, "build_current_wow_sources_tool_result", None)

        def fake_current_source(frame, **kwargs):
            captured["frame"] = frame
            captured["kwargs"] = kwargs
            return expected

        backend.build_current_wow_sources_tool_result = fake_current_source
        try:
            loaded = backend.load_chickenbro_source_tool_results(
                "NQ 在 12.1 PTR 强度如何？",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: signed_release(
                    [signed_release()["manifests"][0], signed_release()["manifests"][1], current_sources_manifest()],
                    registryVersion="chickenbro-tools-2",
                    provenance={"kind": "repository_migration", "revision": "0026"},
                ),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            if original_builder is None:
                delattr(backend, "build_current_wow_sources_tool_result")
            else:
                backend.build_current_wow_sources_tool_result = original_builder

        self.assertEqual([expected], loaded["sourceToolResults"])
        self.assertEqual(["source:current-wow-sources:v1"], loaded["registryContext"]["selectedCapabilityIds"])
        self.assertEqual("current_research", captured["frame"]["questionType"])
        self.assertEqual("paladin", captured["frame"]["subject"]["classKey"])
        self.assertEqual("holy", captured["frame"]["subject"]["specKey"])
        self.assertEqual("12.1", captured["frame"]["scope"]["patchVersion"])
        self.assertNotIn("message", str(captured))

    def test_registry_unavailable_or_invalid_never_uses_fixed_allowlist(self):
        original_raiderio = backend.chickenbro_cached_raiderio_payload
        original_wcl = backend.build_wcl_log_evidence
        backend.chickenbro_cached_raiderio_payload = lambda: (_ for _ in ()).throw(
            AssertionError("fixed Raider.IO branch must not run")
        )
        backend.build_wcl_log_evidence = lambda request: (_ for _ in ()).throw(
            AssertionError("fixed WCL branch must not run")
        )
        try:
            unavailable = backend.load_chickenbro_source_tool_results(
                "protection warrior build",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: (_ for _ in ()).throw(ConnectionError("offline")),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
            invalid = backend.load_chickenbro_source_tool_results(
                "review https://www.warcraftlogs.com/reports/ABC123?fight=7",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: signed_release(releaseHash="sha256:" + "0" * 64),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            backend.chickenbro_cached_raiderio_payload = original_raiderio
            backend.build_wcl_log_evidence = original_wcl

        self.assertEqual([], unavailable["sourceToolResults"])
        self.assertEqual(["registry_unavailable"], unavailable["limitations"])
        self.assertEqual("unavailable", unavailable["registryContext"]["status"])
        self.assertEqual([], invalid["sourceToolResults"])
        self.assertEqual(["registry_invalid"], invalid["limitations"])
        self.assertEqual("invalid", invalid["registryContext"]["status"])

    def test_bounded_context_exposes_only_bounded_registry_projection(self):
        bounded = backend.build_chickenbro_bounded_context(
            "protection warrior build",
            {"region": "cn"},
            registry_loader=lambda: signed_release(),
            registry_runtime=ChickenbroRegistryRuntime(60),
        )

        self.assertEqual(
            {
                "status",
                "registryVersion",
                "registryReleaseHash",
                "registrySource",
                "discoveredCapabilityIds",
                "selectedCapabilityIds",
            },
            set(bounded["registryContext"]),
        )
        self.assertNotIn("manifest", str(bounded["registryContext"]).lower())
        self.assertEqual(["source:raiderio:v1"], bounded["registryContext"]["selectedCapabilityIds"])

    def test_protection_warrior_build_question_is_a_community_build_intent(self):
        classifier = getattr(backend, "classify_chickenbro_request", None)

        self.assertIsNotNone(
            classifier,
            "the source agent must classify ordinary WoW questions before choosing a tool",
        )
        intent = classifier("防战现在天赋怎么点，属性怎么搭配，装备哪里获取？", [])

        self.assertEqual("community_build", intent["kind"])
        self.assertEqual("warrior", intent["classKey"])
        self.assertEqual("protection", intent["specKey"])
        self.assertEqual("retail", intent["productPhase"])

    def test_classifier_projects_question_frame_for_current_ptr_research(self):
        intent = backend.classify_chickenbro_request("NQ 在 12.1 PTR 强度如何？", [])

        self.assertEqual("current_research", intent["kind"])
        self.assertEqual("paladin", intent["classKey"])
        self.assertEqual("holy", intent["specKey"])
        self.assertEqual("ptr", intent["productPhase"])
        self.assertEqual("12.1", intent["patchVersion"])
        self.assertEqual(
            ["official_current_changes", "comparative_strength_signal"],
            intent["evidenceNeeds"],
        )

    def test_classifier_recognizes_canonical_specialization_names_beyond_protection_warrior(self):
        intent = backend.classify_chickenbro_request("frost death knight raid build", [])

        self.assertEqual("community_build", intent["kind"])
        self.assertEqual("deathknight", intent["classKey"])
        self.assertEqual("frost", intent["specKey"])

    def test_classifier_carries_recent_user_specialization_to_a_follow_up(self):
        intent = backend.classify_chickenbro_request(
            "and what changes for raid?",
            [
                {"role": "assistant", "content": "I need your specialization."},
                {"role": "user", "content": "frost death knight mythic plus build"},
            ],
        )

        self.assertEqual("community_build", intent["kind"])
        self.assertEqual("deathknight", intent["classKey"])
        self.assertEqual("frost", intent["specKey"])

    def test_expired_raiderio_payload_is_not_promoted_to_source_reference(self):
        intent = backend.classify_chickenbro_request("frost death knight build", [])
        result = agent.build_raiderio_chickenbro_tool_result(
            {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "checkedAt": "2000-01-01T00:00:00+00:00",
                "expiresAt": "2000-01-01T01:00:00+00:00",
                "specAggregates": [
                    {"classKey": "deathknight", "specKey": "frost", "fullName": "Frost Death Knight"}
                ],
            },
            intent,
        )

        self.assertEqual("stale", result["status"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertTrue(any("expired" in item.lower() for item in result["limitations"]))

    def test_chickenbro_runtime_adapter_marks_expired_postgres_cache_stale(self):
        original_postgres_only = backend.postgres_only_runtime_enabled
        original_runtime_payload = backend.runtime_raiderio_payload
        backend.postgres_only_runtime_enabled = lambda: True
        backend.runtime_raiderio_payload = lambda: {
            "sourceStatus": "synced",
            "expiresAt": "2000-01-01T01:00:00+00:00",
        }
        try:
            payload = backend.chickenbro_cached_raiderio_payload()
        finally:
            backend.postgres_only_runtime_enabled = original_postgres_only
            backend.runtime_raiderio_payload = original_runtime_payload

        self.assertEqual("stale", payload["sourceStatus"])

    def test_raiderio_result_is_narrow_and_retains_source_limits(self):
        intent = backend.classify_chickenbro_request("防战现在天赋怎么点？", [])
        builder = getattr(agent, "build_raiderio_chickenbro_tool_result", None)

        self.assertIsNotNone(builder, "the source agent must reduce Raider.IO to a safe tool result")
        result = builder(
            {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "seasonSlug": "season-mn-1",
                "region": "cn",
                "checkedAt": "2099-08-01T10:00:00+00:00",
                "expiresAt": "2099-08-01T16:00:00+00:00",
                "leaderboardUrl": "https://raider.io/mythic-plus-rankings",
                "specAggregates": [
                    {
                        "classKey": "warrior",
                        "specKey": "protection",
                        "fullName": "Protection Warrior",
                        "role": "tank",
                        "sampleCount": 24,
                        "maxKeyLevel": 18,
                        "topRuns": [{"sourceUrl": "https://raider.io/mythic-plus-rankings"}],
                    }
                ],
                "communityTemplates": [
                    {
                        "classKey": "warrior",
                        "specKey": "protection",
                        "scenarioKey": "mythic_plus",
                        "name": "Raider.IO CN +18 Protection Warrior",
                        "heroKey": "colossus",
                        "sourceUrl": "https://raider.io/characters/cn/example/tank",
                        "updatedAt": "2099-08-01T10:00:00+00:00",
                        "rawImportCode": "DO_NOT_PASS_IMPORT_CODE_TO_AGENT",
                    }
                ],
            },
            intent,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["raiderio:warrior:protection:mythic_plus"], result["evidenceRefs"])
        self.assertEqual("Raider.IO", result["evidence"][0]["sourceName"])
        self.assertEqual("colossus", result["facts"][0]["templates"][0]["heroKey"])
        self.assertIn("+18", result["allowedNumbers"])
        self.assertNotIn("DO_NOT_PASS_IMPORT_CODE_TO_AGENT", str(result))
        self.assertTrue(any("do not replace" in item for item in result["limitations"]))

    def test_source_result_enriches_plain_chat_without_client_context(self):
        parameters = inspect.signature(backend.build_chickenbro_bounded_context).parameters

        self.assertIn("source_tool_results", parameters)
        bounded_context = backend.build_chickenbro_bounded_context(
            "防战现在天赋怎么点？",
            {},
            source_tool_results=[
                {
                    "sourceKey": "raiderio",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Protection Warrior Mythic+ samples."}],
                    "evidence": [{"id": "raiderio:warrior:protection:mythic_plus"}],
                    "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
                    "allowedNumbers": ["+18"],
                    "limitations": ["Raider.IO samples are a community reference."],
                }
            ],
        )

        self.assertEqual("warrior", bounded_context["requestContext"]["classKey"])
        self.assertEqual("protection", bounded_context["requestContext"]["specKey"])
        self.assertEqual("source_reference", bounded_context["answerLayer"])
        self.assertEqual("社区来源参考", bounded_context["basisLabel"])
        self.assertIn("raiderio:warrior:protection:mythic_plus", bounded_context["allowedEvidenceRefs"])
        self.assertIn("+18", bounded_context["allowedNumbers"])
        self.assertIn("sourceEvidence", bounded_context["evidencePacket"])

    def test_plain_chat_loads_allowed_raiderio_source_without_client_context(self):
        loader = getattr(backend, "load_chickenbro_source_tool_results", None)

        self.assertIsNotNone(loader, "ordinary chat must resolve its own allowed source tools")
        expected_source = {
            "sourceKey": "raiderio",
            "status": "source_reference",
            "facts": [{"summary": "Current Protection Warrior Mythic+ samples."}],
            "evidence": [{"id": "raiderio:warrior:protection:mythic_plus"}],
            "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
            "limitations": [],
        }
        original_loader = backend.load_chickenbro_source_tool_results
        backend.load_chickenbro_source_tool_results = lambda *args: [expected_source]
        try:
            bounded_context = backend.build_chickenbro_bounded_context("防战现在天赋怎么点？", {})
        finally:
            backend.load_chickenbro_source_tool_results = original_loader

        self.assertEqual([expected_source], bounded_context["sourceEvidence"])

    def test_verified_wcl_evidence_is_compacted_without_raw_events(self):
        builder = getattr(agent, "build_wcl_chickenbro_tool_result", None)

        self.assertIsNotNone(builder, "the source agent must compact optional WCL evidence")
        result = builder(
            {
                "status": "ready",
                "sourceStatus": "verified",
                "reportCode": "ABC123",
                "sourceUrl": "https://www.warcraftlogs.com/reports/ABC123?fight=7",
                "fightId": "7",
                "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
                "eventSummary": {"casts": 42, "damageEvents": 9000},
                "rawEvents": [{"secret": "DO_NOT_PASS_RAW_EVENTS_TO_AGENT"}],
            }
        )

        self.assertEqual("verified", result["status"])
        self.assertEqual(["wcl.report", "wcl.fight", "wcl.events"], result["evidenceRefs"])
        self.assertEqual("ABC123", result["facts"][0]["reportCode"])
        self.assertNotIn("DO_NOT_PASS_RAW_EVENTS_TO_AGENT", str(result))

    def test_wcl_url_uses_optional_wcl_tool_without_raiderio(self):
        wcl_builder = getattr(backend, "build_wcl_log_evidence", None)

        self.assertIsNotNone(wcl_builder, "the backend must expose the official WCL adapter to the source agent")
        original_builder = backend.build_wcl_log_evidence
        backend.build_wcl_log_evidence = lambda request: {
            "status": "ready",
            "sourceStatus": "verified",
            "reportCode": "ABC123",
            "sourceUrl": "https://www.warcraftlogs.com/reports/ABC123?fight=7",
            "fightId": "7",
            "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
        }
        try:
            results = backend.load_chickenbro_source_tool_results(
                "帮我看看 https://www.warcraftlogs.com/reports/ABC123?fight=7 的防战手法",
                {},
                registry_loader=lambda: signed_release(),
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            backend.build_wcl_log_evidence = original_builder

        self.assertEqual(["warcraftlogs"], [item["sourceKey"] for item in results])
        self.assertEqual("verified", results[0]["status"])

    def test_verified_wcl_uses_log_evidence_prompt_not_raiderio_prompt(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "看看这个报告的防战手法",
            {},
            source_tool_results=[
                {
                    "sourceKey": "warcraftlogs",
                    "status": "verified",
                    "facts": [{"reportCode": "ABC123", "summary": "WCL evidence is ready."}],
                    "evidence": [{"id": "wcl.report"}],
                    "evidenceRefs": ["wcl.report"],
                    "limitations": [],
                }
            ],
        )
        prompt = backend.chickenbro_prompt_from_context(bounded_context)

        self.assertEqual("wcl_evidence", bounded_context["answerLayer"])
        self.assertEqual("已基于你的 WCL 日志证据", bounded_context["basisLabel"])
        self.assertIn("WCL 日志证据", prompt)
        self.assertNotIn("Raider.IO 只能说明", prompt)

    def test_enabled_codex_runner_uses_read_only_worker(self):
        worker = getattr(backend, "run_codex_job", None)

        self.assertIsNotNone(worker, "the configured Codex agent must be available to Chickenbro")
        original_flag = os.environ.get("WOW_CHICKENBRO_CODEX_ENABLED")
        original_worker = backend.run_codex_job
        calls = []
        os.environ["WOW_CHICKENBRO_CODEX_ENABLED"] = "1"
        backend.run_codex_job = lambda prompt, **kwargs: calls.append((prompt, kwargs)) or {
            "status": "succeeded",
            "lastMessage": '{"answer":"ok"}',
        }
        try:
            result = backend.default_chickenbro_model_runner("bounded prompt", schema={"type": "object"})
        finally:
            backend.run_codex_job = original_worker
            if original_flag is None:
                os.environ.pop("WOW_CHICKENBRO_CODEX_ENABLED", None)
            else:
                os.environ["WOW_CHICKENBRO_CODEX_ENABLED"] = original_flag

        self.assertEqual("succeeded", result["status"])
        self.assertEqual("{\"answer\":\"ok\"}", result["lastMessage"])
        self.assertEqual("read-only", calls[0][1]["sandbox"])
        self.assertEqual({"type": "object"}, calls[0][1]["schema"])

    def test_codex_schema_accepts_source_and_wcl_answer_layers(self):
        captured = {}
        bounded_context = backend.build_chickenbro_bounded_context(
            "防战现在天赋怎么点？",
            {},
            source_tool_results=[
                {
                    "sourceKey": "raiderio",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Protection Warrior Mythic+ samples."}],
                    "evidence": [{"id": "raiderio:warrior:protection:mythic_plus"}],
                    "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
                    "limitations": [],
                }
            ],
        )

        def runner(prompt, **kwargs):
            captured["schema"] = kwargs["schema"]
            return {
                "status": "succeeded",
                "content": '{"answer":"ok","confidence":"medium","answerLayer":"source_reference","basisLabel":"社区来源参考","priorityActions":[],"evidenceRefs":["raiderio:warrior:protection:mythic_plus"],"limitations":[],"missingInputs":[],"nextQuestion":""}',
            }

        backend.run_chickenbro_agent(bounded_context, codex_runner=runner)

        answer_layers = captured["schema"]["properties"]["answerLayer"]["enum"]
        self.assertIn("source_reference", answer_layers)
        self.assertIn("wcl_evidence", answer_layers)

    def test_source_reference_prompt_keeps_logs_optional_for_normal_build_chat(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "protection warrior build",
            {},
            source_tool_results=[
                {
                    "sourceKey": "raiderio",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Protection Warrior Mythic+ samples."}],
                    "evidence": [{"id": "raiderio:warrior:protection:mythic_plus"}],
                    "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
                    "limitations": [],
                }
            ],
        )

        prompt = backend.chickenbro_prompt_from_context(bounded_context)

        self.assertIn("do not require the player to provide WCL, SimC, or a link", prompt)

    def test_source_reference_rejects_unsupported_two_digit_claims(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "protection warrior build",
            {},
            source_tool_results=[
                {
                    "sourceKey": "raiderio",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Protection Warrior Mythic+ samples."}],
                    "evidence": [{"id": "raiderio:warrior:protection:mythic_plus"}],
                    "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
                    "limitations": [],
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "unapproved number"):
            backend.validate_chickenbro_model_output(
                {
                    "answer": "The +21 sample proves the best answer.",
                    "confidence": "medium",
                    "priorityActions": [],
                    "evidenceRefs": ["raiderio:warrior:protection:mythic_plus"],
                    "limitations": [],
                    "missingInputs": [],
                    "nextQuestion": "",
                },
                bounded_context,
            )


if __name__ == "__main__":
    unittest.main()
