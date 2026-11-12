"""Find a camera's OpenCV index by name, so it survives index reshuffles.

macOS lists cameras (system_profiler) in the same order AVFoundation / OpenCV
open them, so the position of a device name in that list is its cv2 index.
"""
import re
import subprocess

import cv2

# ponytail: name match, not a fixed index — 3 cameras here (Mac + 2 iPhones)
# reorder whenever a phone sleeps/wakes. Change this to pick a different one.
PREFERRED = "Amv Camera"   # iPhone 12 Pro
EXCLUDE = "Amvx Camera"    # second iPhone — never select or switch to it


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


def find_index(preferred=PREFERRED):
    """Index of the preferred camera if it opens, else first camera that opens."""
    names = _camera_names()
    order = [i for i, n in enumerate(names) if n == preferred]
    order += [i for i in allowed_indices() if i not in order]
    for i in order:
        cap = cv2.VideoCapture(i)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
        if ok:
            label = names[i] if i < len(names) else "?"
            print(f"Camera: index {i} ({label})")
            return i
    raise SystemExit("No working camera found.")


if __name__ == "__main__":
    print("Order:", _camera_names())
    print("Chosen index:", find_index())
