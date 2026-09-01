from fastapi import Request

from server.app.api.errors import ApiProblem
from server.app.identity.application import WebAuthApplication
from server.app.identity.domain import Principal
from server.app.platform.cookies import read_web_cookie
from server.app.platform.origin import OriginRejectedError, require_web_origin


def web_auth_application(request: Request) -> WebAuthApplication:
    return request.app.state.web_auth_application


def require_mini_principal(request: Request) -> Principal:
    authorization = request.headers.get("authorization", "")
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential or any(character.isspace() for character in credential):
        raise ApiProblem(status_code=401, code="AUTH_REQUIRED", message="mini-program authentication is required")
    principal = web_auth_application(request).resolve_principal(credential, "mini_bearer")
    if principal is None:
        raise ApiProblem(status_code=401, code="AUTH_REQUIRED", message="mini-program authentication is required")
    return principal


def require_web_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    credential = read_web_cookie(request, settings)
    principal = web_auth_application(request).resolve_principal(credential, "web_cookie")
    if principal is None:
        raise ApiProblem(status_code=401, code="AUTH_REQUIRED", message="Web authentication is required")
    return principal


def require_web_origin_dependency(request: Request) -> None:
    try:
        require_web_origin(request, request.app.state.settings.web_origin)
    except OriginRejectedError:
        raise ApiProblem(status_code=403, code="ORIGIN_REJECTED", message="request Origin is not allowed") from None
