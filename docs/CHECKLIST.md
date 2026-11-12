# FYP Checklist

Vision-Based Smart Power Management. What is built vs what is not.
Last updated: 2026-11-11.

## Done

### Detection
- [x] Passive mode: MediaPipe multi-person pose, real-time (`live_passive.py`)
- [x] Posture classification: upright vs lying from torso angle
- [x] Power tiers: A upright (green), B lying (yellow), C nobody (red)
- [x] "Highest tier wins" policy for multiple people
- [x] Flicker smoothing (temporal hysteresis / window vote)
- [x] Low-light rescue (CLAHE + gamma for dim rooms)
- [x] Active mode: MediaPipe Hands, 3 gestures (`live_active.py`)
- [x] Gesture gates (upright + consistency + hold + re-arm) to stop accidental toggles
- [x] Camera selected by name, survives index reshuffles (`camera.py`)

### Hardware
- [x] Arduino UNO flashed with `power_leds` firmware (arduino-cli)
- [x] 3 LEDs wired (pin 9/10/11 = green/yellow/red)
- [x] Serial actuation driver (`serial_actuator.py`), auto-finds port, mock fallback
- [x] Actuation linked into both live scripts

### Offline / evaluation artifacts
- [x] Moondream VLM classifier kept as offline evaluator (`classify_passive.py`)

## Not built yet

### System integration
- [x] **Mode Selection layer (Layer 2) in code** - `live_system.py` auto-switches:
      MediaPipe Hands as router (hand -> active, no hand -> passive). Router logic
      self-tested (`python live_system.py selftest`). Live loop needs camera+board.
- [x] Single entrypoint (`live_system.py`) running passive by default, hand = active
- [ ] Run `live_system.py` on the real camera + Arduino to confirm end to end
- [ ] Decide LED mapping: keep traffic-light tier (no code change) vs per-appliance
      light/TV/fan for the house (needs firmware + serial_actuator relabel)

### Demo build
- [ ] Cardboard model house with the 3 LEDs as labelled appliances
- [ ] LEDs extended off the breadboard on jumper wires

### Evaluation (RO3)
- [x] Recapture a labelled dataset from the final camera position (iPhone 12 room
      scene, 3/profile; old Mac-webcam set archived in frames/old_macwebcam/)
- [x] VLM swapped Moondream2 -> qwen3-vl:8b, direct 1-letter prompt. Accuracy +
      latency recorded in docs/EVAL_passive_vlm.md (100% @ 15.4s/frame on new set)
- [ ] Scale dataset to >=10 trials/response (>=70 data points) for formal RO3
- [ ] Run the POSE engine on the same new dataset (pose-vs-VLM comparison)
- [ ] Test latency lever: downscale frame (~640px) before the VLM
- [ ] Report Simulated Appliance Activation Reduction (exact mandated term)
- [ ] Report latency (per mode: active vs passive)

### Writing
- [ ] Align Chapter 3 to the VLM-vs-pose decision (see Open decisions)
- [ ] Chapter 4 (results)
- [ ] Chapter 5 (conclusion / future work)

## Open decisions (not mine to make - decide with Dr. Zaaba)
- [ ] VLM vs pose for the documented passive engine: keep VLM / switch to pose /
      present both. Demo is pose, Chapter 3 says VLM. An examiner will catch the
      mismatch.
- [ ] Is Mode Selection documented as automatic or manual? Decides whether the
      missing auto-switch above must be built.

## Unclear / needs a line from Amir
- [ ] `app-monitor/` React Native + Expo app: what is it for? Signed scope says
      no mobile/web interface.
- [ ] The sleeping-in-the-dark test: did it work or surface a problem?
