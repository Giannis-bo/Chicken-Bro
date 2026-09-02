import math
import re
from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import (
    require_mutating_principal,
    require_principal,
    simulation_application,
)
from server.app.api.errors import ApiProblem
from server.app.identity.domain import Principal
from server.app.simulation.application import (
    SimulationApplication,
    SimulationApplicationError,
    SimulationJobView,
)
from server.app.simulation.domain import SimulationAttempt, SimulationResult, SourceSnapshot


router = APIRouter(prefix="/api/v2/simc")
_SAFE_CODE = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class SourceSnapshotCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source_url: str = Field(alias="sourceUrl", min_length=1, max_length=2048)


class SimulationCreateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    snapshot_id: UUID = Field(alias="snapshotId")
    scenario: dict[str, object]


def _iso(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _bounded_codes(value: object, maximum: int = 64) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [
        item
        for item in value[:maximum]
        if isinstance(item, str) and _SAFE_CODE.fullmatch(item) is not None
    ]


def _snapshot_payload(snapshot: SourceSnapshot) -> dict[str, object]:
    raw_snapshot = snapshot.snapshot if isinstance(snapshot.snapshot, Mapping) else {}
    source_revision = str(snapshot.provenance.get("sourceRevision") or "").strip()
    if len(source_revision) > 160:
        source_revision = ""
    return {
        "id": str(snapshot.id),
        "provider": snapshot.provider.value,
        "sourceUrl": snapshot.source_url,
        "sourceKey": snapshot.source_key,
        "revision": snapshot.revision,
        "readiness": snapshot.readiness.value,
        "missingFields": _bounded_codes(raw_snapshot.get("missingFields")),
        "blockers": _bounded_codes(raw_snapshot.get("readinessBlockers")),
        "fetchedAt": _iso(snapshot.fetched_at),
        "provenance": {
            "sourceRevision": source_revision or None,
            "sourceRawSha256": snapshot.raw_sha256,
        },
    }


def _job_summary(view: SimulationJobView) -> dict[str, object]:
    job = view.job
    public_error = str(job.public_error_code or "")
    if public_error and _SAFE_CODE.fullmatch(public_error) is None:
        public_error = "SIMC_FAILED"
    return {
        "id": str(job.id),
        "snapshotId": str(job.snapshot_id),
        "status": job.status.value,
        "scenarioHash": job.scenario_hash,
        "compilerRevision": job.compiler_revision,
        "runtimeRevision": job.runtime_revision,
        "errorCode": public_error or None,
        "createdAt": _iso(job.created_at),
        "updatedAt": _iso(job.updated_at),
    }


def _attempt_payload(attempt: SimulationAttempt) -> dict[str, object]:
    diagnostic = str(attempt.diagnostic or "")
    if diagnostic == "succeeded":
        diagnostic = "SUCCEEDED"
    elif diagnostic and _SAFE_CODE.fullmatch(diagnostic) is None:
        diagnostic = "SIMC_DIAGNOSTIC_REDACTED"
    return {
        "attemptNumber": attempt.attempt_number,
        "startedAt": _iso(attempt.started_at),
        "finishedAt": _iso(attempt.finished_at) if attempt.finished_at is not None else None,
        "exitCode": attempt.exit_code,
        "diagnosticCode": diagnostic or None,
    }


def _result_payload(view: SimulationJobView) -> dict[str, object] | None:
    result = view.result
    if result is None:
        return None
    job = view.job
    if (
        not isinstance(result, SimulationResult)
        or result.job_id != job.id
        or result.user_id != job.user_id
        or not math.isfinite(result.primary_metric_value)
        or result.primary_metric_value <= 0
        or result.compiler_revision != job.compiler_revision
        or result.runtime_revision != job.runtime_revision
        or _SHA256.fullmatch(result.profile_sha256) is None
    ):
        raise SimulationApplicationError("SIMC_RESULT_INVALID", "simulation result is invalid")
    raw_provenance = result.result.get("provenance", {})
    raw_provenance = raw_provenance if isinstance(raw_provenance, Mapping) else {}
    provenance = {
        key: str(raw_provenance[key])
        for key in (
            "snapshotId",
            "sourceRevision",
            "sourceRawSha256",
            "profileSha256",
            "compilerRevision",
            "runtimeRevision",
            "scenarioHash",
        )
        if key in raw_provenance and len(str(raw_provenance[key])) <= 160
    }
    return {
        "id": str(result.id),
        "profileSha256": result.profile_sha256,
        "metricName": result.primary_metric_name,
        "metricValue": result.primary_metric_value,
        "compilerRevision": result.compiler_revision,
        "runtimeRevision": result.runtime_revision,
        "provenance": provenance,
        "createdAt": _iso(result.created_at),
    }


def _job_detail(view: SimulationJobView) -> dict[str, object]:
    return {
        **_job_summary(view),
        "attempts": [_attempt_payload(attempt) for attempt in view.attempts[:20]],
        "result": _result_payload(view),
    }


def _raise_simulation_error(error: SimulationApplicationError) -> None:
    status_code = {
        "INVALID_LINK": 422,
        "INVALID_CURSOR": 422,
        "SIMULATION_NOT_FOUND": 404,
        "SNAPSHOT_NOT_FOUND": 404,
        "SNAPSHOT_NOT_READY": 409,
        "IDEMPOTENCY_CONFLICT": 409,
        "IDEMPOTENCY_KEY_REQUIRED": 422,
        "IDEMPOTENCY_KEY_INVALID": 422,
        "SCENARIO_INVALID": 422,
        "TALENTS_INVALID": 422,
        "PROFILE_TOO_LARGE": 422,
        "COMPILER_UNAVAILABLE": 503,
        "RUNTIME_UNAVAILABLE": 503,
        "SIMC_RESULT_INVALID": 500,
    }.get(error.code, 500)
    raise ApiProblem(status_code=status_code, code=error.code, message=error.message) from error


@router.post("/snapshots", status_code=201)
def create_snapshot(
    body: SourceSnapshotCreateBody,
    principal: Principal = Depends(require_mutating_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _snapshot_payload(application.resolve_source(principal, body.source_url))
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(
    snapshot_id: UUID,
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _snapshot_payload(application.read_snapshot(principal, snapshot_id))
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/jobs")
def list_jobs(
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    try:
        page = application.list_jobs(principal, cursor, limit)
    except (SimulationApplicationError, TypeError, ValueError) as error:
        if isinstance(error, SimulationApplicationError):
            _raise_simulation_error(error)
        raise ApiProblem(
            status_code=422,
            code="INVALID_LIMIT",
            message="simulation limit is invalid",
        ) from error
    return {
        "items": [_job_summary(view) for view in page.items],
        "nextCursor": page.next_cursor,
    }


@router.post("/jobs", status_code=202)
def create_job(
    body: SimulationCreateBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_mutating_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    if not idempotency_key or any(character.isspace() for character in idempotency_key):
        raise ApiProblem(
            status_code=422,
            code="IDEMPOTENCY_KEY_REQUIRED",
            message="Idempotency-Key is required",
        )
    if len(idempotency_key) > 128:
        raise ApiProblem(
            status_code=422,
            code="IDEMPOTENCY_KEY_INVALID",
            message="Idempotency-Key is invalid",
        )
    try:
        job = application.submit(
            principal,
            body.snapshot_id,
            body.scenario,
            idempotency_key,
        )
        return _job_detail(application.read_job(principal, job.id))
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _job_detail(application.read_job(principal, job_id))
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


__all__ = ["router"]
