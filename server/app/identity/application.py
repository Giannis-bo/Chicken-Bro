import base64
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import re
from _thread import LockType
from threading import Lock
from uuid import UUID, uuid4

from server.app.identity.domain import (
    IdentityConflictError,
    Principal,
    SessionKind,
    WebLoginSession,
    WebLoginSessionStatus,
    cancel_web_login_session,
    confirm_web_login_session,
    digest,
    consume_web_login_session,
    new_opaque_token,
)
from server.app.identity.ports import (
    IdentityRepository,
    WechatAdapterError,
    WechatMiniGateway,
    WechatNotConfiguredError,
)
from server.app.platform.config import AppSettings
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS


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


@dataclass(frozen=True)
class _QrCacheEntry:
    expires_at: datetime
    data_url: str


@dataclass
class _CreateLockEntry:
    lock: LockType
    users: int = 0


_BROWSER_VERIFIER = re.compile(r"[A-Za-z0-9_-]{43,128}\Z")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._~-]{8,128}\Z")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_MAX_QR_CACHE_ENTRIES = 256


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
        self._qr_cache: OrderedDict[UUID, _QrCacheEntry] = OrderedDict()
        self._qr_cache_lock = Lock()
        self._create_locks: dict[tuple[str, str], _CreateLockEntry] = {}
        self._create_locks_guard = Lock()

    def create_web_login(self, browser_verifier: str, *, idempotency_key: str) -> WebLoginCreated:
        self._validate_browser_verifier(browser_verifier)
        if not isinstance(idempotency_key, str) or _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise AuthApplicationError("VALIDATION_ERROR", "login request key is invalid")
        verifier_hash = digest(browser_verifier)
        idempotency_hash = digest(idempotency_key)
        lock_key = (verifier_hash, idempotency_hash)
        create_lock = self._retain_create_lock(lock_key)
        try:
            with create_lock:
                return self._create_web_login_locked(
                    verifier_hash=verifier_hash,
                    idempotency_hash=idempotency_hash,
                )
        finally:
            self._release_create_lock(lock_key)

    def _create_web_login_locked(
        self,
        *,
        verifier_hash: str,
        idempotency_hash: str,
    ) -> WebLoginCreated:
        now = self._now()
        existing = self._repository.get_web_login_session_by_idempotency(
            browser_verifier_sha256=verifier_hash,
            idempotency_key_sha256=idempotency_hash,
        )
        if existing is not None:
            qr_data_url = self._get_cached_qr(existing.id, now=now)
            if qr_data_url is None:
                raise AuthApplicationError(
                    "WEB_LOGIN_RESTART_REQUIRED",
                    "login QR must be regenerated",
                )
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
        if not isinstance(png, bytes):
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider returned invalid QR data")
        if png.startswith(_PNG_SIGNATURE):
            qr_mime = "image/png"
        elif png.startswith(_JPEG_SIGNATURE):
            qr_mime = "image/jpeg"
        else:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider returned invalid QR data")

        session = WebLoginSession(
            id=uuid4(),
            scene_ticket_sha256=digest(scene_ticket),
            browser_verifier_sha256=verifier_hash,
            user_id=None,
            status=WebLoginSessionStatus.PENDING,
            expires_at=now + timedelta(seconds=self._settings.web_login_ttl_seconds),
            consumed_at=None,
            idempotency_key_sha256=idempotency_hash,
        )
        if not self._repository.insert_web_login_session(session, now=now):
            concurrent = self._repository.get_web_login_session_by_idempotency(
                browser_verifier_sha256=verifier_hash,
                idempotency_key_sha256=idempotency_hash,
            )
            if concurrent is None:
                raise AuthApplicationError("INTERNAL_ERROR", "login session insert conflict is unresolved")
            raise AuthApplicationError(
                "WEB_LOGIN_RESTART_REQUIRED",
                "login QR must be regenerated",
            )
        qr_data_url = f"data:{qr_mime};base64," + base64.b64encode(png).decode("ascii")
        self._cache_qr(session.id, expires_at=session.expires_at, data_url=qr_data_url, now=now)
        return WebLoginCreated(session=session, qr_data_url=qr_data_url)

    def get_web_login_status(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView:
        self._validate_browser_verifier(browser_verifier)
        session = self._load_session(session_id)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session)
        return WebLoginStatusView(status=session.status, expires_at=session.expires_at)

    def confirm_mini_web_login(self, scene_ticket: str, principal: Principal) -> None:
        if principal.session_kind != "mini_bearer":
            raise AuthApplicationError("AUTH_REQUIRED", "mini-program authentication is required")
        if not isinstance(scene_ticket, str) or not 1 <= len(scene_ticket) <= 32 or any(character.isspace() for character in scene_ticket):
            raise AuthApplicationError("VALIDATION_ERROR", "login scene is invalid")
        now = self._now()
        scene_ticket_sha256 = digest(scene_ticket)
        if self._repository.confirm_web_login_session(
            scene_ticket_sha256=scene_ticket_sha256,
            user_id=principal.user_id,
            now=now,
        ):
            return
        session = self._repository.get_web_login_session_by_scene(
            scene_ticket_sha256=scene_ticket_sha256,
        )
        if session is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        session = self._expire_if_needed(session, now=now)
        if session.status is WebLoginSessionStatus.EXPIRED:
            raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        try:
            confirm_web_login_session(
                session,
                scene_ticket_sha256=scene_ticket_sha256,
                user_id=principal.user_id,
                now=now,
            )
        except ValueError as error:
            raise self._map_domain_error(error, confirm=True) from error
        raise AuthApplicationError("INTERNAL_ERROR", "login session transition failed")

    def exchange_web_login(self, session_id: UUID, browser_verifier: str) -> IssuedSession:
        self._validate_browser_verifier(browser_verifier)
        now = self._now()
        session = self._load_session(session_id)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session, now=now)
        if session.status is WebLoginSessionStatus.CONSUMED:
            raise AuthApplicationError("WEB_LOGIN_ALREADY_CONSUMED", "login session already consumed")
        if session.status is WebLoginSessionStatus.EXPIRED:
            raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        if session.status is WebLoginSessionStatus.CANCELLED:
            raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
        if session.status is not WebLoginSessionStatus.CONFIRMED or session.user_id is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_CONFIRMED", "login confirmation is required")
        try:
            consumed = consume_web_login_session(
                session,
                verifier_sha256=digest(browser_verifier),
                now=now,
            )
        except ValueError as error:
            raise self._map_domain_error(error) from error
        token = new_opaque_token()
        expires_at = now + timedelta(seconds=self._settings.web_session_ttl_seconds)
        resolved_user_id = self._repository.consume_web_login_session_and_issue_auth_session(
            session_id=consumed.id,
            browser_verifier_sha256=consumed.browser_verifier_sha256,
            expected_user_id=consumed.user_id,
            token_hash=digest(token),
            now=now,
            expires_at=expires_at,
        )
        if resolved_user_id is None:
            latest = self._load_session(session_id)
            latest = self._expire_if_needed(latest, now=now)
            if latest.status is WebLoginSessionStatus.CONSUMED:
                raise AuthApplicationError("WEB_LOGIN_ALREADY_CONSUMED", "login session already consumed")
            if latest.status is WebLoginSessionStatus.EXPIRED:
                raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
            if latest.status is WebLoginSessionStatus.CANCELLED:
                raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
            if latest.status is not WebLoginSessionStatus.CONFIRMED:
                raise AuthApplicationError("WEB_LOGIN_NOT_CONFIRMED", "login confirmation is required")
            raise AuthApplicationError("INTERNAL_ERROR", "login session transition failed")
        self._discard_cached_qr(session_id)
        return IssuedSession(
            token=token,
            expires_at=expires_at,
            principal=Principal(user_id=resolved_user_id, session_kind="web_cookie"),
        )

    def cancel_web_login(self, session_id: UUID, browser_verifier: str) -> WebLoginStatusView:
        self._validate_browser_verifier(browser_verifier)
        now = self._now()
        session = self._load_session(session_id)
        self._verify_browser_verifier(session, browser_verifier)
        session = self._expire_if_needed(session, now=now)
        if session.status is WebLoginSessionStatus.CONSUMED:
            raise AuthApplicationError("WEB_LOGIN_ALREADY_CONSUMED", "login session already consumed")
        if session.status is WebLoginSessionStatus.CANCELLED:
            raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
        if session.status is WebLoginSessionStatus.EXPIRED:
            raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
        try:
            cancelled = cancel_web_login_session(session, now=now)
        except ValueError as error:
            raise self._map_domain_error(error) from error
        if not self._repository.cancel_web_login_session(
            session_id=session.id,
            browser_verifier_sha256=session.browser_verifier_sha256,
            now=now,
        ):
            latest = self._load_session(session_id)
            latest = self._expire_if_needed(latest, now=now)
            if latest.status is WebLoginSessionStatus.CONSUMED:
                raise AuthApplicationError("WEB_LOGIN_ALREADY_CONSUMED", "login session already consumed")
            if latest.status is WebLoginSessionStatus.CANCELLED:
                raise AuthApplicationError("WEB_LOGIN_CANCELLED", "login session cancelled")
            if latest.status is WebLoginSessionStatus.EXPIRED:
                raise AuthApplicationError("WEB_LOGIN_EXPIRED", "login session expired")
            raise AuthApplicationError("INTERNAL_ERROR", "login session transition failed")
        self._discard_cached_qr(session.id)
        return WebLoginStatusView(status=cancelled.status, expires_at=cancelled.expires_at)

    def exchange_mini_code(self, code: str) -> IssuedSession:
        if (
            not isinstance(code, str)
            or not 1 <= len(code) <= 512
            or any(character.isspace() for character in code)
        ):
            raise AuthApplicationError("VALIDATION_ERROR", "WeChat authorization code is invalid")
        try:
            identity = self._wechat_gateway.exchange_code(code)
        except WechatNotConfiguredError:
            raise AuthApplicationError("WECHAT_NOT_CONFIGURED", "WeChat login is not configured") from None
        except WechatAdapterError:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from None
        except Exception as error:
            raise AuthApplicationError("WECHAT_PROVIDER_UNAVAILABLE", "WeChat login provider is unavailable") from error
        try:
            user_id = self._repository.upsert_wechat_mini_identity(
                app_context=self._settings.wechat_appid,
                provider_subject=identity.openid,
                union_id=identity.unionid,
                now=self._now(),
            )
        except IdentityConflictError as error:
            raise AuthApplicationError("IDENTITY_CONFLICT", "WeChat identity ownership conflicts") from error
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

    def exchange_test_account(self, account: str, credential: str, kind: SessionKind) -> IssuedSession:
        if not self._settings.test_login_enabled:
            raise AuthApplicationError("TEST_LOGIN_DISABLED", "test login is unavailable")
        expected = {"A": self._settings.test_login_a_sha256, "B": self._settings.test_login_b_sha256}
        if (account not in expected or kind not in {"mini_bearer", "web_cookie"}
                or not isinstance(credential, str) or not 32 <= len(credential) <= 256
                or not hmac.compare_digest(digest(credential), expected[account])):
            raise AuthApplicationError("AUTH_REQUIRED", "test credential is invalid")
        user_id = TEST_ACCOUNT_IDS[account]
        try:
            self._repository.ensure_test_user(user_id=user_id, display_name=f"测试账号 {account}", now=self._now())
        except IdentityConflictError:
            raise AuthApplicationError("IDENTITY_CONFLICT", "test account is unavailable") from None
        token = new_opaque_token()
        expires_at = self._now() + timedelta(seconds=min(self._settings.web_session_ttl_seconds, 86400))
        self._repository.issue_auth_session(token_hash=digest(token), user_id=user_id, kind=kind, expires_at=expires_at)
        return IssuedSession(token=token, expires_at=expires_at, principal=Principal(user_id=user_id, session_kind=kind))

    def resolve_principal(self, credential: str | None, kind: SessionKind) -> Principal | None:
        if not credential:
            return None
        principal = self._repository.resolve_auth_session(
            token_hash=digest(credential),
            kind=kind,
            now=self._now(),
        )
        if principal and principal.user_id in TEST_ACCOUNT_IDS.values() and not self._settings.test_login_enabled:
            return None
        return principal

    def me(self, principal: Principal) -> MeView:
        user = self._repository.get_public_user(principal.user_id)
        if user is None:
            raise AuthApplicationError("AUTH_REQUIRED", "authenticated user is unavailable")
        return MeView(
            connected=True,
            display_name=user.display_name or "已连接微信账号",
        )

    def avatar(self, principal: Principal) -> str | None:
        return self._repository.get_avatar(principal.user_id)

    def set_avatar(self, principal: Principal, data_url: str) -> str:
        from server.app.identity.avatar import normalize_avatar

        if principal.session_kind != "mini_bearer":
            raise AuthApplicationError("AVATAR_MINI_REQUIRED", "choose your avatar in the Mini Program")
        try:
            avatar = normalize_avatar(data_url)
        except ValueError as error:
            raise AuthApplicationError("AVATAR_INVALID", "choose a PNG or JPEG avatar up to 256 KB and 1024 pixels") from error
        if not self._repository.set_avatar(principal.user_id, avatar, now=self._now()):
            raise AuthApplicationError("AUTH_REQUIRED", "authenticated user is unavailable")
        return avatar

    def logout(self, principal: Principal, raw_credential: str | None) -> None:
        if raw_credential:
            self._repository.revoke_auth_session(
                token_hash=digest(raw_credential),
                kind=principal.session_kind,
                now=self._now(),
            )

    def _load_session(self, session_id: UUID) -> WebLoginSession:
        session = self._repository.get_web_login_session(session_id=session_id)
        if session is None:
            raise AuthApplicationError("WEB_LOGIN_NOT_FOUND", "login session not found")
        return session

    def _expire_if_needed(self, session: WebLoginSession, *, now: datetime | None = None) -> WebLoginSession:
        effective_now = now or self._now()
        if session.status in {WebLoginSessionStatus.PENDING, WebLoginSessionStatus.CONFIRMED} and effective_now >= session.expires_at:
            expired = WebLoginSession(
                id=session.id,
                scene_ticket_sha256=session.scene_ticket_sha256,
                browser_verifier_sha256=session.browser_verifier_sha256,
                user_id=session.user_id,
                status=WebLoginSessionStatus.EXPIRED,
                expires_at=session.expires_at,
                consumed_at=session.consumed_at,
                idempotency_key_sha256=session.idempotency_key_sha256,
            )
            if self._repository.expire_web_login_session(
                session_id=session.id,
                now=effective_now,
            ):
                self._discard_cached_qr(session.id)
                return expired
            latest = self._load_session(session.id)
            if latest.status in {
                WebLoginSessionStatus.CANCELLED,
                WebLoginSessionStatus.CONSUMED,
                WebLoginSessionStatus.EXPIRED,
            }:
                self._discard_cached_qr(session.id)
            return latest
        if session.status in {
            WebLoginSessionStatus.CANCELLED,
            WebLoginSessionStatus.CONSUMED,
            WebLoginSessionStatus.EXPIRED,
        }:
            self._discard_cached_qr(session.id)
        return session

    def _retain_create_lock(self, key: tuple[str, str]) -> LockType:
        with self._create_locks_guard:
            entry = self._create_locks.get(key)
            if entry is None:
                entry = _CreateLockEntry(lock=Lock())
                self._create_locks[key] = entry
            entry.users += 1
            return entry.lock

    def _release_create_lock(self, key: tuple[str, str]) -> None:
        with self._create_locks_guard:
            entry = self._create_locks[key]
            entry.users -= 1
            if entry.users == 0:
                del self._create_locks[key]

    def _get_cached_qr(self, session_id: UUID, *, now: datetime) -> str | None:
        with self._qr_cache_lock:
            entry = self._qr_cache.get(session_id)
            if entry is None:
                return None
            if now >= entry.expires_at:
                del self._qr_cache[session_id]
                return None
            self._qr_cache.move_to_end(session_id)
            return entry.data_url

    def _cache_qr(
        self,
        session_id: UUID,
        *,
        expires_at: datetime,
        data_url: str,
        now: datetime,
    ) -> None:
        with self._qr_cache_lock:
            expired_ids = [
                cached_session_id
                for cached_session_id, entry in self._qr_cache.items()
                if now >= entry.expires_at
            ]
            for expired_id in expired_ids:
                del self._qr_cache[expired_id]
            self._qr_cache[session_id] = _QrCacheEntry(expires_at=expires_at, data_url=data_url)
            self._qr_cache.move_to_end(session_id)
            while len(self._qr_cache) > _MAX_QR_CACHE_ENTRIES:
                self._qr_cache.popitem(last=False)

    def _discard_cached_qr(self, session_id: UUID) -> None:
        with self._qr_cache_lock:
            self._qr_cache.pop(session_id, None)

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
        if "already consumed" in message:
            return AuthApplicationError("WEB_LOGIN_ALREADY_CONSUMED", "login session already consumed")
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
