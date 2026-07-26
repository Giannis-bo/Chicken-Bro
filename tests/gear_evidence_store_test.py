#!/usr/bin/env python3
import unittest

from server.gear_evidence_gap_store import (
    GearEvidenceGapIntegrityError,
    GearEvidenceGapStore,
)
from server.gear_evidence_registry import (
    build_canonical_fact,
    build_evidence_artifact,
    build_evidence_observation,
)
from server.gear_evidence_store import GearEvidenceStore


class MissingArtifactError(RuntimeError):
    pass


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
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if self.current is None:
            return []
        return self.current if isinstance(self.current, list) else [self.current]


class FakeConnection:
    def __init__(self, responder):
        self.cursor_instance = FakeCursor(responder)
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if not exc_type:
            self.commits += 1
        return False

    def cursor(self):
        return self.cursor_instance


def artifact_fixture():
    return build_evidence_artifact(
        source_type="simc_item_probe",
        source_identity="simc:item:250033:bonus:298",
        source_revision="simc:midnight-r1",
        season_revision="midnight-season-1",
        captured_at="2026-07-26T02:00:00+00:00",
        payload={"itemId": 250033, "bonusId": 298, "socketCount": 1},
    )


def observation_fixture(artifact):
    return build_evidence_observation(
        artifact_id=artifact["artifactId"],
        subject_key="item:250033/variant:void_upgrade-298",
        fact_type="socket_count",
        observed_value=1,
        parser_revision="gear-socket-observer-v1",
        source_scope="exact_variant",
        status="accepted",
    )


def fact_fixture(observation, *, value=1):
    return build_canonical_fact(
        season_revision="midnight-season-1",
        subject_key="item:250033/variant:void_upgrade-298",
        fact_type="socket_count",
        value=value,
        status="verified",
        observation_refs=[observation["observationId"]],
        compiler_rule_revision="gear-capability-matrix-v3",
        impact_scope="socket_only",
    )


def gap_fixture(fact):
    return {
        "schemaRevision": "gear-evidence-gap-v1",
        "gapKey": "gear-gap:sha256:" + ("a" * 64),
        "factKey": fact["factKey"],
        "status": "pending",
        "problemCode": "artifact_missing",
        "missingRequirement": {
            "sourceType": "simc_item_probe",
            "subjectKey": fact["subjectKey"],
            "factType": fact["factType"],
        },
        "attempt": 0,
        "nextAttemptAt": "2026-07-26T02:00:00+00:00",
    }


def gap_row(gap, *, status="pending", attempt=0, lock_token=""):
    return (
        gap["gapKey"],
        gap["factKey"],
        gap["schemaRevision"],
        status,
        gap["problemCode"],
        gap["missingRequirement"],
        attempt,
        "worker-a" if status == "running" else "",
        lock_token,
        "2026-07-26T02:02:00+00:00" if status == "running" else None,
        gap["nextAttemptAt"],
        "2026-07-26T02:00:00+00:00",
        "2026-07-26T02:01:00+00:00" if status == "running" else None,
        None,
        "2026-07-26T02:00:00+00:00",
        "2026-07-26T02:00:00+00:00",
    )


class GearEvidenceStoreTest(unittest.TestCase):
    def test_duplicate_artifact_and_observation_reuse_immutable_rows(self):
        artifact = artifact_fixture()
        duplicate_artifact = build_evidence_artifact(
            source_type="battle_net_item",
            source_identity=artifact["sourceIdentity"],
            source_revision=artifact["sourceRevision"],
            season_revision=artifact["seasonRevision"],
            captured_at="2026-07-26T03:00:00+00:00",
            payload=artifact["payload"],
        )
        observation = observation_fixture(artifact)
        insert_counts = {"artifact": 0, "observation": 0}

        def responder(sql, _params):
            if "INSERT INTO cache.websim_gear_evidence_artifacts" in sql:
                insert_counts["artifact"] += 1
                return (artifact,) if insert_counts["artifact"] == 1 else None
            if (
                "FROM cache.websim_gear_evidence_artifacts" in sql
                and "WHERE artifact_id = %s" in sql
            ):
                return (artifact,)
            if "INSERT INTO cache.websim_gear_evidence_observations" in sql:
                insert_counts["observation"] += 1
                return (
                    (observation,)
                    if insert_counts["observation"] == 1
                    else None
                )
            if (
                "FROM cache.websim_gear_evidence_observations" in sql
                and "WHERE observation_id = %s" in sql
            ):
                return (observation,)
            return None

        conn = FakeConnection(responder)
        store = GearEvidenceStore(lambda: conn)

        self.assertEqual(store.persist_artifact(artifact), artifact)
        self.assertEqual(artifact["artifactId"], duplicate_artifact["artifactId"])
        self.assertEqual(store.persist_artifact(duplicate_artifact), artifact)
        self.assertEqual(store.persist_observation(observation), observation)
        self.assertEqual(store.persist_observation(observation), observation)

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("ON CONFLICT (artifact_id) DO NOTHING", sql)
        self.assertIn("ON CONFLICT (observation_id) DO NOTHING", sql)
        self.assertNotIn("DO UPDATE", sql)
        self.assertNotIn(
            "UPDATE cache.websim_gear_evidence_artifacts",
            sql,
        )
        self.assertNotIn(
            "UPDATE cache.websim_gear_evidence_observations",
            sql,
        )

    def test_observation_insert_relies_on_artifact_foreign_key_and_propagates_failure(self):
        artifact = artifact_fixture()
        observation = observation_fixture(artifact)

        def responder(sql, _params):
            if "INSERT INTO cache.websim_gear_evidence_observations" in sql:
                raise MissingArtifactError("artifact foreign key missing")
            return None

        conn = FakeConnection(responder)

        with self.assertRaisesRegex(MissingArtifactError, "artifact foreign key missing"):
            GearEvidenceStore(lambda: conn).persist_observation(observation)

        self.assertFalse(conn.commits)

    def test_facts_append_distinct_value_and_provenance_versions(self):
        artifact = artifact_fixture()
        observation = observation_fixture(artifact)
        socket_one = fact_fixture(observation, value=1)
        socket_zero = fact_fixture(observation, value=0)
        duplicate_socket_one = build_canonical_fact(
            season_revision=socket_one["seasonRevision"],
            subject_key=socket_one["subjectKey"],
            fact_type=socket_one["factType"],
            value=socket_one["value"],
            status=socket_one["status"],
            observation_refs=socket_one["observationRefs"],
            compiler_rule_revision=socket_one["compilerRuleRevision"],
            impact_scope="whole_variant",
        )
        stored_facts = {}

        def responder(sql, params):
            if "INSERT INTO cache.websim_gear_canonical_facts" in sql:
                identity = (params[0], params[8], params[9])
                if identity in stored_facts:
                    return None
                persisted = socket_one if identity[1] == socket_one["factValueHash"] else socket_zero
                stored_facts[identity] = persisted
                return (persisted,)
            if (
                "FROM cache.websim_gear_canonical_facts" in sql
                and "WHERE fact_key = %s" in sql
            ):
                return (stored_facts[(params[0], params[1], params[2])],)
            return None

        conn = FakeConnection(responder)
        store = GearEvidenceStore(lambda: conn)

        self.assertEqual(store.persist_fact(socket_one), socket_one)
        self.assertEqual(store.persist_fact(socket_zero), socket_zero)
        self.assertEqual(
            (
                socket_one["factKey"],
                socket_one["factValueHash"],
                socket_one["provenanceHash"],
            ),
            (
                duplicate_socket_one["factKey"],
                duplicate_socket_one["factValueHash"],
                duplicate_socket_one["provenanceHash"],
            ),
        )
        self.assertEqual(store.persist_fact(duplicate_socket_one), socket_one)

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn(
            "ON CONFLICT (fact_key, fact_value_hash, provenance_hash) DO NOTHING",
            sql,
        )
        self.assertEqual(socket_one["factKey"], socket_zero["factKey"])
        self.assertNotEqual(socket_one["factValueHash"], socket_zero["factValueHash"])
        fact_params = [
            params
            for statement, params in zip(
                conn.cursor_instance.statements,
                conn.cursor_instance.params,
            )
            if "INSERT INTO cache.websim_gear_canonical_facts" in statement
        ]
        self.assertEqual(
            {params[8] for params in fact_params},
            {socket_one["factValueHash"], socket_zero["factValueHash"]},
        )

    def test_invalidation_is_append_only_and_query_is_target_bounded(self):
        artifact = artifact_fixture()
        invalidation = {
            "schemaRevision": "gear-evidence-invalidation-v1",
            "invalidationId": "gear-invalidation:sha256:" + ("b" * 64),
            "artifactId": artifact["artifactId"],
            "observationId": "",
            "reasonCode": "source_retracted",
            "detail": {"sourceRevision": artifact["sourceRevision"]},
            "invalidatedAt": "2026-07-26T03:00:00+00:00",
        }

        def responder(sql, _params):
            if "INSERT INTO cache.websim_gear_evidence_invalidations" in sql:
                return (invalidation,)
            if "ORDER BY invalidated_at DESC" in sql:
                return [(invalidation,)]
            return None

        conn = FakeConnection(responder)
        store = GearEvidenceStore(lambda: conn)

        self.assertEqual(store.persist_invalidation(invalidation), invalidation)
        self.assertEqual(
            store.list_invalidations(artifact_id=artifact["artifactId"]),
            [invalidation],
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("WHERE artifact_id = %s", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertNotIn("UPDATE cache.websim_gear_evidence_invalidations", sql)
        self.assertNotIn("DELETE FROM cache.websim_gear_evidence_invalidations", sql)


class GearEvidenceGapStoreTest(unittest.TestCase):
    def test_gap_enqueue_is_idempotent_and_cannot_carry_fact_values(self):
        fact = fact_fixture(observation_fixture(artifact_fixture()))
        gap = gap_fixture(fact)
        insert_count = 0

        def responder(sql, _params):
            nonlocal insert_count
            if "INSERT INTO ops.websim_gear_evidence_gaps" in sql:
                insert_count += 1
                return (gap["gapKey"], "pending") if insert_count == 1 else None
            return None

        conn = FakeConnection(responder)
        result = GearEvidenceGapStore(lambda: conn).enqueue_gaps(
            [gap, gap],
            now="2026-07-26T02:00:00+00:00",
        )

        self.assertEqual(result, {"inserted": 1, "reused": 1})
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("ON CONFLICT (gap_key) DO NOTHING", sql)
        self.assertNotIn("result_json", sql)
        self.assertNotIn("fact_value", sql)

        forbidden = {**gap, "value": 1}
        with self.assertRaisesRegex(
            GearEvidenceGapIntegrityError,
            "operational fields",
        ):
            GearEvidenceGapStore(lambda: conn).enqueue_gaps(
                [forbidden],
                now="2026-07-26T02:00:00+00:00",
            )
        nested_fact_value = {
            **gap,
            "missingRequirement": {
                **gap["missingRequirement"],
                "factValue": 1,
            },
        }
        with self.assertRaisesRegex(
            GearEvidenceGapIntegrityError,
            "Fact values",
        ):
            GearEvidenceGapStore(lambda: conn).enqueue_gaps(
                [nested_fact_value],
                now="2026-07-26T02:00:00+00:00",
            )

    def test_gap_claim_and_finish_are_lock_token_fenced(self):
        fact = fact_fixture(observation_fixture(artifact_fixture()))
        gap = gap_fixture(fact)
        claim_conn = FakeConnection(
            lambda sql, _params: gap_row(
                gap,
                status="running",
                attempt=1,
                lock_token="lease-a",
            )
            if "FOR UPDATE SKIP LOCKED" in sql
            else None
        )

        claimed = GearEvidenceGapStore(lambda: claim_conn).claim_next(
            worker_id="worker-a",
            lock_token="lease-a",
            now="2026-07-26T02:00:00+00:00",
        )

        claim_sql = "\n".join(claim_conn.cursor_instance.statements)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["lockToken"], "lease-a")
        self.assertIn("FOR UPDATE SKIP LOCKED", claim_sql)
        self.assertIn("attempt = gap.attempt + 1", claim_sql)

        lost_conn = FakeConnection(lambda _sql, _params: None)
        with self.assertRaisesRegex(
            GearEvidenceGapIntegrityError,
            "lease was lost",
        ):
            GearEvidenceGapStore(lambda: lost_conn).finish(
                gap_key=gap["gapKey"],
                lock_token="wrong-lease",
                outcome={
                    "status": "retryable",
                    "problemCode": "source_unavailable",
                    "nextAttemptAt": "2026-07-26T02:05:00+00:00",
                },
                now="2026-07-26T02:01:00+00:00",
            )

        lost_sql = "\n".join(lost_conn.cursor_instance.statements)
        self.assertIn("lock_token = %s AND status = 'running'", lost_sql)
        self.assertNotIn("cache.websim_gear_canonical_facts", lost_sql)

        finish_conn = FakeConnection(
            lambda sql, _params: (gap["gapKey"], "terminal")
            if "UPDATE ops.websim_gear_evidence_gaps" in sql
            else None
        )
        finished = GearEvidenceGapStore(lambda: finish_conn).finish(
            gap_key=gap["gapKey"],
            lock_token="lease-a",
            outcome={
                "status": "terminal",
                "problemCode": "artifact_missing",
            },
            now="2026-07-26T02:01:00+00:00",
        )
        self.assertEqual(finished, {"gapKey": gap["gapKey"], "status": "terminal"})
        self.assertNotIn(
            "cache.websim_gear_canonical_facts",
            "\n".join(finish_conn.cursor_instance.statements),
        )

    def test_gap_health_is_bounded_and_does_not_read_requirements_or_fact_values(self):
        conn = FakeConnection(
            lambda sql, _params: (2, 1, 3, 4, "2026-07-26T01:00:00+00:00")
            if "count(*) FILTER" in sql
            else [("artifact_missing", 3), ("source_unavailable", 1)]
            if "GROUP BY problem_code" in sql
            else None
        )

        result = GearEvidenceGapStore(lambda: conn).health_summary(
            now="2026-07-26T02:00:00+00:00"
        )

        self.assertEqual(
            result["statusCounts"],
            {"pending": 2, "running": 1, "retryable": 3, "terminal": 4},
        )
        self.assertEqual(
            result["topProblemCodes"],
            [
                {"problemCode": "artifact_missing", "count": 3},
                {"problemCode": "source_unavailable", "count": 1},
            ],
        )
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("LIMIT 1000", sql)
        self.assertNotIn("missing_requirement_json", sql)
        self.assertNotIn("fact_value", sql)


if __name__ == "__main__":
    unittest.main()
