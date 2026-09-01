import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID


SessionKind = Literal["mini_bearer", "web_cookie"]


@dataclass(frozen=True)
class Principal:
    """Authenticated internal identity; provider subjects stay outside the domain object."""

    user_id: UUID
    session_kind: SessionKind


class WebLoginSessionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXCHANGED = "exchanged"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_opaque_token(byte_length: int = 32) -> str:
    if byte_length < 16:
        raise ValueError("opaque token length must be at least 16 bytes")
    return secrets.token_urlsafe(byte_length)


@dataclass(frozen=True)
class WebLoginSession:
    """One browser-bound, mini-program-confirmed web login attempt.

    Only digests are held here. Raw scene tickets and browser verifiers stay
    in the transport/application boundary and never become domain data.
    """

    id: UUID
    scene_ticket_sha256: str
    browser_verifier_sha256: str
    user_id: UUID | None
    status: WebLoginSessionStatus
    expires_at: datetime
    exchanged_at: datetime | None
    idempotency_key_sha256: str | None = None

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.scene_ticket_sha256) is None:
            raise ValueError("scene ticket must be a lowercase SHA-256 digest")
        if _SHA256.fullmatch(self.browser_verifier_sha256) is None:
            raise ValueError("browser verifier must be a lowercase SHA-256 digest")
        if self.idempotency_key_sha256 is not None and _SHA256.fullmatch(self.idempotency_key_sha256) is None:
            raise ValueError("idempotency key must be a lowercase SHA-256 digest")
        if self.status is WebLoginSessionStatus.CONFIRMED and self.user_id is None:
            raise ValueError("confirmed web login session requires a user")
        if self.status is WebLoginSessionStatus.EXCHANGED:
            if self.user_id is None:
                raise ValueError("exchanged web login session requires a user")
            if self.exchanged_at is None:
                raise ValueError("exchanged web login session requires exchange time")


def confirm_web_login_session(
    session: WebLoginSession,
    *,
    scene_ticket_sha256: str,
    user_id: UUID,
    now: datetime,
) -> WebLoginSession:
    if session.status is not WebLoginSessionStatus.PENDING:
        raise ValueError("web login session is not pending")
    if now >= session.expires_at:
        raise ValueError("web login session expired")
    if not hmac.compare_digest(scene_ticket_sha256, session.scene_ticket_sha256):
        raise ValueError("scene ticket does not match")
    return replace(
        session,
        user_id=user_id,
        status=WebLoginSessionStatus.CONFIRMED,
    )


def exchange_web_login_session(
    session: WebLoginSession,
    *,
    verifier_sha256: str,
    now: datetime,
) -> WebLoginSession:
    if session.status is WebLoginSessionStatus.EXCHANGED:
        raise ValueError("web login session already exchanged")
    if session.status is not WebLoginSessionStatus.CONFIRMED:
        raise ValueError("web login session is not confirmed")
    if now >= session.expires_at:
        raise ValueError("web login session expired")
    if not hmac.compare_digest(verifier_sha256, session.browser_verifier_sha256):
        raise ValueError("browser verifier does not match")
    return replace(
        session,
        status=WebLoginSessionStatus.EXCHANGED,
        exchanged_at=now,
    )


def cancel_web_login_session(
    session: WebLoginSession,
    *,
    now: datetime,
) -> WebLoginSession:
    if session.status not in {
        WebLoginSessionStatus.PENDING,
        WebLoginSessionStatus.CONFIRMED,
    }:
        raise ValueError("web login session cannot be cancelled")
    if now >= session.expires_at:
        return replace(session, status=WebLoginSessionStatus.EXPIRED)
    return replace(session, status=WebLoginSessionStatus.CANCELLED)
