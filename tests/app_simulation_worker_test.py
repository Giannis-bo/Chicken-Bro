import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server.app.simulation.compiler import scenario_hash
from server.app.simulation.domain import SimulationJob, SimulationJobStatus, SimulationResult
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.worker import (
    RawSimulationExecution,
    SimulationCraftPort,
    SimulationResultParser,
    SimulationWorker,
)
from server.app.worker.handlers import RetryableJobError
from server.app.worker.leases import JobLease
from server.app.worker.leases import LostLeaseError


class MemorySimulationWorkerRepository:
    def __init__(self, job, snapshot):
        self.job = job
        self.snapshot = snapshot
        self.attempts = []
        self.results = []
        self.updates = []
        self.exhausted = []
        self.lose_lease_on_success = False

    def exhaust_job_after_attempt_limit(self, job_id, *, worker_id, finished_at):
        if job_id != self.job.id:
            return None
        self.exhausted.append((job_id, worker_id, finished_at))
        if self.job.status in {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        }:
            return self.job.status
        if self.attempts:
            self.attempts[-1].update(
                {"returnCode": None, "diagnostic": "ATTEMPT_EXHAUSTED"}
            )
        self.job = replace(
            self.job,
            status=SimulationJobStatus.FAILED,
            public_error_code="ATTEMPT_EXHAUSTED",
            updated_at=finished_at,
        )
        return self.job.status

    def begin_job_attempt(self, job_id, *, worker_id, attempt_number, now):
        if job_id != self.job.id:
            return None
        attempt = {"id": uuid4(), "number": attempt_number}
        self.attempts.append(attempt)
        if self.job.status in {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        }:
            attempt.update({"returnCode": None, "diagnostic": "ALREADY_TERMINAL"})
            return self.job, None
        self.job = replace(
            self.job,
            status=SimulationJobStatus.RUNNING,
            public_error_code="",
            updated_at=now,
        )
        return self.job, attempt["id"]

    def get_snapshot(self, user_id, snapshot_id):
        return self.snapshot if user_id == self.snapshot.user_id and snapshot_id == self.snapshot.id else None

    def complete_job_success(
        self,
        job,
        attempt_id,
        result,
        *,
        worker_id,
        return_code,
        finished_at,
    ):
        if self.lose_lease_on_success:
            raise LostLeaseError("lease lost before result commit")
        if self.job.status in {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        }:
            return self.job.status
        self.results.append(result)
        self.attempts[-1].update({"returnCode": return_code, "diagnostic": "succeeded"})
        self.job = replace(
            self.job,
            status=SimulationJobStatus.SUCCEEDED,
            public_error_code="",
            updated_at=finished_at,
        )
        return self.job.status

    def complete_job_failure(
        self,
        job,
        attempt_id,
        *,
        worker_id,
        status,
        error_code,
        return_code,
        finished_at,
    ):
        if self.job.status in {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        }:
            return self.job.status
        self.attempts[-1].update({"returnCode": return_code, "diagnostic": error_code})
        self.updates.append((status, error_code))
        self.job = replace(
            self.job,
            status=status,
            public_error_code=error_code,
            updated_at=finished_at,
        )
        return self.job.status


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
            scenario_hash=scenario_hash({"fightStyle": "Patchwerk", "desiredTargets": 1}),
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
                "scenarioHash": scenario_hash({"fightStyle": "Patchwerk", "desiredTargets": 1}),
                "compilerRevision": "chickenbro-simc-compiler-v1",
                "runtimeRevision": "simc:current:abc",
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
                stdout="Player: Stormsample\nSimulationCraft completed without a primary result",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )

        status = worker.handle(self.lease)

        self.assertEqual(status, SimulationJobStatus.FAILED)
        self.assertEqual(repository.job.public_error_code, "SIMC_METRIC_MISSING")
        self.assertEqual(repository.results, [])

    def test_exit_zero_placeholder_actor_fails_without_result_publication(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="Player: Stormsample race=none\nDPS=12345\n",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )

        status = worker.handle(self.lease)

        self.assertEqual(status, SimulationJobStatus.FAILED)
        self.assertEqual(repository.job.public_error_code, "SIMC_ACTOR_INVALID")
        self.assertEqual(repository.results, [])

    def test_duplicate_queue_delivery_keeps_one_result_and_does_not_rerun_simc(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="Player: Stormsample\nDPS=12345\n",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )

        first = worker.handle(self.lease)
        second = worker.handle(replace(self.lease, attempt=2))

        self.assertEqual(first, SimulationJobStatus.SUCCEEDED)
        self.assertEqual(second, SimulationJobStatus.SUCCEEDED)
        self.assertEqual(len(repository.results), 1)
        self.assertEqual(len(worker._simc.inputs), 1)
        self.assertEqual(repository.attempts[-1]["diagnostic"], "ALREADY_TERMINAL")

    def test_lost_lease_before_result_commit_is_retryable_and_publishes_nothing(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="Player: Stormsample\nDPS=12345\n",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )
        repository.lose_lease_on_success = True

        with self.assertRaises(RetryableJobError) as context:
            worker.handle(self.lease)

        self.assertEqual(context.exception.code, "LEASE_LOST")
        self.assertEqual(repository.results, [])
        self.assertEqual(repository.job.status, SimulationJobStatus.RUNNING)

    def test_queue_payload_identity_must_match_the_immutable_job(self):
        missing_hash = dict(self.lease.payload)
        missing_hash.pop("scenarioHash")
        invalid_payloads = (
            {**self.lease.payload, "scenarioHash": "f" * 64},
            missing_hash,
            {**self.lease.payload, "compilerRevision": "compiler:tampered"},
            {**self.lease.payload, "profile": "raw profile must never enter the queue"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                worker, repository = self.build_worker(
                    RawSimulationExecution(
                        return_code=0,
                        stdout="Player: Stormsample\nDPS=12345\n",
                        stderr="",
                        runtime_revision="simc:current:abc",
                    )
                )

                status = worker.handle(replace(self.lease, payload=payload))

                self.assertEqual(status, SimulationJobStatus.FAILED)
                self.assertEqual(repository.job.public_error_code, "JOB_PAYLOAD_INVALID")
                self.assertEqual(worker._simc.inputs, [])
                self.assertEqual(repository.results, [])

    def test_expired_final_attempt_is_terminalized_without_a_fourth_simc_run(self):
        worker, repository = self.build_worker(
            RawSimulationExecution(
                return_code=0,
                stdout="Player: Stormsample\nDPS=12345\n",
                stderr="",
                runtime_revision="simc:current:abc",
            )
        )
        repository.job = replace(repository.job, status=SimulationJobStatus.RUNNING)
        repository.attempts.append({"id": uuid4(), "number": 3})

        status = worker.handle(replace(self.lease, attempt=4, max_attempts=3))

        self.assertEqual(status, SimulationJobStatus.FAILED)
        self.assertEqual(repository.job.public_error_code, "ATTEMPT_EXHAUSTED")
        self.assertEqual(repository.attempts[-1]["diagnostic"], "ATTEMPT_EXHAUSTED")
        self.assertEqual(len(repository.exhausted), 1)
        self.assertEqual(worker._simc.inputs, [])
        self.assertEqual(repository.results, [])


class ScriptedCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.statements = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=()):
        self.statements.append((" ".join(statement.split()), parameters))
        self.rowcount = 1

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class ScriptedConnection:
    def __init__(self, rows):
        self.cursor_value = ScriptedCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.cursor_value


def job_row(job):
    return (
        job.id,
        job.user_id,
        job.snapshot_id,
        job.scenario_hash,
        job.compiler_revision,
        job.runtime_revision,
        job.idempotency_key,
        job.status.value,
        job.public_error_code,
        job.created_at,
        job.updated_at,
    )


class SimulationRepositoryAtomicityTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
        self.job = SimulationJob(
            id=UUID("00000000-0000-4000-8000-000000000301"),
            user_id=UUID("00000000-0000-4000-8000-000000000302"),
            snapshot_id=UUID("00000000-0000-4000-8000-000000000303"),
            scenario_hash="a" * 64,
            compiler_revision="compiler:test",
            runtime_revision="simc:test",
            idempotency_key="atomic-job",
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=self.now,
            updated_at=self.now,
        )

    def test_result_attempt_and_terminal_job_commit_share_one_guarded_transaction(self):
        attempt_id = UUID("00000000-0000-4000-8000-000000000304")
        begin_connection = ScriptedConnection([
            (self.job.id,),
            job_row(self.job),
            (attempt_id,),
        ])
        running_job = replace(self.job, status=SimulationJobStatus.RUNNING)
        complete_connection = ScriptedConnection([
            (self.job.id,),
            job_row(running_job),
        ])
        connections = iter((begin_connection, complete_connection))
        repository = PostgresSimulationRepository(lambda: next(connections))

        started = repository.begin_job_attempt(
            self.job.id,
            worker_id="worker-atomic",
            attempt_number=1,
            now=self.now,
        )
        self.assertIsNotNone(started)
        started_job, started_attempt_id = started
        result = SimulationResult(
            id=UUID("00000000-0000-4000-8000-000000000305"),
            job_id=self.job.id,
            user_id=self.job.user_id,
            profile_sha256="b" * 64,
            result={"metricName": "dps", "metricValue": 12345.0, "provenance": {}},
            primary_metric_name="dps",
            primary_metric_value=12345.0,
            compiler_revision=self.job.compiler_revision,
            runtime_revision=self.job.runtime_revision,
            created_at=self.now,
        )

        status = repository.complete_job_success(
            started_job,
            started_attempt_id,
            result,
            worker_id="worker-atomic",
            return_code=0,
            finished_at=self.now,
        )

        self.assertEqual(status, SimulationJobStatus.SUCCEEDED)
        complete_sql = "\n".join(statement for statement, _ in complete_connection.cursor_value.statements)
        self.assertIn("FROM ops.job_queue", complete_sql)
        self.assertIn("NOT cancel_requested", complete_sql)
        self.assertIn("INSERT INTO simc.simulation_results", complete_sql)
        self.assertIn("UPDATE simc.simulation_attempts", complete_sql)
        self.assertIn("UPDATE simc.simulation_jobs", complete_sql)
        self.assertLess(
            complete_sql.index("INSERT INTO simc.simulation_results"),
            complete_sql.index("UPDATE simc.simulation_jobs"),
        )

    def test_lost_queue_lease_prevents_domain_attempt_creation(self):
        connection = ScriptedConnection([])
        repository = PostgresSimulationRepository(lambda: connection)

        with self.assertRaises(LostLeaseError):
            repository.begin_job_attempt(
                self.job.id,
                worker_id="stale-worker",
                attempt_number=1,
                now=self.now,
            )

        sql = "\n".join(statement for statement, _ in connection.cursor_value.statements)
        self.assertIn("FROM ops.job_queue", sql)
        self.assertNotIn("INSERT INTO simc.simulation_attempts", sql)

    def test_exhaustion_closes_unfinished_attempt_and_job_in_one_guarded_transaction(self):
        running_job = replace(self.job, status=SimulationJobStatus.RUNNING)
        connection = ScriptedConnection([
            (self.job.id,),
            job_row(running_job),
        ])
        repository = PostgresSimulationRepository(lambda: connection)

        status = repository.exhaust_job_after_attempt_limit(
            self.job.id,
            worker_id="worker-atomic",
            finished_at=self.now,
        )

        self.assertEqual(status, SimulationJobStatus.FAILED)
        sql = "\n".join(statement for statement, _ in connection.cursor_value.statements)
        self.assertIn("FROM ops.job_queue", sql)
        self.assertIn("NOT cancel_requested", sql)
        self.assertIn("UPDATE simc.simulation_attempts", sql)
        self.assertIn("ATTEMPT_EXHAUSTED", sql)
        self.assertIn("UPDATE simc.simulation_jobs", sql)


if __name__ == "__main__":
    unittest.main()
