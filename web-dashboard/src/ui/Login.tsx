import { useState } from "react";
import { signIn } from "../lib/session";
import TechText from "./TechText";

// The cosmetic demo gate (PRD 7.0). Looks like a real sign-in, gates nothing of
// substance: any input signs in. See session.ts for why that is deliberate.
export default function Login({ onSignIn }: { onSignIn: () => void }) {
  const [email, setEmail] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    signIn();
    onSignIn();
  }

  return (
    <main
      style={{
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 24px",
        maxWidth: 440,
        margin: "0 auto",
      }}
    >
      {/* The logo: React Bits TechText. Hover a letter to reveal its dashed
          outline. The canvas has no text, so the wrapper carries the name. */}
      <div
        role="img"
        aria-label="Awaero"
        style={{
          // TechText insets its text by 5% of its own width; pull it left by that
          // so the wordmark lines up with the headline below.
          width: "calc(100% + 20px)", marginLeft: -20,
          height: 120, position: "relative", color: "var(--navy)", marginBottom: 12,
        }}
      >
        <TechText
          text="AWAERO"
          fontWeight={700}
          fontSize={96}
          letterSpacing={0.02}
          align="left"
          reveal="letter"
          reach={150}
          dashLength={4}
          dashGap={2}
          specks={15}
          accentColor="#7eb994"
          intro="none"
        />
      </div>
      <h1 style={{ fontSize: 34, lineHeight: 1.15, marginBottom: 14 }}>
        Feel comfort
        <br />
        and in control
      </h1>
      <p className="muted" style={{ fontSize: 16, lineHeight: 1.5, marginBottom: 28 }}>
        Vision-based smart power management, running entirely on your own device.
      </p>

      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={field}
          autoComplete="username"
        />
        <input type="password" placeholder="Password" style={field} autoComplete="current-password" />
        <button className="pill" type="submit" style={{ marginTop: 6 }}>
          Sign in
        </button>
      </form>

      <p className="muted" style={{ fontSize: 12, marginTop: 20 }}>
        Local demo access. No account is created or sent anywhere.
      </p>
    </main>
  );
}

const field: React.CSSProperties = {
  border: "1px solid #e3e7ec",
  borderRadius: 12,
  padding: "13px 16px",
  fontSize: 15,
  background: "#fff",
  color: "var(--navy)",
  outline: "none",
};
