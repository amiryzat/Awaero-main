import { useEffect, useRef, useState } from "react";

// Shared number scramble: on mount it flickers random values for LOAD_MS, then
// lands on the real number. After it settles, live refreshes update it without
// re-scrambling. Used by the Stats headlines and the Trials accuracy figure.
// Respects reduced motion (shows the value immediately).
const LOAD_MS = 950;

function reduceMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export default function AnimatedNumber({
  value,
  suffix = "",
  decimals = 1,
}: {
  value: number;
  suffix?: string;
  decimals?: number;
}) {
  const [display, setDisplay] = useState<number>(() => (reduceMotion() ? value : Math.random() * 100));
  const settled = useRef(reduceMotion());
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (reduceMotion()) {
      setDisplay(valueRef.current);
      return;
    }
    const start = performance.now();
    const id = setInterval(() => {
      if (performance.now() - start >= LOAD_MS) {
        clearInterval(id);
        settled.current = true;
        setDisplay(valueRef.current); // the exact, correct number
      } else {
        setDisplay(Math.random() * 100);
      }
    }, 55);
    return () => clearInterval(id);
  }, []); // mount only: the scramble plays once per tab open

  useEffect(() => {
    if (settled.current) setDisplay(value); // live refreshes after settle, no re-scramble
  }, [value]);

  return (
    <>
      {display.toFixed(decimals)}
      {suffix}
    </>
  );
}
