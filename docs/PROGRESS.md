# FYP Progress - Vision-Based Smart Power Management

Last updated: 2026-11-21

## Status: working end to end, live-tested on the iPhone 12 + Arduino

One entrypoint, `live_system.py`, runs the five-layer pipeline. Pose decides
presence, a VLM decides posture, gestures override per appliance, and five LEDs
stand in for the light, fan, TV, desk lamp and aircond. The VLM is **Moondream** by default
(`moondream_vlm.py`, decided 2026-11-14); `python live_system.py qwen` runs the
evaluated alternative.

## How it works
- **Camera** (`camera.py`): pinned to index 1 (iPhone 12), verified by probe;
  refuses to fall back to the Mac webcam. Frames are 1920x1080.
- **Detection runs on a 960 px copy**, pose every 2nd frame (GPU headroom for the
  VLM); hands run on the full-res frame (far hands are small); the display stays
  full resolution.
- **Presence = pose** (MediaPipe multi-pose, up to 4 people, containment-based
  duplicate removal). With Moondream, presence must also be CONFIRMED by the VLM
  describing a person within `PRESENCE_CONFIRM_SECONDS` (10 s), because pose
  produces phantom people on furniture at full confidence. Unconfirmed boxes are
  drawn grey. A room is called empty after `EMPTY_SECONDS` (8 s) of no presence.
- **Posture = VLM** (background thread, throttled by `VLM_MIN_INTERVAL`). Its
  answer sets T/A/B; while no answer exists the current profile is HELD.
  Pose still draws a posture label on the box, but it does not drive the LEDs.
- **Mode selection**: a hand raised with knuckles above the person's face
  (eye/ear landmarks) enters ACTIVE. While ACTIVE, any gesture-shaped hand can
  gesture; 6 s with no gesture returns to PASSIVE.
- **Gestures** (from `live_active.py`, with upright/consistency/hold/re-arm
  gates): open palm = TV, peace = light, fist = all off. Each holds the
  appliance it touched for 60 s (`OVERRIDE_SECONDS`) or until the profile
  changes; the overlay shows `[MANUAL Ns]`.
- **Actuation**: `FUSED_APP` maps the profile to (light, fan, tv, lamp, ac) on
  pins 9/10/11/8/7 via `serial_actuator.py` (variadic). The LCD runs on the SAME
  Arduino (`arduino/room_node.ino`, 0x27); `display_node.py` shares the actuator's
  open port. Policy follows `FYP_Room_Activity_and_Appliance_Decision_Profiles.md`.

| Profile | Meaning | light | fan | tv | lamp | ac |
|---|---|---|---|---|---|---|
| T | transitional (standing / walking) | ON | ON | hold | off | hold |
| A | active (sitting) | ON | ON | off | ON | ON |
| B | resting (lying) | off | ON | off | off | ON |
| C | unoccupied | off | off | off | off | off |

Revised 2026-11-16 to the supervisor's profiles doc. Two deliberate reversals from
the first prototype (pinned by selftest): sitting no longer turns the TV on, and
standing no longer turns the fan off. "hold" = the doc's "No change" (`resolve_hold`
keeps whatever the appliance is doing). AC is an ASSUMED policy (no temp sensor).

## VLM configurations
| | Qwen (`python live_system.py qwen`) | **Moondream (default)** |
|---|---|---|
| model | `qwen3-vl:4b`, thinking off | `moondream`, 60-token cap |
| prompt | one letter + phone flag | "Describe the people in this image." + word-boundary keywords |
| labelled set (12) | 12/12 | 12/12 |
| latency | ~20 s offline, ~12-19 s live | 0.82 s offline, 1.87 s live |
| confirms presence | no (too slow) | yes, 10 s window |
| leaving -> C | 8 s, or never if pose sees phantoms | 10-18 s |

## Hardware (rebuilt 2026-11-21: 5 appliances + LCD + OLED on ONE Uno)
- Board: Arduino UNO, port `/dev/cu.usbmodem1101`, FQBN `arduino:avr:uno`.
- Toolchain: `arduino-cli` (no IDE); Rosetta 2 required for the AVR toolchain.
- 5 LEDs: pin 9 light, 10 fan, 11 tv, 8 desk lamp, 7 aircond. Each pin -> 1 kOhm
  -> LED long leg; short leg -> breadboard blue (-) rail -> one wire to Arduino GND.
  (One shared ground rail because 5 LEDs + LCD exceed the 3 Arduino GND holes.)
- LCD: 16x2 I2C at 0x27, on hardware I2C (SDA->A4, SCL->A5, direct to Arduino).
  GND->blue rail, VCC->red (+) rail (fed from Arduino 5V). Status display.
- OLED: 0.96" SH1106 at 0x3C, on software I2C (SDA->pin 12, SCL->pin 13).
  GND->blue rail, VCC->red (+) rail. Represents the TV appliance: shows content
  when TV=1, blank when TV=0. Uses U8g2 page-buffer mode (low RAM).
  NOTE: sharing hardware I2C between LCD and OLED caused library conflicts; software
  I2C on separate pins was the fix.
- Stepper fan (PARKED, too slow): 28BYJ-48 + ULN2003 on pins 2-5, spins when the
  fan value is on. Being replaced by a fast DC motor + IRF520 MOSFET module.
- Firmware: `arduino/room_node.ino`. Accepts `"l,f,t,d,a\n"` for the LEDs (variable
  count; an old `"a,b,c"` still works) and `"top|bottom\n"` for the LCD, at 9600
  baud. The TV value (index 2) also drives the OLED. Probes 0x27 at boot and skips
  LCD calls if none answers. RAM: 1018 bytes globals, 1030 free. Full pin map
  in `docs/WIRING.md`.

## Key files
- `live_system.py` - main entrypoint. Pure logic (`decide_mode`, `fuse_label`,
  `control_hand_debug`, `FUSED_APP`) is camera-free; `python live_system.py
  selftest`.
- `moondream_vlm.py` - the default VLM engine: people prompt, keyword labels,
  phone flag, and it saves every judged frame + description
  (`snapshots/vlm/`, `vlm_descriptions.csv`). `python moondream_vlm.py selftest`.
  `live_system.use_qwen()` swaps in `classify_passive` instead.
- `live_passive.py` - pose engine (`analyse` returns box, posture, ratio, face
  y), low-light rescue, smoothing constants. `python live_passive.py selftest`.
- `live_active.py` - gesture engine.
- `classify_passive.py` - Qwen prompts, `ask`/`parse_*`, offline evaluator.
- `camera.py` - pinned index; `python camera.py probe` saves one frame per index.
- `serial_actuator.py`, `arduino/power_leds` - actuation.
- `blender/room_model.py` - 3D room model.
- `state_server.py` - stdlib bridge: JSON API (`/state`, `/history`, `/metrics`,
  `/frame.jpg`), the Trials endpoints (`/trials`, writes `trials.csv`), and it
  serves the built dashboard at `/`. `python state_server.py --selftest`.
- `web-dashboard/` - React + Vite "Awaero" (Home, Live, Stats, Trials). Spec and
  as-built departures: `web-dashboard/PRD.md`. Style source: `DESIGN.md`.
  Build with `npm run build`; the server serves `dist/`, never the dev server.
- `archive/` - logs and frames of every test run (evidence for Chapter 4).

## Known limitations (be ready for Q&A)
- **2D pose cannot read posture here.** Leaning over a desk compresses the torso
  exactly like lying feet-to-camera; sitting and standing body-extent ratios
  overlap. Posture is the VLM's job for this reason.
- **Pose phantoms**: false people on the chair / clothes rack with landmark
  confidence ~1.00, the same as real people. Only the VLM confirmation removes
  them (Moondream path).
- **Hallway**: the camera sees past the room; a person there counts as present.
- **Darkness**: low-light rescue helps dim rooms, not black ones (IR camera is
  the production answer).
- **Qwen latency**: ~15 s per answer live; posture changes wait for it.

## Run
```bash
source venv/bin/activate
python live_system.py           # the system (Moondream VLM)
python live_system.py qwen      # same, with Qwen3-VL instead
python live_system.py selftest  # logic checks, no camera/board
python camera.py probe          # if the camera indices ever change
# keys: q quit. Do NOT press number keys during a test (camera switch).
```
Needs Ollama running (`brew services start ollama`). Stop the other model first
so they don't share the GPU (`ollama stop qwen3-vl:4b`).

## Re-flash firmware (only if changed)
```bash
arduino-cli compile --fqbn arduino:avr:uno arduino/room_node
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn arduino:avr:uno arduino/room_node
```
Arduino libs installed: LiquidCrystal I2C 1.1.2, U8g2 2.36.19, DHT sensor
library 1.4.7, Adafruit Unified Sensor.

## Environment
- `venv` (Python 3.12): mediapipe 0.10.21, opencv 4.11.0, numpy 1.26.4,
  pyserial, ollama. Ollama 0.35.0 with `moondream`, `qwen3-vl:2b/4b/8b`.
- Cameras: index 0 MacBook webcam, index 1 iPhone 12 (pinned). iPhone 17
  ("Amvx") excluded.

## Session log
- **2026-11-21**: OLED TV display wired and tested. 0.96" SH1106 OLED on software
  I2C (pins 12/13) represents the TV: shows content when TV=1, blank when TV=0.
  Sharing hardware I2C (A4/A5) caused library conflicts (U8g2 vs LiquidCrystal_I2C);
  fix: LCD on hardware I2C, OLED on software I2C. Firmware updated with U8g2 page
  mode. Both screens work together. Pin map and WIRING.md updated. Port now
  `/dev/cu.usbmodem1101`.
- **2026-11-17**: Awaero phone app built (`awaero-app/`, a copy of app-monitor,
  `com.amiryzat.awaero`) carrying the same server data as the web dashboard, 5
  appliances, Trials tab, real accuracy. Fixed `state_server.py` to serve camera
  frames as `no-cache` (React Native's image loader rejects `no-store`), which also
  fixes the old app. Restarted the stale server (it predated the 5-appliance change).
  Commits f50dfe9, 8ab027d. Full handoff: `awaero-app/PROGRESS.md`.
- **2026-11-16**: Hardware day - 3 appliances -> 5. Wired light/fan/tv/desk-lamp/
  aircond LEDs (pins 9/10/11/8/7), each tested lit; built a shared blue (-) ground
  rail + red (+) 5V rail. Moved the LCD onto the SAME Arduino (`arduino/room_node.ino`,
  0x27) - the old "random symbols" was an uninitialised screen (firmware hung probing
  a missing LCD; now it probes 0x27 and skips LCD calls when absent). Rewrote
  `FUSED_APP` to the supervisor's profiles doc (TV off when sitting, fan held when
  standing, lamp + AC added, HOLD sentinel via `resolve_hold`, AC an assumed policy).
  Fixed the activation-reduction metric to count only appliances a log recorded (an
  absent column was a 100% false saving). Wired a 28BYJ-48 stepper as the physical
  fan (non-blocking) but parked it as too slow. `serial_actuator.set()` variadic;
  `display_node` shares the actuator port. All selftests pass; dashboard shows 5.
  Commits 4078b76, 3ff8338, 03adf11, 887bcec, 909efa3, ff173fb. Holes: `docs/WIRING.md`.
- **2026-11-15 (night)**: web-dashboard UI session, `web-dashboard/` only (no FYP
  Python changed). Web-first layout (>=900px left sidebar with icons; below that
  the topbar + rubber bottom tab bar). Live camera preview at native aspect.
  Stats: 2 column grid, Session timeline strip, Accuracy by response path bars,
  blur-only latency Explain modal, rubber window selector. Trials: card
  consistency + mobile overflow fix. Hybrid restyle to `DESIGN.md` (monochrome
  chrome, profile/status colours kept, borderless soft-shadow cards). No new
  runtime dependencies (BoardUI, React Bits and a 21st.dev chart were rebuilt by
  hand). Open: per-path accuracy is on both Stats and Trials. See `docs/RESUME.md`
  and `web-dashboard/PRD.md` Section 11.
- **2026-11-15**: app-monitor + networking day. Fixed state_server.py
  midnight log-parsing bug (a run crossing 00:00 split into two sessions,
  Stats showed a 110 s window at 0%); `parse_log` now rolls the day without
  splitting, only a >30 min gap splits (`_selftest_midnight` added, selftest
  passes). Rewrote app auto-discovery (`src/lib/useSystem.ts`): learns the
  Mac's IP + Bonjour name from /health, races all known addresses each
  reconnect, survives the DHCP move and self-recovers; added a Settings
  'Wireless check'. Installed on the iPhone 17. Diagnosed phone-to-Mac
  wireless as a DEAD END on the borrowed WiFi (two APs share one SSID and
  isolate clients; not our router, not a code bug); cable stays for now.
  Decided the backup = one LOCAL web app served at `/` (login + dashboard),
  no cloud/Vercel. See `docs/RESUME.md`.
- **2026-11-14**: First full live testing day. Fixed in order: router stuck in
  ACTIVE on typing hands; pose only ran in passive; silent webcam fallback and
  unreliable camera ordering (now pinned); lying misreads at the desk (hip
  visibility guard); duplicate head boxes (containment dedupe); GPU contention
  (10 s standalone vs 44 s live; now 960 px + pose every 2nd frame); VLM
  thinking disabled; model study (Qwen 2b/4b/8b, Moondream); fusion settled as
  pose = presence, VLM = posture, hold instead of guess; gesture fixes (enter by
  raised hand, then gesture freely; face-based raise test; idle timeout;
  per-appliance 60 s override). Evening: Moondream runner; people-focused prompt
  (lying 1/12 -> 12/12, empty 41/41); VLM-confirmed presence beats pose phantoms;
  leaving -> C in 10-18 s. Full numbers in `EVAL_passive_vlm.md`.
- **2026-11-15 (late)**: Three live-run fixes BUILT + VALIDATED in a second run.
  (1) **Posture debounce** (`debounce_vlm`, N=2): the VLM read SEQUENCE is now
  debounced, not frames (one VLM read floods the 4 s frame window in ~1 s, so it
  never damped the VLM). (2) **Fist "leaving" latch**: all-off until the room
  empties (C) or ANY gesture cancels it; fist no longer sets per-appliance holds
  (`GESTURE_HOLDS["fist"]=[]`) so a "changed my mind" gesture fully resumes auto.
  (3) **ACTIVE->PASSIVE log row** so the app/LCD stop freezing on ACTIVE. All
  three confirmed in `live_log.csv`. Also: each trial now logs `vlm_latency_s`
  (detection latency) alongside decide/actuate. **After-fix run: 77 trials, 89.6%
  raw; A 11/11 and B 10/10 both hit 100% (were 90/80 - the VLM-flicker victims);
  once the operator's timing settled (after 21:00) 50/51 = 98.0%.** T dipped to
  75% but all 3 misses were front-loaded while learning the new ~2-read lag (T
  passed 8/8 after 20:57). Before set archived as
  `archive/trials_before_debounce_2026-11-15.csv`. Dashboard: countdown lifted to
  App so it survives tab switches (floating banner on every tab), 15 s delay added.
- **2026-11-15 (eve)**: Local web dashboard "Awaero" BUILT (React+Vite, served by
  state_server.py at `/`). **Trials recorder BUILT** - the RO3 instrument (declare
  ground truth, server scores its own live decision, capture countdown for B/C).
  First real run (BEFORE the fixes): **73 trials, 94.5%** (T 11/11, A 9/10, B 8/10,
  C 10/10). Live-run flaws found + ranked fixes. `lcd_scroll.py` util added.
- **2026-11-13**: Integrated entrypoint `live_system.py`; LEDs relabelled per
  appliance; decision logging; Blender room model.
- **2026-11-12**: Qwen3-VL swap; dataset recaptured from the iPhone 12.
- **2026-11-11**: Camera-by-name selection, multi-pose passive, smoothing,
  low-light enhancement.
- **2026-11-10**: Arduino LED actuation built and wired (`HANDOFF.md`).

## Next
- **One full camera->VLM->LED live run with the 5 appliances** - the revised policy
  has only been driven directly, not yet through the camera pipeline. Launch
  `live_system.py` TRACKED so the whole run can be analysed.
- Fast DC motor swap for the physical fan (DC motor + fan blade + IRF520 module).
- The three live-run fixes are DONE + validated. RO3 postures AND gestures now have
  >=10 trials each (A 11, T 12, B 10, C 10, open_palm 12, peace 12, fist 10).
- End-to-end camera->LED response time table per transition: per-trial `vlm_latency_s`
  + decide/actuate are now logged; still want the wall-clock per-transition table.
- Known limitations to document (not bugs): ~20 s to confirm unoccupied is deliberate
  `EMPTY_SECONDS` hysteresis; a person bent over the desk can read as A (sitting) then
  self-correct to T - the standing-vs-sitting-when-bent case is genuinely ambiguous.
- For the viva: one network we control (hotspot/pocket router), both devices on it.
- Writing: Chapter 3 (fusion), Chapter 4 (94.5% before vs 98% settled after + the
  A/B->100% story, with the T-lag tradeoff), Chapter 5.
