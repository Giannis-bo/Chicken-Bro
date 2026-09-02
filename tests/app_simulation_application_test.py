import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from server.app.identity.prototype import PrototypePrincipal
from server.app.simulation.application import SimulationApplicationError, PrototypeSimulationApplication
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.domain import SimulationJobStatus, SourceReadiness
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import CharacterSourceRouter, RaiderIOCharacterAdapter


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def fetch_json(self, url, *, headers=None):
        return json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())


class MemorySimulationRepository:
    def __init__(self):
        self.snapshots = {}
        self.jobs = {}
        self.results = {}

    def next_snapshot_revision(self, user_id, provider, source_key):
        revisions = [
            snapshot.revision
            for (owner, _), snapshot in self.snapshots.items()
            if owner == user_id and snapshot.provider == provider and snapshot.source_key == source_key
        ]
        return max(revisions, default=0) + 1

    def save_snapshot(self, snapshot):
        self.snapshots[(snapshot.user_id, snapshot.id)] = snapshot

    def get_snapshot(self, user_id, snapshot_id):
        return self.snapshots.get((user_id, snapshot_id))

    def get_job_by_idempotency(self, user_id, idempotency_key):
        return next(
            (job for (owner, _), job in self.jobs.items() if owner == user_id and job.idempotency_key == idempotency_key),
            None,
        )

    def save_job(self, job):
        self.jobs[(job.user_id, job.id)] = job

    def get_job(self, user_id, job_id):
        return self.jobs.get((user_id, job_id))

    def save_result(self, result):
        self.results[(result.user_id, result.job_id)] = result

    def get_result(self, user_id, job_id):
        return self.results.get((user_id, job_id))


class MemoryQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)


class SimulationApplicationTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        self.owner = PrototypePrincipal(
            UUID("00000000-0000-4000-8000-000000000001"),
            UUID("00000000-0000-4000-8000-000000000002"),
        )
        self.other = PrototypePrincipal(
            UUID("00000000-0000-4000-8000-000000000003"),
            UUID("00000000-0000-4000-8000-000000000004"),
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
        self.application = PrototypeSimulationApplication(
            repository=self.repository,
            source_router=router,
            readiness_validator=SimcReadinessValidator(),
            compiler=SimcProfileCompiler(capabilities=capabilities),
            runtime_capabilities=capabilities,
            queue=self.queue,
            clock=lambda: self.now,
        )

    def test_ready_source_can_submit_by_reference_and_is_idempotent(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )
        self.assertEqual(snapshot.readiness, SourceReadiness.READY_FOR_SIMC)

        first = self.application.submit(
            self.owner,
            snapshot.id,
            {"fightStyle": "Patchwerk", "desiredTargets": 1},
            "sim-1",
        )
        second = self.application.submit(
            self.owner,
            snapshot.id,
            {"fightStyle": "Patchwerk", "desiredTargets": 1},
            "sim-1",
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.status, SimulationJobStatus.QUEUED)
        self.assertEqual(len(self.queue.calls), 1)
        self.assertNotIn("profile", self.queue.calls[0]["payload"])
        self.assertEqual(self.queue.calls[0]["payload"]["snapshotId"], str(snapshot.id))

    def test_other_owner_cannot_read_or_submit_snapshot(self):
        snapshot = self.application.resolve_source(
            self.owner,
            "https://raider.io/characters/us/area-52/Stormsample",
        )

        with self.assertRaisesRegex(SimulationApplicationError, "SNAPSHOT_NOT_FOUND"):
            self.application.submit(self.other, snapshot.id, {"fightStyle": "Patchwerk"}, "sim-2")

    def test_incomplete_snapshot_is_saved_for_explanation_but_cannot_enter_queue(self):
        router = CharacterSourceRouter(FakeGateway())
        incomplete_application = PrototypeSimulationApplication(
            repository=self.repository,
            source_router=router,
            readiness_validator=SimcReadinessValidator(),
            compiler=self.application._compiler,
            runtime_capabilities=self.application._runtime_capabilities,
            queue=self.queue,
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
            incomplete_application.submit(self.owner, snapshot.id, {"fightStyle": "Patchwerk"}, "sim-3")
        self.assertEqual(self.queue.calls, [])


if __name__ == "__main__":
    unittest.main()
