import sys, time, cv2, ollama
cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = Mac webcam, 1 = iPhone
cap = cv2.VideoCapture(cam)
desc = "starting..."
last = 0
while True:
    ok, frame = cap.read()
    if not ok:
        continue
    if time.time() - last >= 1.5:
        last = time.time()
        _, buf = cv2.imencode(".jpg", frame)
        r = ollama.chat(model="moondream",
                        messages=[{"role": "user",
                                   "content": "Describe this image.",
                                   "images": [buf.tobytes()]}])
        desc = r["message"]["content"].strip()
        print("\n" + time.strftime("%H:%M:%S"), desc)
    cv2.putText(frame, desc[:55], (15, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.imshow("live describe", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
