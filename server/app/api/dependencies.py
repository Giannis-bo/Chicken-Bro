from datetime import datetime, timezone

from fastapi import Request

from server.app.api.errors import ApiProblem
from server.app.chickenbro.application import PrototypeChatApplication
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway
from server.app.simulation.application import PrototypeSimulationApplication
from server.app.identity.application import WebAuthApplication
from server.app.identity.audit import AuthAuditEvent
from server.app.identity.domain import Principal
from server.app.identity.prototype import PrototypeIdentityApplication, PrototypePrincipal
from server.app.identity.request_auth import (
    CredentialTransportError,
    resolve_mutating_request_principal,
    resolve_request_principal,
)
from server.app.platform.csrf import CsrfRejectedError
from server.app.platform.origin import OriginRejectedError, require_web_origin


def web_auth_application(request: Request) -> WebAuthApplication:
    return request.app.state.web_auth_application


def prototype_identity_application(request: Request) -> PrototypeIdentityApplication:
    return request.app.state.prototype_identity_application


def prototype_chat_application(request: Request) -> PrototypeChatApplication:
    return request.app.state.prototype_chat_application


def prototype_simulation_application(request: Request) -> PrototypeSimulationApplication:
    return request.app.state.prototype_simulation_application


def chickenbro_source_gateway(request: Request) -> ChickenbroSourceGateway:
    return request.app.state.chickenbro_source_gateway


def _record_auth_audit(
    request: Request,
    *,
    event_type: str = "auth.decision",
    principal: Principal | None,
    status_code: int,
    reason_code: str,
) -> None:
    request_id = request.state.request_id
    request.app.state.auth_audit_sink.record_auth_audit(
        AuthAuditEvent(
            event_type=event_type,
            request_id=request_id,
            user_id=principal.user_id if principal is not None else None,
            session_kind=principal.session_kind if principal is not None else None,
            status_code=status_code,
            timestamp=datetime.now(timezone.utc),
            reason_code=reason_code,
        )
    )


def _principal_for_failed_mutation_audit(request: Request) -> Principal | None:
    try:
        return resolve_request_principal(
            request,
            application=web_auth_application(request),
            web_cookie_name=request.app.state.settings.web_cookie_name,
        )
    except CredentialTransportError:
        return None


def _formal_principal(
    request: Request,
    *,
    mutating: bool,
    expected_kind: str | None = None,
) -> Principal:
    try:
        if mutating:
            principal = resolve_mutating_request_principal(
                request,
                application=web_auth_application(request),
                settings=request.app.state.settings,
            )
        else:
            principal = resolve_request_principal(
                request,
                application=web_auth_application(request),
                web_cookie_name=request.app.state.settings.web_cookie_name,
            )
    except CredentialTransportError as error:
        _record_auth_audit(
            request,
            principal=None,
            status_code=error.status_code,
            reason_code=error.code,
        )
        raise ApiProblem(
            status_code=error.status_code,
            code=error.code,
            message=error.message,
        ) from None
    except OriginRejectedError:
        _record_auth_audit(
            request,
            principal=_principal_for_failed_mutation_audit(request),
            status_code=403,
            reason_code="ORIGIN_REJECTED",
        )
        raise ApiProblem(
            status_code=403,
            code="ORIGIN_REJECTED",
            message="request Origin or Host is not allowed",
        ) from None
    except CsrfRejectedError:
        _record_auth_audit(
            request,
            principal=_principal_for_failed_mutation_audit(request),
            status_code=403,
            reason_code="CSRF_REJECTED",
        )
        raise ApiProblem(
            status_code=403,
            code="CSRF_REJECTED",
            message="request CSRF token is invalid",
        ) from None

    if expected_kind is not None and principal.session_kind != expected_kind:
        _record_auth_audit(
            request,
            principal=principal,
            status_code=401,
            reason_code="SESSION_KIND_REJECTED",
        )
        raise ApiProblem(
            status_code=401,
            code="AUTH_REQUIRED",
            message="the required authentication transport is missing",
        )
    _record_auth_audit(
        request,
        principal=principal,
        status_code=200,
        reason_code="AUTHENTICATED",
    )
    return principal


def require_principal(request: Request) -> Principal:
    return _formal_principal(request, mutating=False)


def require_mutating_principal(request: Request) -> Principal:
    return _formal_principal(request, mutating=True)


def require_mini_principal(request: Request) -> Principal:
    return _formal_principal(request, mutating=False, expected_kind="mini_bearer")


def require_web_principal(request: Request) -> Principal:
    return _formal_principal(request, mutating=False, expected_kind="web_cookie")


def require_web_origin_dependency(request: Request) -> None:
    try:
        require_web_origin(request, request.app.state.settings.web_origin)
    except OriginRejectedError:
        _record_auth_audit(
            request,
            event_type="auth.origin",
            principal=None,
            status_code=403,
            reason_code="ORIGIN_REJECTED",
        )
        raise ApiProblem(
            status_code=403,
            code="ORIGIN_REJECTED",
            message="request Origin or Host is not allowed",
        ) from None
    _record_auth_audit(
        request,
        event_type="auth.origin",
        principal=None,
        status_code=200,
        reason_code="ORIGIN_ACCEPTED",
    )


def require_prototype_principal(request: Request) -> PrototypePrincipal:
    if not request.app.state.settings.prototype_enabled:
        raise ApiProblem(status_code=503, code="PROTOTYPE_DISABLED", message="Web prototype is not enabled")
    credential = request.headers.get("X-Prototype-Session", "")
    if not credential or any(character.isspace() for character in credential):
        raise ApiProblem(
            status_code=401,
            code="PROTOTYPE_SESSION_REQUIRED",
            message="prototype session is required",
        )
    principal = prototype_identity_application(request).resolve(credential)
    if principal is None:
        raise ApiProblem(
            status_code=401,
            code="PROTOTYPE_SESSION_REQUIRED",
            message="prototype session is required",
        )
    return principal
