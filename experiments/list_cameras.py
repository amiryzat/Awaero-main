"""
Probe available camera indexes and preview each one.

Use this to find which index is your phone after connecting it (Continuity
Camera on iPhone, or a webcam app on Android). The index you want goes into
the capture scripts as cv2.VideoCapture(INDEX).

Usage:
    python list_cameras.py
"""

import cv2

MAX_INDEX = 4  # check indexes 0..3


def main():
    found = []
    for i in range(MAX_INDEX):
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        if ok:
            h, w = frame.shape[:2]
            found.append((i, w, h))
            print(f"index {i}: OPEN  {w}x{h}")
        else:
            print(f"index {i}: opened but no frame")
        cap.release()

    if not found:
        raise SystemExit("No cameras found.")

    print("\nPreviewing each working camera. Press any key to move to the next.")
    for i, w, h in found:
        cap = cv2.VideoCapture(i)
        for _ in range(10):  # warm up
            cap.read()
        ok, frame = cap.read()
        if ok:
            label = f"index {i}  ({w}x{h})  - press any key"
            cv2.putText(frame, label, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("camera preview", frame)
            cv2.waitKey(0)
        cap.release()
    cv2.destroyAllWindows()

    print("\nWorking indexes:", [i for i, _, _ in found])
    print("Note the index whose preview showed your phone's view.")


if __name__ == "__main__":
    main()
