import unittest

from server.gear_evidence_registry import build_evidence_artifact


GAP_KEY = "gear-gap:sha256:" + ("a" * 64)
FACT_KEY = "gear-fact:sha256:" + ("b" * 64)
NOW = "2026-07-27T01:02:03+00:00"


def gap(*, problem_code="artifact_missing", source_type="simc_item_probe"):
    requirement = {
        "seasonRevision": "midnight-season-1",
        "subjectKey": "item:250033/variant:void_upgrade-298",
        "factType": "socket_count",
        "requiredInputKey": "allowed_observation",
    }
    if source_type:
        requirement.update(
            {
                "sourceType": source_type,
                "sourceScope": "exact_variant",
                "sourceIdentity": "simc:item:250033:variant:void_upgrade-298",
                "sourceRevision": "simc:midnight-r1",
            }
        )
    return {
        "gapKey": GAP_KEY,
        "factKey": FACT_KEY,
        "problemCode": problem_code,
        "missingRequirement": requirement,
        "attempt": 1,
    }


def collected_artifact():
    return build_evidence_artifact(
        source_type="simc_item_probe",
        source_identity="simc:item:250033:variant:void_upgrade-298",
        source_revision="simc:midnight-r1",
        season_revision="midnight-season-1",
        captured_at=NOW,
        payload={
            "itemId": 250033,
            "variantKey": "void_upgrade-298",
            "socketCount": 1,
        },
    )


class FakeGapStore:
    def __init__(self, claimed=(), *, finish_error=None):
        self.claimed = list(claimed)
        self.claim_calls = []
        self.finished = []
        self.finish_error = finish_error

    def claim_next(self, **kwargs):
        self.claim_calls.append(kwargs)
        return self.claimed.pop(0) if self.claimed else {}

    def finish(self, **kwargs):
        self.finished.append(kwargs)
        if self.finish_error:
            raise self.finish_error
        return {"gapKey": kwargs["gap_key"], "status": kwargs["outcome"]["status"]}


class FakeEvidenceStore:
    def __init__(self):
        self.artifacts = []
        self.observations = []

    def persist_artifact(self, artifact):
        self.artifacts.append(artifact)
        return artifact

    def persist_observation(self, observation):
        self.observations.append(observation)
        return observation

    def persist_fact(self, _fact):
        raise AssertionError("gap worker must not write canonical facts")


class FakeCandidateRequestStore:
    def __init__(self):
        self.handoffs = []

    def handoff_recovered(self, **kwargs):
        self.handoffs.append(kwargs)
        return {
            "status": "candidate_pending",
            "requestKey": kwargs["request"]["requestKey"],
        }


class ArtifactCollector:
    def __init__(self, callback):
        self.callback = callback

    def collect(self, route, *, now):
        return {"status": "artifact", "artifact": self.callback(route, now)}


class GearEvidenceGapWorkerTest(unittest.TestCase):
    def test_simc_bonus_collector_replays_one_socket_for_the_strict_target_route(self):
        from server.gear_evidence_gap_worker import SimcBonusSocketCollector
        from server.gear_evidence_observers import observe_artifact

        loader_calls = []
        collector = SimcBonusSocketCollector(
            lambda: loader_calls.append("loaded") or {
                "schemaRevision": "simc-socket-bonus-evidence-v1",
                "status": "verified",
                "sourceType": "simc_bonus_probe",
                "sourceIdentity": "simulationcraft:show_bonus_ids",
                "sourceRevision": "simc-midnight-abcdef",
                "sourceScope": "exact_variant",
                "minimums": {"298": 1},
            }
        )

        result = collector.collect(
            {
                "factType": "socket_count",
                "seasonRevision": "midnight-season-1",
                "sourceScope": "exact_variant",
                "sourceType": "simc_bonus_probe",
                "subjectKey": "item:250033/variant:void_upgrade-298",
            },
            now=NOW,
        )

        self.assertEqual(loader_calls, ["loaded"])
        self.assertEqual(result["status"], "artifact")
        artifact = result["artifact"]
        self.assertEqual(artifact["sourceType"], "simc_bonus_probe")
        self.assertEqual(artifact["sourceIdentity"], "simulationcraft:show_bonus_ids")
        self.assertEqual(artifact["sourceRevision"], "simc-midnight-abcdef")
        self.assertEqual(
            artifact["payload"],
            {
                "bonusId": 298,
                "factType": "socket_count",
                "socketCount": 1,
                "subjectKey": "item:250033/variant:void_upgrade-298",
            },
        )
        observed = observe_artifact(artifact)
        self.assertEqual(observed["status"], "accepted")
        self.assertEqual(
            [
                (row["subjectKey"], row["factType"], row["observedValue"])
                for row in observed["observations"]
            ],
            [("item:250033/variant:void_upgrade-298", "socket_count", 1)],
        )

    def test_fenced_handoff_cannot_reclaim_the_same_gap_in_one_run(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        class ReclaimingGapStore:
            def __init__(self):
                self.current = {
                    **gap(source_type="simc_item_probe"),
                    "nextAttemptAt": NOW,
                }
                self.claim_calls = 0
                self.finished = []

            def claim_next(self, **_kwargs):
                self.claim_calls += 1
                if self.current is None or self.current["nextAttemptAt"] > NOW:
                    return {}
                return dict(self.current)

            def finish(self, **kwargs):
                self.finished.append(kwargs)
                self.current["nextAttemptAt"] = kwargs["outcome"].get("nextAttemptAt", "9999-12-31T00:00:00+00:00")
                return {"gapKey": kwargs["gap_key"], "status": kwargs["outcome"]["status"]}

        store = ReclaimingGapStore()

        class CandidateRequestStore(FakeCandidateRequestStore):
            def handoff_recovered(self, **kwargs):
                store.current["nextAttemptAt"] = "9999-12-31T00:00:00+00:00"
                return super().handoff_recovered(**kwargs)

        candidate_requests = CandidateRequestStore()

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=FakeEvidenceStore(),
            approved_collectors={"simc_item_probe": ArtifactCollector(lambda _route, _now: collected_artifact())},
            candidate_request_store=candidate_requests,
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-paced",
        )

        self.assertEqual(result["claimedCount"], 1)
        self.assertEqual(store.claim_calls, 2)
        self.assertEqual(result["candidateHandoffCount"], 1)
        self.assertEqual(store.finished, [])

    def test_artifact_provenance_mismatch_is_retried_before_any_persistence(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        mismatches = {
            "source_type": "battle_net_item",
            "source_identity": "simc:item:wrong-identity",
            "source_revision": "simc:midnight-r2",
            "season_revision": "midnight-season-2",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                artifact_fields = {
                    "source_type": "simc_item_probe",
                    "source_identity": "simc:item:250033:variant:void_upgrade-298",
                    "source_revision": "simc:midnight-r1",
                    "season_revision": "midnight-season-1",
                }
                artifact_fields[field] = value

                class ArtifactAdapter:
                    def collect(self, _route, *, now):
                        return {
                            "status": "artifact",
                            "artifact": build_evidence_artifact(
                                **artifact_fields,
                                captured_at=NOW,
                                payload={
                                    "itemId": 250033,
                                    "variantKey": "void_upgrade-298",
                                    "socketCount": 1,
                                },
                            ),
                        }

                evidence_store = FakeEvidenceStore()
                store = FakeGapStore([gap()])
                result = run_gear_evidence_gap_worker(
                    gap_store=store,
                    evidence_store=evidence_store,
                    approved_collectors={"simc_item_probe": ArtifactAdapter()},
                    candidate_request_store=FakeCandidateRequestStore(),
                    worker_id="test-gap-worker",
                    now=NOW,
                    lock_token_factory=lambda _: "lease-token-provenance",
                )

                self.assertEqual(result["retryableCount"], 1)
                self.assertEqual(evidence_store.artifacts, [])
                self.assertEqual(store.finished[0]["outcome"]["problemCode"], "source_unavailable")
                self.assertGreater(store.finished[0]["outcome"]["nextAttemptAt"], NOW)

    def test_real_missing_fact_route_hands_off_only_a_fenced_candidate_request_without_a_fact_or_publish_call(self):
        from server.gear_evidence_gap_worker import (
            run_gear_evidence_gap_worker,
            runtime_approved_collection_adapters,
        )
        from server.gear_evidence_registry import build_canonical_fact
        from server.gear_fact_compiler import evidence_gaps_from_facts

        fact = build_canonical_fact(
            season_revision="midnight-season-1",
            subject_key="item:250033/variant:void_upgrade-298",
            fact_type="socket_count",
            value=None,
            status="unresolved_missing",
            observation_refs=[],
            compiler_rule_revision="gear-socket-count-policy-v1",
            impact_scope="socket_only",
            problem_code="artifact_missing",
        )
        projected = evidence_gaps_from_facts([fact])[0]
        routed_gap = {
            "gapKey": GAP_KEY,
            "factKey": projected["factKey"],
            "problemCode": projected["problemCode"],
            "missingRequirement": projected["missingRequirement"],
            "attempt": 1,
        }
        candidate_requests = FakeCandidateRequestStore()

        result = run_gear_evidence_gap_worker(
            gap_store=FakeGapStore([routed_gap]),
            evidence_store=FakeEvidenceStore(),
            approved_collectors=runtime_approved_collection_adapters(
                lambda: {
                    "schemaRevision": "simc-socket-bonus-evidence-v1",
                    "status": "verified",
                    "sourceType": "simc_bonus_probe",
                    "sourceIdentity": "simulationcraft:show_bonus_ids",
                    "sourceRevision": "simc-midnight-abcdef",
                    "sourceScope": "exact_variant",
                    "minimums": {"298": 1},
                }
            ),
            candidate_request_store=candidate_requests,
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-route",
        )

        self.assertEqual(result["candidateHandoffCount"], 1)
        self.assertEqual(
            candidate_requests.handoffs[0]["request"],
            {
                "gapKey": GAP_KEY,
                "artifactId": candidate_requests.handoffs[0]["request"]["artifactId"],
                "factType": "socket_count",
                "observationIds": candidate_requests.handoffs[0]["request"]["observationIds"],
                "requestKey": candidate_requests.handoffs[0]["request"]["requestKey"],
                "schemaRevision": "gear-evidence-candidate-request-v1",
                "seasonRevision": "midnight-season-1",
                "sourceType": "simc_bonus_probe",
                "status": "candidate_pending",
                "subjectKey": "item:250033/variant:void_upgrade-298",
                "attempt": 0,
                "nextAttemptAt": NOW,
            },
        )
        self.assertNotIn("value", str(candidate_requests.handoffs))

    def test_worker_rejects_an_arbitrary_candidate_callable_instead_of_executing_it(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        with self.assertRaisesRegex(ValueError, "candidate request store"):
            run_gear_evidence_gap_worker(
                gap_store=FakeGapStore(),
                evidence_store=FakeEvidenceStore(),
                approved_collectors={},
                candidate_request_store=lambda request: self.fail(f"must not call arbitrary code: {request}"),
                worker_id="test-gap-worker",
                now=NOW,
            )
    def test_approved_collection_persists_only_artifact_observations_and_hands_off_candidate_recompile(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        store = FakeGapStore([gap()])
        evidence_store = FakeEvidenceStore()
        collector_inputs = []

        def collect(requirement, _now):
            collector_inputs.append(requirement)
            return collected_artifact()

        candidate_requests = FakeCandidateRequestStore()

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=evidence_store,
            approved_collectors={"simc_item_probe": ArtifactCollector(collect)},
            candidate_request_store=candidate_requests,
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-1",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["processedCount"], 0)
        self.assertEqual(result["candidateHandoffCount"], 1)
        self.assertEqual(
            collector_inputs,
            [
                {
                    "factKey": FACT_KEY,
                    "factType": "socket_count",
                    "gapKey": GAP_KEY,
                    "seasonRevision": "midnight-season-1",
                    "sourceIdentity": "simc:item:250033:variant:void_upgrade-298",
                    "sourceRevision": "simc:midnight-r1",
                    "sourceScope": "exact_variant",
                    "sourceType": "simc_item_probe",
                    "subjectKey": "item:250033/variant:void_upgrade-298",
                }
            ],
        )
        self.assertEqual(len(evidence_store.artifacts), 1)
        self.assertEqual(len(evidence_store.observations), 1)
        self.assertEqual(store.finished, [])
        self.assertEqual(candidate_requests.handoffs[0]["request"]["gapKey"], GAP_KEY)

    def test_recovered_evidence_is_atomically_handed_to_a_fenced_candidate_request_without_finishing_its_gap(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        class CandidateRequestStore:
            def __init__(self):
                self.handoffs = []

            def handoff_recovered(self, **kwargs):
                self.handoffs.append(kwargs)
                return {"status": "candidate_pending", "requestKey": kwargs["request"]["requestKey"]}

        gap_store = FakeGapStore([gap()])
        evidence_store = FakeEvidenceStore()
        candidate_requests = CandidateRequestStore()

        result = run_gear_evidence_gap_worker(
            gap_store=gap_store,
            evidence_store=evidence_store,
            approved_collectors={"simc_item_probe": ArtifactCollector(lambda _route, _now: collected_artifact())},
            candidate_request_store=candidate_requests,
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "gap-lock",
        )

        self.assertEqual(result["candidateHandoffCount"], 1)
        self.assertEqual(result["processedCount"], 0)
        self.assertEqual(gap_store.finished, [])
        self.assertEqual(len(evidence_store.artifacts), 1)
        self.assertEqual(len(evidence_store.observations), 1)
        self.assertEqual(len(candidate_requests.handoffs), 1)
        handoff = candidate_requests.handoffs[0]
        self.assertEqual(handoff["gap_lock_token"], "gap-lock")
        self.assertEqual(handoff["request"]["gapKey"], GAP_KEY)
        self.assertEqual(handoff["request"]["artifactId"], evidence_store.artifacts[0]["artifactId"])
        self.assertEqual(
            handoff["request"]["observationIds"],
            [evidence_store.observations[0]["observationId"]],
        )

    def test_unapproved_or_missing_collector_is_retryable_without_calling_any_adapter(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        store = FakeGapStore([gap(source_type="unapproved_source")])
        called = []

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=FakeEvidenceStore(),
            approved_collectors={"simc_item_probe": ArtifactCollector(lambda requirement, now: called.append(requirement))},
            candidate_request_store=FakeCandidateRequestStore(),
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-2",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(called, [])
        self.assertEqual(store.finished[0]["outcome"]["status"], "terminal")
        self.assertEqual(store.finished[0]["outcome"]["problemCode"], "compiler_policy_missing")

    def test_parser_rejection_is_retryable_and_never_invents_a_fact(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        store = FakeGapStore([gap()])
        evidence_store = FakeEvidenceStore()

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=evidence_store,
            approved_collectors={"simc_item_probe": ArtifactCollector(lambda requirement, now: collected_artifact())},
            artifact_observer=lambda artifact: {
                "status": "rejected",
                "observations": [],
                "diagnostics": [{"code": "parser_unhandled_shape"}],
            },
            candidate_request_store=FakeCandidateRequestStore(),
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-3",
        )

        self.assertEqual(result["retryableCount"], 1)
        self.assertEqual(len(evidence_store.artifacts), 1)
        self.assertEqual(evidence_store.observations, [])
        self.assertEqual(store.finished[0]["outcome"]["problemCode"], "parser_unhandled_shape")

    def test_conflict_is_terminal_without_collecting_or_overwriting_the_conflict(self):
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        store = FakeGapStore([gap(problem_code="observation_conflict")])

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=FakeEvidenceStore(),
            approved_collectors={},
            candidate_request_store=FakeCandidateRequestStore(),
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-4",
        )

        self.assertEqual(result["terminalCount"], 1)
        self.assertEqual(store.finished[0]["outcome"]["status"], "terminal")
        self.assertEqual(store.finished[0]["outcome"]["problemCode"], "observation_conflict")

    def test_lost_lease_is_reported_not_masked_as_completed(self):
        from server.gear_evidence_gap_store import GearEvidenceGapIntegrityError
        from server.gear_evidence_gap_worker import run_gear_evidence_gap_worker

        store = FakeGapStore(
            [gap()],
            finish_error=GearEvidenceGapIntegrityError("Gear Evidence Gap lease was lost before completion."),
        )

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=FakeEvidenceStore(),
            approved_collectors={"simc_item_probe": ArtifactCollector(lambda requirement, now: collected_artifact())},
            candidate_request_store=FakeCandidateRequestStore(),
            artifact_observer=lambda _artifact: {
                "status": "rejected",
                "observations": [],
                "diagnostics": [{"code": "parser_unhandled_shape"}],
            },
            worker_id="test-gap-worker",
            now=NOW,
            lock_token_factory=lambda _: "lease-token-5",
        )

        self.assertEqual(result["status"], "lease_lost")
        self.assertEqual(result["processedCount"], 0)
        self.assertEqual(result["leaseLostCount"], 1)

    def test_claim_loop_never_exceeds_the_fixed_job_limit(self):
        from server.gear_evidence_gap_worker import MAX_GAP_JOBS_PER_RUN, run_gear_evidence_gap_worker

        claimed = [{**gap(), "gapKey": "gear-gap:sha256:" + (f"{index:x}" * 64)[:64]} for index in range(MAX_GAP_JOBS_PER_RUN + 2)]
        store = FakeGapStore(claimed)

        result = run_gear_evidence_gap_worker(
            gap_store=store,
            evidence_store=FakeEvidenceStore(),
            approved_collectors={},
            candidate_request_store=FakeCandidateRequestStore(),
            worker_id="test-gap-worker",
            now=NOW,
            max_jobs=MAX_GAP_JOBS_PER_RUN + 99,
            lock_token_factory=lambda index: f"lease-token-{index}",
        )

        self.assertEqual(result["claimedCount"], MAX_GAP_JOBS_PER_RUN)
        self.assertEqual(len(store.claim_calls), MAX_GAP_JOBS_PER_RUN)


if __name__ == "__main__":
    unittest.main()
