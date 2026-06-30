"""
websocket/manager.py

Minimal connection pool for broadcasting SystemSnapshot ticks to every
connected dashboard. No external pub/sub needed at this scale (single
backend instance) - if you outgrow one instance, swap this for a Redis
pub/sub channel without changing the API surface used by routes.py.
"""
from __future__ import annotations
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast_json(self, payload: dict):
        stale: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
