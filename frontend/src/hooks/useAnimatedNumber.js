import { useEffect, useRef, useState } from "react";

/**
 * Smoothly tweens displayed value toward `target` over `durationMs`,
 * instead of the UI jump-cutting every time a new websocket snapshot
 * arrives. Pure requestAnimationFrame, no extra dependency.
 */
export function useAnimatedNumber(target, durationMs = 500) {
  const [value, setValue] = useState(target);
  const frameRef = useRef(null);
  const fromRef = useRef(target);

  useEffect(() => {
    const from = fromRef.current;
    const to = target;
    if (from === to) return;

    const start = performance.now();
    cancelAnimationFrame(frameRef.current);

    function tick(now) {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      const current = from + (to - from) * eased;
      setValue(current);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs]);

  return value;
}
