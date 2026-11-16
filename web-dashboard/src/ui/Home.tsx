import type { Appliances, Decision, Metrics, SystemState } from "../lib/types";

// Home: the smart-home face (PRD 7.1), mirroring the reference middle panel.
// Every value traces to a fixture row. Nothing invented.

const PROFILE_META: Record<string, { label: string; accent: string }> = {
  A: { label: "Active", accent: "var(--a)" },
  T: { label: "Transitional", accent: "var(--t)" },
  B: { label: "Resting", accent: "var(--b)" },
  C: { label: "Unoccupied", accent: "var(--c)" },
};
const PROFILE_ORDER = ["A", "T", "B", "C"] as const;

export default function Home({
  state,
  history,
  metrics,
}: {
  state: SystemState | null;
  history: Decision[];
  metrics: Metrics | null;
}) {
  const cur = state?.current ?? null;
  const online = state?.online ?? false;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div className="muted" style={{ fontSize: 14 }}>Welcome back</div>
          <h1 style={{ fontSize: 26 }}>Your room</h1>
        </div>
        {cur && online && <span className="chip">{cur.mode}</span>}
      </div>

      <Hero state={state} />

      <div>
        <div className="section-title">Current state</div>
        <div className="grid-4">
          {PROFILE_ORDER.map((p) => (
            <ProfileCard
              key={p}
              profile={p}
              active={online && cur?.mode === "PASSIVE" && cur?.profile === p}
              pct={metrics?.profile_distribution?.[p]?.pct ?? null}
            />
          ))}
        </div>
      </div>

      <div>
        <div className="section-title">Appliances</div>
        <div className="grid-4">
          <ApplianceTile name="Light" value={applianceState(cur, online, "light")} />
          <ApplianceTile name="Fan" value={applianceState(cur, online, "fan")} />
          <ApplianceTile name="TV" value={applianceState(cur, online, "tv")} />
          <ApplianceTile name="Desk lamp" value={applianceState(cur, online, "lamp")} />
          <ApplianceTile name="AC" value={applianceState(cur, online, "ac")} />
        </div>
      </div>

      <div>
        <div className="section-title">Recent activity</div>
        <RecentList history={history} />
      </div>
    </div>
  );
}

function Hero({ state }: { state: SystemState | null }) {
  const cur = state?.current ?? null;
  const online = state?.online ?? false;

  // Offline: never present a stale profile as current (PRD 7.1).
  if (!cur || !online) {
    return (
      <section className="card" style={{ opacity: 0.6, textAlign: "center", padding: 28 }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: "var(--slate)" }}>-</div>
        <div style={{ fontWeight: 700, marginTop: 4 }}>System not running</div>
        <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
          {state ? `last update ${state.stale_seconds}s ago` : "connecting..."}
        </div>
      </section>
    );
  }

  const isProfile = cur.profile in PROFILE_META;
  const meta = PROFILE_META[cur.profile];

  return (
    <section
      className="card"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 20,
      }}
    >
      <div
        style={{
          width: 76,
          height: 76,
          borderRadius: 20,
          background: isProfile ? meta.accent : "var(--a)",
          color: "var(--navy)",
          display: "grid",
          placeItems: "center",
          fontSize: 38,
          fontWeight: 800,
          flexShrink: 0,
        }}
      >
        {isProfile ? cur.profile : "•"}
      </div>
      <div style={{ flex: 1 }}>
        <h2 style={{ fontSize: 22 }}>{isProfile ? meta.label : cur.profile}</h2>
        <div className="muted" style={{ fontSize: 14, marginTop: 2 }}>
          {cur.mode} mode · updated {state!.stale_seconds}s ago
        </div>
        {state!.override?.active && (
          <div style={{ fontSize: 13, color: "var(--green)", fontWeight: 600, marginTop: 4 }}>
            Manual hold, {state!.override.expires_in_s}s left
          </div>
        )}
      </div>
    </section>
  );
}

function ProfileCard({ profile, active, pct }: { profile: string; active: boolean; pct: number | null }) {
  const meta = PROFILE_META[profile];
  return (
    <div
      className="card"
      style={{
        background: active ? meta.accent : "var(--card)",
        color: "var(--navy)",
        padding: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {!active && (
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: meta.accent, display: "inline-block" }} />
        )}
        <span style={{ fontWeight: 700 }}>{meta.label}</span>
      </div>
      <div style={{ fontSize: 13, marginTop: 10, opacity: active ? 0.9 : 0.6 }}>
        {pct === null ? "-" : `${pct}% dwell`}
      </div>
    </div>
  );
}

type TileState = "on" | "off" | "auto";

// Active mode never sets the fan (PRD 2), so it reads as auto, never a guessed
// on/off. A tile that lies is forbidden (PRD rule 2).
function applianceState(cur: Decision | null, online: boolean, key: keyof Appliances): TileState | null {
  if (!cur || !online) return null;
  if (cur.mode === "ACTIVE" && key === "fan") return "auto";
  return cur.appliances[key] ? "on" : "off";
}

function ApplianceTile({ name, value }: { name: string; value: TileState | null }) {
  const color = value === "on" ? "var(--green)" : value === "auto" ? "var(--subtle)" : "var(--subtle)";
  const label = value === null ? "-" : value === "on" ? "On" : value === "auto" ? "Auto" : "Off";
  return (
    <div className="card" style={{ padding: 16, opacity: value === null ? 0.6 : 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontWeight: 700 }}>{name}</span>
        <span
          style={{
            width: 38,
            height: 22,
            borderRadius: 999,
            background: value === "on" ? "var(--green)" : "#e3e7ec",
            position: "relative",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              position: "absolute",
              top: 2,
              left: value === "on" ? 18 : 2,
              width: 18,
              height: 18,
              borderRadius: "50%",
              background: "#fff",
              transition: "left 160ms cubic-bezier(0.23, 1, 0.32, 1)",
            }}
          />
        </span>
      </div>
      <div style={{ fontSize: 13, color, marginTop: 10, fontWeight: 600 }}>{label}</div>
    </div>
  );
}

function RecentList({ history }: { history: Decision[] }) {
  const rows = history.slice(0, 5);
  if (rows.length === 0) {
    return (
      <div className="card">
        <p className="muted" style={{ fontSize: 14, margin: 0 }}>No activity yet.</p>
      </div>
    );
  }
  return (
    <div className="card" style={{ display: "grid", gap: 0, padding: 0, overflow: "hidden" }}>
      {rows.map((d, i) => {
        const isProfile = d.profile in PROFILE_META;
        const label = isProfile ? PROFILE_META[d.profile].label : d.profile;
        return (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "13px 18px",
              borderTop: i === 0 ? "none" : "1px solid #eef1f4",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: isProfile ? PROFILE_META[d.profile].accent : "var(--a)",
                }}
              />
              <span style={{ fontWeight: 600, fontSize: 14 }}>{label}</span>
              <span className="muted" style={{ fontSize: 12 }}>{d.mode}</span>
            </div>
            <span className="muted" style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
              {d.at.slice(11, 19)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
