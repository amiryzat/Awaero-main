import { useEffect, useRef, useState } from "react";

function reduceMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

// A segmented control whose active thumb's two edges move with a slight lag, so
// it stretches across the gap then settles (the "rubber band" feel). Shared by
// the Stats window selector and the mobile tab bar; no motion-library dependency.
export default function RubberSegment<T extends string>({
  options,
  value,
  onChange,
  label = (v) => v,
  thumb = "var(--card)",
  thumbShadow = "0 1px 3px rgba(0,0,0,0.14)",
  activeText = "var(--navy)",
  inactiveText = "var(--slate)",
  itemStyle,
  containerStyle,
  className,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  label?: (v: T) => string;
  thumb?: string;
  thumbShadow?: string;
  activeText?: string;
  inactiveText?: string;
  itemStyle?: React.CSSProperties;
  containerStyle?: React.CSSProperties;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const btns = useRef<(HTMLButtonElement | null)[]>([]);
  const activeIdx = Math.max(0, options.indexOf(value));
  const prev = useRef(activeIdx);
  const [geo, setGeo] = useState<{ left: number; right: number; top: number; height: number } | null>(null);
  const calm = reduceMotion();

  useEffect(() => {
    const measure = () => {
      const c = ref.current;
      const b = btns.current[activeIdx];
      if (!c || !b) return;
      setGeo({
        left: b.offsetLeft,
        right: c.clientWidth - (b.offsetLeft + b.offsetWidth),
        top: b.offsetTop,
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
  const dur = 380, lead = 95, ease = "cubic-bezier(.5,.05,.25,1)";
  const thumbStyle: React.CSSProperties = geo
    ? {
        position: "absolute",
        left: geo.left,
        right: geo.right,
        top: geo.top,
        height: geo.height,
        background: thumb,
        borderRadius: 999,
        boxShadow: thumbShadow,
        transition: calm
          ? "none"
          : `left ${dur}ms ${ease} ${dir > 0 ? lead : 0}ms, right ${dur}ms ${ease} ${dir < 0 ? lead : 0}ms`,
      }
    : { display: "none" };

  return (
    <div ref={ref} className={className} style={{ display: "inline-flex", ...containerStyle }}>
      <div style={thumbStyle} aria-hidden />
      {options.map((o, i) => (
        <button
          key={o}
          ref={(el) => {
            btns.current[i] = el;
          }}
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
