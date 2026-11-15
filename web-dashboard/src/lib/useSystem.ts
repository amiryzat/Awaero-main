import { useEffect, useState } from "react";
import type { Decision, Metrics, SystemState } from "./types";

// Same-origin relative paths: the Python server serves this build, and the dev
// proxy (vite.config.ts) maps these to :8000. See PRD 3 and 6.1.
async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

export type MetricsWindow = "session" | "today" | "all";
export type Conn = "connecting" | "live" | "down";

// A timer that pauses while the tab is hidden (PRD 7.4) and fires once on
// return. Returns a cleanup. ponytail: one helper, both polling loops use it.
function poll(everyMs: number, tick: () => void): () => void {
  const run = () => {
    if (!document.hidden) tick();
  };
  run();
  const id = setInterval(run, everyMs);
  document.addEventListener("visibilitychange", run);
  return () => {
    clearInterval(id);
    document.removeEventListener("visibilitychange", run);
  };
}

/** The single polling data layer. /state + /history every 2s, /metrics every
 *  10s and immediately when the window changes. /frame.jpg is Live-only and
 *  lives in that screen, not here. */
export function useSystem(metricsWindow: MetricsWindow = "session") {
  const [state, setState] = useState<SystemState | null>(null);
  const [history, setHistory] = useState<Decision[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [conn, setConn] = useState<Conn>("connecting");

  useEffect(() => {
    let alive = true;
    const stop = poll(2000, async () => {
      try {
        const [s, h] = await Promise.all([
          getJson<SystemState>("/state"),
          getJson<Decision[]>("/history?limit=200"),
        ]);
        if (!alive) return;
        setState(s);
        setHistory(h);
        setConn("live");
      } catch {
        if (alive) setConn("down");
      }
    });
    return () => {
      alive = false;
      stop();
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const stop = poll(10000, async () => {
      try {
        const m = await getJson<Metrics | null>(`/metrics?window=${metricsWindow}`);
        if (alive) setMetrics(m);
      } catch {
        // connection state is owned by the /state loop
      }
    });
    return () => {
      alive = false;
      stop();
    };
  }, [metricsWindow]);

  return { state, history, metrics, conn };
}
