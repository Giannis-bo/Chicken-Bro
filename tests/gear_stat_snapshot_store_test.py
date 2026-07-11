import unittest

from server.gear_stat_snapshot import verified_snapshot_record
from server.gear_stat_snapshot_store import GearStatSnapshotIntegrityError, GearStatSnapshotStore


class FakeCursor:
    def __init__(self, responder):
        self.responder = responder
        self.statements = []
        self.params = []
        self.current = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        self.params.append(params)
        result = self.responder(normalized, params)
        self.current = result
        self.rowcount = 0 if result is None else 1

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
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


SIGNATURE = "stat-snapshot:sha256:" + "a" * 64
JOB_ROW = (
    7,
    SIGNATURE,
    "queued",
    {"selectionIntent": {"schemaRevision": "selection-intent-v1"}},
    {"manifestRevision": "season-manifest:a"},
    "sha256:client",
    0,
    "",
    "",
    None,
    "2026-07-11T12:00:00+00:00",
    None,
    None,
    None,
    {},
)


class GearStatSnapshotStoreTest(unittest.TestCase):
    def test_get_or_start_miss_inserts_one_job_after_bounded_limits(self):
        def responder(sql, _params):
            if "FROM cache.websim_gear_stat_snapshots" in sql:
                return None
            if "FROM ops.websim_gear_stat_jobs" in sql and "status IN ('queued', 'running')" in sql:
                return None
            if "count(*)" in sql:
                return (0,)
            if "INSERT INTO ops.websim_gear_stat_jobs" in sql:
                return JOB_ROW
            return None

        conn = FakeConnection(responder)
        result = GearStatSnapshotStore(lambda: conn).get_or_start(
            SIGNATURE,
            request_payload={"selectionIntent": {"schemaRevision": "selection-intent-v1"}},
            release_context={"manifestRevision": "season-manifest:a"},
            client_key_hash="sha256:client",
            now="2026-07-11T12:00:00+00:00",
            global_limit=100,
            per_client_limit=2,
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["job"]["jobId"], 7)
        self.assertIn("INSERT INTO ops.websim_gear_stat_jobs", sql)
        self.assertIn("client_key_hash", sql)
        self.assertTrue(conn.committed)

    def test_get_or_start_returns_verified_snapshot_without_new_job(self):
        snapshot_row = (
            SIGNATURE,
            "stat-signature-v1",
            "sha256:gear",
            "season-manifest:a",
            "gear-release:a",
            "simc-v1",
            {"simcRuntimeRevision": "simc-v1"},
            "sha256:profile",
            "sha256:snapshot",
            {"statStatus": "verified", "secondary": []},
            "2026-07-11T12:00:00+00:00",
        )
        conn = FakeConnection(lambda sql, _params: snapshot_row if "FROM cache.websim_gear_stat_snapshots" in sql else None)
        result = GearStatSnapshotStore(lambda: conn).get_or_start(
            SIGNATURE,
            request_payload={},
            release_context={},
            client_key_hash="sha256:client",
            now="2026-07-11T12:00:00+00:00",
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["snapshot"]["statSignature"], SIGNATURE)
        self.assertNotIn("INSERT INTO ops.websim_gear_stat_jobs", "\n".join(conn.cursor_instance.statements))

    def test_get_or_start_reuses_deterministic_blocker_and_active_cooldown(self):
        cases = [
            (("blocked", {"code": "GEAR_STAT_PROFILE_BLOCKED"}, None, False), "blocked"),
            (("failed", {"code": "GEAR_STAT_TIMEOUT"}, "2026-07-11T12:01:00+00:00", True), "unavailable"),
        ]
        for terminal_row, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                def responder(sql, _params):
                    if "FROM cache.websim_gear_stat_snapshots" in sql:
                        return None
                    if "status IN ('queued', 'running')" in sql and "FROM ops.websim_gear_stat_jobs" in sql:
                        return None
                    if "status IN ('blocked', 'failed')" in sql:
                        return terminal_row
                    return None

                conn = FakeConnection(responder)
                result = GearStatSnapshotStore(lambda: conn).get_or_start(
                    SIGNATURE,
                    request_payload={},
                    release_context={},
                    client_key_hash="sha256:client",
                    now="2026-07-11T12:00:00+00:00",
                )
                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["problem"]["code"], terminal_row[1]["code"])
                self.assertNotIn("INSERT INTO ops.websim_gear_stat_jobs", "\n".join(conn.cursor_instance.statements))

    def test_get_or_start_enforces_global_limit_before_insert(self):
        def responder(sql, _params):
            if "FROM cache.websim_gear_stat_snapshots" in sql:
                return None
            if "status IN ('queued', 'running')" in sql and "FROM ops.websim_gear_stat_jobs" in sql and "count(*)" not in sql:
                return None
            if "status IN ('blocked', 'failed')" in sql:
                return None
            if "count(*)" in sql:
                return (1,)
            return None

        conn = FakeConnection(responder)
        with self.assertRaisesRegex(Exception, "saturated"):
            GearStatSnapshotStore(lambda: conn).get_or_start(
                SIGNATURE,
                request_payload={},
                release_context={},
                client_key_hash="sha256:client",
                now="2026-07-11T12:00:00+00:00",
                global_limit=1,
            )
        self.assertNotIn("INSERT INTO ops.websim_gear_stat_jobs", "\n".join(conn.cursor_instance.statements))

    def test_claim_reclaims_expired_jobs_and_uses_skip_locked_fenced_token(self):
        running_row = list(JOB_ROW)
        running_row[2] = "running"
        running_row[6] = 1
        running_row[7] = "worker-a"
        running_row[8] = "token-a"
        conn = FakeConnection(lambda sql, _params: tuple(running_row) if "RETURNING" in sql else None)
        result = GearStatSnapshotStore(lambda: conn).claim_next(
            worker_id="worker-a",
            lock_token="token-a",
            now="2026-07-11T12:00:00+00:00",
            lease_seconds=30,
        )
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["status"], "running")
        self.assertIn("lease_until <", sql)
        self.assertIn("attempt >= 20", sql)
        self.assertIn("attempt < 20", sql)
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertIn("lock_token", sql)
        self.assertIn("RETURNING job.job_id", sql)

    def test_publish_verifies_fence_before_immutable_snapshot_insert(self):
        record = verified_snapshot_record(
            {
                "statSignature": SIGNATURE,
                "schemaRevision": "stat-signature-v1",
                "resolvedGearSignature": "sha256:gear",
                "manifestRevision": "season-manifest:a",
                "gearReleaseId": "gear-release:a",
                "simcRuntimeRevision": "simc-v1",
                "dependencyVector": {"simcRuntimeRevision": "simc-v1"},
                "profileHash": "sha256:" + "b" * 64,
            },
            {"statStatus": "verified", "secondary": []},
            verified_at="2026-07-11T12:00:00+00:00",
        )

        def responder(sql, _params):
            if "FOR UPDATE" in sql and "ops.websim_gear_stat_jobs" in sql:
                return (SIGNATURE,)
            if "INSERT INTO cache.websim_gear_stat_snapshots" in sql:
                return (record["snapshotHash"],)
            if "UPDATE ops.websim_gear_stat_jobs" in sql:
                return (7,)
            return None

        conn = FakeConnection(responder)
        result = GearStatSnapshotStore(lambda: conn).publish_verified(
            job_id=7,
            lock_token="token-a",
            record=record,
            now="2026-07-11T12:00:00+00:00",
        )
        statements = conn.cursor_instance.statements
        fence_index = next(i for i, sql in enumerate(statements) if "FOR UPDATE" in sql)
        insert_index = next(i for i, sql in enumerate(statements) if "INSERT INTO cache.websim_gear_stat_snapshots" in sql)
        self.assertLess(fence_index, insert_index)
        self.assertEqual(result["status"], "verified")

    def test_publish_rejects_tampered_snapshot_hash_before_sql(self):
        record = verified_snapshot_record(
            {
                "statSignature": SIGNATURE,
                "schemaRevision": "stat-signature-v1",
                "resolvedGearSignature": "sha256:gear",
                "manifestRevision": "season-manifest:a",
                "gearReleaseId": "gear-release:a",
                "simcRuntimeRevision": "simc-v1",
                "dependencyVector": {"simcRuntimeRevision": "simc-v1"},
                "profileHash": "sha256:" + "b" * 64,
            },
            {"statStatus": "verified", "secondary": []},
            verified_at="2026-07-11T12:00:00+00:00",
        )
        record["snapshot"]["secondary"].append({"key": "crit", "value": "999"})
        conn = FakeConnection(lambda _sql, _params: None)
        with self.assertRaisesRegex(GearStatSnapshotIntegrityError, "content hash"):
            GearStatSnapshotStore(lambda: conn).publish_verified(
                job_id=7,
                lock_token="token-a",
                record=record,
                now="2026-07-11T12:00:00+00:00",
            )
        self.assertEqual(conn.cursor_instance.statements, [])

    def test_publish_rejects_stale_lock_before_snapshot_insert(self):
        record = verified_snapshot_record(
            {
                "statSignature": SIGNATURE,
                "schemaRevision": "stat-signature-v1",
                "resolvedGearSignature": "sha256:gear",
                "manifestRevision": "season-manifest:a",
                "gearReleaseId": "gear-release:a",
                "simcRuntimeRevision": "simc-v1",
                "dependencyVector": {"simcRuntimeRevision": "simc-v1"},
                "profileHash": "sha256:" + "b" * 64,
            },
            {"statStatus": "verified", "secondary": []},
            verified_at="2026-07-11T12:00:00+00:00",
        )
        conn = FakeConnection(lambda _sql, _params: None)
        with self.assertRaises(GearStatSnapshotIntegrityError):
            GearStatSnapshotStore(lambda: conn).publish_verified(
                job_id=7,
                lock_token="stale-token",
                record=record,
                now="2026-07-11T12:00:00+00:00",
            )
        self.assertNotIn("INSERT INTO cache.websim_gear_stat_snapshots", "\n".join(conn.cursor_instance.statements))
        self.assertTrue(conn.rolled_back)

    def test_health_summary_uses_bounded_history_and_caps_snapshot_count(self):
        def responder(sql, _params):
            if "WITH active_jobs AS" in sql:
                return (1, 0, 3, 4, "2026-07-11T12:00:00+00:00")
            if "LIMIT 10001" in sql:
                return (10001,)
            if "FROM ops.websim_gear_stat_worker_state" in sql:
                return []
            if "FROM ops.websim_gear_stat_metrics" in sql:
                return (10, 4, 6, 2, "2026-07-11T12:00:00+00:00")
            return None

        conn = FakeConnection(responder)
        health = GearStatSnapshotStore(lambda: conn).health_summary(now="2026-07-11T12:00:00+00:00")
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(health["queue"]["queued"], 1)
        self.assertEqual(health["snapshotCount"], 10000)
        self.assertTrue(health["snapshotCountTruncated"])
        self.assertEqual(health["metrics"]["cacheHitRate"], 0.4)
        self.assertIn("LIMIT 1000", sql)
        self.assertIn("LIMIT 10001", sql)


if __name__ == "__main__":
    unittest.main()
