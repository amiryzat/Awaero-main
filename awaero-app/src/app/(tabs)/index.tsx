import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import ReplayBanner from "@/components/ReplayBanner";
import { APPLIANCE_KEYS, decisionLabel, type Appliances } from "@/lib/state";
import { shrinkOnScroll } from "@/lib/tabBarScroll";
import { CARD_SHADOW, COLORS, themeFor } from "@/lib/theme";
import { useSystem } from "@/lib/useSystem";

function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const APPLIANCE_UI: Record<keyof Appliances, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  light: { label: "Light", icon: "bulb" },
  fan: { label: "Fan", icon: "aperture" },
  tv: { label: "TV", icon: "tv" },
  lamp: { label: "Desk lamp", icon: "flashlight" },
  ac: { label: "AC", icon: "snow" },
};

export default function Home() {
  const insets = useSafeAreaInsets();
  const { state, history, problem, current: cur } = useSystem();
  const theme = themeFor(cur);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      {...shrinkOnScroll}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Room</Text>
        <View style={styles.headerRight}>
          {cur && (
            <View style={styles.modePill}>
              <Text style={styles.modePillText}>{cur.mode}</Text>
            </View>
          )}
          <Pressable onPress={() => router.push("/settings")} hitSlop={10} accessibilityLabel="Settings">
            <Ionicons name="settings-outline" size={24} color={COLORS.muted} />
          </Pressable>
        </View>
      </View>

      <ReplayBanner state={state} />

      <View style={[styles.hero, !cur && styles.dim]}>
        <View style={[styles.ring, { borderColor: theme.dot }]}>
          <Text style={[styles.letter, { color: theme.text }]}>
            {cur?.mode === "PASSIVE" ? cur.profile : cur ? "•" : "-"}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[styles.heroLabel, { color: theme.text }]}>
            {cur ? decisionLabel(cur) : problem}
          </Text>
          {cur && <Text style={styles.updated}>Updated {ago(cur.at)}</Text>}
          {cur && state?.override?.active && (
            <Text style={styles.override}>
              Manual override active. Automatic control resumes in {mmss(state.override.expires_in_s)}.
            </Text>
          )}
        </View>
      </View>

      <View style={[styles.tiles, !cur && styles.dim]}>
        {APPLIANCE_KEYS.map((k) => {
          // Every decision row logs the full appliance vector (gesture rows
          // too, since the fused live_system.py), so the value shown is the
          // logged one. Unknown only when there is no trustworthy decision.
          const unknown = !cur;
          const on = !unknown && !!cur.appliances[k];
          return (
            <View key={k} style={[styles.tile, on && { backgroundColor: theme.tint }]}>
              <Ionicons
                name={on ? APPLIANCE_UI[k].icon : (`${APPLIANCE_UI[k].icon}-outline` as keyof typeof Ionicons.glyphMap)}
                size={26}
                color={on ? theme.text : COLORS.subtle}
              />
              <Text style={styles.tileLabel}>{APPLIANCE_UI[k].label}</Text>
              <Text style={[styles.tileState, on && { color: theme.text }]}>
                {unknown ? "-" : on ? "On" : "Off"}
              </Text>
            </View>
          );
        })}
      </View>

      <Text style={styles.sectionTitle}>Recent decisions</Text>
      <View style={styles.card}>
        {history.length === 0 && <Text style={[styles.muted, { paddingVertical: 14 }]}>No decisions logged yet</Text>}
        {history.slice(0, 5).map((d, i) => (
          <View key={`${d.at}-${i}`} style={[styles.historyRow, i > 0 && styles.divider]}>
            <View style={[styles.historyDot, { backgroundColor: themeFor(d).dot }]} />
            <View style={{ flex: 1 }}>
              <Text style={styles.historyLabel}>{decisionLabel(d)}</Text>
              <Text style={styles.subtle}>
                {d.mode === "PASSIVE" ? `Profile ${d.profile}` : d.mode === "ACTIVE" ? "Gesture" : "Phone"}
              </Text>
            </View>
            <Text style={styles.muted}>{ago(d.at)}</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 16, paddingBottom: 110, gap: 14, width: "100%", maxWidth: 520, alignSelf: "center" },
  dim: { opacity: 0.5 },

  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontSize: 28, fontWeight: "800", color: COLORS.ink },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 12 },
  modePill: { backgroundColor: COLORS.chip, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  modePillText: { fontSize: 11, fontWeight: "700", color: "#475569", letterSpacing: 0.5 },

  hero: {
    backgroundColor: COLORS.card,
    borderRadius: 20,
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    padding: 22,
    ...CARD_SHADOW,
  },
  ring: { width: 68, height: 68, borderRadius: 34, borderWidth: 3, alignItems: "center", justifyContent: "center" },
  letter: { fontSize: 30, fontWeight: "800" },
  heroLabel: { fontSize: 24, fontWeight: "800" },
  updated: { fontSize: 13, color: COLORS.subtle, marginTop: 6 },
  override: { fontSize: 13, color: "#b45309", marginTop: 6, fontWeight: "600" },

  // Five tiles: a row of three, then a row of two.
  tiles: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  tile: {
    flexGrow: 1,
    flexBasis: "28%",
    backgroundColor: COLORS.card,
    borderRadius: 18,
    padding: 16,
    gap: 4,
    ...CARD_SHADOW,
  },
  tileLabel: { fontSize: 15, fontWeight: "600", color: COLORS.ink, marginTop: 6 },
  tileState: { fontSize: 13, color: COLORS.subtle },

  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#334155", marginTop: 2, marginLeft: 4 },
  card: { backgroundColor: COLORS.card, borderRadius: 18, paddingHorizontal: 18, ...CARD_SHADOW },
  historyRow: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 14 },
  divider: { borderTopWidth: 1, borderTopColor: COLORS.hairline },
  historyDot: { width: 14, height: 14, borderRadius: 7 },
  historyLabel: { fontSize: 16, fontWeight: "600", color: COLORS.ink },

  muted: { fontSize: 15, color: COLORS.muted },
  subtle: { fontSize: 13, color: COLORS.subtle, marginTop: 1 },
});
