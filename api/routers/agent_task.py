from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.schemas.agent_task import (
    AgentTaskCreateRequest,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTaskUpdateRequest,
)
from api.services.agent_task_service import agent_task_service

router = APIRouter(prefix="/api/agent-tasks", tags=["agent-tasks"])


@router.post("", response_model=AgentTaskResponse)
def create_agent_task(payload: AgentTaskCreateRequest) -> AgentTaskResponse:
    task = agent_task_service.create_task(payload)
    return AgentTaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=AgentTaskResponse)
def update_agent_task(task_id: str, payload: AgentTaskUpdateRequest) -> AgentTaskResponse:
    if payload.task_id != task_id:
        raise HTTPException(status_code=400, detail="task_id in body must match path")
    task = agent_task_service.update_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse.model_validate(task)


@router.get("", response_model=AgentTaskListResponse)
def list_agent_tasks(
    status: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AgentTaskListResponse:
    tasks, total = agent_task_service.list_tasks(
        status=status,
        agent_type=agent_type,
        session_id=session_id,
        team_name=team_name,
        limit=limit,
        offset=offset,
    )
    return AgentTaskListResponse(tasks=[AgentTaskResponse.model_validate(t) for t in tasks], total_count=total)


@router.get("/{task_id}", response_model=AgentTaskResponse)
def get_agent_task(task_id: str) -> AgentTaskResponse:
    task = agent_task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTaskResponse.model_validate(task)


@router.delete("/{task_id}")
def delete_agent_task(task_id: str) -> dict[str, bool]:
    deleted = agent_task_service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}

