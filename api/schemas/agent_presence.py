from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PresenceState = Literal["active", "idle", "offline"]


class PresenceUpsertRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=128)
    agent_type: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    team_name: str | None = Field(default=None, max_length=128)
    state: PresenceState = "active"


class PresenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    agent_type: str | None
    session_id: str | None
    team_name: str | None
    state: PresenceState
    last_seen_at: datetime

