import { useCallback, useEffect, useState } from "react";
import Login from "./ui/Login";
import Home from "./ui/Home";
import Live from "./ui/Live";
import Stats from "./ui/Stats";
import Trials, { LABELS } from "./ui/Trials";
import { isSignedIn, signOut } from "./lib/session";
import { useSystem, type Conn, type MetricsWindow } from "./lib/useSystem";
import type { SystemState } from "./lib/types";

export default function App() {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  if (!signedIn) return <Login onSignIn={() => setSignedIn(true)} />;
  return <Dashboard onSignOut={() => { signOut(); setSignedIn(false); }} />;
}

type Tab = "home" | "live" | "stats" | "trials";

function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const [tab, setTab] = useState<Tab>("home");
  const [win, setWin] = useState<MetricsWindow>("session");
  const { state, history, metrics, conn } = useSystem(win);

  // Trial capture countdown lives HERE, not in Trials, so it survives switching
  // to the Live tab mid-count (you arm it, then watch the profile change live).
  const [delay, setDelay] = useState(10);
  const [pending, setPending] = useState<{ expected: string; left: number } | null>(null);
  const [flash, setFlash] = useState<
    { expected: string; got: string; ok: boolean; vlm: string; decide: string } | null
  >(null);

  const fire = useCallback(async (expected: string) => {
    try {
      const r = await fetch("/trials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected }),
      });
      const row = await r.json();
      if (r.ok) setFlash({
        expected: row.expected, got: row.got || "-", ok: row.correct === "True",
        vlm: row.vlm_latency_s || "", decide: row.decide_latency_ms || "",
      });
    } catch {
      /* ignore: the Trials tab re-polls /trials every 3s */
    }
  }, []);

  // One tick per second; fires at zero.
  useEffect(() => {
    if (!pending) return;
    if (pending.left <= 0) {
      void fire(pending.expected);
      setPending(null);
      return;
    }
    const id = setTimeout(() => setPending((p) => (p ? { ...p, left: p.left - 1 } : null)), 1000);
    return () => clearTimeout(id);
  }, [pending, fire]);

  // Clear the result flash after a few seconds.
  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 4000);
    return () => clearTimeout(id);
  }, [flash]);

  const arm = useCallback((expected: string) => {
    setFlash(null);
    setPending({ expected, left: delay });
  }, [delay]);

  return (
    <>
      <div className="topbar">
        <span className="brand">AWAERO</span>
        <button className="pill" style={{ padding: "8px 16px", fontSize: 13 }} onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="container">
        {state?.source === "replay" && (
          <div className="banner">Replay data, not a live system</div>
        )}

        <ConnLine conn={conn} online={state?.online} stale={state?.stale_seconds} />

        <div key={tab} className="fade-in">
          {tab === "home" && <Home state={state} history={history} metrics={metrics} />}
          {tab === "live" && <Live state={state} />}
          {tab === "stats" && <Stats metrics={metrics} window={win} onWindow={setWin} />}
          {tab === "trials" && (
            <Trials state={state} delay={delay} setDelay={setDelay} pending={pending} onArm={arm} />
          )}
        </div>

        <footer className="muted" style={{ fontSize: 12, textAlign: "center", marginTop: 8 }}>
          build {__BUILD_STAMP__}
        </footer>
      </div>

      <CaptureBanner pending={pending} flash={flash} state={state} onCancel={() => setPending(null)} />

      <nav className="tabbar">
        <button className={tab === "home" ? "active" : ""} onClick={() => setTab("home")}>
          Home
        </button>
        <button className={tab === "live" ? "active" : ""} onClick={() => setTab("live")}>
          Live
        </button>
        <button className={tab === "stats" ? "active" : ""} onClick={() => setTab("stats")}>
          Stats
        </button>
        <button className={tab === "trials" ? "active" : ""} onClick={() => setTab("trials")}>
          Trials
        </button>
      </nav>
    </>
  );
}

// Floating countdown / result, pinned above the tab bar so it shows on EVERY tab
// (the whole point: arm on Trials, switch to Live, still see the count and result).
function CaptureBanner({ pending, flash, state, onCancel }: {
  pending: { expected: string; left: number } | null;
  flash: { expected: string; got: string; ok: boolean; vlm: string; decide: string } | null;
  state: SystemState | null;
  onCancel: () => void;
}) {
  if (!pending && !flash) return null;
  const online = state?.online ?? false;
  const liveProfile = online && state?.current ? state.current.profile : null;
  const wrap: React.CSSProperties = {
    position: "fixed", left: 12, right: 12, bottom: 74, zIndex: 50,
    maxWidth: 560, margin: "0 auto",
  };

  if (pending) {
    return (
      <div style={wrap}>
        <div className="card" style={{
          display: "flex", alignItems: "center", gap: 14, padding: "12px 16px",
          borderLeft: "6px solid var(--t)", boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
        }}>
          <div style={{ fontSize: 38, fontWeight: 800, color: "var(--t)", lineHeight: 1, minWidth: 54 }}>
            {pending.left}s
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700 }}>Recording {LABELS[pending.expected] ?? pending.expected}</div>
            <div className="muted" style={{ fontSize: 13 }}>
              get into position · reads <b>{liveProfile ? (LABELS[liveProfile] ?? liveProfile) : "..."}</b>
            </div>
          </div>
          <button className="pill" style={{ padding: "6px 16px", fontSize: 13 }} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={wrap}>
      <div className="card" style={{
        padding: "12px 16px", fontWeight: 600,
        color: flash!.ok ? "var(--green)" : "#c0392b",
        borderLeft: `6px solid ${flash!.ok ? "var(--green)" : "#c0392b"}`,
        boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
      }}>
        <div>
          {flash!.ok ? "✓ Correct" : "✗ Miss"} — expected {LABELS[flash!.expected] ?? flash!.expected},
          system read {LABELS[flash!.got] ?? flash!.got}
        </div>
        {(flash!.vlm || flash!.decide) && (
          <div className="muted" style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>
            latency · VLM detect {flash!.vlm ? `${flash!.vlm}s` : "—"} · decide {flash!.decide ? `${flash!.decide}ms` : "—"}
          </div>
        )}
      </div>
    </div>
  );
}

function ConnLine({ conn, online, stale }: { conn: Conn; online?: boolean; stale?: number }) {
  const text =
    conn === "connecting"
      ? "Connecting to the system..."
      : conn === "down"
        ? "Cannot reach the system server"
        : online
          ? "Live"
          : `System not running (last update ${stale ?? "?"}s ago)`;
  const color = conn === "live" && online ? "var(--green)" : conn === "down" ? "#c0392b" : "var(--slate)";
  return (
    <div style={{ fontSize: 13, fontWeight: 600, color }}>
      <span style={{ marginRight: 6 }}>●</span>
      {text}
    </div>
  );
}
