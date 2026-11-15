import { useCallback, useEffect, useState } from "react";
import type { SystemState } from "../lib/types";

// Trials: the RO3 live-accuracy recorder. You declare the GROUND TRUTH (what the
// system SHOULD read right now); the server snapshots its own live decision and
// scores it. RO3 wants >=10 trials per response path. The server owns the
// measurement (trials.csv); this screen only sends the label and shows progress.

const TARGET = 10; // RO3: >=10 trials per response path

const POSTURES = [
  { id: "A", label: "Active", sub: "sitting", accent: "var(--a)" },
  { id: "T", label: "Transitional", sub: "standing", accent: "var(--t)" },
  { id: "B", label: "Resting", sub: "lying", accent: "var(--b)" },
  { id: "C", label: "Unoccupied", sub: "empty", accent: "var(--c)" },
] as const;

const GESTURES = [
  { id: "open_palm", label: "Open palm", sub: "TV" },
  { id: "peace", label: "Peace", sub: "lights" },
  { id: "fist", label: "Fist", sub: "all off" },
] as const;

const LABELS: Record<string, string> = {
  A: "Active", T: "Transitional", B: "Resting", C: "Unoccupied",
  open_palm: "Open palm", peace: "Peace", fist: "Fist",
};

type Summ = { n: number; correct: number; pct: number };
type TrialRow = { time: string; expected: string; got: string; correct: string; mode: string };
type Report = { rows: TrialRow[]; n: number; overall: Summ | null; per_path: Record<string, Summ> };

export default function Trials({ state }: { state: SystemState | null }) {
  const [report, setReport] = useState<Report | null>(null);
  const [flash, setFlash] = useState<{ expected: string; got: string; ok: boolean } | null>(null);
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

  const record = useCallback(async (expected: string) => {
    setBusy(true);
    try {
      const r = await fetch("/trials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected }),
      });
      const row = await r.json();
      if (r.ok) setFlash({ expected: row.expected, got: row.got || "-", ok: row.correct === "True" });
      await refresh();
    } catch {
      /* ignore: next poll refreshes */
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const undo = useCallback(async () => {
    setBusy(true);
    try {
      await fetch("/trials/last", { method: "DELETE" });
      setFlash(null);
      await refresh();
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const cur = state?.current ?? null;
  const online = state?.online ?? false;
  const liveProfile = online && cur ? cur.profile : null;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <div className="muted" style={{ fontSize: 14 }}>RO3 instrument</div>
        <h1 style={{ fontSize: 26 }}>Trials</h1>
      </div>

      {/* Live now: what the system reads this instant, so you tap at the right moment */}
      <section className="card" style={{ textAlign: "center" }}>
        <div className="muted" style={{ fontSize: 13 }}>System reads now</div>
        <div style={{ fontSize: 32, fontWeight: 800, marginTop: 2, color: online ? "var(--navy)" : "var(--slate)" }}>
          {liveProfile ? (LABELS[liveProfile] ?? liveProfile) : online ? "..." : "offline"}
        </div>
        <div className="muted" style={{ fontSize: 13 }}>
          {online ? `${cur?.mode} mode` : "start live_system.py to record trials"}
        </div>
        <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          Get into the state, then tap what it <b>should</b> be. One tap = one scored trial.
        </p>
      </section>

      {flash && (
        <div
          className="card"
          style={{
            padding: "12px 16px", fontWeight: 600,
            color: flash.ok ? "var(--green)" : "#c0392b",
            borderLeft: `5px solid ${flash.ok ? "var(--green)" : "#c0392b"}`,
          }}
        >
          {flash.ok ? "✓ Correct" : "✗ Miss"} — expected {LABELS[flash.expected] ?? flash.expected},
          system read {LABELS[flash.got] ?? flash.got}
        </div>
      )}

      <div>
        <div className="section-title">Record a posture trial</div>
        <div className="grid-4">
          {POSTURES.map((p) => (
            <RecordButton key={p.id} id={p.id} label={p.label} sub={p.sub} accent={p.accent}
              count={report?.per_path[p.id]?.n ?? 0} disabled={busy || !online} onClick={record} />
          ))}
        </div>
      </div>

      <div>
        <div className="section-title">Record a gesture trial</div>
        <div className="grid-4">
          {GESTURES.map((g) => (
            <RecordButton key={g.id} id={g.id} label={g.label} sub={g.sub} accent="var(--green)"
              count={report?.per_path[g.id]?.n ?? 0} disabled={busy || !online} onClick={record} />
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
        opacity: disabled ? 0.5 : 1, borderLeft: `5px solid ${accent}`, font: "inherit",
      }}
    >
      <div style={{ fontWeight: 700, color: "var(--navy)" }}>{label}</div>
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
          background: n >= TARGET ? "var(--green)" : "var(--t)" }} />
      </span>
      <span className="muted" style={{ width: 92, textAlign: "right", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
        {summ ? `${summ.pct}% · ${n}/${TARGET}` : `0/${TARGET}`}
      </span>
    </div>
  );
}
