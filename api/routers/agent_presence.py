from __future__ import annotations

from fastapi import APIRouter

from api.realtime import realtime_hub
from api.schemas.agent_presence import PresenceResponse, PresenceUpsertRequest
from api.services.agent_presence_service import agent_presence_service

router = APIRouter(prefix="/api/agent-presence", tags=["agent-presence"])


@router.get("", response_model=list[PresenceResponse])
def list_presence() -> list[PresenceResponse]:
    rows = agent_presence_service.list()
    return [PresenceResponse.model_validate(r) for r in rows]


@router.post("", response_model=PresenceResponse)
async def upsert_presence(payload: PresenceUpsertRequest) -> PresenceResponse:
    row = agent_presence_service.upsert(payload)
    response = PresenceResponse.model_validate(row)
    await realtime_hub.broadcast("presence.updated", response.model_dump(mode="json"))
    return response

