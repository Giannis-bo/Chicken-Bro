import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import re
from uuid import UUID, uuid4

from server.app.identity.domain import (
    Principal,
    SessionKind,
    WebLoginSession,
    WebLoginSessionStatus,
    cancel_web_login_session,
    confirm_web_login_session,
    digest,
    exchange_web_login_session,
    new_opaque_token,
)
from server.app.identity.ports import IdentityRepository, WechatMiniGateway
from server.app.integrations.wechat_mini import WechatAdapterError, WechatNotConfiguredError
from server.app.platform.config import AppSettings


class AuthApplicationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IssuedSession:
    token: str
    expires_at: datetime
    principal: Principal


@dataclass(frozen=True)
class WebLoginCreated:
    session: WebLoginSession
    qr_data_url: str


@dataclass(frozen=True)
class WebLoginStatusView:
    status: WebLoginSessionStatus
    expires_at: datetime


@dataclass(frozen=True)
class MeView:
    connected: bool
    display_name: str


_BROWSER_VERIFIER = re.compile(r"[A-Za-z0-9_-]{43,128}\Z")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._~-]{8,128}\Z")


class WebAuthApplication:
    def __init__(
        self,
        *,
        repository: IdentityRepository,
        wechat_gateway: WechatMiniGateway,
        settings: AppSettings,
        clock: Callable[[], datetime] | None = None,
    ):
        self._repository = repository
        self._wechat_gateway = wechat_gateway
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._qr_cache: dict[UUID, str] = {}

    def create_web_login(self, browser_verifier: str, *, idempotency_key: str) -> WebLoginCreated:
        self._validate_browser_verifier(browser_verifier)
        if not isinstance(idempotency_key, str) or _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise AuthApplicationError("VALIDATION_ERROR", "login request key is invalid")
        now = self._now()
        verifier_hash = digest(browser_verifier)
        idempotency_hash = digest(idempotency_key)
        existing = self._repository.get_web_login_session_by_idempotency(
            browser_verifier_sha256=verifier_hash,
            idempotency_key_sha256=idempotency_hash,
            for_update=False,
        )
        if existing is not None and now < existing.expires_at:
            qr_data_url = self._qr_cache.get(existing.id)
            if qr_data_url is None:
                raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "login QR is temporarily unavailable")
            return WebLoginCreated(session=existing, qr_data_url=qr_data_url)

        scene_ticket = new_opaque_token(16)
        try:
            png = self._wechat_gateway.create_mini_code(
                scene=scene_ticket,
                page=self._settings.wechat_page,
                env_version=self._settings.wechat_env_version,
            )
        except WechatNotConfiguredError:
            raise AuthApplicationError("WECHAT_NOT_CONFIGURED", "WeChat login is not configured") from None
        except WechatAdapterError:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from None
        except Exception as error:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from error
        if not isinstance(png, bytes) or not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider returned invalid QR data")

        session = WebLoginSession(
            id=uuid4(),
            scene_ticket_sha256=digest(scene_ticket),
            browser_verifier_sha256=verifier_hash,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now + timedelta(seconds=self._settings.web_login_ttl_seconds),
            exchanged_at=None,
            idempotency_key_sha256=idempotency_hash,
        )
        self._repository.insert_web_login_session(session, now=now)
        qr_data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        self._qr_cache[session.id] = qr_data_url
        return WebLoginCreated(session=session, qr_data_url=qr_data_url)

    def get_web_login_status(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView:
        self._validate_browser_verifier(browser_verifier)
        session = self._load_session(session_id, for_update=True)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session)
        return WebLoginStatusView(status=session.status, expires_at=session.expires_at)

    def confirm_mini_web_login(self, scene_ticket: str, principal: Principal) -> None:
        if principal.session_kind != "mini_bearer":
            raise AuthApplicationError("AUTH_REQUIRED", "mini-program authentication is required")
        if not isinstance(scene_ticket, str) or not 1 <= len(scene_ticket) <= 32 or any(character.isspace() for character in scene_ticket):
            raise AuthApplicationError("VALIDATION_ERROR", "login scene is invalid")
        session = self._repository.get_web_login_session_by_scene(
            scene_ticket_sha256=digest(scene_ticket),
            for_update=True,
        )
        if session is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        session = self._expire_if_needed(session)
        if session.status is WebLoginSessionStatus.EXPIRED:
            raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        try:
            confirmed = confirm_web_login_session(
                session,
                scene_ticket_sha256=digest(scene_ticket),
                user_id=principal.user_id,
                now=self._now(),
            )
        except ValueError as error:
            raise self._map_domain_error(error, confirm=True) from error
        self._repository.save_web_login_session(confirmed, now=self._now())

    def exchange_web_login(self, session_id: UUID, browser_verifier: str) -> IssuedSession:
        self._validate_browser_verifier(browser_verifier)
        session = self._load_session(session_id, for_update=True)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session)
        if session.status is WebLoginSessionStatus.EXCHANGED:
            raise AuthApplicationError("WEB_LOGIN_ALREADY_EXCHANGED", "login session already exchanged")
        if session.status is WebLoginSessionStatus.EXPIRED:
            raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        if session.status is WebLoginSessionStatus.CANCELLED:
            raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
        if session.status is not WebLoginSessionStatus.CONFIRMED or session.user_id is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_CONFIRMED", "login confirmation is required")
        try:
            exchanged = exchange_web_login_session(
                session,
                verifier_sha256=digest(browser_verifier),
                now=self._now(),
            )
        except ValueError as error:
            raise self._map_domain_error(error) from error
        token = new_opaque_token()
        expires_at = self._now() + timedelta(seconds=self._settings.web_session_ttl_seconds)
        self._repository.save_web_login_session(exchanged, now=self._now())
        self._repository.issue_auth_session(
            token_hash=digest(token),
            user_id=exchanged.user_id,
            kind="web_cookie",
            expires_at=expires_at,
        )
        return IssuedSession(
            token=token,
            expires_at=expires_at,
            principal=Principal(user_id=exchanged.user_id, session_kind="web_cookie"),
        )

    def cancel_web_login(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView:
        self._validate_browser_verifier(browser_verifier)
        session = self._load_session(session_id, for_update=True)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session)
        if session.status is WebLoginSessionStatus.EXCHANGED:
            raise AuthApplicationError("WEB_LOGIN_ALREADY_EXCHANGED", "login session already exchanged")
        if session.status is WebLoginSessionStatus.CANCELLED:
            raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
        try:
            cancelled = cancel_web_login_session(session, now=self._now())
        except ValueError as error:
            raise self._map_domain_error(error) from error
        self._repository.save_web_login_session(cancelled, now=self._now())
        return WebLoginStatusView(status=cancelled.status, expires_at=cancelled.expires_at)

    def exchange_mini_code(self, code: str) -> IssuedSession:
        try:
            identity = self._wechat_gateway.exchange_code(code)
        except WechatNotConfiguredError:
            raise AuthApplicationError("WECHAT_NOT_CONFIGURED", "WeChat login is not configured") from None
        except WechatAdapterError:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from None
        except Exception as error:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from error
        user_id = self._repository.upsert_wechat_mini_identity(
            provider_subject=identity.openid,
            now=self._now(),
        )
        token = new_opaque_token()
        expires_at = self._now() + timedelta(seconds=min(self._settings.web_session_ttl_seconds, 86400))
        self._repository.issue_auth_session(
            token_hash=digest(token),
            user_id=user_id,
            kind="mini_bearer",
            expires_at=expires_at,
        )
        return IssuedSession(
            token=token,
            expires_at=expires_at,
            principal=Principal(user_id=user_id, session_kind="mini_bearer"),
        )

    def resolve_principal(self, credential: str | None, kind: SessionKind) -> Principal | None:
        if not credential:
            return None
        return self._repository.resolve_auth_session(
            token_hash=digest(credential),
            kind=kind,
            now=self._now(),
        )

    def me(self, principal: Principal) -> MeView:
        user = self._repository.get_public_user(principal.user_id)
        if user is None:
            raise AuthApplicationError("AUTH_REQUIRED", "authenticated user is unavailable")
        return MeView(
            connected=True,
            display_name=user.display_name or "已连接微信账号",
        )

    def logout(self, principal: Principal, raw_cookie: str | None) -> None:
        if principal.session_kind != "web_cookie":
            raise AuthApplicationError("AUTH_REQUIRED", "Web authentication is required")
        if raw_cookie:
            self._repository.revoke_auth_session(
                token_hash=digest(raw_cookie),
                kind="web_cookie",
                now=self._now(),
            )

    def _load_session(self, session_id: UUID, *, for_update: bool) -> WebLoginSession:
        session = self._repository.get_web_login_session(session_id=session_id, for_update=for_update)
        if session is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        return session

    def _expire_if_needed(self, session: WebLoginSession) -> WebLoginSession:
        if session.status in {WebLoginSessionStatus.PENDING, WebLoginSessionStatus.CONFIRMED} and self._now() >= session.expires_at:
            expired = WebLoginSession(
                id=session.id,
                scene_ticket_sha256=session.scene_ticket_sha256,
                browser_verifier_sha256=session.browser_verifier_sha256,
                user_id=session.user_id,
                status=WebLoginSessionStatus.EXPIRED,
                expires_at=session.expires_at,
                exchanged_at=session.exchanged_at,
                idempotency_key_sha256=session.idempotency_key_sha256,
            )
            self._repository.save_web_login_session(expired, now=self._now())
            return expired
        return session

    @staticmethod
    def _validate_browser_verifier(browser_verifier: str) -> None:
        if not isinstance(browser_verifier, str) or _BROWSER_VERIFIER.fullmatch(browser_verifier) is None:
            raise AuthApplicationError("VALIDATION_ERROR", "browser verifier is invalid")

    @staticmethod
    def _verify_browser_verifier(session: WebLoginSession, browser_verifier: str) -> None:
        if not hmac.compare_digest(digest(browser_verifier), session.browser_verifier_sha256):
            raise AuthApplicationError("WEB_LOGIN_VERIFIER_MISMATCH", "browser verifier does not match")

    @staticmethod
    def _map_domain_error(error: ValueError, *, confirm: bool = False) -> AuthApplicationError:
        message = str(error)
        if "already exchanged" in message:
            return AuthApplicationError("WEB_LOGIN_ALREADY_EXCHANGED", "login session already exchanged")
        if "expired" in message:
            return AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        if "cancel" in message:
            return AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
        if "not confirmed" in message or "not pending" in message:
            return AuthApplicationError("WEB_LOGIN_NOT_CONFIRMED", "login confirmation is required")
        if "scene ticket" in message:
            return AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        if confirm:
            return AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        return AuthApplicationError("INTERNAL_ERROR", "login session transition failed")

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
