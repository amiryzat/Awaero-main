# PRD — app-monitor: FYP instrument + smart home app

Single source of truth for building this app. Written 2026-11-13 against the
real code in `~/fyp-prototype/`. Supersedes the earlier read-only draft:
Dr. Zaaba has approved the app, so bidirectional control and the evaluation
instrument are both in scope.

**Precedence.** This document outranks last semester's thesis writing, which is
being revised this semester. It does not outrank the running Python: if this
document and `live_system.py` disagree, the Python wins and this document gets
corrected. The three project objectives outrank everything, including this
document.

---

## 0. MASTER PROMPT (paste this first)

> You are building `app-monitor`, an Expo/React Native iOS app in
> `~/fyp-prototype/app-monitor`. It serves a final year project: a context-aware
> vision-based smart power management system running on a Mac, driving an
> Arduino over USB serial.
>
> The app is three things: a **smart home interface** for the room, a **window
> into the decision pipeline**, and an **evaluation instrument** that collects
> the accuracy and latency data the project is graded on.
>
> Read `PRD.md` fully before writing code. Then `AGENTS.md` for Expo rules and
> `CONTEXT.md` for how the owner works.
>
> Hard rules:
> 1. **Every feature must trace to a project objective.** Section 1 lists the
>    three. If a feature you are about to build maps to none of them, do not
>    build it, and say so.
> 2. **Never invent a number.** Every figure on screen traces to a row in a data
>    file. If a metric cannot be computed from available data, render "not yet
>    measured", never a zero or a guess. Section 5 is the authority on what is
>    computable. This rule is not a style preference; fabricated evidence in a
>    graded project is unrecoverable at viva.
> 3. **Edits to the FYP Python are surgical and listed.** Section 4.3 names the
>    exact additions allowed to `live_system.py`. Nothing else outside
>    `app-monitor/` may be touched, and every allowed edit is additive and
>    reversible.
> 4. **No em dashes** anywhere: UI copy, code comments, chat replies.
> 5. The hardware is not connected right now. Everything is built and verified
>    against the replay fixture (Section 6.3) using the real schema, so that
>    connecting hardware later changes a flag and nothing else.
> 6. Run `npx tsc --noEmit` and `npx expo lint` before calling any task done.
>
> Work the phases in Section 8, one at a time. Stop at each boundary and report.
> Give the owner one clear next step, never a long walkthrough.

---

## 1. The three objectives, and how the app satisfies them

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

| RO | What the app contributes | Where | Done when |
|---|---|---|---|
| **RO1** | Makes the decision layer visible and demonstrates it arbitrating between automatic and manual IoT inputs | Live tab, Controls tab, override path | Pipeline strip renders every stage from real data, and a phone command reaches the Arduino through the decision layer with automatic resume |
| **RO2** | Exposes the detection module's internals and proves the edge claim | Live tab, edge indicator | People count, pose label, VLM label, fusion outcome, and presence gate all render from real rows, with local-only inference stated on screen |
| **RO3** | Collects ground-truthed accuracy and response latency, then reports all three required measures | Trials tab, Stats tab | 70 or more labelled trials recorded, and Stats shows accuracy, per-mode response latency, and Simulated Appliance Activation Reduction, each with its sample size |

**RO3 is the one with a real gap.** `docs/CHECKLIST.md` still has "scale dataset
to >=10 trials/response (>=70 data points)" unticked, and `live_log.csv` carries
no ground truth, so accuracy cannot be computed from it. The Trials tab
(Section 7.4) exists to close that gap. It is the highest-value feature in this
document and should not be cut for time.

### On "energy saving performance"

RO3's written wording says "energy saving performance". `docs/CONTEXT.md`
records that term, along with "Simulated Energy Reduction", as rejected, with
**"Simulated Appliance Activation Reduction"** mandated instead.

That is not a contradiction, it is a correction. The hardware is three LEDs, so
a watt or kWh claim would be unsupportable. The honest measurable form of RO3's
third clause is the proportion of appliance-on time avoided versus an always-on
baseline. Use the mandated term in all UI copy, identifiers and comments. The
thesis wording gets aligned to it when Chapter 4 is written.

Banned everywhere: "energy saving", "energy saved", "power saved", "Simulated
Energy Reduction", kWh, cost, carbon.

---

## 2. The system being monitored (ground truth)

Entry point `~/fyp-prototype/live_system.py`. Five layers, one loop, two modes.

**Layer 2, mode router.** MediaPipe Hands every frame. Hand visible, go
`ACTIVE`. No hand for `PASSIVE_FALLBACK_SECONDS = 2.0`, go `PASSIVE`. Inside the
grace window the mode is held, which stops flicker.

**PASSIVE, Layer 4 fusion.** Pose (MediaPipe) is real-time and authoritative.
The VLM (`qwen3-vl:8b`, roughly 15 s per frame) runs on a background thread and
only refines an upright person.

```
pose sees nobody   -> C                   (presence gate, blocks VLM hallucination)
pose sees lying    -> B                   (posture authoritative)
pose sees upright  -> VLM splits T vs A   (the one thing 2D pose cannot tell)
```

A VLM answer of B or C is **ignored** when pose sees someone upright. That gate
is the headline reliability claim and the Live tab must surface it (RO2).

**The four passive profiles and their appliance vectors** (`FUSED_APP`,
authoritative):

| Profile | Meaning | light | fan | tv |
|---|---|---|---|---|
| `T` | transitional (standing/walking) | 1 | 0 | 0 |
| `A` | active (sitting) | 1 | 1 | 1 |
| `B` | resting (lying) | 0 | 1 | 0 |
| `C` | unoccupied | 0 | 0 | 0 |

The thesis scope paragraph lists three occupancy classes (sitting, sleeping,
absent). The system implements four. Four is correct; the writing gets updated.

**ACTIVE, gestures.** Open palm toggles TV, peace toggles lights, fist is
all-off. A gesture holds for `CONFIRM_FRAMES`, then `HOLD_SECONDS`, then fires,
then disarms until the hand leaves for `REARM_SECONDS`. Active mode **never sets
the fan**: it writes `act.set(lights, 0, tv)`. Do not render a fan state in
active mode.

**Actuation.** `serial_actuator.py` writes `"a,b,c\n"` over USB serial to an
Arduino UNO. Pin 9 light, pin 10 fan, pin 11 tv. The old green/yellow/red
traffic light meaning is dead; the same three pins were relabelled with no
firmware reflash.

### What the current app gets wrong

`src/lib/state.ts` is built on the dead model and gets rewritten in Phase 1:

| Currently | Reality |
|---|---|
| 3 profiles `A/B/C` | 4 profiles `T/A/B/C` |
| `led: {green, yellow, red}` | `appliances: {light, fan, tv}` |
| `levelFromLed()` traffic light | profile drives the accent color |
| `PROFILE_LABELS` missing `T` | `T` = "Transitional" |

Keep `src/lib/theme.ts` and its card look, but rebind tokens to profiles:
`A` green, `T` blue, `B` amber, `C` slate. Add the blue token.

---

## 3. Architecture

```
  camera -> live_system.py (pose + VLM fusion, Layer 4) -> serial -> Arduino
                   |                        ^
            writes |                        | reads override.json each loop
                   v                        |
             live_log.csv            override.json
                   |                        ^
                   v                        | writes
            state_server.py  (read + command, LAN :8000)
                   |  ^
            JSON   |  | POST commands, trial markers
                   v  |
              app-monitor on iPhone (same WiFi)
```

Three rules that keep this safe:

1. **Only `live_system.py` owns the serial port.** The server never imports
   `serial_actuator`. Two writers on one `/dev/cu.usbmodem*` interleave into
   garbage. Commands reach the Arduino by way of the decision layer, which is
   also what makes the Controls tab satisfy RO1 rather than bypass it.
2. **The server never writes `live_log.csv`.** That file is FYP evidence. The
   server reads it. Trial data goes in its own file.
3. **Everything is LAN-local.** No cloud, no account, no telemetry. That is not
   just privacy hygiene, it is RO2's edge claim and the thesis problem statement
   names cloud cameras as the thing being avoided.

---

## 4. Data contracts

### 4.1 `live_log.csv` (written by the FYP, read-only to us)

One row per committed decision, not per frame. Header exactly:

```
time,mode,people,pose,vlm,phone,vlm_latency_s,profile,light,fan,tv
```

| Field | Written by | Meaning | Gotcha |
|---|---|---|---|
| `time` | all | `%H:%M:%S` local | **No date.** See 4.2. |
| `mode` | all | `PASSIVE`, `ACTIVE`, or `MANUAL` (new, see 4.3) | |
| `people` | passive | detected body count | blank on active rows |
| `pose` | passive | raw pose label `A`/`B`/`C` | blank on active rows |
| `vlm` | passive | raw VLM label or blank | blank when no person or not ready |
| `phone` | passive | phone-usage flag | **metadata only**, never affects control |
| `vlm_latency_s` | passive | seconds for the VLM call | blank when the VLM did not run |
| `profile` | all | passive: `T/A/B/C`. active: the **gesture name**. manual: `OVERRIDE` | different meaning per mode, never mix in one chart |
| `light`,`fan`,`tv` | all | `0`/`1` | active rows always write `fan` as `0` |

**The file does not exist yet.** The live loop has not run with hardware. Treat
"missing" as a normal empty state, never an error.

### 4.2 Known defects, handle them, do not paper over them

1. **No date on rows.** Sorting breaks across midnight and across sessions. The
   server attaches a date from the file's mtime and rolls forward one day when a
   row's time is earlier than the previous row's. Mark those rows
   `date_inferred: true` so the UI never claims false precision.
2. **Change-triggered, not sampled.** Gaps are dwell time, not missing data.
   Duration of row *i* is `time[i+1] - time[i]`; the last row runs to now only
   while the system is live.
3. **Append-only across runs.** No session marker. Treat a backwards time jump,
   or a gap over 30 minutes, as a session boundary.

### 4.3 Allowed edits to `live_system.py` (the only ones)

Both are additive, roughly 25 lines total, and both exist to serve an objective.
Make them in one commit, keep `python live_system.py selftest` passing, and add
a selftest case for each.

**(a) Manual override, for RO1.** At the top of each loop iteration, read
`override.json` if present. While `now < expires_at`, drive the appliance vector
from the override instead of the profile, and log one row with `mode=MANUAL`,
`profile=OVERRIDE`. On expiry, resume automatic control and log the resume. This
is the decision layer arbitrating two input sources, which is exactly what RO1
describes.

```json
{ "appliances": {"light": 1, "fan": 0, "tv": 1},
  "set_at": 1763000000.0, "expires_at": 1763000120.0, "source": "app" }
```

**(b) Response-latency instrumentation, for RO3.** RO3 requires response
latency and only the VLM call is currently timed. Add two fields to
`LOG_FIELDS`: `decide_latency_ms` (frame grab to committed decision, both modes)
and `actuate_latency_ms` (decision to serial write returning). Append to the end
of the header so existing parsers keep working. Without this, per-mode latency
cannot be reported and RO3 stays open.

**(c) Camera frame relay, added 2026-11-14 at the owner's request.** About
twice a second, write the annotated frame to `live_frame.jpg` (temp file then
rename). `state_server.py` serves it at `GET /frame.jpg` only while it is under
5 s old, and the Live tab shows it. The same file doubles as a heartbeat: the
log is change-triggered, so a quiet log alone cannot tell "nobody moved" from
"system stopped".

Nothing else. Do not refactor the fusion, the router, or the thresholds.

### 4.4 `trials.csv` (server-owned, the RO3 instrument)

New file, `~/fyp-prototype/trials.csv`. Written by the server, never by the FYP.

```
trial_id,started_at,armed_at,mode,expected,predicted,correct,response_latency_s,people,pose,vlm,vlm_latency_s,note
```

- `expected` is the ground truth the operator declared on the phone before
  posing. This column is what makes live accuracy computable at all.
- `armed_at` is when the countdown finished and the operator was in position.
  `response_latency_s` is measured from `armed_at`, not `started_at`.
- `predicted` is the first committed decision in `live_log.csv` after `armed_at`.
- A trial that sees no decision within the timeout records
  `predicted=TIMEOUT`, `correct=false`. Do not silently drop it; a non-response
  is a result.

### 4.5 `classify_results.csv` (offline eval, existing)

```
frame,actual,predicted,correct,seconds,raw_answer
```

Overwritten by each `classify_passive.py` run. Current record from
`docs/EVAL_passive_vlm.md`: 100% over 12 frames at 15.4 s mean. Twelve frames is
thin and the doc says so, so always print n beside the percentage. Once Trials
has 70+ rows, Stats leads with trial accuracy and keeps this as the offline
comparison.

### 4.6 JSON the app consumes

`src/lib/state.ts` mirrors this exactly.

```ts
type Profile = "T" | "A" | "B" | "C";
type Mode = "PASSIVE" | "ACTIVE" | "MANUAL";
type Appliances = { light: boolean; fan: boolean; tv: boolean };

type Decision = {
  at: string;                  // ISO 8601
  date_inferred: boolean;
  mode: Mode;
  profile: string;             // Profile | gesture name | "OVERRIDE"
  people: number | null;
  pose: string | null;
  vlm: string | null;
  phone: string | null;
  vlm_latency_s: number | null;
  decide_latency_ms: number | null;
  actuate_latency_ms: number | null;
  appliances: Appliances;
};

// GET /state
type SystemState = {
  online: boolean;             // false when live_log.csv is missing or stale
  stale_seconds: number;
  source: "live" | "replay";   // replay MUST be visible in the UI
  current: Decision | null;
  gate_active: boolean;        // pose and VLM disagreed and pose won
  override: { active: boolean; expires_in_s: number } | null;
};

// GET /metrics
type Metrics = {
  window: { from: string; to: string; seconds: number };
  activation: {                // Simulated Appliance Activation Reduction
    reduction_pct: number;
    per_appliance: Record<"light" | "fan" | "tv",
      { on_seconds: number; baseline_seconds: number; reduction_pct: number }>;
  };
  latency: {
    decide_ms: Record<"PASSIVE" | "ACTIVE", Stat | null>;   // per mode, RO3
    actuate_ms: Stat | null;
    vlm_s: Stat | null;
  };
  profile_distribution: Record<Profile, { seconds: number; pct: number }>;
  accuracy: {
    live: { n: number; correct: number; pct: number;
            per_profile: Record<Profile, { n: number; pct: number }> } | null;
    offline: { n: number; correct: number; pct: number; captured_at: string } | null;
  };
};

type Stat = { n: number; mean: number; p50: number; p95: number };
```

---

## 5. What is and is not computable

Build the Stats tab from this table, not from optimism.

### Computable

**Simulated Appliance Activation Reduction** (RO3, third clause). Every row
carries `light/fan/tv` plus a timestamp, so on-time is a sum of durations.

```
baseline_seconds = window_seconds              // always-on comparison
on_seconds       = sum of durations where that appliance == 1
reduction_pct    = 100 * (1 - on_seconds / baseline_seconds)
```

Report per appliance and as a mean. Always state the window length. Label it as
simulated over LED proxies. Never a watt claim.

**Response latency** (RO3, second clause). Two independent sources, report both:
`decide_latency_ms` per mode from 4.3(b), and end-to-end
`response_latency_s` from `trials.csv`. They measure different things and the
difference is informative: the first is machine time, the second includes the
full perception-to-actuation path.

**Accuracy** (RO3, first clause). From `trials.csv` only, because it is the only
file with a declared ground truth. Report overall and per profile, since a
system that is 100% on C and 40% on T is not 70% useful.

**Profile distribution.** Passive rows only, by dwell time.

**VLM latency.** `vlm_latency_s` where present. Never average in blanks.

### Not computable, render "not yet measured"

- **Accuracy from `live_log.csv` alone.** No ground truth column. This is the
  entire reason the Trials tab exists.
- **Pose-engine accuracy.** The pose-vs-VLM comparison run is still outstanding
  in the checklist.
- **Watts, kWh, cost, carbon.** Three LEDs. Any such figure would be invented.

### Honest caveats the UI must carry

- Trial response latency includes operator reaction time. Mitigate with the
  countdown and measure from `armed_at`, then state the caveat under the number.
- A trial's `predicted` is the first decision after arming, so a system still
  settling from the previous trial can be scored early. Enforce a settle gap
  between trials (Section 7.4) and record it.

---

## 6. The state server

New file `~/fyp-prototype/state_server.py`. Python, stdlib first. Reads
`live_log.csv` and `classify_results.csv`, owns `override.json` and
`trials.csv`, never touches serial.

```
GET  /health            -> { ok, source, rows, log_path, lan_ip }
GET  /state             -> SystemState
GET  /history?limit=200 -> newest first
GET  /metrics?window=   -> session | today | all
GET  /frame.jpg         -> latest camera frame, 404 unless under 5 s old
POST /override          -> { appliances, hold_s }   sets override.json
DELETE /override        -> clears it, resumes automatic
POST /trials/start      -> { expected, mode, countdown_s } -> trial_id
POST /trials/arm        -> { trial_id }  marks armed_at, starts the clock
GET  /trials            -> list + aggregate accuracy and latency
DELETE /trials/:id      -> discard a spoiled trial, must be explicit
```

Requirements:

- Bind `0.0.0.0:8000`, print the LAN IP at startup.
- Permissive CORS, it is a LAN tool.
- Poll mtime and size, re-parse only on change.
- Missing `live_log.csv` is valid: `online: false`, empty history, null metrics.
- `online` false when the newest row is older than 30 s and no fresh camera
  frame exists (the frame is the heartbeat, see 4.3(c)).
- Override writes are atomic (temp file then rename) so the FYP loop never reads
  a half-written JSON.
- `--replay <fixture.csv>` serves a fixture and sets `source: "replay"`.
- `--selftest` asserts duration, reduction, and trial-matching math against a
  fixture with hand-checked answers. No test framework.

### 6.3 Replay fixture, this is how you build without hardware

`~/fyp-prototype/fixtures/replay_log.csv`, real schema, roughly 40 rows:
a C to T to A progression, a B stretch, two ACTIVE gesture rows, one MANUAL
override row, at least one row where `pose=A` and `vlm=B` to exercise
`gate_active`, blank `vlm_latency_s` on several rows, and one backwards time
jump to exercise session splitting.

**The UI shows a persistent "Replay data" banner whenever `source` is
`replay`.** Not optional. A demo that looks live but is not would be dishonest
in front of an examiner, and the banner costs one component.

---

## 7. Screens

Expo Router, five tabs, keep the `PillTabBar` glass pill and the white-card look.

### 7.1 Home — the smart home face

Current profile card (letter, label, accent, "updated Xs ago"), mode chip,
three appliance tiles showing light/fan/tv, last five decisions. When `online`
is false, dim the card and say "System not running"; never present a stale
profile as current. When an override is active, show the remaining hold time.

### 7.2 Live — the pipeline, for RO2

The tab that explains the system to an examiner. Legibility over polish.

- Pipeline strip: `people -> pose -> VLM -> fused profile -> appliances`, each
  stage showing its current value from the latest decision.
- When `gate_active`, mark the VLM value overridden and label it "presence gate:
  pose authoritative". This is the main reliability claim, made visible.
- Phone flag tagged "metadata only, does not affect control".
- Edge indicator: "All inference local on this Mac. No cloud. Video stays on
  this WiFi." This is RO2's deployment claim and the thesis problem statement's
  privacy argument.
- VLM thinking indicator with last measured latency.
- **Camera feed, real or absent, never faked.** (Changed 2026-11-14, owner
  request; was "no camera feed".) The Live tab shows the Mac's own annotated
  frame relayed over the LAN, see 4.3(c). When no fresh frame exists, including
  on replay, it shows "Camera feed offline".

### 7.3 Stats — the RO3 report

Ordered to mirror RO3's own clauses.

1. **Accuracy.** Live trial accuracy with n, plus per-profile breakdown. Offline
   figure beneath it as comparison, labelled with its date and n=12. If trials
   are empty, "not yet measured", never 0%.
2. **Response latency.** Per mode. Both `decide_latency_ms` and end-to-end trial
   latency, labelled distinctly, with the reaction-time caveat.
3. **Simulated Appliance Activation Reduction.** Headline percentage, per
   appliance breakdown bar, window length, simulated-proxy label.
4. **Profile distribution.** Hand-built bars, no chart library.

Every card carries source and sample size. A number without provenance does not
ship.

### 7.4 Trials — the RO3 instrument (the important one)

Turns the phone into the evaluation rig. The operator sets the phone down where
the camera can see them, so the flow must work at arm's length: large text,
large targets, audio or haptic cues rather than things you must read mid-pose.

Flow for one trial:

1. Pick the expected class: `T`, `A`, `B`, `C`, or a gesture.
2. Tap Start. Countdown, default 10 s, adjustable, with haptic ticks.
3. At zero the app POSTs `/trials/arm`. Operator is in position.
4. Server watches `live_log.csv` for the next committed decision, records
   `predicted` and `response_latency_s`, timeout default 60 s.
5. Result card: correct or wrong, latency, and the raw pose and VLM labels so a
   wrong answer can be diagnosed rather than just counted.
6. Enforced settle gap, default 15 s, before the next trial can arm.

Also needed:

- **Session runner.** Queue n trials per class (default 10, which is the
  checklist's requirement) in randomised order. Randomisation matters: a fixed
  T, A, B, C order lets temporal smoothing flatter the result.
- **Progress to target.** "41 of 70 trials" against the 70-point requirement,
  broken down per class so gaps are visible.
- **Discard with a reason.** Spoiled trials happen. Deleting one must be
  explicit, recorded, and counted, so the discard rate can be reported honestly.
- **Export.** Share `trials.csv` off the phone for Chapter 4.

### 7.5 Controls — RO1's manual input path

Now live, since Dr. Zaaba approved it.

- Three appliance toggles. A tap POSTs `/override` with a hold duration
  (default 120 s, adjustable).
- A visible countdown and a "Resume automatic" button that DELETEs the override.
- Copy that states what is happening: "Manual override active. Automatic control
  resumes in 1:42." The point of RO1 is the decision layer arbitrating, so the
  UI should show arbitration, not pretend the phone is a light switch.
- Gesture reference: palm TV, peace lights, fist all-off.
- Disable the toggles with an explanation when `online` is false. Queuing
  commands for a system that is not running would be a lie.

---

## 8. Phases

Stop and report at each boundary.

| # | Phase | Done when |
|---|---|---|
| 1 | **Data model.** Rewrite `state.ts` to 4.6, rebind `theme.ts` to profiles, add the blue `T` token, update all screens to compile. Still mock. | `npx tsc --noEmit` clean, app runs in the simulator |
| 2 | **Server and fixture.** `state_server.py` read-only endpoints plus `fixtures/replay_log.csv`. | Four GET endpoints verified by curl, `--selftest` passes, `/metrics` returns a hand-checkable reduction |
| 3 | **Wire the app.** Replace `getState()` with fetch. Settings entry for the Mac LAN IP, persisted. Poll 2 s foregrounded, back off backgrounded. Offline, stale, and replay states visible. | All five tabs render from the server |
| 4 | **Stats.** The four cards against computed metrics. | Every number traceable by hand to fixture rows |
| 5 | **Trials.** `trials.csv`, trial endpoints, the Trials tab, session runner, export. | A full 10-trial session runs end to end on replay and writes correct rows |
| 6 | **FYP edits.** The two additions in 4.3, plus selftest cases. | `python live_system.py selftest` passes, override round-trips on replay |
| 7 | **Controls.** Toggles, countdown, resume. | Override round-trips and the UI reflects expiry |
| 8 | **Hardware day.** Run `live_system.py` with camera and Arduino, point the server at the real log, confirm the app tracks it, then run a real trial session toward 70 points. | RO1, RO2, RO3 each demonstrable on real data |

Phases 1 to 5 and 7 need no hardware. Only Phase 8 does.

---

## 9. Terminology

| Use | Never use |
|---|---|
| Simulated Appliance Activation Reduction | energy saving, energy saved, power saved, Simulated Energy Reduction, kWh, cost, carbon |
| Profile T / A / B / C | the green/yellow/red traffic light (dead model) |
| Appliances: light, fan, tv | LEDs as colors |
| Presence gate | hallucination filter |
| Trial accuracy (n=N) | accuracy, unqualified |
| Manual override | remote control |

---

## 10. Open questions for the owner

1. **Override default hold.** 120 s is a guess. Too short looks broken in a
   demo, too long looks like the automation stopped. Tune on hardware day.
2. **Trials per class.** The checklist says 10 per response path for 70 points.
   Confirm whether gestures count toward that 70 or are evaluated separately,
   because it changes the session runner's target math.
3. **Who operates trials.** Single-person operation means posing and tapping.
   The countdown covers it, but a second person reading the prompts is faster
   and less error-prone for a 70-trial run.
4. **Chapter 4 alignment.** This app produces trial accuracy, per-mode latency,
   and activation reduction. Confirm with Dr. Zaaba that those three are the
   reported RO3 measures, before 70 trials get collected against the wrong spec.
