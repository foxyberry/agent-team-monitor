from __future__ import annotations

from fastapi import APIRouter, Query

from api.realtime import realtime_hub
from api.schemas.agent_chat import (
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatRoomCreateRequest,
    ChatRoomResponse,
)
from api.services.agent_chat_service import agent_chat_service

router = APIRouter(prefix="/api/agent-chat", tags=["agent-chat"])


@router.post("/rooms", response_model=ChatRoomResponse)
def create_room(payload: ChatRoomCreateRequest) -> ChatRoomResponse:
    room = agent_chat_service.create_room(payload)
    return ChatRoomResponse.model_validate(room)


@router.get("/rooms", response_model=list[ChatRoomResponse])
def list_rooms() -> list[ChatRoomResponse]:
    rooms = agent_chat_service.list_rooms()
    return [ChatRoomResponse.model_validate(r) for r in rooms]


@router.post("/messages", response_model=ChatMessageResponse)
async def create_message(payload: ChatMessageCreateRequest) -> ChatMessageResponse:
    msg = agent_chat_service.create_message(
        room_key=payload.room_key,
        sender_type=payload.sender_type,
        sender_name=payload.sender_name,
        session_id=payload.session_id,
        team_name=payload.team_name,
        message=payload.message,
        metadata_json=payload.metadata_json,
    )
    response = ChatMessageResponse.model_validate(msg)
    await realtime_hub.broadcast("chat.message.created", response.model_dump(mode="json"))
    return response


@router.get("/messages", response_model=list[ChatMessageResponse])
def list_messages(room_key: str = Query(...), limit: int = Query(default=50, ge=1, le=200)) -> list[ChatMessageResponse]:
    rows = agent_chat_service.list_messages(room_key=room_key, limit=limit)
    return [ChatMessageResponse.model_validate(r) for r in rows]

