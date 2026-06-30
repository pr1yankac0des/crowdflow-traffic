import { useEffect, useState } from "react";
import CommandHeader from "./components/CommandHeader";
import IncidentFeed from "./components/IncidentFeed";
import TrafficMap from "./components/TrafficMap";
import StatsPanel from "./components/StatsPanel";
import RouteOptimizer from "./components/RouteOptimizer";
import EmergencyPanel from "./components/EmergencyPanel";
import { useLiveSnapshot } from "./hooks/useWebSocket";
import { fetchHealth } from "./lib/api";

export default function App() {
  const { snapshot, connected } = useLiveSnapshot();
  const [demoMode, setDemoMode] = useState(true);
  const [route, setRoute] = useState(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => setDemoMode(Boolean(h.demo_mode)))
      .catch(() => {});
  }, []);

  const zones = snapshot?.zones ?? [];
  const incidents = snapshot?.incidents ?? [];
  const heatmap = snapshot?.heatmap ?? [];

  return (
    <div className="h-screen w-screen flex flex-col bg-void font-body overflow-hidden">
      <CommandHeader connected={connected} demoMode={demoMode} snapshot={snapshot} />

      <div className="flex-1 flex min-h-0 relative">
        <aside className="w-[300px] shrink-0 border-r border-hairline bg-panel hidden md:flex shadow-[4px_0_24px_-8px_rgba(0,0,0,0.55)]">
          <IncidentFeed incidents={incidents} selectedId={selectedIncidentId} onSelect={setSelectedIncidentId} />
        </aside>

        <main className="flex-1 min-w-0 relative bg-void">
          {!snapshot ? (
            <div className="absolute inset-0 flex items-center justify-center text-ink-dim font-mono text-xs">
              ESTABLISHING UPLINK TO BACKEND...
            </div>
          ) : (
            <TrafficMap
              zones={zones}
              incidents={incidents}
              heatmap={heatmap}
              route={route}
              selectedIncidentId={selectedIncidentId}
              onSelectIncident={setSelectedIncidentId}
            />
          )}
        </main>

        <aside className="w-[320px] shrink-0 border-l border-hairline bg-panel hidden lg:flex flex-col shadow-[-4px_0_24px_-8px_rgba(0,0,0,0.55)]">
          <StatsPanel snapshot={snapshot} />
          <RouteOptimizer zones={zones} onRouteComputed={setRoute} route={route} />
          <EmergencyPanel incidents={incidents} selectedId={selectedIncidentId} />
        </aside>
      </div>
    </div>
  );
}
