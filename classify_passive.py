"""
Passive-mode classifier (Layer 3 Inference + Layer 4 Decision Logic), offline
evaluator over the labelled frames in frames/.

Single-stage direct classification: the VLM is asked for ONE letter (T/A/B/C)
with capped output. This replaced the old Moondream2 two-stage "describe then
keyword-scan" workaround, which existed only because that build answered nothing
but free-form "Describe this image." Qwen3-VL follows an instruction, so the
describe + keyword machinery is gone: it was both slow (paragraph generation,
~60 s/frame) and fragile (e.g. "seated upright" keyword-matched T, not A).

Profiles:
    T  transitional / standing or walking
    A  active / sitting
    B  resting / lying down
    C  unoccupied / no person

Runs across frames/profile_*.jpg, prints per-frame results, a confusion matrix
and overall accuracy, and writes classify_results.csv.

Usage:
    python classify_passive.py
"""

import csv
import glob
import os
import time

import ollama

MODEL = "qwen3-vl:8b"   # swapped from moondream (lecturer's call)

CLASSIFY_PROMPT = (
    "You classify a room for energy control. Reply with ONE letter only, no other "
    "text:\n"
    "T = a person standing or walking\n"
    "A = a person sitting\n"
    "B = a person lying down or resting\n"
    "C = no person present\n"
    "Answer:"
)
# Qwen3-VL is a thinking model: it emits hidden reasoning before the answer, so
# DON'T cap num_predict (the cap gets eaten by <think> and the letter never comes).
# temperature 0 = deterministic. Thinking goes to a separate field; content is the
# clean letter. ~3 s/frame. ponytail: raise num_predict only if answers truncate.
OPTIONS = {"temperature": 0}

FRAMES_DIR = "frames"
CSV_OUT = "classify_results.csv"

PROFILE_NAMES = {
    "T": "transitional / standing",
    "A": "active sitting",
    "B": "resting (lying)",
    "C": "unoccupied",
}


def parse_label(answer):
    """First T/A/B/C letter in the model's reply, else '?'."""
    for ch in answer.upper():
        if ch in ("T", "A", "B", "C"):
            return ch
    return "?"


def ask(image, prompt):
    t0 = time.time()
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt, "images": [image]}],
        options=OPTIONS,
    )
    return response["message"]["content"].strip(), time.time() - t0


def true_label(filename):
    return os.path.basename(filename).split("_")[1]


def main():
    frames = sorted(glob.glob(os.path.join(FRAMES_DIR, "profile_*.jpg")))
    if not frames:
        raise SystemExit(f"No frames found in {FRAMES_DIR}/")

    labels = ["T", "A", "B", "C"]
    confusion = {t: {p: 0 for p in labels + ["?"]} for t in labels}
    rows = []
    correct = 0
    total_time = 0.0

    print(f"Model: {MODEL}  (direct one-letter classification)\n")

    for frame in frames:
        with open(frame, "rb") as f:
            image = f.read()

        answer, elapsed = ask(image, CLASSIFY_PROMPT)
        predicted = parse_label(answer)

        total_time += elapsed
        actual = true_label(frame)
        hit = actual == predicted
        if hit:
            correct += 1
        confusion[actual][predicted] += 1

        mark = "OK " if hit else "XX "
        print(f"{mark}{os.path.basename(frame)}  actual={actual} pred={predicted}  "
              f"{elapsed:.2f}s  (raw: {answer!r})")

        rows.append({
            "frame": os.path.basename(frame),
            "actual": actual,
            "predicted": predicted,
            "correct": hit,
            "seconds": f"{elapsed:.2f}",
            "raw_answer": answer,
        })

    total = len(frames)
    print("\n" + "=" * 60)
    print("Confusion matrix (rows = actual, cols = predicted)")
    cols = labels + ["?"]
    print("        " + "  ".join(f"{p:>3}" for p in cols))
    for t in labels:
        counts = "  ".join(f"{confusion[t][p]:>3}" for p in cols)
        print(f"  {t}    {counts}")
    print()
    print(f"Accuracy: {correct}/{total} = {100 * correct / total:.1f}%")
    print(f"Average inference: {total_time / total:.2f}s per frame")

    with open(CSV_OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "frame", "actual", "predicted", "correct", "seconds", "raw_answer",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {CSV_OUT}")


if __name__ == "__main__":
    main()
