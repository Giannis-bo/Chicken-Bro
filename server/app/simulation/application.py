from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Mapping
from uuid import UUID, uuid4

from server.app.identity.prototype import PrototypePrincipal
from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler
from server.app.simulation.domain import SimulationJob, SimulationJobStatus, SimulationResult, SourceSnapshot
from server.app.simulation.readiness import ReadinessReport, SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import CharacterSourceRouter, InvalidSourceLink


class SimulationApplicationError(ValueError):
    def __init__(self, code: str, message: str, *, blockers: tuple[str, ...] = ()):
        self.code = code
        self.message = message
        self.blockers = blockers
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class SimulationJobView:
    job: SimulationJob
    result: SimulationResult | None = None


def _utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class PrototypeSimulationApplication:
    def __init__(
        self,
        *,
        repository: object,
        source_router: CharacterSourceRouter,
        readiness_validator: SimcReadinessValidator,
        compiler: SimcProfileCompiler,
        runtime_capabilities: SimcRuntimeCapabilities,
        queue: object,
        clock: Callable[[], datetime] | None = None,
    ):
        self._repository = repository
        self._source_router = source_router
        self._readiness_validator = readiness_validator
        self._compiler = compiler
        self._runtime_capabilities = runtime_capabilities
        self._queue = queue
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve_source(self, principal: PrototypePrincipal, source_url: str) -> SourceSnapshot:
        try:
            candidate = self._source_router.resolve(source_url)
        except InvalidSourceLink as error:
            raise SimulationApplicationError("INVALID_LINK", "source link is not allowed") from error
        report = self._readiness_validator.validate(candidate, self._runtime_capabilities)
        revision = self._repository.next_snapshot_revision(
            principal.user_id,
            candidate.provider,
            candidate.source_key,
        )
        snapshot = candidate.to_source_snapshot(
            user_id=principal.user_id,
            snapshot_id=uuid4(),
            readiness_report=report,
            revision=revision,
        )
        self._repository.save_snapshot(snapshot)
        return snapshot

    def submit(
        self,
        principal: PrototypePrincipal,
        snapshot_id: UUID,
        scenario: Mapping[str, object],
        idempotency_key: str,
    ) -> SimulationJob:
        key = self._bounded_key(idempotency_key)
        existing = self._repository.get_job_by_idempotency(principal.user_id, key)
        if existing is not None:
            return existing
        snapshot = self._repository.get_snapshot(principal.user_id, snapshot_id)
        if snapshot is None:
            raise SimulationApplicationError("SNAPSHOT_NOT_FOUND", "snapshot not found")
        report = self._readiness_validator.validate(snapshot, self._runtime_capabilities)
        if not report.ready:
            raise SimulationApplicationError(
                "SNAPSHOT_NOT_READY",
                "snapshot is not ready for SimC",
                blockers=report.blockers,
            )
        ready_snapshot = snapshot if snapshot.readiness is report.readiness else replace(snapshot, readiness=report.readiness)
        try:
            compiled = self._compiler.compile(ready_snapshot, scenario)
        except SimcCompileError as error:
            raise SimulationApplicationError(error.code, str(error)) from error

        now = _utc(self._clock)
        job = SimulationJob(
            id=uuid4(),
            user_id=principal.user_id,
            snapshot_id=snapshot.id,
            scenario_hash=compiled.scenario_hash,
            compiler_revision=compiled.compiler_revision,
            runtime_revision=compiled.runtime_revision,
            idempotency_key=key,
            status=SimulationJobStatus.QUEUED,
            public_error_code="",
            created_at=now,
            updated_at=now,
        )
        self._repository.save_job(job)
        self._queue.enqueue(
            job_id=job.id,
            domain="simc",
            command_type="run_simulation",
            aggregate_id=job.id,
            payload={
                "snapshotId": str(snapshot.id),
                "scenario": dict(compiled.scenario),
                "scenarioHash": compiled.scenario_hash,
                "compilerRevision": compiled.compiler_revision,
                "runtimeRevision": compiled.runtime_revision,
            },
            max_attempts=3,
        )
        return job

    def read_snapshot(self, principal: PrototypePrincipal, snapshot_id: UUID) -> SourceSnapshot:
        snapshot = self._repository.get_snapshot(principal.user_id, snapshot_id)
        if snapshot is None:
            raise SimulationApplicationError("SNAPSHOT_NOT_FOUND", "snapshot not found")
        return snapshot

    def read_job(self, principal: PrototypePrincipal, job_id: UUID) -> SimulationJobView:
        job = self._repository.get_job(principal.user_id, job_id)
        if job is None:
            raise SimulationApplicationError("SIMULATION_NOT_FOUND", "simulation not found")
        result = self._repository.get_result(principal.user_id, job.id)
        return SimulationJobView(job=job, result=result)

    @staticmethod
    def _bounded_key(value: str) -> str:
        if not isinstance(value, str):
            raise SimulationApplicationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
        key = value.strip()
        if not key:
            raise SimulationApplicationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
        if len(key) > 200 or any(character.isspace() for character in key):
            raise SimulationApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")
        return key


__all__ = ("PrototypeSimulationApplication", "SimulationApplicationError", "SimulationJobView")
