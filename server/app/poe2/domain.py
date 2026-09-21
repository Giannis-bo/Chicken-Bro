from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping
from uuid import UUID


class Poe2JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Poe2Build:
    id: UUID
    user_id: UUID
    title: str
    source_xml: str
    game_version: str
    league: str
    input_sha256: str
    engine_version: str
    export_code: str
    summary: Mapping[str, object]
    created_at: datetime


@dataclass(frozen=True)
class Poe2Job:
    id: UUID
    user_id: UUID
    build_id: UUID
    idempotency_key: str
    request_hash: str
    changes: Mapping[str, object]
    status: Poe2JobStatus
    result: Mapping[str, object] | None
    public_error_code: str
    attempt_count: int
    lease_owner: str
    lease_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
