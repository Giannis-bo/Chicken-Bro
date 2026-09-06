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
    validated_simulation_result_provenance,
    public_simulation_report,
    public_simulation_metric_error,
)
from server.app.simulation.domain import SimulationAttempt, SourceSnapshot


router = APIRouter(prefix="/api/v2/simc")
_SAFE_CODE = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")


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


def _character_payload(snapshot: SourceSnapshot | None) -> dict[str, object] | None:
    raw = snapshot.snapshot.get("character") if snapshot is not None else None
    if not isinstance(raw, Mapping):
        return None
    def text(key):
        value = raw.get(key)
        return value[:160] if isinstance(value, str) else ""
    return {"name": text("name"), "className": text("classKey"),
            "specialization": text("specKey"), "race": text("raceKey"),
            "level": raw.get("level") if type(raw.get("level")) is int and 0 < raw["level"] <= 1000 else None}


def _snapshot_payload(snapshot: SourceSnapshot, workbench: bool = False) -> dict[str, object]:
    raw_snapshot = snapshot.snapshot if isinstance(snapshot.snapshot, Mapping) else {}
    source_revision = str(snapshot.provenance.get("sourceRevision") or "").strip()
    if len(source_revision) > 160:
        source_revision = ""
    return {
        "id": str(snapshot.id),
        **({"character": _character_payload(snapshot)} if workbench else {}),
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


def _job_summary(view: SimulationJobView, workbench: bool = False) -> dict[str, object]:
    validated_simulation_result_provenance(view)
    job = view.job
    public_error = str(job.public_error_code or "")
    if public_error and _SAFE_CODE.fullmatch(public_error) is None:
        public_error = "SIMC_FAILED"
    return {
        "id": str(job.id),
        **({"character": _character_payload(view.snapshot), "scenario": view.scenario,
            "metric": {"name": view.result.primary_metric_name, "value": view.result.primary_metric_value} if view.result else None} if workbench else {}),
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


def _result_payload(view: SimulationJobView, workbench: bool = False) -> dict[str, object] | None:
    provenance = validated_simulation_result_provenance(view)
    result = view.result
    if result is None:
        return None
    if provenance is None:
        raise SimulationApplicationError("SIMC_RESULT_INVALID", "simulation result is invalid")
    return {
        "id": str(result.id),
        "profileSha256": result.profile_sha256,
        **({"report": public_simulation_report(view), "metricError": public_simulation_metric_error(view)} if workbench else {}),
        "metricName": result.primary_metric_name,
        "metricValue": result.primary_metric_value,
        "compilerRevision": result.compiler_revision,
        "runtimeRevision": result.runtime_revision,
        "provenance": provenance,
        "createdAt": _iso(result.created_at),
    }


def _job_detail(view: SimulationJobView, workbench: bool = False) -> dict[str, object]:
    return {
        **_job_summary(view, workbench),
        "attempts": [_attempt_payload(attempt) for attempt in view.attempts[:20]],
        "result": _result_payload(view, workbench),
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


@router.get("/runtime")
def runtime_info(
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    return application.runtime_info(principal)


@router.post("/snapshots", status_code=201)
def create_snapshot(
    body: SourceSnapshotCreateBody,
    view: str | None = None,
    principal: Principal = Depends(require_mutating_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _snapshot_payload(application.resolve_source(principal, body.source_url), view == "workbench")
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(
    snapshot_id: UUID,
    view: str | None = None,
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _snapshot_payload(application.read_snapshot(principal, snapshot_id), view == "workbench")
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/jobs")
def list_jobs(
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
    view: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    try:
        page = application.list_jobs(principal, cursor, limit)
        return {
            "items": [_job_summary(item, view == "workbench") for item in page.items],
            "nextCursor": page.next_cursor,
        }
    except (SimulationApplicationError, TypeError, ValueError) as error:
        if isinstance(error, SimulationApplicationError):
            _raise_simulation_error(error)
        raise ApiProblem(
            status_code=422,
            code="INVALID_LIMIT",
            message="simulation limit is invalid",
        ) from error


@router.post("/jobs", status_code=202)
def create_job(
    body: SimulationCreateBody,
    view: str | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_mutating_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        job = application.submit(
            principal,
            body.snapshot_id,
            body.scenario,
            idempotency_key or "",
        )
        return _job_detail(application.read_job(principal, job.id), view == "workbench")
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    view: str | None = None,
    principal: Principal = Depends(require_principal),
    application: SimulationApplication = Depends(simulation_application),
) -> dict[str, object]:
    try:
        return _job_detail(application.read_job(principal, job_id), view == "workbench")
    except SimulationApplicationError as error:
        _raise_simulation_error(error)


__all__ = ["router"]
