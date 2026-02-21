from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from api.services.agent_chat_service import agent_chat_service
from api.services.agent_presence_service import agent_presence_service
from api.schemas.agent_presence import PresenceUpsertRequest

DEFAULT_AGENT_OFFICE_STATUS_URL = os.getenv(
    "AGENT_OFFICE_STATUS_URL",
    "http://127.0.0.1:8766/api/agent-office/status",
)


@dataclass
class SyncResult:
    source_url: str
    projects: int
    agents_seen: int
    presence_upserts: int
    chat_messages: int


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=5) as res:
        body = res.read().decode("utf-8", errors="ignore")
    data = json.loads(body)
    return data if isinstance(data, dict) else {}


def _map_presence_state(raw: str) -> str:
    if raw in ("active", "working"):
        return "active"
    if raw in ("waiting_input", "idle"):
        return "idle"
    return "offline"


class AgentOfficeSyncService:
    def sync(self, source_url: str | None = None) -> SyncResult:
        url = source_url or DEFAULT_AGENT_OFFICE_STATUS_URL
        payload = _fetch_json(url)
        projects = payload.get("projects", [])

        agents_seen = 0
        presence_upserts = 0
        chat_messages = 0

        for proj in projects:
            proj_name = str(proj.get("name") or proj.get("id") or "unknown")
            status_data = proj.get("statusData", {}) if isinstance(proj, dict) else {}
            agents = status_data.get("agents", {}) if isinstance(status_data, dict) else {}
            for agent_name, agent_row in agents.items():
                agents_seen += 1
                status = (agent_row.get("status", {}) if isinstance(agent_row, dict) else {}).get("state", "idle")
                agent_presence_service.upsert(
                    PresenceUpsertRequest(
                        agent_name=f"{proj_name}:{agent_name}",
                        agent_type=agent_name,
                        team_name=proj_name,
                        state=_map_presence_state(str(status)),
                    )
                )
                presence_upserts += 1

            # Emit one system summary line per project for quick operator visibility.
            summary = status_data.get("summary", {}) if isinstance(status_data, dict) else {}
            if summary:
                msg = (
                    f"[sync] {proj_name} "
                    f"active={summary.get('active', 0)} "
                    f"working={summary.get('working', 0)} "
                    f"waiting={summary.get('waiting_input', 0)} "
                    f"idle={summary.get('idle', 0)} "
                    f"sleeping={summary.get('sleeping', 0)}"
                )
                agent_chat_service.create_message(
                    room_key=proj_name,
                    sender_type="system",
                    sender_name="sync-bot",
                    session_id=None,
                    team_name=proj_name,
                    message=msg,
                    metadata_json={"event": "agent_office.sync"},
                )
                chat_messages += 1

        return SyncResult(
            source_url=url,
            projects=len(projects),
            agents_seen=agents_seen,
            presence_upserts=presence_upserts,
            chat_messages=chat_messages,
        )


agent_office_sync_service = AgentOfficeSyncService()

