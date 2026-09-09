from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from server.app.identity.domain import Principal, SessionKind, WebLoginSession


@dataclass(frozen=True)
class PublicUser:
    user_id: UUID
    display_name: str


@dataclass(frozen=True)
class WechatIdentity:
    openid: str
    unionid: str | None = None


class WechatAdapterError(RuntimeError):
    """Provider-port failure that the application can map without importing an adapter."""


class WechatNotConfiguredError(WechatAdapterError):
    pass


class WechatProviderError(WechatAdapterError):
    pass


class IdentityRepository(Protocol):
    def ensure_test_user(self, *, user_id: UUID, display_name: str, now: datetime) -> None: ...

    def upsert_wechat_mini_identity(
        self,
        *,
        app_context: str,
        provider_subject: str,
        union_id: str | None,
        now: datetime,
    ) -> UUID:
        raise NotImplementedError

    def issue_auth_session(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        kind: SessionKind,
        expires_at: datetime,
    ) -> None:
        raise NotImplementedError

    def consume_web_login_session_and_issue_auth_session(
        self,
        *,
        session_id: UUID,
        browser_verifier_sha256: str,
        expected_user_id: UUID,
        token_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> UUID | None:
        """Atomically consume one confirmed login and issue its Web credential."""
        raise NotImplementedError

    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None:
        raise NotImplementedError

    def revoke_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> None:
        raise NotImplementedError

    def insert_web_login_session(self, session: WebLoginSession, *, now: datetime) -> bool:
        """Insert once, returning false when a concurrent unique insert won."""
        raise NotImplementedError

    def confirm_web_login_session(
        self,
        *,
        scene_ticket_sha256: str,
        user_id: UUID,
        now: datetime,
    ) -> bool:
        """Claim a live pending QR ticket exactly once."""
        raise NotImplementedError

    def cancel_web_login_session(
        self,
        *,
        session_id: UUID,
        browser_verifier_sha256: str,
        now: datetime,
    ) -> bool:
        """Cancel a verifier-bound live ticket without overwriting terminal state."""
        raise NotImplementedError

    def expire_web_login_session(self, *, session_id: UUID, now: datetime) -> bool:
        """Advance an overdue live ticket without overwriting terminal state."""
        raise NotImplementedError

    def get_web_login_session(self, *, session_id: UUID) -> WebLoginSession | None:
        raise NotImplementedError

    def get_web_login_session_by_scene(
        self,
        *,
        scene_ticket_sha256: str,
    ) -> WebLoginSession | None:
        raise NotImplementedError

    def get_web_login_session_by_idempotency(
        self,
        *,
        browser_verifier_sha256: str,
        idempotency_key_sha256: str,
    ) -> WebLoginSession | None:
        raise NotImplementedError

    def get_avatar(self, user_id: UUID) -> str | None:
        ...

    def set_avatar(self, user_id: UUID, avatar: str, *, now: datetime) -> bool:
        ...

    def get_public_user(self, user_id: UUID) -> PublicUser | None:
        raise NotImplementedError

class WechatMiniGateway(Protocol):
    def exchange_code(self, code: str) -> WechatIdentity:
        raise NotImplementedError

    def create_mini_code(self, *, scene: str, page: str, env_version: str) -> bytes:
        raise NotImplementedError


@dataclass(frozen=True)
class QqIdentity:
    client_id: str
    openid: str
    profile: dict = field(default_factory=dict)


class QqProviderError(RuntimeError):
    """Sanitized provider failure; never attach response bodies or request URLs."""


class QqGateway(Protocol):
    def authorization_url(self, state: str) -> str: ...
    def exchange_code(self, code: str) -> QqIdentity: ...


class QqIdentityRepository(Protocol):
    def insert_qq_login_attempt(self, *, state_hash: str, browser_hash: str, expires_at: datetime, now: datetime) -> None: ...
    def consume_qq_login_attempt(self, *, state_hash: str, browser_hash: str, now: datetime) -> bool: ...
    def upsert_qq_identity(self, *, appid: str, openid: str, profile: dict, now: datetime) -> UUID: ...
    def has_qq_identity(self, *, user_id: UUID, appid: str) -> bool: ...
    def get_qq_profile(self, *, user_id: UUID, appid: str) -> dict: ...
    def issue_auth_session(self, *, token_hash: str, user_id: UUID, kind: SessionKind, expires_at: datetime) -> None: ...
    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None: ...
    def revoke_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> None: ...
    def get_public_user(self, user_id: UUID) -> PublicUser | None: ...
    def get_avatar(self, user_id: UUID) -> str | None: ...
    def ensure_test_user(self, *, user_id: UUID, display_name: str, now: datetime) -> None: ...
