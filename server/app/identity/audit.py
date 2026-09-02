from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping, Protocol
from uuid import UUID

from server.app.identity.domain import SessionKind


_ALLOWED_PAYLOAD_KEYS = frozenset({
    "requestId",
    "sessionKind",
    "statusCode",
    "timestamp",
    "reasonCode",
})
_SENSITIVE_KEY = re.compile(
    r"token|cookie|openid|session[_-]?key|verifier|ticket|secret",
    re.IGNORECASE,
)
_REASON_CODE = re.compile(r"[A-Z0-9_]{1,64}\Z")


def validate_auth_audit_payload(payload: Mapping[str, object]) -> None:
    for key in payload:
        if _SENSITIVE_KEY.search(key):
            raise ValueError("auth audit payload contains a sensitive key")
    unknown = set(payload) - _ALLOWED_PAYLOAD_KEYS
    if unknown:
        raise ValueError("auth audit payload contains non-allowlisted keys")


class AuthAuditSink(Protocol):
    def record_auth_audit(self, event: "AuthAuditEvent") -> None: ...


class NullAuthAuditSink:
    def record_auth_audit(self, event: "AuthAuditEvent") -> None:
        event.payload()


@dataclass(frozen=True)
class AuthAuditEvent:
    event_type: str
    request_id: str
    user_id: UUID | None
    session_kind: SessionKind | None
    status_code: int
    timestamp: datetime
    reason_code: str

    def __post_init__(self) -> None:
        if not self.event_type or len(self.event_type) > 128:
            raise ValueError("auth audit event type is invalid")
        try:
            request_uuid = UUID(self.request_id)
        except (TypeError, ValueError) as error:
            raise ValueError("auth audit request ID is invalid") from error
        if str(request_uuid) != self.request_id:
            raise ValueError("auth audit request ID is invalid")
        if not 100 <= self.status_code <= 599:
            raise ValueError("auth audit status code is invalid")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("auth audit timestamp must be timezone-aware")
        if not _REASON_CODE.fullmatch(self.reason_code):
            raise ValueError("auth audit reason code is invalid")

    @property
    def subject_key(self) -> str:
        return self.request_id

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "requestId": self.request_id,
            "sessionKind": self.session_kind,
            "statusCode": self.status_code,
            "timestamp": self.timestamp.isoformat(),
            "reasonCode": self.reason_code,
        }
        validate_auth_audit_payload(payload)
        return payload
