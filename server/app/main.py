import os
from collections.abc import Mapping

from fastapi import FastAPI, Request

from server.app.api.errors import (
    ApiProblem,
    api_problem_handler,
    http_exception_handler,
    resolve_request_id,
    unhandled_exception_handler,
    validation_exception_handler,
)
from server.app.api.routes import router as health_router
from server.app.chickenbro.application import PrototypeChatApplication
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    DEFAULT_SOURCE_GATEWAY_URL,
    ServerConfiguredSourceQuery,
)
from server.app.identity.application import WebAuthApplication
from server.app.identity.audit import AuthAuditSink, NullAuthAuditSink
from server.app.identity.prototype import PrototypeIdentityApplication
from server.app.identity.repository import PostgresIdentityRepository
from server.app.integrations.wechat_mini import WechatMiniClient
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry, default_readiness_registry
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.simulation.application import PrototypeSimulationApplication
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.sources import CharacterSourceRouter, HttpxSourceGateway
from server.app.worker.leases import PostgresJobQueue


def create_app(
    settings: AppSettings,
    readiness_registry: ReadinessRegistry | None = None,
    web_auth_application: WebAuthApplication | None = None,
    prototype_identity_application: PrototypeIdentityApplication | None = None,
    prototype_chat_application: PrototypeChatApplication | None = None,
    prototype_simulation_application: PrototypeSimulationApplication | None = None,
    auth_audit_sink: AuthAuditSink | None = None,
) -> FastAPI:
    formal_auth_application_injected = web_auth_application is not None
    production = settings.environment == "production"
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None if production else "/api/v2/openapi.json",
    )
    app.state.settings = settings
    source_gateway = ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery())
    repository = None
    if (
        web_auth_application is None
        or prototype_identity_application is None
        or prototype_chat_application is None
        or prototype_simulation_application is None
    ):
        postgres_factory = PostgresConnectionFactory(settings)
        repository = PostgresIdentityRepository(postgres_factory.connection)
    if web_auth_application is None:
        if repository is None:
            raise RuntimeError("identity repository was not constructed")
        web_auth_application = WebAuthApplication(
            repository=repository,
            wechat_gateway=WechatMiniClient(settings),
            settings=settings,
        )
    if prototype_identity_application is None:
        if repository is None:
            raise RuntimeError("identity repository was not constructed")
        from datetime import timedelta

        prototype_identity_application = PrototypeIdentityApplication(
            repository=repository,
            ttl=timedelta(seconds=settings.prototype_ttl_seconds),
        )
    if prototype_chat_application is None:
        prototype_chat_application = PrototypeChatApplication(
            repository=PostgresChatRepository(postgres_factory.connection),
            codex=NativeCodexChatAdapter(
                source_gateway=source_gateway,
                source_gateway_url=f"http://127.0.0.1:{settings.port}/api/v2/internal/chickenbro/source-query",
            ),
        )
    if prototype_simulation_application is None:
        runtime_capabilities = SimcRuntimeCapabilities.from_env()
        prototype_simulation_application = PrototypeSimulationApplication(
            repository=PostgresSimulationRepository(postgres_factory.connection),
            source_router=CharacterSourceRouter(HttpxSourceGateway()),
            readiness_validator=SimcReadinessValidator(),
            compiler=SimcProfileCompiler(capabilities=runtime_capabilities),
            runtime_capabilities=runtime_capabilities,
            queue=PostgresJobQueue(postgres_factory.connection),
        )
    app.state.web_auth_application = web_auth_application
    app.state.auth_audit_sink = (
        repository
        if auth_audit_sink is None and repository is not None and not formal_auth_application_injected
        else auth_audit_sink or NullAuthAuditSink()
    )
    app.state.prototype_identity_application = prototype_identity_application
    app.state.prototype_chat_application = prototype_chat_application
    app.state.prototype_simulation_application = prototype_simulation_application
    app.state.chickenbro_source_gateway = source_gateway
    app.state.chickenbro_source_gateway_url = DEFAULT_SOURCE_GATEWAY_URL.replace(
        ":8790", f":{settings.port}", 1
    )
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
    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    return app


def build_app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    return create_app(settings=AppSettings.from_env(os.environ if env is None else env))


app: FastAPI | None = None
if os.environ.get("WOW_APP_ENV") and os.environ.get("WOW_DATABASE_URL"):
    app = build_app_from_env()
