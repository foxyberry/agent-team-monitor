from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from api.realtime import realtime_hub
from api.schemas.agent_presence import PresenceResponse, PresenceUpsertRequest
from api.services.agent_presence_service import agent_presence_service

router = APIRouter(prefix="/api/agent-presence", tags=["agent-presence"])


@router.get("", response_model=list[PresenceResponse])
def list_presence() -> list[PresenceResponse]:
    rows = agent_presence_service.list()
    now = datetime.now(timezone.utc)
    out: list[PresenceResponse] = []
    for r in rows:
        row = PresenceResponse.model_validate(r)
        try:
            last = row.last_seen_at.astimezone(timezone.utc)
        except Exception:
            last = now - timedelta(hours=24)
        age = now - last
        # Soft-state view: do not overwrite DB, just present stale agents as offline.
        if age > timedelta(minutes=5):
            row.state = "offline"
        elif age > timedelta(minutes=2) and row.state == "active":
            row.state = "idle"
        out.append(row)
    return out


@router.post("", response_model=PresenceResponse)
async def upsert_presence(payload: PresenceUpsertRequest) -> PresenceResponse:
    row = agent_presence_service.upsert(payload)
    response = PresenceResponse.model_validate(row)
    await realtime_hub.broadcast("presence.updated", response.model_dump(mode="json"))
    return response
