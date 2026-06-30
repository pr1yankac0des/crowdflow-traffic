# CrowdFlow Traffic

A proactive, not reactive, urban traffic management system: live congestion
scoring from computer vision, graph-based route optimization that reacts to
real-time conditions, and an automated emergency dispatch recommendation
layer — fronted by a command-center dashboard.

```
                    ┌─────────────────────────┐
   Camera feed /    │   CV pipeline (YOLOv8)   │
   simulated feed → │   density · motion ·     │──┐
                    │   overlap heuristics     │  │
                    └─────────────────────────┘  ▼
                                          ┌──────────────────┐
                                          │ Congestion scorer │ → 0-100 score, severity
                                          └──────────────────┘
                                                    │
                          ┌─────────────────────────┼─────────────────────────┐
                          ▼                         ▼                         ▼
               ┌───────────────────┐     ┌────────────────────┐    ┌──────────────────┐
               │ Incident lifecycle │     │  Graph routing      │    │ Emergency dispatch│
               │ spawn/clear        │     │  (NetworkX, dynamic │    │ recommendation     │
               │                    │     │  edge weights)      │    │ (rules engine)     │
               └───────────────────┘     └────────────────────┘    └──────────────────┘
                          │                         │                         │
                          └─────────────┬───────────┴─────────────┬───────────┘
                                        ▼                          ▼
                              FastAPI REST + WebSocket  ──────────────────→  React command deck
```

## Be honest about scope before you demo this

This is a genuinely working full-stack system end-to-end — backend has been
tested with live simulated ticks, all three routing modes, incident
spawning, and the websocket stream. But two pieces are **heuristics, not
trained models**, and you should say so if anyone asks (it's a stronger
answer than pretending otherwise):

- **"Accident detection"** — there is no reliable free pretrained model that
  classifies "this frame shows a collision." What's implemented is vehicle
  detection (YOLOv8n on COCO classes) plus a bounding-box-overlap heuristic
  that flags *possible* collisions for a human to confirm. The architecture
  is built so a fine-tuned model (trained on a labeled dataset like CADP or
  a Kaggle CCTV-accident set) drops into `cv_detection.analyze_frame()`
  without touching anything downstream.
- **"Predictive clearance time"** — a transparent formula (incident type ×
  severity multiplier), not a regression model. Swap in scikit-learn once
  you have real "incident logged → incident resolved" timestamp pairs to
  train on.

Everything else — the congestion scoring math, the NetworkX routing with
live-updated edge weights, the incident lifecycle, the dispatch rules, the
websocket broadcast loop — is real logic doing real work, just running on
simulated input by default so you can demo it with no GPU, no camera, and
no API keys.

## Tech stack, and why each piece is free-tier-friendly

| Layer | Choice | Why |
|---|---|---|
| CV | YOLOv8n (Ultralytics) | Open weights, runs on CPU, industry-standard detector |
| Routing | NetworkX + OSMnx | Pure Python graph algorithms; OSMnx wraps the free OpenStreetMap Overpass API — no Google Maps billing needed |
| Backend | FastAPI + WebSockets | Native async websockets, no third-party realtime service required |
| Frontend | React + Vite + Tailwind | Fast dev loop, small bundle, no framework license |
| Maps | Leaflet + CARTO dark tiles | Free, no API key, unlike Mapbox/Google which need billing past free quotas |
| Charts | Recharts | MIT-licensed |
| Deploy | Docker + docker-compose | Runs identically on Render/Railway/Fly.io free tiers or any VM |

**License note:** Ultralytics YOLOv8 is AGPL-3.0 for the open-source
release. That's fine for a portfolio/demo project; if you ever take this
commercial, you'd need either an Ultralytics enterprise license or to swap
to an Apache/MIT-licensed detector.

**Overpass API note:** the public Overpass endpoint OSMnx talks to is free
but rate-limited and intended for occasional queries, not bulk traffic — the
routing module fetches a city's road graph once and caches it to disk
(`routing.get_graph()` / `routing_cache_path`), never on a hot request path.

## Project layout

```
backend/
  app/
    core/config.py        # DEMO_MODE + all tunables, env-driven
    models/schemas.py     # Pydantic contracts shared by every module
    services/
      cv_detection.py      # real YOLOv8 path + simulated frame generator
      congestion.py        # scoring math (pure functions, unit-testable)
      routing.py           # NetworkX graph + demo grid / OSMnx production path
      emergency.py         # dispatch recommendation rules
      simulation.py        # ties it all together into live "world state"
    api/routes.py         # REST: /api/snapshot, /api/route, /api/cv/analyze-frame
    websocket/manager.py  # broadcast pool for /ws/live
    main.py               # FastAPI app + background tick loop
frontend/
  src/
    components/
      TrafficMap.jsx       # Leaflet + heatmap + radar sweep + route overlay
      IncidentFeed.jsx     # dispatch-log styled incident ledger
      StatsPanel.jsx       # rolling congestion trend + severity split
      RouteOptimizer.jsx   # zone-to-zone routing UI, 3 priority modes
      EmergencyPanel.jsx   # dispatch recommendation detail
      CommandHeader.jsx    # ticker bar
    hooks/useWebSocket.js  # live snapshot stream + REST polling fallback
docker-compose.yml
```

## Run it locally (no Docker)

**Backend**
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Visit `http://localhost:8000/` — you should see `{"status":"ok",...}`.

**Frontend** (separate terminal)
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173`. Within ~2 seconds you should see the map
populate with 24 zones, a live heatmap, and the trend chart start moving.
Incidents will spawn organically as simulated congestion drifts upward —
give it 30–60 seconds if the ledger looks empty on first load.

## Run it with Docker

```bash
docker compose up --build
```
Backend on `:8000`, frontend on `:5173`. If you deploy frontend and backend
to different hosts, rebuild the frontend image with the right build args:
```bash
docker build --build-arg VITE_API_BASE_URL=https://your-backend.onrender.com \
              --build-arg VITE_WS_URL=wss://your-backend.onrender.com/ws/live \
              -t crowdflow-frontend ./frontend
```
(Vite env vars are baked in at build time, not read at container runtime —
that's why these are build args, not a `.env` you can swap post-build.)

## Free-tier deployment path

- **Backend** → Render or Railway free web service. Note free tiers spin
  down on inactivity (cold start delay on first request after idle).
- **Frontend** → Vercel or Netlify free tier, static `dist/` output.
- **CV inference at scale** → a free-tier Hugging Face Space (CPU) can host
  the YOLOv8n inference endpoint separately if you don't want torch in your
  main API container.

## API reference (demo mode)

| Endpoint | Method | Notes |
|---|---|---|
| `/` | GET | Health + whether demo_mode is on |
| `/api/snapshot` | GET | Current zones, incidents, heatmap, city avg |
| `/api/route` | POST | `{origin_lat, origin_lon, dest_lat, dest_lon, priority}` → `priority` is `fastest` \| `avoid_congestion` \| `emergency` |
| `/api/cv/analyze-frame` | POST | Multipart image upload — **disabled in demo_mode**, see note in `routes.py` |
| `/ws/live` | WS | Pushes a full snapshot every `simulation_tick_seconds` |

## Turning off demo mode (real cameras, real roads)

1. Set `CROWDFLOW_DEMO_MODE=False` in `backend/.env`.
2. Uncomment the production deps in `requirements.txt` (`ultralytics`,
   `torch`, `opencv-python-headless`, `osmnx`, `geopandas`) and `pip install`.
3. Run a one-off script to fetch + cache your city's road graph via OSMnx
   (see the docstring in `routing._load_osm_graph()` for the exact call) —
   do this once, not on a request path.
4. Point real camera frames at `POST /api/cv/analyze-frame` per zone on
   whatever schedule your cameras allow (e.g. every 2–5s per camera).

Nothing else changes — `congestion.py`, `routing.py`'s pathfinding,
`emergency.py`, and every frontend component consume the same schemas
regardless of where the data originated.
