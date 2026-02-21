from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models.agent_chat import AgentChatMessage, AgentChatRoom
from api.schemas.agent_chat import ChatMessageCreateRequest, ChatRoomCreateRequest


class AgentChatService:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def ensure_room(self, room_key: str, room_name: str | None = None) -> AgentChatRoom:
        with self._session_factory() as db:
            room = db.scalar(select(AgentChatRoom).where(AgentChatRoom.room_key == room_key))
            if room:
                return room
            room = AgentChatRoom(room_key=room_key, room_name=room_name or room_key)
            db.add(room)
            db.commit()
            db.refresh(room)
            return room

    def create_room(self, payload: ChatRoomCreateRequest) -> AgentChatRoom:
        return self.ensure_room(payload.room_key, payload.room_name)

    def list_rooms(self) -> list[AgentChatRoom]:
        with self._session_factory() as db:
            return list(db.scalars(select(AgentChatRoom).order_by(AgentChatRoom.room_key.asc())).all())

    def create_message(
        self,
        *,
        room_key: str,
        sender_type: str,
        sender_name: str,
        session_id: str | None,
        team_name: str | None,
        message: str,
        metadata_json: dict | None = None,
    ) -> AgentChatMessage:
        payload = ChatMessageCreateRequest(
            room_key=room_key,
            sender_type=sender_type,
            sender_name=sender_name,
            session_id=session_id,
            team_name=team_name,
            message=message,
            metadata_json=metadata_json or {},
        )
        with self._session_factory() as db:
            room = db.scalar(select(AgentChatRoom).where(AgentChatRoom.room_key == payload.room_key))
            if room is None:
                room = AgentChatRoom(room_key=payload.room_key, room_name=payload.room_key)
                db.add(room)
                db.flush()

            row = AgentChatMessage(
                room_id=room.id,
                sender_type=payload.sender_type,
                sender_name=payload.sender_name,
                session_id=payload.session_id,
                team_name=payload.team_name,
                message=payload.message,
                metadata_json=payload.metadata_json or {},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def list_messages(self, room_key: str, limit: int = 50) -> list[AgentChatMessage]:
        with self._session_factory() as db:
            room = db.scalar(select(AgentChatRoom).where(AgentChatRoom.room_key == room_key))
            if room is None:
                return []
            query = (
                select(AgentChatMessage)
                .where(AgentChatMessage.room_id == room.id)
                .order_by(AgentChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = list(db.scalars(query).all())
            rows.reverse()
            return rows


agent_chat_service = AgentChatService()
