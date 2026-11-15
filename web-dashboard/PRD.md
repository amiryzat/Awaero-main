# PRD - web-dashboard: the local smart-home web app and demo fallback

Single source of truth for building `web-dashboard/`. Written 2026-11-15 against
the real code in `~/fyp-prototype/`. This folder has its own Claude Code session.

**Precedence.** This document does not outrank the running Python. If this
document and `live_system.py` or `state_server.py` disagree, the code wins and
this document gets corrected. The three project objectives outrank everything,
including this document. `../app-monitor/PRD.md` is the sibling spec for the
native phone app and remains the authority on the shared data contracts.

---

## 0. MASTER PROMPT (paste this first in the web-dashboard session)

> You are building `web-dashboard`, a React + Vite web app in
> `~/fyp-prototype/web-dashboard`. It serves a final year project: a
> context-aware vision-based smart power management system running on a Mac,
> driving an Arduino over USB serial.
>
> It is two things at once: a **polished smart-home web app**, and the
> **can't-fail demo fallback** for the viva. The native phone app
> (`../app-monitor`) depends on the phone reaching the Mac over a network. On a
> borrowed or hostile WiFi that fails. This dashboard runs in the **Mac's own
> browser** with zero networking involved, so the demo always has a face.
>
> Read `PRD.md` fully before writing code. Then `../docs/RESUME.md` for current
> project state and `../docs/CONTEXT.md` for how the owner works.
>
> Hard rules:
> 1. **Every feature must trace to a project objective.** Section 1 lists the
>    three. If a feature maps to none of them, do not build it, and say so.
> 2. **Never invent a number.** Every figure on screen traces to a row in a data
>    file served by `state_server.py`. If a metric is not computable, render
>    "not yet measured", never a zero or a guess. Section 5 is the authority.
>    Fabricated evidence in a graded project is unrecoverable at viva.
> 3. **Only ONE file outside this folder may be edited**, and only once:
>    the static-serving route in `../state_server.py` (Section 6.2). Never touch
>    `live_system.py`, `moondream_vlm.py`, `serial_actuator.py`, `camera.py`, or
>    anything in `../app-monitor/`.
> 4. **No cloud. Ever.** No hosting, no CDN for runtime data, no analytics, no
>    external API calls at runtime. RO2's claim is that everything is local, and
>    the thesis problem statement argues against cloud cameras. Violating that
>    hands an examiner a weapon. npm packages at build time are fine.
> 5. **No em dashes** anywhere: UI copy, code comments, chat replies.
> 6. **The Python server serves the BUILT output**, never the Vite dev server.
>    `npm run dev` is for development only. See Section 6.1, the build rule.
> 7. Run `npm run build` and `npx tsc --noEmit` before calling any task done.
>
> Work the phases in Section 8, one at a time. Stop at each boundary and report.
> Give the owner one clear next step, never a long walkthrough.

---

## 1. The three objectives, and how this dashboard satisfies them

Verbatim from the thesis, section 1.3:

> **RO1.** To design a context-aware decision logic layer that maps detected
> activities to power control actions via IoT.
>
> **RO2.** To develop an occupant activity detection module using computer
> vision deployed on a single edge device.
>
> **RO3.** To evaluate the accuracy of activity detection, the response latency,
> and the energy saving performance of the proposed system.

### Coverage matrix

| RO | What the dashboard contributes | Where | Done when |
|---|---|---|---|
| **RO1** | Makes the decision layer visible: detected activity to profile to appliance vector, rendered live | Home, Live | Every stage renders from real rows, and the appliance tiles match `FUSED_APP` |
| **RO2** | Exposes the detection module's internals and proves the edge claim | Live | People count, pose label, VLM label, fusion outcome, presence gate, and a local-only statement all render from real rows |
| **RO3** | Presents accuracy, response latency, and Simulated Appliance Activation Reduction with their sample sizes | Stats | All three render with n, provenance, and honest "not yet measured" where data is absent |

**This dashboard does not collect new evidence.** It presents what
`state_server.py` computes. The Trials instrument that will close the RO3
accuracy gap lives in `../app-monitor` (its PRD Phase 5). If Trials data later
appears in `/metrics`, this dashboard renders it. Do not duplicate Trials here.

---

## 2. The system being monitored (ground truth)

Entry point `../live_system.py`. Five layers, one loop, two modes. The
authoritative description is `../app-monitor/PRD.md` Section 2 and
`../docs/CONTEXT.md`. The short version this dashboard needs:

**Fusion, settled by evidence:** pose = PRESENCE only. The VLM = POSTURE
(T/A/B). While no VLM answer exists the profile is HELD, never guessed. The VLM
also confirms presence within 10 s, which overrides pose's phantom people on
furniture.

**The four passive profiles and their appliance vectors** (`FUSED_APP` in
`live_system.py` is authoritative):

| Profile | Meaning | light | fan | tv |
|---|---|---|---|---|
| `T` | transitional (standing/walking) | 1 | 0 | 0 |
| `A` | active (sitting) | 1 | 1 | 1 |
| `B` | resting (lying) | 0 | 1 | 0 |
| `C` | unoccupied | 0 | 0 | 0 |

**ACTIVE, gestures.** Open palm toggles TV, peace toggles lights, fist is
all-off. Active mode **never sets the fan**. Do not render a fan state in active
mode.

**Known scope limit to respect in the UI:** the system is single-room,
single-occupant. With several people in frame it reads whoever is sitting. Do
not present a people count above 1 as if the profile describes all of them.

---

## 3. Architecture

```
  camera -> live_system.py (pose + VLM fusion) -> serial -> Arduino
                   |
            writes | live_log.csv + live_frame.jpg
                   v
            state_server.py  (port 8000)
             |            |
     JSON API |            | serves web-dashboard/dist/ at /
             v            v
        same-origin fetch from the browser
        (Mac's own browser, or the phone over the LAN/cable)
```

Three rules that keep this safe:

1. **The dashboard is read-only in v1.** It never writes `live_log.csv`, never
   opens the serial port, never commands appliances. Controls come later and
   only through the decision layer (`override.json`), never direct to serial.
2. **Same origin.** Because the Python server serves the built files, the API
   is at the same host and port. No CORS, no mixed content, no configured IP.
   This is the main reason Section 6.1 chooses served-build over dev-server.
3. **Everything is local.** No cloud, no account, no telemetry. That is RO2's
   edge claim and the thesis problem statement names cloud cameras as the thing
   being avoided.

---

## 4. Data contracts

The server already publishes everything. Do not invent new endpoints in v1.
Mirror these types in `src/lib/types.ts` exactly. They are the same shapes
`../app-monitor/PRD.md` Section 4.6 defines; change both sides together.

```ts
type Profile = "T" | "A" | "B" | "C";
type Mode = "PASSIVE" | "ACTIVE" | "MANUAL";
type Appliances = { light: boolean; fan: boolean; tv: boolean };

type Decision = {
  at: string;                  // ISO 8601
  date_inferred: boolean;      // the log has no date column, see 4.2
  mode: Mode;
  profile: string;             // Profile | gesture name | "OVERRIDE"
  people: number | null;
  pose: string | null;
  vlm: string | null;
  phone: string | null;        // metadata only, never affects control
  vlm_latency_s: number | null;
  decide_latency_ms: number | null;
  actuate_latency_ms: number | null;
  appliances: Appliances;
};

// GET /health
type Health = { ok: boolean; source: "live" | "replay"; rows: number;
                log_path: string; lan_ip: string; local_name: string | null };

// GET /state
type SystemState = {
  online: boolean;             // false when the log is missing or stale
  stale_seconds: number;
  source: "live" | "replay";   // replay MUST be visible in the UI
  current: Decision | null;
  gate_active: boolean;        // pose and VLM disagreed and pose won
  override: { active: boolean; expires_in_s: number } | null;
};

// GET /history?limit=200   -> Decision[], newest first
// GET /metrics?window=session|today|all
type Stat = { n: number; mean: number; p50: number; p95: number };
type Metrics = {
  window: { from: string; to: string; seconds: number };
  activation: {                // Simulated Appliance Activation Reduction
    reduction_pct: number;
    per_appliance: Record<keyof Appliances,
      { on_seconds: number; baseline_seconds: number; reduction_pct: number }>;
  } | null;                    // null when the window holds a single row
  latency: {
    decide_ms: Record<"PASSIVE" | "ACTIVE", Stat | null>;
    actuate_ms: Stat | null;
    vlm_s: Stat | null;
  };
  profile_distribution: Record<Profile, { seconds: number; pct: number }>;
  timeline: { at: string; seconds: number; mode: Mode; profile: string;
              appliances: Appliances }[];   // oldest first
  accuracy: {
    live: { n: number; correct: number; pct: number;
            per_profile: Record<Profile, { n: number; correct: number; pct: number } | null> } | null;
    offline: { n: number; correct: number; pct: number; captured_at: string } | null;
  };
};

// GET /frame.jpg -> the annotated camera frame, 404 unless under 5 s old
```

### 4.1 Defects to handle, not paper over

1. **`date_inferred` is true.** The log has no date column; the server infers it
   from file mtime. Never claim precision the data lacks. Show relative time
   ("updated 4s ago") rather than absolute timestamps where possible.
2. **Change-triggered, not sampled.** Gaps are dwell time, not missing data.
3. **A quiet log does not mean a dead system.** `online` already accounts for
   the camera frame as a heartbeat. Trust `online`, do not re-derive it.
4. **`/frame.jpg` 404s when no fresh frame exists.** That is the correct
   "camera offline" state, not an error to retry aggressively.

---

## 5. What is and is not computable

Build Stats from this table, not from optimism.

### Computable now
- **Simulated Appliance Activation Reduction** from `metrics.activation`. Report
  per appliance and as a mean. Always state the window length. Label it as
  simulated over LED proxies. Never a watt claim.
- **Response latency** from `metrics.latency.decide_ms` (per mode) and
  `actuate_ms`. This is machine time, label it as such.
- **VLM latency** from `metrics.latency.vlm_s`.
- **Profile distribution** from `metrics.profile_distribution` (dwell time).
- **Offline accuracy** from `metrics.accuracy.offline` (n=12 as of writing).
  Always print n beside the percentage.

### Not computable, render "not yet measured"
- **Live accuracy.** `metrics.accuracy.live` is null until the app-monitor
  Trials instrument writes `trials.csv`. Render the absence honestly. Never 0%.
- **End-to-end camera-to-LED latency.** `decide_ms` is machine time only.
- **Watts, kWh, cost, carbon.** Three LEDs. Any such figure would be invented.

### Caveats the UI must carry
- Every stat card shows its **source and sample size**. A number without
  provenance does not ship.
- When `source` is `"replay"`, a persistent banner says so. Not optional. A demo
  that looks live but is not would be dishonest in front of an examiner.

---

## 6. Build and serving

### 6.1 The build rule (read twice)

The Python server serves the **built output**, `web-dashboard/dist/`. The Vite
dev server is for development only and must never be part of a demo.

```bash
npm run dev     # development only: localhost:5173, proxies /api calls to :8000
npm run build   # produces dist/ ; the Python server serves this
```

**The failure mode this creates:** you change code, forget `npm run build`, and
the demo shows a stale dashboard. Mitigations, all required:

1. `npm run build` is part of "done" for every phase.
2. The footer renders a **build stamp** (date + short git SHA, injected by Vite
   `define` at build time). If the stamp is old, the build is stale. This is the
   single cheapest insurance against the stale-build trap.
3. The server returns `Cache-Control: no-store` for `index.html` so a reload
   always picks up a new build.

Vite config requirements:
- `base: "./"` so asset paths are relative and work when served from Python.
- `build.outDir: "dist"`.
- dev `server.proxy` maps the API paths to `http://localhost:8000` so `fetch`
  code is identical in dev and production (always same-origin relative paths).

### 6.2 The ONE allowed edit outside this folder

In `../state_server.py`, `Handler.do_GET`, add a static-file branch. The API
routes keep priority; anything else falls through to the dashboard.

Requirements:
- API paths (`/health`, `/state`, `/history`, `/metrics`, `/frame.jpg`) are
  matched FIRST and are unchanged.
- Otherwise serve from `web-dashboard/dist/`. `/` serves `index.html`.
- **Path traversal guard.** Resolve the requested path and confirm it stays
  inside `dist/`. Reject anything that escapes. This is a trust boundary and is
  not optional, even on a LAN.
- Correct MIME types via the stdlib `mimetypes` module (js, css, svg, woff2,
  png). A wrong type silently breaks module loading.
- SPA fallback: a path that is not a real file serves `index.html`.
- Missing `dist/` is a normal state before the first build: return a plain
  readable message saying to run `npm run build`, not a stack trace.
- `python ../state_server.py --selftest` must still pass, and the existing
  JSON endpoints must be byte-identical in behaviour.

### 6.3 Developing without hardware

`state_server.py --replay ../fixtures/replay_log.csv` serves a fixture with the
real schema. Build and verify every screen against it. The replay banner must
appear. The camera feed correctly shows "offline" on replay.

---

## 7. Screens

Three routes in v1. Phone-width first (the Mac browser window can be narrow,
and the phone may use this over the cable), scaling up cleanly to a laptop
screen for the viva.

### 7.-1 Visual language (LOCKED, follow the reference)

The design is `design/reference-smarthome.png`. Match it closely. It is a clean
light smart-home app, and it maps onto this system almost one to one, which is
exactly why it was chosen. Study the image before writing any component.

**Design tokens** (approximate from the reference; refine against the image,
define once as CSS variables, never hard-code per component):
- Primary green `#4F9E70` (buttons, selected cards, on-toggles, active tab).
  A lighter tint `#E8F3EC` for soft green fills.
- Heading navy `#1E3A5F` (all headings and strong numbers).
- Body text muted slate `#8A94A6`; subtle `#AEB6C2`.
- App background `#F3F5F7`; cards pure white `#FFFFFF`.
- Card radius ~18px, soft shadow (low opacity, ~8px blur, small y offset).
- Pill buttons, fully rounded. Bold navy headings, generous whitespace.

**Keep the FYP profile accents for the four state cards**, so T/A/B/C stay
distinguishable (the reference's four state cards are a single green, but ours
carry meaning): A green `#15803D`, T blue `#3B82F6`, B amber `#F59E0B`,
C slate `#94A3B8`. The CURRENT profile's card is filled with its accent and
white text, like the reference's selected "I'm Home" card; the others are white
with the accent as a dot or label. Everything else (chrome, buttons, toggles,
nav) is the primary green above.

**The mapping from the reference to our real data** (this is the whole point,
build these, do not copy the reference's fake content):

| Reference element | Our real, honest version |
|---|---|
| "Welcome, Christina!" hero + "Get started" | The **login** screen (7.0): same calm hero feel, then Sign in. Header greeting can read "Welcome" + the product name. |
| "Current state" cards: I'm Home / Leaving / Sleeping / Vacation, each "X% activity" | The **four detected profiles**: Active (A) / Transitional (T) / Resting (B) / Unoccupied (C). The current one is highlighted. The "% activity" slot shows that profile's **dwell share** from `metrics.profile_distribution[p].pct`, a real number. Never invent it; if the window is empty show a dash. |
| "Rooms" cards with room photos | One room. Use the **live camera frame** (`/frame.jpg`) as the room card image, with "Camera offline" when no fresh frame. This doubles as the Live view's feed. |
| Device cards with toggles: Lights / Wifi / Air / Fans | The **appliances**: Light, Fan, TV, each a card showing on/off from `current.appliances`. In v1 the toggles are **read-only / reflect state** (a tap does nothing, or shows "automatic" copy), because Controls is v2. A toggle that lies is forbidden (rule 2). The fan shows "auto" in ACTIVE mode. |
| Bottom tab bar: Main / grid / calendar / profile | Our three routes: **Home / Live / Stats**, plus a profile/sign-out item. Green active tab, same floating style. |

Do not render fake rooms, fake devices, temperatures, a robot vacuum, or any
reference content that has no backing data. The look is copied; the content is
always real.

### 7.0 Login (cosmetic demo gate)

A real-looking sign-in screen that gates the UI. **It is a demo gate, not
security**, and a `ponytail:` comment in the code must say so. No server-side
auth, no stored credentials, no hashing theatre. A local flag in
`localStorage` remembers the session; a visible Sign out clears it. Wrap every
storage read and write in try/catch so a private window cannot break the app.

Rationale: it gives the "real product" feel the owner wants with zero security
surface and zero backend work. It traces to no RO, so it stays this thin.

### 7.1 Home - the smart-home face

- Current profile: large letter, label, accent colour, "updated Xs ago".
- Mode chip (PASSIVE / ACTIVE / MANUAL).
- Three appliance tiles: light, fan, tv, on/off. In ACTIVE mode the fan shows
  as unknown, because active mode never sets it.
- Last five decisions.
- When `online` is false: dim the card and say "System not running". Never
  present a stale profile as current.
- When an override is active, show the remaining hold time.

### 7.2 Live - the pipeline, for RO2

The screen that explains the system to an examiner. Legibility over polish.

- **Camera feed** from `/frame.jpg`, polled about twice a second with a
  cache-busting query. Real or absent, never faked. When no fresh frame exists,
  including on replay, show "Camera feed offline".
- Pipeline strip: `people -> pose -> VLM -> fused profile -> appliances`, each
  stage showing its current value from the latest decision.
- When `gate_active`, mark the VLM value overridden and label it "presence gate:
  pose authoritative". This is the headline reliability claim, made visible.
- Phone flag tagged "metadata only, does not affect control".
- Edge statement: "All inference local on this Mac. No cloud. Video stays on
  this machine." This is RO2's deployment claim.
- VLM latency of the last call.
- If `people > 1`, show a quiet note that the system is scoped to one occupant.

### 7.3 Stats - the RO3 report

Ordered to mirror RO3's own clauses. Window selector: session / today / all.

1. **Accuracy.** Live trial accuracy with n when it exists, otherwise "not yet
   measured" with a line explaining that the Trials instrument in the phone app
   produces it. Offline figure beneath as comparison, labelled with its date
   and n.
2. **Response latency.** Per mode, from `decide_ms`, plus `actuate_ms`, labelled
   as machine time, with the note that end-to-end camera-to-LED timing is
   measured separately.
3. **Simulated Appliance Activation Reduction.** Headline percentage, per
   appliance breakdown bars, window length, simulated-proxy label.
4. **Profile distribution.** Hand-built bars, dwell time, with seconds and
   percentage.

Charts: hand-built with CSS and SVG. **Do not add a charting library.** The
shapes needed are horizontal bars and a simple timeline strip.

### 7.4 Global

- Persistent **replay banner** whenever `source` is `"replay"`.
- A connection state line: connecting, live, or cannot reach the server, with
  the stale seconds when stale.
- Build stamp in the footer (Section 6.1).
- Polling: `/state` and `/history` every 2 s, `/metrics` every 10 s,
  `/frame.jpg` about every 500 ms on the Live screen only. Pause polling when
  the tab is hidden (`document.visibilitychange`).

---

## 8. Phases

Stop and report at each boundary. Run `npm run build` and `npx tsc --noEmit`
before declaring any phase done.

| # | Phase | Done when |
|---|---|---|
| 1 | **Scaffold + serving.** Vite + React + TS app, `base: "./"`, dev proxy, build stamp. The one allowed edit to `state_server.py` (6.2) with the traversal guard. | `npm run build` then loading `http://localhost:8000/` shows the app; `--selftest` still passes; a traversal attempt is rejected |
| 2 | **Data layer + login.** `types.ts` mirroring Section 4, a single polling hook, connection and replay state, the cosmetic login gate. | All three states (live, replay, server down) render correctly against the fixture |
| 3 | **Home.** Profile hero, mode chip, appliance tiles, recent decisions, offline handling. | Every value traceable by hand to a fixture row |
| 4 | **Live.** Camera feed, pipeline strip, presence-gate marking, edge statement. | Gate case renders correctly on the fixture row where pose and VLM disagree |
| 5 | **Stats.** The four cards, window selector, honest "not yet measured". | Every number traceable by hand to fixture rows, each with n and source |
| 6 | **Demo-proofing.** Keyboard-free full-screen layout for the viva, dark-mode check, slow/stale behaviour, a final pass for invented numbers and em dashes. | A cold run: build, start server, open browser, everything correct with no console errors |

Phases 1 to 5 need no hardware. Verify everything against the replay fixture.

---

## 9. Terminology

| Use | Never use |
|---|---|
| Simulated Appliance Activation Reduction | energy saving, energy saved, power saved, Simulated Energy Reduction, kWh, cost, carbon |
| Profile T / A / B / C | the green/yellow/red traffic light (dead model) |
| Appliances: light, fan, tv | LEDs as colours |
| Presence gate | hallucination filter |
| Trial accuracy (n=N) | accuracy, unqualified |
| Machine latency / end-to-end latency | latency, unqualified |

---

## 10. Open questions for the owner

1. **Product name.** The login screen and header need one. Not "app-monitor".
2. ~~Visual direction~~ **RESOLVED.** Follow `design/reference-smarthome.png`,
   specified in Section 7.-1: light theme, primary green, navy headings, white
   rounded cards, with the four FYP profile accents kept for the state cards.
3. **Does this replace the phone app in the viva, or sit beside it?** Changes
   how hard Phase 6 pushes on full-screen presentation.
4. **Controls and Trials in v2?** Controls needs the `override.json` path wired
   into `live_system.py` first (app-monitor PRD 4.3a), which is a change to the
   FYP Python and currently out of scope here.
