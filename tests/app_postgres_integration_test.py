import os
from pathlib import Path
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(
    sorted(
        path
        for path in (ROOT / "server" / "migrations" / "postgres").glob("[0-9][0-9][0-9][0-9]_*.sql")
        if path.name <= "0038_chickenbro_simc_platform_foundation.sql"
    )
)
DSN = os.environ.get("WOW_PG_TEST_DSN_V2", "").strip()


@unittest.skipUnless(DSN, "WOW_PG_TEST_DSN_V2 is not configured")
class AppPostgresIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - only reached with an invalid test setup
            raise unittest.SkipTest(f"psycopg is unavailable: {error}")

        cls.connection = psycopg.connect(DSN)
        cls.connection.autocommit = True
        with cls.connection.cursor() as cursor:
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "connection", None) is not None:
            cls.connection.close()

    def setUp(self):
        self.user_a = UUID("00000000-0000-0000-0000-0000000000a1")
        self.user_b = UUID("00000000-0000-0000-0000-0000000000b1")
        self.job_a = UUID("00000000-0000-4000-8000-0000000000a1")
        self.job_b = UUID("00000000-0000-4000-8000-0000000000b1")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO identity.users (id, display_name)
                VALUES (%s, 'v2-test-a'), (%s, 'v2-test-b')
                ON CONFLICT (id) DO NOTHING
                """,
                (self.user_a, self.user_b),
            )

    def test_owner_foreign_keys_and_claimable_queue_rows(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat.conversations (id, user_id, status)
                VALUES (%s, %s, 'active')
                """,
                (UUID("00000000-0000-4000-8000-0000000000c1"), self.user_a),
            )
            cursor.execute(
                """
                INSERT INTO ops.job_queue (id, domain, command_type, payload_json, status)
                VALUES
                    (%s, 'simc', 'snapshot.resolve', '{"owner":"a"}', 'queued'),
                    (%s, 'simc', 'snapshot.resolve', '{"owner":"b"}', 'queued')
                """,
                (self.job_a, self.job_b),
            )
            cursor.execute("SELECT COUNT(*) FROM chat.conversations WHERE user_id = %s", (self.user_a,))
            self.assertEqual(cursor.fetchone()[0], 1)

        with self.connection.cursor() as first_cursor, self.connection.cursor() as second_cursor:
            first_cursor.execute("BEGIN")
            second_cursor.execute("BEGIN")
            claim_sql = """
                WITH candidate AS (
                    SELECT id
                    FROM ops.job_queue
                    WHERE status = 'queued' AND available_at <= now()
                    ORDER BY available_at, created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE ops.job_queue AS jobs
                SET status = 'running', attempt = jobs.attempt + 1,
                    lease_owner = %s,
                    lease_expires_at = now() + make_interval(secs => %s),
                    heartbeat_at = now(), updated_at = now()
                FROM candidate
                WHERE jobs.id = candidate.id
                RETURNING jobs.id
            """
            first_cursor.execute(claim_sql, ("integration-a", 30))
            second_cursor.execute(claim_sql, ("integration-b", 30))
            first_claim = first_cursor.fetchone()[0]
            second_claim = second_cursor.fetchone()[0]
            first_cursor.execute("COMMIT")
            second_cursor.execute("COMMIT")

        self.assertNotEqual(first_claim, second_claim)

    def test_expired_lease_can_be_reclaimed(self):
        expired_job = UUID("00000000-0000-4000-8000-0000000000e1")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ops.job_queue (
                    id, domain, command_type, status, attempt,
                    lease_owner, lease_expires_at
                )
                VALUES (%s, 'simc', 'snapshot.resolve', 'running', 1, 'old-worker', now() - interval '1 minute')
                ON CONFLICT (id) DO UPDATE SET
                    status = 'running', attempt = 1,
                    lease_owner = 'old-worker', lease_expires_at = now() - interval '1 minute'
                """,
                (expired_job,),
            )
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT id
                    FROM ops.job_queue
                    WHERE status = 'running' AND lease_expires_at < now()
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE ops.job_queue AS jobs
                SET status = 'running', attempt = jobs.attempt + 1,
                    lease_owner = 'new-worker',
                    lease_expires_at = now() + make_interval(secs => 30),
                    heartbeat_at = now(), updated_at = now()
                FROM candidate
                WHERE jobs.id = candidate.id
                RETURNING jobs.lease_owner, jobs.attempt
                """
            )
            self.assertEqual(cursor.fetchone(), ("new-worker", 2))

    def test_simulation_results_are_immutable(self):
        job_id = UUID("00000000-0000-4000-8000-0000000000f1")
        result_id = UUID("00000000-0000-4000-8000-0000000000f2")
        snapshot_id = UUID("00000000-0000-4000-8000-0000000000f3")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO simc.source_snapshots (
                    id, user_id, provider, source_url, source_key, revision,
                    readiness, snapshot_json, provenance_json, raw_sha256
                )
                VALUES (%s, %s, 'raiderio', 'https://raider.io/characters/cn/test/hero', 'cn/test/hero', 1,
                        'READY_FOR_SIMC', '{}', '{}', repeat('a', 64))
                ON CONFLICT (id) DO NOTHING
                """,
                (snapshot_id, self.user_a),
            )
            cursor.execute(
                """
                INSERT INTO simc.simulation_jobs (
                    id, user_id, snapshot_id, scenario_hash, compiler_revision,
                    runtime_revision, idempotency_key, status
                )
                VALUES (%s, %s, %s, 'scenario', 'compiler', 'runtime', 'integration-result', 'succeeded')
                ON CONFLICT (id) DO NOTHING
                """,
                (job_id, self.user_a, snapshot_id),
            )
            cursor.execute(
                """
                INSERT INTO simc.simulation_results (
                    id, job_id, user_id, profile_sha256, result_json,
                    primary_metric_name, primary_metric_value,
                    compiler_revision, runtime_revision
                )
                VALUES (%s, %s, %s, repeat('b', 64), '{}', 'dps', 1.0, 'compiler', 'runtime')
                ON CONFLICT (id) DO NOTHING
                """,
                (result_id, job_id, self.user_a),
            )
            with self.assertRaises(Exception):
                cursor.execute("UPDATE simc.simulation_results SET primary_metric_value = 2.0 WHERE id = %s", (result_id,))
            self.connection.rollback()
            with self.assertRaises(Exception):
                cursor.execute("DELETE FROM simc.simulation_results WHERE id = %s", (result_id,))
            self.connection.rollback()
