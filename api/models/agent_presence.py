from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentPresence(Base):
    __tablename__ = "agent_presence"
    __table_args__ = (UniqueConstraint("agent_name", name="uq_agent_presence_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

