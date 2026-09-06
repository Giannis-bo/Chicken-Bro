from fastapi import APIRouter
from server.app.api.routes.simulation_tools import router as simulation_tools_router

from server.app.api.routes.auth import router as auth_router
from server.app.api.routes.chat import router as chat_router
from server.app.api.routes.health import router as health_router
from server.app.api.routes.simc import router as simc_router
from server.app.api.routes.source_gateway import router as source_gateway_router


router = APIRouter()
router.include_router(simulation_tools_router)
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(simc_router)
router.include_router(source_gateway_router)

__all__ = ["router"]
