import { useEffect, useState } from "react";
import type { Appliances, SystemState } from "../lib/types";

// Live: the pipeline, for RO2 (PRD 7.2). Legibility over polish. This is the
// screen that explains the system to an examiner. Nothing here is faked.

export default function Live({ state }: { state: SystemState | null }) {
  const cur = state?.current ?? null;
  const online = state?.online ?? false;
  const gate = state?.gate_active ?? false;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h1 style={{ fontSize: 26 }}>Live pipeline</h1>

      <CameraFeed />

      <div className="section-title">Decision pipeline</div>
      {cur && online ? (
        <PipelineStrip
          people={cur.people}
          pose={cur.pose}
          vlm={cur.vlm}
          profile={cur.profile}
          appliances={cur.appliances}
          mode={cur.mode}
          gate={gate}
        />
      ) : (
        <div className="card">
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            No live decision. {state ? "System not running." : "Connecting..."}
          </p>
        </div>
      )}

      {gate && (
        <div
          className="card"
          style={{ fontSize: 14, fontWeight: 600, color: "var(--navy)" }}
        >
          Presence gate active: pose authoritative. The VLM and pose disagreed, so
          pose decided presence and the VLM posture was overridden.
        </div>
      )}

      {cur && online && cur.people !== null && cur.people > 1 && (
        <div className="card" style={{ fontSize: 13 }} role="note">
          <span className="muted">
            {cur.people} people in frame. The system is scoped to one occupant and reads whoever is
            sitting, so the profile describes one person, not all of them.
          </span>
        </div>
      )}

      <div className="grid">
        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>VLM latency</div>
          <div style={{ fontSize: 26, fontWeight: 800 }}>
            {cur?.vlm_latency_s != null ? `${cur.vlm_latency_s.toFixed(2)} s` : "-"}
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>last vision-model call</div>
        </div>

        <div className="card">
          <div className="section-title" style={{ marginTop: 0 }}>Phone flag</div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{cur?.phone ?? "-"}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
            metadata only, does not affect control
          </div>
        </div>
      </div>

      <div className="card" style={{ background: "var(--green-soft)", border: "1px solid #cfe6d8" }}>
        <div style={{ fontWeight: 700, color: "var(--green)" }}>Runs entirely on this device</div>
        <div style={{ fontSize: 14, marginTop: 4, color: "var(--navy)" }}>
          All inference local on this Mac. No cloud. Video stays on this machine.
        </div>
      </div>
    </div>
  );
}

// Camera feed from /frame.jpg, polled about twice a second with a cache-busting
// query (PRD 7.2 / 7.4). Polling pauses while the tab is hidden. The server
// 404s when no frame is under 5s old, including on replay, which is the correct
// "offline" state, not an error to hide.
function CameraFeed() {
  const [tick, setTick] = useState(0);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    const run = () => {
      if (!document.hidden) setTick((t) => t + 1);
    };
    const id = setInterval(run, 500);
    document.addEventListener("visibilitychange", run);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", run);
    };
  }, []);

  return (
    // Capped to a phone-sized preview so it is not huge on web. The frame shows
    // at its own aspect ratio (no cover crop), so it matches the real camera
    // output instead of being stretched to fill a 4:3 box.
    <div
      className="card"
      style={{
        maxWidth: 480,
        padding: 0,
        overflow: "hidden",
        background: "#11161c",
        display: "grid",
        placeItems: "center",
        aspectRatio: ok ? undefined : "4 / 3", // reserve space only for the offline card
      }}
    >
      <img
        src={`/frame.jpg?t=${tick}`}
        onLoad={() => setOk(true)}
        onError={() => setOk(false)}
        alt="Live camera frame"
        style={{ width: "100%", height: "auto", display: ok ? "block" : "none" }}
      />
      {!ok && (
        <div style={{ textAlign: "center", color: "#8a94a6" }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Camera feed offline</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>no fresh frame on this machine</div>
        </div>
      )}
    </div>
  );
}

function PipelineStrip({
  people,
  pose,
  vlm,
  profile,
  appliances,
  mode,
  gate,
}: {
  people: number | null;
  pose: string | null;
  vlm: string | null;
  profile: string;
  appliances: Appliances;
  mode: string;
  gate: boolean;
}) {
  return (
    <div
      className="card"
      style={{ display: "flex", flexWrap: "wrap", alignItems: "stretch", gap: 8, overflowX: "auto" }}
    >
      <Stage label="People" value={people === null ? "-" : String(people)} />
      <Arrow />
      <Stage label="Pose" value={pose ?? "-"} sub="presence" />
      <Arrow />
      <Stage
        label="VLM"
        value={vlm ?? "-"}
        sub={gate ? "overridden" : "posture"}
        struck={gate}
        badge={gate ? "gate" : undefined}
      />
      <Arrow />
      <Stage label="Fused" value={profile} highlight sub={mode} />
      <Arrow />
      <ApplianceStage appliances={appliances} mode={mode} />
    </div>
  );
}

function Stage({
  label,
  value,
  sub,
  highlight,
  struck,
  badge,
}: {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
  struck?: boolean;
  badge?: string;
}) {
  return (
    <div
      style={{
        flex: "1 1 90px",
        minWidth: 90,
        textAlign: "center",
        padding: "10px 8px",
        borderRadius: 12,
        background: highlight ? "var(--green-soft)" : "transparent",
      }}
    >
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 800,
          marginTop: 4,
          color: highlight ? "var(--green)" : "var(--navy)",
          textDecoration: struck ? "line-through" : "none",
          opacity: struck ? 0.55 : 1,
        }}
      >
        {value}
      </div>
      {badge && (
        <span
          style={{
            display: "inline-block",
            marginTop: 4,
            fontSize: 10,
            fontWeight: 700,
            color: "var(--navy)",
            background: "var(--t)",
            borderRadius: 999,
            padding: "2px 8px",
          }}
        >
          {badge}
        </span>
      )}
      {sub && !badge && (
        <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function ApplianceStage({
  appliances,
  mode,
}: {
  appliances: Appliances;
  mode: string;
}) {
  const items: [string, boolean | "auto"][] = [
    ["Light", appliances.light],
    ["Fan", mode === "ACTIVE" ? "auto" : appliances.fan], // active never sets the fan
    ["TV", appliances.tv],
    ["Lamp", appliances.lamp],
    ["AC", appliances.ac],
  ];
  return (
    <div style={{ flex: "1 1 120px", minWidth: 120, textAlign: "center", padding: "10px 8px" }}>
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
        Appliances
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 8 }}>
        {items.map(([name, on]) => (
          <div key={name} style={{ textAlign: "center" }}>
            <span
              style={{
                display: "block",
                width: 14,
                height: 14,
                borderRadius: "50%",
                margin: "0 auto",
                background: on === true ? "var(--green)" : on === "auto" ? "var(--subtle)" : "#e3e7ec",
              }}
            />
            <span className="muted" style={{ fontSize: 10 }}>{name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div style={{ display: "grid", placeItems: "center", color: "var(--subtle)", fontSize: 18 }}>
      ›
    </div>
  );
}
