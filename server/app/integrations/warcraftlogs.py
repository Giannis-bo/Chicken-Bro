import base64
import json
import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WarcraftLogsAccessError(RuntimeError):
    pass


class WarcraftLogsProviderError(RuntimeError):
    pass


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


def warcraftlogs_oauth_token(
    timeout_seconds: Any = None,
    *,
    env: Mapping[str, str] | None = None,
    opener: Callable[..., Any] | None = None,
) -> str:
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
            timeout=warcraftlogs_timeout_seconds(timeout_seconds, env=source_env),
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
        raise WarcraftLogsProviderError("Warcraft Logs OAuth provider failed") from None
    except (OSError, TypeError, ValueError, UnicodeError):
        raise WarcraftLogsProviderError("Warcraft Logs OAuth provider failed") from None
    token = str(payload.get("access_token") or "").strip() if isinstance(payload, Mapping) else ""
    if not token or len(token) > 4096:
        raise WarcraftLogsAccessError("Warcraft Logs OAuth response did not include an access token")
    return token


__all__ = (
    "WarcraftLogsAccessError",
    "WarcraftLogsProviderError",
    "warcraftlogs_credentials_state",
    "warcraftlogs_oauth_token",
    "warcraftlogs_timeout_seconds",
)
