from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.errors import ApiProblem
from server.app.chickenbro.simulation_tools import SimulationToolUnauthorized


router = APIRouter()


class SimulationToolBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation: str = Field(min_length=1, max_length=20)
    arguments: dict[str, object] = Field(default_factory=dict, max_length=4)


@router.post("/api/v2/internal/chickenbro/simc-tool", include_in_schema=False)
def execute_simulation_tool(body: SimulationToolBody, request: Request,
                            capability: str | None = Header(default=None, alias="X-Chickenbro-Simulation-Gateway")):
    try:
        return request.app.state.chickenbro_simulation_gateway.execute(
            capability or "", body.operation, body.arguments)
    except SimulationToolUnauthorized as error:
        raise ApiProblem(status_code=401, code="SIMULATION_TOOL_UNAUTHORIZED",
                         message="active Chat simulation capability is required") from error
