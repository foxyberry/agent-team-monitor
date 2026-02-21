from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models.agent_task import AgentTask
from api.schemas.agent_task import AgentTaskCreateRequest, AgentTaskUpdateRequest


class AgentTaskService:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def _merge_metadata(self, base: dict[str, Any], incoming: dict[str, Any] | None) -> dict[str, Any]:
        if not incoming:
            return base
        merged = dict(base or {})
        merged.update(incoming)
        return merged

    def _apply_status_transition(self, task: AgentTask, next_status: str) -> None:
        now = datetime.now(timezone.utc)
        task.status = next_status
        if next_status == "in_progress" and task.started_at is None:
            task.started_at = now
        if next_status == "completed":
            if task.started_at is None:
                task.started_at = now
            task.completed_at = now

    def create_task(self, payload: AgentTaskCreateRequest) -> AgentTask:
        with self._session_factory() as db:
            existing = db.scalar(select(AgentTask).where(AgentTask.task_id == payload.task_id))
            if existing:
                return existing

            task = AgentTask(
                task_id=payload.task_id,
                session_id=payload.session_id,
                agent_type=payload.agent_type,
                team_name=payload.team_name,
                subject=payload.subject,
                description=payload.description,
                status=payload.status,
                files_modified=[],
                metadata_json=payload.metadata_json or {},
            )
            task.mark_timestamps_from_status(payload.status)
            db.add(task)
            db.commit()
            db.refresh(task)
            return task

    def update_task(self, task_id: str, payload: AgentTaskUpdateRequest) -> AgentTask | None:
        with self._session_factory() as db:
            task = db.scalar(select(AgentTask).where(AgentTask.task_id == task_id))
            if task is None:
                return None

            if payload.session_id is not None:
                task.session_id = payload.session_id
            if payload.subject is not None:
                task.subject = payload.subject
            if payload.description is not None:
                task.description = payload.description
            if payload.files_modified is not None:
                task.files_modified = payload.files_modified
            if payload.metadata_json is not None:
                task.metadata_json = self._merge_metadata(task.metadata_json or {}, payload.metadata_json)
            if payload.status is not None and payload.status != task.status:
                self._apply_status_transition(task, payload.status)

            db.commit()
            db.refresh(task)
            return task

    def get_task(self, task_id: str) -> AgentTask | None:
        with self._session_factory() as db:
            return db.scalar(select(AgentTask).where(AgentTask.task_id == task_id))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        agent_type: str | None = None,
        session_id: str | None = None,
        team_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentTask], int]:
        with self._session_factory() as db:
            filters = []
            if status:
                filters.append(AgentTask.status == status)
            if agent_type:
                filters.append(AgentTask.agent_type == agent_type)
            if session_id:
                filters.append(AgentTask.session_id == session_id)
            if team_name:
                filters.append(AgentTask.team_name == team_name)

            query: Select[tuple[AgentTask]] = select(AgentTask)
            count_query = select(func.count(AgentTask.id))
            if filters:
                query = query.where(*filters)
                count_query = count_query.where(*filters)

            query = query.order_by(AgentTask.created_at.desc()).limit(limit).offset(offset)
            total = db.scalar(count_query) or 0
            tasks = list(db.scalars(query).all())
            return tasks, int(total)

    def delete_task(self, task_id: str) -> bool:
        with self._session_factory() as db:
            task = db.scalar(select(AgentTask).where(AgentTask.task_id == task_id))
            if task is None:
                return False
            db.delete(task)
            db.commit()
            return True


agent_task_service = AgentTaskService()

