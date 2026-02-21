from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models.agent_task import AgentTask
from api.models.agent_task_edge import AgentTaskEdge
from api.schemas.agent_graph import GraphEdge, GraphNode


class AgentGraphService:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    def add_edge(self, parent_task_id: str, child_task_id: str, edge_type: str = "spawned") -> AgentTaskEdge | None:
        if not parent_task_id or not child_task_id or parent_task_id == child_task_id:
            return None
        with self._session_factory() as db:
            exists = db.scalar(
                select(AgentTaskEdge).where(
                    AgentTaskEdge.parent_task_id == parent_task_id,
                    AgentTaskEdge.child_task_id == child_task_id,
                    AgentTaskEdge.edge_type == edge_type,
                )
            )
            if exists:
                return exists
            row = AgentTaskEdge(parent_task_id=parent_task_id, child_task_id=child_task_id, edge_type=edge_type)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def get_graph(self, session_id: str | None = None, team_name: str | None = None) -> tuple[list[GraphNode], list[GraphEdge]]:
        with self._session_factory() as db:
            task_query = select(AgentTask)
            if session_id:
                task_query = task_query.where(AgentTask.session_id == session_id)
            if team_name:
                task_query = task_query.where(AgentTask.team_name == team_name)
            tasks = list(db.scalars(task_query).all())
            task_ids = {t.task_id for t in tasks}

            edge_query = select(AgentTaskEdge)
            edges_raw = list(db.scalars(edge_query).all())
            edges = [
                e
                for e in edges_raw
                if (not task_ids or (e.parent_task_id in task_ids or e.child_task_id in task_ids))
            ]

            nodes = [
                GraphNode(
                    id=t.task_id,
                    label=t.subject,
                    status=t.status,
                    agent_type=t.agent_type,
                    team_name=t.team_name,
                    session_id=t.session_id,
                    metadata=t.metadata_json or {},
                )
                for t in tasks
            ]
            graph_edges = [
                GraphEdge(
                    id=f"{e.parent_task_id}->{e.child_task_id}:{e.edge_type}",
                    source=e.parent_task_id,
                    target=e.child_task_id,
                    edge_type=e.edge_type,
                )
                for e in edges
            ]
            return nodes, graph_edges


agent_graph_service = AgentGraphService()

