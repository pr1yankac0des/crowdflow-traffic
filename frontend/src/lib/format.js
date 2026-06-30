// lib/format.js

export const SEVERITY_COLOR = {
  low: { text: "text-cyan", bg: "bg-cyan", ring: "ring-cyan/40", hex: "#3FE0C5" },
  moderate: { text: "text-amber", bg: "bg-amber", ring: "ring-amber/40", hex: "#FFB020" },
  high: { text: "text-red", bg: "bg-red", ring: "ring-red/40", hex: "#FF4D5E" },
  critical: { text: "text-red", bg: "bg-red", ring: "ring-red/40", hex: "#FF4D5E" },
};

export const INCIDENT_LABEL = {
  congestion: "CONGESTION",
  stalled_vehicle: "STALLED VEHICLE",
  possible_collision: "POSSIBLE COLLISION",
  road_closure: "ROAD CLOSURE",
};

export function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const sec = Math.max(0, Math.floor(diffMs / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

export function clockTime(date = new Date()) {
  return date.toLocaleTimeString("en-IN", { hour12: false });
}

export function heatColorForIntensity(intensity) {
  // 0 -> cyan, 0.5 -> amber, 1 -> red, interpolated for the heat layer gradient stops
  if (intensity < 0.45) return "#3FE0C5";
  if (intensity < 0.75) return "#FFB020";
  return "#FF4D5E";
}
