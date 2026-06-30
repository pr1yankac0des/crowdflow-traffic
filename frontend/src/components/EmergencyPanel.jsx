import { Siren, Ambulance, Flame, Wrench, ShieldCheck } from "lucide-react";
import { SEVERITY_COLOR, INCIDENT_LABEL } from "../lib/format";

export default function EmergencyPanel({ incidents, selectedId }) {
  const active = incidents.filter((i) => i.status !== "resolved");
  const focused =
    active.find((i) => i.id === selectedId) ??
    [...active].sort((a, b) => b.congestion_score - a.congestion_score)[0];

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3">
      <h2 className="font-display text-sm font-semibold tracking-wide text-ink flex items-center gap-1.5 mb-3">
        <Siren className="w-4 h-4 text-amber" />
        EMERGENCY DISPATCH
      </h2>

      {!focused ? (
        <div className="text-ink-dim text-xs font-mono leading-relaxed flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 text-cyan shrink-0 mt-0.5" />
          No active incident requires dispatch right now. Select one from the ledger or the map to inspect
          its recommendation.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-ink">{focused.id}</span>
            <span className={`font-mono text-[10px] ${SEVERITY_COLOR[focused.severity]?.text}`}>
              {focused.severity.toUpperCase()}
            </span>
          </div>
          <div className="text-ink-dim text-[11px] font-mono">
            {INCIDENT_LABEL[focused.type]} · ZONE {focused.zone_id.replace("zone_", "")}
          </div>

          <div className="grid grid-cols-4 gap-2">
            <UnitCount icon={ShieldCheck} label="POLICE" count={focused.recommended_units.traffic_police} color="text-cyan" />
            <UnitCount icon={Ambulance} label="MEDIC" count={focused.recommended_units.ambulance} color="text-red" />
            <UnitCount icon={Flame} label="FIRE" count={focused.recommended_units.fire_rescue} color="text-amber" />
            <UnitCount icon={Wrench} label="TOW" count={focused.recommended_units.tow_trucks} color="text-violet" />
          </div>

          <div className="bg-panel-raised border border-hairline rounded p-2.5">
            <div className="font-mono text-[9.5px] text-ink-dim mb-1">RESPONSE LEVEL {focused.recommended_units.response_level}/3 — RATIONALE</div>
            <p className="text-[11px] text-ink leading-relaxed">{focused.recommended_units.rationale}</p>
          </div>

          <div className="flex items-center justify-between font-mono text-[10px] text-ink-dim border-t border-hairline pt-2">
            <span>EST. CLEARANCE</span>
            <span className="text-ink">{focused.estimated_clearance_minutes} min</span>
          </div>
        </div>
      )}
    </div>
  );
}

function UnitCount({ icon: Icon, label, count, color }) {
  return (
    <div className={`flex flex-col items-center gap-1 rounded border border-hairline py-2 ${count > 0 ? "bg-panel-raised" : "opacity-40"}`}>
      <Icon className={`w-4 h-4 ${color}`} strokeWidth={1.75} />
      <span className="font-mono text-sm text-ink leading-none">{count}</span>
      <span className="font-mono text-[8.5px] text-ink-dim">{label}</span>
    </div>
  );
}
