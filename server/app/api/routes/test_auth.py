"""Mounted only on explicitly enabled test servers."""
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import require_web_origin_dependency, web_auth_application
from server.app.api.routes.auth import _raise_application_error
from server.app.identity.application import AuthApplicationError
from server.app.identity.qq_application import QqAuthApplication
from server.app.platform.cookies import set_web_auth_cookies
from server.app.platform.csrf import issue_csrf_token


router = APIRouter(prefix="/api/v2/auth/test")


class TestLoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: Literal["A", "B"]
    credential: str = Field(min_length=32, max_length=256, repr=False)


@router.post("/web")
def login_web(body: TestLoginBody, request: Request, response: Response,
              _origin: None = Depends(require_web_origin_dependency),
              application: QqAuthApplication = Depends(web_auth_application)) -> dict[str, object]:
    try:
        issued = application.exchange_test_account(body.account, body.credential, "web_cookie")
    except AuthApplicationError as error:
        _raise_application_error(error)
    set_web_auth_cookies(response, request.app.state.settings,
                         session_token=issued.token, csrf_token=issue_csrf_token())
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "requestId": request.state.request_id}
