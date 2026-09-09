import os
import logging
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
from server.app.chickenbro.application import ChatApplication
from server.app.chickenbro.simulation_tools import SimulationToolGateway
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    DEFAULT_SOURCE_GATEWAY_URL,
    ServerConfiguredSourceQuery,
)
from server.app.identity.audit import AuthAuditSink, NullAuthAuditSink
from server.app.identity.repository import PostgresIdentityRepository
from server.app.integrations.qq_connect import QqConnectClient
from server.app.identity.qq_application import QqAuthApplication
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry, default_readiness_registry
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.simulation.application import SimulationApplication
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.repository import PostgresSimulationRepository
from server.app.simulation.sources import CharacterSourceRouter, HttpxSourceGateway


class QqCallbackAccessFilter(logging.Filter):
    """Uvicorn access logs must never retain OAuth code/state query parameters."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if isinstance(args[2], str) and args[2].split('?', 1)[0] == '/api/v2/auth/qq/callback':
                args[2] = '/api/v2/auth/qq/callback'
                record.args = tuple(args)
        return True


def create_app(
    settings: AppSettings,
    readiness_registry: ReadinessRegistry | None = None,
    web_auth_application: QqAuthApplication | None = None,
    chat_application: ChatApplication | None = None,
    simulation_application: SimulationApplication | None = None,
    auth_audit_sink: AuthAuditSink | None = None,
    readiness_environment: Mapping[str, str] | None = None,
) -> FastAPI:
    access_logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, QqCallbackAccessFilter) for item in access_logger.filters):
        access_logger.addFilter(QqCallbackAccessFilter())
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
    postgres_factory = None
    if web_auth_application is None or chat_application is None or simulation_application is None:
        postgres_factory = PostgresConnectionFactory(settings)
        repository = PostgresIdentityRepository(postgres_factory.connection)
    if web_auth_application is None:
        if repository is None:
            raise RuntimeError("identity repository was not constructed")
        web_auth_application = QqAuthApplication(
            repository=repository,
            qq_gateway=QqConnectClient(settings),
            settings=settings,
        )
    if simulation_application is None:
        if postgres_factory is None:
            postgres_factory = PostgresConnectionFactory(settings)
        runtime_capabilities = SimcRuntimeCapabilities.from_env()
        simulation_application = SimulationApplication(
            repository=PostgresSimulationRepository(postgres_factory.connection),
            source_router=CharacterSourceRouter(HttpxSourceGateway()),
            readiness_validator=SimcReadinessValidator(),
            compiler=SimcProfileCompiler(capabilities=runtime_capabilities),
            runtime_capabilities=runtime_capabilities,
        )
    simulation_gateway = SimulationToolGateway(simulation_application)
    app.state.chickenbro_simulation_gateway = simulation_gateway
    if chat_application is None:
        if postgres_factory is None:
            raise RuntimeError("Chat application was not constructed")
        chat_application = ChatApplication(
            repository=PostgresChatRepository(postgres_factory.connection),
            codex=NativeCodexChatAdapter(
                source_gateway=source_gateway,
                simulation_gateway=simulation_gateway,
                simulation_gateway_url=f"http://127.0.0.1:{settings.port}/api/v2/internal/chickenbro/simc-tool",
                source_gateway_url=f"http://127.0.0.1:{settings.port}/api/v2/internal/chickenbro/source-query",
            ),
        )
    app.state.web_auth_application = web_auth_application
    app.state.auth_audit_sink = (
        repository
        if auth_audit_sink is None and repository is not None and not formal_auth_application_injected
        else auth_audit_sink or NullAuthAuditSink()
    )
    app.state.chat_application = chat_application
    app.state.simulation_application = simulation_application
    app.state.chickenbro_source_gateway = source_gateway
    app.state.chickenbro_source_gateway_url = DEFAULT_SOURCE_GATEWAY_URL.replace(
        ":8790", f":{settings.port}", 1
    )
    app.state.readiness_registry = (
        default_readiness_registry(settings, readiness_environment)
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
    if settings.test_login_enabled:
        from server.app.api.routes.test_auth import router as test_auth_router
        app.include_router(test_auth_router)
    return app


def build_app_from_env(env: Mapping[str, str] | None = None) -> FastAPI:
    source_env = os.environ if env is None else env
    return create_app(
        settings=AppSettings.from_env(source_env),
        readiness_environment=source_env,
    )


app: FastAPI | None = None
if os.environ.get("WOW_APP_ENV") and os.environ.get("WOW_DATABASE_URL"):
    app = build_app_from_env()
