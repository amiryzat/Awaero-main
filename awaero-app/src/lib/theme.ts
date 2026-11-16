import { isProfile, type Decision, type Profile } from "@/lib/state";

// App-wide color tokens. Keep colors here, not scattered across screens.
export const COLORS = {
  bg: "#f1f5f9",
  card: "#ffffff",
  ink: "#0f172a",
  muted: "#64748b",
  subtle: "#94a3b8",
  hairline: "#f1f5f9",
  chip: "#e2e8f0",
};

type Accent = { dot: string; tint: string; text: string };

// The profile drives the accent: A green, T blue, B amber, C slate.
export const PROFILE_THEME: Record<Profile, Accent> = {
  // A is green-700, not the brighter 500: next to B's amber the brighter one fails
  // the colorblind separation check (protan). Checked with the dataviz validator.
  A: { dot: "#15803d", tint: "#ecfdf5", text: "#166534" },
  T: { dot: "#3b82f6", tint: "#eff6ff", text: "#1d4ed8" },
  B: { dot: "#f59e0b", tint: "#fffbeb", text: "#b45309" },
  C: { dot: "#94a3b8", tint: "#f8fafc", text: "#475569" },
};

// Gesture and override rows carry no profile, so they get a neutral ink accent.
const NEUTRAL: Accent = { dot: "#0f172a", tint: "#f1f5f9", text: "#0f172a" };

export function themeFor(d: Decision | null): Accent {
  if (!d) return PROFILE_THEME.C;
  return d.mode === "PASSIVE" && isProfile(d.profile) ? PROFILE_THEME[d.profile] : NEUTRAL;
}

export const CARD_SHADOW = {
  shadowColor: "#000",
  shadowOpacity: 0.05,
  shadowRadius: 8,
  shadowOffset: { width: 0, height: 2 },
  elevation: 2,
} as const;
