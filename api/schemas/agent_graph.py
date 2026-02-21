from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    status: str
    agent_type: str | None
    team_name: str | None
    session_id: str | None
    metadata: dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

