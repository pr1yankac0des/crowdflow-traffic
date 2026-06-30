/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        void: "#0B0F14",
        panel: "#11161D",
        "panel-raised": "#161D27",
        hairline: "#1D2733",
        ink: "#E7ECEF",
        "ink-dim": "#6E7A88",
        cyan: "#3FE0C5",
        amber: "#FFB020",
        red: "#FF4D5E",
        violet: "#8B7CFF",
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      keyframes: {
        sweep: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        pulse_ring: {
          "0%": { boxShadow: "0 0 0 0 rgba(255, 77, 94, 0.55)" },
          "100%": { boxShadow: "0 0 0 14px rgba(255, 77, 94, 0)" },
        },
        ticker: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        incident_in: {
          "0%": { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        route_in: {
          "0%": { opacity: "0" },
          "100%": { opacity: "0.85" },
        },
      },
      animation: {
        sweep: "sweep 4s linear infinite",
        pulse_ring: "pulse_ring 1.6s ease-out infinite",
        ticker: "ticker 28s linear infinite",
        incident_in: "incident_in 0.4s ease-out",
        route_in: "route_in 0.5s ease-out forwards",
      },
    },
  },
  plugins: [],
};
