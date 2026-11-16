import Ionicons from "@expo/vector-icons/Ionicons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { trialLabel } from "@/lib/state";
import { CARD_SHADOW, COLORS } from "@/lib/theme";
import { cancel, useTrials } from "@/lib/trials";
import { useSystem } from "@/lib/useSystem";

const GOOD = "#15803d";
const BAD = "#b91c1c";

// The trial countdown, then its result, floating above the tab bar on EVERY tab.
// That is the point: arm on Trials, switch to Live, still see the count.
export default function CaptureBanner() {
  const insets = useSafeAreaInsets();
  const { pending, flash } = useTrials();
  const { current: cur } = useSystem();
  if (!pending && !flash) return null;

  const wrap = [styles.wrap, { bottom: insets.bottom + 84 }];

  if (pending) {
    return (
      <View style={wrap} pointerEvents="box-none">
        <View style={styles.card}>
          <Text style={styles.count}>{pending.left}s</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.head}>Recording {trialLabel(pending.expected)}</Text>
            <Text style={styles.sub}>Get into position. Reads {cur ? trialLabel(cur.profile) : "nothing"} now.</Text>
          </View>
          <Pressable style={({ pressed }) => [styles.cancel, pressed && { opacity: 0.6 }]} onPress={cancel} hitSlop={8}>
            <Text style={styles.cancelText}>Cancel</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if ("error" in flash!) {
    return (
      <View style={wrap} pointerEvents="none">
        <View style={[styles.card, { borderLeftWidth: 6, borderLeftColor: BAD }]}>
          <Ionicons name="alert-circle" size={28} color={BAD} />
          <Text style={[styles.head, { flex: 1, color: BAD }]}>{flash.error}</Text>
        </View>
      </View>
    );
  }

  const r = flash!.row;
  const ok = r.correct === "True";
  const tint = ok ? GOOD : BAD;
  return (
    <View style={wrap} pointerEvents="none">
      <View style={[styles.card, { borderLeftWidth: 6, borderLeftColor: tint }]}>
        <Ionicons name={ok ? "checkmark-circle" : "close-circle"} size={28} color={tint} />
        <View style={{ flex: 1 }}>
          <Text style={[styles.head, { color: tint }]}>{ok ? "Correct" : "Miss"}</Text>
          <Text style={styles.sub}>
            Expected {trialLabel(r.expected)}, system read {trialLabel(r.got)}.
          </Text>
          {(r.vlm_latency_s || r.decide_latency_ms) && (
            <Text style={styles.sub}>
              VLM detect {r.vlm_latency_s ? `${r.vlm_latency_s} s` : "-"}, decide{" "}
              {r.decide_latency_ms ? `${r.decide_latency_ms} ms` : "-"}
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: 16, right: 16, alignItems: "center" },
  card: {
    width: "100%",
    maxWidth: 488,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: COLORS.card,
    borderRadius: 18,
    paddingVertical: 12,
    paddingHorizontal: 16,
    ...CARD_SHADOW,
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 12,
  },
  count: { fontSize: 36, fontWeight: "800", color: COLORS.ink, minWidth: 62, fontVariant: ["tabular-nums"] },
  head: { fontSize: 16, fontWeight: "700", color: COLORS.ink },
  sub: { fontSize: 13, color: COLORS.muted, marginTop: 2 },
  cancel: { backgroundColor: COLORS.chip, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
  cancelText: { fontSize: 13, fontWeight: "700", color: COLORS.ink },
});
