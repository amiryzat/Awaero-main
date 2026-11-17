import { useCallback, useEffect, useState } from "react";

// Capture: build the VLM A/B evaluation set from the phone. The mounted camera
// (what production sees) streams here; you get into a position, tap the matching
// activity, and the server saves the CURRENT CLEAN frame (live_raw.jpg, no
// overlays) under that label into eval_frames/. Later, eval_two_models.py runs
// Moondream and Qwen over this same set and scores which reads the scene better.

const TARGET = 10; // frames per activity for a usable eval set

const ACTIVITIES = [
  { id: "studying", label: "Studying", sub: "sitting at the desk", accent: "var(--a)" },
  { id: "resting", label: "Resting", sub: "lying on the bed", accent: "var(--b)" },
  { id: "standing", label: "Standing", sub: "moving around", accent: "var(--t)" },
  { id: "empty", label: "Empty", sub: "no one in frame", accent: "var(--c)" },
] as const;

type Info = { counts: Record<string, number>; live: boolean; labels: string[] };

export default function Capture() {
  const [info, setInfo] = useState<Info | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ ok: boolean; text: string } | null>(null);
  const [tick, setTick] = useState(0);
  const [frameOk, setFrameOk] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setInfo(await (await fetch("/capture", { cache: "no-store" })).json());
    } catch {
      /* server down: the connection line already says so */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 3000);
    return () => clearInterval(id);
  }, [refresh]);

  // Poll the camera preview ~twice a second; pause while the tab is hidden.
  useEffect(() => {
    const run = () => { if (!document.hidden) setTick((t) => t + 1); };
    const id = setInterval(run, 500);
    document.addEventListener("visibilitychange", run);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", run); };
  }, []);

  const capture = useCallback(async (label: string) => {
    setBusy(true);
    try {
      const r = await fetch("/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });
      const res = await r.json();
      if (r.ok) {
        setFlash({ ok: true, text: `Saved — ${label}` });
        setInfo((i) => (i ? { ...i, counts: res.counts } : i));
      } else {
        setFlash({ ok: false, text: res.error || "failed" });
      }
    } catch {
      setFlash({ ok: false, text: "server unreachable" });
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 2500);
    return () => clearTimeout(id);
  }, [flash]);

  const live = info?.live ?? false;
  const total = info ? Object.values(info.counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <div className="muted" style={{ fontSize: 14 }}>VLM evaluation set</div>
        <h1 style={{ fontSize: 26 }}>Capture</h1>
      </div>

      <section className="card" style={{ padding: 0, overflow: "hidden", background: "#11161c",
        display: "grid", placeItems: "center", aspectRatio: frameOk ? undefined : "4 / 3" }}>
        <img
          src={`/frame.jpg?t=${tick}`}
          onLoad={() => setFrameOk(true)}
          onError={() => setFrameOk(false)}
          alt="Live camera"
          style={{ width: "100%", height: "auto", display: frameOk ? "block" : "none", maxWidth: 480 }}
        />
        {!frameOk && (
          <div style={{ textAlign: "center", color: "#8a94a6", padding: 24 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Camera feed offline</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>start live_system.py on the Mac</div>
          </div>
        )}
      </section>

      <p className="muted" style={{ fontSize: 13, margin: 0 }}>
        Get into the position, then tap the matching activity. The server saves the
        <b> current frame</b> under that label. Aim for <b>{TARGET}</b> of each.
      </p>

      <div className="grid-4">
        {ACTIVITIES.map((a) => {
          const n = info?.counts[a.id] ?? 0;
          const done = n >= TARGET;
          return (
            <button
              key={a.id}
              className="card"
              onClick={() => capture(a.id)}
              disabled={busy || !live}
              style={{
                padding: 14, textAlign: "left", font: "inherit",
                cursor: busy || !live ? "not-allowed" : "pointer",
                opacity: busy || !live ? 0.5 : 1,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: a.accent,
                  display: "inline-block", flexShrink: 0 }} />
                <span style={{ fontWeight: 700, color: "var(--navy)" }}>{a.label}</span>
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{a.sub}</div>
              <div style={{ fontSize: 12, marginTop: 8, fontWeight: 600,
                color: done ? "var(--green)" : "var(--slate)" }}>
                {done ? `✓ ${n}` : `${n}/${TARGET}`}
              </div>
            </button>
          );
        })}
      </div>

      <div className="muted" style={{ fontSize: 13 }}>
        {total} frame{total === 1 ? "" : "s"} captured ·{" "}
        {live ? "camera live" : "camera offline — buttons disabled until live_system.py runs"}
      </div>

      {flash && (
        <div className="card" style={{ padding: "12px 16px", fontWeight: 600,
          color: flash.ok ? "var(--green)" : "#c0392b" }}>
          {flash.ok ? "✓ " : "✗ "}{flash.text}
        </div>
      )}
    </div>
  );
}
