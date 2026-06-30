import { useState } from "react";
import { Navigation, Loader2, ShieldAlert } from "lucide-react";
import { computeRoute } from "../lib/api";

const PRIORITIES = [
  { id: "fastest", label: "FASTEST" },
  { id: "avoid_congestion", label: "AVOID CONGESTION" },
  { id: "emergency", label: "EMERGENCY" },
];

export default function RouteOptimizer({ zones, onRouteComputed, route }) {
  const [originId, setOriginId] = useState("");
  const [destId, setDestId] = useState("");
  const [priority, setPriority] = useState("fastest");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sortedZones = [...zones].sort((a, b) => a.name.localeCompare(b.name));

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    const origin = zones.find((z) => z.zone_id === originId);
    const dest = zones.find((z) => z.zone_id === destId);
    if (!origin || !dest) {
      setError("Select both an origin and a destination zone.");
      return;
    }
    if (origin.zone_id === dest.zone_id) {
      setError("Origin and destination must differ.");
      return;
    }

    setLoading(true);
    try {
      const result = await computeRoute({
        originLat: origin.lat,
        originLon: origin.lon,
        destLat: dest.lat,
        destLon: dest.lon,
        priority,
      });
      onRouteComputed({ ...result, _computedAt: Date.now() });
    } catch (err) {
      setError("Route request failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-b border-hairline px-4 py-3">
      <h2 className="font-display text-sm font-semibold tracking-wide text-ink flex items-center gap-1.5 mb-3">
        <Navigation className="w-4 h-4 text-violet" />
        ROUTE OPTIMIZER
      </h2>

      <form onSubmit={handleSubmit} className="space-y-2.5">
        <ZoneSelect label="ORIGIN" value={originId} onChange={setOriginId} zones={sortedZones} />
        <ZoneSelect label="DESTINATION" value={destId} onChange={setDestId} zones={sortedZones} />

        <div>
          <label className="block font-mono text-[10px] text-ink-dim mb-1">PRIORITY</label>
          <div className="grid grid-cols-3 gap-1">
            {PRIORITIES.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPriority(p.id)}
                className={`font-mono text-[9.5px] py-1.5 rounded border transition-colors ${
                  priority === p.id
                    ? "bg-violet/20 border-violet text-ink"
                    : "bg-panel-raised border-hairline text-ink-dim hover:text-ink"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-violet/90 hover:bg-violet text-void font-display text-xs font-semibold py-2 rounded flex items-center justify-center gap-1.5 transition-all duration-150 disabled:opacity-50 shadow-[0_0_0_0_rgba(139,124,255,0)] hover:shadow-[0_0_20px_-2px_rgba(139,124,255,0.6)]"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
          {loading ? "COMPUTING..." : "COMPUTE ROUTE"}
        </button>

        {error && (
          <div className="flex items-center gap-1.5 text-red text-[11px] font-mono">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}
      </form>

      {route && route.path?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-hairline grid grid-cols-3 gap-2 font-mono text-center">
          <Stat label="DISTANCE" value={`${route.distance_km}`} unit="km" />
          <Stat label="ETA" value={`${route.estimated_minutes}`} unit="min" />
          <Stat label="AVOIDED" value={route.avoided_zones.length} unit="zones" />
        </div>
      )}
    </div>
  );
}

function ZoneSelect({ label, value, onChange, zones }) {
  return (
    <div>
      <label className="block font-mono text-[10px] text-ink-dim mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-panel-raised border border-hairline rounded px-2 py-1.5 text-xs text-ink font-mono focus:outline-none focus:border-violet"
      >
        <option value="">SELECT ZONE...</option>
        {zones.map((z) => (
          <option key={z.zone_id} value={z.zone_id}>
            {z.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function Stat({ label, value, unit }) {
  return (
    <div>
      <div className="text-ink text-sm leading-tight">{value}</div>
      <div className="text-ink-dim text-[9px]">{unit}</div>
      <div className="text-ink-dim text-[9px] mt-0.5">{label}</div>
    </div>
  );
}
