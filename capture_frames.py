"""
Capture labelled reference frames for the four passive energy profiles, from the
real mounted phone camera (the demo camera position), not the Mac webcam.

Opens a live preview on the phone camera (picked by name via camera.py). Press
the key for a profile to save the current frame into frames/ with a sequential
filename (profile_<LABEL>_<NN>.jpg). Frame the phone on the room scene first.

    T  transitional / standing or walking
    A  active / sitting
    B  resting / lying down
    C  unoccupied (step fully out of shot first - an empty room)
    0/1/... switch camera     Q  quit

Usage:
    python capture_frames.py
"""

import os

import cv2

import camera

OUTPUT_DIR = "frames"
PROFILES = {ord("t"): "T", ord("a"): "A", ord("b"): "B", ord("c"): "C"}
PROFILE_NAMES = {
    "T": "transitional / standing",
    "A": "active sitting",
    "B": "resting (lying)",
    "C": "unoccupied",
}


def next_index(profile):
    existing = [f for f in os.listdir(OUTPUT_DIR)
                if f.startswith(f"profile_{profile}_")]
    return len(existing) + 1


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    idx = camera.find_index()
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {idx}.")

    print(__doc__)
    print(f"Preview open on camera {idx}. Click the window, then press a key.\n")

    counts = {p: 0 for p in PROFILE_NAMES}

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        preview = frame.copy()
        tally = "  ".join(f"{p}:{counts[p]}" for p in "TABC")
        cv2.putText(preview, f"cam {idx}   {tally}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(preview, "T/A/B/C capture  0-9 switch cam  Q quit", (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Capture reference frames", preview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key in PROFILES:
            profile = PROFILES[key]
            n = next_index(profile)
            path = os.path.join(OUTPUT_DIR, f"profile_{profile}_{n:02d}.jpg")
            cv2.imwrite(path, frame)          # save the raw frame, not the overlay
            counts[profile] += 1
            print(f"saved {path}  ({PROFILE_NAMES[profile]})")
        if ord("0") <= key <= ord("9"):
            new = key - ord("0")
            if new not in camera.allowed_indices():
                print(f"Camera index {new} not available; staying on {idx}.")
            else:
                cap.release()
                cap = cv2.VideoCapture(new)
                idx = new
                print(f"Switched to camera index {idx}.")

    cap.release()
    cv2.destroyAllWindows()

    print("\nCaptured this session:")
    for profile, count in counts.items():
        print(f"  {profile}  {PROFILE_NAMES[profile]:<24} {count}")


if __name__ == "__main__":
    main()
