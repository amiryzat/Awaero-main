import Ionicons from "@expo/vector-icons/Ionicons";
import { ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import ReplayBanner from "@/components/ReplayBanner";
import { APPLIANCE_KEYS, type Appliances } from "@/lib/state";
import { shrinkOnScroll } from "@/lib/tabBarScroll";
import { CARD_SHADOW, COLORS } from "@/lib/theme";
import { useSystem } from "@/lib/useSystem";

const ROWS: Record<keyof Appliances, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  light: { label: "Light", icon: "bulb-outline" },
  fan: { label: "Fan", icon: "aperture-outline" },
  tv: { label: "TV", icon: "tv-outline" },
  lamp: { label: "Desk lamp", icon: "flashlight-outline" },
  ac: { label: "AC", icon: "snow-outline" },
};

// ponytail: read-only until Phase 7 wires POST /override. The switches mirror
// the current decision and stay disabled; a toggle that does nothing is a lie.
export default function Controls() {
  const insets = useSafeAreaInsets();
  const { state, current: cur } = useSystem();

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 16 }]}
      {...shrinkOnScroll}
    >
      <Text style={styles.title}>Controls</Text>
      <ReplayBanner state={state} />
      <Text style={styles.subtitle}>
        Manual override is not connected yet. These show what the system has set.
      </Text>

      <View style={styles.card}>
        {APPLIANCE_KEYS.map((k, i) => (
          <View key={k} style={[styles.toggleRow, i > 0 && styles.divider]}>
            <Ionicons name={ROWS[k].icon} size={22} color={COLORS.muted} />
            <Text style={styles.toggleLabel}>{ROWS[k].label}</Text>
            <Switch value={cur?.appliances[k] ?? false} disabled trackColor={{ true: "#86efac" }} />
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 16, paddingBottom: 110, gap: 14, width: "100%", maxWidth: 520, alignSelf: "center" },
  title: { fontSize: 28, fontWeight: "800", color: COLORS.ink },
  subtitle: { fontSize: 15, color: COLORS.muted },

  card: { backgroundColor: COLORS.card, borderRadius: 18, paddingHorizontal: 18, ...CARD_SHADOW },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 16 },
  divider: { borderTopWidth: 1, borderTopColor: COLORS.hairline },
  toggleLabel: { flex: 1, fontSize: 17, fontWeight: "600", color: COLORS.ink },
});
