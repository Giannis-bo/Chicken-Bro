import unittest
from uuid import UUID

from server.app.worker.leases import LostLeaseError, PostgresJobQueue


JOB_ID = UUID("00000000-0000-4000-8000-000000000010")


class RecordingCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = connection.rowcount

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.connection.statements.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return self.connection.rows.pop(0) if self.connection.rows else None


class RecordingConnection:
    def __init__(self, *, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, **_):
        return RecordingCursor(self)

    @property
    def normalized_sql(self):
        return "\n".join(sql for sql, _ in self.statements)


class AppWorkerLeaseTest(unittest.TestCase):
    def test_claim_uses_skip_locked_and_returns_typed_envelope(self):
        connection = RecordingConnection(rows=[{
            "id": UUID("00000000-0000-0000-0000-000000000010"),
            "domain": "simc",
            "command_type": "snapshot.resolve",
            "aggregate_id": None,
            "payload_json": {"snapshotId": "s1"},
            "attempt": 1,
            "max_attempts": 3,
        }])
        queue = PostgresJobQueue(lambda: connection)
        lease = queue.claim(worker_id="worker-a", lease_seconds=30)
        self.assertEqual(lease.command_type, "snapshot.resolve")
        self.assertIn("FOR UPDATE SKIP LOCKED", connection.normalized_sql)

    def test_terminal_update_requires_the_current_lease_owner(self):
        connection = RecordingConnection(rowcount=0)
        queue = PostgresJobQueue(lambda: connection)
        with self.assertRaisesRegex(LostLeaseError, "lease"):
            queue.succeed(JOB_ID, worker_id="wrong-worker")
        self.assertIn("status = 'succeeded'", connection.normalized_sql)
        self.assertIn("status = 'running'", connection.normalized_sql)
        self.assertIn("lease_owner = %s", connection.normalized_sql)

    def test_retryable_failure_is_bound_to_the_lease_owner(self):
        connection = RecordingConnection(rowcount=1)
        queue = PostgresJobQueue(lambda: connection)
        queue.fail(JOB_ID, worker_id="worker-a", error_code="TEMPORARY_UPSTREAM", retryable=True)
        sql = connection.normalized_sql
        self.assertIn("attempt < max_attempts", sql)
        self.assertIn("status = 'running'", sql)
        self.assertNotIn("cancel_requested", sql)

    def test_queue_exposes_no_queue_only_cancellation_mutation(self):
        self.assertFalse(hasattr(PostgresJobQueue, "request_cancel"))
