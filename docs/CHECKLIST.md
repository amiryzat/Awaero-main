# FYP Checklist

Vision-Based Smart Power Management. What is built vs what is not.
Last updated: 2026-11-15. Newest live-state pointer: `docs/RESUME.md`.

## Done

### Integrated system (`live_system.py`, the main entrypoint)
- [x] Five-layer pipeline end to end on the real iPhone 12 camera + Arduino
      (verified live, 2026-11-14, many runs)
- [x] **Layer 2 mode selection** - a hand raised ABOVE THE FACE enters ACTIVE;
      typing/resting hands stay PASSIVE. Compared against face landmarks, not
      the box top (a raised arm stretched the box and blocked the near hand)
- [x] ACTIVE stays alive only while a gesture-shaped hand is visible, and drops
      back to PASSIVE after 6 s with no gesture. Every entry logged
      (`ACTIVE_ENTER`) + snapshotted. Final run: 10 activations, 10 real gestures
- [x] **Layer 4 fusion (settled by evidence)** - pose = PRESENCE only, VLM =
      POSTURE (T/A/B). With no VLM answer yet the profile is HELD, never guessed
      (pose guessing made the LEDs switch twice per event)
- [x] Presence hysteresis: `EMPTY_SECONDS=8` (leaning forward no longer drops
      the room to unoccupied)
- [x] **Per-appliance LEDs** - pin 9 light, 10 fan, 11 tv; `FUSED_APP` maps
      T/A/B/C to on/off vectors. Same 3-pin firmware, no reflash
- [x] **Gesture override** - per appliance (peace = light, open palm = TV, fist =
      all), held 60 s or until the room context changes, then automation resumes.
      Overlay shows `[MANUAL Ns]`
- [x] Decision logging (`live_log.csv`): profile changes, gestures, activations,
      and one row per VLM inference (latency stats not double-counted)
- [x] Annotated snapshot per decision (`snapshots/`), on-screen `HAND:` gate
      diagnostics and posture ratio
- [x] GPU contention fixed: detection at 960 px, pose every 2nd frame, display
      at full resolution, hands at full resolution (small far hands)

### Camera
- [x] `camera.py` PINNED to index 1 (iPhone 12), verified by
      `python camera.py probe`. system_profiler order proved unreliable (a whole
      run was recorded on the Mac webcam while the log said iPhone)
- [x] Refuses to fall back to the Mac webcam; 12 s warm-up for a waking iPhone

### Passive VLM
- [x] Qwen path: `qwen3-vl:4b`, thinking off (19.6 s -> 10.0 s, no accuracy
      loss), 640 px, 3 s cadence. ~12-19 s live
- [x] **Moondream (default engine, `moondream_vlm.py`)**: prompt
      "Describe the people in this image.", 60-token cap, word-boundary keyword
      matcher, phone flag read from the description, VLM confirms presence
      within 10 s (overrides pose phantoms). 68/70 on eye-checked frames at
      0.82 s; live 1.87 s mean; leaving -> C in 10-18 s. Every judged frame +
      description saved (`snapshots/vlm/`, `vlm_descriptions.csv`)
- [x] Model study written up: `docs/EVAL_passive_vlm.md` Runs 0-13

### Hardware / demo assets
- [x] Arduino UNO, 3 LEDs, `power_leds` firmware, `serial_actuator.py`
- [x] **Display node (2026-11-14):** second Arduino (black Techlympics Uno clone,
      CH340, `/dev/cu.usbserial*`) drives a 16x2 I2C LCD (GND/5V/A4/A5, address
      0x27). `arduino/display_node` firmware shows two lines sent by the Mac and
      says NO SIGNAL after 10 s of silence; `display_node.py` formats the state
      (`PASSIVE Sitting` / `L:ON F:ON TV:ON`) and `live_system.py` sends it.
      Needs a DATA micro-USB cable (the first cable was power-only)
- [ ] Run `live_system.py` with BOTH boards plugged in and confirm the screen
      follows the camera
- [ ] 7-segment display: verified common anode (dot lit) but parked; the LCD
      replaced it (needs 4 wires instead of 8)
- [ ] LED board GND shortage: all 3 GND holes used; build a ground rail on the
      big breadboard when the extra wires arrive
- [x] 3D room model in Blender (`blender/room_model.py`): open-front cutaway,
      roof, ceiling fan, 2 lamps, wall AC, desk + laptop, TV facing the bed

## Not done

### Decisions (Amir has full control over these)
- [x] **Passive engine: Moondream** (decided 2026-11-14). Default in
      `live_system.py` via `moondream_vlm.py`; Qwen kept as
      `python live_system.py qwen`. Both 12/12 on the labelled set; Moondream
      ~0.8 s vs Qwen ~20 s, confirms presence, and is the model Chapter 3 specifies
- [ ] Present the fusion honestly in Chapter 3: pose = presence, VLM = posture
      (draft text in `docs/VLM_vs_Pose.md`)
- [ ] 4th appliance (AC) and a 4th status LED for presence (empty room = all
      LEDs off, which looks the same as "system off")
- [ ] Relay showpiece - LOW-VOLTAGE load only, never mains

### Dashboard / app (next phase)
- [ ] App reads `live_log.csv` and shows live profile, appliance states, VLM
      latency, accuracy (scaffolded in `app-monitor/`; Dr. Zaaba approved it for
      RO3)

### Evaluation (RO3)
- [ ] >=10 trials per response path (>=70 data points); current sets are
      3/profile labelled + ~70 eye-checked live frames
- [ ] End-to-end response time per transition (camera -> LED), per mode
- [ ] Report Simulated Appliance Activation Reduction (exact mandated term)
- [ ] Gesture accuracy table (3 gestures x >=10 trials)

### Demo build
- [ ] Physical cardboard model house with the LEDs as labelled appliances
- [ ] LEDs extended off the breadboard on jumper wires (m-f, on order)

### Writing
- [ ] Chapter 3: align to the settled fusion and the chosen VLM
- [ ] Chapter 4 (results) - numbers are in `docs/EVAL_passive_vlm.md`
- [ ] Chapter 5 (conclusion / future work: IR camera for darkness, depth for
      posture, room ROI to exclude the hallway)

## Known limitations (be ready for Q&A)
- Pose posture is unusable in this room (three methods failed; ranges overlap),
  which is why posture is the VLM's job
- Pose produces phantom people on furniture with full confidence; presence needs
  the VLM's confirmation
- The camera sees down the hallway, so a person there counts as occupied
- A hand resting on top of the head can enter ACTIVE (2 of 7 activations in
  Run 14). Harmless: no appliance changes without a completed gesture, and it
  returns to PASSIVE after 6 s
- Pitch-black rooms: a visible-light camera cannot see; IR is the production fix
