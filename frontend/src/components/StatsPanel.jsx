import { useEffect, useRef, useState } from "react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { Activity } from "lucide-react";
import { useAnimatedNumber } from "../hooks/useAnimatedNumber";

const HISTORY_LIMIT = 40;

export default function StatsPanel({ snapshot }) {
  const [history, setHistory] = useState([]);
  const lastTsRef = useRef(null);
  const animatedAvg = useAnimatedNumber(snapshot?.city_avg_congestion ?? 0, 600);

  useEffect(() => {
    if (!snapshot) return;
    if (lastTsRef.current === snapshot.timestamp) return;
    lastTsRef.current = snapshot.timestamp;

    setHistory((prev) => {
      const next = [...prev, { t: prev.length, avg: snapshot.city_avg_congestion }];
      return next.length > HISTORY_LIMIT ? next.slice(next.length - HISTORY_LIMIT) : next;
    });
  }, [snapshot]);

  const severityCounts = { low: 0, moderate: 0, high: 0, critical: 0 };
  for (const z of snapshot?.zones ?? []) {
    severityCounts[z.congestion.severity] = (severityCounts[z.congestion.severity] ?? 0) + 1;
  }
  const totalZones = snapshot?.zones?.length || 1;

  return (
    <div className="border-b border-hairline">
      <div className="px-4 py-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold tracking-wide text-ink flex items-center gap-1.5">
          <Activity className="w-4 h-4 text-cyan" />
          CITY CONGESTION TREND
        </h2>
        <span className="font-mono text-lg text-ink leading-none">
          {animatedAvg.toFixed(1)}
          <span className="text-ink-dim text-xs">/100</span>
        </span>
      </div>

      <div className="h-24 px-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="avgFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3FE0C5" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#3FE0C5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" hide />
            <YAxis domain={[0, 100]} hide />
            <Tooltip
              contentStyle={{ background: "#11161D", border: "1px solid #1D2733", fontSize: 11 }}
              labelFormatter={() => ""}
              formatter={(value) => [`${value.toFixed(1)} / 100`, "City avg"]}
            />
            <Area type="monotone" dataKey="avg" stroke="#3FE0C5" strokeWidth={2} fill="url(#avgFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="px-4 pb-4 pt-1">
        <div className="flex h-2 w-full rounded-full overflow-hidden bg-panel-raised">
          <div className="bg-cyan" style={{ width: `${(severityCounts.low / totalZones) * 100}%` }} />
          <div className="bg-amber" style={{ width: `${(severityCounts.moderate / totalZones) * 100}%` }} />
          <div className="bg-red" style={{ width: `${((severityCounts.high + severityCounts.critical) / totalZones) * 100}%` }} />
        </div>
        <div className="flex justify-between mt-1.5 font-mono text-[10px] text-ink-dim">
          <span>{severityCounts.low} LOW</span>
          <span>{severityCounts.moderate} MOD</span>
          <span>{severityCounts.high + severityCounts.critical} HIGH/CRIT</span>
        </div>
      </div>
    </div>
  );
}
