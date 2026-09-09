
from urllib.parse import urlsplit
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict

from server.app.api.dependencies import (
    require_mutating_principal,
    require_principal,
    require_web_origin_dependency,
    web_auth_application,
)
from server.app.api.errors import ApiProblem
from server.app.identity.application import (
    AuthApplicationError,
)
from server.app.identity.qq_application import QqAuthApplication
from server.app.identity.domain import Principal
from server.app.identity.request_auth import credential_for_principal
from server.app.platform.cookies import clear_web_auth_cookies, set_web_auth_cookies
from server.app.platform.csrf import issue_csrf_token


router = APIRouter()


def _status_for_code(code: str) -> int:
    return {
        "QQ_NOT_CONFIGURED": 503,
        "AUTH_REQUIRED": 401,
        "TEST_LOGIN_DISABLED": 404,
        "ORIGIN_REJECTED": 403,
        "VALIDATION_ERROR": 422,
        "IDENTITY_CONFLICT": 409,
    }.get(code, 500)


def _raise_application_error(error: AuthApplicationError) -> None:
    raise ApiProblem(
        status_code=_status_for_code(error.code),
        code=error.code,
        message=error.message,
    ) from error


def _request_id(request: Request) -> str:
    return request.state.request_id


@router.post("/api/v2/auth/logout")
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(require_mutating_principal),
    application: QqAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        application.logout(
            principal,
            credential_for_principal(
                request,
                principal,
                request.app.state.settings.web_cookie_name,
            ),
        )
    except AuthApplicationError as error:
        _raise_application_error(error)
    if principal.session_kind == "web_cookie":
        clear_web_auth_cookies(response, request.app.state.settings)
    return {"loggedOut": True, "requestId": _request_id(request)}


@router.get("/api/v2/me")
def me(
    request: Request,
    principal: Principal = Depends(require_principal),
    application: QqAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        view = application.me(principal)
    except AuthApplicationError as error:
        _raise_application_error(error)
    return {
        "connected": view.connected,
        "displayName": view.display_name,
        **({"avatarUrl": view.avatar_url} if getattr(view, "avatar_url", None) else {}),
        "requestId": _request_id(request),
    }


class QqLoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/api/v2/auth/qq/login")
def create_qq_login(body: QqLoginBody, request: Request, response: Response,
                    _origin: None = Depends(require_web_origin_dependency),
                    application: QqAuthApplication = Depends(web_auth_application)):
    try:
        created = application.create_qq_login()
    except AuthApplicationError as error:
        _raise_application_error(error)
    response.set_cookie(key=request.app.state.settings.qq_binding_cookie_name, value=created.browser_binding,
                        max_age=request.app.state.settings.web_login_ttl_seconds,
                        secure=True, httponly=True, samesite="Lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"authorizationUrl": created.authorization_url, "requestId": _request_id(request)}


@router.get("/api/v2/auth/qq/callback")
def qq_callback(request: Request, application: QqAuthApplication = Depends(web_auth_application)):
    settings = request.app.state.settings
    destination = settings.web_origin.rstrip("/") + settings.qq_landing_path
    issued = None
    try:
        if request.headers.get("host") != urlsplit(settings.web_origin).netloc:
            raise AuthApplicationError("QQ_LOGIN_INVALID", "Restart QQ login")
        query = request.query_params
        if any(len(query.getlist(key)) > 1 for key in ("state", "code", "error")):
            raise AuthApplicationError("QQ_LOGIN_INVALID", "Restart QQ login")
        issued = application.finish_qq_login(state=query.get("state", ""), code=query.get("code", ""),
            error=query.get("error", ""), browser_binding=request.cookies.get(settings.qq_binding_cookie_name, ""))
    except AuthApplicationError as error:
        safe = error.code if error.code in {"QQ_LOGIN_INVALID", "QQ_LOGIN_CANCELLED", "QQ_NOT_CONFIGURED", "QQ_PROVIDER_UNAVAILABLE"} else "QQ_LOGIN_INVALID"
        destination += "?loginError=" + safe
    except Exception:
        destination += "?loginError=QQ_PROVIDER_UNAVAILABLE"
    response = RedirectResponse(destination, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.delete_cookie(key=request.app.state.settings.qq_binding_cookie_name, secure=True, httponly=True, samesite="Lax", path="/")
    if issued is not None:
        set_web_auth_cookies(response, settings, session_token=issued.token, csrf_token=issue_csrf_token())
    return response


@router.get("/api/v2/me/avatar")
def get_avatar(request: Request, response: Response,
               principal: Principal = Depends(require_principal),
               application: QqAuthApplication = Depends(web_auth_application)):
    response.headers["Cache-Control"] = "private, no-store"
    return {"avatarDataUrl": application.avatar(principal), "requestId": _request_id(request)}
