import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol
from uuid import UUID, uuid4

from server.app.identity.domain import digest, new_opaque_token


PrototypeSessionKind = Literal["prototype"]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class PrototypePrincipal:
    """The internal owner bound to one short-lived Web prototype capability."""

    user_id: UUID
    session_id: UUID
    session_kind: PrototypeSessionKind = "prototype"


@dataclass(frozen=True)
class PrototypeSession:
    """Persistable prototype session; the raw capability never becomes domain data."""

    id: UUID
    user_id: UUID
    token_sha256: str
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.token_sha256) is None:
            raise ValueError("prototype token must be a lowercase SHA-256 digest")
        if self.expires_at.tzinfo is None:
            raise ValueError("prototype session expiry must be timezone-aware")


@dataclass(frozen=True)
class PrototypeSessionIssued:
    session: PrototypeSession
    token: str
    principal: PrototypePrincipal


class PrototypeIdentityRepository(Protocol):
    def create_prototype_user(self, *, user_id: UUID, now: datetime) -> None:
        raise NotImplementedError

    def insert_prototype_session(self, session: PrototypeSession, *, now: datetime) -> None:
        raise NotImplementedError

    def get_prototype_session_by_token_hash(
        self,
        *,
        token_sha256: str,
        for_update: bool = False,
    ) -> PrototypeSession | None:
        raise NotImplementedError

    def get_prototype_session(
        self,
        *,
        session_id: UUID,
        for_update: bool = False,
    ) -> PrototypeSession | None:
        raise NotImplementedError

    def save_prototype_session(self, session: PrototypeSession, *, now: datetime) -> None:
        raise NotImplementedError


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def issue_prototype_session(
    *,
    user_id: UUID,
    session_id: UUID,
    now: datetime,
    ttl: timedelta,
) -> PrototypeSessionIssued:
    if ttl <= timedelta(0):
        raise ValueError("prototype session ttl must be positive")
    issued_at = _utc(now)
    token = new_opaque_token(32)
    session = PrototypeSession(
        id=session_id,
        user_id=user_id,
        token_sha256=digest(token),
        expires_at=issued_at + ttl,
    )
    return PrototypeSessionIssued(
        session=session,
        token=token,
        principal=PrototypePrincipal(user_id=user_id, session_id=session_id),
    )


def resolve_prototype_principal(
    session: PrototypeSession,
    token: str,
    *,
    now: datetime,
) -> PrototypePrincipal | None:
    if not isinstance(token, str) or not token or session.revoked_at is not None:
        return None
    if _utc(now) >= session.expires_at:
        return None
    if not hmac.compare_digest(digest(token), session.token_sha256):
        return None
    return PrototypePrincipal(user_id=session.user_id, session_id=session.id)


def revoke_prototype_session(session: PrototypeSession, *, now: datetime) -> PrototypeSession:
    if session.revoked_at is not None:
        return session
    return replace(session, revoked_at=_utc(now))


class PrototypeIdentityApplication:
    def __init__(
        self,
        *,
        repository: PrototypeIdentityRepository,
        ttl: timedelta,
        clock: Callable[[], datetime] | None = None,
    ):
        if ttl <= timedelta(0):
            raise ValueError("prototype session ttl must be positive")
        self._repository = repository
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_session(self) -> PrototypeSessionIssued:
        now = _utc(self._clock())
        issued = issue_prototype_session(
            user_id=uuid4(),
            session_id=uuid4(),
            now=now,
            ttl=self._ttl,
        )
        self._repository.create_prototype_user(user_id=issued.session.user_id, now=now)
        self._repository.insert_prototype_session(issued.session, now=now)
        return issued

    def resolve(self, token: str) -> PrototypePrincipal | None:
        if not isinstance(token, str) or not token or len(token) > 512:
            return None
        session = self._repository.get_prototype_session_by_token_hash(
            token_sha256=digest(token),
            for_update=False,
        )
        if session is None:
            return None
        return resolve_prototype_principal(session, token, now=_utc(self._clock()))

    def revoke(self, principal: PrototypePrincipal) -> None:
        session = self._repository.get_prototype_session(
            session_id=principal.session_id,
            for_update=True,
        )
        if session is None or session.user_id != principal.user_id:
            return
        self._repository.save_prototype_session(
            revoke_prototype_session(session, now=_utc(self._clock())),
            now=_utc(self._clock()),
        )


__all__ = (
    "PrototypePrincipal",
    "PrototypeSession",
    "PrototypeSessionIssued",
    "PrototypeIdentityRepository",
    "PrototypeIdentityApplication",
    "issue_prototype_session",
    "resolve_prototype_principal",
    "revoke_prototype_session",
)
