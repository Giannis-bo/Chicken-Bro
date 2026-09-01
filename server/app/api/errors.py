import re
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


_CANONICAL_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)


class ApiProblem(Exception):
    def __init__(self, *, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def resolve_request_id(value: str | None) -> str:
    if value is not None and _CANONICAL_UUID.fullmatch(value):
        try:
            parsed = UUID(value)
        except ValueError:
            parsed = None
        if parsed is not None and str(parsed) == value:
            return value
    return str(uuid4())


def request_id_for(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and _CANONICAL_UUID.fullmatch(request_id):
        return request_id
    return resolve_request_id(None)


def problem_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    request_id = request_id_for(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id,
            }
        },
        headers={"X-Request-Id": request_id},
    )


async def http_exception_handler(request: Request, exception: StarletteHTTPException) -> JSONResponse:
    if exception.status_code == 404:
        return problem_response(
            request=request,
            status_code=404,
            code="NOT_FOUND",
            message="resource not found",
        )
    return problem_response(
        request=request,
        status_code=exception.status_code,
        code="REQUEST_REJECTED",
        message="request rejected",
    )


async def api_problem_handler(request: Request, exception: ApiProblem) -> JSONResponse:
    return problem_response(
        request=request,
        status_code=exception.status_code,
        code=exception.code,
        message=exception.message,
    )


async def validation_exception_handler(request: Request, exception: RequestValidationError) -> JSONResponse:
    return problem_response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="request validation failed",
    )


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    return problem_response(
        request=request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="internal server error",
    )
