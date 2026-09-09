"""QQ-only Web identity application; legacy WeChat methods are not composed."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import re
import unicodedata
from urllib.parse import urlsplit

from server.app.identity.application import AuthApplicationError, IssuedSession
from server.app.identity.domain import IdentityConflictError, Principal, SessionKind, digest, new_opaque_token
from server.app.identity.ports import QqGateway, QqIdentityRepository, QqProviderError
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
from server.app.platform.config import AppSettings


def sanitize_qq_profile(profile: dict) -> dict[str, str]:
    if not isinstance(profile, dict):
        return {}
    public = {}
    nickname = profile.get('nickname')
    if isinstance(nickname, str):
        nickname = ''.join(c for c in nickname if not unicodedata.category(c).startswith('C')).strip()[:64]
        if nickname:
            public['nickname'] = nickname
    avatar = profile.get('avatarUrl')
    if isinstance(avatar, str) and len(avatar) <= 2048 and not any(c.isspace() or ord(c) < 32 for c in avatar):
        try:
            url = urlsplit(avatar)
            if (url.scheme == 'https' and url.netloc in {'q.qlogo.cn', 'thirdqq.qlogo.cn'}
                    and not url.fragment and not url.username and not url.password):
                public['avatarUrl'] = avatar
        except ValueError:
            pass
    return public


@dataclass(frozen=True)
class QqMeView:
    connected: bool
    display_name: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class QqLoginCreated:
    authorization_url: str
    state: str
    browser_binding: str


class QqAuthApplication:
    def __init__(self, *, repository: QqIdentityRepository, qq_gateway: QqGateway,
                 settings: AppSettings, clock: Callable[[], datetime] | None = None):
        self._repository = repository
        self._qq_gateway = qq_gateway
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _configured(self):
        if not (self._settings.qq_appid and self._settings.qq_app_key and self._settings.qq_redirect_uri):
            raise AuthApplicationError('QQ_NOT_CONFIGURED', 'QQ login is not configured')

    def create_qq_login(self) -> QqLoginCreated:
        self._configured()
        state, binding = new_opaque_token(), new_opaque_token()
        now = self._clock()
        self._repository.insert_qq_login_attempt(state_hash=digest(state), browser_hash=digest(binding),
            expires_at=now + timedelta(seconds=self._settings.web_login_ttl_seconds), now=now)
        return QqLoginCreated(self._qq_gateway.authorization_url(state), state, binding)

    def finish_qq_login(self, *, state: str, browser_binding: str, code: str, error: str = '') -> IssuedSession:
        self._configured()
        if any(not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9_-]{43,128}', value) is None
               for value in (state, browser_binding)):
            raise AuthApplicationError('QQ_LOGIN_INVALID', 'Restart QQ login')
        if not self._repository.consume_qq_login_attempt(state_hash=digest(state), browser_hash=digest(browser_binding), now=self._clock()):
            raise AuthApplicationError('QQ_LOGIN_INVALID', 'Restart QQ login')
        if error:
            raise AuthApplicationError('QQ_LOGIN_CANCELLED', 'QQ login was cancelled')
        if not isinstance(code, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,512}', code) is None:
            raise AuthApplicationError('QQ_LOGIN_INVALID', 'Restart QQ login')
        try:
            identity = self._qq_gateway.exchange_code(code)
            if (identity.client_id != self._settings.qq_appid or not isinstance(identity.openid, str)
                    or re.fullmatch(r'[A-Za-z0-9_-]{16,256}', identity.openid) is None):
                raise QqProviderError('QQ provider unavailable')
        except Exception:
            raise AuthApplicationError('QQ_PROVIDER_UNAVAILABLE', 'QQ login provider is unavailable') from None
        now = self._clock()
        user_id = self._repository.upsert_qq_identity(appid=self._settings.qq_appid, openid=identity.openid, profile=sanitize_qq_profile(identity.profile), now=now)
        token = new_opaque_token()
        expires = now + timedelta(seconds=self._settings.web_session_ttl_seconds)
        self._repository.issue_auth_session(token_hash=digest(token), user_id=user_id, kind='web_cookie', expires_at=expires)
        return IssuedSession(token, expires, Principal(user_id=user_id, session_kind='web_cookie'))

    def resolve_principal(self, credential: str | None, kind: SessionKind) -> Principal | None:
        if kind != 'web_cookie' or not credential:
            return None
        principal = self._repository.resolve_auth_session(token_hash=digest(credential), kind=kind, now=self._clock())
        if principal is None:
            return None
        if principal.user_id in TEST_ACCOUNT_IDS.values():
            return principal if self._settings.test_login_enabled else None
        return principal if self._repository.has_qq_identity(user_id=principal.user_id, appid=self._settings.qq_appid) else None

    def exchange_test_account(self, account: str, credential: str, kind: SessionKind) -> IssuedSession:
        if not self._settings.test_login_enabled:
            raise AuthApplicationError('TEST_LOGIN_DISABLED', 'test login is unavailable')
        expected = {'A': self._settings.test_login_a_sha256, 'B': self._settings.test_login_b_sha256}
        if (account not in expected or kind != 'web_cookie' or not isinstance(credential, str)
                or not 32 <= len(credential) <= 256 or not hmac.compare_digest(digest(credential), expected[account])):
            raise AuthApplicationError('AUTH_REQUIRED', 'test credential is invalid')
        user_id = TEST_ACCOUNT_IDS[account]
        now = self._clock()
        try:
            self._repository.ensure_test_user(user_id=user_id, display_name=f'测试账号 {account}', now=now)
        except IdentityConflictError:
            raise AuthApplicationError('IDENTITY_CONFLICT', 'test account is unavailable') from None
        token = new_opaque_token()
        expires = now + timedelta(seconds=min(self._settings.web_session_ttl_seconds, 86400))
        self._repository.issue_auth_session(token_hash=digest(token), user_id=user_id, kind=kind, expires_at=expires)
        return IssuedSession(token, expires, Principal(user_id=user_id, session_kind=kind))

    def me(self, principal: Principal) -> QqMeView:
        user = self._repository.get_public_user(principal.user_id)
        if user is None:
            raise AuthApplicationError('AUTH_REQUIRED', 'authenticated user is unavailable')
        profile = sanitize_qq_profile(self._repository.get_qq_profile(user_id=principal.user_id, appid=self._settings.qq_appid))
        return QqMeView(connected=True, display_name=user.display_name or 'QQ 账号', avatar_url=profile.get('avatarUrl'))

    def avatar(self, principal: Principal) -> str | None:
        return self._repository.get_avatar(principal.user_id)

    def logout(self, principal: Principal, raw_credential: str | None) -> None:
        if raw_credential:
            self._repository.revoke_auth_session(token_hash=digest(raw_credential), kind='web_cookie', now=self._clock())
