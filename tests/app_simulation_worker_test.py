import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server.app.simulation.domain import SimulationJob, SimulationJobStatus
from server.app.simulation.worker import (
    RawSimulationExecution,
    SimulationCraftPort,
    SimulationResultParser,
    SimulationWorker,
)
from server.app.worker.leases import JobLease


class MemorySimulationWorkerRepository:
    def __init__(self, job, snapshot):
        self.job = job
        self.snapshot = snapshot
        self.attempts = []
        self.results = []
        self.updates = []

    def get_job_by_id(self, job_id):
        return self.job if job_id == self.job.id else None

    def update_job(self, user_id, job_id, status, public_error_code=""):
        self.updates.append((status, public_error_code))
        self.job = self.job.__class__(**{
            **self.job.__dict__,
            "status": status,
            "public_error_code": public_error_code,
        })

    def get_snapshot(self, user_id, snapshot_id):
        return self.snapshot if user_id == self.snapshot.user_id and snapshot_id == self.snapshot.id else None

    def start_attempt(self, job_id, user_id, worker_id, attempt_number, now):
        attempt = {"id": uuid4(), "number": attempt_number}
        self.attempts.append(attempt)
        return attempt["id"]

    def finish_attempt(self, attempt_id, *, return_code, diagnostic, finished_at):
        self.attempts[-1].update({"returnCode": return_code, "diagnostic": diagnostic})

    def save_result(self, result):
        self.results.append(result)


class FakeSimc(SimulationCraftPort):
    def __init__(self, execution):
        self.execution = execution
        self.inputs = []

    def run(self, compiled_input, runtime_revision):
        self.inputs.append((compiled_input, runtime_revision))
        return self.execution


def ready_fixture_snapshot():
    from tests.app_simulation_compiler_test import SimulationCompilerTest

    test = SimulationCompilerTest("test_compiler_outputs_bounded_profile_with_hash_and_provenance")
    test.setUp()
    return test.snapshot


class SimulationWorkerTest(unittest.TestCase):
    def setUp(self):
        snapshot = ready_fixture_snapshot()
        self.job = SimulationJob(
            id=UUID("00000000-0000-4000-8000-000000000201"),
            user_id=snapshot.user_id,
            snapshot_id=snapshot.id,
            scenario_hash="unused-until-compile",
            compiler_revision="chickenbro-simc-compiler-v1",
            runtime_revision="simc:current:abc",
            idempotency_key="sim-1",
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        self.lease = JobLease(
            id=self.job.id,
            domain="simc",
            command_type="run_simulation",
            aggregate_id=self.job.id,
            payload={
                "snapshotId": str(snapshot.id),
                "scenario": {"fightStyle": "Patchwerk", "desiredTargets": 1},
            },
            attempt=1,
            max_attempts=3,
        )

    def build_worker(self, execution):
        repository = MemorySimulationWorkerRepository(self.job, ready_fixture_snapshot())
        worker = SimulationWorker(
            repository=repository,
            simc=FakeSimc(execution),
            worker_id="worker-test",
            compiler=__import__("server.app.simulation.compiler", fromlist=["SimcProfileCompiler"]).SimcProfileCompiler(
                capabilities=__import__("server.app.simulation.readiness", fromlist=["SimcRuntimeCapabilities"]).SimcRuntimeCapabilities(
                    runtime_revision="simc:current:abc",
                    compiler_revision="chickenbro-simc-compiler-v1",
                    supported_specs=frozenset({("shaman", "elemental")}),
                )
            ),
            readiness_validator=__import__("server.app.simulation.readiness", fromlist=["SimcReadinessValidator"]).SimcReadinessValidator(),
            runtime_capabilities=__import__("server.app.simulation.readiness", fromlist=["SimcRuntimeCapabilities"]).SimcRuntimeCapabilities(
                runtime_revision="simc:current:abc",
                compiler_revision="chickenbro-simc-compiler-v1",
                supported_specs=frozenset({("shaman", "elemental")}),
            ),
            result_parser=SimulationResultParser(),
            clock=lambda: datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
        return worker, repository

    def test_only_semantic_metric_publishes_succeeded_result(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="Player: Stormsample\nDPS=12345 DPS-Error=0/0.00%\n",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )

        status = worker.handle(self.lease)

        self.assertEqual(status, SimulationJobStatus.SUCCEEDED)
        self.assertEqual(len(repository.results), 1)
        self.assertEqual(repository.results[0].primary_metric_name, "dps")
        self.assertEqual(repository.results[0].primary_metric_value, 12345)
        self.assertNotIn("stdout", repository.results[0].result)
        self.assertEqual(repository.job.status, SimulationJobStatus.SUCCEEDED)

    def test_exit_zero_without_metric_fails_without_result_publication(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="SimulationCraft completed without a primary result",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )

        status = worker.handle(self.lease)

        self.assertEqual(status, SimulationJobStatus.FAILED)
        self.assertEqual(repository.job.public_error_code, "SIMC_METRIC_MISSING")
        self.assertEqual(repository.results, [])


if __name__ == "__main__":
    unittest.main()
