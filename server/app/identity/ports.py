from dataclasses import dataclass
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


class PrincipalResolver(Protocol):
    def resolve(self, credential: str) -> Principal | None:
        raise NotImplementedError


class IdentityRepository(Protocol):
    def get_user(self, user_id: UUID) -> Principal | None:
        raise NotImplementedError

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

    def get_public_user(self, user_id: UUID) -> PublicUser | None:
        raise NotImplementedError


class WebLoginSessionRepository(Protocol):
    def get(self, session_id: UUID) -> WebLoginSession | None:
        raise NotImplementedError

    def save(self, session: WebLoginSession) -> None:
        raise NotImplementedError


class WechatMiniGateway(Protocol):
    def exchange_code(self, code: str) -> WechatIdentity:
        raise NotImplementedError

    def create_mini_code(self, *, scene: str, page: str, env_version: str) -> bytes:
        raise NotImplementedError
