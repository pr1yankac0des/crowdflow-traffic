"""
services/congestion.py

Turns raw per-frame CV measurements into a 0-100 congestion score and a
severity bucket. This module is deliberately pure-Python / pure-math with
no model dependencies, so it is identical whether the upstream detection
came from a real YOLO model or the simulator - and it's trivial to unit
test or replace with a trained regressor later if historical ground-truth
clearance data is ever collected.

Scoring model:
    score = density_component + stoppage_component + collision_component

  - density_component   : how full the road is (0-55 pts)
  - stoppage_component   : how stopped traffic is, i.e. density without
                            flow is worse than density with flow (0-30 pts)
  - collision_component  : bounding-box overlap anomaly, a proxy signal for
                            "vehicles unnaturally on top of each other"
                            (0-15 pts)
"""
from __future__ import annotations
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.schemas import CongestionScore, FrameAnalysis, SeverityLevel

settings = get_settings()


def score_frame(frame: FrameAnalysis) -> CongestionScore:
    density_component = min(frame.density, 1.0) * 55
    stoppage_component = (1.0 - min(frame.avg_motion, 1.0)) * min(frame.density, 1.0) * 30
    collision_component = min(frame.overlap_score, 1.0) * 15

    score = round(density_component + stoppage_component + collision_component, 1)
    score = max(0.0, min(100.0, score))

    return CongestionScore(
        zone_id=frame.zone_id,
        score=score,
        severity=_severity_for_score(score),
        vehicle_count=frame.vehicle_count,
        avg_motion=frame.avg_motion,
        updated_at=datetime.now(timezone.utc),
    )


def _severity_for_score(score: float) -> SeverityLevel:
    if score >= 80:
        return SeverityLevel.CRITICAL
    if score >= 60:
        return SeverityLevel.HIGH
    if score >= 30:
        return SeverityLevel.MODERATE
    return SeverityLevel.LOW


def estimate_clearance_minutes(score: float, incident_type: str) -> float:
    """
    Heuristic ETA-to-clear model. Base clearance time by incident type,
    scaled by how severe the congestion around it is. This is intentionally
    a transparent formula rather than a black box - swap in a regression
    model (scikit-learn) once real historical "time logged -> time
    resolved" pairs exist; the function signature stays the same.
    """
    base_minutes = {
        "congestion": 8.0,
        "stalled_vehicle": 12.0,
        "possible_collision": 25.0,
        "road_closure": 45.0,
    }.get(incident_type, 10.0)

    severity_multiplier = 0.6 + (score / 100.0) * 1.4  # 0.6x at score=0, 2.0x at score=100
    return round(base_minutes * severity_multiplier, 1)
