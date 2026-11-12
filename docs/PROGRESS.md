# FYP Progress — Vision-Based Smart Power Management

Last updated: 2026-11-11

## Status: passive mode rebuilt as multi-person, pose-based, real-time

Detection + Arduino LED actuation both work. Passive mode was migrated from a
single-person VLM (Moondream) to **multi-person MediaPipe pose** this session,
plus camera selection, low-light rescue, and flicker smoothing.

## System overview
A webcam feeds two detection modes; each drives 3 status LEDs on an Arduino UNO
over USB serial (green / yellow / red = power tier). Run one at a time (they
share the camera).

- **Passive mode** (`live_passive.py`) — MediaPipe multi-pose finds everyone,
  classifies each person upright (active) vs lying (resting) from body geometry,
  and runs the room at the **most active person's** tier. Real-time, no VLM.
- **Active mode** (`live_active.py`) — MediaPipe Hands, 3 gestures toggle a
  simulated TV + lights, with upright/hold/re-arm gates.

## Power tiers (passive mode)
| Profile | Meaning | LED |
|---|---|---|
| A | someone upright (sitting/standing) | 🟢 GREEN — appliances ON |
| B | everyone present is lying/resting | 🟡 YELLOW — dim / standby |
| C | nobody detected | 🔴 RED — all off |

Policy: **highest tier wins** — one active person keeps the room green even if
others are lying down.

## Hardware
- Board: Arduino UNO, port `/dev/cu.usbmodem1201`, FQBN `arduino:avr:uno`.
- Toolchain: `arduino-cli` (no IDE). Apple Silicon AVR toolchain is x86_64, so
  **Rosetta 2 is required** (installed).
- Wiring: pin 9 → GREEN, pin 10 → YELLOW, pin 11 → RED. Each: digital pin →
  1 kΩ resistor → LED long leg; LED short leg → an Arduino GND pin.
- Firmware: `arduino/power_leds` — reads `"g,y,r\n"` over serial at 9600 baud.

## Key files
- `live_passive.py` — passive mode (multi-person pose, smoothing, low-light).
- `live_active.py` — active mode (MediaPipe Hands gestures).
- `camera.py` — picks the iPhone camera **by name** (survives index reshuffles).
- `serial_actuator.py` — `Actuator().set(green, yellow, red)`, auto-finds port,
  mock-prints if no board. Self-test: `python serial_actuator.py`.
- `classify_passive.py` — **offline** Moondream VLM evaluator (100% on labeled
  `frames/`). No longer in the live path; kept as the VLM evaluation artifact.
- `models/pose_landmarker_full.task` — multi-pose model used live (9.4 MB).

## How passive mode works now (detail)
1. **Camera** picked by name via `camera.py` (prefers "Amv Camera" = iPhone 12
   Pro; "Amvx" iPhone 17 is excluded). Live-switch with number keys 0/1/…
2. **Low-light rescue** — frames below avg brightness `DARK_MEAN` (60) are
   brightened (CLAHE + gamma) before detection so dim rooms still detect.
3. **Multi-pose** — up to `num_poses=4` people, each boxed; green box = upright,
   amber = lying.
4. **Posture** — torso axis angle (shoulders→hips): ≥ `LYING_ANGLE` (45°) from
   vertical = lying, else upright. Validated 12/12 on labeled frames.
5. **Room label per frame** — A if anyone upright, B if anyone lying, else C.
6. **Temporal smoothing (hysteresis)** — the LED follows a **1.5 s window
   vote**; a new profile must hold ≥ `SWITCH_RATIO` (60%) of the window and
   ≥ `MIN_VOTES` (5) frames to switch. Kills flicker; also cushions brief exits
   (no separate grace timer).

### Tunables (top of `live_passive.py`)
`LYING_ANGLE=45`, `SMOOTH_SECONDS=1.5`, `SWITCH_RATIO=0.60`, `MIN_VOTES=5`,
`DARK_MEAN=60`, detector `num_poses=4`.

## Known limitations (be ready for Q&A)
- **Pitch-black rooms**: a visible-light webcam can't see a person it can't
  capture; enhancement helps *dim* rooms, not full darkness. Honest options:
  (a) demo in a dim-but-not-black room, (b) frame red-in-the-dark as correct
  energy-off behavior, (c) production answer = IR/night-vision camera.
- **2D pose can't always separate lying-on-floor from sitting** when the camera
  is high and the torso looks vertical in-image. Smoothing keeps the LED stable;
  perfect separation would need a side angle or depth.
- **Overlapping bodies on the floor** can be merged/missed by MediaPipe.

## Run
```bash
source venv/bin/activate
python live_passive.py      # or live_active.py  (Arduino plugged in)
# keys: q quit | 0/1/... switch camera
```

## Re-flash firmware (only if changed)
```bash
arduino-cli compile --fqbn arduino:avr:uno arduino/power_leds
arduino-cli upload -p /dev/cu.usbmodem1201 --fqbn arduino:avr:uno arduino/power_leds
```

## Environment
- `venv` (Python 3.12): mediapipe 0.10.21, opencv 4.11.0, numpy 1.26.4, pyserial, ollama.
- Cameras: MacBook Air (index 0), iPhone 12 "Amv" (1), iPhone 17 "Amvx" (excluded).
- Ollama (for the offline `classify_passive.py` only): `brew services start ollama`.

## Session log
- **2026-11-11**: Camera-by-name selection (`camera.py`); live camera switch
  keys; passive mode moved Moondream → MediaPipe multi-pose; most-active-wins
  policy; posture via torso angle; temporal-smoothing hysteresis (fixed
  green/yellow flicker); low-light enhancement for dark rooms. Moondream kept
  as offline evaluator only.
- **2026-11-10**: Arduino LED actuation built, wired, and linked into both live
  scripts (original hardware handoff — see `HANDOFF.md`, now complete).

## Possible next work
- IR camera path for true darkness.
- Log state changes to a file / combined dashboard.
- Tune `LYING_ANGLE` / smoothing for the specific demo camera angle.
