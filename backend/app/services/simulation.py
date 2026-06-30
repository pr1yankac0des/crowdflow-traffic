"""
services/simulation.py

The live "world state" of the demo city. Owns a set of zones with smoothly
drifting congestion (random walk, not white noise, so the dashboard reads
as traffic rather than static), spawns/clears incidents probabilistically
weighted by how congested a zone already is, and pushes every update into
routing.py so route requests are always reacting to the current state.

In production, this module's job is taken over by real camera feeds calling
cv_detection.analyze_frame() on a schedule per camera/zone. The rest of the
pipeline (scoring -> incident lifecycle -> dispatch -> routing weights ->
websocket broadcast) is unchanged - `tick()` below is the seam.
"""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.schemas import (
    CongestionScore, HeatmapPoint, Incident, IncidentType, SeverityLevel,
    SystemSnapshot, ZoneState,
)
from app.services import congestion, cv_detection, emergency, routing

settings = get_settings()


class _ZoneWorldState:
    def __init__(self, zone_id: str, name: str, lat: float, lon: float):
        self.zone_id = zone_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.base_density = random.uniform(0.15, 0.45)

    def step(self) -> CongestionScore:
        drift = random.uniform(-0.06, 0.07)  # slight upward bias, like real rush-hour drift
        self.base_density = max(0.05, min(0.95, self.base_density + drift * 0.3))
        frame = cv_detection.simulate_frame_analysis(self.zone_id, self.base_density, drift)
        return congestion.score_frame(frame)


class SimulationEngine:
    def __init__(self):
        self.zones: dict[str, _ZoneWorldState] = {}
        self.incidents: dict[str, Incident] = {}
        self._build_zones()

    def _build_zones(self):
        for zone_id, (name, lat, lon) in routing.get_zone_anchors().items():
            self.zones[zone_id] = _ZoneWorldState(zone_id, name, lat, lon)

    def tick(self) -> SystemSnapshot:
        zone_states: list[ZoneState] = []
        heatmap: list[HeatmapPoint] = []
        total_score = 0.0

        for zone in self.zones.values():
            score = zone.step()
            routing.update_zone_congestion(zone.zone_id, score.score)
            zone_states.append(ZoneState(
                zone_id=zone.zone_id, name=zone.name, lat=zone.lat, lon=zone.lon, congestion=score,
            ))
            heatmap.append(HeatmapPoint(lat=zone.lat, lon=zone.lon, intensity=score.score / 100.0))
            total_score += score.score

            self._maybe_spawn_incident(zone, score)

        self._progress_incidents()

        city_avg = round(total_score / len(self.zones), 1) if self.zones else 0.0
        active = [i for i in self.incidents.values() if i.status != "resolved"]

        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            zones=zone_states,
            incidents=list(self.incidents.values()),
            heatmap=heatmap,
            city_avg_congestion=city_avg,
            active_incident_count=len(active),
        )

    def _maybe_spawn_incident(self, zone: _ZoneWorldState, score: CongestionScore):
        zone_has_active = any(
            inc.zone_id == zone.zone_id and inc.status != "resolved" for inc in self.incidents.values()
        )
        if zone_has_active:
            return
        if len([i for i in self.incidents.values() if i.status != "resolved"]) >= settings.simulation_num_incidents_max:
            return

        # Spawn probability scales with severity - critical zones are far
        # more likely to be flagged than free-flowing ones.
        spawn_chance = {
            SeverityLevel.LOW: 0.0,
            SeverityLevel.MODERATE: 0.01,
            SeverityLevel.HIGH: 0.05,
            SeverityLevel.CRITICAL: 0.12,
        }[score.severity]

        if random.random() > spawn_chance:
            return

        incident_type = random.choices(
            [IncidentType.CONGESTION, IncidentType.STALLED_VEHICLE, IncidentType.POSSIBLE_COLLISION],
            weights=[0.55, 0.30, 0.15],
        )[0]
        clearance = congestion.estimate_clearance_minutes(score.score, incident_type.value)
        dispatch = emergency.recommend_dispatch(incident_type, score.severity)

        incident = Incident(
            id=f"INC-{uuid.uuid4().hex[:6].upper()}",
            zone_id=zone.zone_id,
            type=incident_type,
            severity=score.severity,
            lat=zone.lat + random.uniform(-0.0008, 0.0008),
            lon=zone.lon + random.uniform(-0.0008, 0.0008),
            congestion_score=score.score,
            detected_at=datetime.now(timezone.utc),
            estimated_clearance_minutes=clearance,
            recommended_units=dispatch,
            status="active",
        )
        self.incidents[incident.id] = incident

    def _progress_incidents(self):
        for incident in list(self.incidents.values()):
            if incident.status == "resolved":
                continue
            age_minutes = (datetime.now(timezone.utc) - incident.detected_at).total_seconds() / 60
            if age_minutes >= incident.estimated_clearance_minutes * 0.6 and incident.status == "active":
                incident.status = "clearing"
            if age_minutes >= incident.estimated_clearance_minutes:
                incident.status = "resolved"
