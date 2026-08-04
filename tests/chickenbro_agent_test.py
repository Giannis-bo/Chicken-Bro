import inspect
import json
import os
import unittest

import server.news_backend as backend
import server.chickenbro_agent as agent
from server.chickenbro_tool_runtime import ChickenbroRegistryRuntime
from tests.chickenbro_registry_test import community_strength_manifest, current_sources_manifest, signed_release


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

    def test_current_source_context_is_evidence_aware_and_rejects_unsupported_strength_tier(self):
        registry_context = {
            "status": "verified",
            "registryVersion": "chickenbro-tools-2",
            "registryReleaseHash": "sha256:a25340f6fe51dfa01d956b7d944891de39771694e4fd3b33fb41b4fba2d9a102",
            "registrySource": "postgres",
            "discoveredCapabilityIds": ["source:current-wow-sources:v1"],
            "selectedCapabilityIds": ["source:current-wow-sources:v1"],
        }
        source = {
            "sourceKey": "current_wow_sources",
            "status": "source_reference",
            "facts": [{"kind": "official_change", "summary": "Holy Paladin PTR adjustment."}],
            "evidence": [{"id": "current.blizzard-forums.holy-paladin-121"}],
            "evidenceRefs": ["current.blizzard-forums.holy-paladin-121"],
            "limitations": ["comparative_strength_signal_missing"],
            "nextActions": [],
        }
        bounded = backend.build_chickenbro_bounded_context(
            "NQ 在 12.1 PTR 强度如何？",
            {},
            source_tool_results={"sourceToolResults": [source], "registryContext": registry_context},
        )

        self.assertEqual("current_research", bounded["questionFrame"]["questionType"])
        self.assertEqual("holy", bounded["questionFrame"]["subject"]["specKey"])
        self.assertEqual(["source:current-wow-sources:v1"], bounded["capabilityPlan"]["selectedCapabilityIds"])
        self.assertEqual(["comparative_strength_signal"], bounded["capabilityPlan"]["unmetEvidenceNeeds"])
        self.assertEqual("已核对官方当前来源", bounded["basisLabel"])
        prompt = json.loads(backend.chickenbro_prompt_from_context(bounded))
        self.assertTrue(any("已确认改动" in item for item in prompt["instructions"]))
        self.assertFalse(any("没有抓取能力" in item for item in prompt["instructions"]))

        with self.assertRaisesRegex(ValueError, "unsupported comparative strength"):
            backend.validate_chickenbro_model_output(
                {
                    "answer": "奶骑在 PTR 目前是 T0。",
                    "confidence": "medium",
                    "priorityActions": [],
                    "evidenceRefs": ["current.blizzard-forums.holy-paladin-121"],
                    "limitations": [],
                    "missingInputs": [],
                    "nextQuestion": "",
                },
                bounded,
            )

    def test_current_source_failure_records_actual_unmet_evidence_without_a_fixed_reply(self):
        bounded = backend.build_chickenbro_bounded_context(
            "NQ 在 12.1 PTR 强度如何？",
            {},
            source_tool_results={
                "sourceToolResults": [
                    {
                        "sourceKey": "current_wow_sources",
                        "status": "failed",
                        "facts": [],
                        "evidence": [],
                        "evidenceRefs": [],
                        "limitations": ["current_source_unavailable"],
                        "nextActions": [],
                    }
                ],
                "registryContext": {
                    "status": "verified",
                    "registryVersion": "chickenbro-tools-2",
                    "registryReleaseHash": "sha256:a25340f6fe51dfa01d956b7d944891de39771694e4fd3b33fb41b4fba2d9a102",
                    "registrySource": "postgres",
                    "discoveredCapabilityIds": ["source:current-wow-sources:v1"],
                    "selectedCapabilityIds": ["source:current-wow-sources:v1"],
                },
            },
        )

        self.assertEqual(
            ["official_current_changes", "comparative_strength_signal"],
            bounded["capabilityPlan"]["unmetEvidenceNeeds"],
        )
        self.assertIn("current_source_unavailable", bounded["limitations"])
        self.assertNotIn("answer", bounded["capabilityPlan"])
        prompt = json.loads(backend.chickenbro_prompt_from_context(bounded))
        self.assertTrue(any("本轮来源证据不可用" in item for item in prompt["instructions"]))
        self.assertFalse(any("系统没有抓取能力" in item for item in prompt["instructions"]))

    def test_source_reference_without_an_evidence_ref_does_not_satisfy_the_capability_plan(self):
        plan = backend.chickenbro_capability_plan(
            {
                "questionType": "current_research",
                "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
            },
            {"selectedCapabilityIds": ["source:current-wow-sources:v1"]},
            [{"sourceKey": "current_wow_sources", "status": "source_reference", "evidenceRefs": []}],
        )

        self.assertEqual(
            ["official_current_changes", "comparative_strength_signal"],
            plan["unmetEvidenceNeeds"],
        )

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

    def test_raiderio_strength_projects_same_role_high_key_signal_without_player_identity(self):
        builder = getattr(agent, "build_raiderio_strength_chickenbro_tool_result", None)

        self.assertIsNotNone(builder, "current-strength research needs a dedicated Raider.IO adapter")
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
                        "classKey": "shaman",
                        "specKey": "elemental",
                        "fullName": "Elemental Shaman",
                        "role": "dps",
                        "sampleCount": 24,
                        "maxKeyLevel": 23,
                        "bestScore": 4226.13,
                        "topRuns": [{"sourceUrl": "https://raider.io/mythic-plus-spec-rankings/season-mn-1/world/shaman/elemental"}],
                        "characterName": "MUST_NOT_ESCAPE",
                    },
                    {
                        "classKey": "mage",
                        "specKey": "frost",
                        "fullName": "Frost Mage",
                        "role": "dps",
                        "sampleCount": 20,
                        "maxKeyLevel": 24,
                        "bestScore": 4300.0,
                    },
                    {
                        "classKey": "warrior",
                        "specKey": "protection",
                        "fullName": "Protection Warrior",
                        "role": "tank",
                        "sampleCount": 20,
                        "maxKeyLevel": 24,
                        "bestScore": 4300.0,
                    },
                ],
            },
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
        )

        self.assertEqual("raiderio_strength", result["sourceKey"])
        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["raiderio-strength:shaman:elemental:mythic_plus"], result["evidenceRefs"])
        signal = result["facts"][0]["highKeySignal"]
        self.assertEqual(2, signal["sameRolePopulation"])
        self.assertEqual(2, signal["sameRolePlacement"])
        self.assertEqual(
            {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage"},
            signal["sameRoleLeader"],
        )
        self.assertEqual(4226.13, signal["bestObservedScore"])
        self.assertEqual(23, signal["maxKeyLevel"])
        self.assertIn("23", result["allowedNumbers"])
        self.assertNotIn("MUST_NOT_ESCAPE", str(result))

    def test_raiderio_strength_fails_closed_when_the_real_aggregate_has_no_positive_best_score(self):
        result = agent.build_raiderio_strength_chickenbro_tool_result(
            {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "checkedAt": "2099-08-01T10:00:00+00:00",
                "expiresAt": "2099-08-01T16:00:00+00:00",
                "specAggregates": [{
                    "classKey": "shaman",
                    "specKey": "elemental",
                    "role": "dps",
                    "sampleCount": 24,
                    "maxKeyLevel": 23,
                }],
            },
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
        )

        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertIn("bestScore", result["limitations"][0])

    def test_raiderio_strength_projects_tied_same_role_leaders_without_inventing_a_unique_first(self):
        result = agent.build_raiderio_strength_chickenbro_tool_result(
            {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "checkedAt": "2099-08-01T10:00:00+00:00",
                "expiresAt": "2099-08-01T16:00:00+00:00",
                "specAggregates": [
                    {"classKey": "shaman", "specKey": "elemental", "fullName": "Elemental Shaman", "role": "dps", "bestScore": 4200, "maxKeyLevel": 23, "sampleCount": 24},
                    {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage", "role": "dps", "bestScore": 4300, "maxKeyLevel": 24, "sampleCount": 20},
                    {"classKey": "deathknight", "specKey": "unholy", "fullName": "Unholy Death Knight", "role": "dps", "bestScore": 4300, "maxKeyLevel": 24, "sampleCount": 20},
                ],
            },
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
        )

        signal = result["facts"][0]["highKeySignal"]
        self.assertNotIn("sameRoleLeader", signal)
        self.assertEqual(
            [
                {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage"},
                {"classKey": "deathknight", "specKey": "unholy", "fullName": "Unholy Death Knight"},
            ],
            signal["sameRoleLeaders"],
        )

    def test_raiderio_strength_uses_competition_rank_for_a_tied_target_score(self):
        result = agent.build_raiderio_strength_chickenbro_tool_result(
            {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "checkedAt": "2099-08-01T10:00:00+00:00",
                "expiresAt": "2099-08-01T16:00:00+00:00",
                "specAggregates": [
                    {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage", "role": "dps", "bestScore": 4300, "maxKeyLevel": 24, "sampleCount": 20},
                    {"classKey": "shaman", "specKey": "elemental", "fullName": "Elemental Shaman", "role": "dps", "bestScore": 4300, "maxKeyLevel": 24, "sampleCount": 20},
                    {"classKey": "deathknight", "specKey": "unholy", "fullName": "Unholy Death Knight", "role": "dps", "bestScore": 4200, "maxKeyLevel": 23, "sampleCount": 20},
                ],
            },
            {"classKey": "shaman", "specKey": "elemental", "productPhase": "retail"},
        )

        self.assertEqual(1, result["facts"][0]["highKeySignal"]["sameRolePlacement"])

    def test_retail_strength_query_executes_registered_raiderio_and_public_wcl_sources(self):
        wcl_builder = getattr(backend, "build_wcl_public_rankings_tool_result", None)

        self.assertIsNotNone(wcl_builder, "backend must bind the registered public WCL rankings adapter")
        payload = {
            "sourceName": "Raider.IO",
            "sourceStatus": "synced",
            "checkedAt": "2099-08-01T10:00:00+00:00",
            "expiresAt": "2099-08-01T16:00:00+00:00",
            "region": "cn",
            "specAggregates": [
                {
                    "classKey": "shaman",
                    "specKey": "elemental",
                    "fullName": "Elemental Shaman",
                    "role": "dps",
                    "sampleCount": 24,
                    "maxKeyLevel": 23,
                    "bestScore": 4226.13,
                },
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "fullName": "Frost Mage",
                    "role": "dps",
                    "sampleCount": 20,
                    "maxKeyLevel": 24,
                    "bestScore": 4300,
                },
            ],
        }
        wcl_result = {
            "sourceKey": "warcraftlogs_public_rankings",
            "status": "source_reference",
            "facts": [{"summary": "Current WCL public Mythic+ rows are available.", "sampleCount": 2}],
            "evidence": [{"id": "wcl.public.shaman.elemental.mythic_plus"}],
            "evidenceRefs": ["wcl.public.shaman.elemental.mythic_plus"],
            "allowedNumbers": ["2"],
            "limitations": [],
            "nextActions": [],
        }
        rio = community_strength_manifest(
            "source:raiderio-strength:v1",
            "chickenbro.source.raiderio_strength.v1",
            "raiderio_strength",
        )
        wcl = community_strength_manifest(
            "source:warcraftlogs-public-rankings:v1",
            "chickenbro.source.warcraftlogs_public_rankings.v1",
            "warcraftlogs_public_rankings",
        )
        release = signed_release(
            [signed_release()["manifests"][0], signed_release()["manifests"][1], current_sources_manifest(), rio, wcl],
            registryVersion="chickenbro-tools-3",
            provenance={"kind": "repository_migration", "revision": "0027"},
        )
        original_payload = backend.chickenbro_cached_raiderio_payload
        original_wcl_builder = backend.build_wcl_public_rankings_tool_result
        backend.chickenbro_cached_raiderio_payload = lambda: payload
        backend.build_wcl_public_rankings_tool_result = lambda intent: wcl_result
        try:
            loaded = backend.load_chickenbro_source_tool_results(
                "元素萨现在版本大秘境强度如何？",
                {"region": "cn"},
                include_registry=True,
                registry_loader=lambda: release,
                registry_runtime=ChickenbroRegistryRuntime(60),
            )
        finally:
            backend.chickenbro_cached_raiderio_payload = original_payload
            backend.build_wcl_public_rankings_tool_result = original_wcl_builder

        self.assertEqual(
            ["raiderio_strength", "warcraftlogs_public_rankings"],
            [item["sourceKey"] for item in loaded["sourceToolResults"]],
        )
        bounded = backend.build_chickenbro_bounded_context(
            "元素萨现在版本大秘境强度如何？",
            {},
            source_tool_results=loaded,
        )
        self.assertEqual([], bounded["capabilityPlan"]["unmetEvidenceNeeds"])
        self.assertEqual("source_reference", bounded["answerLayer"])
        self.assertIn("raiderio-strength:shaman:elemental:mythic_plus", bounded["allowedEvidenceRefs"])
        self.assertIn("wcl.public.shaman.elemental.mythic_plus", bounded["allowedEvidenceRefs"])
        self.assertEqual("已核对社区当前数据", bounded["basisLabel"])
        prompt = json.loads(backend.chickenbro_prompt_from_context(bounded))
        self.assertTrue(any("当前强度证据" in item for item in prompt["instructions"]))
        self.assertFalse(any("来源证据不可用" in item for item in prompt["instructions"]))

    def test_public_wcl_rows_do_not_satisfy_a_cross_spec_strength_requirement(self):
        plan = backend.chickenbro_capability_plan(
            {"questionType": "current_research", "evidenceNeeds": ["comparative_strength_signal"]},
            {"selectedCapabilityIds": ["source:warcraftlogs-public-rankings:v1"]},
            [{
                "sourceKey": "warcraftlogs_public_rankings",
                "status": "source_reference",
                "evidenceRefs": ["wcl.public.shaman.elemental.mythic_plus"],
            }],
        )

        self.assertEqual(["comparative_strength_signal"], plan["unmetEvidenceNeeds"])

    def test_current_message_scenario_cannot_be_overridden_by_a_stale_client_mplus_context(self):
        rio = community_strength_manifest(
            "source:raiderio-strength:v1",
            "chickenbro.source.raiderio_strength.v1",
            "raiderio_strength",
        )
        release = signed_release(
            [signed_release()["manifests"][0], signed_release()["manifests"][1], current_sources_manifest(), rio],
            registryVersion="chickenbro-tools-3",
            provenance={"kind": "repository_migration", "revision": "0027"},
        )
        loaded = backend.load_chickenbro_source_tool_results(
            "元素萨正式服团本单体强度如何？",
            {"region": "cn", "scenarioKey": "mythic_plus", "productPhase": "retail"},
            include_registry=True,
            registry_loader=lambda: release,
            registry_runtime=ChickenbroRegistryRuntime(60),
        )

        self.assertEqual([], loaded["sourceToolResults"])
        self.assertEqual([], loaded["registryContext"]["selectedCapabilityIds"])

    def test_returned_community_strength_evidence_rejects_no_data_manual_lookup_reply(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "元素萨现在版本大秘境强度如何？",
            {},
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Elemental Shaman high-key signal.", "highKeySignal": {"bestObservedScore": 4226.13}}],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13"],
                    "limitations": [],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified",
                    "registryVersion": "chickenbro-tools-3",
                    "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres",
                    "discoveredCapabilityIds": ["source:raiderio-strength:v1"],
                    "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "comparative evidence"):
            backend.validate_chickenbro_model_output(
                {
                    "answer": "我目前没有数据，你可以自己去 WCL 或 Raider.IO 查询。",
                    "confidence": "medium",
                    "priorityActions": [],
                    "evidenceRefs": [],
                    "limitations": [],
                    "missingInputs": [],
                    "nextQuestion": "",
                },
                bounded_context,
            )

    def test_rejected_strength_model_reply_uses_a_generic_evidence_backed_fallback(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "元素萨现在版本大秘境强度如何？",
            {},
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{
                        "summary": "Raider.IO current Mythic+ high-key signal is available for Elemental Shaman.",
                        "highKeySignal": {
                            "bestObservedScore": 4226.13,
                            "sameRolePlacement": 2,
                            "sameRolePopulation": 12,
                            "maxKeyLevel": 23,
                            "sampleCount": 24,
                        },
                    }],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13", "2", "12", "23", "24"],
                    "limitations": ["same-role high-key samples are not a universal tier list"],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified",
                    "registryVersion": "chickenbro-tools-3",
                    "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres",
                    "discoveredCapabilityIds": ["source:raiderio-strength:v1"],
                    "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )
        result = backend.run_chickenbro_agent(
            bounded_context,
            codex_runner=lambda *_args, **_kwargs: {
                "status": "succeeded",
                "content": '{"answer":"没有数据，你自己去 Raider.IO 查。","confidence":"medium","priorityActions":[],"evidenceRefs":[],"limitations":[],"missingInputs":[],"nextQuestion":""}',
            },
        )

        self.assertEqual("deterministic_source_fallback", result["answer"]["answerSource"])
        self.assertEqual(["raiderio-strength:shaman:elemental:mythic_plus"], result["answer"]["evidenceRefs"])
        self.assertNotIn("没有数据", result["answer"]["answer"])
        self.assertIn("4226.13", result["answer"]["answer"])

    def test_streamed_strength_reply_is_buffered_until_evidence_validation_then_falls_back(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "元素萨现在版本大秘境强度如何？",
            {},
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Elemental Shaman high-key signal.", "highKeySignal": {"bestObservedScore": 4226.13, "sameRolePlacement": 2, "sameRolePopulation": 12, "maxKeyLevel": 23, "sampleCount": 24}}],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13", "2", "12", "23", "24"],
                    "limitations": [],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified", "registryVersion": "chickenbro-tools-3", "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres", "discoveredCapabilityIds": ["source:raiderio-strength:v1"], "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )
        payload = '{"answer":"没有数据，你自己去 Raider.IO 查。","confidence":"medium","priorityActions":[],"evidenceRefs":[],"limitations":[],"missingInputs":[],"nextQuestion":""}'
        stream = backend.run_chickenbro_agent_stream(bounded_context, stream_runner=lambda *_args, **_kwargs: [payload])
        events = []
        while True:
            try:
                events.append(next(stream))
            except StopIteration as stop:
                result = stop.value
                break

        self.assertEqual(1, len(events))
        self.assertNotIn("没有数据", events[0]["text"])
        self.assertEqual("deterministic_source_fallback", result["answer"]["answerSource"])
        with self.assertRaisesRegex(ValueError, "summarized"):
            backend.validate_chickenbro_model_output(
                {
                    "answer": "我目前没有数据，你可以自己去 WCL 或 Raider.IO 查询。",
                    "confidence": "medium",
                    "priorityActions": [],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "limitations": [],
                    "missingInputs": [],
                    "nextQuestion": "",
                },
                bounded_context,
            )

    def test_streamed_strength_ratio_follow_up_fallback_explains_the_dynamic_ratio(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "解读一下2/12是啥意思？",
            {},
            history=[{"role": "user", "content": "元素萨现在版本大秘境强度如何？"}],
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Elemental Shaman high-key signal.", "highKeySignal": {"bestObservedScore": 4226.13, "sameRolePlacement": 2, "sameRolePopulation": 12, "maxKeyLevel": 23, "sampleCount": 24}}],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13", "2", "12", "23", "24"],
                    "limitations": [],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified", "registryVersion": "chickenbro-tools-3", "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres", "discoveredCapabilityIds": ["source:raiderio-strength:v1"], "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )
        payload = '{"answer":"没有数据，你自己去 Raider.IO 查。","confidence":"medium","priorityActions":[],"evidenceRefs":[],"limitations":[],"missingInputs":[],"nextQuestion":""}'
        stream = backend.run_chickenbro_agent_stream(bounded_context, stream_runner=lambda *_args, **_kwargs: [payload])
        events = []
        while True:
            try:
                events.append(next(stream))
            except StopIteration as stop:
                result = stop.value
                break

        self.assertEqual("current_research", bounded_context["questionFrame"]["questionType"])
        self.assertEqual(["comparative_strength_signal"], bounded_context["questionFrame"]["evidenceNeeds"])
        self.assertEqual("deterministic_source_fallback", result["answer"]["answerSource"])
        self.assertIn("第 2/12 表示", events[0]["text"])
        self.assertIn("12 个同职责高层样本", events[0]["text"])
        self.assertIn("不是全职业排名", events[0]["text"])

    def test_streamed_strength_leader_follow_up_fallback_names_the_bounded_leader(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "排第一的是啥呢？",
            {},
            history=[
                {"role": "user", "content": "元素萨现在版本大秘境强度如何？"},
                {"role": "assistant", "content": "元素萨在同职责样本中位于第 2/12。"},
                {"role": "user", "content": "解读一下2/12是啥意思？"},
            ],
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Elemental Shaman high-key signal.", "highKeySignal": {
                        "bestObservedScore": 4226.13,
                        "sameRolePlacement": 2,
                        "sameRolePopulation": 12,
                        "sameRoleLeader": {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage"},
                        "maxKeyLevel": 23,
                        "sampleCount": 24,
                    }}],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13", "2", "12", "23", "24"],
                    "limitations": [],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified", "registryVersion": "chickenbro-tools-3", "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres", "discoveredCapabilityIds": ["source:raiderio-strength:v1"], "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )
        payload = '{"answer":"没有数据，你自己去 Raider.IO 查。","confidence":"medium","priorityActions":[],"evidenceRefs":[],"limitations":[],"missingInputs":[],"nextQuestion":""}'
        stream = backend.run_chickenbro_agent_stream(bounded_context, stream_runner=lambda *_args, **_kwargs: [payload])
        events = []
        while True:
            try:
                events.append(next(stream))
            except StopIteration as stop:
                result = stop.value
                break

        self.assertEqual("current_research", bounded_context["questionFrame"]["questionType"])
        self.assertEqual(["comparative_strength_signal"], bounded_context["questionFrame"]["evidenceNeeds"])
        self.assertEqual("deterministic_source_fallback", result["answer"]["answerSource"])
        self.assertIn("Frost Mage", events[0]["text"])
        self.assertIn("同职责", events[0]["text"])
        self.assertIn("不是全职业", events[0]["text"])

    def test_streamed_strength_leader_follow_up_fallback_reports_a_tied_lead(self):
        bounded_context = backend.build_chickenbro_bounded_context(
            "排第一的是啥呢？",
            {},
            history=[
                {"role": "user", "content": "元素萨现在版本大秘境强度如何？"},
                {"role": "user", "content": "解读一下2/12是啥意思？"},
            ],
            source_tool_results={
                "sourceToolResults": [{
                    "sourceKey": "raiderio_strength",
                    "status": "source_reference",
                    "facts": [{"summary": "Current Elemental Shaman high-key signal.", "highKeySignal": {
                        "bestObservedScore": 4226.13,
                        "sameRolePlacement": 2,
                        "sameRolePopulation": 12,
                        "sameRoleLeaders": [
                            {"classKey": "mage", "specKey": "frost", "fullName": "Frost Mage"},
                            {"classKey": "deathknight", "specKey": "unholy", "fullName": "Unholy Death Knight"},
                        ],
                        "maxKeyLevel": 23,
                        "sampleCount": 24,
                    }}],
                    "evidence": [{"id": "raiderio-strength:shaman:elemental:mythic_plus", "checkedAt": "2099-08-01T10:00:00+00:00"}],
                    "evidenceRefs": ["raiderio-strength:shaman:elemental:mythic_plus"],
                    "allowedNumbers": ["4226.13", "2", "12", "23", "24"],
                    "limitations": [],
                    "nextActions": [],
                }],
                "registryContext": {
                    "status": "verified", "registryVersion": "chickenbro-tools-3", "registryReleaseHash": "sha256:" + "1" * 64,
                    "registrySource": "postgres", "discoveredCapabilityIds": ["source:raiderio-strength:v1"], "selectedCapabilityIds": ["source:raiderio-strength:v1"],
                },
            },
        )
        payload = '{"answer":"没有数据，你自己去 Raider.IO 查。","confidence":"medium","priorityActions":[],"evidenceRefs":[],"limitations":[],"missingInputs":[],"nextQuestion":""}'
        stream = backend.run_chickenbro_agent_stream(bounded_context, stream_runner=lambda *_args, **_kwargs: [payload])
        events = []
        while True:
            try:
                events.append(next(stream))
            except StopIteration:
                break

        self.assertIn("并列第一", events[0]["text"])
        self.assertIn("Frost Mage", events[0]["text"])
        self.assertIn("Unholy Death Knight", events[0]["text"])

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
