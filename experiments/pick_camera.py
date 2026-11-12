"""
Live camera chooser. Shows one camera live at a time so you can identify
which index is the iPhone (wave at it and see which feed moves).

Keys:
    n  switch to the next camera index
    q  quit

Usage:
    python pick_camera.py
"""

import cv2

MAX_INDEX = 4


def working_indexes():
    found = []
    for i in range(MAX_INDEX):
        cap = cv2.VideoCapture(i)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
        if ok:
            found.append(i)
    return found


def main():
    indexes = working_indexes()
    if not indexes:
        raise SystemExit("No cameras found.")
    print("Working indexes:", indexes)
    print("Wave at your iPhone. Press 'n' to switch, 'q' to quit.")

    pos = 0
    cap = cv2.VideoCapture(indexes[pos])

    while True:
        ok, frame = cap.read()
        if not ok:
            frame = None

        if frame is not None:
            label = f"index {indexes[pos]}   'n' next   'q' quit"
            cv2.putText(frame, label, (15, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
            cv2.imshow("pick camera", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("n"):
            cap.release()
            pos = (pos + 1) % len(indexes)
            cap = cv2.VideoCapture(indexes[pos])
            print(f"now showing index {indexes[pos]}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
