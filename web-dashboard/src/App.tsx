import { useState } from "react";
import Login from "./ui/Login";
import Home from "./ui/Home";
import Live from "./ui/Live";
import Stats from "./ui/Stats";
import { isSignedIn, signOut } from "./lib/session";
import { useSystem, type Conn, type MetricsWindow } from "./lib/useSystem";

export default function App() {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  if (!signedIn) return <Login onSignIn={() => setSignedIn(true)} />;
  return <Dashboard onSignOut={() => { signOut(); setSignedIn(false); }} />;
}

type Tab = "home" | "live" | "stats";

function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const [tab, setTab] = useState<Tab>("home");
  const [win, setWin] = useState<MetricsWindow>("session");
  const { state, history, metrics, conn } = useSystem(win);

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
        </div>

        <footer className="muted" style={{ fontSize: 12, textAlign: "center", marginTop: 8 }}>
          build {__BUILD_STAMP__}
        </footer>
      </div>

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
      </nav>
    </>
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

