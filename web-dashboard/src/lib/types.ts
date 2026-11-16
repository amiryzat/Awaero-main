// Mirrors state_server.py and PRD Section 4 exactly. Same shapes as
// app-monitor/PRD.md Section 4.6: change both sides together.

export type Profile = "T" | "A" | "B" | "C";
export type Mode = "PASSIVE" | "ACTIVE" | "MANUAL";
// Pin order in arduino/room_node.ino. lamp (desk lamp) and ac were added with
// the revised decision profiles; logs recorded before them simply read false.
export type Appliances = {
  light: boolean; fan: boolean; tv: boolean; lamp: boolean; ac: boolean;
};

export const APPLIANCE_LABELS: Record<keyof Appliances, string> = {
  light: "Light", fan: "Fan", tv: "TV", lamp: "Desk lamp", ac: "AC",
};

export type Decision = {
  at: string; // ISO 8601
  date_inferred: boolean; // the log has no date column, see PRD 4.2
  mode: Mode;
  profile: string; // Profile | gesture name | "OVERRIDE"
  people: number | null;
  pose: string | null;
  vlm: string | null;
  phone: string | null; // metadata only, never affects control
  vlm_latency_s: number | null;
  decide_latency_ms: number | null;
  actuate_latency_ms: number | null;
  appliances: Appliances;
};

export type Health = {
  ok: boolean;
  source: "live" | "replay";
  rows: number;
  log_path: string;
  lan_ip: string;
  local_name: string | null;
};

export type SystemState = {
  online: boolean; // false when the log is missing or stale
  stale_seconds: number;
  source: "live" | "replay"; // replay MUST be visible in the UI
  current: Decision | null;
  gate_active: boolean; // pose and VLM disagreed and pose won
  override: { active: boolean; expires_in_s: number } | null;
};

export type Stat = { n: number; mean: number; p50: number; p95: number };

export type Metrics = {
  window: { from: string; to: string; seconds: number };
  activation: {
    // Simulated Appliance Activation Reduction
    reduction_pct: number;
    // Partial: the server reports only the appliances a log ACTUALLY recorded,
    // so a run from before the desk lamp and AC existed has no entry for them.
    // Never index this blind - iterate it.
    per_appliance: Partial<
      Record<
        keyof Appliances,
        { on_seconds: number; baseline_seconds: number; reduction_pct: number }
      >
    >;
  } | null; // null when the window holds a single row
  latency: {
    decide_ms: Record<"PASSIVE" | "ACTIVE", Stat | null>;
    actuate_ms: Stat | null;
    vlm_s: Stat | null;
  };
  profile_distribution: Record<Profile, { seconds: number; pct: number }>;
  timeline: {
    at: string;
    seconds: number;
    mode: Mode;
    profile: string;
    appliances: Appliances;
  }[]; // oldest first
  accuracy: {
    live: {
      n: number;
      correct: number;
      pct: number;
      per_profile: Record<Profile, { n: number; correct: number; pct: number } | null>;
    } | null;
    offline: { n: number; correct: number; pct: number; captured_at: string } | null;
  };
};
