"""
Live integrated system - the documented five-layer pipeline, end to end.

This is the single-entry dual-mode runtime described in Chapter 3. It does NOT
reimplement detection; it reuses the two engines already built and wires them
through the Pre-Processing / Mode Selection Layer (Layer 2):

    MediaPipe Hands is the router. Every frame:
      - a hand is detected  -> ACTIVE mode  (gesture control, from live_active)
      - no hand (grace)     -> PASSIVE mode (pose activity, from live_passive)

Only one mode owns the LEDs per frame (the two modes mean different things by
the same 3 LEDs, so running both at once would fight). Passive runs pose only
when idle (no hand), which is also the only time ambient classification is
wanted, so the heavy model runs exactly when the light one says to.

Note vs the thesis: the documented passive engine is Moondream2 (VLM). This
runtime uses the pose engine instead - the implemented improvement (real-time,
multi-person, no hallucination). See docs/VLM_vs_Pose.md. The VLM path still
lives in classify_passive.py as the designed baseline.

Keys:  q quit   0/1/... switch camera (Amvx excluded)
Usage: python live_system.py        (selftest: python live_system.py selftest)
"""

import sys
import time
from collections import deque, Counter

import cv2
import mediapipe as mp

from serial_actuator import Actuator
import camera

# Reuse both engines, no rewrite. Importing these runs their camera scan + loads
# the pose model (module-level in live_passive). ponytail: double camera scan at
# import (one per module); harmless, factor find_index into a cached call if slow.
from live_passive import (
    analyse, enhance_if_dark, LED, ACTUATION, PROFILE_NAMES,
    SMOOTH_SECONDS, SWITCH_RATIO, MIN_VOTES, CAMERA_INDEX,
)
from live_active import (
    classify_gesture, apply, led_state, GESTURE_LABEL,
    CONFIRM_FRAMES, HOLD_SECONDS, REARM_SECONDS,
)

PASSIVE_FALLBACK_SECONDS = 2.0   # no hand for this long -> drop back to passive

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


def decide_mode(current, hand_present, now, last_hand_time):
    """Layer 2 router. Hand -> ACTIVE at once; no hand past the grace -> PASSIVE;
    inside the grace the mode is held (stops flicker when detection blinks)."""
    if hand_present:
        return "ACTIVE"
    if now - last_hand_time > PASSIVE_FALLBACK_SECONDS:
        return "PASSIVE"
    return current


def main():
    act = Actuator()
    act.set(*LED["C"])                       # start all off -> RED

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {CAMERA_INDEX}.")

    print(f"Live integrated system on camera {CAMERA_INDEX}.")
    print("Show a hand = ACTIVE (gestures). No hand = PASSIVE (activity). 'q' quits.\n")

    mode = "PASSIVE"
    last_hand_time = 0.0
    pose_ts = 0                              # strictly-increasing ms for pose VIDEO mode

    # passive smoothing state (from live_passive)
    window = deque()
    committed = "C"

    # active gesture state (from live_active)
    tv_on = lights_on = False
    recent = deque(maxlen=CONFIRM_FRAMES)
    armed = True
    candidate = "none"
    hold_start = 0.0
    none_start = None
    stable = "none"
    progress = 0.0

    with mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7,
                        min_tracking_confidence=0.6) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            frame = enhance_if_dark(frame)   # rescue dark rooms (helps pose; harmless to hands)
            now = time.time()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hres = hands.process(rgb)
            hand_present = bool(hres.multi_hand_landmarks)
            if hand_present:
                last_hand_time = now

            prev_mode = mode
            mode = decide_mode(mode, hand_present, now, last_hand_time)

            if mode == "ACTIVE":
                raw = "none"
                if hand_present:
                    hand = hres.multi_hand_landmarks[0]
                    mp_draw.draw_landmarks(
                        frame, hand, mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style())
                    raw = classify_gesture(hand.landmark)

                recent.append(raw)
                stable = recent[0] if (len(recent) == CONFIRM_FRAMES
                                       and len(set(recent)) == 1) else "none"
                progress = 0.0
                if stable == "none":
                    candidate = "none"
                    if none_start is None:
                        none_start = now
                    elif now - none_start >= REARM_SECONDS:
                        armed = True
                else:
                    none_start = None
                    if stable != candidate:
                        candidate, hold_start = stable, now
                    else:
                        held = now - hold_start
                        progress = min(held / HOLD_SECONDS, 1.0)
                        if armed and held >= HOLD_SECONDS:
                            tv_on, lights_on = apply(stable, tv_on, lights_on)
                            act.set(*led_state(tv_on, lights_on))
                            armed, candidate = False, "none"

                if prev_mode != "ACTIVE":     # just entered -> show appliance state
                    act.set(*led_state(tv_on, lights_on))

            else:  # PASSIVE
                if prev_mode == "ACTIVE":     # just entered -> show the room tier
                    window.clear()
                    act.set(*LED[committed])
                pose_ts += 40
                label, people = analyse(frame, pose_ts)
                window.append((now, label))
                while window and now - window[0][0] > SMOOTH_SECONDS:
                    window.popleft()
                cand, votes = Counter(l for _, l in window).most_common(1)[0]
                if (cand != committed and votes >= MIN_VOTES
                        and votes >= SWITCH_RATIO * len(window)):
                    committed = cand
                    print(f"[{time.strftime('%H:%M:%S')}] passive -> {committed}: {ACTUATION[committed]}")
                    act.set(*LED[committed])
                for (x1, y1, x2, y2), post in people:
                    c = (0, 255, 0) if post == "upright" else (0, 200, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
                    cv2.putText(frame, post, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)

            # --- overlay: mode is front and center so the router is visible ---
            mcolor = (0, 200, 255) if mode == "ACTIVE" else (0, 255, 0)
            cv2.putText(frame, f"MODE: {mode}", (15, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, mcolor, 3)
            if mode == "ACTIVE":
                cv2.putText(frame, GESTURE_LABEL[stable], (15, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, f"TV: {'ON' if tv_on else 'OFF'}   Lights: {'ON' if lights_on else 'OFF'}",
                            (15, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
                if progress > 0 and armed:
                    cv2.rectangle(frame, (15, 130), (315, 150), (80, 80, 80), 1)
                    cv2.rectangle(frame, (15, 130), (15 + int(300 * progress), 150), (0, 255, 0), -1)
            else:
                cv2.putText(frame, f"{committed}: {PROFILE_NAMES[committed]}", (15, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, ACTUATION[committed], (15, 115),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("live integrated system", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if ord("0") <= key <= ord("9"):
                idx = key - ord("0")
                if idx not in camera.allowed_indices():
                    print(f"Camera index {idx} not available; staying put.")
                else:
                    cap.release()
                    cap = cv2.VideoCapture(idx)
                    print(f"Switched to camera index {idx}.")

    act.close()
    cap.release()
    cv2.destroyAllWindows()


def _selftest():
    """Router truth table: hand wins instantly; grace holds; timeout -> passive."""
    assert decide_mode("PASSIVE", True, 100.0, 0.0) == "ACTIVE"      # hand -> active
    assert decide_mode("ACTIVE", False, 100.0, 99.5) == "ACTIVE"     # within grace -> held
    assert decide_mode("ACTIVE", False, 103.0, 100.0) == "PASSIVE"   # past grace -> passive
    assert decide_mode("PASSIVE", False, 103.0, 100.0) == "PASSIVE"  # stays passive
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        main()
