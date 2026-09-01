import os
from collections.abc import Mapping

from fastapi import FastAPI, Request

from server.app.api.errors import (
    http_exception_handler,
    resolve_request_id,
    unhandled_exception_handler,
    validation_exception_handler,
)
from server.app.api.routes import router as health_router
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry, default_readiness_registry


def create_app(
    settings: AppSettings,
    readiness_registry: ReadinessRegistry | None = None,
) -> FastAPI:
    production = settings.environment == "production"
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None if production else "/api/v2/openapi.json",
    )
    app.state.settings = settings
    app.state.readiness_registry = (
        default_readiness_registry(settings)
        if readiness_registry is None
        else readiness_registry
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = resolve_request_id(request.headers.get("X-Request-Id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    app.add_exception_handler(404, http_exception_handler)
    app.add_exception_handler(422, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    return app


def build_app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(settings=AppSettings.from_env(os.environ if env is None else env))


app: FastAPI | None = None
if os.environ.get("WOW_APP_ENV") and os.environ.get("WOW_DATABASE_URL"):
    app = build_app_from_env()
