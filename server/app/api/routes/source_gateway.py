from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import chickenbro_source_gateway
from server.app.api.errors import ApiProblem
from server.app.chickenbro.source_gateway import (
    SOURCE_GATEWAY_PATH,
    ChickenbroSourceGateway,
    SourceGatewayUnauthorized,
)
from server.app.simulation.sources import InvalidSourceLink


router = APIRouter()


class SourceGatewayQueryBody(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=2048)
    options: dict[str, str | int | float] = Field(default_factory=dict, max_length=4)

    model_config = ConfigDict(extra="forbid")


@router.post(SOURCE_GATEWAY_PATH, include_in_schema=False)
def query_chickenbro_source_gateway(
    body: SourceGatewayQueryBody,
    request: Request,
    capability: str | None = Header(
        default=None,
        alias="X-Chickenbro-Source-Gateway",
    ),
    gateway: ChickenbroSourceGateway = Depends(chickenbro_source_gateway),
) -> dict[str, object]:
    try:
        result = gateway.query(capability or "", body.provider, body.target, options=body.options)
    except SourceGatewayUnauthorized as error:
        raise ApiProblem(
            status_code=401,
            code=SourceGatewayUnauthorized.code,
            message="source gateway capability is required",
        ) from error
    except InvalidSourceLink as error:
        raise ApiProblem(
            status_code=422,
            code="INVALID_SOURCE_LINK",
            message="source link is not allowed",
        ) from error
    return {**dict(result), "requestId": request.state.request_id}


__all__ = ("router",)
