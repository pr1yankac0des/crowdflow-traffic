import { useEffect, useMemo, useRef } from "react";
import { MapContainer, TileLayer, CircleMarker, Marker, Polyline, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";
import { SEVERITY_COLOR, heatColorForIntensity } from "../lib/format";

const CITY_CENTER = [12.9529, 77.634];

// CircleMarker (Leaflet's SVG path renderer) has no box model, so it can
// never take a CSS box-shadow animation - which is what `animate-pulse_ring`
// needs. A divIcon-based Marker is a real positioned <div>, so it can. This
// is layered behind the actual interactive CircleMarker purely as a visual
// halo; pointer events pass through it to the marker underneath.
const PULSE_ICON_CACHE = new Map();
function pulseIcon() {
  if (!PULSE_ICON_CACHE.has("red")) {
    PULSE_ICON_CACHE.set(
      "red",
      L.divIcon({
        className: "",
        html: '<div class="w-3 h-3 rounded-full bg-red/70 animate-pulse_ring"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      })
    );
  }
  return PULSE_ICON_CACHE.get("red");
}

// A fixed center+zoom is a guess about how much area is visible - it can
// clip zones off-screen on a narrower window or smaller monitor. fitBounds
// computed from the real zone coordinates guarantees every zone is inside
// the viewport on first load, regardless of screen size. Only runs once
// (fittedRef) so it doesn't fight the user's own panning/zooming on every
// 2-second snapshot refresh afterward.
function FitToZones({ zones }) {
  const map = useMap();
  const fittedRef = useRef(false);

  useEffect(() => {
    if (fittedRef.current || zones.length === 0) return;
    const bounds = L.latLngBounds(zones.map((z) => [z.lat, z.lon]));
    map.fitBounds(bounds, { padding: [48, 48] });
    fittedRef.current = true;
  }, [zones, map]);

  return null;
}

function HeatLayer({ points }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    const heatPoints = points.map((p) => [p.lat, p.lon, p.intensity]);
    if (layerRef.current) {
      layerRef.current.setLatLngs(heatPoints);
    } else {
      layerRef.current = L.heatLayer(heatPoints, {
        radius: 38,
        blur: 30,
        maxZoom: 16,
        minOpacity: 0.25,
        gradient: { 0.2: "#3FE0C5", 0.5: "#FFB020", 0.85: "#FF4D5E" },
      }).addTo(map);
    }
    return () => {
      // layer persists across re-renders intentionally; only torn down on unmount
    };
  }, [points, map]);

  useEffect(() => {
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [map]);

  return null;
}

function RadarSweep() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-[400]">
      <div
        className="absolute left-1/2 top-1/2 w-[140%] h-[140%] -translate-x-1/2 -translate-y-1/2 animate-sweep"
        style={{
          background:
            "conic-gradient(from 0deg, rgba(63,224,197,0.16) 0deg, rgba(63,224,197,0) 35deg, transparent 360deg)",
          borderRadius: "50%",
        }}
      />
    </div>
  );
}

export default function TrafficMap({ zones, incidents, heatmap, route, selectedIncidentId, onSelectIncident }) {
  const routeColor = route?.priority === "emergency" ? "#FF4D5E" : route?.priority === "avoid_congestion" ? "#FFB020" : "#8B7CFF";

  const routeLatLngs = useMemo(
    () => (route?.path ?? []).map((s) => [s.lat, s.lon]),
    [route]
  );

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={CITY_CENTER}
        zoom={11}
        className="w-full h-full"
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />

        <FitToZones zones={zones} />
        <HeatLayer points={heatmap} />

        {zones.map((z) => (
          <CircleMarker
            key={z.zone_id}
            center={[z.lat, z.lon]}
            radius={5}
            pathOptions={{
              color: heatColorForIntensity(z.congestion.score / 100),
              fillColor: heatColorForIntensity(z.congestion.score / 100),
              fillOpacity: 0.85,
              weight: 1,
            }}
          >
            <Tooltip direction="top" offset={[0, -4]}>
              <div className="font-mono text-[11px]">
                <strong>{z.name}</strong>
                <br />
                Score: {z.congestion.score.toFixed(0)}/100 ({z.congestion.severity})
                <br />
                Vehicles: {z.congestion.vehicle_count}
              </div>
            </Tooltip>
          </CircleMarker>
        ))}

        {incidents
          .filter((i) => i.status !== "resolved" && (i.severity === "high" || i.severity === "critical"))
          .map((inc) => (
            <Marker
              key={`pulse-${inc.id}`}
              position={[inc.lat, inc.lon]}
              icon={pulseIcon()}
              interactive={false}
              zIndexOffset={-100}
            />
          ))}

        {incidents
          .filter((i) => i.status !== "resolved")
          .map((inc) => {
            const sev = SEVERITY_COLOR[inc.severity] ?? SEVERITY_COLOR.low;
            const isSelected = inc.id === selectedIncidentId;
            return (
              <CircleMarker
                key={inc.id}
                center={[inc.lat, inc.lon]}
                radius={isSelected ? 11 : 8}
                pathOptions={{
                  color: sev.hex,
                  fillColor: sev.hex,
                  fillOpacity: 0.9,
                  weight: isSelected ? 3 : 1.5,
                }}
                eventHandlers={{ click: () => onSelectIncident(inc.id === selectedIncidentId ? null : inc.id) }}
              >
                <Tooltip direction="top" offset={[0, -6]}>
                  <div className="font-mono text-[11px]">
                    <strong>{inc.id}</strong> — {inc.type.replace("_", " ")}
                    <br />
                    Severity: {inc.severity} · ETA clear: {inc.estimated_clearance_minutes}m
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          })}

        {routeLatLngs.length > 1 && (
          <Polyline
            key={route._computedAt ?? route.priority}
            positions={routeLatLngs}
            pathOptions={{
              color: routeColor,
              weight: 4,
              opacity: 0.85,
              dashArray: route.priority === "emergency" ? "1,6" : null,
              className: "animate-route_in",
            }}
          />
        )}
      </MapContainer>

      <RadarSweep />

      <div className="absolute bottom-3 left-3 z-[450] bg-panel/90 border border-hairline rounded px-2.5 py-1.5 font-mono text-[10px] text-ink-dim flex items-center gap-3 pointer-events-none">
        <LegendDot color="#3FE0C5" label="LOW" />
        <LegendDot color="#FFB020" label="MODERATE" />
        <LegendDot color="#FF4D5E" label="CRITICAL" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <span className="flex items-center gap-1">
      <span className="w-2 h-2 rounded-full inline-block" style={{ background: color }} />
      {label}
    </span>
  );
}
