import copy
import unittest

try:
    from server.gear_variant_materialization_runner import (
        EXPECTED_RELEASE_CONTEXT_FIELDS,
        build_gear_variant_materialization_runner,
    )
except ModuleNotFoundError:
    EXPECTED_RELEASE_CONTEXT_FIELDS = None
    build_gear_variant_materialization_runner = None


class RecordingRequest:
    def __init__(self, responses):
        self.responses = list(copy.deepcopy(responses))
        self.calls = []

    def __call__(self, method, path, body, headers):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "body": copy.deepcopy(body),
                "headers": copy.deepcopy(headers),
            }
        )
        if not self.responses:
            raise AssertionError("unexpected extra request")
        response = self.responses.pop(0)
        if len(response) == 2:
            return response
        if len(response) == 3:
            return response
        raise AssertionError("response tuple must be length 2 or 3")


class GearVariantMaterializationRunnerTest(unittest.TestCase):
    def selection_intent(self):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "manifestRevision": "manifest-r1",
                "gearCatalogRevision": "catalog-r1",
                "gearExactRegistryRevision": "exact-r1",
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "frost",
                "level": 80,
            },
            "slots": {
                "head": {
                    "itemId": "1001",
                    "variantKey": "browse-a",
                }
            },
        }

    def profile_context(self):
        return {
            "name": "Candidate Mage",
            "race": "human",
            "scenarioKey": "single",
            "talents": "C4DAAAAAAAAA",
        }

    def expected_release_context(self, **overrides):
        context = {
            "manifestRevision": "manifest-r1",
            "pointerGeneration": 7,
            "gearCatalogRevision": "catalog-r1",
            "gearExactRegistryRevision": "exact-r1",
            "simcRuntimeRevision": "simc-r1",
        }
        context.update(overrides)
        return context

    def resolve_envelope(
        self,
        *,
        status="resolved",
        snapshot_status="verified",
        slot_item_id="1001",
        slot_variant_key="browse-a",
        release_context=None,
    ):
        return {
            "contractRevision": "gear-result-envelope-v1",
            "requestId": "resolve-1",
            "status": status,
            "releaseContext": copy.deepcopy(
                release_context or self.expected_release_context()
            ),
            "data": {
                "contractRevision": "gear-resolved-snapshot-v1",
                "status": snapshot_status,
                "resolvedSlots": {
                    "head": {
                        "slot": "head",
                        "itemId": slot_item_id,
                        "variantKey": slot_variant_key,
                    }
                },
                "profileReadiness": {
                    "status": "verified",
                    "simcReady": True,
                },
            },
            "problems": [],
        }

    def profile_envelope(
        self,
        *,
        status="resolved",
        profile_status="resolved",
        profile="player=\"Candidate\"\nclass=mage",
        readiness_status="verified",
        simc_ready=True,
        release_context=None,
    ):
        return {
            "contractRevision": "gear-result-envelope-v1",
            "requestId": "profile-1",
            "status": status,
            "releaseContext": copy.deepcopy(
                release_context or self.expected_release_context()
            ),
            "data": {
                "status": profile_status,
                "profile": profile,
                "profileReadiness": {
                    "status": readiness_status,
                    "simcReady": simc_ready,
                },
            },
            "problems": [],
        }

    def build_runner(self, request, **overrides):
        config = {
            "request_json": request,
            "profile_context_factory": (
                lambda **_: copy.deepcopy(self.profile_context())
            ),
            "expected_release_context": self.expected_release_context(),
        }
        config.update(overrides)
        return build_gear_variant_materialization_runner(**config)

    def materialize(self, runner):
        return runner(
            item_id="1001",
            browse_variant_key="browse-a",
            class_key="mage",
            spec_key="frost",
            slot="head",
            selection_intent=self.selection_intent(),
        )

    def test_happy_path_returns_exact_identity_ready_report(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        self.assertEqual(
            EXPECTED_RELEASE_CONTEXT_FIELDS,
            (
                "manifestRevision",
                "pointerGeneration",
                "gearCatalogRevision",
                "gearExactRegistryRevision",
                "simcRuntimeRevision",
            ),
        )
        request = RecordingRequest(
            [
                (200, self.resolve_envelope(), 12.5),
                (200, self.profile_envelope(), 14.0),
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["resolverStatus"], "verified")
        self.assertEqual(report["profileStatus"], "resolved")
        self.assertEqual(report["profileReadinessStatus"], "verified")
        self.assertTrue(report["simcReady"])
        self.assertEqual(report["materializedItemId"], "1001")
        self.assertEqual(report["materializedBrowseVariantKey"], "browse-a")
        self.assertEqual(report["selectionIntent"], self.selection_intent())
        self.assertEqual(report["profileContext"], self.profile_context())
        self.assertEqual(report["failureCodes"], [])
        self.assertFalse(report["usedDefaultVariant"])

    def test_resolver_blocked_status_is_preserved_and_profile_is_not_called(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (
                    200,
                    self.resolve_envelope(
                        status="blocked",
                        snapshot_status="blocked",
                    ),
                )
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["resolverStatus"], "blocked")
        self.assertEqual(report["profileStatus"], "")
        self.assertIsNone(report["simcReady"])
        self.assertIn(
            "MATERIALIZATION_RUNNER_RESOLVER_STATUS_NOT_READY",
            report["failureCodes"],
        )
        self.assertEqual(len(request.calls), 1)

    def test_pair_mismatch_blocks_before_profile_request(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (
                    200,
                    self.resolve_envelope(
                        slot_variant_key="browse-b",
                    ),
                )
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["materializedItemId"], "1001")
        self.assertEqual(report["materializedBrowseVariantKey"], "browse-b")
        self.assertIn(
            "MATERIALIZATION_RUNNER_RESOLVED_PAIR_MISMATCH",
            report["failureCodes"],
        )
        self.assertEqual(len(request.calls), 1)

    def test_resolver_pair_mismatch_preserves_release_context_mismatch_evidence(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (
                    200,
                    self.resolve_envelope(
                        slot_variant_key="browse-b",
                        release_context=self.expected_release_context(
                            manifestRevision="manifest-r2"
                        ),
                    ),
                )
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "MATERIALIZATION_RUNNER_RESOLVER_RELEASE_CONTEXT_MISMATCH",
            report["failureCodes"],
        )
        self.assertEqual(
            report["releaseContextIssues"],
            [
                {
                    "code": "MATERIALIZATION_RUNNER_RESOLVER_RELEASE_CONTEXT_MISMATCH",
                    "stage": "resolver",
                    "field": "manifestRevision",
                    "expected": "manifest-r1",
                    "actual": "manifest-r2",
                }
            ],
        )
        self.assertEqual(len(request.calls), 1)

    def test_profile_partial_and_not_ready_status_are_preserved(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (200, self.resolve_envelope()),
                (
                    200,
                    self.profile_envelope(
                        status="partial",
                        profile_status="partial",
                        readiness_status="partial",
                        simc_ready=False,
                    ),
                ),
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["resolverStatus"], "verified")
        self.assertEqual(report["profileStatus"], "partial")
        self.assertEqual(report["profileReadinessStatus"], "partial")
        self.assertFalse(report["simcReady"])
        self.assertIn(
            "MATERIALIZATION_RUNNER_PROFILE_STATUS_NOT_READY",
            report["failureCodes"],
        )
        self.assertIn(
            "MATERIALIZATION_RUNNER_PROFILE_SIMC_NOT_READY",
            report["failureCodes"],
        )

    def test_release_context_identity_mismatch_blocks_even_when_bodies_are_ready(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (
                    200,
                    self.resolve_envelope(
                        release_context=self.expected_release_context(
                            manifestRevision="manifest-r2"
                        )
                    ),
                ),
                (200, self.profile_envelope()),
            ]
        )

        report = self.materialize(self.build_runner(request))

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "MATERIALIZATION_RUNNER_RESOLVER_RELEASE_CONTEXT_MISMATCH",
            report["failureCodes"],
        )
        self.assertEqual(len(request.calls), 2)

    def test_request_order_and_exact_bodies_are_preserved(self):
        self.assertIsNotNone(build_gear_variant_materialization_runner)
        request = RecordingRequest(
            [
                (200, self.resolve_envelope()),
                (200, self.profile_envelope()),
            ]
        )
        runner = self.build_runner(request)

        report = self.materialize(runner)

        self.assertEqual(report["status"], "verified")
        self.assertEqual(
            request.calls,
            [
                {
                    "method": "POST",
                    "path": "/api/websim/gear/resolve",
                    "body": self.selection_intent(),
                    "headers": {"Content-Type": "application/json"},
                },
                {
                    "method": "POST",
                    "path": "/api/websim/profile",
                    "body": {
                        "selectionIntent": self.selection_intent(),
                        "profileContext": self.profile_context(),
                    },
                    "headers": {"Content-Type": "application/json"},
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
