import Ionicons from "@expo/vector-icons/Ionicons";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import ReplayBanner from "@/components/ReplayBanner";
import { APPLIANCE_KEYS, APPLIANCE_LABELS, decisionLabel } from "@/lib/state";
import { shrinkOnScroll } from "@/lib/tabBarScroll";
import { CARD_SHADOW, COLORS, themeFor } from "@/lib/theme";
import { baseUrl, useSystem } from "@/lib/useSystem";

// The Mac's annotated camera view, relayed over the LAN. live_system.py owns
// the camera and writes its latest frame; the server only serves a frame that
// is seconds old, so a stale picture can never pass as live.
// ponytail: polled stills at 2 fps, not a video stream. Each frame lands in the
// image cache. Move to a real stream if the feed needs to be smoother.
function CameraFeed({ host, enabled }: { host: string; enabled: boolean }) {
  const [uri, setUri] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!enabled) return;
      let alive = true;
      let misses = 0;
      const id = setInterval(async () => {
        const next = `${baseUrl(host)}/frame.jpg?t=${Date.now()}`;
        const ok = await Image.prefetch(next).catch(() => false);
        if (!alive) return;
        if (ok) {
          misses = 0;
          setUri(next);
        } else if (++misses >= 3) setUri(null);
      }, 500);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }, [host, enabled]),
  );

  if (enabled && uri) {
    return (
      <View style={styles.feed}>
        <Image source={{ uri }} style={StyleSheet.absoluteFill} resizeMode="contain" fadeDuration={0} />
      </View>
    );
  }
  return (
    <View style={styles.feed}>
      <Ionicons name="videocam-off" size={40} color="#64748b" />
      <Text style={styles.feedText}>Camera feed offline</Text>
      <Text style={styles.feedSub}>Shows the Mac camera while live_system.py is running.</Text>
    </View>
  );
}

function Stage({ name, value, note, struck }: { name: string; value: string; note?: string; struck?: boolean }) {
  return (
    <View style={styles.stage}>
      <Text style={styles.stageName}>{name}</Text>
      <View style={{ flex: 1, alignItems: "flex-end" }}>
        <Text style={[styles.stageValue, struck && styles.struck]}>{value}</Text>
        {note && <Text style={styles.stageNote}>{note}</Text>}
      </View>
    </View>
  );
}

export default function Live() {
  const insets = useSafeAreaInsets();
  const { state, host, status, problem, current: cur } = useSystem();
  const theme = themeFor(cur);
  const passive = cur?.mode === "PASSIVE";
  const show = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "-" : String(v));

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      {...shrinkOnScroll}
    >
      <Text style={styles.title}>Pipeline</Text>
      <ReplayBanner state={state} />

      <CameraFeed host={host} enabled={status === "ok"} />

      <View style={styles.edge}>
        <Ionicons name="lock-closed" size={16} color="#15803d" />
        <Text style={styles.edgeText}>All inference local on this Mac. No cloud. Video stays on this WiFi.</Text>
      </View>

      {!cur ? (
        <View style={styles.card}>
          <Text style={styles.empty}>{problem}. No decision to show.</Text>
        </View>
      ) : (
        <View style={styles.card}>
          <Stage name="Mode" value={cur.mode} />
          {passive ? (
            <>
              <Stage name="People" value={show(cur.people)} />
              <Stage name="Pose" value={show(cur.pose)} />
              <Stage
                name="VLM"
                value={cur.vlm ?? "not run"}
                struck={state?.gate_active}
                note={
                  state?.gate_active
                    ? "presence gate: pose authoritative"
                    : cur.vlm_latency_s !== null
                      ? `last call ${cur.vlm_latency_s} s`
                      : undefined
                }
              />
              <Stage name="Phone" value={show(cur.phone)} note="metadata only, does not affect control" />
              <Stage name="Fused profile" value={`${cur.profile}  ${decisionLabel(cur)}`} />
            </>
          ) : (
            <Stage name={cur.mode === "ACTIVE" ? "Gesture" : "Source"} value={decisionLabel(cur)} />
          )}
          <View style={[styles.stage, { borderBottomWidth: 0, alignItems: "flex-start" }]}>
            <Text style={styles.stageName}>Appliances</Text>
            <View style={styles.chips}>
              {APPLIANCE_KEYS.map((k) => {
                const on = !!cur.appliances[k];
                return (
                  <View key={k} style={[styles.chip, on && { backgroundColor: theme.tint }]}>
                    <Text style={[styles.chipText, on && { color: theme.text }]}>
                      {APPLIANCE_LABELS[k]} {on ? "on" : "off"}
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        </View>
      )}

      {cur && cur.people !== null && cur.people > 1 && (
        <View style={styles.card}>
          <Text style={styles.empty}>
            {cur.people} people in frame. The system is scoped to one occupant and reads whoever is sitting, so the
            profile describes one person, not all of them.
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 16, paddingBottom: 110, gap: 14, width: "100%", maxWidth: 520, alignSelf: "center" },
  title: { fontSize: 28, fontWeight: "800", color: COLORS.ink },

  edge: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: "#ecfdf5", borderRadius: 12, padding: 12 },
  edgeText: { flex: 1, color: "#15803d", fontSize: 13, fontWeight: "600" },

  card: { backgroundColor: COLORS.card, borderRadius: 18, paddingHorizontal: 18, ...CARD_SHADOW },
  empty: { fontSize: 15, color: COLORS.muted, paddingVertical: 18 },
  stage: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.hairline,
  },
  stageName: { fontSize: 15, color: COLORS.muted, fontWeight: "600" },
  stageValue: { fontSize: 18, fontWeight: "700", color: COLORS.ink },
  struck: { textDecorationLine: "line-through", color: COLORS.subtle },
  stageNote: { fontSize: 12, color: COLORS.subtle, marginTop: 2, textAlign: "right" },

  chips: { flex: 1, flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-end", gap: 6 },
  chip: { backgroundColor: COLORS.chip, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  chipText: { fontSize: 13, fontWeight: "700", color: COLORS.muted },

  feed: {
    aspectRatio: 4 / 3,
    borderRadius: 20,
    backgroundColor: "#0f172a",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: 24,
    overflow: "hidden",
  },
  feedText: { color: "#e2e8f0", fontSize: 16, fontWeight: "600" },
  feedSub: { color: "#64748b", fontSize: 13, textAlign: "center", maxWidth: 260 },
});
