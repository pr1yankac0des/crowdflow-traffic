"""
models/schemas.py

Shared data contracts. Every service speaks these shapes so the CV module,
routing module, emergency module, and websocket layer can be developed and
swapped independently without breaking each other.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    CONGESTION = "congestion"
    STALLED_VEHICLE = "stalled_vehicle"
    POSSIBLE_COLLISION = "possible_collision"
    ROAD_CLOSURE = "road_closure"


class Detection(BaseModel):
    """A single bounding box from the CV model for one frame."""
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class FrameAnalysis(BaseModel):
    """Output of running the CV pipeline on a single camera frame."""
    zone_id: str
    timestamp: datetime
    vehicle_count: int
    density: float = Field(ge=0, le=1, description="Fraction of ROI area occupied by vehicles")
    avg_motion: float = Field(description="0 = fully stopped, 1 = free-flowing, relative scale")
    overlap_score: float = Field(ge=0, le=1, description="Bounding-box overlap heuristic, used as a collision proxy")
    detections: list[Detection] = []


class CongestionScore(BaseModel):
    zone_id: str
    score: float = Field(ge=0, le=100, description="0 = empty road, 100 = gridlock")
    severity: SeverityLevel
    vehicle_count: int
    avg_motion: float
    updated_at: datetime


class Incident(BaseModel):
    id: str
    zone_id: str
    type: IncidentType
    severity: SeverityLevel
    lat: float
    lon: float
    congestion_score: float
    detected_at: datetime
    estimated_clearance_minutes: float
    recommended_units: "DispatchRecommendation"
    status: str = "active"  # active | clearing | resolved


class DispatchRecommendation(BaseModel):
    response_level: int = Field(ge=1, le=3)
    traffic_police: int
    ambulance: int
    fire_rescue: int
    tow_trucks: int
    rationale: str


Incident.model_rebuild()


class ZoneState(BaseModel):
    zone_id: str
    name: str
    lat: float
    lon: float
    congestion: CongestionScore


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    priority: str = "fastest"  # fastest | avoid_congestion | emergency


class RouteStep(BaseModel):
    lat: float
    lon: float
    zone_id: Optional[str] = None


class RouteResponse(BaseModel):
    priority: str
    distance_km: float
    estimated_minutes: float
    congestion_adjusted: bool
    path: list[RouteStep]
    avoided_zones: list[str] = []


class HeatmapPoint(BaseModel):
    lat: float
    lon: float
    intensity: float = Field(ge=0, le=1)


class SystemSnapshot(BaseModel):
    """Broadcast over the websocket on every simulation tick."""
    timestamp: datetime
    zones: list[ZoneState]
    incidents: list[Incident]
    heatmap: list[HeatmapPoint]
    city_avg_congestion: float
    active_incident_count: int
