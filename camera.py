"""Find a camera's OpenCV index by name, so it survives index reshuffles.

macOS lists cameras (system_profiler) in the same order AVFoundation / OpenCV
open them, so the position of a device name in that list is its cv2 index.
"""
import re
import subprocess
import time

import cv2

# ponytail: name match, not a fixed index — 3 cameras here (Mac + 2 iPhones)
# reorder whenever a phone sleeps/wakes. Change this to pick a different one.
PREFERRED = "Amv Camera"   # iPhone 12 Pro
EXCLUDE = "Amvx Camera"    # second iPhone — never select or switch to it

# VERIFIED BY PROBE on 2026-11-14: index 0 = MacBook webcam, index 1 = iPhone 12.
#
# Name matching alone is NOT trustworthy here: it assumed system_profiler lists
# cameras in AVFoundation (== OpenCV) order, and it does not. The order changed
# between calls and a whole test run was recorded on the Mac webcam while the log
# claimed it was the iPhone. So the index is PINNED and only sanity-checked.
#
# If the hardware shuffles, re-verify with:   python camera.py probe
# then look at the saved frames and update this number.
PINNED_INDEX = 1


def _camera_names():
    """Camera device names in AVFoundation order (== OpenCV index order)."""
    out = subprocess.run(
        ["system_profiler", "SPCameraDataType"],
        capture_output=True, text=True,
    ).stdout
    # device-name lines are indented exactly 4 spaces and end in ':'
    return [m.group(1) for m in re.finditer(r"^ {4}(\S.*?):$", out, re.M)]


def allowed_indices():
    """Indices of cameras that aren't the excluded one."""
    return [i for i, n in enumerate(_camera_names()) if n != EXCLUDE]


# A waking Continuity Camera (iPhone) opens but delivers no frame for a second or
# two. A single read() fails there and we silently fell back to the Mac webcam, so
# keep retrying for this long before giving up on a camera.
WARMUP_SECONDS = 4.0
PREFERRED_WARMUP = 12.0   # a sleeping iPhone needs longer to start streaming


def _yields_frame(index, warmup=WARMUP_SECONDS):
    """True if this camera delivers a frame within the warm-up window."""
    cap = cv2.VideoCapture(index)
    try:
        deadline = time.time() + warmup
        while time.time() < deadline:
            if cap.isOpened() and cap.read()[0]:
                return True
            time.sleep(0.2)
        return False
    finally:
        cap.release()


def probe(out_dir="camera_probe"):
    """Save one frame from every index, so you can SEE which camera is which."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    for i in range(4):
        cap = cv2.VideoCapture(i)
        got = None
        deadline = time.time() + PREFERRED_WARMUP
        while time.time() < deadline:
            if cap.isOpened():
                ok, frame = cap.read()
                if ok:
                    got = frame
                    break
            time.sleep(0.2)
        cap.release()
        if got is None:
            print(f"index {i}: no frame")
        else:
            path = os.path.join(out_dir, f"index_{i}.jpg")
            cv2.imwrite(path, got)
            print(f"index {i}: {got.shape[1]}x{got.shape[0]} -> {path}")
    print(f"\nLook at the frames in {out_dir}/ and set PINNED_INDEX in camera.py.")


def find_index(preferred=PREFERRED, require_preferred=True):
    """The pinned camera, verified to actually stream.

    Does NOT silently substitute another camera: recording a whole test run on
    the Mac webcam while the log claimed 'Amv Camera' is exactly what this
    prevents. require_preferred=False allows any working camera instead.
    """
    if PINNED_INDEX is not None and _yields_frame(PINNED_INDEX, PREFERRED_WARMUP):
        print(f"Camera: index {PINNED_INDEX} (pinned, expected {preferred})")
        return PINNED_INDEX

    if require_preferred:
        raise SystemExit(
            f"Pinned camera index {PINNED_INDEX} ({preferred}) is not streaming - "
            "the phone is probably asleep or locked.\n"
            "  Wake the iPhone, unlock it, keep it mounted and in range, then re-run.\n"
            "  If the indices shuffled: python camera.py probe\n"
            "  To allow any camera:     camera.find_index(require_preferred=False)")

    for i in allowed_indices():
        if _yields_frame(i):
            print(f"Camera: index {i}  [FALLBACK - may NOT be {preferred}]")
            return i
    raise SystemExit("No working camera found.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        probe()
    else:
        print("system_profiler order (UNRELIABLE):", _camera_names())
        print("Chosen index:", find_index())
