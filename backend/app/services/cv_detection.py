"""
services/cv_detection.py

Computer vision pipeline: takes a camera frame, returns vehicle detections
plus the derived signals congestion.py needs (density, motion, overlap).

IMPORTANT - be honest about what this actually detects:
  Ultralytics YOLOv8 has no public, reliable pretrained class for "accident".
  There is no off-the-shelf free model that reliably says "this is a crash"
  from a single frame. What this module does instead, and what is realistic
  on a free tier, is:

    1. Detect vehicles/pedestrians per frame (YOLOv8n, pretrained on COCO -
       classes: car, truck, bus, motorcycle, person, bicycle).
    2. Track density over the ROI -> feeds the congestion score.
    3. Estimate motion via frame-to-frame centroid displacement -> "is
       traffic actually stopped, or just dense".
    4. Flag abnormal bounding-box overlap between vehicles as a heuristic
       *proxy* for a possible collision worth a human operator's attention
       - NOT a verified accident classification.

  For a real accident-detection model, the upgrade path is: collect/label
  footage (e.g. public datasets such as CADP or Kaggle's CCTV accident sets),
  fine-tune a YOLOv8 classification or a two-stage (detect + temporal CNN/
  LSTM) model on accident vs. non-accident clips, then swap that model in
  here behind the same `analyze_frame` function signature. The rest of the
  system (scoring, routing, dispatch) does not need to change.

Heavy ML deps (torch, ultralytics) are imported lazily inside
`_load_model()` so the rest of the backend runs without them when
DEMO_MODE=True.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import random

import numpy as np

from app.core.config import get_settings
from app.models.schemas import Detection, FrameAnalysis

settings = get_settings()

_VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
_model = None
_prev_centroids: dict[str, list[tuple[float, float]]] = {}


def _load_model():
    """Lazily import + load YOLOv8. Only called when demo_mode is False."""
    global _model
    if _model is None:
        from ultralytics import YOLO  # heavy import, kept out of module scope
        _model = YOLO(settings.yolo_model_path)
    return _model


def analyze_frame(zone_id: str, frame: "np.ndarray", roi_area_px: float) -> FrameAnalysis:
    """
    Real pipeline entry point for production use: pass a decoded video
    frame (e.g. from OpenCV / RTSP) and the pixel area of the region of
    interest (the road segment) for that camera.
    """
    model = _load_model()
    results = model(frame, verbose=False)[0]

    detections: list[Detection] = []
    occupied_px = 0.0
    centroids: list[tuple[float, float]] = []

    for box in results.boxes:
        cls_name = model.names[int(box.cls[0])]
        conf = float(box.conf[0])
        if conf < settings.yolo_confidence_threshold:
            continue
        if cls_name not in _VEHICLE_CLASSES:
            continue

        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
        detections.append(Detection(label=cls_name, confidence=conf, x1=x1, y1=y1, x2=x2, y2=y2))
        occupied_px += max(0.0, (x2 - x1) * (y2 - y1))
        centroids.append(((x1 + x2) / 2, (y1 + y2) / 2))

    density = min(occupied_px / roi_area_px, 1.0) if roi_area_px > 0 else 0.0
    avg_motion = _estimate_motion(zone_id, centroids)
    overlap_score = _bbox_overlap_score(detections)

    return FrameAnalysis(
        zone_id=zone_id,
        timestamp=datetime.now(timezone.utc),
        vehicle_count=len(detections),
        density=density,
        avg_motion=avg_motion,
        overlap_score=overlap_score,
        detections=detections,
    )


def _estimate_motion(zone_id: str, centroids: list[tuple[float, float]]) -> float:
    """Cheap frame-to-frame displacement proxy for 'is traffic moving'."""
    prev = _prev_centroids.get(zone_id, [])
    _prev_centroids[zone_id] = centroids
    if not prev or not centroids:
        return 1.0  # nothing to compare yet; assume free-flowing

    n = min(len(prev), len(centroids))
    if n == 0:
        return 1.0
    displacement = np.mean([
        np.hypot(centroids[i][0] - prev[i][0], centroids[i][1] - prev[i][1])
        for i in range(n)
    ])
    return float(np.clip(displacement / 40.0, 0.0, 1.0))  # 40px ~ "clearly moving"


def _bbox_overlap_score(detections: list[Detection]) -> float:
    """Fraction of vehicle pairs with meaningfully overlapping boxes."""
    if len(detections) < 2:
        return 0.0
    overlaps = 0
    pairs = 0
    for i in range(len(detections)):
        for j in range(i + 1, len(detections)):
            pairs += 1
            if _iou(detections[i], detections[j]) > 0.15:
                overlaps += 1
    return overlaps / pairs if pairs else 0.0


def _iou(a: Detection, b: Detection) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Demo-mode synthetic frame generator
# ---------------------------------------------------------------------------
def simulate_frame_analysis(zone_id: str, base_density: float, drift: float) -> FrameAnalysis:
    """
    Produces a plausible FrameAnalysis without any camera, model, or GPU.
    `base_density` is nudged by `drift` each tick (random walk) by the
    simulation engine so zones evolve smoothly instead of jittering randomly,
    which is what makes the live dashboard feel like real traffic rather
    than noise.
    """
    density = float(np.clip(base_density + drift, 0.02, 0.98))
    vehicle_count = int(density * random.randint(18, 30))
    # Stopped traffic correlates with high density but isn't identical to it
    avg_motion = float(np.clip(1.0 - density + random.uniform(-0.15, 0.15), 0.0, 1.0))
    overlap_score = max(0.0, (density - 0.7) * random.uniform(0.3, 1.0)) if density > 0.7 else 0.0

    return FrameAnalysis(
        zone_id=zone_id,
        timestamp=datetime.now(timezone.utc),
        vehicle_count=vehicle_count,
        density=density,
        avg_motion=avg_motion,
        overlap_score=min(overlap_score, 1.0),
        detections=[],
    )
