# FYP hardware handoff (for Claude Code in the Mac terminal)

> **STATUS: COMPLETE (historical).** All 5 steps below are done. Hardware
> actuation is wired and working. For the current project state, the live-mode
> design, tunables, and known limitations, see **`PROGRESS.md`** — that is the
> live tracker. This file is kept only as the original hardware setup record.
> Note: it still says 220 Ω / breadboard GND rail; the build actually used the
> kit's 1 kΩ resistors with LED cathodes straight to the Arduino GND pins.

Vision-Based Smart Power Management System. The software detection is done;
this handoff covers the Arduino actuation only. Run these in Claude Code
opened in `~/fyp-prototype`, because that shell runs on the real Mac (this
project was built in the Claude desktop app, whose sandbox cannot reach the
Mac's USB or serial ports).

## Project state (done)
- Passive mode: `live_passive.py` (Moondream2 via Ollama, four profiles
  T/A/B/C, presence gate + debounce). Works.
- Active mode: `live_active.py` (MediaPipe Hands, 3 gestures, upright + hold +
  re-arm gates). Works.
- Env: `venv` (Python 3.12). mediapipe 0.10.21, opencv 4.11, numpy 1.26,
  pyserial, ollama. Camera is iPhone Continuity Camera at index 1.

## What's left (this handoff)
1. Confirm the board, 2. upload blink test, 3. wire 3 LEDs, 4. upload real
firmware, 5. wire `serial_actuator.py` into the live scripts.

## Wiring (3 LEDs)
Each LED: digital pin -> 220 ohm resistor -> LED long leg (anode);
LED short leg (cathode) -> breadboard GND rail. Arduino GND -> GND rail.
    pin 9  -> GREEN    pin 10 -> YELLOW    pin 11 -> RED

## Step 1 - confirm the board
Plug the Arduino into the Mac (USB-B cable through the USB-C hub), then:
    ls /dev/cu.*
Expect a new `cu.usbmodem*` or `cu.usbserial*`. Note it as PORT.

## Step 2 - install arduino-cli and upload the blink test
    brew install arduino-cli
    arduino-cli core update-index
    arduino-cli core install arduino:avr
    arduino-cli board list                       # confirm PORT and FQBN
    arduino-cli compile --fqbn arduino:avr:uno arduino/blink_test
    arduino-cli upload -p <PORT> --fqbn arduino:avr:uno arduino/blink_test
The onboard LED (pin 13) should blink even with nothing wired. That proves
the upload path. If the board is a CH340 clone, FQBN is still arduino:avr:uno;
if upload fails with a port error, try the other `cu.*` entry.

## Step 3 - wire the 3 LEDs (see Wiring above), then watch the blink test
GREEN, YELLOW, RED should flash in sequence.

## Step 4 - upload the real firmware
    arduino-cli compile --fqbn arduino:avr:uno arduino/power_leds
    arduino-cli upload -p <PORT> --fqbn arduino:avr:uno arduino/power_leds
Then test the serial link from the venv:
    source venv/bin/activate
    python serial_actuator.py        # cycles the 3 LEDs once

## Step 5 - connect actuation to the live detection
`serial_actuator.py` exposes `Actuator().set(green, yellow, red)` and
auto-finds the port (falls back to mock printing if no board). Suggested
passive mapping (3 power levels from 4 profiles):
    A (active)        -> set(1,0,0)   GREEN  = appliances ON
    T, B (standby)    -> set(0,1,0)   YELLOW = standby
    C (unoccupied)    -> set(0,0,1)   RED    = all off
Replace the MOCK_ACTUATION print in live_passive.py with an Actuator call.
Ask the main Claude chat to make that edit, or do it here.

## Notes
- Ollama runs as a brew service; start with `brew services start ollama` if
  passive mode throws a connection error.
- Do not run passive and active at once; they share the camera.
