from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models.agent_presence import AgentPresence
from api.schemas.agent_presence import PresenceUpsertRequest


class AgentPresenceService:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def upsert(self, payload: PresenceUpsertRequest) -> AgentPresence:
        with self._session_factory() as db:
            row = db.scalar(select(AgentPresence).where(AgentPresence.agent_name == payload.agent_name))
            if row is None:
                row = AgentPresence(
                    agent_name=payload.agent_name,
                    agent_type=payload.agent_type,
                    session_id=payload.session_id,
                    team_name=payload.team_name,
                    state=payload.state,
                )
                db.add(row)
            else:
                row.agent_type = payload.agent_type
                row.session_id = payload.session_id
                row.team_name = payload.team_name
                row.state = payload.state
            db.commit()
            db.refresh(row)
            return row

    def list(self) -> list[AgentPresence]:
        with self._session_factory() as db:
            return list(db.scalars(select(AgentPresence).order_by(AgentPresence.last_seen_at.desc())).all())


agent_presence_service = AgentPresenceService()

