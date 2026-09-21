from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID


class SourceProvider(str, Enum):
    WEGAME = "wegame"
    NINJA = "ninja"


class ImportStatus(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"
    MAPPING = "mapping"
    VALIDATING = "validating"
    READY = "ready"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class SourceRef:
    provider: SourceProvider
    canonical_url: str
    account: str | None = None
    league: str | None = None
    character: str | None = None
    share_id: str | None = None


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    severity: IssueSeverity
    message: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.code, str)
            or not self.code
            or not isinstance(self.path, str)
            or not isinstance(self.severity, IssueSeverity)
            or not isinstance(self.message, str)
            or not self.message
        ):
            raise ValueError("POE2_IMPORT_ISSUE_INVALID")


# Descriptive alias for callers that keep several issue domains in one module.
ImportIssue = Issue


@dataclass(frozen=True)
class ImportPacket:
    id: UUID
    status: ImportStatus
    provider: SourceProvider
    preview: Mapping[str, object] | None
    issues: tuple[Issue, ...]
    next_action: str | None
    build_id: UUID | None
    baseline_job_id: UUID | None
    attempt: int
    updated_at: datetime

    def __post_init__(self) -> None:
        valid = (
            isinstance(self.id, UUID)
            and isinstance(self.status, ImportStatus)
            and isinstance(self.provider, SourceProvider)
            and (self.preview is None or isinstance(self.preview, Mapping))
            and isinstance(self.issues, tuple)
            and all(isinstance(issue, Issue) for issue in self.issues)
            and (self.next_action is None or isinstance(self.next_action, str))
            and (self.build_id is None or isinstance(self.build_id, UUID))
            and (
                self.baseline_job_id is None
                or isinstance(self.baseline_job_id, UUID)
            )
            and isinstance(self.attempt, int)
            and not isinstance(self.attempt, bool)
            and self.attempt >= 0
            and isinstance(self.updated_at, datetime)
            and self.updated_at.tzinfo is not None
            and self.updated_at.utcoffset() is not None
        )
        if not valid:
            raise ValueError("POE2_IMPORT_PACKET_INVALID")
        if self.status is ImportStatus.READY and (
            self.build_id is None or self.baseline_job_id is None
        ):
            raise ValueError("POE2_IMPORT_READY_RESULT_REQUIRED")
        if self.preview is not None:
            object.__setattr__(self, "preview", MappingProxyType(dict(self.preview)))
