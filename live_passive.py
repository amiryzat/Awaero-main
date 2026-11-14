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

# ponytail: the camera is resolved in main(), NOT at import. A module-level
# find_index() ran a full camera scan (and grabbed the device) on every import,
# including from live_system.py - which is why startup scanned twice.

# --- posture (per person, per frame) ---
LYING_ANGLE = 45        # torso axis >this many deg from vertical => lying
# Hips must be at least this visible before we are willing to say "lying".
# 0.5 sat right on the boundary for someone seated at a desk: visibility hovered
# around it and the posture oscillated upright/lying frame to frame, flipping the
# room between A and B 11 times in 70 seconds. 0.7 means we only claim lying when
# the hips are genuinely seen (a person on a bed), and default to upright
# otherwise, letting the VLM split T vs A.
MIN_VISIBILITY = 0.7
# Body vertical extent divided by shoulder width. Dividing by shoulder width
# makes it independent of how far away the person is. Standing with the legs in
# view runs about 5-7; seated (especially with the legs hidden by a desk) about
# 2.5-3.5. This lets POSE tell standing from sitting instantly, instead of
# calling everything "upright" and waiting ~20 s for the VLM to split T from A -
# which made the LEDs switch twice for one event.
STAND_RATIO = 4.0
DUP_OVERLAP = 0.6       # a box this contained within another is the same person

# --- low-light rescue: brighten dark frames so pose can still see a person ---
DARK_MEAN = 60          # frame avg brightness (0-255) below this => enhance
_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
_gamma = [min(255, int((i / 255) ** 0.5 * 255)) for i in range(256)]  # <1 => brighter
import numpy as np
_gamma_lut = np.array(_gamma, dtype="uint8")

# --- temporal smoothing (what actually drives the LED) ---
SMOOTH_SECONDS = 4.0    # decision window; also the de-facto grace for exits
                        # (1.5s was too short: a person intermittently lost or
                        # re-postured flipped the LEDs every couple of seconds)
SWITCH_RATIO = 0.60     # a new profile needs this share of the window to win
MIN_VOTES = 5           # ...and at least this many frames, so we never flip on a blip

MODEL = os.path.join(os.path.dirname(__file__), "models", "pose_landmarker_full.task")

PROFILE_NAMES = {
    "T": "transitional (someone standing)",
    "A": "active (someone sitting)",
    "B": "resting (all lying)",
    "C": "unoccupied",
}
ACTUATION = {
    "T": "light ON, other appliances OFF (passing through)",
    "A": "lights ON, appliances ON (active use)",
    "B": "lights DIM, appliances STANDBY (resting)",
    "C": "all OFF (unoccupied)",
}
LED = {
    "T": (1, 1, 0),   # someone standing -> GREEN+YELLOW
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
    """'upright' or 'lying' from the torso-axis angle (shoulders -> hips).

    Guarded by hip VISIBILITY. Sitting at a desk hides the hips behind the table,
    so MediaPipe guesses landmarks 23/24, the torso axis comes out near-horizontal
    and a seated person is reported as 'lying' (observed 2026-11-14: both boxes
    on a man typing at his desk were labelled lying, and the room dropped to B).
    If the hips are not actually seen we do NOT claim lying; we say upright and
    let the VLM settle T vs A, which it does correctly.
    """
    # Hip visibility gates only the LYING claim: with the hips hidden behind a
    # desk the torso axis is guesswork and a seated person reads as lying.
    # returns (posture, ratio); ratio is the standing/sitting measure, 0 if lying
    if min(getattr(lms[23], "visibility", 1.0),
           getattr(lms[24], "visibility", 1.0)) >= MIN_VISIBILITY:
        sx = (lms[11].x + lms[12].x) / 2 * w
        sy = (lms[11].y + lms[12].y) / 2 * h
        hx = (lms[23].x + lms[24].x) / 2 * w
        hy = (lms[23].y + lms[24].y) / 2 * h
        angle = math.degrees(math.atan2(abs(sx - hx), abs(sy - hy)))  # 0=vert, 90=flat
        if angle >= LYING_ANGLE:
            return "lying", 0.0

    # standing vs sitting from how tall the body is relative to the shoulders.
    # The ratio is RETURNED so it can be shown on screen and logged: STAND_RATIO
    # has been guessed wrong twice, so it gets calibrated from real numbers.
    seen = [lm for lm in lms if getattr(lm, "visibility", 1.0) >= 0.5]
    shoulder_w = abs(lms[11].x - lms[12].x) * w
    ratio = 0.0
    if len(seen) >= 8 and shoulder_w > 0:
        ratio = ((max(l.y for l in seen) - min(l.y for l in seen)) * h) / shoulder_w
    return ("standing" if ratio >= STAND_RATIO else "sitting"), ratio
    # ponytail: a foreshortening cue (torso shorter than shoulder width => lying
    # towards the camera) was tried and REMOVED on 2026-11-14. Leaning forward
    # over a laptop compresses the torso identically, so it reported a man typing
    # at his desk as lying and flipped the room A<->B every few seconds. 2D
    # geometry cannot separate those two poses; the VLM can, and does it on the
    # slow path. Do not reintroduce it without a depth cue.


def bbox_of(lms, w, h, pad=20):
    xs = [lm.x * w for lm in lms]
    ys = [lm.y * h for lm in lms]
    return (max(int(min(xs)) - pad, 0), max(int(min(ys)) - pad, 0),
            min(int(max(xs)) + pad, w), min(int(max(ys)) + pad, h))


def _overlap(a, b):
    """Intersection as a fraction of the SMALLER of two (x1,y1,x2,y2) boxes.

    Deliberately NOT IoU: the duplicate we actually see is a head-only box nested
    inside a full-body box, which scores just ~0.38 IoU because the areas differ
    so much, yet it is 100% contained. Containment is the right test here.
    """
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if not inter:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(min(area_a, area_b))


def analyse(frame, ts_ms):
    """Return (per_frame_label, people). label: A any upright, B any lying, C empty."""
    h, w = frame.shape[:2]
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                      data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    res = _det.detect_for_video(mp_img, ts_ms)

    # Largest box first, then drop heavy overlaps: MediaPipe sometimes returns a
    # head-only duplicate of a person already detected, which double-counts them.
    # Each person: (box, posture, ratio, head_y). head_y is the highest FACE
    # landmark (nose/eyes/ears/mouth, indices 0-10). Unlike the box top it does
    # not move when an arm is raised, so it is the reference for "hand above head".
    found = []
    for p in res.pose_landmarks:
        post, ratio = posture_of(p, w, h)
        head_y = min(l.y for l in p[:11]) * h
        found.append((bbox_of(p, w, h), post, ratio, head_y))
    found.sort(key=lambda t: (t[0][2] - t[0][0]) * (t[0][3] - t[0][1]), reverse=True)
    people = []
    for person in found:
        if not any(_overlap(person[0], kept[0]) > DUP_OVERLAP for kept in people):
            people.append(person)

    if not people:
        return "C", people
    postures = [p[1] for p in people]
    if "sitting" in postures:        # someone settled and working -> full comfort
        return "A", people
    if "standing" in postures:       # only movers -> transitional
        return "T", people
    return "B", people               # everyone lying -> resting


def main():
    _act = Actuator()
    _act.set(*LED["C"])

    camera_index = camera.find_index()
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {camera_index}.")

    print(f"Live passive mode (multi-person, smoothed) on camera {camera_index}.")
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
        for (x1, y1, x2, y2), post, *_ in people:
            color = (0, 200, 255) if post == "lying" else (0, 255, 0)
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


def _selftest():
    """Dedupe + posture guards (no camera needed)."""
    assert _overlap((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert _overlap((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    # a head-only box nested in a body box IS the same person (IoU would miss it)
    assert _overlap((0, 0, 100, 400), (10, 10, 90, 200)) > DUP_OVERLAP
    # two people standing apart must NOT be merged
    assert _overlap((0, 0, 100, 400), (300, 0, 400, 400)) < DUP_OVERLAP

    class _L:
        def __init__(self, x, y, visibility=1.0):
            self.x, self.y, self.visibility = x, y, visibility

    # hips hidden behind a desk -> must NOT be called lying
    hidden = [_L(0.5, 0.5) for _ in range(33)]
    hidden[23] = hidden[24] = _L(0.9, 0.5, visibility=0.1)
    assert posture_of(hidden, 100, 100)[0] != "lying"

    # genuinely lying: hips visible and the torso axis is horizontal
    flat = [_L(0.5, 0.5) for _ in range(33)]
    flat[11] = flat[12] = _L(0.2, 0.5, visibility=0.9)
    flat[23] = flat[24] = _L(0.8, 0.5, visibility=0.9)
    assert posture_of(flat, 100, 100)[0] == "lying"

    # LEANING FORWARD at a desk: torso compressed but still vertical, legs hidden
    # -> sitting. Calling this "lying" flipped the room A<->B every few seconds.
    leaning = [_L(0.5, 0.5) for _ in range(33)]
    leaning[11] = _L(0.35, 0.50, visibility=0.9)
    leaning[12] = _L(0.65, 0.50, visibility=0.9)
    leaning[23] = leaning[24] = _L(0.50, 0.57, visibility=0.9)
    assert posture_of(leaning, 100, 100)[0] == "sitting"

    # STANDING: legs in view, so the body is tall relative to the shoulders.
    # This is what lets pose answer T vs A instantly instead of waiting ~20s
    # for the VLM, which made the LEDs switch twice for one event.
    standing = [_L(0.50, 0.50, visibility=0.9) for _ in range(33)]
    standing[11] = _L(0.45, 0.20, visibility=0.9)
    standing[12] = _L(0.55, 0.20, visibility=0.9)
    standing[23] = standing[24] = _L(0.50, 0.50, visibility=0.9)
    standing[27] = _L(0.50, 0.95, visibility=0.9)      # ankle
    standing[0] = _L(0.50, 0.05, visibility=0.9)       # nose
    assert posture_of(standing, 100, 100)[0] == "standing"
    print("selftest ok")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        main()
