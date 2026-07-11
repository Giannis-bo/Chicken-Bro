import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from server.gear_stat_snapshot_api import get_or_start_stat_snapshot
from server import websim_payload


SIGNATURE = "stat-snapshot:sha256:" + "a" * 64
FIXTURE_INTENT = json.loads(
    (Path(__file__).parent / "fixtures" / "gear-resolver-complete-authority-v1.json").read_text(
        encoding="utf-8"
    )
)["intent"]
RELEASE = {
    "manifestRevision": "season-manifest:r17",
    "pointerGeneration": 9,
    "gearCatalogRevision": "gear-release:r17",
    "communityTemplateRevision": "community-release:r17",
    "talentCatalogRevision": "talent-catalog:r17",
    "formalActiveManifest": True,
}
SNAPSHOT = {
    "contractRevision": "gear-resolved-snapshot-v1",
    "status": "verified",
    "resolvedGearSignature": "sha256:" + "b" * 64,
    "dependencyVector": {
        "seasonRevision": "season-r17",
        "gearCatalogReleaseId": "gear-release:r17",
        "gearCatalogRevision": "gear-release:r17",
        "gearRuleRevision": "rules-v1",
        "resolverContractRevision": "resolver-v1",
        "serializerRevision": "serializer-v1",
        "simcRuntimeRevision": "simc-v1",
        "statPolicyRevision": "stats-v1",
        "selectionSchemaRevision": "selection-intent-v1",
        "capabilityRevision": "capability-v1",
    },
}


class FakeSnapshotStore:
    def __init__(self, *, cached=None, ready=True, queue_result=None, queue_error=None):
        self.cached = cached or {}
        self.ready = ready
        self.queue_result = queue_result or {
            "status": "pending",
            "job": {"jobId": 7, "queuedAt": "2026-07-11T12:00:00+00:00"},
        }
        self.queue_error = queue_error
        self.calls = []

    def lookup_snapshot(self, stat_signature, *, record_request=False):
        self.calls.append(("lookup", stat_signature, record_request))
        return copy.deepcopy(self.cached)

    def worker_readiness(self, *, simc_runtime_revision, now, max_age_seconds=30):
        self.calls.append(("readiness", simc_runtime_revision, now, max_age_seconds))
        return {"ready": self.ready}

    def get_or_start(self, stat_signature, **kwargs):
        self.calls.append(("queue", stat_signature, copy.deepcopy(kwargs)))
        if self.queue_error:
            raise self.queue_error
        return copy.deepcopy(self.queue_result)


def resolved(_intent, *, store, simc_runtime_revision, request_id):
    del store, simc_runtime_revision
    return 200, {
        "contractRevision": "gear-result-envelope-v1",
        "requestId": request_id,
        "status": "resolved",
        "releaseContext": copy.deepcopy(RELEASE),
        "data": copy.deepcopy(SNAPSHOT),
        "problems": [],
    }


def profile_builder(_snapshot, *, source_context, execution_flavor):
    return {
        "status": "resolved",
        "profile": "mage=fixture\niterations=1\ncalculate_scale_factors=0",
        "profileReadiness": {"simcReady": True},
        "talentEncoding": {"status": "external"},
        "sourceContext": source_context,
        "executionFlavor": execution_flavor,
        "problems": [],
    }


class GearStatSnapshotApiTest(unittest.TestCase):
    def request(self):
        return {
            "selectionIntent": copy.deepcopy(FIXTURE_INTENT),
            "profileContext": {
                "name": "fixture",
                "talents": "external-code",
                "untrustedExtra": "must-not-persist",
            },
            "rawProfile": "must-not-persist",
        }

    def call(self, snapshot_store, *, resolver=resolved):
        return get_or_start_stat_snapshot(
            self.request(),
            authority_store=object(),
            snapshot_store=snapshot_store,
            simc_runtime_revision="simc-v1",
            request_id="request-stat",
            client_id="client-a",
            now="2026-07-11T12:00:00+00:00",
            resolver=resolver,
            profile_builder=profile_builder,
        )

    def test_cache_hit_is_200_even_when_worker_is_unavailable(self):
        cached = {
            "statSignature": SIGNATURE,
            "snapshotHash": "sha256:" + "c" * 64,
            "snapshot": {"statStatus": "verified", "secondary": []},
            "verifiedAt": "2026-07-11T11:59:00+00:00",
        }
        store = FakeSnapshotStore(cached=cached, ready=False)

        status, envelope = self.call(store)

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["data"]["statSnapshot"]["statStatus"], "verified")
        self.assertEqual([call[0] for call in store.calls], ["lookup"])

    def test_miss_with_fresh_matching_worker_returns_bounded_202(self):
        store = FakeSnapshotStore(ready=True)

        status, envelope = self.call(store)

        self.assertEqual(status, 202)
        self.assertEqual(envelope["status"], "pending")
        self.assertEqual(envelope["data"]["jobId"], 7)
        self.assertEqual(envelope["data"]["retryAfterMs"], 1500)
        queue_call = next(call for call in store.calls if call[0] == "queue")
        self.assertFalse(queue_call[2]["record_request"])
        persisted = queue_call[2]["request_payload"]
        self.assertEqual(set(persisted), {"selectionIntent", "profileContext"})
        self.assertNotIn("untrustedExtra", persisted["profileContext"])
        self.assertNotIn("rawProfile", persisted)

    def test_miss_without_fresh_matching_worker_returns_structured_503_without_job(self):
        store = FakeSnapshotStore(ready=False)

        status, envelope = self.call(store)

        self.assertEqual(status, 503)
        self.assertEqual(envelope["status"], "unavailable")
        self.assertEqual(envelope["problems"][0]["code"], "GEAR_STAT_WORKER_UNAVAILABLE")
        self.assertNotIn("queue", [call[0] for call in store.calls])

    def test_resolver_failure_is_preserved_and_never_touches_snapshot_store(self):
        def blocked(_intent, **_kwargs):
            return 409, {
                "contractRevision": "gear-result-envelope-v1",
                "requestId": "request-stat",
                "status": "blocked",
                "releaseContext": RELEASE,
                "data": {},
                "problems": [
                    {
                        "kind": "REVISION_CONFLICT",
                        "code": "GEAR_REVISION_CONFLICT",
                        "title": "revision conflict",
                        "detail": "",
                        "path": "",
                        "retryable": True,
                        "meta": {},
                    }
                ],
            }

        store = FakeSnapshotStore()
        status, envelope = self.call(store, resolver=blocked)

        self.assertEqual(status, 409)
        self.assertEqual(envelope["problems"][0]["code"], "GEAR_REVISION_CONFLICT")
        self.assertEqual(store.calls, [])

    def test_resolved_snapshot_serializer_forwards_stat_snapshot_execution_flavor(self):
        snapshot = {
            "contractRevision": "gear-resolved-snapshot-v1",
            "status": "verified",
            "resolvedGearSignature": "sha256:" + "d" * 64,
            "profileReadiness": {
                "status": "verified",
                "simcReady": True,
                "serializerRevision": "websim-profile-compat-v1",
            },
            "dependencyVector": {"serializerRevision": "websim-profile-compat-v1"},
            "serializerInput": {
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": "123",
                        "variantKey": "variant-123",
                        "simcOptions": {},
                    }
                ]
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
        }
        captured = {}

        def fake_response(payload, conn=None, execution_flavor=""):
            captured.update({"payload": payload, "conn": conn, "executionFlavor": execution_flavor})
            return {
                "profile": "mage=fixture\niterations=1",
                "profileReadiness": {"simcReady": True},
                "talentEncoding": {"status": "external"},
            }

        with patch.object(websim_payload, "build_websim_profile_response", side_effect=fake_response):
            response = websim_payload.build_websim_profile_response_from_resolved_snapshot(
                snapshot,
                source_context={"talents": "external-code"},
                execution_flavor=websim_payload.WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
            )

        self.assertEqual(response["status"], "resolved")
        self.assertIsNone(captured["conn"])
        self.assertEqual(
            captured["executionFlavor"],
            websim_payload.WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
        )


if __name__ == "__main__":
    unittest.main()
