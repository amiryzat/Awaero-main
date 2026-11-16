import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

function reduceMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

type Geo = { left: number; right: number; top: number; bottom: number; width: number; height: number };

// A segmented control whose active thumb's two edges move with a slight lag, so
// it stretches across the gap then settles (the "rubber band" feel). Horizontal
// by default (Stats window selector, mobile tab bar); `vertical` stretches the
// top and bottom edges instead (web sidebar). No motion-library dependency.
export default function RubberSegment<T extends string>({
  options,
  value,
  onChange,
  label = (v) => v,
  vertical = false,
  thumb = "var(--card)",
  thumbShadow = "0 1px 3px rgba(0,0,0,0.14)",
  thumbRadius = 999,
  activeText = "var(--navy)",
  inactiveText = "var(--slate)",
  itemStyle,
  itemClassName,
  containerStyle,
  className,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  label?: (v: T) => ReactNode;
  vertical?: boolean;
  thumb?: string;
  thumbShadow?: string;
  thumbRadius?: number | string;
  activeText?: string;
  inactiveText?: string;
  itemStyle?: CSSProperties;
  itemClassName?: string;
  containerStyle?: CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const btns = useRef<(HTMLButtonElement | null)[]>([]);
  const activeIdx = Math.max(0, options.indexOf(value));
  const prev = useRef(activeIdx);
  const [geo, setGeo] = useState<Geo | null>(null);
  const calm = reduceMotion();

  // Layout effect: measure before first paint, so the active item's light text is
  // never shown on a light background for a frame before the thumb appears.
  useLayoutEffect(() => {
    const measure = () => {
      const c = ref.current;
      const b = btns.current[activeIdx];
      if (!c || !b) return;
      setGeo({
        left: b.offsetLeft,
        right: c.clientWidth - (b.offsetLeft + b.offsetWidth),
        top: b.offsetTop,
        bottom: c.clientHeight - (b.offsetTop + b.offsetHeight),
        width: b.offsetWidth,
        height: b.offsetHeight,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (ref.current) ro.observe(ref.current);
    return () => ro.disconnect();
  }, [activeIdx, options.length]);

  const dir = activeIdx - prev.current;
  useEffect(() => {
    prev.current = activeIdx;
  });

  // Trailing edge lags the leading edge, so the thumb stretches then squashes.
  // Moving forward (right or down) the first edge (left/top) trails; moving back,
  // the second edge (right/bottom) does.
  const dur = 380, lead = 95, ease = "cubic-bezier(.5,.05,.25,1)";
  const [a, b] = vertical ? ["top", "bottom"] : ["left", "right"];
  const thumbStyle: CSSProperties = geo
    ? {
        position: "absolute",
        ...(vertical
          ? { top: geo.top, bottom: geo.bottom, left: geo.left, width: geo.width }
          : { left: geo.left, right: geo.right, top: geo.top, height: geo.height }),
        background: thumb,
        borderRadius: thumbRadius,
        boxShadow: thumbShadow,
        transition: calm
          ? "none"
          : `${a} ${dur}ms ${ease} ${dir > 0 ? lead : 0}ms, ${b} ${dur}ms ${ease} ${dir < 0 ? lead : 0}ms`,
      }
    : { display: "none" };

  return (
    <div
      ref={ref}
      className={className}
      style={{ position: "relative", display: "inline-flex", flexDirection: vertical ? "column" : "row", ...containerStyle }}
    >
      <div style={thumbStyle} aria-hidden />
      {options.map((o, i) => (
        <button
          key={o}
          ref={(el) => {
            btns.current[i] = el;
          }}
          className={itemClassName}
          data-active={i === activeIdx}
          onClick={() => onChange(o)}
          style={{
            position: "relative",
            zIndex: 1,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontWeight: 600,
            fontFamily: "inherit",
            textTransform: "capitalize",
            borderRadius: 999,
            padding: "7px 16px",
            fontSize: 13,
            color: i === activeIdx ? activeText : inactiveText,
            transition: "color 220ms var(--ease-out)",
            ...itemStyle,
          }}
        >
          {label(o)}
        </button>
      ))}
    </div>
  );
}
