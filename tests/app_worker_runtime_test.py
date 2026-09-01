import unittest
from uuid import UUID

from server.app.worker.handlers import HandlerRegistry, UnknownJobHandler
from server.app.worker.leases import JobLease
from server.app.worker.main import Worker


LEASE = JobLease(
    id=UUID("00000000-0000-4000-8000-000000000020"),
    domain="simc",
    command_type="snapshot.resolve",
    aggregate_id=None,
    payload={"snapshotId": "s1"},
    attempt=1,
    max_attempts=3,
)


class FakeQueue:
    def __init__(self, *, claimed):
        self.claimed = claimed
        self.succeeded = []
        self.failed = []

    def claim(self, *, worker_id, lease_seconds):
        return self.claimed

    def succeed(self, job_id, *, worker_id):
        self.succeeded.append((job_id, worker_id))

    def fail(self, job_id, *, worker_id, error_code, retryable):
        self.failed.append((job_id, worker_id, error_code, retryable))


class AppWorkerRuntimeTest(unittest.TestCase):
    def test_idle_once_returns_false_without_sleeping(self):
        worker = Worker(queue=FakeQueue(claimed=None), handlers=HandlerRegistry(), worker_id="worker-a")
        self.assertFalse(worker.run_once())

    def test_registered_handler_marks_the_lease_succeeded(self):
        calls = []
        registry = HandlerRegistry()
        registry.register("simc", "snapshot.resolve", lambda lease: calls.append(lease.id))
        queue = FakeQueue(claimed=LEASE)
        self.assertTrue(Worker(queue=queue, handlers=registry, worker_id="worker-a").run_once())
        self.assertEqual(calls, [LEASE.id])
        self.assertEqual(queue.succeeded, [(LEASE.id, "worker-a")])

    def test_unknown_handler_is_terminal_and_not_retried(self):
        queue = FakeQueue(claimed=LEASE)
        Worker(queue=queue, handlers=HandlerRegistry(), worker_id="worker-a").run_once()
        self.assertEqual(queue.failed, [(LEASE.id, "worker-a", "UNKNOWN_JOB_HANDLER", False)])

    def test_handler_registry_rejects_duplicate_and_reports_unknown_keys(self):
        registry = HandlerRegistry()
        registry.register("simc", "snapshot.resolve", lambda lease: None)
        with self.assertRaisesRegex(ValueError, "duplicate job handler"):
            registry.register("simc", "snapshot.resolve", lambda lease: None)
        with self.assertRaises(UnknownJobHandler):
            registry.resolve("chat", "conversation.run")
