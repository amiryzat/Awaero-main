"""
Live passive mode — multi-person, real-time, pose-based, flicker-smoothed.

Every frame, MediaPipe's multi-pose model finds all people; each person's
posture (upright/active vs lying/resting) is read from body geometry. The room
runs at the power level of the MOST ACTIVE person ("highest tier wins").

Flicker control: per-frame posture from 2D pose is noisy (a reclining person's
torso can look vertical; overlapping bodies blink in and out of detection). So
the LED is NOT driven by the raw per-frame call. Instead we keep the room
profile over a short time WINDOW and only switch when a new profile holds a
clear majority of that window (hysteresis). Ambiguous flicker -> the light
holds steady. This window also absorbs brief exits (no separate grace timer).

Why not the Moondream VLM here: single-person, ~1s/call, and it hallucinated
people from chairs. (The VLM pipeline still lives in classify_passive.py.)

Keys:  q quit   0/1/... switch camera (Amvx excluded)

Usage:  python live_passive.py
"""

import math
import os
import time
from collections import deque, Counter

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from serial_actuator import Actuator
import camera

CAMERA_INDEX = camera.find_index()   # finds the iPhone by name (see camera.py)

# --- posture (per person, per frame) ---
LYING_ANGLE = 45        # torso axis >this many deg from vertical => lying

# --- low-light rescue: brighten dark frames so pose can still see a person ---
DARK_MEAN = 60          # frame avg brightness (0-255) below this => enhance
_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
_gamma = [min(255, int((i / 255) ** 0.5 * 255)) for i in range(256)]  # <1 => brighter
import numpy as np
_gamma_lut = np.array(_gamma, dtype="uint8")

# --- temporal smoothing (what actually drives the LED) ---
SMOOTH_SECONDS = 1.5    # decision window; also the de-facto grace for exits
SWITCH_RATIO = 0.60     # a new profile needs this share of the window to win
MIN_VOTES = 5           # ...and at least this many frames, so we never flip on a blip

MODEL = os.path.join(os.path.dirname(__file__), "models", "pose_landmarker_full.task")

PROFILE_NAMES = {
    "A": "active (someone upright)",
    "B": "resting (all lying)",
    "C": "unoccupied",
}
ACTUATION = {
    "A": "lights ON, appliances ON (active use)",
    "B": "lights DIM, appliances STANDBY (resting)",
    "C": "all OFF (unoccupied)",
}
LED = {
    "A": (1, 0, 0),   # someone active   -> GREEN
    "B": (0, 1, 0),   # everyone resting -> YELLOW
    "C": (0, 0, 1),   # nobody           -> RED
}

_det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=MODEL),
    running_mode=vision.RunningMode.VIDEO,
    num_poses=4,
    min_pose_detection_confidence=0.5,   # 0.4 made the full model hallucinate poses in empty frames
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
))


def enhance_if_dark(frame):
    """Brighten a dark frame (CLAHE + gamma) so pose can detect; pass bright frames through."""
    if cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() >= DARK_MEAN:
        return frame
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    out = cv2.cvtColor(cv2.merge((_clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)
    return cv2.LUT(out, _gamma_lut)


def posture_of(lms, w, h):
    """'upright' or 'lying' from the torso-axis angle (shoulders -> hips)."""
    sx = (lms[11].x + lms[12].x) / 2 * w
    sy = (lms[11].y + lms[12].y) / 2 * h
    hx = (lms[23].x + lms[24].x) / 2 * w
    hy = (lms[23].y + lms[24].y) / 2 * h
    angle = math.degrees(math.atan2(abs(sx - hx), abs(sy - hy)))   # 0=vertical, 90=flat
    return "lying" if angle >= LYING_ANGLE else "upright"


def bbox_of(lms, w, h, pad=20):
    xs = [lm.x * w for lm in lms]
    ys = [lm.y * h for lm in lms]
    return (max(int(min(xs)) - pad, 0), max(int(min(ys)) - pad, 0),
            min(int(max(xs)) + pad, w), min(int(max(ys)) + pad, h))


def analyse(frame, ts_ms):
    """Return (per_frame_label, people). label: A any upright, B any lying, C empty."""
    h, w = frame.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                      data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    res = _det.detect_for_video(mp_img, ts_ms)
    people = []
    for p in res.pose_landmarks:
        people.append((bbox_of(p, w, h), posture_of(p, w, h)))
    if not people:
        return "C", people
    postures = [post for _, post in people]
    return ("A" if "upright" in postures else "B"), people


def main():
    _act = Actuator()
    _act.set(*LED["C"])

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {CAMERA_INDEX}.")

    print(f"Live passive mode (multi-person, smoothed) on camera {CAMERA_INDEX}.")
    print("Most-active-person wins. Press 'q' to quit.\n")

    window = deque()        # (timestamp, per_frame_label)
    committed = "C"
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame_idx += 1
        frame = enhance_if_dark(frame)   # rescue dark rooms before detection + display

        label, people = analyse(frame, frame_idx * 33)   # ts must strictly increase
        now = time.time()

        # Slide the window and vote with hysteresis.
        window.append((now, label))
        while window and now - window[0][0] > SMOOTH_SECONDS:
            window.popleft()
        counts = Counter(l for _, l in window)
        cand, votes = counts.most_common(1)[0]
        if (cand != committed and votes >= MIN_VOTES
                and votes >= SWITCH_RATIO * len(window)):
            committed = cand
            print(f"[{time.strftime('%H:%M:%S')}] -> {committed}: {ACTUATION[committed]}")
            _act.set(*LED[committed])

        # Draw every person's box + posture.
        for (x1, y1, x2, y2), post in people:
            color = (0, 255, 0) if post == "upright" else (0, 200, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, post, (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.putText(frame, f"{committed}: {PROFILE_NAMES[committed]}  ({len(people)} ppl)",
                    (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
        cv2.putText(frame, ACTUATION[committed], (15, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("live passive mode", frame)

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

    _act.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
