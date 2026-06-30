"""
state.py

Single shared SimulationEngine instance. Kept separate from main.py so
api/routes.py can import it without circular-importing the FastAPI app.
"""
from __future__ import annotations
from app.services.simulation import SimulationEngine

_engine: SimulationEngine | None = None


def get_engine() -> SimulationEngine:
    global _engine
    if _engine is None:
        _engine = SimulationEngine()
    return _engine
