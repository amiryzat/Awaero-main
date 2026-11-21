# FYP Context - for a new chat

Read this plus `PROGRESS.md` to continue without re-reading the old chat.
`PROGRESS.md` = technical build state. This file = decisions, rationale, and
the open questions. Evidence for every number is in `EVAL_passive_vlm.md`.

## The project
- Title: Context-Aware Vision-Based Smart Power Management System for
  Room-Level Energy Optimisation Based on Activity Detection.
- Final-year CS project, UiTM. Studies finish ~Feb 2027. Viva ahead.
- Supervisor: Ts Dr. Zaaba. Amir has full control over technical decisions
  (Dr. Zaaba said he can decide which approach is best). Scope: single node,
  single room. Dr. Zaaba approved a dashboard/app for RO3 evaluation.
- Dual-mode system over a 5-layer architecture
  (Perception -> Pre-Processing/Mode Selection -> Inference -> Decision ->
  Actuation), ending at USB/PySerial to an Arduino. No networking layer.
  - Passive: scene/posture -> 4 energy profiles: T (transitional/standing),
    A (active sitting), B (resting), C (unoccupied).
  - Active: hand gestures -> open palm = TV, peace = lights, point = desk lamp,
    rock = AC, fist = all-off.

## Current state (2026-11-21)
- **app-monitor** (phone app) works over the USB cable through PRD Phase 4;
  auto-discovery rewritten and installed on the iPhone 17. **Wireless
  phone-to-Mac is a dead end on the borrowed WiFi** (two APs share one
  SSID and isolate clients; not our router, not a code bug), so the cable
  stays for now. **Backup decided: one LOCAL web app served by
  state_server.py at `/`** (login + dashboard), no cloud, no Vercel. **Now BUILT**
  ("Awaero": Home, Live, Stats, Trials; styled per `DESIGN.md`; departures from
  its spec are in `web-dashboard/PRD.md` Section 11).
  state_server.py midnight log-parsing bug fixed + tested. Full handoff
  in `docs/RESUME.md`.
- `live_system.py` runs the whole pipeline end to end on the iPhone 12 +
  Arduino, verified across many live runs.
- **Fusion, settled by evidence:** pose = PRESENCE only; the VLM = POSTURE
  (T/A/B). While no VLM answer exists the profile is HELD, never guessed. Pose
  posture failed three ways in this room (torso angle, foreshortening, body
  extent: a man standing bent over the desk measured inside the seated range),
  and pose guessing made the LEDs switch twice per event.
- **VLM engine: Moondream (decided by Amir, 2026-11-14)**, the default in
  `live_system.py` via `moondream_vlm.py`. Prompt "Describe the people in this
  image.": 12/12 on the labelled set (same as Qwen), 0.82 s offline, 1.87 s live.
  Because it is fast it also CONFIRMS presence (room occupied only if a person
  was described in the last 10 s), which overrides pose's phantom people on
  furniture. Leaving -> C in 10-18 s. Qwen (`qwen3-vl:4b`, thinking off,
  ~12-19 s live) remains available: `python live_system.py qwen`.
- **Mode selection:** a hand raised above the FACE (eye/ear landmarks) enters
  ACTIVE; any gesture-shaped hand keeps it; 6 s idle returns to PASSIVE. Gesture
  overrides are per appliance, held 60 s or until the room context changes.
- **Camera:** `camera.py` is PINNED to index 1 (iPhone 12), verified by
  `python camera.py probe`. Name-matching via system_profiler was unreliable.
  It refuses to fall back to the Mac webcam.
- **Five appliances (revised 2026-11-16):** pin 9 light, 10 fan, 11 tv, 8 desk
  lamp, 7 aircond. The LCD runs on the SAME Arduino (`arduino/room_node.ino`, 0x27),
  no second board. A **0.96" SH1106 OLED** (added 2026-11-21) on software I2C
  (pins 12/13) represents the TV: shows content when TV=1, blank when TV=0. The
  LCD stays on hardware I2C (A4/A5). Both screens + 5 LEDs on one Uno, tested.
  Breadboard holes and full pin map in `docs/WIRING.md`. The decision policy now
  follows `FYP_Room_Activity_and_Appliance_Decision_Profiles.md` (see below).
- **Logging:** `live_log.csv` (or `live_log_moondream.csv`) = the RO3 data
  source for the app. Snapshots per decision; the Moondream runner also saves
  every judged frame + its description.

## THE APPLIANCE POLICY (revised 2026-11-16, from the supervisor's profiles doc)
Five appliances now, in pin order light, fan, tv, lamp, ac. `FUSED_APP`:
- A sitting: light ON, fan ON, **TV OFF**, lamp ON, AC ON
- T standing: light ON, **fan ON**, TV hold, lamp OFF, AC hold
- B lying: light OFF, fan ON, TV OFF, lamp OFF, AC ON
- C empty: all OFF

Two deliberate changes from the first prototype, both pinned by selftest so they
cannot regress: **sitting no longer turns the TV on** (sitting is not proof of
watching), and **standing no longer turns the fan off** (standing is a transition,
not a departure). "No change" rows use a HOLD sentinel resolved by `resolve_hold`
against whatever the appliance is currently doing; T holds TV and AC.

**AC is NOT auto-on (changed 2026-11-19).** It is off in the automatic policy and
comes on only by the ROCK gesture, or by temperature when the DHT22 arrives. The
fan is the default cooling, and **AC and fan never run together** (Malaysian norm):
`exclusive_cooling()` forces the fan off whenever the AC is on. There is no temperature sensor yet,
and the doc is explicit that AC control must then be described as a configurable
assumption, never a measured context-aware decision. A DHT11 would make it genuine
(future work). The desk lamp is a separate appliance from the main light: lamp is
ON only while sitting, the ceiling light is ON in both T and A.

## THE PASSIVE-ENGINE DECISION (decided: Moondream)
Amir chose Moondream on the measured case: equal accuracy to Qwen on the
labelled set at ~1/25 of the latency, it can confirm presence (Qwen is too slow
to), and it is the model Chapter 3 specifies. The key was the prompt: "Describe
this image." ignored people lying on the bed (1/12); "Describe the people in this
image." caught 12/12 and never invented a person in 41 empty frames. Qwen is the
evaluated alternative in Chapter 4.

## Demo decisions already made
- Camera: static, mounted, iPhone 12. The elevated CCTV idea goes in Chapter 5.
- Physical build: cardboard model house, the LEDs become labelled appliances,
  extended on female-to-male jumper wires. Everything 5V/USB, never 240V mains.
  A relay with a low-voltage load is optional.
- Physical fan: a 28BYJ-48 stepper was wired and spins but is too slow (~10-15 rpm,
  geared); being replaced by a fast plain DC motor (+ IRF520 MOSFET module). The
  fan value drives the motor, so no protocol change when it is swapped.
- A spare servo is kept for an optional AC vent flap (opens when AC turns on).
- 3D room model already done in Blender (`blender/room_model.py`).
- Present VLM limitations honestly with the measured mitigations.

## Remaining work
- **Dashboard + RO3 trials: built.** >=10 live trials on every posture and gesture
  path. Before the posture fixes 94.5% (n=73); after, 89.6% raw (n=77) and 98.0%
  once operator timing settled. Still open here: the per-transition camera->LED
  latency table and the final Simulated Appliance Activation Reduction figure.
- Chapter 3 alignment to the settled fusion (draft in `VLM_vs_Pose.md`).
- RO3 still open: end-to-end camera->LED response time per transition, and the
  final Simulated Appliance Activation Reduction figure. (Mandated term; "energy saving performance" and
  "Simulated Energy Reduction" are banned.)
- **One full camera->VLM->LED live run with the 5 appliances** - the revised
  policy has only been driven directly, never through the camera pipeline yet.
- Fast DC motor swap for the physical fan; optional DHT11 for real AC temperature.
- Physical model house; optional presence status LED.
- Chapters 4 and 5.

## How the user likes to work
- Direct, honest pushback over agreement. Hold firm recommendations; don't
  fold when scope shifts mid-task.
- Single clear next step over long walkthroughs; gets overwhelmed by big dumps.
- No em dashes. Raw code/files to copy over zip packages.
- Amir runs the camera/hardware and sends screenshots; the assistant reads the
  saved snapshots and logs to verify instead of guessing.
- Separate test files for experiments ("don't disturb the working detection").

## Key files
- `live_system.py` (main entrypoint: mode select, fusion, LEDs, logging,
  snapshots), `moondream_vlm.py` (default VLM engine),
  `live_passive.py` (pose engine), `live_active.py` (gesture engine),
  `classify_passive.py` (Qwen prompts + offline evaluator), `camera.py`
  (pinned index + probe), `serial_actuator.py`, `arduino/power_leds`.
- `state_server.py` (JSON API, Trials, serves the dashboard), `web-dashboard/`
  (React + Vite "Awaero"; spec `web-dashboard/PRD.md`), `awaero-app/` (Expo phone
  app, same server data, 5 appliances).
- `docs/WIRING.md` - exact breadboard holes for all 5 appliances, LCD, OLED, and
  full pin map (including reserved pins for DHT22 and DC motor).
- `FYP_Room_Activity_and_Appliance_Decision_Profiles.md` - the supervisor's spec
  the revised policy implements.
- Docs: `PROGRESS.md` (build detail), `CHECKLIST.md` (done vs not),
  `EVAL_passive_vlm.md` (all measurements), `VLM_vs_Pose.md` (thesis framing),
  `HANDOFF.md` (historical hardware handoff).
- Evidence: `archive/` holds every test run's log and frames.
