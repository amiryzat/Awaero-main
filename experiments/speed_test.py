import cv2
import time
import ollama

PROMPT = "Describe what the person in this image is doing."

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise SystemExit("Could not open webcam.")

print("Warming up camera...")
for _ in range(10):
    cap.read()

ok, frame = cap.read()
cap.release()
if not ok:
    raise SystemExit("Could not capture a frame.")

cv2.imwrite("test_frame.jpg", frame)
_, buf = cv2.imencode(".jpg", frame)
img = buf.tobytes()

print("Loading model (first call is slow, this is expected)...")
t0 = time.time()
r = ollama.chat(model="moondream",
                messages=[{"role": "user", "content": PROMPT, "images": [img]}])
print(f"Cold start: {time.time() - t0:.2f}s")
print(f"Caption: {r['message']['content'].strip()}\n")

times = []
for i in range(3):
    t0 = time.time()
    r = ollama.chat(model="moondream",
                    messages=[{"role": "user", "content": PROMPT, "images": [img]}])
    dt = time.time() - t0
    times.append(dt)
    print(f"Run {i+1}: {dt:.2f}s")
    print(f"  {r['message']['content'].strip()}\n")

print(f"Average warm inference: {sum(times)/len(times):.2f}s")
