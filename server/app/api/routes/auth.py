from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import (
    require_mini_principal,
    require_mutating_principal,
    require_principal,
    require_web_origin_dependency,
    web_auth_application,
)
from server.app.api.errors import ApiProblem
from server.app.identity.application import (
    AuthApplicationError,
    WebAuthApplication,
)
from server.app.identity.domain import Principal
from server.app.identity.request_auth import credential_for_principal
from server.app.platform.cookies import clear_web_auth_cookies, set_web_auth_cookies
from server.app.platform.csrf import issue_csrf_token


router = APIRouter()


class WebLoginCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    browserVerifier: str = Field(
        min_length=43,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniExchangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=512, pattern=r"^\S+$")


class MiniConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sceneTicket: str = Field(
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


def _status_for_code(code: str) -> int:
    return {
        "AUTH_REQUIRED": 401,
        "ORIGIN_REJECTED": 403,
        "VALIDATION_ERROR": 422,
        "WEB_LOGIN_NOT_FOUND": 404,
        "WEB_LOGIN_EXPIRED": 410,
        "WEB_LOGIN_CANCELLED": 409,
        "WEB_LOGIN_VERIFIER_MISMATCH": 403,
        "WEB_LOGIN_ALREADY_CONSUMED": 409,
        "WEB_LOGIN_NOT_CONFIRMED": 409,
        "WEB_LOGIN_RESTART_REQUIRED": 409,
        "IDENTITY_CONFLICT": 409,
        "WECHAT_NOT_CONFIGURED": 503,
        "WECHAT_PROVIDER_UNAVAILABLE": 502,
    }.get(code, 500)


def _raise_application_error(error: AuthApplicationError) -> None:
    raise ApiProblem(
        status_code=_status_for_code(error.code),
        code=error.code,
        message=error.message,
    ) from error


def _request_id(request: Request) -> str:
    return request.state.request_id


def _status_payload(request: Request, status: str, expires_at: datetime) -> dict[str, object]:
    return {
        "status": status,
        "expiresAt": expires_at.isoformat(),
        "requestId": _request_id(request),
    }


def _required_header(value: str | None, *, name: str) -> str:
    if not value:
        raise ApiProblem(status_code=422, code="VALIDATION_ERROR", message=f"{name} is required")
    return value


@router.post("/api/v2/auth/wechat/web/login-sessions", status_code=201)
def create_web_login_session(
    body: WebLoginCreateBody,
    request: Request,
    _origin: None = Depends(require_web_origin_dependency),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        created = application.create_web_login(
            body.browserVerifier,
            idempotency_key=_required_header(idempotency_key, name="Idempotency-Key"),
        )
    except ApiProblem:
        raise
    except AuthApplicationError as error:
        _raise_application_error(error)
    return {
        "sessionId": str(created.session.id),
        "expiresAt": created.session.expires_at.isoformat(),
        "qrDataUrl": created.qr_data_url,
        "requestId": _request_id(request),
    }


@router.get("/api/v2/auth/wechat/web/login-sessions/{session_id}")
def get_web_login_status(
    session_id: UUID,
    request: Request,
    verifier: Annotated[str | None, Header(alias="X-Web-Login-Verifier")] = None,
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        status = application.get_web_login_status(
            session_id,
            _required_header(verifier, name="X-Web-Login-Verifier"),
        )
    except ApiProblem:
        raise
    except AuthApplicationError as error:
        _raise_application_error(error)
    return _status_payload(request, status.status.value, status.expires_at)


@router.post("/api/v2/auth/wechat/web/login-sessions/{session_id}/exchange")
def exchange_web_login_session(
    session_id: UUID,
    request: Request,
    response: Response,
    _origin: None = Depends(require_web_origin_dependency),
    verifier: Annotated[str | None, Header(alias="X-Web-Login-Verifier")] = None,
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        issued = application.exchange_web_login(
            session_id,
            _required_header(verifier, name="X-Web-Login-Verifier"),
        )
    except ApiProblem:
        raise
    except AuthApplicationError as error:
        _raise_application_error(error)
    set_web_auth_cookies(
        response,
        request.app.state.settings,
        session_token=issued.token,
        csrf_token=issue_csrf_token(),
    )
    return {"authenticated": True, "requestId": _request_id(request)}


@router.post("/api/v2/auth/wechat/web/login-sessions/{session_id}/cancel")
def cancel_web_login_session(
    session_id: UUID,
    request: Request,
    _origin: None = Depends(require_web_origin_dependency),
    verifier: Annotated[str | None, Header(alias="X-Web-Login-Verifier")] = None,
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        status = application.cancel_web_login(
            session_id,
            _required_header(verifier, name="X-Web-Login-Verifier"),
        )
    except ApiProblem:
        raise
    except AuthApplicationError as error:
        _raise_application_error(error)
    return _status_payload(request, status.status.value, status.expires_at)


@router.post("/api/v2/auth/wechat/mini/exchange")
def exchange_mini_code(
    body: MiniExchangeBody,
    request: Request,
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        issued = application.exchange_mini_code(body.code)
    except AuthApplicationError as error:
        _raise_application_error(error)
    return {
        "accessToken": issued.token,
        "expiresAt": issued.expires_at.isoformat(),
        "requestId": _request_id(request),
    }


@router.post("/api/v2/auth/wechat/mini/web-login-confirm")
def confirm_mini_web_login(
    body: MiniConfirmBody,
    request: Request,
    principal: Principal = Depends(require_mini_principal),
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        application.confirm_mini_web_login(body.sceneTicket, principal)
    except AuthApplicationError as error:
        _raise_application_error(error)
    return {"confirmed": True, "requestId": _request_id(request)}


@router.post("/api/v2/auth/logout")
def logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(require_mutating_principal),
    application: WebAuthApplication = Depends(web_auth_application),
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
    application: WebAuthApplication = Depends(web_auth_application),
) -> dict[str, object]:
    try:
        view = application.me(principal)
    except AuthApplicationError as error:
        _raise_application_error(error)
    return {
        "connected": view.connected,
        "displayName": view.display_name,
        "requestId": _request_id(request),
    }
