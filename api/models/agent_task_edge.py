from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentTaskEdge(Base):
    __tablename__ = "agent_task_edges"
    __table_args__ = (
        UniqueConstraint("parent_task_id", "child_task_id", "edge_type", name="uq_task_edge"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    child_task_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="spawned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

