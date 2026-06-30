"""
main.py

FastAPI entrypoint. On startup, kicks off a background task that ticks the
simulation engine every `simulation_tick_seconds` and broadcasts the
resulting SystemSnapshot to every connected websocket client. REST routes
in api/routes.py cover route optimization and first-paint snapshots.

Run locally:
    uvicorn app.main:app --reload --port 8000

Run in Docker: see Dockerfile / docker-compose.yml at the project root.
"""
from __future__ import annotations
import asyncio
import contextlib
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.state import get_engine
from app.websocket.manager import manager

settings = get_settings()


async def _simulation_loop():
    engine = get_engine()
    while True:
        snapshot = engine.tick()
        await manager.broadcast_json(json.loads(snapshot.model_dump_json()))
        await asyncio.sleep(settings.simulation_tick_seconds)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_simulation_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def health():
    return {"status": "ok", "app": settings.app_name, "demo_mode": settings.demo_mode}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send an immediate snapshot so the client doesn't wait for the
        # next tick on first connect.
        snapshot = get_engine().tick()
        await websocket.send_json(json.loads(snapshot.model_dump_json()))
        while True:
            # We don't expect inbound messages on this channel, but keep
            # the receive loop alive to detect client disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
