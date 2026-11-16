import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { APPLIANCE_LABELS } from "../lib/types";
import type { Appliances, Metrics, Profile, Stat } from "../lib/types";
import type { MetricsWindow } from "../lib/useSystem";
import RubberSegment from "./RubberSegment";

// How long the meters take to fill, and the scrambling numbers to settle.
const LOAD_MS = 950;

function reduceMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

// Stats: the RO3 report (PRD 7.3). Ordered to mirror RO3's clauses: accuracy,
// response latency, Simulated Appliance Activation Reduction, profile
// distribution. Every number carries its source and sample size. Where a figure
// is not computable the card says "not yet measured", never a zero or a guess.

const PROFILE_META: Record<Profile, { label: string; accent: string }> = {
  A: { label: "Active", accent: "var(--a)" },
  T: { label: "Transitional", accent: "var(--t)" },
  B: { label: "Resting", accent: "var(--b)" },
  C: { label: "Unoccupied", accent: "var(--c)" },
};

const WINDOWS: MetricsWindow[] = ["session", "today", "all"];

export default function Stats({
  metrics,
  window: win,
  onWindow,
}: {
  metrics: Metrics | null;
  window: MetricsWindow;
  onWindow: (w: MetricsWindow) => void;
}) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ fontSize: 26 }}>Evaluation</h1>
        <RubberSegment
          options={WINDOWS}
          value={win}
          onChange={onWindow}
          containerStyle={{ position: "relative", background: "#e9e9ec", borderRadius: 11, padding: 3 }}
        />
      </div>

      {metrics ? (
        <>
          <div className="muted" style={{ fontSize: 13 }}>
            Window: {secs(metrics.window.seconds)} of data.
          </div>
          <div className="stats-grid">
            <AccuracyByPathCard />
            <TimelineCard metrics={metrics} />
            <AccuracyCard metrics={metrics} />
            <LatencyCard metrics={metrics} />
            <ActivationCard metrics={metrics} />
            <DistributionCard metrics={metrics} />
          </div>
        </>
      ) : (
        <div className="card">
          <h3 style={{ fontSize: 16 }}>Not yet measured</h3>
          <p className="muted" style={{ fontSize: 14, marginTop: 6 }}>
            No decisions in this window yet. Run the system, or pick a wider window.
          </p>
        </div>
      )}
    </div>
  );
}

// Session timeline: one block per decision, width proportional to how long that
// profile held, colored by the locked profile palette. Reveals left-to-right on
// mount (every tab open), like a playback of the session. All from real rows.
function TimelineCard({ metrics }: { metrics: Metrics }) {
  const items = metrics.timeline.filter((t) => t.seconds > 0);
  const total = items.reduce((s, t) => s + t.seconds, 0);
  const [revealed, setRevealed] = useState(reduceMotion());

  useEffect(() => {
    const id = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const color = (p: string) => (p in PROFILE_META ? PROFILE_META[p as Profile].accent : "var(--a)");
  const name = (p: string) => (p in PROFILE_META ? PROFILE_META[p as Profile].label : p);

  return (
    <section className="card" style={{ gridColumn: "1 / -1" }}>
      <h3 style={{ fontSize: 16 }}>Session timeline</h3>
      <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        Each block is one decision; its width is how long that state held. {secs(total)} total.
      </p>

      {items.length === 0 || total === 0 ? (
        <div className="muted" style={{ fontSize: 14, marginTop: 10 }}>Not enough data yet.</div>
      ) : (
        <>
          <div
            style={{
              marginTop: 14,
              height: 34,
              borderRadius: 10,
              overflow: "hidden",
              display: "flex",
              clipPath: revealed ? "inset(0 0 0 0)" : "inset(0 100% 0 0)",
              transition: "clip-path 1100ms var(--ease-out)",
            }}
          >
            {items.map((t, i) => (
              <div
                key={i}
                title={`${name(t.profile)} · ${secs(t.seconds)} · ${t.at.slice(11, 16)}`}
                style={{ width: `${(t.seconds / total) * 100}%`, background: color(t.profile), minWidth: 1 }}
              />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <span className="muted" style={{ fontSize: 11 }}>{items[0].at.slice(11, 16)}</span>
            <span className="muted" style={{ fontSize: 11 }}>{items[items.length - 1].at.slice(11, 16)}</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 10 }}>
            {(["A", "T", "B", "C"] as Profile[]).map((p) => (
              <span key={p} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: PROFILE_META[p].accent }} />
                <span className="muted">{PROFILE_META[p].label}</span>
              </span>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

// Accuracy by response path: live trial accuracy for each detected state and
// gesture, with its sample size. This is the RO3 evaluation view that an
// examiner asks for. Real data from /trials; bars fill in on load. A path with
// no trials reads "not yet measured", never a misleading 0%.
const ACC_PATHS = [
  { id: "A", label: "Active", accent: "var(--a)" },
  { id: "T", label: "Transitional", accent: "var(--t)" },
  { id: "B", label: "Resting", accent: "var(--b)" },
  { id: "C", label: "Unoccupied", accent: "var(--c)" },
  { id: "open_palm", label: "Open palm", accent: "var(--a)" },
  { id: "peace", label: "Peace", accent: "var(--a)" },
  { id: "fist", label: "Fist", accent: "var(--a)" },
] as const;

type PathSumm = { n: number; correct: number; pct: number };

function AccuracyByPathCard() {
  const [data, setData] = useState<{ overall: PathSumm | null; per_path: Record<string, PathSumm> } | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/trials", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { if (alive) setData({ overall: d.overall ?? null, per_path: d.per_path ?? {} }); })
      .catch(() => { if (alive) setData({ overall: null, per_path: {} }); });
    return () => { alive = false; };
  }, []);

  return (
    <section className="card" style={{ gridColumn: "1 / -1" }}>
      <h3 style={{ fontSize: 16 }}>Accuracy by response path</h3>
      <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        Live trial accuracy for each detected state and gesture. RO3 targets at least 10 trials per path.
      </p>

      {data === null ? (
        <div className="muted" style={{ fontSize: 14, marginTop: 10 }}>Loading...</div>
      ) : !data.overall || data.overall.n === 0 ? (
        <div className="muted" style={{ fontSize: 14, marginTop: 10 }}>
          No live trials yet. Record some on the Trials tab.
        </div>
      ) : (
        <>
          <div style={{ ...big, marginTop: 6 }}>
            <AnimatedNumber value={data.overall.pct} suffix="%" />
            <span className="muted" style={{ fontSize: 14, fontWeight: 600, marginLeft: 8 }}>
              overall · n={data.overall.n}
            </span>
          </div>
          <div style={{ marginTop: 14 }}>
            {ACC_PATHS.map((p) => {
              const s = data.per_path[p.id];
              if (!s || s.n === 0) {
                return (
                  <div key={p.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 12 }}>
                    <span style={{ fontWeight: 600 }}>{p.label}</span>
                    <span className="muted">not yet measured</span>
                  </div>
                );
              }
              return (
                <AnimatedBar key={p.id} label={p.label} pct={s.pct} suffix={`· ${s.correct}/${s.n} correct`} color={p.accent} />
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

function AccuracyCard({ metrics }: { metrics: Metrics }) {
  const { live, offline } = metrics.accuracy;
  return (
    <section className="card">
      <h3 style={{ fontSize: 16 }}>Detection accuracy</h3>

      <div style={{ marginTop: 12 }}>
        <div className="section-title" style={{ marginTop: 0 }}>Live trial accuracy</div>
        {live ? (
          <div>
            <span style={big}>{live.pct}%</span>
            <span className="muted" style={{ marginLeft: 8 }}>n={live.n}</span>
          </div>
        ) : (
          <>
            <div style={{ ...big, color: "var(--slate)" }}>Not yet measured</div>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Produced by the Trials instrument in the phone app, which labels live
              decisions and writes trials.csv. Until it runs, there is no live figure.
            </p>
          </>
        )}
      </div>

      <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid #eef1f4" }}>
        <div className="section-title" style={{ marginTop: 0 }}>Offline accuracy (comparison)</div>
        {offline ? (
          <div style={{ fontSize: 15 }}>
            <b>{offline.pct}%</b>
            <span className="muted"> on a labelled set, n={offline.n}, captured {offline.captured_at.slice(0, 10)}</span>
          </div>
        ) : (
          <div className="muted" style={{ fontSize: 14 }}>Not yet measured</div>
        )}
      </div>
    </section>
  );
}

type LatencyRow = { label: string; stat: Stat | null; unit: string; why: string };

function LatencyCard({ metrics }: { metrics: Metrics }) {
  const { decide_ms, actuate_ms, vlm_s } = metrics.latency;
  const [open, setOpen] = useState(false);
  const rows: LatencyRow[] = [
    { label: "Decide, PASSIVE", stat: decide_ms.PASSIVE, unit: "ms",
      why: "Time to turn one camera frame into a room decision while watching the room. Well under the blink of an eye." },
    { label: "Decide, ACTIVE", stat: decide_ms.ACTIVE, unit: "ms",
      why: "The same decision step, but while reading a hand gesture instead of posture." },
    { label: "Actuate", stat: actuate_ms, unit: "ms",
      why: "Sending the on/off command to the Arduino over USB. Effectively instant." },
    { label: "VLM call", stat: vlm_s, unit: "s",
      why: "The AI vision model recognising your posture (sitting / standing / lying). This is the slowest step, and why a posture change takes a moment to show up." },
  ];
  return (
    <section className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
        <div>
          <h3 style={{ fontSize: 16 }}>Response latency</h3>
          <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Machine time. End-to-end camera-to-LED timing is measured separately.
          </p>
        </div>
        <button className="pill" onClick={() => setOpen(true)} aria-label="Explain response latency"
          style={{ padding: "6px 12px", fontSize: 13, whiteSpace: "nowrap", flexShrink: 0 }}>
          Explain ›
        </button>
      </div>

      <div className="grid" style={{ marginTop: 12 }}>
        {rows.map((r) => <StatBlock key={r.label} title={r.label} stat={r.stat} unit={r.unit} />)}
      </div>

      {open && (
        <InsightModal title="Response latency, explained" onClose={() => setOpen(false)}>
          <p className="muted" style={{ fontSize: 14, lineHeight: 1.55, margin: "0 0 3px" }}>
            The stages between seeing a camera frame and switching an appliance.
          </p>
          <p className="muted" style={{ fontSize: 12, lineHeight: 1.5, margin: 0 }}>
            <b>p50</b> typical (median) · <b>p95</b> near worst case · <b>n</b> samples measured
          </p>
          {rows.map((r) => (
            <div key={r.label} style={{ padding: "16px 0", borderTop: "1px solid #eef1f4", marginTop: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <span style={{ fontWeight: 700, fontSize: 15, color: "var(--navy)" }}>{r.label}</span>
                <span style={{ fontWeight: 800, fontSize: 16, color: "var(--navy)", whiteSpace: "nowrap" }}>
                  {r.stat ? <>{r.stat.mean}<span className="muted" style={{ fontSize: 12, fontWeight: 600 }}> {r.unit}</span></> : "-"}
                </span>
              </div>
              <p className="muted" style={{ fontSize: 13, lineHeight: 1.55, margin: "6px 0 0" }}>{r.why}</p>
              {r.stat && (
                <div className="muted" style={{ fontSize: 12, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>
                  p50 {r.stat.p50}{r.unit} · p95 {r.stat.p95}{r.unit} · n={r.stat.n}
                </div>
              )}
            </div>
          ))}
        </InsightModal>
      )}
    </section>
  );
}

function InsightModal({ title, onClose, children }: {
  title: string; onClose: () => void; children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);   // false = enter-from / exit-to state
  const calm = reduceMotion();

  // play the enter transition on the frame after mount
  useEffect(() => {
    const id = requestAnimationFrame(() => setShow(true));
    return () => cancelAnimationFrame(id);
  }, []);

  // play the exit transition, then unmount after it finishes
  const close = useCallback(() => {
    if (calm) { onClose(); return; }
    setShow(false);
    const id = setTimeout(onClose, 190);
    return () => clearTimeout(id);
  }, [onClose, calm]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  // Portaled to <body> so position:fixed covers the whole viewport (sidebar
  // included), not just the card's layout box. Blur only, no dark tint.
  return createPortal(
    <div onClick={close} style={{
      position: "fixed", inset: 0, zIndex: 100,
      background: "transparent",
      backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
      opacity: calm || show ? 1 : 0,
      transition: "opacity 180ms var(--ease-out, ease)",
    }}>
      <div onClick={(e) => e.stopPropagation()} className="card" style={{
        width: "100%", maxWidth: 460, maxHeight: "82vh", overflow: "auto", padding: 24,
        boxShadow: "0 16px 48px rgba(18,28,48,0.20)",
        transformOrigin: "center",
        transform: calm || show ? "scale(1)" : "scale(0.92)",
        opacity: calm || show ? 1 : 0,
        transition: "transform 200ms cubic-bezier(.2,.8,.25,1), opacity 170ms var(--ease-out, ease)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <h3 style={{ fontSize: 18 }}>{title}</h3>
          <button className="pill" onClick={close} aria-label="Close"
            style={{ padding: "4px 12px", fontSize: 16, lineHeight: 1 }}>×</button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}

function StatBlock({ title, stat, unit }: { title: string; stat: Stat | null; unit: string }) {
  return (
    <div style={{ padding: "12px 14px", background: "var(--bg)", borderRadius: 14 }}>
      <div className="section-title" style={{ marginTop: 0 }}>{title}</div>
      {stat ? (
        <>
          <div style={{ fontSize: 22, fontWeight: 800 }}>
            {stat.mean}
            <span style={{ fontSize: 13, fontWeight: 600 }}> {unit}</span>
            <span className="muted" style={{ fontSize: 12, fontWeight: 600 }}> mean</span>
          </div>
        </>
      ) : (
        <div className="muted" style={{ fontSize: 14 }}>not yet measured</div>
      )}
    </div>
  );
}

function ActivationCard({ metrics }: { metrics: Metrics }) {
  const a = metrics.activation;
  return (
    <section className="card">
      <h3 style={{ fontSize: 16 }}>Simulated Appliance Activation Reduction</h3>
      <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
        Simulated over LED proxies, across {secs(metrics.window.seconds)}. Not a watt or energy claim.
      </p>
      {a ? (
        <>
          <div style={{ ...big, marginTop: 8 }}>
            <AnimatedNumber value={a.reduction_pct} suffix="%" />
          </div>
          <div style={{ marginTop: 14 }}>
            {/* Only the appliances this log recorded: a run from before the
                desk lamp existed must not show an empty lamp bar. */}
            {Object.entries(a.per_appliance).map(([k, v]) => (
              <AnimatedBar
                key={k}
                label={APPLIANCE_LABELS[k as keyof Appliances] ?? k}
                pct={v!.reduction_pct}
                suffix={`off · on ${secs(v!.on_seconds)}`}
                color="var(--a)"
              />
            ))}
          </div>
        </>
      ) : (
        <div className="muted" style={{ fontSize: 14, marginTop: 8 }}>
          Window too short to measure. A single decision has no elapsed duration yet.
        </div>
      )}
    </section>
  );
}

function DistributionCard({ metrics }: { metrics: Metrics }) {
  const d = metrics.profile_distribution;
  const empty = (["A", "T", "B", "C"] as Profile[]).every((p) => d[p].seconds === 0);
  return (
    <section className="card">
      <h3 style={{ fontSize: 16 }}>Profile distribution</h3>
      <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>Dwell time in each passive profile.</p>
      {empty ? (
        <div className="muted" style={{ fontSize: 14, marginTop: 8 }}>Not yet measured</div>
      ) : (
        <div style={{ marginTop: 14 }}>
          {(["A", "T", "B", "C"] as Profile[]).map((p) => (
            <AnimatedBar
              key={p}
              label={PROFILE_META[p].label}
              pct={d[p].pct}
              suffix={`· ${secs(d[p].seconds)}`}
              color={PROFILE_META[p].accent}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// A meter that fills from zero on mount (every tab open). The percentage shows
// its real value straight away; only the headline number scrambles, so the page
// is not a wall of flickering digits.
function AnimatedBar({ label, pct, suffix, color }: { label: string; pct: number; suffix: string; color: string }) {
  const [frac, setFrac] = useState(0);
  useEffect(() => {
    setFrac(Math.max(0, Math.min(1, pct / 100)));
  }, [pct]);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
        <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{label}</span>
        <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
          {pct}% {suffix}
        </span>
      </div>
      <div style={{ height: 9, background: "#eef1f4", borderRadius: 999, marginTop: 5, overflow: "hidden" }}>
        <div
          style={{
            width: "100%",
            height: "100%",
            background: color,
            borderRadius: 999,
            transformOrigin: "left",
            transform: `scaleX(${frac})`,
            transition: `transform ${LOAD_MS}ms var(--ease-out)`,
          }}
        />
      </div>
    </div>
  );
}

// Scrambles random numbers on mount for LOAD_MS, then snaps to the exact value
// (lands as the meter finishes). After settling it tracks real updates without
// re-scrambling. Reduced motion skips the scramble entirely.
function AnimatedNumber({ value, suffix = "", decimals = 1 }: { value: number; suffix?: string; decimals?: number }) {
  const [display, setDisplay] = useState<number>(() => (reduceMotion() ? value : Math.random() * 100));
  const settled = useRef(reduceMotion());
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (reduceMotion()) {
      setDisplay(valueRef.current);
      return;
    }
    const start = performance.now();
    const id = setInterval(() => {
      if (performance.now() - start >= LOAD_MS) {
        clearInterval(id);
        settled.current = true;
        setDisplay(valueRef.current); // the exact, correct number
      } else {
        setDisplay(Math.random() * 100);
      }
    }, 55);
    return () => clearInterval(id);
  }, []); // mount only: the scramble plays once per tab open

  useEffect(() => {
    if (settled.current) setDisplay(value); // live refreshes after settle, no re-scramble
  }, [value]);

  return (
    <>
      {display.toFixed(decimals)}
      {suffix}
    </>
  );
}

const big: React.CSSProperties = { fontSize: 32, fontWeight: 800, color: "var(--navy)" };

// Seconds to a readable span, no invented precision.
function secs(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}
