"""
core/config.py

Central configuration for CrowdFlow Traffic.

Design decision: every "real" integration (YOLO inference, OSMnx/Overpass
road graphs, live camera ingestion) has a DEMO_MODE fallback that runs on
pure Python with no GPU, no API keys, and no internet access. This lets the
whole system boot and look fully alive on a laptop in under a minute, while
every module that touches real infrastructure is isolated behind a single
toggle so swapping in production data sources later is a config change, not
a rewrite.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "CrowdFlow Traffic"
    environment: str = "development"

    # When True (default), CV + routing + traffic feed run on synthetic /
    # simulated data so the full stack is demoable with zero external
    # dependencies. Set to False once real camera feeds / OSM data / a
    # trained model are wired up.
    demo_mode: bool = True

    # CV
    yolo_model_path: str = "yolov8n.pt"          # Ultralytics auto-downloads this
    yolo_confidence_threshold: float = 0.35
    congestion_density_high: float = 0.65         # fraction of ROI considered "high density"
    congestion_density_critical: float = 0.85

    # Routing
    osm_place_name: str = "Bengaluru, India"      # used when demo_mode=False
    routing_cache_path: str = "data/graph_cache.pkl"

    # Realtime
    simulation_tick_seconds: float = 2.0
    simulation_num_incidents_max: int = 5

    # CORS
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_prefix = "CROWDFLOW_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
