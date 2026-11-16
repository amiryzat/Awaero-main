import { StyleSheet, Text, View } from "react-native";
import type { SystemState } from "@/lib/state";

// PRD 6.3: persistent whenever the data is not live. Not optional.
export default function ReplayBanner({ state }: { state: SystemState | null }) {
  if (state?.source !== "replay") return null;
  return (
    <View style={styles.banner}>
      <Text style={styles.text}>Replay data. Not the live system.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: { backgroundColor: "#fef3c7", borderRadius: 12, paddingVertical: 8, paddingHorizontal: 12 },
  text: { color: "#92400e", fontSize: 13, fontWeight: "700", textAlign: "center" },
});
