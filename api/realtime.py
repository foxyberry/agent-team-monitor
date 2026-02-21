from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps(
            {
                "event_type": event_type,
                "ts": datetime.now(timezone.utc).isoformat(),
                "data": data,
            },
            ensure_ascii=False,
        )
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


realtime_hub = RealtimeHub()

