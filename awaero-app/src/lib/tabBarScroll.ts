import { Animated } from "react-native";

// Shared between the screens and the floating pill. 1 = resting (full size),
// 0 = actively scrolling (shrunk). Screens spread `shrinkOnScroll` onto their
// ScrollView; the pill reads `pillSize` to animate.
export const pillSize = new Animated.Value(1);

const to = (v: number) =>
  Animated.timing(pillSize, { toValue: v, duration: 160, useNativeDriver: true }).start();

let idle: ReturnType<typeof setTimeout>;

// Shrink on any scroll, restore ~220ms after scrolling stops (static state).
export const shrinkOnScroll = {
  scrollEventThrottle: 32,
  onScroll: () => {
    to(0);
    clearTimeout(idle);
    idle = setTimeout(() => to(1), 220);
  },
};
