import { useCallback, useEffect, useState } from "react";
import type { SystemState } from "../lib/types";

// Trials: the RO3 live-accuracy recorder. You declare the GROUND TRUTH (what the
// system SHOULD read right now); the server snapshots its own live decision and
// scores it. RO3 wants >=10 trials per response path. The server owns the
// measurement (trials.csv); this screen only sends the label and shows progress.
//
// The capture COUNTDOWN (arm -> move into position -> fire at zero) lives in App,
// not here, so it survives switching to the Live tab mid-count. This screen just
// arms it (onArm) and reflects the pending state.

export const TARGET = 10; // RO3: >=10 trials per response path
const DELAYS = [3, 10, 15, 20] as const;

const POSTURES = [
  { id: "A", label: "Active", sub: "sitting", accent: "var(--a)" },
  { id: "T", label: "Transitional", sub: "standing", accent: "var(--t)" },
  { id: "B", label: "Resting", sub: "lying", accent: "var(--b)" },
  { id: "C", label: "Unoccupied", sub: "leave frame", accent: "var(--c)" },
] as const;

const GESTURES = [
  { id: "open_palm", label: "Open palm", sub: "TV" },
  { id: "peace", label: "Peace", sub: "lights" },
  { id: "fist", label: "Fist", sub: "all off" },
] as const;

export const LABELS: Record<string, string> = {
  A: "Active", T: "Transitional", B: "Resting", C: "Unoccupied",
  open_palm: "Open palm", peace: "Peace", fist: "Fist",
};

type Summ = { n: number; correct: number; pct: number };
type TrialRow = { time: string; expected: string; got: string; correct: string; mode: string };
type Report = { rows: TrialRow[]; n: number; overall: Summ | null; per_path: Record<string, Summ> };

export default function Trials({ state, delay, setDelay, pending, onArm }: {
  state: SystemState | null;
  delay: number;
  setDelay: (n: number) => void;
  pending: { expected: string; left: number } | null;
  onArm: (id: string) => void;
}) {
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setReport(await (await fetch("/trials", { cache: "no-store" })).json());
    } catch {
      /* server down: the connection line in the shell already says so */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const undo = useCallback(async () => {
    setBusy(true);
    try {
      await fetch("/trials/last", { method: "DELETE" });
      await refresh();
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const cur = state?.current ?? null;
  const online = state?.online ?? false;
  const liveProfile = online && cur ? cur.profile : null;
  const blocked = busy || !online || !!pending;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ fontSize: 26 }}>Trials</h1>
        <span className="muted" style={{ fontSize: 14 }}>RO3 instrument</span>
      </div>

      {/* Live now: what the system reads this instant */}
      <section className="card" style={{ textAlign: "center" }}>
        <div className="muted" style={{ fontSize: 13 }}>System reads now</div>
        <div style={{ fontSize: 32, fontWeight: 800, marginTop: 2, color: online ? "var(--navy)" : "var(--slate)" }}>
          {liveProfile ? (LABELS[liveProfile] ?? liveProfile) : online ? "..." : "offline"}
        </div>
        <div className="muted" style={{ fontSize: 13 }}>
          {online ? `${cur?.mode} mode` : "start live_system.py to record trials"}
        </div>
        <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          Tap what it <b>should</b> be, then move into that state before the countdown ends.
          The trial is scored at zero, not when you tap. You can switch to the Live tab while it counts.
        </p>
      </section>

      {/* Capture delay: C needs ~20s to clear EMPTY_SECONDS; A/T a few seconds */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 13 }}>Capture delay</span>
        {DELAYS.map((d) => (
          <button
            key={d}
            onClick={() => setDelay(d)}
            className="card"
            style={{
              padding: "4px 14px", fontWeight: 600, fontSize: 13, cursor: "pointer", font: "inherit",
              borderLeft: delay === d ? "3px solid var(--green)" : "3px solid transparent",
              color: delay === d ? "var(--green)" : "var(--slate)",
            }}
          >
            {d}s
          </button>
        ))}
        <span className="muted" style={{ fontSize: 12 }}>· use 20s for Unoccupied</span>
      </div>

      <div>
        <div className="section-title">Record a posture trial</div>
        <div className="grid-4">
          {POSTURES.map((p) => (
            <RecordButton key={p.id} id={p.id} label={p.label} sub={p.sub} accent={p.accent}
              count={report?.per_path[p.id]?.n ?? 0} disabled={blocked} onClick={onArm} />
          ))}
        </div>
      </div>

      <div>
        <div className="section-title">Record a gesture trial</div>
        <div className="grid-4">
          {GESTURES.map((g) => (
            <RecordButton key={g.id} id={g.id} label={g.label} sub={g.sub} accent="var(--a)"
              count={report?.per_path[g.id]?.n ?? 0} disabled={blocked} onClick={onArm} />
          ))}
        </div>
      </div>

      <div>
        <div className="section-title">Accuracy so far</div>
        <section className="card">
          {report?.overall ? (
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontSize: 40, fontWeight: 800, color: "var(--green)" }}>{report.overall.pct}%</span>
              <span className="muted">{report.overall.correct}/{report.overall.n} trials</span>
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 14 }}>No trials yet. Record one above.</div>
          )}
          <div style={{ display: "grid", gap: 8, marginTop: 14 }}>
            {[...POSTURES, ...GESTURES].map((x) => (
              <PathRow key={x.id} label={LABELS[x.id]} summ={report?.per_path[x.id]} />
            ))}
          </div>
        </section>
      </div>

      {report && report.rows.length > 0 && (
        <div>
          <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Recent</span>
            <button className="pill" style={{ padding: "6px 14px", fontSize: 13 }} onClick={undo} disabled={busy}>
              Undo last
            </button>
          </div>
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            {report.rows.slice(0, 8).map((r, i) => {
              const ok = r.correct === "True";
              return (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "11px 16px", borderTop: i === 0 ? "none" : "1px solid #eef1f4",
                }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>
                    {LABELS[r.expected] ?? r.expected}
                    <span className="muted" style={{ fontWeight: 400 }}> → {LABELS[r.got] ?? (r.got || "-")}</span>
                  </span>
                  <span style={{ color: ok ? "var(--green)" : "#c0392b", fontWeight: 700, fontSize: 14 }}>
                    {ok ? "✓" : "✗"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function RecordButton({ id, label, sub, accent, count, disabled, onClick }: {
  id: string; label: string; sub: string; accent: string; count: number;
  disabled: boolean; onClick: (id: string) => void;
}) {
  const done = count >= TARGET;
  return (
    <button
      className="card"
      onClick={() => onClick(id)}
      disabled={disabled}
      style={{
        padding: 14, textAlign: "left", cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1, font: "inherit",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: accent, display: "inline-block", flexShrink: 0 }} />
        <span style={{ fontWeight: 700, color: "var(--navy)" }}>{label}</span>
      </div>
      <div className="muted" style={{ fontSize: 12 }}>{sub}</div>
      <div style={{ fontSize: 12, marginTop: 8, fontWeight: 600, color: done ? "var(--green)" : "var(--slate)" }}>
        {done ? `✓ ${count}` : `${count}/${TARGET}`}
      </div>
    </button>
  );
}

function PathRow({ label, summ }: { label: string; summ?: Summ }) {
  const n = summ?.n ?? 0;
  const frac = Math.min(1, n / TARGET);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
      <span style={{ width: 96, flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, height: 8, background: "#eef1f4", borderRadius: 99, overflow: "hidden" }}>
        <span style={{ display: "block", height: "100%", width: `${frac * 100}%`,
          background: n >= TARGET ? "var(--a)" : "var(--t)" }} />
      </span>
      <span className="muted" style={{ width: 92, textAlign: "right", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
        {summ ? `${summ.pct}% · ${n}/${TARGET}` : `0/${TARGET}`}
      </span>
    </div>
  );
}
