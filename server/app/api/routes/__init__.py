from fastapi import APIRouter

from server.app.api.routes.auth import router as auth_router
from server.app.api.routes.health import router as health_router
from server.app.api.routes.prototype import router as prototype_router


router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(prototype_router)

__all__ = ["router"]
