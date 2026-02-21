from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    files_modified: Mapped[list[str]] = mapped_column(SAJSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def mark_timestamps_from_status(self, status: str) -> None:
        now = datetime.now(timezone.utc)
        if status == "in_progress" and self.started_at is None:
            self.started_at = now
        if status == "completed":
            if self.started_at is None:
                self.started_at = now
            if self.completed_at is None:
                self.completed_at = now

