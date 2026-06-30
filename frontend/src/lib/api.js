// lib/api.js
// Centralizes backend URLs so swapping from local dev to a deployed
// Render/Railway backend is a single env var change, not a code change.

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const WS_URL = import.meta.env.VITE_WS_URL || API_BASE.replace(/^http/, "ws") + "/ws/live";

export async function fetchSnapshot() {
  const res = await fetch(`${API_BASE}/api/snapshot`);
  if (!res.ok) throw new Error(`Snapshot fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function computeRoute({ originLat, originLon, destLat, destLon, priority }) {
  const res = await fetch(`${API_BASE}/api/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin_lat: originLat,
      origin_lon: originLon,
      dest_lat: destLat,
      dest_lon: destLon,
      priority,
    }),
  });
  if (!res.ok) throw new Error(`Route request failed: ${res.status}`);
  return res.json();
}
