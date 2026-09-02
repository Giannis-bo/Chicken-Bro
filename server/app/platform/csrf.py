import base64
import hmac
import secrets
from typing import Any, Protocol

from server.app.platform.config import AppSettings
from server.app.platform.origin import HeaderRequest, header_value, require_web_origin


class CsrfRequest(HeaderRequest, Protocol):
    cookies: Any


class CsrfRejectedError(ValueError):
    pass


def issue_csrf_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def require_web_csrf(request: CsrfRequest, settings: AppSettings) -> None:
    require_web_origin(request, settings.web_origin)
    cookie = request.cookies.get(settings.web_csrf_cookie_name, "")
    header = header_value(request, "x-csrf-token")
    if (
        not isinstance(cookie, str)
        or not cookie
        or not header
        or not hmac.compare_digest(cookie, header)
    ):
        raise CsrfRejectedError("Web CSRF token is invalid")
