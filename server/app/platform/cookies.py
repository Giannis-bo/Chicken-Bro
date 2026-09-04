from typing import Any, Protocol

from server.app.platform.config import AppSettings


class CookieRequest(Protocol):
    cookies: Any


class CookieResponse(Protocol):
    def set_cookie(self, **kwargs: Any) -> None: ...

    def delete_cookie(self, **kwargs: Any) -> None: ...


def read_web_cookie(request: CookieRequest, settings: AppSettings) -> str | None:
    value = request.cookies.get(settings.web_cookie_name)
    return value if value else None


def read_web_csrf_cookie(request: CookieRequest, settings: AppSettings) -> str | None:
    value = request.cookies.get(settings.web_csrf_cookie_name)
    return value if value else None


def set_web_cookie(response: CookieResponse, settings: AppSettings, token: str) -> None:
    response.set_cookie(
        key=settings.web_cookie_name,
        value=token,
        max_age=settings.web_session_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )


def set_web_auth_cookies(
    response: CookieResponse,
    settings: AppSettings,
    *,
    session_token: str,
    csrf_token: str,
) -> None:
    set_web_cookie(response, settings, session_token)
    response.set_cookie(
        key=settings.web_csrf_cookie_name,
        value=csrf_token,
        max_age=settings.web_session_ttl_seconds,
        httponly=False,
        secure=True,
        samesite="Lax",
        path="/",
    )


def clear_web_cookie(response: CookieResponse, settings: AppSettings) -> None:
    response.delete_cookie(
        key=settings.web_cookie_name,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )


def clear_web_auth_cookies(response: CookieResponse, settings: AppSettings) -> None:
    clear_web_cookie(response, settings)
    response.delete_cookie(
        key=settings.web_csrf_cookie_name,
        httponly=False,
        secure=True,
        samesite="Lax",
        path="/",
    )
