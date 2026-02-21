#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

API_BASE = os.getenv("AGENT_TASK_API_BASE", "http://127.0.0.1:8765")
TIMEOUT_ARGS = ["--connect-timeout", "2", "--max-time", "5"]


def _extract_task_id(tool_name: str, tool_input: dict[str, Any], tool_response: Any) -> str | None:
    if tool_name == "TaskCreate":
        if isinstance(tool_response, dict):
            return tool_response.get("task_id") or tool_response.get("id")
        return None
    if tool_name == "TaskUpdate":
        return tool_input.get("task_id") or tool_input.get("taskId")
    return None


def _spawn_curl(method: str, url: str, payload: dict[str, Any]) -> None:
    cmd = [
        "curl",
        "-sS",
        "-X",
        method,
        *TIMEOUT_ARGS,
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(payload, ensure_ascii=False),
        url,
    ]
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return 0
        event = json.loads(raw)
    except Exception:
        return 0

    tool_name = event.get("tool_name")
    if tool_name not in ("TaskCreate", "TaskUpdate"):
        return 0

    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    tool_response = event.get("tool_response")
    session_id = event.get("session_id")
    task_id = _extract_task_id(tool_name, tool_input, tool_response)
    if not task_id:
        return 0

    if tool_name == "TaskCreate":
        payload = {
            "task_id": task_id,
            "session_id": session_id,
            "agent_type": tool_input.get("agent_type"),
            "team_name": tool_input.get("team_name"),
            "subject": tool_input.get("subject") or tool_input.get("title") or f"Task {task_id}",
            "description": tool_input.get("description"),
            "status": tool_input.get("status", "pending"),
            "metadata_json": {"source": "post_tool_use_hook"},
        }
        _spawn_curl("POST", f"{API_BASE}/api/agent-tasks", payload)
        return 0

    payload = {
        "task_id": task_id,
        "session_id": session_id,
        "status": tool_input.get("status"),
        "subject": tool_input.get("subject"),
        "description": tool_input.get("description"),
        "files_modified": tool_input.get("files_modified"),
        "metadata_json": {"source": "post_tool_use_hook_update"},
    }
    _spawn_curl("PUT", f"{API_BASE}/api/agent-tasks/{task_id}", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
