import { useCallback, useEffect, useState } from "react";
import Login from "./ui/Login";
import Home from "./ui/Home";
import Live from "./ui/Live";
import Stats from "./ui/Stats";
import Trials, { LABELS } from "./ui/Trials";
import Capture from "./ui/Capture";
import RubberSegment from "./ui/RubberSegment";
import TechText from "./ui/TechText";
import { isSignedIn, signOut } from "./lib/session";
import { useSystem, type Conn, type MetricsWindow } from "./lib/useSystem";
import type { SystemState } from "./lib/types";

export default function App() {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  if (!signedIn) return <Login onSignIn={() => setSignedIn(true)} />;
  return <Dashboard onSignOut={() => { signOut(); setSignedIn(false); }} />;
}

type Tab = "home" | "live" | "stats" | "trials" | "capture";

// Line icons for the web sidebar. Inline SVG, no icon dependency.
const svg = {
  width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  "aria-hidden": true, focusable: false,
};
const HomeIcon = () => (<svg {...svg}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></svg>);
const LiveIcon = () => (<svg {...svg}><rect x="3" y="6" width="13" height="12" rx="2" /><path d="M16 10l5-3v10l-5-3" /></svg>);
const StatsIcon = () => (<svg {...svg}><path d="M5 21V10" /><path d="M12 21V4" /><path d="M19 21v-7" /></svg>);
const TrialsIcon = () => (<svg {...svg}><path d="M9 11l3 3 8-8" /><path d="M21 12a9 9 0 1 1-6.2-8.6" /></svg>);
const CaptureIcon = () => (<svg {...svg}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></svg>);

const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "home", label: "Home", icon: <HomeIcon /> },
  { id: "live", label: "Live", icon: <LiveIcon /> },
  { id: "stats", label: "Stats", icon: <StatsIcon /> },
  { id: "trials", label: "Trials", icon: <TrialsIcon /> },
  { id: "capture", label: "Capture", icon: <CaptureIcon /> },
];

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

  const content = (
    <>
      {state?.source === "replay" && (
        <div className="banner">Replay data, not a live system</div>
      )}

      <div key={tab} className="fade-in">
        {tab === "home" && <Home state={state} history={history} metrics={metrics} />}
        {tab === "live" && <Live state={state} />}
        {tab === "stats" && <Stats metrics={metrics} window={win} onWindow={setWin} />}
        {tab === "trials" && (
          <Trials state={state} delay={delay} setDelay={setDelay} pending={pending} onArm={arm} />
        )}
        {tab === "capture" && <Capture />}
      </div>

      <footer
        className="muted"
        style={{ fontSize: 12, marginTop: 8, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "center", gap: 12 }}
      >
        <ConnLine conn={conn} online={state?.online} stale={state?.stale_seconds} />
        <span>build {__BUILD_STAMP__}</span>
      </footer>
    </>
  );

  return (
    <>
      {/* Web: a left sidebar. Hidden under 900px (CSS), where the topbar + bottom
          tab bar take over. Resizing the window flips between the two. */}
      <aside className="sidebar">
        {/* Compact TechText logo: hover reveals the dashed outline. Labels, letter
            dragging, click-kick and the idle sweep are off: too busy, and a
            permanent animation loop, for a 52px nav logo on every screen. */}
        <div
          role="img"
          aria-label="Awaero"
          style={{ width: "100%", height: 52, position: "relative", color: "var(--navy)", marginBottom: 14 }}
        >
          <TechText
            text="AWAERO"
            fontWeight={700}
            fontSize={36}
            letterSpacing={0.02}
            align="left"
            reveal="letter"
            reach={70}
            dashLength={3}
            dashGap={2}
            strokeWidth={1.2}
            specks={6}
            labels={false}
            selection={false}
            draggable={false}
            clickKick={false}
            sweep={false}
            accentColor="#7eb994"
            intro="none"
          />
        </div>
        {/* The dark active pill is the sliding RubberSegment thumb: it stretches
            down or up to the next item and settles, like the mobile tab bar. */}
        <nav>
          <RubberSegment
            vertical
            options={NAV.map((n) => n.id)}
            value={tab}
            onChange={setTab}
            label={(id) => {
              const n = NAV.find((x) => x.id === id)!;
              return (
                <>
                  {n.icon}
                  <span>{n.label}</span>
                </>
              );
            }}
            thumb="var(--primary)"
            thumbShadow="none"
            thumbRadius={18}
            activeText="#fafafa"
            inactiveText="var(--slate)"
            itemClassName="sidebar-item"
            itemStyle={{ padding: "11px 14px", fontSize: 15, fontWeight: 500, textTransform: "none", borderRadius: 18 }}
            containerStyle={{ display: "flex", gap: 4, width: "100%" }}
          />
        </nav>
        <button
          className="pill"
          style={{ marginTop: "auto", padding: "10px 16px", fontSize: 14 }}
          onClick={onSignOut}
        >
          Sign out
        </button>
      </aside>

      {/* Phone: topbar + bottom tab bar (unchanged). */}
      <div className="topbar">
        <span className="brand">AWAERO</span>
        <button className="pill" style={{ padding: "8px 16px", fontSize: 13 }} onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="main">
        <div className="container">{content}</div>
      </div>

      <CaptureBanner pending={pending} flash={flash} state={state} onCancel={() => setPending(null)} />

      <nav className="tabbar">
        <RubberSegment
          options={NAV.map((n) => n.id)}
          value={tab}
          onChange={setTab}
          label={(id) => NAV.find((n) => n.id === id)?.label ?? id}
          thumb="var(--primary)"
          thumbShadow="0 1px 4px rgba(0,0,0,0.22)"
          activeText="#fafafa"
          inactiveText="var(--slate)"
          itemStyle={{ padding: "10px 22px", fontSize: 14 }}
          containerStyle={{ position: "relative", display: "flex", gap: 4 }}
        />
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
          boxShadow: "0 6px 24px rgba(0,0,0,0.18)",
        }}>
          <div style={{ fontSize: 38, fontWeight: 800, color: "var(--navy)", lineHeight: 1, minWidth: 54 }}>
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
          {flash!.ok ? "✓ Correct" : "✗ Miss"} · expected {LABELS[flash!.expected] ?? flash!.expected},
          system read {LABELS[flash!.got] ?? flash!.got}
        </div>
        {(flash!.vlm || flash!.decide) && (
          <div className="muted" style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>
            latency · VLM detect {flash!.vlm ? `${flash!.vlm}s` : "-"} · decide {flash!.decide ? `${flash!.decide}ms` : "-"}
          </div>
        )}
      </div>
    </div>
  );
}

function ConnLine({ conn, online, stale }: { conn: Conn; online?: boolean; stale?: number }) {
  const live = conn === "live" && online;
  const text =
    conn === "connecting"
      ? "Connecting to the system..."
      : conn === "down"
        ? "Cannot reach the system server"
        : online
          ? "Live"
          : `System not running (last update ${stale ?? "?"}s ago)`;
  const color = live ? "var(--green)" : conn === "down" ? "#c0392b" : "var(--slate)";
  const bg = live ? "var(--green-soft)" : conn === "down" ? "#fdecea" : "#eef1f4";
  return (
    <div
      style={{
        display: "inline-flex", alignItems: "center", gap: 7,
        fontSize: 13, fontWeight: 600, color, background: bg,
        padding: "5px 12px", borderRadius: 999, width: "fit-content",
      }}
    >
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: "currentColor", flexShrink: 0 }} />
      {text}
    </div>
  );
}
