from __future__ import annotations

from fastapi import APIRouter, Query

from api.schemas.agent_graph import GraphResponse
from api.services.agent_graph_service import agent_graph_service

router = APIRouter(prefix="/api/agent-graph", tags=["agent-graph"])


@router.get("", response_model=GraphResponse)
def get_graph(
    session_id: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
) -> GraphResponse:
    nodes, edges = agent_graph_service.get_graph(session_id=session_id, team_name=team_name)
    return GraphResponse(nodes=nodes, edges=edges)

