from fastapi import Request, Response

from server.app.platform.config import AppSettings


def read_web_cookie(request: Request, settings: AppSettings) -> str | None:
    value = request.cookies.get(settings.web_cookie_name)
    return value if value else None


def set_web_cookie(response: Response, settings: AppSettings, token: str) -> None:
    response.set_cookie(
        key=settings.web_cookie_name,
        value=token,
        max_age=settings.web_session_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )


def clear_web_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=settings.web_cookie_name,
        max_age=0,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )
