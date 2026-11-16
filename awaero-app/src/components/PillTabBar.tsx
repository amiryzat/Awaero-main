import Ionicons from "@expo/vector-icons/Ionicons";
import { BlurView } from "expo-blur";
import { GlassView, isGlassEffectAPIAvailable } from "expo-glass-effect";
import { Tabs } from "expo-router";
import type { ComponentProps, ReactNode } from "react";
import { Animated, Pressable, StyleSheet, View } from "react-native";
import { pillSize } from "@/lib/tabBarScroll";

type TabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>["tabBar"]>>[0];
type IconName = keyof typeof Ionicons.glyphMap;

const ICONS: Record<string, IconName> = {
  index: "home",
  live: "pulse",
  stats: "stats-chart",
  trials: "checkmark-done-circle",
  controls: "options",
};

// Real iOS 26 liquid glass when available; frosted blur (and web preview) otherwise.
const LIQUID = isGlassEffectAPIAvailable();

function Glass({ children }: { children: ReactNode }) {
  if (LIQUID) {
    return (
      <GlassView style={styles.pill} glassEffectStyle="regular" isInteractive>
        {children}
      </GlassView>
    );
  }
  return (
    <BlurView intensity={30} tint="light" style={[styles.pill, styles.blurBg]}>
      {children}
    </BlurView>
  );
}

export default function PillTabBar({ state, navigateToTab, insets }: TabBarProps) {
  const scale = pillSize.interpolate({ inputRange: [0, 1], outputRange: [0.86, 1] });
  const translateY = pillSize.interpolate({ inputRange: [0, 1], outputRange: [10, 0] });

  return (
    <View style={[styles.wrap, { bottom: insets.bottom + 10 }]} pointerEvents="box-none">
      <Animated.View style={[styles.shadow, { transform: [{ scale }, { translateY }] }]}>
        <Glass>
          {state.routes.map((route, i) => {
            const focused = state.index === i;
            const base = ICONS[route.name] ?? "ellipse";
            const name = (focused ? base : `${base}-outline`) as IconName;
            return (
              <Pressable
                key={route.key}
                onPress={() => {
                  if (!focused) navigateToTab(route.key);
                }}
                hitSlop={6}
                accessibilityRole="button"
                accessibilityLabel={route.name === "index" ? "home" : route.name}
                accessibilityState={{ selected: focused }}
              >
                <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
                  <Ionicons name={name} size={24} color={focused ? "#16a34a" : "#64748b"} />
                </View>
              </Pressable>
            );
          })}
        </Glass>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", left: 0, right: 0, alignItems: "center", paddingHorizontal: 20 },
  shadow: {
    width: "100%",
    maxWidth: 460,
    borderRadius: 34,
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 10,
  },
  pill: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderRadius: 34,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.5)",
  },
  blurBg: { backgroundColor: "rgba(255,255,255,0.5)" },
  iconWrap: {
    width: 52,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
  },
  iconWrapActive: { backgroundColor: "rgba(22,163,74,0.14)" },
});
