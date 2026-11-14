# FYP Progress - Vision-Based Smart Power Management

Last updated: 2026-11-14

## Status: working end to end, live-tested on the iPhone 12 + Arduino

One entrypoint, `live_system.py`, runs the five-layer pipeline. Pose decides
presence, a VLM decides posture, gestures override per appliance, and three LEDs
stand in for the light, fan and TV. The VLM is **Moondream** by default
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
- **Actuation**: `FUSED_APP` maps the profile to (light, fan, tv) on pins
  9/10/11 via `serial_actuator.py`.

| Profile | Meaning | light | fan | tv |
|---|---|---|---|---|
| T | transitional (standing / walking) | ON | off | off |
| A | active (sitting) | ON | ON | ON |
| B | resting (lying) | off | ON | off |
| C | unoccupied | off | off | off |

## VLM configurations
| | Qwen (`python live_system.py qwen`) | **Moondream (default)** |
|---|---|---|
| model | `qwen3-vl:4b`, thinking off | `moondream`, 60-token cap |
| prompt | one letter + phone flag | "Describe the people in this image." + word-boundary keywords |
| labelled set (12) | 12/12 | 12/12 |
| latency | ~20 s offline, ~12-19 s live | 0.82 s offline, 1.87 s live |
| confirms presence | no (too slow) | yes, 10 s window |
| leaving -> C | 8 s, or never if pose sees phantoms | 10-18 s |

## Hardware
- Board: Arduino UNO, port `/dev/cu.usbmodem1201`, FQBN `arduino:avr:uno`.
- Toolchain: `arduino-cli` (no IDE); Rosetta 2 required for the AVR toolchain.
- Wiring: pin 9 / 10 / 11 -> 1 kOhm -> LED long leg; short leg -> Arduino GND.
  Logically: pin 9 = light, 10 = fan, 11 = tv.
- Firmware: `arduino/power_leds` reads `"a,b,c\n"` at 9600 baud.

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
arduino-cli compile --fqbn arduino:avr:uno arduino/power_leds
arduino-cli upload -p /dev/cu.usbmodem1201 --fqbn arduino:avr:uno arduino/power_leds
```

## Environment
- `venv` (Python 3.12): mediapipe 0.10.21, opencv 4.11.0, numpy 1.26.4,
  pyserial, ollama. Ollama 0.35.0 with `moondream`, `qwen3-vl:2b/4b/8b`.
- Cameras: index 0 MacBook webcam, index 1 iPhone 12 (pinned). iPhone 17
  ("Amvx") excluded.

## Session log
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
- **2026-11-13**: Integrated entrypoint `live_system.py`; LEDs relabelled per
  appliance; decision logging; Blender room model.
- **2026-11-12**: Qwen3-VL swap; dataset recaptured from the iPhone 12.
- **2026-11-11**: Camera-by-name selection, multi-pose passive, smoothing,
  low-light enhancement.
- **2026-11-10**: Arduino LED actuation built and wired (`HANDOFF.md`).

## Next
- **Build `web/dashboard.html`** served by state_server.py at `/` (login +
  live dashboard, local only). The decided backup. Just say go.
- app-monitor Phase 5 (Trials, the RO3 instrument) when back on it.
- For the viva: one network we control (hotspot/pocket router), both
  devices on it; demo needs no internet.
- RO3 trials and end-to-end response time.
