from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
async def liveness(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "requestId": request.state.request_id,
    }


@router.get("/api/v2/health/readiness")
async def readiness(request: Request) -> dict[str, object]:
    registry = request.app.state.readiness_registry
    states = registry.check_all()
    return {
        "status": registry.overall_status(states),
        "requestId": request.state.request_id,
        "components": {
            name: {"status": state.status, "code": state.code}
            for name, state in states.items()
        },
    }
