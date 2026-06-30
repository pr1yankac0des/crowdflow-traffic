"""
services/routing.py

Graph-based route optimization. NetworkX does the actual pathfinding in
both modes - the only thing that changes between demo and production is
where the graph's nodes/edges come from:

  - demo_mode=True   : a graph anchored at real city-landmark coordinates,
                        connected by a realistic sparse backbone, standing
                        in for a city's road network. Lets every routing
                        endpoint, and the frontend route optimizer, work
                        immediately with no network calls.
  - demo_mode=False  : OSMnx pulls the real drivable road network for
                        `settings.osm_place_name` from the Overpass API
                        (OpenStreetMap), cached to disk after first fetch
                        so you're not re-hitting the public Overpass
                        endpoint on every restart (it's free but rate
                        limited and not meant for repeated bulk queries -
                        see Overpass API usage policy).

Dynamic weighting: every edge carries a `base_time` (free-flow travel time)
and a `congestion_multiplier` that the simulation/CV layer updates live.
Effective edge weight = base_time * congestion_multiplier, so the same
Dijkstra call naturally re-routes around live congestion without any
special-case logic.
"""
from __future__ import annotations
import math
import pickle
import random
from functools import lru_cache
from pathlib import Path

import networkx as nx

from app.core.config import get_settings
from app.models.schemas import RouteRequest, RouteResponse, RouteStep

settings = get_settings()

EARTH_RADIUS_KM = 6371.0

# Real, approximate coordinates for each named zone. These are placed by
# general knowledge of Bengaluru's layout (north/south/east/west spread,
# rough relative distances) - good enough for a demo to look and behave
# like the real city, not surveyed to street-level precision. This is the
# single source of truth for zone identity: routing.py builds the graph
# from it, simulation.py reads names/positions from it directly instead of
# keeping its own separate list (which is what let a previous version
# silently fall out of sync).
ZONE_ANCHORS: list[tuple[str, float, float]] = [
    ("MG Road", 12.9758, 77.6045),
    ("Outer Ring Rd", 12.9350, 77.6950),
    ("Silk Board", 12.9166, 77.6228),
    ("Hebbal Flyover", 13.0358, 77.5970),
    ("KR Puram", 13.0070, 77.6960),
    ("Whitefield Main Rd", 12.9698, 77.7500),
    ("Indiranagar 100ft", 12.9716, 77.6412),
    ("Koramangala Inner Ring", 12.9352, 77.6245),
    ("Bannerghatta Rd", 12.8988, 77.5970),
    ("Electronic City Flyover", 12.8452, 77.6602),
    ("Sarjapur Rd", 12.9008, 77.6850),
    ("Marathahalli Bridge", 12.9569, 77.7011),
    ("Yeshwanthpur Jn", 13.0284, 77.5546),
    ("Tin Factory", 13.0021, 77.6608),
    ("Domlur Flyover", 12.9610, 77.6387),
    ("BTM Layout", 12.9166, 77.6101),
    ("Mysore Rd Jn", 12.9540, 77.5350),
    ("Hosur Rd", 12.9400, 77.6150),
    ("Old Airport Rd", 12.9606, 77.6499),
    ("Jayanagar 4th Block", 12.9300, 77.5828),
    ("Rajajinagar Entrance", 12.9911, 77.5520),
    ("Banashankari", 12.9251, 77.5460),
    ("ITPL Main Gate", 12.9860, 77.7320),
    ("Bellandur Jn", 12.9257, 77.6649),
]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
@lru_cache
def get_graph() -> nx.Graph:
    if settings.demo_mode:
        return _build_demo_network()
    return _load_osm_graph()


def get_zone_anchors() -> dict[str, tuple[str, float, float]]:
    """zone_id -> (name, anchor_lat, anchor_lon). Lets simulation.py (and
    anything else) read each zone's real representative point directly,
    instead of keeping a second, separately-maintained list that can drift
    out of sync with the graph."""
    return {f"zone_{i}": (name, lat, lon) for i, (name, lat, lon) in enumerate(ZONE_ANCHORS)}


def _build_demo_network(nodes_per_zone: int = 6, local_radius_deg: float = 0.0015, knn: int = 4) -> nx.Graph:
    """
    Builds a routable graph anchored at real Bengaluru landmark coordinates
    (ZONE_ANCHORS) rather than a uniform synthetic grid. Each zone gets a
    small local cluster of nodes scattered within ~150m of its real anchor
    (standing in for nearby intersections within that area), and zones are
    linked to each other via a backbone over real haversine distance: each
    zone connects to every other zone within 9km (capped at 6), falling
    back to its `knn` nearest if fewer than that many neighbors are within
    range, with a minimum-spanning-tree pass guaranteeing the whole network
    stays connected. The radius+kNN hybrid (rather than kNN alone) matters
    for route quality, not just looks: a pure sparse kNN backbone tends
    toward a near-tree shape with only one reasonable path between most
    zone pairs, so "fastest" / "avoid congestion" / "emergency" routing
    would always converge on the same answer even under heavy congestion -
    there'd be nothing for "avoid congestion" to meaningfully choose
    between. Denser local connectivity gives Dijkstra real alternatives to
    weigh, the same way real road networks have multiple redundant local
    streets but only a few arterial links between distant areas.
    """
    g = nx.Graph()
    rng = random.Random(42)  # deterministic layout across restarts; live congestion still varies via simulation.py
    zone_gateway: dict[str, str] = {}

    for zone_idx, (name, anchor_lat, anchor_lon) in enumerate(ZONE_ANCHORS):
        zone_id = f"zone_{zone_idx}"
        local_nodes = []
        for j in range(nodes_per_zone):
            node_id = f"{zone_id}_n{j}"
            lat = anchor_lat + rng.uniform(-local_radius_deg, local_radius_deg)
            lon = anchor_lon + rng.uniform(-local_radius_deg, local_radius_deg)
            g.add_node(
                node_id, lat=lat, lon=lon, zone_id=zone_id, zone_name=name,
                anchor_lat=anchor_lat, anchor_lon=anchor_lon,
            )
            local_nodes.append(node_id)
        zone_gateway[zone_id] = local_nodes[0]
        # light internal mesh so each zone isn't purely star-shaped
        for a, b in zip(local_nodes, local_nodes[1:]):
            _add_road(g, a, b)

    zone_ids = [f"zone_{i}" for i in range(len(ZONE_ANCHORS))]

    def zone_dist(a: str, b: str) -> float:
        la, loa = g.nodes[zone_gateway[a]]["anchor_lat"], g.nodes[zone_gateway[a]]["anchor_lon"]
        lb, lob = g.nodes[zone_gateway[b]]["anchor_lat"], g.nodes[zone_gateway[b]]["anchor_lon"]
        return _haversine_km(la, loa, lb, lob)

    backbone = nx.Graph()
    backbone.add_nodes_from(zone_ids)
    radius_km, max_neighbors = 9.0, 6
    for a in zone_ids:
        by_dist = sorted((b for b in zone_ids if b != a), key=lambda b: zone_dist(a, b))
        within_radius = [b for b in by_dist if zone_dist(a, b) <= radius_km]
        neighbors = within_radius[:max_neighbors] if len(within_radius) >= knn else by_dist[:knn]
        for b in neighbors:
            backbone.add_edge(a, b)

    if not nx.is_connected(backbone):
        # local radius+kNN can leave a far-flung zone isolated; stitch
        # everything together with a minimum spanning tree over real
        # distances so every zone is guaranteed reachable from every other.
        complete = nx.Graph()
        complete.add_nodes_from(zone_ids)
        for i, a in enumerate(zone_ids):
            for b in zone_ids[i + 1:]:
                complete.add_edge(a, b, weight=zone_dist(a, b))
        backbone.add_edges_from(nx.minimum_spanning_tree(complete, weight="weight").edges())

    for a, b in backbone.edges():
        _add_road(g, zone_gateway[a], zone_gateway[b])

    return g


def _add_road(g: nx.Graph, u: str, v: str):
    lat1, lon1 = g.nodes[u]["lat"], g.nodes[u]["lon"]
    lat2, lon2 = g.nodes[v]["lat"], g.nodes[v]["lon"]
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    free_flow_kmh = 35.0
    base_time_min = (dist_km / free_flow_kmh) * 60
    g.add_edge(u, v, dist_km=dist_km, base_time=base_time_min, congestion_multiplier=1.0)


def _load_osm_graph() -> nx.Graph:
    """
    Production path: loads the real road network cached to disk by
    scripts/build_osm_cache.py. Deliberately does NOT fetch from
    OSMnx/Overpass itself on a cold request path - that requires internet
    access and can take 30s to a few minutes, which you never want
    blocking a server startup or, worse, a request. Run the setup script
    once; this function just reads its output afterward.
    """
    cache_path = Path(settings.routing_cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"No cached road network found at '{cache_path}'. Run this once first:\n"
            f"    cd backend && python scripts/build_osm_cache.py\n"
            f"That fetches the real Bengaluru road network from OpenStreetMap and "
            f"caches it here. After it finishes, restart the backend."
        )
    with open(cache_path, "rb") as f:
        g: nx.Graph = pickle.load(f)
    return g


def _get_zone_edge_index(g: nx.Graph) -> dict[str, list[tuple[str, str]]]:
    """
    Precomputed zone_id -> [edges] lookup, built once per graph and cached
    on the graph object itself (g.graph persists across calls since
    get_graph() is lru_cached, so this only runs once per process).

    This exists because update_zone_congestion() used to scan every edge
    in the whole graph on every call to find the ones touching a given
    zone. That's fine on the small demo network (~200 edges total) but
    catastrophic on the real OSM graph (~198,788 edges): with 24 zones
    updated every 2-second tick, the naive scan does roughly 24 * 198,788
    ≈ 4.8 million edge checks every tick, forever - enough to peg a
    free-tier CPU and make every request (including the websocket
    handshake) time out, which is exactly what surfaced as a confusing
    "CORS error" in the browser once this ran in production against real
    data instead of the small demo graph.
    """
    idx = g.graph.get("_zone_edge_index")
    if idx is None:
        idx = {}
        for u, v in g.edges():
            zu = g.nodes[u].get("zone_id")
            zv = g.nodes[v].get("zone_id")
            if zu:
                idx.setdefault(zu, []).append((u, v))
            if zv and zv != zu:
                idx.setdefault(zv, []).append((u, v))
        g.graph["_zone_edge_index"] = idx
    return idx


def update_zone_congestion(zone_id: str, congestion_score: float):
    """Called by the simulation/CV layer to push live congestion onto every
    edge whose endpoints fall in this zone. multiplier ranges ~1.0 (free
    flow) to ~4.0 (gridlock). O(edges in this zone) via the precomputed
    index above, not O(all edges in the graph)."""
    g = get_graph()
    multiplier = 1.0 + (congestion_score / 100.0) * 3.0
    idx = _get_zone_edge_index(g)
    for u, v in idx.get(zone_id, []):
        g[u][v]["congestion_multiplier"] = multiplier


def _nearest_node(g: nx.Graph, lat: float, lon: float) -> str:
    return min(g.nodes, key=lambda n: _haversine_km(lat, lon, g.nodes[n]["lat"], g.nodes[n]["lon"]))


def compute_route(req: RouteRequest) -> RouteResponse:
    g = get_graph()
    origin = _nearest_node(g, req.origin_lat, req.origin_lon)
    dest = _nearest_node(g, req.dest_lat, req.dest_lon)

    def weight_fn(u, v, data):
        effective = data["base_time"] * data["congestion_multiplier"]
        if req.priority == "fastest":
            return effective
        if req.priority == "avoid_congestion":
            # penalize congested edges more aggressively than raw time would
            return effective * (1 + data["congestion_multiplier"])
        if req.priority == "emergency":
            # emergency vehicles get much less penalty from congestion
            # (sirens/lane-splitting) but still avoid total gridlock edges
            return data["base_time"] * (1 + max(0, data["congestion_multiplier"] - 2.5))
        return effective

    try:
        path_nodes = nx.shortest_path(g, origin, dest, weight=weight_fn)
    except nx.NetworkXNoPath:
        return RouteResponse(
            priority=req.priority, distance_km=0, estimated_minutes=0,
            congestion_adjusted=True, path=[], avoided_zones=[],
        )

    distance_km = 0.0
    estimated_minutes = 0.0
    avoided_zones: set[str] = set()
    steps: list[RouteStep] = []

    for i, node in enumerate(path_nodes):
        ndata = g.nodes[node]
        steps.append(RouteStep(lat=ndata["lat"], lon=ndata["lon"], zone_id=ndata.get("zone_id")))
        if i > 0:
            edata = g[path_nodes[i - 1]][node]
            distance_km += edata["dist_km"]
            estimated_minutes += edata["base_time"] * edata["congestion_multiplier"]
            if edata["congestion_multiplier"] > 2.0:
                avoided_zones.add(ndata.get("zone_id", ""))

    return RouteResponse(
        priority=req.priority,
        distance_km=round(distance_km, 2),
        estimated_minutes=round(estimated_minutes, 1),
        congestion_adjusted=True,
        path=steps,
        avoided_zones=sorted(z for z in avoided_zones if z),
    )
