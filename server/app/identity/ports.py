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


class PrincipalResolver(Protocol):
    def resolve(self, credential: str) -> Principal | None:
        raise NotImplementedError


class IdentityRepository(Protocol):
    def get_user(self, user_id: UUID) -> Principal | None:
        raise NotImplementedError

    def upsert_wechat_mini_identity(self, *, provider_subject: str, now: datetime) -> UUID:
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

    def resolve_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> Principal | None:
        raise NotImplementedError

    def revoke_auth_session(self, *, token_hash: str, kind: SessionKind, now: datetime) -> None:
        raise NotImplementedError

    def insert_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None:
        raise NotImplementedError

    def get_web_login_session(self, *, session_id: UUID, for_update: bool = False) -> WebLoginSession | None:
        raise NotImplementedError

    def get_web_login_session_by_scene(
        self,
        *,
        scene_ticket_sha256: str,
        for_update: bool = False,
    ) -> WebLoginSession | None:
        raise NotImplementedError

    def get_web_login_session_by_idempotency(
        self,
        *,
        browser_verifier_sha256: str,
        idempotency_key_sha256: str,
        for_update: bool = False,
    ) -> WebLoginSession | None:
        raise NotImplementedError

    def save_web_login_session(self, session: WebLoginSession, *, now: datetime) -> None:
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
