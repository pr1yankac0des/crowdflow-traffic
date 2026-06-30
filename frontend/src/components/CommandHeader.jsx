import { useEffect, useState } from "react";
import { Radio, Satellite } from "lucide-react";
import { clockTime } from "../lib/format";

export default function CommandHeader({ connected, demoMode, snapshot }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const cityAvg = snapshot?.city_avg_congestion ?? 0;
  const activeIncidents = snapshot?.active_incident_count ?? 0;
  const zoneCount = snapshot?.zones?.length ?? 0;

  const tickerItems = [
    `CITY AVG CONGESTION ${cityAvg.toFixed(1)}/100`,
    `ACTIVE INCIDENTS ${activeIncidents}`,
    `ZONES MONITORED ${zoneCount}`,
    demoMode ? "FEED: SIMULATED DEMO DATA" : "FEED: LIVE CAMERA NETWORK",
    `STREAM ${connected ? "NOMINAL" : "RECONNECTING"}`,
  ];

  return (
    <header className="h-12 shrink-0 bg-panel border-b border-hairline flex items-center px-4 gap-4 font-mono text-[11px] tracking-wide shadow-[0_4px_24px_-6px_rgba(0,0,0,0.6)] relative z-10">
      <div className="flex items-center gap-2 shrink-0 pr-4 border-r border-hairline">
        <Satellite className="w-4 h-4 text-cyan" strokeWidth={1.75} />
        <span className="font-display font-semibold text-sm text-ink tracking-tight">
          CROWDFLOW<span className="text-cyan">//</span>
        </span>
      </div>

      <div className="flex-1 overflow-hidden relative h-full flex items-center">
        <div className="flex gap-10 whitespace-nowrap animate-ticker">
          {[...tickerItems, ...tickerItems].map((item, i) => (
            <span key={i} className="text-ink-dim">
              {item}
            </span>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-panel to-transparent" />
      </div>

      <div className="flex items-center gap-2 shrink-0 pl-4 border-l border-hairline">
        <Radio className={`w-3.5 h-3.5 ${connected ? "text-cyan" : "text-amber"}`} strokeWidth={2} />
        <span className={connected ? "text-cyan" : "text-amber"}>
          {connected ? "LIVE" : "SYNCING"}
        </span>
        <span className="text-ink-dim">{clockTime(now)} IST</span>
      </div>
    </header>
  );
}
