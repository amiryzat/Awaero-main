import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { COLORS } from "@/lib/theme";
import { checkWifiPath, reconnect, setHost, useSystem } from "@/lib/useSystem";

type Wifi = { ip: string | null; ok: boolean } | "checking" | null;

export default function Settings() {
  const { host, typed, status, state, candidates } = useSystem();
  const [draft, setDraft] = useState(typed);
  const [wifi, setWifi] = useState<Wifi>(null);

  const run = useCallback(() => checkWifiPath().then(setWifi), []);
  const check = useCallback(() => {
    setWifi("checking");
    void run();
  }, [run]);

  // Answer the cable question on open, not in the middle of a demo.
  useEffect(() => {
    if (status === "ok") void run();
  }, [status, run]);

  const line =
    status === "ok"
      ? `Connected to ${host}. Data source: ${state?.source === "replay" ? "replay fixture" : "live log"}.`
      : status === "unreachable"
        ? "Cannot reach the Mac. Check that this phone is on the same WiFi, that iPhone Settings, Privacy and Security, Local Network has app-monitor switched on, and that state_server.py is running."
        : "Looking for the Mac...";

  return (
    // "automatic" keeps the content below the modal header, which floats on iOS 26.
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <Text style={[styles.status, status === "ok" && { color: "#15803d" }]}>{line}</Text>

      <Text style={styles.label}>Wireless check</Text>
      <View style={styles.card}>
        {wifi === "checking" ? (
          <Text style={styles.cardText}>Checking...</Text>
        ) : wifi === null ? (
          <Text style={styles.cardText}>Connect first, then this tells you if the cable is needed.</Text>
        ) : wifi.ok ? (
          <Text style={[styles.cardText, { color: "#15803d", fontWeight: "700" }]}>
            Reachable at {wifi.ip} over WiFi. The USB cable is not needed.
          </Text>
        ) : (
          <Text style={[styles.cardText, { color: "#b45309", fontWeight: "700" }]}>
            {wifi.ip
              ? `Not reachable at the Mac's WiFi address ${wifi.ip}. This phone is not on the same WiFi as the Mac, so the app is running over the USB cable and will stop when it is unplugged.`
              : "The Mac's WiFi address is not known yet. Connect once, then check again."}
          </Text>
        )}
        <Pressable style={({ pressed }) => [styles.minor, pressed && { opacity: 0.6 }]} onPress={check}>
          <Text style={styles.minorText}>Check again</Text>
        </Pressable>
      </View>

      <Text style={styles.label}>Addresses the app will try</Text>
      <View style={styles.card}>
        {candidates.map((c) => (
          <Text key={c} style={[styles.cardText, c === host && { color: "#15803d", fontWeight: "700" }]}>
            {c}
            {c === host ? "  (in use)" : ""}
          </Text>
        ))}
        <Pressable style={({ pressed }) => [styles.minor, pressed && { opacity: 0.6 }]} onPress={reconnect}>
          <Text style={styles.minorText}>Search again</Text>
        </Pressable>
      </View>

      <Text style={styles.label}>Mac address (optional)</Text>
      <TextInput
        style={styles.input}
        value={draft}
        onChangeText={setDraft}
        placeholder="leave empty to find it automatically"
        placeholderTextColor={COLORS.subtle}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="numbers-and-punctuation"
        returnKeyType="done"
        onSubmitEditing={() => setHost(draft)}
      />
      <Pressable style={({ pressed }) => [styles.save, pressed && { opacity: 0.7 }]} onPress={() => setHost(draft)}>
        <Text style={styles.saveText}>Save</Text>
      </Pressable>

      <Text style={styles.help}>
        The app finds the Mac by itself: it remembers the WiFi address and the Bonjour name that
        state_server.py reports, and tries them all on every reconnect. Only type an address if
        that fails. On the Mac, run python state_server.py.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  content: { padding: 16, gap: 12, paddingBottom: 40 },
  label: { fontSize: 13, fontWeight: "700", color: COLORS.muted, marginLeft: 4, marginTop: 6 },
  card: { backgroundColor: COLORS.card, borderRadius: 14, padding: 16, gap: 8 },
  cardText: { fontSize: 15, color: COLORS.ink, lineHeight: 21 },
  input: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 18,
    color: COLORS.ink,
  },
  save: { backgroundColor: COLORS.ink, borderRadius: 14, paddingVertical: 14, alignItems: "center" },
  saveText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  minor: { alignSelf: "flex-start", paddingVertical: 4 },
  minorText: { fontSize: 15, fontWeight: "700", color: "#1d4ed8" },
  status: { fontSize: 14, fontWeight: "600", color: "#b45309", marginLeft: 4, lineHeight: 20 },
  help: { fontSize: 13, color: COLORS.subtle, marginLeft: 4, lineHeight: 19 },
});
