import { useFocusEffect } from "expo-router";
import { useCallback, useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import ReplayBanner from "@/components/ReplayBanner";
import {
  APPLIANCE_KEYS,
  APPLIANCE_LABELS,
  isProfile,
  PROFILE_LABELS,
  TRIAL_PATHS,
  type Metrics,
  type Profile,
  type Stat,
  type TrialsReport,
} from "@/lib/state";
import { shrinkOnScroll } from "@/lib/tabBarScroll";
import { CARD_SHADOW, COLORS, PROFILE_THEME } from "@/lib/theme";
import { getJson, useSystem } from "@/lib/useSystem";

// The RO3 report, ordered like RO3's own clauses (PRD 7.3). Every figure comes
// from GET /metrics; anything the server cannot compute renders as
// "Not yet measured", never as a zero.

const WINDOWS = [
  ["session", "Session"],
  ["today", "Today"],
  ["all", "All"],
] as const;
type Win = (typeof WINDOWS)[number][0];

const PROFILE_ORDER: Profile[] = ["T", "A", "B", "C"];
const INK = "#0f172a";

function dur(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`;
}
const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const day = (iso: string) => new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });

function Card({ title, source, children }: { title: string; source?: string; children: ReactNode }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {children}
      {source && <Text style={styles.source}>{source}</Text>}
    </View>
  );
}

function NotMeasured({ why }: { why: string }) {
  return (
    <>
      <Text style={styles.notMeasured}>Not yet measured</Text>
      <Text style={styles.caption}>{why}</Text>
    </>
  );
}

// A strip of time, oldest on the left. Each segment's width is its duration.
// Neighbours of the same color are merged so a 1 px gap only marks a change.
function Lane({ segs }: { segs: { seconds: number; color: string }[] }) {
  const merged: { seconds: number; color: string }[] = [];
  for (const s of segs) {
    if (s.seconds <= 0) continue;
    const last = merged[merged.length - 1];
    if (last && last.color === s.color) last.seconds += s.seconds;
    else merged.push({ ...s });
  }
  return (
    <View style={styles.lane}>
      {merged.map((s, i) => (
        <View key={i} style={{ flex: s.seconds, backgroundColor: s.color }} />
      ))}
    </View>
  );
}

function LatencyRow({ name, stat, unit, last }: { name: string; stat: Stat | null; unit: string; last?: boolean }) {
  return (
    <View style={[styles.latRow, last && { borderBottomWidth: 0 }]}>
      <Text style={styles.latName}>{name}</Text>
      {stat ? (
        <View style={{ alignItems: "flex-end" }}>
          <Text style={styles.latValue}>
            {stat.mean} {unit}
          </Text>
          <Text style={styles.caption}>
            mean of {stat.n}, median {stat.p50}, p95 {stat.p95}
          </Text>
        </View>
      ) : (
        <Text style={styles.latMissing}>Not yet measured</Text>
      )}
    </View>
  );
}

export default function Stats() {
  const insets = useSafeAreaInsets();
  const { state, status, host, problem } = useSystem();
  const [win, setWin] = useState<Win>("session");
  // undefined = not loaded yet, null = the server has no rows for this window
  const [m, setM] = useState<Metrics | null | undefined>(undefined);
  const [trials, setTrials] = useState<TrialsReport | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (status !== "ok") return;
      let alive = true;
      const load = () => {
        getJson<Metrics | null>(`/metrics?window=${win}`, host)
          .then((x) => alive && setM(x))
          .catch(() => {});
        getJson<TrialsReport>("/trials", host)
          .then((x) => alive && setTrials(x))
          .catch(() => {});
      };
      load();
      const id = setInterval(load, 5000);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }, [win, status, host]),
  );

  const data = status === "ok" ? m : undefined;
  const origin = state?.source === "replay" ? "replay fixture" : "live_log.csv";
  const source = data
    ? `Source: ${origin}, ${data.timeline.length} logged decisions, ${clock(data.window.from)} to ${clock(data.window.to)}`
    : undefined;
  const offline = data?.accuracy.offline;
  // Trial accuracy covers every recorded trial: trials.csv is not windowed.
  const acc = status === "ok" ? trials : null;
  const act = data?.activation;
  const tracked = act ? APPLIANCE_KEYS.filter((k) => act.per_appliance[k]) : [];
  const passiveSeconds = data ? PROFILE_ORDER.reduce((a, p) => a + data.profile_distribution[p].seconds, 0) : 0;
  const hasOther = data?.timeline.some((t) => t.mode !== "PASSIVE" && t.seconds > 0);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      {...shrinkOnScroll}
    >
      <Text style={styles.title}>Stats</Text>
      <ReplayBanner state={state} />

      <View style={styles.segmented}>
        {WINDOWS.map(([key, label]) => (
          <Pressable
            key={key}
            style={[styles.segment, win === key && styles.segmentOn]}
            onPress={() => {
              setM(undefined);
              setWin(key);
            }}
          >
            <Text style={[styles.segmentText, win === key && styles.segmentTextOn]}>{label}</Text>
          </Pressable>
        ))}
      </View>

      {status !== "ok" && (
        <View style={styles.card}>
          <Text style={styles.caption}>{problem}</Text>
        </View>
      )}

      <Card
        title="Trial accuracy"
        source={[acc?.overall && "Source: trials.csv, all recorded trials", offline && "Offline source: classify_results.csv"]
          .filter(Boolean)
          .join(". ")}
      >
        {acc?.overall ? (
          <>
            <Text style={styles.hero}>{acc.overall.pct}%</Text>
            <Text style={styles.caption}>
              Trial accuracy (n={acc.overall.n}): {acc.overall.correct} of {acc.overall.n} live trials correct. The
              operator declares the true state and the server scores its own decision.
            </Text>
            {TRIAL_PATHS.map((p) => {
              const sm = acc.per_path[p.id];
              const color = isProfile(p.id) ? PROFILE_THEME[p.id].dot : INK;
              return (
                <View key={p.id} style={styles.distRow}>
                  <View style={[styles.swatch, { backgroundColor: color }]} />
                  <Text style={styles.distLabel}>{p.label}</Text>
                  <View style={styles.distTrack}>
                    {sm && <View style={[styles.distFill, { width: `${sm.pct}%`, backgroundColor: color }]} />}
                  </View>
                  <Text style={styles.distValue}>{sm ? `${sm.pct}%` : "-"}</Text>
                  <Text style={styles.distTime}>{sm ? `${sm.correct}/${sm.n}` : "none"}</Text>
                </View>
              );
            })}
          </>
        ) : (
          <NotMeasured why="Needs labelled trials. Record them on the Trials tab. The decision log has no ground truth." />
        )}
        {offline && (
          <View style={styles.compare}>
            <Text style={styles.compareValue}>
              {offline.pct}% (n={offline.n})
            </Text>
            <Text style={styles.caption}>
              Offline VLM evaluation on saved frames, {offline.correct} of {offline.n} correct, {day(offline.captured_at)}. A
              comparison only, not live accuracy.
            </Text>
          </View>
        )}
      </Card>

      <Card title="Response latency" source={source}>
        {data === null ? (
          <NotMeasured why="No decisions logged in this window." />
        ) : (
          <>
            <LatencyRow name="Decide, passive" stat={data?.latency.decide_ms.PASSIVE ?? null} unit="ms" />
            <LatencyRow name="Decide, active" stat={data?.latency.decide_ms.ACTIVE ?? null} unit="ms" />
            <LatencyRow name="Actuate" stat={data?.latency.actuate_ms ?? null} unit="ms" />
            <LatencyRow name="VLM call" stat={data?.latency.vlm_s ?? null} unit="s" />
            <View style={[styles.latRow, { borderBottomWidth: 0 }]}>
              <Text style={styles.latName}>End to end (trials)</Text>
              <Text style={styles.latMissing}>Not yet measured</Text>
            </View>
            <Text style={styles.caption}>
              Decide is frame to committed decision. Actuate is decision to serial write. End to end comes from trials
              and will include operator reaction time.
            </Text>
          </>
        )}
      </Card>

      <Card title="Simulated Appliance Activation Reduction" source={source}>
        {!data || !act ? (
          <NotMeasured why={data === undefined ? "Loading." : "Needs at least two logged decisions in this window."} />
        ) : (
          <>
            <Text style={styles.hero}>{act.reduction_pct}%</Text>
            <Text style={styles.caption}>
              Mean of {tracked.map((k) => APPLIANCE_LABELS[k]).join(", ")} over {dur(data.window.seconds)}, against an
              always-on baseline. Simulated: LEDs stand in for the appliances.
            </Text>
            <View style={styles.lanes}>
              {/* Only the appliances this log recorded. A run from before the
                  desk lamp and AC existed must not show them as "off all along". */}
              {tracked.map((k) => (
                <View key={k} style={styles.laneRow}>
                  <Text style={styles.laneLabel}>{APPLIANCE_LABELS[k]}</Text>
                  <View style={{ flex: 1 }}>
                    <Lane segs={data.timeline.map((t) => ({ seconds: t.seconds, color: t.appliances[k] ? INK : COLORS.chip }))} />
                    <Text style={styles.laneNote}>
                      on {dur(act.per_appliance[k]!.on_seconds)} of {dur(act.per_appliance[k]!.baseline_seconds)}
                    </Text>
                  </View>
                  <Text style={styles.laneValue}>{act.per_appliance[k]!.reduction_pct}%</Text>
                </View>
              ))}
            </View>
            <View style={styles.axis}>
              <Text style={styles.axisText}>{clock(data.window.from)}</Text>
              <View style={styles.legend}>
                <View style={[styles.swatch, { backgroundColor: INK }]} />
                <Text style={styles.axisText}>on</Text>
                <View style={[styles.swatch, { backgroundColor: COLORS.chip }]} />
                <Text style={styles.axisText}>off</Text>
              </View>
              <Text style={styles.axisText}>{clock(data.window.to)}</Text>
            </View>
          </>
        )}
      </Card>

      <Card title="Profile distribution" source={source}>
        {!data || passiveSeconds <= 0 ? (
          <NotMeasured why={data === undefined ? "Loading." : "Needs passive decisions with a measurable duration."} />
        ) : (
          <>
            <Lane
              segs={data.timeline.map((t) => ({
                seconds: t.seconds,
                color: t.mode === "PASSIVE" && isProfile(t.profile) ? PROFILE_THEME[t.profile].dot : INK,
              }))}
            />
            <View style={styles.axis}>
              <Text style={styles.axisText}>{clock(data.window.from)}</Text>
              {hasOther && (
                <View style={styles.legend}>
                  <View style={[styles.swatch, { backgroundColor: INK }]} />
                  <Text style={styles.axisText}>gesture or manual</Text>
                </View>
              )}
              <Text style={styles.axisText}>{clock(data.window.to)}</Text>
            </View>
            {PROFILE_ORDER.map((p) => {
              const d = data.profile_distribution[p];
              return (
                <View key={p} style={styles.distRow}>
                  <View style={[styles.swatch, { backgroundColor: PROFILE_THEME[p].dot }]} />
                  <Text style={styles.distLabel}>
                    {p} {PROFILE_LABELS[p]}
                  </Text>
                  <View style={styles.distTrack}>
                    <View style={[styles.distFill, { width: `${d.pct}%`, backgroundColor: PROFILE_THEME[p].dot }]} />
                  </View>
                  <Text style={styles.distValue}>{d.pct}%</Text>
                  <Text style={styles.distTime}>{dur(d.seconds)}</Text>
                </View>
              );
            })}
            <Text style={[styles.caption, { marginTop: 12 }]}>Share of passive time, {dur(passiveSeconds)} in total.</Text>
          </>
        )}
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 16, paddingBottom: 110, gap: 14, width: "100%", maxWidth: 520, alignSelf: "center" },
  title: { fontSize: 28, fontWeight: "800", color: COLORS.ink },

  segmented: { flexDirection: "row", backgroundColor: COLORS.chip, borderRadius: 12, padding: 3 },
  segment: { flex: 1, paddingVertical: 8, borderRadius: 10, alignItems: "center" },
  segmentOn: { backgroundColor: COLORS.card },
  segmentText: { fontSize: 14, fontWeight: "600", color: COLORS.muted },
  segmentTextOn: { color: COLORS.ink },

  card: { backgroundColor: COLORS.card, borderRadius: 18, padding: 18, ...CARD_SHADOW },
  cardTitle: { fontSize: 13, fontWeight: "700", color: COLORS.muted, marginBottom: 8 },
  source: { fontSize: 11, color: COLORS.subtle, marginTop: 12 },
  caption: { fontSize: 12, color: COLORS.muted, lineHeight: 17, marginTop: 2 },
  notMeasured: { fontSize: 22, fontWeight: "800", color: COLORS.subtle },
  hero: { fontSize: 44, fontWeight: "800", color: COLORS.ink, letterSpacing: -1 },

  compare: { marginTop: 14, paddingTop: 12, borderTopWidth: 1, borderTopColor: COLORS.hairline },
  compareValue: { fontSize: 18, fontWeight: "700", color: COLORS.ink },

  latRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.hairline,
  },
  latName: { fontSize: 15, fontWeight: "600", color: COLORS.ink },
  latValue: { fontSize: 18, fontWeight: "800", color: COLORS.ink },
  latMissing: { fontSize: 14, fontWeight: "600", color: COLORS.subtle },

  lane: { flexDirection: "row", height: 14, borderRadius: 4, overflow: "hidden", gap: 1, backgroundColor: COLORS.card },
  lanes: { gap: 12, marginTop: 16 },
  laneRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  laneLabel: { width: 72, fontSize: 13, fontWeight: "600", color: COLORS.ink },
  laneNote: { fontSize: 11, color: COLORS.muted, marginTop: 3 },
  laneValue: { width: 52, textAlign: "right", fontSize: 14, fontWeight: "800", color: COLORS.ink },

  axis: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8 },
  axisText: { fontSize: 11, color: COLORS.muted },
  legend: { flexDirection: "row", alignItems: "center", gap: 5 },
  swatch: { width: 10, height: 10, borderRadius: 3 },

  distRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 12 },
  distLabel: { width: 116, fontSize: 13, fontWeight: "600", color: COLORS.ink },
  distTrack: { flex: 1, height: 8, justifyContent: "center" },
  distFill: { height: 8, borderRadius: 4, minWidth: 2 },
  distValue: { width: 60, textAlign: "right", fontSize: 13, fontWeight: "800", color: COLORS.ink },
  distTime: { width: 50, textAlign: "right", fontSize: 12, color: COLORS.muted },
});
