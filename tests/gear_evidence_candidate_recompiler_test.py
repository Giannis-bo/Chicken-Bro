import unittest
from pathlib import Path

from server.gear_evidence_registry import (
    build_evidence_artifact,
    build_evidence_observation,
)


GAP_KEY = "gear-gap:sha256:" + ("a" * 64)
NOW = "2026-07-27T01:02:03+00:00"
SUBJECT_KEY = "item:250033/variant:void_upgrade-298"


def collected_artifact():
    return build_evidence_artifact(
        source_type="simc_bonus_probe",
        source_identity="simulationcraft:show_bonus_ids",
        source_revision="simc-midnight-abcdef",
        season_revision="midnight-season-1",
        captured_at=NOW,
        payload={
            "bonusId": 298,
            "factType": "socket_count",
            "socketCount": 1,
            "subjectKey": SUBJECT_KEY,
        },
    )


def collected_observation(artifact):
    return build_evidence_observation(
        artifact_id=artifact["artifactId"],
        subject_key=SUBJECT_KEY,
        fact_type="socket_count",
        observed_value=1,
        parser_revision="simc-bonus-probe-observer-v1",
        source_scope="exact_variant",
        status="accepted",
    )


class FakeRequestStore:
    def __init__(self, request):
        self.request = request
        self.claimed = False
        self.completed = []
        self.retried = []

    def claim_next(self, **_kwargs):
        if self.claimed:
            return {}
        self.claimed = True
        return self.request

    def complete_sealed(self, **kwargs):
        self.completed.append(kwargs)
        return {"status": "terminal", "requestKey": kwargs["request_key"]}

    def retry(self, **kwargs):
        self.retried.append(kwargs)
        return {"status": "retryable", "requestKey": kwargs["request_key"]}


class FakeEvidenceStore:
    def __init__(self, artifact, observation):
        self.artifact = artifact
        self.observation = observation

    def load_candidate_evidence(self, **kwargs):
        self.loaded = kwargs
        return {"artifacts": [self.artifact], "observations": [self.observation]}


class FakeCursor:
    def __init__(self, responder):
        self.responder = responder
        self.statements = []
        self.params = []
        self.current = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        self.params.append(params)
        self.current = self.responder(normalized, params)

    def fetchone(self):
        return self.current[0] if isinstance(self.current, list) and self.current else self.current

    def fetchall(self):
        return self.current if isinstance(self.current, list) else []


class FakeConnection:
    def __init__(self, responder):
        self.cursor_instance = FakeCursor(responder)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        return None


class GearEvidenceCandidateRecompilerTest(unittest.TestCase):
    def test_consumer_seals_candidate_before_it_completes_the_fenced_request_and_gap(self):
        from server.gear_evidence_candidate_recompiler import (
            run_gear_evidence_candidate_recompiler,
        )
        from server.gear_evidence_candidate_request_store import (
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )
        request = {**request, "lockToken": "candidate-lock"}
        request_store = FakeRequestStore(request)
        evidence_store = FakeEvidenceStore(artifact, observation)
        builder_calls = []

        def build_candidate(*, collected_evidence, request):
            self.assertEqual(request_store.completed, [])
            builder_calls.append((collected_evidence, request))
            return {
                "gearRelease": {"releaseId": "gear-release:candidate"},
                "gearSeal": {"status": "inserted", "releaseId": "gear-release:candidate"},
            }

        result = run_gear_evidence_candidate_recompiler(
            request_store=request_store,
            evidence_store=evidence_store,
            candidate_builder=build_candidate,
            worker_id="candidate-worker",
            now=NOW,
            lock_token_factory=lambda _: "candidate-lock",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sealedCount"], 1)
        self.assertEqual(len(builder_calls), 1)
        self.assertEqual(evidence_store.loaded["artifact_id"], artifact["artifactId"])
        self.assertEqual(evidence_store.loaded["observation_ids"], [observation["observationId"]])
        self.assertEqual(request_store.retried, [])
        self.assertEqual(
            request_store.completed,
            [
                {
                    "candidate_gear_release_id": "gear-release:candidate",
                    "lock_token": "candidate-lock",
                    "now": NOW,
                    "request_key": request["requestKey"],
                }
            ],
        )

    def test_candidate_build_failure_keeps_the_fenced_request_and_gap_retryable(self):
        from server.gear_evidence_candidate_recompiler import (
            run_gear_evidence_candidate_recompiler,
        )
        from server.gear_evidence_candidate_request_store import (
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )
        request = {**request, "lockToken": "candidate-lock"}
        request_store = FakeRequestStore(request)

        result = run_gear_evidence_candidate_recompiler(
            request_store=request_store,
            evidence_store=FakeEvidenceStore(artifact, observation),
            candidate_builder=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("seal failed")),
            worker_id="candidate-worker",
            now=NOW,
            lock_token_factory=lambda _: "candidate-lock",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["retryableCount"], 1)
        self.assertEqual(request_store.completed, [])
        self.assertEqual(
            request_store.retried,
            [
                {
                    "lock_token": "candidate-lock",
                    "now": NOW,
                    "problem_code": "candidate_recompile_failed",
                    "request_key": request["requestKey"],
                }
            ],
        )

    def test_runtime_consumer_is_candidate_only_and_has_a_dedicated_oneshot(self):
        root = Path(__file__).resolve().parents[1]
        consumer_source = (root / "server" / "gear_evidence_candidate_recompiler.py").read_text(
            encoding="utf-8"
        )
        service_source = (root / "server" / "wow-gear-evidence-candidate-recompiler.service").read_text(
            encoding="utf-8"
        )
        deploy_source = (root / "server" / "deploy_lighthouse.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("build_staging_candidates", consumer_source)
        self.assertIn("extra_artifacts", consumer_source)
        self.assertIn("extra_observations", consumer_source)
        self.assertNotIn("run_release_refresh", consumer_source)
        self.assertNotIn("seal_manifest", consumer_source)
        self.assertNotIn("compare_and_swap", consumer_source)
        self.assertIn("gear_evidence_candidate_recompiler.py --json", service_source)
        self.assertIn("NoNewPrivileges=true", service_source)
        self.assertIn("wow-gear-evidence-candidate-recompiler.service", deploy_source)

    def test_candidate_runtime_rejects_nonformal_or_incomplete_active_bindings(self):
        from server.gear_evidence_candidate_recompiler import _formal_active_binding

        with self.assertRaisesRegex(RuntimeError, "formal active Manifest"):
            _formal_active_binding({"formalActiveManifest": False})
        with self.assertRaisesRegex(RuntimeError, "complete active release pair"):
            _formal_active_binding({"formalActiveManifest": True, "manifest": {}})
        binding = {
            "formalActiveManifest": True,
            "manifest": {"seasonRevision": "midnight-season-1"},
            "gearRelease": {"releaseId": "gear-release:active"},
            "communityRelease": {"releaseId": "community-release:active"},
        }
        self.assertIs(_formal_active_binding(binding), binding)


class GearEvidenceCandidateRequestStoreTest(unittest.TestCase):
    def test_duplicate_observation_cannot_create_an_ambiguous_candidate_request_identity(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestIntegrityError,
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)

        with self.assertRaises(GearEvidenceCandidateRequestIntegrityError):
            build_candidate_recompile_request(
                gap_key=GAP_KEY,
                artifact=artifact,
                observations=[observation, observation],
                now=NOW,
            )

    def test_store_rejects_a_request_key_that_does_not_match_its_fenced_evidence_identity(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestIntegrityError,
            GearEvidenceCandidateRequestStore,
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )
        forged = {
            **request,
            "requestKey": "gear-candidate-request:sha256:" + ("f" * 64),
        }

        store = GearEvidenceCandidateRequestStore(
            lambda: self.fail("forged request must fail before opening a connection")
        )
        with self.assertRaises(GearEvidenceCandidateRequestIntegrityError):
            store.enqueue(forged, now=NOW)

    def test_recovered_gap_handoff_links_one_pending_candidate_request_under_the_worker_lease(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestStore,
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )

        connection = FakeConnection(
            lambda sql, _params: {**request, "status": "candidate_pending"}
            if "gear_evidence_candidate_handoff_gap" in sql
            else None
        )
        store = GearEvidenceCandidateRequestStore(lambda: connection)

        handoff = store.handoff_recovered(
            request=request,
            gap_lock_token="gap-lock",
            now=NOW,
        )

        self.assertEqual(handoff["requestKey"], request["requestKey"])
        self.assertEqual(handoff["status"], "candidate_pending")
        self.assertEqual(connection.commits, 1)
        sql = "\n".join(connection.cursor_instance.statements)
        self.assertIn("gear_evidence_candidate_handoff_insert", sql)
        self.assertIn("gear_evidence_candidate_handoff_gap", sql)
        self.assertIn("gap.status = 'running'", sql)
        self.assertIn("gap.lock_token = %s", sql)
        self.assertIn("status = 'candidate_pending'", sql)
        self.assertIn("candidate_request_key = %s", sql)

    def test_claim_retry_and_seal_keep_request_and_gap_in_one_fenced_handoff(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestStore,
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )
        claimed = {**request, "status": "candidate_running", "lockToken": "candidate-lock", "attempt": 1}

        def responder(sql, _params):
            if "gear_evidence_candidate_enqueue" in sql:
                return {"requestKey": request["requestKey"], "status": "candidate_pending"}
            if "gear_evidence_candidate_claim" in sql:
                return claimed
            if "gear_evidence_candidate_retry" in sql:
                return {"requestKey": request["requestKey"], "status": "candidate_pending"}
            if "gear_evidence_candidate_complete" in sql:
                return {"requestKey": request["requestKey"], "status": "terminal"}
            return None

        connection = FakeConnection(responder)
        store = GearEvidenceCandidateRequestStore(lambda: connection)

        self.assertEqual(store.enqueue(request, now=NOW)["status"], "candidate_pending")
        claimed_result = store.claim_next(
            worker_id="candidate-worker", lock_token="candidate-lock", now=NOW
        )
        self.assertEqual(claimed_result["requestKey"], request["requestKey"])
        self.assertEqual(claimed_result["gapKey"], GAP_KEY)
        self.assertEqual(claimed_result["status"], "candidate_running")
        self.assertEqual(claimed_result["attempt"], 1)
        self.assertEqual(claimed_result["lockToken"], "candidate-lock")
        self.assertEqual(
            store.retry(
                request_key=request["requestKey"],
                lock_token="candidate-lock",
                problem_code="candidate_recompile_failed",
                now=NOW,
            )["status"],
            "candidate_pending",
        )
        self.assertEqual(
            store.complete_sealed(
                request_key=request["requestKey"],
                lock_token="candidate-lock",
                candidate_gear_release_id="gear-release:candidate",
                now=NOW,
            )["status"],
            "terminal",
        )
        self.assertGreaterEqual(connection.commits, 4)
        sql = "\n".join(connection.cursor_instance.statements)
        self.assertIn("candidate_pending", sql)
        self.assertIn("candidate_running", sql)
        self.assertIn("FOR UPDATE OF request, gap SKIP LOCKED", sql)
        self.assertIn("ops.websim_gear_evidence_gaps", sql)

    def test_stale_candidate_lease_returns_only_the_same_linked_gap_to_candidate_pending(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestStore,
            build_candidate_recompile_request,
        )

        artifact = collected_artifact()
        observation = collected_observation(artifact)
        request = build_candidate_recompile_request(
            gap_key=GAP_KEY,
            artifact=artifact,
            observations=[observation],
            now=NOW,
        )
        reclaimed = {**request, "status": "candidate_running", "lockToken": "fresh-lock", "attempt": 2}

        connection = FakeConnection(
            lambda sql, _params: reclaimed if "gear_evidence_candidate_claim" in sql else None
        )
        store = GearEvidenceCandidateRequestStore(lambda: connection)

        reclaimed_result = store.claim_next(
            worker_id="candidate-worker", lock_token="fresh-lock", now=NOW
        )
        self.assertEqual(reclaimed_result["requestKey"], request["requestKey"])
        self.assertEqual(reclaimed_result["status"], "candidate_running")
        self.assertEqual(reclaimed_result["attempt"], 2)
        self.assertEqual(reclaimed_result["lockToken"], "fresh-lock")
        sql = "\n".join(connection.cursor_instance.statements)
        self.assertIn("candidate_running", sql)
        self.assertIn("lease_until <", sql)
        self.assertIn("candidate_pending", sql)
        self.assertIn("gap_key = request.gap_key", sql)

    def test_exhausted_candidate_attempt_is_terminalized_with_its_linked_gap_before_any_new_claim(self):
        from server.gear_evidence_candidate_request_store import (
            GearEvidenceCandidateRequestStore,
        )

        connection = FakeConnection(
            lambda sql, _params: None if "gear_evidence_candidate_claim" in sql else None
        )
        store = GearEvidenceCandidateRequestStore(lambda: connection)

        self.assertEqual(
            store.claim_next(
                worker_id="candidate-worker",
                lock_token="fresh-lock",
                now=NOW,
            ),
            {},
        )

        sql = "\n".join(connection.cursor_instance.statements)
        self.assertIn("WITH exhausted AS", sql)
        self.assertIn("request.attempt >= 3", sql)
        self.assertIn("exhausted_gaps AS", sql)
        self.assertIn("status = 'terminal'", sql)
        self.assertIn("problem_code = 'source_unavailable'", sql)
        self.assertLess(sql.index("WITH exhausted AS"), sql.index("next_request AS"))


if __name__ == "__main__":
    unittest.main()
