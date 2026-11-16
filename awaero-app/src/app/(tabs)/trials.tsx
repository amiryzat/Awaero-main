import Ionicons from "@expo/vector-icons/Ionicons";
import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import ReplayBanner from "@/components/ReplayBanner";
import { isProfile, TRIAL_PATHS, TRIAL_TARGET, trialLabel, type Summ, type TrialsReport } from "@/lib/state";
import { shrinkOnScroll } from "@/lib/tabBarScroll";
import { CARD_SHADOW, COLORS, PROFILE_THEME } from "@/lib/theme";
import { arm, DELAYS, setDelay, undoLast, useTrials } from "@/lib/trials";
import { getJson, useSystem } from "@/lib/useSystem";

// Trials: the RO3 live-accuracy instrument (PRD 7.4), the same recorder as the
// web dashboard and the same trials.csv. Tap what the system SHOULD read, get
// into that state before the countdown ends, and the server scores its own
// decision at zero. This screen only sends the label and shows progress.

const GOOD = "#15803d";
const BAD = "#b91c1c";
const INK = "#0f172a";
const POSTURES = TRIAL_PATHS.slice(0, 4);
const GESTURES = TRIAL_PATHS.slice(4);
const dotFor = (id: string) => (isProfile(id) ? PROFILE_THEME[id].dot : INK);

function RecordButton({
  id,
  label,
  sub,
  summ,
  disabled,
}: {
  id: string;
  label: string;
  sub: string;
  summ?: Summ;
  disabled: boolean;
}) {
  const n = summ?.n ?? 0;
  const done = n >= TRIAL_TARGET;
  return (
    <Pressable
      style={({ pressed }) => [styles.record, disabled && styles.dim, pressed && { opacity: 0.6 }]}
      onPress={() => arm(id)}
      disabled={disabled}
      accessibilityLabel={`Record a ${label} trial`}
    >
      <View style={styles.recordHead}>
        <View style={[styles.dot, { backgroundColor: dotFor(id) }]} />
        <Text style={styles.recordLabel} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={styles.recordSub}>{sub}</Text>
      <Text style={[styles.recordCount, done && { color: GOOD }]}>
        {done ? `${n} recorded, target met` : `${n} of ${TRIAL_TARGET}`}
      </Text>
    </Pressable>
  );
}

export default function Trials() {
  const insets = useSafeAreaInsets();
  const { state, status, host, problem, current: cur } = useSystem();
  const { delay, pending, version } = useTrials();
  const [report, setReport] = useState<TrialsReport | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (status !== "ok") return;
    getJson<TrialsReport>("/trials", host)
      .then(setReport)
      .catch(() => {});
  }, [status, host]);

  // The 3 s poll picks up trials recorded from the web dashboard.
  useFocusEffect(
    useCallback(() => {
      load();
      const id = setInterval(load, 3000);
      return () => clearInterval(id);
    }, [load]),
  );
  // version bumps when this phone recorded or removed a trial: refresh at once.
  useEffect(load, [load, version]);

  const data = status === "ok" ? report : null;
  const replay = state?.source === "replay";
  // A trial is only evidence when it scores the LIVE system. Never against a
  // fixture, never while the system is down.
  const blocked = busy || !cur || replay || !!pending;
  const why = replay
    ? "Replay data. Trials are only recorded against the live system."
    : !cur
      ? `${problem}. Start live_system.py on the Mac to record trials.`
      : null;

  const last = data?.rows[0];
  const undo = () => {
    if (!last) return;
    // This deletes a row of the RO3 dataset, so it has to be asked for twice.
    Alert.alert(
      "Remove the last trial?",
      `Expected ${trialLabel(last.expected)}, system read ${trialLabel(last.got)}. This deletes it from trials.csv on the Mac.`,
      [
        { text: "Keep", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            setBusy(true);
            try {
              await undoLast();
            } catch {
              Alert.alert("Not removed", "The Mac did not answer. The trial is still in trials.csv.");
            } finally {
              setBusy(false);
            }
          },
        },
      ],
    );
  };

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      {...shrinkOnScroll}
    >
      <View style={styles.titleRow}>
        <Text style={styles.title}>Trials</Text>
        <Text style={styles.caption}>RO3 instrument</Text>
      </View>
      <ReplayBanner state={state} />

      <View style={[styles.card, styles.now]}>
        <Text style={styles.caption}>System reads now</Text>
        <Text style={[styles.nowValue, !cur && { color: COLORS.subtle }]}>{cur ? trialLabel(cur.profile) : "Offline"}</Text>
        <Text style={styles.caption}>{cur ? `${cur.mode} mode` : problem}</Text>
        <Text style={[styles.caption, { marginTop: 10, textAlign: "center" }]}>
          Tap what it should read, then get into that state before the countdown ends. The trial is scored at zero, not
          when you tap, and the phone buzzes when it captures.
        </Text>
      </View>

      <Text style={styles.sectionTitle}>Capture delay</Text>
      <View style={styles.segmented}>
        {DELAYS.map((d) => (
          <Pressable key={d} style={[styles.segment, delay === d && styles.segmentOn]} onPress={() => setDelay(d)}>
            <Text style={[styles.segmentText, delay === d && styles.segmentTextOn]}>{d}s</Text>
          </Pressable>
        ))}
      </View>
      <Text style={[styles.caption, { marginLeft: 4 }]}>Use 20s for Unoccupied: the room needs time to read empty.</Text>

      {why && (
        <View style={styles.card}>
          <Text style={styles.why}>{why}</Text>
        </View>
      )}

      <Text style={styles.sectionTitle}>Record a posture trial</Text>
      <View style={styles.grid}>
        {POSTURES.map((p) => (
          <RecordButton key={p.id} {...p} summ={data?.per_path[p.id]} disabled={blocked} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>Record a gesture trial</Text>
      <View style={styles.grid}>
        {GESTURES.map((p) => (
          <RecordButton key={p.id} {...p} summ={data?.per_path[p.id]} disabled={blocked} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>Accuracy so far</Text>
      <View style={styles.card}>
        {data?.overall ? (
          <View style={styles.overall}>
            <Text style={styles.hero}>{data.overall.pct}%</Text>
            <Text style={styles.caption}>
              {data.overall.correct} of {data.overall.n} trials correct
            </Text>
          </View>
        ) : (
          <Text style={styles.caption}>{data ? "No trials yet. Record one above." : "Not loaded yet."}</Text>
        )}
        {TRIAL_PATHS.map((p) => {
          const s = data?.per_path[p.id];
          const n = s?.n ?? 0;
          return (
            <View key={p.id} style={styles.pathRow}>
              <Text style={styles.pathLabel}>{p.label}</Text>
              <View style={styles.track}>
                <View
                  style={[
                    styles.fill,
                    { width: `${Math.min(1, n / TRIAL_TARGET) * 100}%`, backgroundColor: dotFor(p.id) },
                  ]}
                />
              </View>
              <Text style={styles.pathValue}>{s ? `${s.pct}%, n=${n}` : "no trials"}</Text>
            </View>
          );
        })}
        <Text style={[styles.caption, { marginTop: 12 }]}>
          Bars show progress to {TRIAL_TARGET} trials per response path. Source: trials.csv on the Mac.
        </Text>
      </View>

      {data && data.rows.length > 0 && (
        <>
          <View style={styles.titleRow}>
            <Text style={styles.sectionTitle}>Recent</Text>
            <Pressable
              style={({ pressed }) => [styles.undo, (busy || !!pending) && styles.dim, pressed && { opacity: 0.6 }]}
              onPress={undo}
              disabled={busy || !!pending}
            >
              <Text style={styles.undoText}>Undo last</Text>
            </Pressable>
          </View>
          <View style={[styles.card, { paddingVertical: 0 }]}>
            {data.rows.slice(0, 8).map((r, i) => {
              const ok = r.correct === "True";
              return (
                <View key={`${r.time}-${i}`} style={[styles.recentRow, i > 0 && styles.divider]}>
                  <Text style={styles.recentText}>
                    {trialLabel(r.expected)}
                    <Text style={styles.recentGot}> read as {trialLabel(r.got)}</Text>
                  </Text>
                  <Ionicons name={ok ? "checkmark-circle" : "close-circle"} size={20} color={ok ? GOOD : BAD} />
                </View>
              );
            })}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  // Extra bottom room: the capture banner floats above the tab bar.
  content: { padding: 16, paddingBottom: 190, gap: 14, width: "100%", maxWidth: 520, alignSelf: "center" },
  dim: { opacity: 0.45 },
  titleRow: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: 10 },
  title: { fontSize: 28, fontWeight: "800", color: COLORS.ink },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#334155", marginTop: 2, marginLeft: 4 },
  caption: { fontSize: 12, color: COLORS.muted, lineHeight: 17 },
  card: { backgroundColor: COLORS.card, borderRadius: 18, padding: 18, ...CARD_SHADOW },

  now: { alignItems: "center" },
  nowValue: { fontSize: 32, fontWeight: "800", color: COLORS.ink, marginVertical: 2 },
  why: { fontSize: 14, fontWeight: "600", color: "#b45309", lineHeight: 20 },

  segmented: { flexDirection: "row", backgroundColor: COLORS.chip, borderRadius: 12, padding: 3 },
  segment: { flex: 1, paddingVertical: 8, borderRadius: 10, alignItems: "center" },
  segmentOn: { backgroundColor: COLORS.card },
  segmentText: { fontSize: 14, fontWeight: "600", color: COLORS.muted },
  segmentTextOn: { color: COLORS.ink },

  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  record: {
    flexGrow: 1,
    flexBasis: "40%",
    backgroundColor: COLORS.card,
    borderRadius: 18,
    padding: 16,
    minHeight: 96,
    ...CARD_SHADOW,
  },
  recordHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 12, height: 12, borderRadius: 6 },
  recordLabel: { flexShrink: 1, fontSize: 17, fontWeight: "700", color: COLORS.ink },
  recordSub: { fontSize: 13, color: COLORS.muted, marginTop: 2 },
  recordCount: { fontSize: 13, fontWeight: "700", color: COLORS.muted, marginTop: 10 },

  overall: { flexDirection: "row", alignItems: "baseline", gap: 10, marginBottom: 4 },
  hero: { fontSize: 44, fontWeight: "800", color: COLORS.ink, letterSpacing: -1 },
  pathRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 12 },
  pathLabel: { width: 96, fontSize: 13, fontWeight: "600", color: COLORS.ink },
  track: { flex: 1, height: 8, borderRadius: 4, backgroundColor: COLORS.chip, overflow: "hidden" },
  fill: { height: 8, borderRadius: 4 },
  pathValue: { width: 92, textAlign: "right", fontSize: 12, color: COLORS.muted, fontVariant: ["tabular-nums"] },

  undo: { backgroundColor: COLORS.chip, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 7 },
  undoText: { fontSize: 13, fontWeight: "700", color: COLORS.ink },
  recentRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 13 },
  divider: { borderTopWidth: 1, borderTopColor: COLORS.hairline },
  recentText: { flex: 1, fontSize: 15, fontWeight: "600", color: COLORS.ink },
  recentGot: { fontWeight: "400", color: COLORS.muted },
});
