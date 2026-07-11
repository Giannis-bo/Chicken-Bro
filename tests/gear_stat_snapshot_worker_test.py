import copy
import unittest

from server.gear_stat_snapshot_worker import LeaseLost, process_claimed_job


SIGNATURE = "stat-snapshot:sha256:" + "a" * 64
JOB = {
    "jobId": 7,
    "statSignature": SIGNATURE,
    "request": {
        "selectionIntent": {"schemaRevision": "selection-intent-v1"},
        "profileContext": {"talents": "external-code"},
    },
    "releaseContext": {"manifestRevision": "manifest-r1", "pointerGeneration": 9},
    "lockToken": "token-a",
}


def prepared(signature=SIGNATURE):
    return {
        "request": copy.deepcopy(JOB["request"]),
        "resolvedSnapshot": {
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90}
        },
        "releaseContext": copy.deepcopy(JOB["releaseContext"]),
        "profile": "mage=fixture\niterations=1\ncalculate_scale_factors=0",
        "signature": {
            "statSignature": signature,
            "schemaRevision": "stat-signature-v1",
            "resolvedGearSignature": "sha256:" + "b" * 64,
            "manifestRevision": "manifest-r1",
            "gearReleaseId": "gear-r1",
            "simcRuntimeRevision": "simc-v1",
            "dependencyVector": {"simcRuntimeRevision": "simc-v1"},
            "profileHash": "sha256:" + "c" * 64,
        },
    }


class FakeStore:
    def __init__(self):
        self.published = []
        self.failed = []

    def publish_verified(self, **kwargs):
        self.published.append(copy.deepcopy(kwargs))
        return {"status": "verified", "snapshotHash": kwargs["record"]["snapshotHash"]}

    def fail_job(self, **kwargs):
        self.failed.append(copy.deepcopy(kwargs))
        return True


def valid_result():
    return {
        "ran": True,
        "jsonPayload": {
            "sim": {
                "players": [
                    {
                        "collected_data": {
                            "buffed_stats": {
                                "attribute": {"intellect": 12345, "stamina": 54321},
                                "stats": {
                                    "crit_rating": 1200,
                                    "haste_rating": 1300,
                                    "mastery_rating": 1400,
                                    "versatility_rating": 1500,
                                    "armor": 900,
                                },
                            }
                        }
                    }
                ]
            }
        },
        "itemResolutionWarnings": [],
    }


class GearStatSnapshotWorkerTest(unittest.TestCase):
    def prepare(self, value):
        calls = []

        def fake(raw_request, **kwargs):
            calls.append((copy.deepcopy(raw_request), kwargs))
            return 200, {"status": "resolved"}, copy.deepcopy(value)

        return calls, fake

    def test_re_resolves_runs_one_child_and_publishes_verified_json_snapshot(self):
        store = FakeStore()
        prepare_calls, prepare = self.prepare(prepared())
        runner_calls = []

        outcome = process_claimed_job(
            copy.deepcopy(JOB),
            authority_store=object(),
            snapshot_store=store,
            simc_runtime_revision="simc-v1",
            worker_id="worker-a",
            now_fn=lambda: "2026-07-11T12:00:00+00:00",
            prepare=prepare,
            runner=lambda profile: runner_calls.append(profile) or valid_result(),
            run_with_heartbeat=lambda run, profile, heartbeat: run(profile),
        )

        self.assertEqual(outcome["status"], "verified")
        self.assertEqual(prepare_calls[0][0], JOB["request"])
        self.assertEqual(len(runner_calls), 1)
        self.assertEqual(len(store.published), 1)
        snapshot = store.published[0]["record"]["snapshot"]
        self.assertEqual(snapshot["statStatus"], "verified")
        self.assertNotIn("dps", snapshot)

    def test_signature_drift_blocks_before_simc(self):
        store = FakeStore()
        _calls, prepare = self.prepare(prepared("stat-snapshot:sha256:" + "d" * 64))

        outcome = process_claimed_job(
            copy.deepcopy(JOB),
            authority_store=object(),
            snapshot_store=store,
            simc_runtime_revision="simc-v1",
            worker_id="worker-a",
            now_fn=lambda: "2026-07-11T12:00:00+00:00",
            prepare=prepare,
            runner=lambda _profile: self.fail("SimC must not run after signature drift"),
            run_with_heartbeat=lambda run, profile, heartbeat: run(profile),
        )

        self.assertEqual(outcome["code"], "GEAR_STAT_SIGNATURE_DRIFT")
        self.assertTrue(store.failed[0]["deterministic"])

    def test_lost_heartbeat_fails_closed_without_publish(self):
        store = FakeStore()
        _calls, prepare = self.prepare(prepared())

        outcome = process_claimed_job(
            copy.deepcopy(JOB),
            authority_store=object(),
            snapshot_store=store,
            simc_runtime_revision="simc-v1",
            worker_id="worker-a",
            now_fn=lambda: "2026-07-11T12:00:00+00:00",
            prepare=prepare,
            runner=lambda _profile: valid_result(),
            run_with_heartbeat=lambda _run, _profile, _heartbeat: (_ for _ in ()).throw(LeaseLost()),
        )

        self.assertEqual(outcome["code"], "GEAR_STAT_LEASE_LOST")
        self.assertEqual(store.published, [])
        self.assertEqual(store.failed, [])

    def test_simc_runtime_failure_uses_transient_cooldown(self):
        store = FakeStore()
        _calls, prepare = self.prepare(prepared())

        outcome = process_claimed_job(
            copy.deepcopy(JOB),
            authority_store=object(),
            snapshot_store=store,
            simc_runtime_revision="simc-v1",
            worker_id="worker-a",
            now_fn=lambda: "2026-07-11T12:00:00+00:00",
            prepare=prepare,
            runner=lambda _profile: {"ran": False, "error": "private crash detail"},
            run_with_heartbeat=lambda run, profile, heartbeat: run(profile),
        )

        self.assertEqual(outcome["code"], "GEAR_STAT_SIMC_FAILED")
        self.assertFalse(store.failed[0]["deterministic"])
        self.assertNotIn("private crash detail", str(store.failed[0]))

    def test_missing_json_buffed_stats_is_deterministically_blocked(self):
        store = FakeStore()
        _calls, prepare = self.prepare(prepared())

        outcome = process_claimed_job(
            copy.deepcopy(JOB),
            authority_store=object(),
            snapshot_store=store,
            simc_runtime_revision="simc-v1",
            worker_id="worker-a",
            now_fn=lambda: "2026-07-11T12:00:00+00:00",
            prepare=prepare,
            runner=lambda _profile: {"ran": True, "jsonPayload": {}},
            run_with_heartbeat=lambda run, profile, heartbeat: run(profile),
        )

        self.assertEqual(outcome["code"], "GEAR_STAT_JSON_INVALID")
        self.assertTrue(store.failed[0]["deterministic"])
        self.assertEqual(store.published, [])


if __name__ == "__main__":
    unittest.main()
