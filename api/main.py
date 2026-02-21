from __future__ import annotations

from fastapi import FastAPI

from api.database import init_db
from api.routers import agent_task_router

app = FastAPI(title="Agent Task Tracking API", version="0.1.0")
app.include_router(agent_task_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

