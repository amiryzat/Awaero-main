// The JSON the app consumes. Mirrors PRD.md Section 4.6 exactly; the Mac state
// server (Phase 2) publishes this shape. Change both sides together.

export type Profile = "T" | "A" | "B" | "C";
export type Mode = "PASSIVE" | "ACTIVE" | "MANUAL";
// Pin order in arduino/room_node.ino. lamp (desk lamp) and ac came with the
// 5-appliance policy; a log recorded before them simply reads false.
export type Appliances = { light: boolean; fan: boolean; tv: boolean; lamp: boolean; ac: boolean };

export type Decision = {
  at: string; // ISO 8601
  date_inferred: boolean;
  mode: Mode;
  profile: string; // Profile | gesture name | "OVERRIDE"
  people: number | null;
  pose: string | null;
  vlm: string | null;
  phone: string | null;
  vlm_latency_s: number | null;
  decide_latency_ms: number | null;
  actuate_latency_ms: number | null;
  appliances: Appliances;
};

// GET /state
export type SystemState = {
  online: boolean; // false when live_log.csv is missing or stale
  stale_seconds: number;
  source: "live" | "replay"; // replay MUST be visible in the UI
  current: Decision | null;
  gate_active: boolean; // pose and VLM disagreed and pose won
  override: { active: boolean; expires_in_s: number } | null;
};

export type Stat = { n: number; mean: number; p50: number; p95: number };
export type Summ = { n: number; correct: number; pct: number };

// One row of trials.csv, exactly as the server returns it (all strings).
export type TrialRow = {
  time: string;
  expected: string;
  got: string;
  correct: string; // "True" | "False"
  mode: string;
  online: string;
  decide_latency_ms: string;
  actuate_latency_ms: string;
  vlm_latency_s: string;
};

// GET /trials. rows are newest first, capped at 50 by the server.
export type TrialsReport = {
  rows: TrialRow[];
  n: number;
  overall: Summ | null;
  per_path: Record<string, Summ>;
};

// GET /metrics
export type Metrics = {
  window: { from: string; to: string; seconds: number };
  // Simulated Appliance Activation Reduction. null when the window holds a
  // single row, which has no measurable duration yet.
  activation: {
    reduction_pct: number;
    // Partial: the server reports only the appliances a log ACTUALLY recorded,
    // so a run from before the desk lamp and AC has no entry for them. Iterate
    // it, never index it blind.
    per_appliance: Partial<
      Record<keyof Appliances, { on_seconds: number; baseline_seconds: number; reduction_pct: number }>
    >;
  } | null;
  latency: {
    decide_ms: Record<"PASSIVE" | "ACTIVE", Stat | null>;
    actuate_ms: Stat | null;
    vlm_s: Stat | null;
  };
  profile_distribution: Record<Profile, { seconds: number; pct: number }>;
  // One entry per logged row in the window, oldest first.
  timeline: { at: string; seconds: number; mode: Mode; profile: string; appliances: Appliances }[];
  accuracy: {
    live: {
      n: number;
      correct: number;
      pct: number;
      per_profile: Record<Profile, Summ | null>;
    } | null;
    offline: { n: number; correct: number; pct: number; captured_at: string } | null;
  };
};

// ---- Display helpers ------------------------------------------------------

export const PROFILE_LABELS: Record<Profile, string> = {
  T: "Transitional",
  A: "Active",
  B: "Resting",
  C: "Unoccupied",
};

// Gesture names exactly as live_active.py writes them into the profile column.
const GESTURE_LABELS: Record<string, string> = {
  open_palm: "Open palm (TV)",
  peace: "Peace (lights)",
  fist: "Fist (all off)",
};

export function isProfile(p: string | null): p is Profile {
  return p !== null && p in PROFILE_LABELS;
}

// The profile column means a different thing per mode (PRD 4.1), so the label
// has to be picked by mode, never by the raw string alone.
export function decisionLabel(d: Decision): string {
  if (d.mode === "MANUAL") return "Manual override";
  if (d.mode === "ACTIVE") return GESTURE_LABELS[d.profile] ?? d.profile;
  return isProfile(d.profile) ? PROFILE_LABELS[d.profile] : d.profile;
}

export const APPLIANCE_KEYS = ["light", "fan", "tv", "lamp", "ac"] as const;
export const APPLIANCE_LABELS: Record<keyof Appliances, string> = {
  light: "Light",
  fan: "Fan",
  tv: "TV",
  lamp: "Desk lamp",
  ac: "AC",
};

// The seven RO3 response paths (TRIAL_PATHS in state_server.py), in the order
// the Trials and Stats tabs list them. RO3 wants at least 10 trials on each.
export const TRIAL_TARGET = 10;
export const TRIAL_PATHS = [
  { id: "A", label: "Active", sub: "sitting" },
  { id: "T", label: "Transitional", sub: "standing" },
  { id: "B", label: "Resting", sub: "lying" },
  { id: "C", label: "Unoccupied", sub: "leave the frame" },
  { id: "open_palm", label: "Open palm", sub: "TV" },
  { id: "peace", label: "Peace", sub: "lights" },
  { id: "fist", label: "Fist", sub: "all off" },
] as const;
const TRIAL_LABELS: Record<string, string> = Object.fromEntries(TRIAL_PATHS.map((p) => [p.id, p.label]));
export const trialLabel = (id: string | null | undefined) => (id ? (TRIAL_LABELS[id] ?? id) : "-");
