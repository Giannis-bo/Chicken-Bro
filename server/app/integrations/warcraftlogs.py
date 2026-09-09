import base64
import json
import hashlib
import math
import ssl
import threading
from collections import OrderedDict
from time import monotonic
import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WarcraftLogsAccessError(RuntimeError):
    pass


class WarcraftLogsProviderError(RuntimeError):
    retryable = False


class _TransientOAuthError(WarcraftLogsProviderError):
    retryable = True


def warcraftlogs_credentials_state(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_env = os.environ if env is None else env
    has_v2_credentials = bool(
        source_env.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
        and source_env.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    )
    if has_v2_credentials:
        return {
            "configured": True,
            "mode": "v2_oauth",
            "api": "warcraftlogs-v2-graphql",
        }
    if source_env.get("WOW_WARCRAFTLOGS_API_KEY", "").strip():
        return {
            "configured": True,
            "mode": "v1_api_key",
            "api": "warcraftlogs-v1-rest",
        }
    return {
        "configured": False,
        "mode": "none",
        "api": "warcraftlogs-v2-graphql",
    }


def warcraftlogs_timeout_seconds(
    timeout_seconds: Any = None,
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    source_env = os.environ if env is None else env
    try:
        configured = int(source_env.get("WOW_WARCRAFTLOGS_TIMEOUT_SECONDS", "15"))
    except (TypeError, ValueError):
        configured = 15
    configured = max(1, configured)
    if timeout_seconds is None:
        return configured
    try:
        return min(configured, max(1, int(timeout_seconds)))
    except (TypeError, ValueError):
        return configured


def _oauth_token_payload(
    timeout_seconds: Any = None,
    *,
    env: Mapping[str, str] | None = None,
    opener: Callable[..., Any] | None = None,
) -> tuple[str, Any]:
    source_env = os.environ if env is None else env
    client_id = source_env.get("WOW_WARCRAFTLOGS_CLIENT_ID", "").strip()
    client_secret = source_env.get("WOW_WARCRAFTLOGS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise WarcraftLogsAccessError("Warcraft Logs v2 credentials are not configured")
    token_url = source_env.get(
        "WOW_WARCRAFTLOGS_TOKEN_URL",
        "https://www.warcraftlogs.com/oauth/token",
    ).strip()
    request = Request(
        token_url,
        data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
        headers={
            "Authorization": "Basic " + base64.b64encode(
                f"{client_id}:{client_secret}".encode("utf-8")
            ).decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "wow-mini-program-wcl-sync",
        },
        method="POST",
    )
    open_request = urlopen if opener is None else opener
    try:
        with open_request(
            request,
            timeout=timeout_seconds,
        ) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise WarcraftLogsProviderError("Warcraft Logs OAuth response was too large")
        payload = json.loads(raw.decode("utf-8"))
    except WarcraftLogsProviderError:
        raise
    except HTTPError as error:
        if error.code in {401, 403}:
            raise WarcraftLogsAccessError("Warcraft Logs OAuth access was rejected") from None
        error_type = _TransientOAuthError if error.code == 429 or 500 <= error.code <= 599 else WarcraftLogsProviderError
        raise error_type("Warcraft Logs OAuth provider failed") from None
    except (URLError, OSError) as error:
        reason = getattr(error, 'reason', error)
        error_type = WarcraftLogsProviderError if isinstance(reason, ssl.SSLError) else _TransientOAuthError
        raise error_type("Warcraft Logs OAuth provider failed") from None
    except (TypeError, ValueError, UnicodeError):
        raise WarcraftLogsProviderError("Warcraft Logs OAuth provider failed") from None
    token = str(payload.get("access_token") or "").strip() if isinstance(payload, Mapping) else ""
    if not token or len(token) > 4096:
        raise WarcraftLogsAccessError("Warcraft Logs OAuth response did not include an access token")
    return token, payload.get('expires_in')


def warcraftlogs_oauth_token(timeout_seconds=None, *, env=None, opener=None) -> str:
    """Legacy uncached single fetch, including its existing timeout policy."""
    try:
        token, _ = _oauth_token_payload(
            warcraftlogs_timeout_seconds(timeout_seconds, env=env), env=env, opener=opener)
    except _TransientOAuthError:
        raise WarcraftLogsProviderError('Warcraft Logs OAuth provider failed') from None
    return token


def _chat_cache_identity(source_env, fetch):
    identity = tuple(source_env.get(k,'').strip() for k in (
        'WOW_WARCRAFTLOGS_CLIENT_ID','WOW_WARCRAFTLOGS_CLIENT_SECRET'))
    endpoint = source_env.get('WOW_WARCRAFTLOGS_TOKEN_URL','https://www.warcraftlogs.com/oauth/token').strip()
    key = (hashlib.sha256(json.dumps((*identity,endpoint)).encode()).digest(), id(fetch))
    slot = (hashlib.sha256(json.dumps((identity[0],endpoint)).encode()).digest(), id(fetch))
    return key, slot


class ChatWarcraftLogsTokenCache:
    """Process-local Chat cache. No credentials, tokens or upstream text in errors.

    The lock covers fetching: concurrent requests for a token share a single
    successful fetch. Other credentials wait within their own unchanged deadline.
    """
    def __init__(self, *, max_entries=8, clock=monotonic):
        self._entries = OrderedDict()
        self._lock = threading.Lock()
        self._invalidation_lock = threading.Lock()
        self._invalidations = OrderedDict()
        self._clock = clock
        self._max_entries = max(1, min(32, int(max_entries)))

    def token(self, timeout_seconds=None, *, env=None, opener=None):
        source_env = dict(os.environ if env is None else env)
        fetch = urlopen if opener is None else opener
        configured = warcraftlogs_timeout_seconds(None, env=source_env)
        try:
            budget = configured if timeout_seconds is None else min(configured, float(timeout_seconds))
        except (TypeError, ValueError):
            budget = configured
        if not math.isfinite(budget) or budget <= 0:
            raise WarcraftLogsProviderError('Warcraft Logs OAuth deadline exhausted')
        started = self._clock()
        deadline = started + budget
        key, credential_slot = _chat_cache_identity(source_env, fetch)
        if not self._lock.acquire(timeout=max(0, deadline-self._clock())):
            raise WarcraftLogsProviderError('Warcraft Logs OAuth deadline exhausted')
        try:
            now = self._clock()
            if now >= deadline:
                raise WarcraftLogsProviderError('Warcraft Logs OAuth deadline exhausted')
            for old_key, (_, expires, _, slot) in list(self._entries.items()):
                if expires <= now or (slot == credential_slot and old_key != key):
                    del self._entries[old_key]
            entry = self._entries.get(key)
            with self._invalidation_lock:
                rejected = self._invalidations.pop(key, None)
            if entry is not None and rejected == hashlib.sha256(entry[0].encode()).digest():
                del self._entries[key]
                entry = None
            if entry is not None:
                self._entries.move_to_end(key)
                return entry[0]
            for attempt in range(2):
                remaining = deadline-self._clock()
                if remaining <= 0:
                    raise WarcraftLogsProviderError('Warcraft Logs OAuth deadline exhausted')
                fetched_at = self._clock()
                try:
                    token, expiry = _oauth_token_payload(remaining, env=source_env, opener=fetch)
                except _TransientOAuthError:
                    if attempt == 0 and self._clock() < deadline:
                        continue
                    raise
                if self._clock() >= deadline:
                    raise WarcraftLogsProviderError('Warcraft Logs OAuth deadline exhausted')
                if isinstance(expiry,(int,float)) and not isinstance(expiry,bool) and math.isfinite(expiry) and expiry > 0:
                    # Underestimate from request start, refresh slightly early; never
                    # assume an expiry when the provider omits or misformats it.
                    life = min(float(expiry), 86400.0)
                    expires = fetched_at + life - min(30.0,life * 0.1)
                    if expires > self._clock():
                        self._entries[key] = (token, expires, fetch, credential_slot)
                        while len(self._entries) > self._max_entries:
                            self._entries.popitem(last=False)
                return token
        finally:
            self._lock.release()

    def invalidate(self, rejected_token, *, env=None, opener=None):
        """Mark only the rejected credential/token pair, without waiting on I/O.

        Applied before the next cache read. A delayed rejection of an old token
        must not invalidate a newer token acquired by another request.
        """
        source_env = os.environ if env is None else env
        fetch = urlopen if opener is None else opener
        key, _ = _chat_cache_identity(source_env, fetch)
        if not isinstance(rejected_token, str) or not rejected_token:
            return
        with self._invalidation_lock:
            entry = self._entries.get(key)
            if entry is None or entry[0] != rejected_token:
                return
            self._invalidations[key] = hashlib.sha256(rejected_token.encode()).digest()
            self._invalidations.move_to_end(key)
            while len(self._invalidations)>32:
                self._invalidations.popitem(last=False)


_CHAT_TOKEN_CACHE = ChatWarcraftLogsTokenCache()


def chat_warcraftlogs_oauth_token(timeout_seconds=None, *, env=None, opener=None):
    return _CHAT_TOKEN_CACHE.token(timeout_seconds, env=env, opener=opener)


def invalidate_chat_warcraftlogs_oauth_token(rejected_token, *, env=None, opener=None):
    _CHAT_TOKEN_CACHE.invalidate(rejected_token, env=env, opener=opener)


__all__ = (
    "ChatWarcraftLogsTokenCache",
    "chat_warcraftlogs_oauth_token",
    "invalidate_chat_warcraftlogs_oauth_token",
    "WarcraftLogsAccessError",
    "WarcraftLogsProviderError",
    "warcraftlogs_credentials_state",
    "warcraftlogs_oauth_token",
    "warcraftlogs_timeout_seconds",
)
