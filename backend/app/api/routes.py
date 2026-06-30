"""
api/routes.py

REST surface for everything that isn't the live websocket feed:
  - route optimization (graph routing, three priority modes)
  - on-demand snapshot (zones, incidents, heatmap) for first paint before
    the websocket connects
  - a real CV endpoint for uploaded frames, for when demo_mode=False
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.models.schemas import FrameAnalysis, RouteRequest, RouteResponse, SystemSnapshot
from app.services import routing
from app.state import get_engine

router = APIRouter(prefix="/api")
settings = get_settings()


@router.get("/snapshot", response_model=SystemSnapshot)
def get_snapshot():
    """One-shot current state - used by the frontend for first paint
    before the websocket stream takes over."""
    return get_engine().tick()


@router.post("/route", response_model=RouteResponse)
def post_route(req: RouteRequest):
    if req.priority not in ("fastest", "avoid_congestion", "emergency"):
        raise HTTPException(400, "priority must be one of: fastest, avoid_congestion, emergency")
    return routing.compute_route(req)


@router.post("/cv/analyze-frame", response_model=FrameAnalysis)
async def analyze_frame_upload(zone_id: str, roi_area_px: float, file: UploadFile = File(...)):
    """
    Production endpoint: POST a camera frame (jpg/png) for a given zone.
    Disabled in demo_mode to avoid requiring torch/ultralytics + model
    weights just to boot the demo.
    """
    if settings.demo_mode:
        raise HTTPException(
            409,
            "Server is running in DEMO_MODE (simulated traffic feed). "
            "Set CROWDFLOW_DEMO_MODE=False and install ultralytics/torch to enable real frame analysis.",
        )
    import cv2
    import numpy as np
    from app.services import cv_detection

    contents = await file.read()
    img_array = np.frombuffer(contents, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Could not decode uploaded image")
    return cv_detection.analyze_frame(zone_id, frame, roi_area_px)
