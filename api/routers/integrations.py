from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from api.realtime import realtime_hub
from api.services.agent_office_sync_service import agent_office_sync_service

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class SyncAgentOfficeRequest(BaseModel):
    source_url: str | None = Field(default=None)


@router.post("/agent-office/sync")
async def sync_agent_office(payload: SyncAgentOfficeRequest) -> dict:
    try:
        result = agent_office_sync_service.sync(payload.source_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"sync failed: {exc}") from exc

    response = {
        "source_url": result.source_url,
        "projects": result.projects,
        "agents_seen": result.agents_seen,
        "presence_upserts": result.presence_upserts,
        "chat_messages": result.chat_messages,
    }
    await realtime_hub.broadcast("integration.agent_office.synced", response)
    return response

