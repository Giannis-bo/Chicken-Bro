from fastapi import APIRouter, Depends, Request
from server.app.api.dependencies import require_web_principal, _record_auth_audit
from server.app.api.errors import ApiProblem
from server.app.identity.domain import Principal
from server.app.admin.application import AdminError

router = APIRouter(prefix='/api/v2/admin', tags=['admin'])

@router.get('/access')
def access(request: Request, principal: Principal = Depends(require_web_principal)):
    return {'isAdmin': request.app.state.admin_application.allowed(principal), 'accountId': str(principal.user_id)}

@router.get('/overview')
def overview(request: Request, start: str | None = None, end: str | None = None,
             principal: Principal = Depends(require_web_principal)):
    application = request.app.state.admin_application
    try:
        application.require(principal)
    except AdminError as error:
        _record_auth_audit(request, event_type='admin.access', principal=principal,
                           status_code=error.status, reason_code=error.code)
        raise ApiProblem(status_code=error.status, code=error.code, message=error.message) from None
    _record_auth_audit(request, event_type='admin.access', principal=principal,
                       status_code=200, reason_code='ADMIN_AUTHORIZED')
    try:
        return application.overview(principal, start, end)
    except AdminError as error:
        raise ApiProblem(status_code=error.status, code=error.code, message=error.message) from None
