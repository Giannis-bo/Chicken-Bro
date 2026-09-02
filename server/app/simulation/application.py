import base64
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

from server.app.identity.domain import Principal
from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler, scenario_hash
from server.app.simulation.domain import SimulationJob, SimulationJobStatus, SimulationResult, SourceSnapshot
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
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


@dataclass(frozen=True)
class SimulationJobPage:
    items: tuple[SimulationJobView, ...]
    next_cursor: str | None


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _encode_job_cursor(row: Any) -> str:
    updated_at = _value(row, "updated_at")
    if not isinstance(updated_at, datetime):
        raise SimulationApplicationError("INVALID_CURSOR", "job cursor cannot be encoded")
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    payload = {
        "updatedAt": updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "id": str(UUID(str(_value(row, "id")))),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return encoded.rstrip(b"=").decode("ascii")


def _decode_job_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 1024:
            raise ValueError("invalid cursor envelope")
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"updatedAt", "id"}:
            raise ValueError("invalid cursor payload")
        raw_updated_at = payload["updatedAt"]
        if not isinstance(raw_updated_at, str):
            raise ValueError("invalid cursor timestamp")
        updated_at = datetime.fromisoformat(raw_updated_at.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        return updated_at.astimezone(timezone.utc), UUID(str(payload["id"]))
    except (UnicodeError, ValueError, TypeError) as error:
        raise SimulationApplicationError("INVALID_CURSOR", "job cursor is invalid") from error


class SimulationApplication:
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

    def resolve_source(self, principal: Principal, source_url: str) -> SourceSnapshot:
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
        principal: Principal,
        snapshot_id: UUID,
        scenario: Mapping[str, object],
        idempotency_key: str,
    ) -> SimulationJob:
        key = self._bounded_key(idempotency_key)
        try:
            requested_scenario_hash = scenario_hash(scenario)
        except SimcCompileError as error:
            raise SimulationApplicationError(error.code, str(error)) from error
        existing = self._repository.get_job_by_idempotency(principal.user_id, key)
        if existing is not None:
            if existing.snapshot_id != snapshot_id or existing.scenario_hash != requested_scenario_hash:
                raise SimulationApplicationError(
                    "IDEMPOTENCY_CONFLICT",
                    "idempotency key belongs to a different simulation request",
                )
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

    def read_snapshot(self, principal: Principal, snapshot_id: UUID) -> SourceSnapshot:
        snapshot = self._repository.get_snapshot(principal.user_id, snapshot_id)
        if snapshot is None:
            raise SimulationApplicationError("SNAPSHOT_NOT_FOUND", "snapshot not found")
        return snapshot

    def list_jobs(
        self,
        principal: Principal,
        cursor: str | None = None,
        limit: int = 20,
    ) -> SimulationJobPage:
        boundary = _decode_job_cursor(cursor) if cursor else None
        bounded_limit = min(max(int(limit), 1), 50)
        rows = self._repository.list_jobs(
            principal.user_id,
            boundary,
            bounded_limit + 1,
        )
        page_rows = rows[:bounded_limit]
        items = tuple(
            SimulationJobView(
                job=job,
                result=self._repository.get_result(principal.user_id, job.id),
            )
            for job in page_rows
        )
        next_cursor = (
            _encode_job_cursor(page_rows[-1])
            if len(rows) > bounded_limit and page_rows
            else None
        )
        return SimulationJobPage(items=items, next_cursor=next_cursor)

    def read_job(self, principal: Principal, job_id: UUID) -> SimulationJobView:
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
        if len(key) > 128 or any(character.isspace() for character in key):
            raise SimulationApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")
        return key


PrototypeSimulationApplication = SimulationApplication


__all__ = (
    "PrototypeSimulationApplication",
    "SimulationApplication",
    "SimulationApplicationError",
    "SimulationJobPage",
    "SimulationJobView",
)
