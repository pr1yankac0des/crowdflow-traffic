import { useEffect, useRef } from "react";
import { AlertTriangle, CircleDot, Truck } from "lucide-react";
import { INCIDENT_LABEL, SEVERITY_COLOR, timeAgo } from "../lib/format";

export default function IncidentFeed({ incidents, selectedId, onSelect }) {
  const seenIdsRef = useRef(new Set());

  const sorted = [...incidents].sort((a, b) => {
    const statusRank = { active: 0, clearing: 1, resolved: 2 };
    if (statusRank[a.status] !== statusRank[b.status]) return statusRank[a.status] - statusRank[b.status];
    return new Date(b.detected_at) - new Date(a.detected_at);
  });

  // Anything not in seenIdsRef yet (as of the previous render) is new this
  // tick and should play an entrance animation. The ref updates *after*
  // paint via the effect below, so it reflects last render's state while
  // this render's JSX is built - exactly the one-shot window we want.
  const newIds = new Set(sorted.filter((inc) => !seenIdsRef.current.has(inc.id)).map((inc) => inc.id));

  useEffect(() => {
    sorted.forEach((inc) => seenIdsRef.current.add(inc.id));
  }, [sorted]);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-hairline flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold tracking-wide text-ink">DISPATCH LEDGER</h2>
        <span className="font-mono text-[10px] text-ink-dim">{sorted.length} LOGGED</span>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-hairline">
        {sorted.length === 0 && (
          <div className="px-4 py-8 text-center text-ink-dim text-xs font-mono leading-relaxed">
            NO INCIDENTS LOGGED.
            <br />
            ALL MONITORED ZONES NOMINAL.
          </div>
        )}

        {sorted.map((inc) => {
          const sev = SEVERITY_COLOR[inc.severity] ?? SEVERITY_COLOR.low;
          const isSelected = inc.id === selectedId;
          const isNew = newIds.has(inc.id);
          return (
            <button
              key={inc.id}
              onClick={() => onSelect(inc.id === selectedId ? null : inc.id)}
              className={`w-full text-left px-4 py-3 transition-all duration-150 border-l-2 ${
                isSelected
                  ? "bg-panel-raised border-l-cyan shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)]"
                  : "border-l-transparent hover:bg-panel-raised/60 hover:border-l-hairline"
              } ${isNew ? "animate-incident_in" : ""}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-ink font-medium">{inc.id}</span>
                <span
                  className={`font-mono text-[10px] px-1.5 py-0.5 rounded border ${sev.text} border-current/30`}
                >
                  {inc.severity.toUpperCase()}
                </span>
              </div>

              <div className="flex items-center gap-1.5 text-ink-dim text-[11px] mb-1.5">
                <AlertTriangle className="w-3 h-3" strokeWidth={2} />
                <span>{INCIDENT_LABEL[inc.type] ?? inc.type.toUpperCase()}</span>
              </div>

              <div className="flex items-center justify-between font-mono text-[10px] text-ink-dim">
                <span className="flex items-center gap-1">
                  <CircleDot className="w-3 h-3" />
                  {inc.zone_id.replace("zone_", "Z-")}
                </span>
                <span>{timeAgo(inc.detected_at)}</span>
              </div>

              <div className="mt-2 flex items-center justify-between">
                <StatusPill status={inc.status} />
                {(inc.recommended_units.ambulance > 0 ||
                  inc.recommended_units.fire_rescue > 0 ||
                  inc.recommended_units.tow_trucks > 0 ||
                  inc.recommended_units.traffic_police > 0) && (
                  <span className="flex items-center gap-1 text-[10px] font-mono text-ink-dim">
                    <Truck className="w-3 h-3" />
                    {inc.recommended_units.traffic_police +
                      inc.recommended_units.ambulance +
                      inc.recommended_units.fire_rescue +
                      inc.recommended_units.tow_trucks}{" "}
                    UNIT(S)
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    active: { label: "ACTIVE", className: "bg-red/15 text-red" },
    clearing: { label: "CLEARING", className: "bg-amber/15 text-amber" },
    resolved: { label: "RESOLVED", className: "bg-cyan/15 text-cyan" },
  };
  const s = map[status] ?? map.active;
  return (
    <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded ${s.className}`}>{s.label}</span>
  );
}
