from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SenderType = Literal["user", "agent", "system"]


class ChatRoomCreateRequest(BaseModel):
    room_key: str = Field(min_length=1, max_length=64)
    room_name: str = Field(min_length=1, max_length=128)


class ChatRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_key: str
    room_name: str
    created_at: datetime


class ChatMessageCreateRequest(BaseModel):
    room_key: str = Field(min_length=1, max_length=64)
    sender_type: SenderType = "agent"
    sender_name: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    team_name: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    sender_type: SenderType
    sender_name: str
    session_id: str | None
    team_name: str | None
    message: str
    metadata_json: dict[str, Any]
    created_at: datetime

