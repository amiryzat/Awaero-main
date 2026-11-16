import { Tabs } from "expo-router";
import { View } from "react-native";
import CaptureBanner from "@/components/CaptureBanner";
import PillTabBar from "@/components/PillTabBar";

export default function TabLayout() {
  return (
    <View style={{ flex: 1 }}>
      <Tabs screenOptions={{ headerShown: false }} tabBar={(props) => <PillTabBar {...props} />}>
        <Tabs.Screen name="index" options={{ title: "Home" }} />
        <Tabs.Screen name="live" options={{ title: "Live" }} />
        <Tabs.Screen name="stats" options={{ title: "Stats" }} />
        <Tabs.Screen name="trials" options={{ title: "Trials" }} />
        <Tabs.Screen name="controls" options={{ title: "Controls" }} />
      </Tabs>
      {/* Above every tab, so a countdown armed on Trials survives a tab switch. */}
      <CaptureBanner />
    </View>
  );
}
