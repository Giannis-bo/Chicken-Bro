import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from server.app.identity.domain import Principal
from server.app.simulation.application import SimulationApplication, SimulationApplicationError
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.domain import (
    SimulationJob,
    SimulationJobStatus,
    SourceProvider,
    SourceReadiness,
    SourceSnapshot,
)
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.sources import CharacterSourceRouter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def fetch_json(self, url, *, headers=None):
        return json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())


class MemorySimulationRepository:
    def __init__(self):
        self.snapshots = {}
        self.jobs = {}
        self.results = {}
        self.attempts = {}
        self.list_job_calls = []
        self.queue = None
        self.atomic_snapshot_writes = []
        self.atomic_submission_calls = []
        self.atomic_submission_result = None

    def next_snapshot_revision(self, user_id, provider, source_key):
        revisions = [
            snapshot.revision
            for (owner, _), snapshot in self.snapshots.items()
            if owner == user_id and snapshot.provider == provider and snapshot.source_key == source_key
        ]
        return max(revisions, default=0) + 1

    def save_snapshot(self, snapshot):
        self.snapshots[(snapshot.user_id, snapshot.id)] = snapshot

    def save_snapshot_with_next_revision(self, snapshot):
        self.atomic_snapshot_writes.append(snapshot)
        revision = self.next_snapshot_revision(
            snapshot.user_id,
            snapshot.provider,
            snapshot.source_key,
        )
        persisted = SourceSnapshot(**{**snapshot.__dict__, "revision": revision})
        self.snapshots[(persisted.user_id, persisted.id)] = persisted
        return persisted

    def get_snapshot(self, user_id, snapshot_id):
        return self.snapshots.get((user_id, snapshot_id))

    def get_job_by_idempotency(self, user_id, idempotency_key):
        return next(
            (job for (owner, _), job in self.jobs.items() if owner == user_id and job.idempotency_key == idempotency_key),
            None,
        )

    def save_job(self, job):
        self.jobs[(job.user_id, job.id)] = job

    def create_job_and_enqueue(self, job, *, payload, max_attempts=3):
        self.atomic_submission_calls.append((job, payload, max_attempts))
        if self.atomic_submission_result is not None:
            return self.atomic_submission_result
        if self.queue is None:
            raise RuntimeError("test queue is not configured")
        self.jobs[(job.user_id, job.id)] = job
        self.queue.enqueue(
            job_id=job.id,
            domain="simc",
            command_type="run_simulation",
            aggregate_id=job.id,
            payload=payload,
            max_attempts=max_attempts,
        )
        return job

    def get_job(self, user_id, job_id):
        return self.jobs.get((user_id, job_id))

    def list_jobs(self, user_id, boundary, limit):
        self.list_job_calls.append((user_id, boundary, limit))
        rows = [job for (owner, _), job in self.jobs.items() if owner == user_id]
        rows.sort(key=lambda job: (job.updated_at, job.id), reverse=True)
        if boundary is not None:
            rows = [job for job in rows if (job.updated_at, job.id) < boundary]
        return rows[:limit]

    def save_result(self, result):
        self.results[(result.user_id, result.job_id)] = result

    def get_result(self, user_id, job_id):
        return self.results.get((user_id, job_id))

    def list_attempts(self, job_id, limit=20):
        return list(self.attempts.get(job_id, ()))[:limit]


class MemoryQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)


class SimulationApplicationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        self.owner = Principal(
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            session_kind="mini_bearer",
        )
        self.other = Principal(
            user_id=UUID("00000000-0000-4000-8000-000000000003"),
            session_kind="web_cookie",
        )
        capabilities = SimcRuntimeCapabilities(
            runtime_revision="simc:current:abc",
            compiler_revision="chickenbro-simc-compiler-v1",
            supported_specs=frozenset({("shaman", "elemental")}),
        )
        gateway = FakeGateway()
        router = CharacterSourceRouter(gateway)
        self.repository = MemorySimulationRepository()
        self.queue = MemoryQueue()
        self.repository.queue = self.queue
        self.application = SimulationApplication(
            repository=self.repository,
            source_router=router,
            readiness_validator=SimcReadinessValidator(),
            compiler=SimcProfileCompiler(capabilities=capabilities),
            runtime_capabilities=capabilities,
            clock=lambda: self.now,
        )

    def test_ready_source_can_submit_by_reference_and_is_idempotent(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        self.assertEqual(snapshot.readiness, SourceReadiness.READY_FOR_SIMC)
        self.assertEqual(snapshot.revision, 1)
        self.assertEqual(len(self.repository.atomic_snapshot_writes), 1)

        first = self.application.submit(
            self.owner,
            snapshot.id,
            {"fightStyle": "Patchwerk", "desiredTargets": 1},
            "sim-request-1",
        )
        second = self.application.submit(
            self.owner,
            snapshot.id,
            {"fightStyle": "Patchwerk", "desiredTargets": 1},
            "sim-request-1",
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.status, SimulationJobStatus.QUEUED)
        self.assertEqual(len(self.repository.atomic_submission_calls), 1)
        self.assertEqual(len(self.queue.calls), 1)
        self.assertNotIn("profile", self.queue.calls[0]["payload"])
        self.assertEqual(self.queue.calls[0]["payload"]["snapshotId"], str(snapshot.id))

    def test_other_owner_cannot_read_or_submit_snapshot(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )

        with self.assertRaisesRegex(SimulationApplicationError, "SNAPSHOT_NOT_FOUND"):
            self.application.submit(self.other, snapshot.id, {"fightStyle": "Patchwerk"}, "sim-request-2")

    def test_idempotency_key_contract_matches_the_typed_clients(self):
        snapshot_id = UUID("00000000-0000-4000-8000-000000000099")

        for invalid_key in ("short", " leading-space", "contains space", "bad/control\n", "k" * 129):
            with self.subTest(invalid_key=invalid_key):
                with self.assertRaisesRegex(SimulationApplicationError, "IDEMPOTENCY_KEY_INVALID"):
                    self.application.submit(
                        self.owner,
                        snapshot_id,
                        {"fightStyle": "Patchwerk"},
                        invalid_key,
                    )

        with self.assertRaisesRegex(SimulationApplicationError, "IDEMPOTENCY_KEY_REQUIRED"):
            self.application.submit(
                self.owner,
                snapshot_id,
                {"fightStyle": "Patchwerk"},
                "",
            )

    def test_same_idempotency_key_rejects_changed_scenario(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        self.application.submit(
            self.owner,
            snapshot.id,
            {"fightStyle": "Patchwerk", "desiredTargets": 1},
            "sim-conflict-scenario",
        )

        with self.assertRaisesRegex(SimulationApplicationError, "IDEMPOTENCY_CONFLICT"):
            self.application.submit(
                self.owner,
                snapshot.id,
                {"fightStyle": "Patchwerk", "desiredTargets": 2},
                "sim-conflict-scenario",
            )

        self.assertEqual(len(self.queue.calls), 1)

    def test_same_idempotency_key_rejects_changed_snapshot(self):
        first_snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        second_snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        self.assertEqual((first_snapshot.revision, second_snapshot.revision), (1, 2))
        self.application.submit(
            self.owner,
            first_snapshot.id,
            {"fightStyle": "Patchwerk"},
            "sim-conflict-snapshot",
        )

        with self.assertRaisesRegex(SimulationApplicationError, "IDEMPOTENCY_CONFLICT"):
            self.application.submit(
                self.owner,
                second_snapshot.id,
                {"fightStyle": "Patchwerk"},
                "sim-conflict-snapshot",
            )

        self.assertEqual(len(self.queue.calls), 1)

    def test_concurrent_idempotency_conflict_is_rechecked_after_atomic_insert(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        raced = SimulationJob(
            id=UUID("00000000-0000-4000-8000-000000000077"),
            user_id=self.owner.user_id,
            snapshot_id=snapshot.id,
            scenario_hash="f" * 64,
            compiler_revision="compiler:other",
            runtime_revision="simc:other",
            idempotency_key="sim-race-conflict",
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=self.now,
            updated_at=self.now,
        )
        self.repository.atomic_submission_result = raced

        with self.assertRaisesRegex(SimulationApplicationError, "IDEMPOTENCY_CONFLICT"):
            self.application.submit(
                self.owner,
                snapshot.id,
                {"fightStyle": "Patchwerk", "desiredTargets": 1},
                "sim-race-conflict",
            )

        self.assertEqual(len(self.repository.atomic_submission_calls), 1)
        self.assertEqual(self.queue.calls, [])

    def test_incomplete_snapshot_is_saved_for_explanation_but_cannot_enter_queue(self):
        router = CharacterSourceRouter(FakeGateway())
        incomplete_application = SimulationApplication(
            repository=self.repository,
            source_router=router,
            readiness_validator=SimcReadinessValidator(),
            compiler=self.application._compiler,
            runtime_capabilities=self.application._runtime_capabilities,
            clock=lambda: self.now,
        )
        # A valid source candidate is made incomplete by removing one required semantic field.
        original = FakeGateway.fetch_json
        FakeGateway.fetch_json = lambda _self, _url, headers=None: {
            **json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text()),
            "gear": {"items": {}},
        }
        try:
            snapshot = incomplete_application.resolve_source(
                self.owner,
                "https://raider.io/characters/us/area-52/Stormsample",
            )
        finally:
            FakeGateway.fetch_json = original
        self.assertEqual(snapshot.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        with self.assertRaisesRegex(SimulationApplicationError, "SNAPSHOT_NOT_READY"):
            incomplete_application.submit(
                self.owner,
                snapshot.id,
                {"fightStyle": "Patchwerk"},
                "sim-request-3",
            )
        self.assertEqual(self.queue.calls, [])

    def test_same_owner_job_history_is_stable_across_pages(self):
        jobs = []
        for index in range(4):
            job = SimulationJob(
                id=UUID(f"00000000-0000-4000-8000-{index + 1:012d}"),
                user_id=self.owner.user_id,
                snapshot_id=UUID("00000000-0000-4000-8000-000000000099"),
                scenario_hash=f"{index + 1:064x}",
                compiler_revision="compiler:test",
                runtime_revision="simc:test",
                idempotency_key=f"history-{index}",
                status=SimulationJobStatus.QUEUED,
                public_error_code="",
                created_at=self.now + timedelta(minutes=index),
                updated_at=self.now + timedelta(minutes=index),
            )
            self.repository.jobs[(job.user_id, job.id)] = job
            jobs.append(job)
        hidden = SimulationJob(
            **{
                **jobs[0].__dict__,
                "id": UUID("00000000-0000-4000-8000-000000000098"),
                "user_id": self.other.user_id,
                "updated_at": self.now + timedelta(hours=1),
            }
        )
        self.repository.jobs[(hidden.user_id, hidden.id)] = hidden

        first = self.application.list_jobs(self.owner, cursor=None, limit=2)
        second = self.application.list_jobs(self.owner, cursor=first.next_cursor, limit=2)

        self.assertEqual(
            [view.job.id for view in first.items + second.items],
            [job.id for job in reversed(jobs)],
        )
        self.assertIsNotNone(first.next_cursor)
        self.assertIsNone(second.next_cursor)
        self.assertTrue(all(view.job.user_id == self.owner.user_id for view in first.items + second.items))

    def test_invalid_job_cursor_fails_before_repository_query(self):
        with self.assertRaisesRegex(SimulationApplicationError, "INVALID_CURSOR"):
            self.application.list_jobs(self.owner, cursor="not-a-cursor", limit=20)

        self.assertEqual(self.repository.list_job_calls, [])


class RecordingCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters):
        self.executed.append((" ".join(statement.split()), parameters))

    def fetchall(self):
        return list(self.rows)


class RecordingConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_value


class AtomicSubmissionCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters):
        self.executed.append((" ".join(statement.split()), parameters))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class AtomicSubmissionConnection(RecordingConnection):
    pass


class SimulationRepositoryOwnerTest(unittest.TestCase):
    def test_snapshot_revision_and_insert_share_one_user_locked_transaction(self):
        owner_id = UUID("00000000-0000-4000-8000-0000000000d1")
        now = datetime(2026, 9, 3, tzinfo=timezone.utc)
        snapshot = SourceSnapshot(
            id=UUID("00000000-0000-4000-8000-0000000000d2"),
            user_id=owner_id,
            provider=SourceProvider.RAIDERIO,
            source_url="https://raider.io/characters/us/area-52/test",
            source_key="raiderio:us:area-52:test",
            revision=1,
            readiness=SourceReadiness.READY_FOR_SIMC,
            snapshot={"character": {"name": "Test"}},
            provenance={"sourceRevision": "fixture"},
            raw_sha256="d" * 64,
            fetched_at=now,
        )
        cursor = AtomicSubmissionCursor([(owner_id,), (5,)])
        connection = AtomicSubmissionConnection(cursor)
        connection_count = 0

        def connection_factory():
            nonlocal connection_count
            connection_count += 1
            return connection

        repository = PostgresSimulationRepository(connection_factory)

        persisted = repository.save_snapshot_with_next_revision(snapshot)

        statements = [statement for statement, _ in cursor.executed]
        self.assertEqual(connection_count, 1)
        self.assertEqual(persisted.revision, 5)
        self.assertIn("FROM identity.users", statements[0])
        self.assertIn("FOR UPDATE", statements[0])
        self.assertIn("MAX(revision)", statements[1])
        self.assertIn("INSERT INTO simc.source_snapshots", statements[2])

    def test_postgres_job_history_uses_owner_scoped_keyset_query(self):
        owner_id = UUID("00000000-0000-4000-8000-0000000000a1")
        job_id = UUID("00000000-0000-4000-8000-0000000000a2")
        snapshot_id = UUID("00000000-0000-4000-8000-0000000000a3")
        now = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
        cursor = RecordingCursor([(
            job_id,
            owner_id,
            snapshot_id,
            "a" * 64,
            "compiler:test",
            "simc:test",
            "history-request",
            "queued",
            "",
            now,
            now,
        )])
        repository = PostgresSimulationRepository(lambda: RecordingConnection(cursor))

        rows = repository.list_jobs(owner_id, (now, job_id), 21)

        self.assertEqual([job.id for job in rows], [job_id])
        statement, parameters = cursor.executed[0]
        self.assertIn("WHERE user_id = %s", statement)
        self.assertIn("(updated_at, id) < (%s, %s)", statement)
        self.assertIn("ORDER BY updated_at DESC, id DESC LIMIT %s", statement)
        self.assertEqual(parameters, (owner_id, now, job_id, 21))

    def test_job_and_queue_are_inserted_on_one_connection_transaction(self):
        owner_id = UUID("00000000-0000-4000-8000-0000000000b1")
        now = datetime(2026, 9, 3, tzinfo=timezone.utc)
        job = SimulationJob(
            id=UUID("00000000-0000-4000-8000-0000000000b2"),
            user_id=owner_id,
            snapshot_id=UUID("00000000-0000-4000-8000-0000000000b3"),
            scenario_hash="a" * 64,
            compiler_revision="compiler:test",
            runtime_revision="simc:test",
            idempotency_key="atomic-submit",
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=now,
            updated_at=now,
        )
        cursor = AtomicSubmissionCursor([(job.id,)])
        connection = AtomicSubmissionConnection(cursor)
        connection_count = 0

        def connection_factory():
            nonlocal connection_count
            connection_count += 1
            return connection

        repository = PostgresSimulationRepository(connection_factory)
        payload = {
            "snapshotId": str(job.snapshot_id),
            "scenario": {"fightStyle": "Patchwerk"},
            "scenarioHash": job.scenario_hash,
            "compilerRevision": job.compiler_revision,
            "runtimeRevision": job.runtime_revision,
        }

        persisted = repository.create_job_and_enqueue(job, payload=payload, max_attempts=3)

        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIs(persisted, job)
        self.assertEqual(connection_count, 1)
        self.assertIn("INSERT INTO simc.simulation_jobs", sql)
        self.assertIn("ON CONFLICT (user_id, idempotency_key) DO NOTHING", sql)
        self.assertIn("INSERT INTO ops.job_queue", sql)

    def test_atomic_idempotency_race_returns_existing_without_second_queue_row(self):
        owner_id = UUID("00000000-0000-4000-8000-0000000000c1")
        now = datetime(2026, 9, 3, tzinfo=timezone.utc)
        requested = SimulationJob(
            id=UUID("00000000-0000-4000-8000-0000000000c2"),
            user_id=owner_id,
            snapshot_id=UUID("00000000-0000-4000-8000-0000000000c3"),
            scenario_hash="b" * 64,
            compiler_revision="compiler:test",
            runtime_revision="simc:test",
            idempotency_key="atomic-race",
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=now,
            updated_at=now,
        )
        existing_id = UUID("00000000-0000-4000-8000-0000000000c4")
        existing_row = (
            existing_id,
            owner_id,
            requested.snapshot_id,
            requested.scenario_hash,
            requested.compiler_revision,
            requested.runtime_revision,
            requested.idempotency_key,
            "queued",
            "",
            now,
            now,
        )
        cursor = AtomicSubmissionCursor([None, existing_row])
        repository = PostgresSimulationRepository(lambda: AtomicSubmissionConnection(cursor))

        persisted = repository.create_job_and_enqueue(requested, payload={}, max_attempts=3)

        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertEqual(persisted.id, existing_id)
        self.assertNotIn("INSERT INTO ops.job_queue", sql)


if __name__ == "__main__":
    unittest.main()
