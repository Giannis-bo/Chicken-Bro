from typing import Any, Protocol

from server.app.identity.domain import Principal, SessionKind
from server.app.platform.config import AppSettings
from server.app.platform.csrf import require_web_csrf


class AuthRequest(Protocol):
    headers: Any
    cookies: Any


class PrincipalApplication(Protocol):
    def resolve_principal(self, raw_credential: str | None, kind: SessionKind) -> Principal | None: ...


class CredentialTransportError(ValueError):
    def __init__(self, *, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _header(request: AuthRequest, name: str) -> str:
    value = request.headers.get(name)
    if value is None:
        value = request.headers.get(name.lower())
    return value if isinstance(value, str) else ""


def _bearer_credential(authorization: str) -> str:
    parts = authorization.split(" ")
    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not parts[1]
        or any(character.isspace() for character in parts[1])
    ):
        raise CredentialTransportError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="authentication is required",
        )
    return parts[1]


def _web_credential(request: AuthRequest, web_cookie_name: str) -> str:
    value = request.cookies.get(web_cookie_name, "")
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise CredentialTransportError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="authentication is required",
        )
    return value


def resolve_request_principal(
    request: AuthRequest,
    *,
    application: PrincipalApplication,
    web_cookie_name: str,
) -> Principal:
    authorization = _header(request, "authorization")
    cookie_present = bool(request.cookies.get(web_cookie_name, ""))
    if authorization and cookie_present:
        raise CredentialTransportError(
            status_code=400,
            code="AMBIGUOUS_AUTH",
            message="use exactly one authentication transport",
        )

    if authorization:
        credential = _bearer_credential(authorization)
        kind: SessionKind = "mini_bearer"
    elif cookie_present:
        credential = _web_credential(request, web_cookie_name)
        kind = "web_cookie"
    else:
        raise CredentialTransportError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="authentication is required",
        )

    principal = application.resolve_principal(credential, kind)
    if principal is None or principal.session_kind != kind:
        raise CredentialTransportError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="authentication is required",
        )
    return principal


def resolve_mutating_request_principal(
    request: AuthRequest,
    *,
    application: PrincipalApplication,
    settings: AppSettings,
) -> Principal:
    principal = resolve_request_principal(
        request,
        application=application,
        web_cookie_name=settings.web_cookie_name,
    )
    if principal.session_kind == "web_cookie":
        require_web_csrf(request, settings)
    return principal


def credential_for_principal(
    request: AuthRequest,
    principal: Principal,
    web_cookie_name: str,
) -> str:
    if principal.session_kind == "mini_bearer":
        return _bearer_credential(_header(request, "authorization"))
    if principal.session_kind == "web_cookie":
        return _web_credential(request, web_cookie_name)
    raise CredentialTransportError(
        status_code=401,
        code="AUTH_REQUIRED",
        message="authentication is required",
    )
