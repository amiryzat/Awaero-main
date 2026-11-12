"""
Live active mode: real-time gesture recognition with deliberate triggering.

MediaPipe Hands (classic solutions API) tracks 21 landmarks at full framerate.
Three gestures control simulated appliances:

    open palm    -> toggle TV
    peace sign   -> toggle lights
    closed fist  -> all OFF override

Accidental toggles are prevented by four gates, applied in order:

    1. Upright gate  - the hand must be held up, facing the camera, fingers up.
                       A hand resting on the face or lying sideways is ignored,
                       because the finger-extension test only means anything on
                       an upright hand.
    2. Consistency   - the same gesture must appear for CONFIRM_FRAMES frames in
                       a row before it becomes a candidate (kills flicker from
                       passing hand movements).
    3. Hold          - the candidate must be held for HOLD_SECONDS before firing.
    4. Re-arm        - after firing, the system disarms until the hand returns to
                       neutral for REARM_SECONDS.

Appliance state is simulated and printed, ready for PySerial to the Arduino.

Keys:
    q  quit

Usage:
    python live_active.py
"""

import time
from collections import deque

import cv2
import mediapipe as mp

from serial_actuator import Actuator
import camera

CAMERA_INDEX = camera.find_index()   # finds the iPhone by name (see camera.py)
CONFIRM_FRAMES = 3      # consecutive frames a gesture must agree to count
HOLD_SECONDS = 1.0      # how long the candidate must be held to fire
REARM_SECONDS = 0.4     # neutral time before a new command can fire
UPRIGHT_MARGIN = 0.05   # how far the knuckles must sit above the wrist (0-1)

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

FINGERS = {
    "index": (8, 6),
    "middle": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}

GESTURE_LABEL = {
    "open_palm": "OPEN PALM -> TV",
    "peace": "PEACE -> lights",
    "fist": "FIST -> all OFF",
    "none": "(no gesture)",
}


def hand_is_upright(lm):
    """True when the hand is held up, fingers pointing up, facing the camera.

    The knuckle row (index, middle, pinky MCPs) must sit clearly above the
    wrist in the image. This rejects sideways, downward and resting hands, for
    which the finger-extension test is meaningless.
    """
    wrist_y = lm[0].y
    knuckles_y = (lm[5].y + lm[9].y + lm[17].y) / 3.0
    return knuckles_y < wrist_y - UPRIGHT_MARGIN


def fingers_up(lm):
    return {name: lm[tip].y < lm[pip].y for name, (tip, pip) in FINGERS.items()}


def classify_gesture(lm):
    if not hand_is_upright(lm):
        return "none"
    up = fingers_up(lm)
    count = sum(up.values())
    if count == 0:
        return "fist"
    if count == 4:
        return "open_palm"
    if up["index"] and up["middle"] and not up["ring"] and not up["pinky"]:
        return "peace"
    return "none"


def apply(gesture, tv_on, lights_on):
    if gesture == "open_palm":
        tv_on = not tv_on
        print(f"TV toggled -> {'ON' if tv_on else 'OFF'}")
    elif gesture == "peace":
        lights_on = not lights_on
        print(f"Lights toggled -> {'ON' if lights_on else 'OFF'}")
    elif gesture == "fist":
        tv_on, lights_on = False, False
        print("ALL OFF override")
    return tv_on, lights_on


def led_state(tv_on, lights_on):
    """2 appliances -> 3-level LED: both on=GREEN, one=YELLOW, none=RED."""
    on = int(tv_on) + int(lights_on)
    return (1, 0, 0) if on == 2 else (0, 1, 0) if on == 1 else (0, 0, 1)


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {CAMERA_INDEX}.")

    act = Actuator()            # board, or mock mode if unplugged

    tv_on = False
    lights_on = False
    act.set(*led_state(tv_on, lights_on))   # start all OFF -> RED

    recent = deque(maxlen=CONFIRM_FRAMES)   # for the consistency gate
    armed = True
    candidate = "none"
    hold_start = 0.0
    none_start = None

    print("Live active mode (deliberate gesture control).")
    print(f"Hold a gesture UPRIGHT for {HOLD_SECONDS}s to fire. Drop hand to re-arm.")
    print("open palm = TV, peace = lights, fist = all off. 'q' to quit.\n")

    with mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
    ) as hands:

        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            now = time.time()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            raw = "none"
            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0]
                mp_draw.draw_landmarks(
                    frame, hand, mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )
                raw = classify_gesture(hand.landmark)

            # Consistency gate: only a gesture seen CONFIRM_FRAMES in a row counts.
            recent.append(raw)
            if len(recent) == CONFIRM_FRAMES and len(set(recent)) == 1:
                stable = recent[0]
            else:
                stable = "none"

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
                    candidate = stable
                    hold_start = now
                else:
                    held = now - hold_start
                    progress = min(held / HOLD_SECONDS, 1.0)
                    if armed and held >= HOLD_SECONDS:
                        tv_on, lights_on = apply(stable, tv_on, lights_on)
                        act.set(*led_state(tv_on, lights_on))
                        armed = False
                        candidate = "none"

            # Overlay: show the stabilized gesture, not the raw per-frame read.
            cv2.putText(frame, GESTURE_LABEL[stable], (15, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            status = "READY" if armed else "drop hand to reset"
            status_color = (0, 255, 0) if armed else (0, 165, 255)
            cv2.putText(frame, status, (15, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
            state = f"TV: {'ON' if tv_on else 'OFF'}   Lights: {'ON' if lights_on else 'OFF'}"
            cv2.putText(frame, state, (15, 125),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
            if progress > 0 and armed:
                bar_w = int(300 * progress)
                cv2.rectangle(frame, (15, 145), (315, 165), (80, 80, 80), 1)
                cv2.rectangle(frame, (15, 145), (15 + bar_w, 165), (0, 255, 0), -1)

            cv2.imshow("live active mode", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if ord("0") <= key <= ord("9"):   # switch camera live (Amvx excluded)
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


if __name__ == "__main__":
    main()
