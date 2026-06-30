import { useEffect, useRef, useState } from "react";
import { WS_URL, fetchSnapshot } from "../lib/api";

/**
 * Subscribes to the /ws/live snapshot stream. If the socket can't connect
 * (backend not running yet, network hiccup), falls back to polling
 * /api/snapshot every 3s so the dashboard still comes alive instead of
 * showing a dead screen - then transparently switches back to the socket
 * once it reconnects.
 */
export function useLiveSnapshot() {
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const retryRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    function startPolling() {
      if (pollRef.current) return;
      pollRef.current = setInterval(async () => {
        try {
          const data = await fetchSnapshot();
          if (!cancelled) setSnapshot(data);
        } catch {
          // backend genuinely unreachable; keep retrying silently
        }
      }, 3000);
    }

    function stopPolling() {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }

    function connect() {
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelled) return;
          setConnected(true);
          retryRef.current = 0;
          stopPolling();
        };

        ws.onmessage = (event) => {
          if (cancelled) return;
          try {
            setSnapshot(JSON.parse(event.data));
          } catch {
            /* ignore malformed frame */
          }
        };

        ws.onclose = () => {
          if (cancelled) return;
          setConnected(false);
          startPolling();
          const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
          retryRef.current += 1;
          setTimeout(() => !cancelled && connect(), delay);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        startPolling();
      }
    }

    connect();
    startPolling(); // run in parallel until the first successful onopen

    return () => {
      cancelled = true;
      stopPolling();
      wsRef.current?.close();
    };
  }, []);

  return { snapshot, connected };
}
