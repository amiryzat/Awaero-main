# FYP Checklist

Vision-Based Smart Power Management. What is built vs what is not.
Last updated: 2026-11-17. Newest live-state pointer: `docs/RESUME.md`.

### Activity-based redesign (Phase 1, 2026-11-17) - the VLM A/B
- [x] `scene_activity.py` - description -> activity (STUDYING/RESTING/
      TRANSITIONAL/UNOCCUPIED) + at_desk flag; validated on 2000 real descriptions
- [x] `eval_two_models.py` - offline Moondream-vs-Qwen over the same frames,
      data-integrity check, findings + per-frame CSV. Method: `docs/EVAL_two_models.md`
- [x] Web **Capture tab**: capture labelled frames from the phone off the mounted
      camera (clean `live_raw.jpg`), review thumbnails + delete to fix labels
- [ ] Capture >=10 frames/activity, run the A/B, record the result in Chapter 4
- [ ] Wire the winning engine's activity->appliance logic (desk lamp at desk only)
- [ ] Gestures: point = desk lamp, rock = AC
- [ ] DHT22 temperature sensor -> AC on >27C (ordered)
- [ ] Tag trials by engine; two live runs (Moondream, Qwen) for live latency/accuracy

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
- [x] **Five appliance LEDs** (2026-11-16) - pin 9 light, 10 fan, 11 tv,
      8 desk lamp, 7 aircond; `FUSED_APP` maps T/A/B/C to 5-tuples. Firmware is
      `arduino/room_node.ino` (variadic CSV), uploaded. Holes in `docs/WIRING.md`
- [x] **Revised decision policy** (2026-11-16) from
      `FYP_Room_Activity_and_Appliance_Decision_Profiles.md`: sitting no longer
      turns the TV on, standing no longer turns the fan off (both pinned by
      selftest). "No change" rows use a HOLD sentinel (`resolve_hold`); T holds
      TV + AC. AC is an ASSUMED policy (no temp sensor), stated as such
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
- [x] Arduino UNO, 5 LEDs + LCD + stepper on `arduino/room_node.ino`, `serial_actuator.py` (variadic). `power_leds`/`display_node` sketches kept as history
- [x] **LCD on ONE Arduino with the LEDs (2026-11-16):** the 16x2 I2C LCD (0x27,
      GND->blue rail, VCC->red rail, SDA->A4, SCL->A5) runs on the SAME Uno as the
      5 LEDs via `arduino/room_node.ino` - no second board. Shows two lines sent
      by the Mac, NO SIGNAL after 10 s silence. `display_node.py` shares the
      actuator's open port (`LcdDisplay(ser=act.ser)`) and renders 5 appliances
      ("L+ F+ T- D+ A+") to fit 16 columns
- [x] **LCD "random symbols" RESOLVED (2026-11-16):** it was an UNINITIALISED
      screen, not a fault - the firmware hung in setup() probing a not-yet-wired
      LCD, so nothing drove any pin. Firmware now probes 0x27 and skips all LCD
      calls when absent, so the LEDs never hang. Verified writing text at 0x27
- [ ] 7-segment display: verified common anode (dot lit) but parked; the LCD
      replaced it (needs 4 wires instead of 8)
- [x] **Ground + 5V rails built (2026-11-16):** one Arduino GND -> blue (-) rail
      (every LED short leg + LCD GND return there); one 5V -> red (+) rail (LCD
      VCC). Solves the old 3-GND-hole shortage for 5 LEDs + LCD
- [~] **Stepper fan (PARKED):** 28BYJ-48 + ULN2003 wired as the physical fan on
      pins 2-5, spins non-blocking mirroring the fan value (commit 887bcec). But
      the geared motor tops out ~10-15 rpm - too slow. Being replaced by a fast
      DC motor (DC motor + fan blade + IRF520 MOSFET module), on order
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
- [x] **4th + 5th appliances DONE (2026-11-16):** desk lamp (pin 8) and aircond
      (pin 7) added, so 5 appliances total. (A presence status LED for "empty vs
      system off" is still optional, not done)
- [ ] Relay showpiece - LOW-VOLTAGE load only, never mains

### Dashboard / app (app-monitor, built through PRD Phase 4)
- [x] `state_server.py`: stdlib LAN bridge serving /state, /metrics, /history,
      /frame.jpg from `live_log.csv`; `--replay` fixture; `--selftest` (incl. the
      2026-11-15 midnight-parse fix). Runs on port 8000
- [x] app-monitor rebuilt on the real 4-profile model: Home, Live (pipeline +
      relayed camera feed), Stats (RO3 report), Controls. Installed on the iPhone 17
- [x] Auto-discovery: the app learns the Mac's IP + Bonjour name, races all known
      addresses each reconnect, self-recovers; Settings has a "Wireless check"
- [x] FYP latency instrumentation (`decide_latency_ms`, `actuate_latency_ms`) and
      the `live_frame.jpg` camera relay are wired into `live_system.py`
- [x] **Phase 5 Trials - BUILT (2026-11-15).** The RO3 instrument lives in the web
      dashboard (Trials tab) + `state_server.py` (POST/GET/DELETE /trials, live
      accuracy in /metrics, `trials.csv`). You declare the ground truth, the server
      snapshots its own live decision and scores it; a capture countdown lets you
      get into B (lying) / C (leaving) before the trial fires. First real run:
      **73 trials, 94.5%** (T 11/11, A 9/10, B 8/10, C 10/10)
- [x] **Local web dashboard - BUILT (2026-11-15).** React+Vite "Awaero", served at
      `/` by `state_server.py` from `dist/` (login gate + Home/Live/Stats/Trials),
      follows the reference UI. Runs in the Mac's browser and the phone browser
      (reached the Mac at 192.168.0.16:8000 over the phone this session)
- [x] **Dashboard UI pass (2026-11-15 night).** Web-first sidebar layout, rubber
      mobile nav, Stats Session timeline + Accuracy by response path, hybrid
      restyle to `DESIGN.md` (monochrome chrome, profile/status colours kept),
      borderless soft-shadow cards. No new runtime dependencies. Departures from the
      spec: `web-dashboard/PRD.md` Section 11
- [x] **Awaero phone app - BUILT (2026-11-16).** `awaero-app/`, a copy of
      app-monitor that leaves the old app alone (`com.amiryzat.awaero`, both on the
      iPhone 17). Five appliances, a Trials tab on the same `trials.csv`, real trial
      accuracy on Stats. Simulator-tested, then installed. See `awaero-app/PROGRESS.md`
- [x] Phone camera feed fixed: `state_server.py` sent `no-store` on the frame, which
      React Native refuses; frames are `no-cache` now
- [ ] Record a trial from the phone on real hardware (only simulator-tested so far)
- [ ] Decide which tab owns per-path accuracy (it shows on both Stats and Trials)
- [ ] Manual override (Controls -> `override.json` -> system), PRD Phase 6-7.
      Controls tab is still read-only

### Fixes from the 2026-11-15 live run - ALL DONE + VALIDATED (2026-11-15 late)
- [x] **1. Posture debounce.** Root cause was subtler: the 4 s vote window smooths
      POSE frames, but one VLM read floods it in ~1 s so it never damped the VLM.
      Fix debounces the VLM READ SEQUENCE (`debounce_vlm`, `POSTURE_DEBOUNCE_N=2`).
      Validated: A 90->100%, B 80->100%. Cost: T ~1 read slower (documented)
- [x] **2. Fist "leaving" latch** (`leave_target` + `leaving_latch`). All-off until
      the room empties (C) or ANY gesture cancels it. Fist sets no per-appliance
      holds now (`GESTURE_HOLDS["fist"]=[]`) so a "changed my mind" gesture fully
      resumes auto (fan/TV no longer stuck off ~60 s). Confirmed `fist->PASSIVE A`
      stayed 0,0,0 in `live_log.csv`
- [x] **3. PASSIVE row on ACTIVE->PASSIVE return.** Confirmed a PASSIVE row logs
      ~3 s after every ACTIVE; app/LCD no longer freeze on ACTIVE
- [ ] Cosmetic (not decision-affecting): pose phantom box parks on the clothes rail
      when you lie down (VLM still gives the right B); pose "0 ppl" when an arm is
      raised. Known limitations, document for Q&A, no fix needed

### Evaluation (RO3)
- [x] **>=10 trials per response path - DONE twice.** BEFORE (73, 94.5%):
      `archive/trials_before_debounce_2026-11-15.csv`. AFTER the fixes (77, 89.6% raw;
      98.0% once timing settled): `trials.csv`. Per-path after: A 11/11, B 10/10 (both
      100%), C 9/10, T 9/12 (misses front-loaded while learning the debounce lag)
- [x] **Gesture accuracy - DONE (>=10 each).** open_palm 12/12 (100%), peace 9/12,
      fist 9/10 - in `trials.csv`. Early peace/fist misses were gesture-registration
      while learning, not the posture path
- [~] End-to-end response time per transition (camera -> LED): each trial row now
      carries `vlm_latency_s` (detection) + `decide_latency_ms` + `actuate_latency_ms`;
      decide ~24 ms p50, actuate ~0.1 ms, VLM ~1.4-1.9 s. Still need the
      per-transition camera->LED wall-clock table
- [ ] Report Simulated Appliance Activation Reduction (exact mandated term) - the
      dashboard shows it live (15.6% last window); pull the final number for Ch 4

### Demo build
- [ ] Physical cardboard model house with the LEDs as labelled appliances
- [ ] LEDs extended off the breadboard on jumper wires (m-f, on order)
- [ ] Wireless phone<->Mac for the viva: bring ONE network we control (hotspot or
      pocket router). The borrowed WiFi isolates clients (two APs share one SSID)
      so the phone cannot reach the Mac on it; the USB cable works meanwhile. Not
      a code bug, not our router to change (diagnosed 2026-11-15)

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
- ~20 s to confirm UNOCCUPIED is DELIBERATE (`EMPTY_SECONDS` hysteresis), not lag -
  it stops a brief step-out blacking the room and re-powering appliances
- A person BENT OVER the desk can read as A (sitting) then self-correct to T: standing
  vs sitting when bent forward is genuinely ambiguous from one camera. The debounce
  cut the flicker; the residual case is a documented VLM limitation, not a bug
