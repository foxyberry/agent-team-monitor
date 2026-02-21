from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.schemas.agent_task import (
    AgentTaskCreateRequest,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTaskUpdateRequest,
)
from api.services.agent_chat_service import agent_chat_service
from api.services.agent_graph_service import agent_graph_service
from api.services.agent_task_service import agent_task_service
from api.realtime import realtime_hub

router = APIRouter(prefix="/api/agent-tasks", tags=["agent-tasks"])


@router.post("", response_model=AgentTaskResponse)
async def create_agent_task(payload: AgentTaskCreateRequest) -> AgentTaskResponse:
    task = agent_task_service.create_task(payload)
    if payload.parent_task_id:
        agent_graph_service.add_edge(payload.parent_task_id, payload.task_id, "spawned")
    agent_chat_service.create_message(
        room_key=payload.team_name or "general",
        sender_type="system",
        sender_name="task-bot",
        session_id=payload.session_id,
        team_name=payload.team_name,
        message=f"Task created: {payload.task_id} - {payload.subject}",
        metadata_json={"event": "task.created"},
    )
    response = AgentTaskResponse.model_validate(task)
    await realtime_hub.broadcast("task.created", response.model_dump(mode="json"))
    return response


@router.put("/{task_id}", response_model=AgentTaskResponse)
async def update_agent_task(task_id: str, payload: AgentTaskUpdateRequest) -> AgentTaskResponse:
    if payload.task_id != task_id:
        raise HTTPException(status_code=400, detail="task_id in body must match path")
    task = agent_task_service.update_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if payload.parent_task_id:
        agent_graph_service.add_edge(payload.parent_task_id, payload.task_id, "related")
    response = AgentTaskResponse.model_validate(task)
    await realtime_hub.broadcast("task.updated", response.model_dump(mode="json"))
    return response


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
