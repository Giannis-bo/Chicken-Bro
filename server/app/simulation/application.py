import base64
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID, uuid4

from server.app.identity.domain import Principal
from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler, scenario_hash
from server.app.simulation.domain import (
    SimulationAttempt,
    SimulationJob,
    SimulationJobStatus,
    SimulationResult,
    SourceSnapshot,
)
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import CharacterSourceRouter, InvalidSourceLink


_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._~-]{8,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PUBLIC_RESULT_PROVENANCE_KEYS = (
    "snapshotId",
    "sourceRevision",
    "sourceRawSha256",
    "profileSha256",
    "compilerRevision",
    "runtimeRevision",
    "scenarioHash",
)


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
    attempts: tuple[SimulationAttempt, ...] = ()
    snapshot: SourceSnapshot | None = None


@dataclass(frozen=True)
class SimulationJobPage:
    items: tuple[SimulationJobView, ...]
    next_cursor: str | None


def _invalid_result() -> SimulationApplicationError:
    return SimulationApplicationError("SIMC_RESULT_INVALID", "simulation result is invalid")


def validated_simulation_result_provenance(
    view: SimulationJobView,
) -> dict[str, str] | None:
    """Return the exact public provenance only when the persisted result is coherent."""

    job = view.job
    result = view.result
    if result is None:
        if job.status is SimulationJobStatus.SUCCEEDED:
            raise _invalid_result()
        return None
    if (
        job.status is not SimulationJobStatus.SUCCEEDED
        or not isinstance(result, SimulationResult)
        or result.job_id != job.id
        or result.user_id != job.user_id
        or not isinstance(result.profile_sha256, str)
        or _SHA256.fullmatch(result.profile_sha256) is None
        or result.primary_metric_name not in {"dps", "hps"}
        or isinstance(result.primary_metric_value, bool)
        or not isinstance(result.primary_metric_value, (int, float))
        or not math.isfinite(result.primary_metric_value)
        or result.primary_metric_value <= 0
        or not isinstance(result.compiler_revision, str)
        or not 0 < len(result.compiler_revision) <= 160
        or result.compiler_revision != job.compiler_revision
        or not isinstance(result.runtime_revision, str)
        or not 0 < len(result.runtime_revision) <= 160
        or result.runtime_revision != job.runtime_revision
        or not isinstance(job.scenario_hash, str)
        or _SHA256.fullmatch(job.scenario_hash) is None
        or not isinstance(result.result, Mapping)
    ):
        raise _invalid_result()

    raw_metric_name = result.result.get("metricName")
    raw_metric_value = result.result.get("metricValue")
    if (
        raw_metric_name != result.primary_metric_name
        or isinstance(raw_metric_value, bool)
        or not isinstance(raw_metric_value, (int, float))
        or not math.isfinite(raw_metric_value)
        or raw_metric_value != result.primary_metric_value
    ):
        raise _invalid_result()

    def public_provenance(raw: object) -> dict[str, str]:
        if not isinstance(raw, Mapping):
            raise _invalid_result()
        output: dict[str, str] = {}
        for key in _PUBLIC_RESULT_PROVENANCE_KEYS:
            value = raw.get(key)
            if not isinstance(value, str) or not 0 < len(value) <= 160:
                raise _invalid_result()
            output[key] = value
        return output

    provenance = public_provenance(result.result.get("provenance"))
    persisted_provenance = public_provenance(result.provenance)
    snapshot = view.snapshot
    if (
        provenance != persisted_provenance
        or not isinstance(snapshot, SourceSnapshot)
        or snapshot.id != job.snapshot_id
        or snapshot.user_id != job.user_id
        or not isinstance(snapshot.provenance, Mapping)
        or not isinstance(snapshot.raw_sha256, str)
        or _SHA256.fullmatch(snapshot.raw_sha256) is None
    ):
        raise _invalid_result()
    source_revision = snapshot.provenance.get("sourceRevision")
    if not isinstance(source_revision, str) or not 0 < len(source_revision) <= 160:
        raise _invalid_result()

    if (
        provenance["snapshotId"] != str(job.snapshot_id)
        or provenance["sourceRevision"] != source_revision
        or provenance["sourceRawSha256"] != snapshot.raw_sha256
        or _SHA256.fullmatch(provenance["sourceRawSha256"]) is None
        or provenance["profileSha256"] != result.profile_sha256
        or provenance["compilerRevision"] != job.compiler_revision
        or provenance["runtimeRevision"] != job.runtime_revision
        or provenance["scenarioHash"] != job.scenario_hash
    ):
        raise _invalid_result()
    return provenance


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
        clock: Callable[[], datetime] | None = None,
    ):
        self._repository = repository
        self._source_router = source_router
        self._readiness_validator = readiness_validator
        self._compiler = compiler
        self._runtime_capabilities = runtime_capabilities
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve_source(self, principal: Principal, source_url: str) -> SourceSnapshot:
        try:
            candidate = self._source_router.resolve(source_url)
        except InvalidSourceLink as error:
            raise SimulationApplicationError("INVALID_LINK", "source link is not allowed") from error
        report = self._readiness_validator.validate(candidate, self._runtime_capabilities)
        snapshot = candidate.to_source_snapshot(
            user_id=principal.user_id,
            snapshot_id=uuid4(),
            readiness_report=report,
            revision=1,
        )
        return self._repository.save_snapshot_with_next_revision(snapshot)

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
        persisted = self._repository.create_job_and_enqueue(
            job,
            payload={
                "snapshotId": str(snapshot.id),
                "scenario": dict(compiled.scenario),
                "scenarioHash": compiled.scenario_hash,
                "compilerRevision": compiled.compiler_revision,
                "runtimeRevision": compiled.runtime_revision,
            },
            max_attempts=3,
        )
        if persisted.snapshot_id != snapshot_id or persisted.scenario_hash != requested_scenario_hash:
            raise SimulationApplicationError(
                "IDEMPOTENCY_CONFLICT",
                "idempotency key belongs to a different simulation request",
            )
        return persisted

    def read_snapshot(self, principal: Principal, snapshot_id: UUID) -> SourceSnapshot:
        snapshot = self._repository.get_snapshot(principal.user_id, snapshot_id)
        if snapshot is None:
            raise SimulationApplicationError("SNAPSHOT_NOT_FOUND", "snapshot not found")
        return snapshot

    def _job_view(
        self,
        principal: Principal,
        job: SimulationJob,
        *,
        attempts: tuple[SimulationAttempt, ...] = (),
    ) -> SimulationJobView:
        result = self._repository.get_result(principal.user_id, job.id)
        snapshot = (
            self._repository.get_snapshot(principal.user_id, job.snapshot_id)
            if result is not None
            else None
        )
        return SimulationJobView(
            job=job,
            result=result,
            attempts=attempts,
            snapshot=snapshot,
        )

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
        items = tuple(self._job_view(principal, job) for job in page_rows)
        for item in items:
            validated_simulation_result_provenance(item)
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
        attempts = tuple(self._repository.list_attempts(job.id, 20))
        view = self._job_view(principal, job, attempts=attempts)
        validated_simulation_result_provenance(view)
        return view

    @staticmethod
    def _bounded_key(value: str) -> str:
        if not isinstance(value, str) or not value:
            raise SimulationApplicationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
        if not _IDEMPOTENCY_KEY.fullmatch(value):
            raise SimulationApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")
        return value


__all__ = (
    "SimulationApplication",
    "SimulationApplicationError",
    "SimulationJobPage",
    "SimulationJobView",
    "validated_simulation_result_provenance",
)
