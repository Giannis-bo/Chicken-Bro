from datetime import datetime, timedelta, timezone
from time import sleep
import unittest

from tests.chickenbro_registry_test import signed_release


NOW = datetime(2026, 8, 2, 8, 0, tzinfo=timezone.utc)
INTENT = {
    "kind": "community_build",
    "productPhase": "retail",
    "classKey": "warrior",
    "specKey": "protection",
}
CONTEXT = {
    "region": "cn",
    "classKey": "warrior",
    "specKey": "protection",
}


class ChickenbroToolRuntimeTest(unittest.TestCase):
    def test_each_validated_agentic_call_receives_its_own_arguments(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_tool_calls
        from tests.chickenbro_registry_test import signed_manifest, wcl_manifest

        manifests = [signed_manifest(), wcl_manifest()]

        def raiderio_adapter(request):
            return {
                "sourceKey": "raiderio",
                "status": "source_reference",
                "facts": [{"classKey": request["intent"]["classKey"]}],
                "evidence": [],
                "evidenceRefs": ["fixture.raiderio"],
                "limitations": [],
                "nextActions": [],
            }

        def wcl_adapter(request):
            return {
                "sourceKey": "warcraftlogs",
                "status": "verified",
                "facts": [{"report": request["intent"]["wclReport"]}],
                "evidence": [],
                "evidenceRefs": ["fixture.wcl"],
                "limitations": [],
                "nextActions": [],
            }

        results = execute_chickenbro_tool_calls(
            manifests,
            {
                "chickenbro.source.raiderio.v1": raiderio_adapter,
                "chickenbro.source.warcraftlogs.v1": wcl_adapter,
            },
            [
                {
                    "toolId": "source:raiderio:v1",
                    "arguments": {"classKey": "paladin", "specKey": "holy"},
                },
                {
                    "toolId": "source:warcraftlogs:v1",
                    "arguments": {"wclReport": "https://www.warcraftlogs.com/reports/ABC123"},
                },
            ],
        )

        self.assertEqual("paladin", results[0]["facts"][0]["classKey"])
        self.assertEqual(
            "https://www.warcraftlogs.com/reports/ABC123",
            results[1]["facts"][0]["report"],
        )
    def test_dispatch_stops_waiting_when_the_manifest_timeout_budget_expires(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_selected_tools

        resolution = {
            "selectedManifests": [{
                "toolId": "source:raiderio:v1",
                "implementationRef": "chickenbro.source.raiderio.v1",
                "sourcePolicy": {"sourceKey": "raiderio"},
                "timeoutBudgetMs": 1,
            }]
        }
        results = execute_chickenbro_selected_tools(
            resolution,
            {"chickenbro.source.raiderio.v1": lambda _request: (sleep(0.05), {})[1]},
            {"intent": INTENT, "context": CONTEXT},
        )

        self.assertEqual("failed", results[0]["status"])
        self.assertIn("timeout", results[0]["limitations"][0].lower())

    def test_dispatch_demotes_timestamp_less_current_source_evidence_to_stale(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_selected_tools

        resolution = {
            "selectedManifests": [{
                "toolId": "source:raiderio:v1",
                "implementationRef": "chickenbro.source.raiderio.v1",
                "sourcePolicy": {"sourceKey": "raiderio"},
                "timeoutBudgetMs": 1000,
                "freshnessPolicy": {"maxAgeSeconds": 60, "requireCheckedAt": True},
            }]
        }
        results = execute_chickenbro_selected_tools(
            resolution,
            {"chickenbro.source.raiderio.v1": lambda _request: {
                "sourceKey": "raiderio",
                "status": "source_reference",
                "facts": [{"summary": "missing timestamp"}],
                "evidence": [{"id": "raiderio:test"}],
                "evidenceRefs": ["raiderio:test"],
                "limitations": [],
                "nextActions": [],
            }},
            {"intent": INTENT, "context": CONTEXT},
        )

        self.assertEqual("stale", results[0]["status"])
        self.assertEqual([], results[0]["evidenceRefs"])
    def test_verified_release_uses_postgres_then_bounded_cache(self):
        from server.chickenbro_tool_runtime import (
            ChickenbroRegistryRuntime,
            RegistryUnavailable,
        )

        runtime = ChickenbroRegistryRuntime(cache_ttl_seconds=60)
        release = signed_release()

        fresh = runtime.resolve(lambda: release, INTENT, CONTEXT, now=NOW)
        cached = runtime.resolve(
            lambda: (_ for _ in ()).throw(ConnectionError("database offline")),
            INTENT,
            CONTEXT,
            now=NOW + timedelta(seconds=30),
        )

        self.assertEqual("postgres", fresh["registrySource"])
        self.assertEqual("verified_cache", cached["registrySource"])
        self.assertEqual("verified", cached["registryStatus"])
        self.assertEqual(fresh["registryReleaseHash"], cached["registryReleaseHash"])
        with self.assertRaises(RegistryUnavailable):
            runtime.resolve(
                lambda: (_ for _ in ()).throw(ConnectionError("database offline")),
                INTENT,
                CONTEXT,
                now=NOW + timedelta(seconds=61),
            )

    def test_cold_start_loader_failure_is_unavailable(self):
        from server.chickenbro_tool_runtime import (
            ChickenbroRegistryRuntime,
            RegistryUnavailable,
        )

        runtime = ChickenbroRegistryRuntime(cache_ttl_seconds=60)
        with self.assertRaisesRegex(RegistryUnavailable, "unavailable"):
            runtime.resolve(
                lambda: (_ for _ in ()).throw(TimeoutError("secret host name")),
                INTENT,
                CONTEXT,
                now=NOW,
            )

    def test_invalid_database_release_never_substitutes_or_preserves_cache(self):
        from server.chickenbro_tool_runtime import (
            ChickenbroRegistryRuntime,
            RegistryInvalid,
            RegistryUnavailable,
        )

        runtime = ChickenbroRegistryRuntime(cache_ttl_seconds=60)
        runtime.resolve(lambda: signed_release(), INTENT, CONTEXT, now=NOW)
        invalid = signed_release(releaseHash="sha256:" + "0" * 64)

        with self.assertRaisesRegex(RegistryInvalid, "invalid"):
            runtime.resolve(lambda: invalid, INTENT, CONTEXT, now=NOW + timedelta(seconds=10))
        with self.assertRaises(RegistryUnavailable):
            runtime.resolve(
                lambda: (_ for _ in ()).throw(ConnectionError("database offline")),
                INTENT,
                CONTEXT,
                now=NOW + timedelta(seconds=20),
            )

    def test_unknown_adapter_fails_before_any_callable_runs(self):
        from server.chickenbro_tool_runtime import (
            RegistryInvalid,
            execute_chickenbro_selected_tools,
        )

        calls = []
        resolution = {
            "selectedManifests": [
                {
                    "toolId": "source:raiderio:v1",
                    "implementationRef": "chickenbro.source.raiderio.v1",
                    "sourcePolicy": {"sourceKey": "raiderio"},
                },
                {
                    "toolId": "source:unknown:v1",
                    "implementationRef": "chickenbro.source.unknown.v1",
                    "sourcePolicy": {"sourceKey": "unknown"},
                },
            ]
        }
        bindings = {
            "chickenbro.source.raiderio.v1": lambda request: calls.append(request),
        }

        with self.assertRaisesRegex(RegistryInvalid, "adapter"):
            execute_chickenbro_selected_tools(
                resolution,
                bindings,
                {"message": "build", "intent": INTENT, "context": CONTEXT},
            )
        self.assertEqual([], calls)

    def test_dispatch_sanitizes_request_and_bounds_adapter_failure(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_selected_tools

        received = []

        def failing_adapter(request):
            received.append(request)
            raise RuntimeError("x" * 500)

        resolution = {
            "selectedManifests": [
                {
                    "toolId": "source:raiderio:v1",
                    "implementationRef": "chickenbro.source.raiderio.v1",
                    "sourcePolicy": {"sourceKey": "raiderio"},
                }
            ]
        }
        results = execute_chickenbro_selected_tools(
            resolution,
            {"chickenbro.source.raiderio.v1": failing_adapter},
            {
                "message": "build",
                "intent": {**INTENT, "credential": "must-not-pass"},
                "context": {**CONTEXT, "userId": "must-not-pass"},
                "credential": "must-not-pass",
            },
        )

        self.assertEqual({"intent", "context"}, set(received[0]))
        self.assertNotIn("credential", received[0]["intent"])
        self.assertNotIn("userId", received[0]["context"])
        self.assertEqual("failed", results[0]["status"])
        self.assertLessEqual(len(results[0]["limitations"][0]), 160)
        self.assertEqual([], results[0]["evidence"])

    def test_dispatch_preserves_valid_tool_result(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_selected_tools

        expected = {
            "sourceKey": "raiderio",
            "status": "verified",
            "facts": [{"key": "spec", "value": "protection"}],
            "evidence": [{"source": "raiderio"}],
            "evidenceRefs": ["rio:protection"],
            "limitations": [],
            "nextActions": [],
        }
        resolution = {
            "selectedManifests": [
                {
                    "toolId": "source:raiderio:v1",
                    "implementationRef": "chickenbro.source.raiderio.v1",
                    "sourcePolicy": {"sourceKey": "raiderio"},
                }
            ]
        }
        results = execute_chickenbro_selected_tools(
            resolution,
            {"chickenbro.source.raiderio.v1": lambda request: expected},
            {"message": "build", "intent": INTENT, "context": CONTEXT},
        )

        self.assertEqual([expected], results)
        self.assertIsNot(expected, results[0])

    def test_current_source_adapter_receives_only_frame_projection_not_raw_message_or_owner(self):
        from server.chickenbro_tool_runtime import execute_chickenbro_selected_tools

        received = []
        resolution = {
            "selectedManifests": [
                {
                    "toolId": "source:current-wow-sources:v1",
                    "implementationRef": "chickenbro.source.current_wow_sources.v1",
                    "sourcePolicy": {"sourceKey": "current_wow_sources"},
                }
            ]
        }
        expected = {
            "sourceKey": "current_wow_sources",
            "status": "partial",
            "facts": [],
            "evidence": [],
            "evidenceRefs": [],
            "limitations": ["subject_specific_official_change_missing"],
            "nextActions": [],
        }
        results = execute_chickenbro_selected_tools(
            resolution,
            {"chickenbro.source.current_wow_sources.v1": lambda request: received.append(request) or expected},
            {
                "message": "NQ 12.1 PTR https://not-blizzard.example/anything",
                "intent": {
                    "kind": "current_research",
                    "questionType": "current_research",
                    "productPhase": "ptr",
                    "patchVersion": "12.1",
                    "classKey": "paladin",
                    "specKey": "holy",
                    "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
                    "ownerId": "must-not-pass",
                },
                "context": {
                    "region": "cn",
                    "productPhase": "ptr",
                    "questionType": "current_research",
                    "patchVersion": "12.1",
                    "classKey": "paladin",
                    "specKey": "holy",
                    "ownerId": "must-not-pass",
                },
            },
        )

        self.assertEqual([expected], results)
        self.assertEqual({"intent", "context"}, set(received[0]))
        self.assertNotIn("ownerId", str(received[0]))
        self.assertNotIn("not-blizzard.example", str(received[0]))
        self.assertEqual(
            {
                "kind",
                "questionType",
                "productPhase",
                "patchVersion",
                "classKey",
                "specKey",
                "evidenceNeeds",
            },
            set(received[0]["intent"]),
        )


if __name__ == "__main__":
    unittest.main()
