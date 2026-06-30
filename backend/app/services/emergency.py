"""
services/emergency.py

Maps an incident's type + severity into a dispatch recommendation: how many
units of each kind, and at what response level. This is a transparent rules
table, not a trained model - dispatch decisions need to be auditable and
explainable to a human operator, so a heuristic is the right tool here even
in a "production" version. Tune the table with real ops data over time.
"""
from __future__ import annotations

from app.models.schemas import DispatchRecommendation, IncidentType, SeverityLevel


def recommend_dispatch(incident_type: IncidentType, severity: SeverityLevel) -> DispatchRecommendation:
    if incident_type == IncidentType.POSSIBLE_COLLISION:
        if severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH):
            return DispatchRecommendation(
                response_level=3,
                traffic_police=2,
                ambulance=2,
                fire_rescue=1,
                tow_trucks=1,
                rationale="Possible collision with high surrounding congestion: "
                          "treat as multi-unit response until human-confirmed otherwise.",
            )
        return DispatchRecommendation(
            response_level=2,
            traffic_police=1,
            ambulance=1,
            fire_rescue=0,
            tow_trucks=1,
            rationale="Possible collision, moderate severity: send ambulance + traffic "
                      "control, hold fire/rescue unless escalated.",
        )

    if incident_type == IncidentType.STALLED_VEHICLE:
        return DispatchRecommendation(
            response_level=1,
            traffic_police=1,
            ambulance=0,
            fire_rescue=0,
            tow_trucks=1,
            rationale="Stalled vehicle: traffic control plus tow support to restore flow.",
        )

    if incident_type == IncidentType.ROAD_CLOSURE:
        return DispatchRecommendation(
            response_level=2,
            traffic_police=2,
            ambulance=0,
            fire_rescue=0,
            tow_trucks=0,
            rationale="Road closure: traffic control for diversion management at both ends.",
        )

    # Plain congestion, no discrete incident
    if severity == SeverityLevel.CRITICAL:
        return DispatchRecommendation(
            response_level=1,
            traffic_police=2,
            ambulance=0,
            fire_rescue=0,
            tow_trucks=0,
            rationale="Severe congestion with no detected incident cause: deploy traffic "
                      "police for manual signal control at the bottleneck.",
        )
    return DispatchRecommendation(
        response_level=1,
        traffic_police=0,
        ambulance=0,
        fire_rescue=0,
        tow_trucks=0,
        rationale="Congestion within manageable range: monitor only, no dispatch needed.",
    )
