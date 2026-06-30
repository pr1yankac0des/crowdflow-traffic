"""
scripts/build_osm_cache.py

One-time setup script: fetches the real Bengaluru road network from
OpenStreetMap (via OSMnx -> the public Overpass API), processes it into
this project's graph schema (same shape the synthetic demo network uses:
lat/lon, zone_id, zone_name on nodes; dist_km, base_time,
congestion_multiplier on edges), and caches it to disk as a pickle.

Run this ONCE. After that, set CROWDFLOW_DEMO_MODE=False and start the
backend normally - routing.py just loads the cache file on every startup
instead of re-fetching (the public Overpass API is free but rate-limited
and not meant for repeated bulk queries on every server restart).

Requires the production deps (commented out in requirements.txt by
default):
    pip install osmnx geopandas

Usage (from the backend/ directory):
    python scripts/build_osm_cache.py

Expect this to take anywhere from 30 seconds to a few minutes depending on
Overpass server load - the bounding box covers all 24 named zones plus a
buffer, which is a meaningful chunk of central Bengaluru. Needs a real
internet connection; if it times out, that's usually Overpass being under
load, not your setup - wait a minute and try again.
"""
from __future__ import annotations
import pickle
import sys
from pathlib import Path

# allow running as `python scripts/build_osm_cache.py` from the backend/ dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import networkx as nx

from app.core.config import get_settings
from app.services.routing import ZONE_ANCHORS, _haversine_km

settings = get_settings()

# Fallback free-flow speed by OSM road classification, used whenever a
# specific maxspeed tag is missing or doesn't parse cleanly - real-world
# OSM maxspeed tagging is inconsistent enough that a fallback table is
# necessary, not optional.
HIGHWAY_SPEED_KMH = {
    "motorway": 70, "motorway_link": 50,
    "trunk": 55, "trunk_link": 40,
    "primary": 45, "primary_link": 35,
    "secondary": 35, "secondary_link": 30,
    "tertiary": 30, "tertiary_link": 25,
    "residential": 25, "living_street": 15,
    "unclassified": 25, "service": 15,
}
DEFAULT_SPEED_KMH = 30


def _edge_speed_kmh(data: dict) -> float:
    maxspeed = data.get("maxspeed")
    if maxspeed:
        candidate = maxspeed[0] if isinstance(maxspeed, list) else maxspeed
        digits = "".join(ch for ch in str(candidate) if ch.isdigit() or ch == ".")
        if digits:
            try:
                return float(digits)
            except ValueError:
                pass

    highway = data.get("highway")
    if isinstance(highway, list):
        highway = highway[0] if highway else None
    return HIGHWAY_SPEED_KMH.get(highway, DEFAULT_SPEED_KMH)


def main():
    try:
        import osmnx as ox
    except ImportError:
        print("ERROR: osmnx is not installed. Run: pip install osmnx geopandas")
        sys.exit(1)

    lats = [lat for _, lat, _ in ZONE_ANCHORS]
    lons = [lon for _, _, lon in ZONE_ANCHORS]
    pad = 0.035  # ~3.9km buffer beyond the outermost anchors in each direction
    bbox = (min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad)  # (west, south, east, north)

    print(f"Fetching real road network for bbox {bbox} from OpenStreetMap...")
    print("This calls the public Overpass API and can take anywhere from 30s to a few minutes.")
    raw = ox.graph_from_bbox(bbox=bbox, network_type="drive", simplify=True)
    print(f"Fetched {raw.number_of_nodes()} nodes, {raw.number_of_edges()} edges (raw, directed).")

    # Collapse the directed multigraph OSMnx returns into a simple
    # undirected graph - matches the schema every other module in this
    # project expects (sacrifices one-way-street realism for consistency
    # with the rest of the codebase, which is built on nx.Graph throughout).
    undirected = nx.Graph(raw)
    print(f"Collapsed to {undirected.number_of_nodes()} nodes, {undirected.number_of_edges()} edges (undirected).")

    if not nx.is_connected(undirected):
        components = list(nx.connected_components(undirected))
        largest = max(components, key=len)
        print(f"Graph has {len(components)} disconnected components - keeping only the largest "
              f"({len(largest)} of {undirected.number_of_nodes()} nodes).")
        undirected = undirected.subgraph(largest).copy()

    print("Assigning every real intersection to its nearest named zone...")
    g = nx.Graph()
    for node_id, data in undirected.nodes(data=True):
        lat, lon = data["y"], data["x"]  # osmnx convention: x=lon, y=lat
        nearest_idx = min(
            range(len(ZONE_ANCHORS)),
            key=lambda i: _haversine_km(lat, lon, ZONE_ANCHORS[i][1], ZONE_ANCHORS[i][2]),
        )
        zone_name, anchor_lat, anchor_lon = ZONE_ANCHORS[nearest_idx]
        g.add_node(
            node_id, lat=lat, lon=lon, zone_id=f"zone_{nearest_idx}", zone_name=zone_name,
            anchor_lat=anchor_lat, anchor_lon=anchor_lon,
        )

    print("Computing real-world edge weights from OSM road classification...")
    for u, v, data in undirected.edges(data=True):
        dist_km = data.get("length", 0) / 1000.0
        speed_kmh = _edge_speed_kmh(data)
        base_time = (dist_km / speed_kmh) * 60 if speed_kmh > 0 else 1.0
        g.add_edge(u, v, dist_km=dist_km, base_time=base_time, congestion_multiplier=1.0)

    zone_counts: dict[str, int] = {}
    for _, data in g.nodes(data=True):
        zone_counts[data["zone_name"]] = zone_counts.get(data["zone_name"], 0) + 1
    print("\nNodes per zone:")
    for name, count in sorted(zone_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name}: {count}")

    all_names = {name for name, _, _ in ZONE_ANCHORS}
    missing = all_names - set(zone_counts)
    if missing:
        print(f"\nWARNING: {len(missing)} zone(s) got no real nodes assigned "
              f"(likely outside the fetched bbox, or in a disconnected component that got dropped): {sorted(missing)}")
        print("Those zones will behave oddly in the simulation. Consider widening `pad` above and re-running.")

    cache_path = Path(settings.routing_cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(g, f)
    print(f"\nSaved {g.number_of_nodes()} nodes / {g.number_of_edges()} edges to {cache_path}")
    print("Now set CROWDFLOW_DEMO_MODE=False and start the backend normally - it will load this cache file.")


if __name__ == "__main__":
    main()
