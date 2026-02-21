from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["pending", "in_progress", "completed", "deleted"]


class AgentTaskCreateRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    agent_type: str | None = Field(default=None, max_length=64)
    team_name: str | None = Field(default=None, max_length=128)
    subject: str = Field(min_length=1, max_length=512)
    description: str | None = None
    status: TaskStatus = "pending"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AgentTaskUpdateRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    status: TaskStatus | None = None
    subject: str | None = Field(default=None, max_length=512)
    description: str | None = None
    files_modified: list[str] | None = None
    metadata_json: dict[str, Any] | None = None


class AgentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    session_id: str | None
    agent_type: str | None
    team_name: str | None
    subject: str
    description: str | None
    status: TaskStatus
    files_modified: list[str]
    metadata_json: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskResponse]
    total_count: int

