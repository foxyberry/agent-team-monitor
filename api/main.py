from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect

from api.database import init_db
from api.realtime import realtime_hub
from api.routers import (
    agent_chat_router,
    agent_graph_router,
    agent_presence_router,
    agent_task_router,
    integrations_router,
)

app = FastAPI(title="Agent Task Tracking API", version="0.1.0")
app.include_router(agent_task_router)
app.include_router(agent_chat_router)
app.include_router(agent_graph_router)
app.include_router(agent_presence_router)
app.include_router(integrations_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ui")
def office_ui() -> FileResponse:
    html = Path(__file__).resolve().parent / "static" / "office.html"
    return FileResponse(str(html))


@app.websocket("/ws/office")
async def office_ws(websocket: WebSocket) -> None:
    await realtime_hub.connect(websocket)
    try:
        while True:
            # Keep alive: client may send any ping payload.
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_hub.disconnect(websocket)
    except Exception:
        realtime_hub.disconnect(websocket)
