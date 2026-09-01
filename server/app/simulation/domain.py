from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class SourceProvider(str, Enum):
    RAIDERIO = "raiderio"
    WARCRAFTLOGS = "warcraftlogs"


class SourceReadiness(str, Enum):
    INVALID_LINK = "INVALID_LINK"
    CHARACTER_NOT_FOUND = "CHARACTER_NOT_FOUND"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    SNAPSHOT_UNAVAILABLE = "SNAPSHOT_UNAVAILABLE"
    INCOMPLETE_FOR_SIMC = "INCOMPLETE_FOR_SIMC"
    READY_FOR_SIMC = "READY_FOR_SIMC"


class SimulationJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SourceSnapshot:
    id: UUID
    user_id: UUID
    provider: SourceProvider
    source_url: str
    source_key: str
    revision: int
    readiness: SourceReadiness
    snapshot: Mapping[str, object]
    provenance: Mapping[str, object]
    raw_sha256: str
    fetched_at: datetime


@dataclass(frozen=True)
class SimulationJob:
    id: UUID
    user_id: UUID
    snapshot_id: UUID
    scenario_hash: str
    compiler_revision: str
    runtime_revision: str
    idempotency_key: str
    status: SimulationJobStatus
    public_error_code: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SimulationResult:
    id: UUID
    job_id: UUID
    user_id: UUID
    profile_sha256: str
    result: Mapping[str, object]
    primary_metric_name: str
    primary_metric_value: float
    compiler_revision: str
    runtime_revision: str
    created_at: datetime


def transition_simulation_job(
    current: SimulationJobStatus,
    target: SimulationJobStatus,
) -> SimulationJobStatus:
    legal = {
        SimulationJobStatus.QUEUED: {
            SimulationJobStatus.RUNNING,
            SimulationJobStatus.CANCELLED,
        },
        SimulationJobStatus.RUNNING: {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        },
    }
    if target not in legal.get(current, set()):
        raise ValueError("illegal simulation job transition")
    return target
