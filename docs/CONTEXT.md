# FYP Context — for a new chat

Read this plus `PROGRESS.md` to continue without re-reading the old chat.
`PROGRESS.md` = technical build state. This file = decisions, rationale, and
the open questions.

## The project
- Title: Context-Aware Vision-Based Smart Power Management System for
  Room-Level Energy Optimisation Based on Activity Detection.
- Final-year CS project, UiTM. Studies finish ~Feb 2027. Viva ahead.
- Supervisor: Ts Dr. Zaaba. Scope is locked by signed documentation
  (single node, single room, no mobile/web interface). Changes that contradict
  the signed scope need his sign-off.
- Dual-mode system over a 5-layer architecture
  (Perception -> Pre-Processing/Mode Selection -> Inference -> Decision ->
  Actuation), ending at USB/PySerial to an Arduino. No networking layer.
  - Passive: scene/posture -> 4 energy profiles: T (transitional/standing),
    A (active sitting), B (resting), C (unoccupied).
  - Active: hand gestures -> open palm = TV, peace = lights, fist = all-off.

## Current state (2026-11-10)
- Both modes work. Hardware actuation done: Arduino UNO, 3 LEDs
  (pin 9 green / 10 yellow / 11 red), flashed via arduino-cli, driven over
  serial by `serial_actuator.py`. See PROGRESS.md for wiring and commands.
- Camera: `camera.py` selects by NAME (iPhone "Amv Camera"), not a fixed
  index, which fixed the Continuity Camera index reshuffle.

## THE OPEN DECISION (most important)
`live_passive.py` was rewritten to use **MediaPipe Pose** (multi-person,
real-time, 2D skeleton -> posture), NOT the Moondream2 VLM. The VLM pipeline
still exists in `classify_passive.py`.
- Pro: fixes VLM hallucination, removes the ~1s lag, and handles multiple
  people (matters because the viva room will have other presenters).
- Problem: the WRITTEN methodology (Chapter 3, system design, RO2) specifies
  Moondream2 as the passive engine. Demo-on-pose vs thesis-says-VLM is a
  mismatch an examiner will catch.
- Three options, user to decide WITH supervisor:
  1. Keep VLM as the documented system, demo that, pose = future work.
  2. Switch methodology to pose-based, revise Chapter 3, clear with Dr. Zaaba.
  3. Present both: VLM as designed, pose as an implemented improvement, with a
     comparison. Strongest thesis story, most writing.
- NOT yet decided. Do not pick one silently; surface it.

## Demo decisions already made
- Camera: follow the lecturer — static, body level, on a tripod. The elevated
  CCTV idea goes in Chapter 5 as future work.
- Multi-person room: frame the camera on a bounded zone (the user's area) so
  only the user is in scope. (Pose mode also handles multi-person directly.)
- Physical build: lecturer wants a model house with appliances. Plan: cardboard
  house, the 3 LEDs become labelled appliances, extended off the breadboard with
  female-to-male jumper wires (socket grips the LED leg, male into breadboard).
  No code change. Keep everything 5V/USB — never switch 240V mains. A relay +
  small 5V fan is optional and needs supervisor sign-off (scope change).
- VLM hallucination: present honestly as a known limitation with the two-stage
  presence-gate mitigation; don't claim perfection.

## Remaining work
- Decide the VLM-vs-pose fork (above) and align Chapter 3 to it.
- Build the model house and mount the 3 LEDs as appliances.
- Evaluation for RO3: recapture a labelled dataset from the final camera
  position, report accuracy + Simulated Appliance Activation Reduction + latency.
  (Note: the mandated metric term is "Simulated Appliance Activation Reduction";
  "energy saving performance" / "Simulated Energy Reduction" are banned.)
- Writing: Chapter 4 (results), Chapter 5 (conclusion/future work).

## How the user likes to work
- Direct, honest pushback over agreement. Hold firm recommendations; don't
  fold when scope shifts mid-task.
- Single clear next step over long walkthroughs; gets overwhelmed by big dumps.
- No em dashes. Raw code/files to copy over zip packages.
- The assistant edits files via the connected Mac folder; the user runs the
  camera/hardware (the assistant cannot see the live window or be the subject).
- Run scripts from the venv. One mode at a time (shared camera).

## Key files
- live_passive.py (pose-based now), classify_passive.py (VLM version),
  live_active.py (gestures), camera.py, serial_actuator.py,
  arduino/power_leds (firmware), PROGRESS.md (build detail), HANDOFF.md (older
  hardware handoff).
