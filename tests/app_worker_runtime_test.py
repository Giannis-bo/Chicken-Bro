import unittest
from threading import Event
from uuid import UUID

from server.app.worker.handlers import HandlerRegistry, UnknownJobHandler
from server.app.worker.leases import JobLease, LostLeaseError
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
        self.heartbeats = []

    def claim(self, *, worker_id, lease_seconds):
        return self.claimed

    def succeed(self, job_id, *, worker_id):
        self.succeeded.append((job_id, worker_id))

    def fail(self, job_id, *, worker_id, error_code, retryable):
        self.failed.append((job_id, worker_id, error_code, retryable))

    def heartbeat(self, job_id, *, worker_id, lease_seconds):
        self.heartbeats.append((job_id, worker_id, lease_seconds))


class AppWorkerRuntimeTest(unittest.TestCase):
    def test_idle_once_returns_false_without_sleeping(self):
        service_heartbeats = []
        worker = Worker(
            queue=FakeQueue(claimed=None),
            handlers=HandlerRegistry(),
            worker_id="worker-a",
            service_heartbeat=lambda: service_heartbeats.append("alive"),
        )
        self.assertFalse(worker.run_once())
        self.assertEqual(service_heartbeats, ["alive"])

    def test_queue_access_failure_does_not_publish_a_fresh_service_heartbeat(self):
        class FailingQueue(FakeQueue):
            def claim(self, *, worker_id, lease_seconds):
                raise RuntimeError("queue unavailable")

        service_heartbeats = []
        worker = Worker(
            queue=FailingQueue(claimed=None),
            handlers=HandlerRegistry(),
            worker_id="worker-a",
            service_heartbeat=lambda: service_heartbeats.append("alive"),
        )

        with self.assertRaisesRegex(RuntimeError, "queue unavailable"):
            worker.run_once()
        self.assertEqual(service_heartbeats, [])

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

    def test_long_handler_renews_its_lease_until_domain_commit_finishes(self):
        release = Event()
        registry = HandlerRegistry()
        registry.register("simc", "snapshot.resolve", lambda _lease: release.wait(1))
        queue = FakeQueue(claimed=LEASE)
        original_heartbeat = queue.heartbeat

        def heartbeat(*args, **kwargs):
            original_heartbeat(*args, **kwargs)
            release.set()

        queue.heartbeat = heartbeat
        service_heartbeats = []
        worker = Worker(
            queue=queue,
            handlers=registry,
            worker_id="worker-a",
            heartbeat_interval_seconds=0.01,
            service_heartbeat=lambda: service_heartbeats.append("alive"),
        )

        self.assertTrue(worker.run_once())

        self.assertEqual(queue.heartbeats, [(LEASE.id, "worker-a", 30)])
        self.assertEqual(queue.succeeded, [(LEASE.id, "worker-a")])
        self.assertEqual(service_heartbeats, ["alive", "alive"])

    def test_lost_heartbeat_never_acknowledges_the_stale_lease(self):
        release = Event()
        registry = HandlerRegistry()
        registry.register("simc", "snapshot.resolve", lambda _lease: release.wait(1))
        queue = FakeQueue(claimed=LEASE)

        def lose_lease(*_args, **_kwargs):
            release.set()
            raise LostLeaseError("lease lost")

        queue.heartbeat = lose_lease
        worker = Worker(
            queue=queue,
            handlers=registry,
            worker_id="worker-a",
            heartbeat_interval_seconds=0.01,
        )

        self.assertTrue(worker.run_once())

        self.assertEqual(queue.succeeded, [])
        self.assertEqual(queue.failed, [])
