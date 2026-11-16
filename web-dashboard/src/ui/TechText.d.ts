import type { CSSProperties, ReactElement } from "react";

// Types for the React Bits TechText (src/ui/TechText.jsx, copied unmodified from
// reactbits.dev, JS-CSS variant). The component is plain JS, so this declaration
// is what lets strict TypeScript import it.
export interface TechTextProps {
  text?: string;
  fontFamily?: string;
  fontWeight?: number;
  fontSize?: number;
  letterSpacing?: number;
  color?: string;
  accentColor?: string;
  align?: "left" | "center" | "right";
  reach?: number;
  softness?: number;
  dashLength?: number;
  dashGap?: number;
  strokeWidth?: number;
  lineStyle?: "dashed" | "solid";
  reveal?: string;
  specks?: number;
  selection?: boolean;
  labels?: boolean;
  draggable?: boolean;
  bounce?: number;
  sweep?: boolean;
  speed?: number;
  clickKick?: boolean;
  intro?: "none" | "type" | "metrics" | "assemble";
  introDuration?: number;
  guides?: boolean;
  className?: string;
  style?: CSSProperties;
}

declare const TechText: (props: TechTextProps) => ReactElement;
export default TechText;
