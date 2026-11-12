"""
Prompt comparison for passive mode (Layer 3: Inference).

Runs several prompt styles against a single captured frame to find which
one produces output that is short and reliably classifiable into the four
passive energy profiles (T, A, B, C).

Usage:
    python prompt_test.py [image_path]
"""

import sys
import time

import ollama

IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else "test_frame.jpg"
MODEL = "moondream"
REPEATS = 3

PROMPTS = {
    "A_baseline": "Describe what the person in this image is doing.",
    "B_one_sentence": "In one short sentence, what is the person doing?",
    "C_three_words": "What is the person doing? Answer in three words or less.",
    "D_forced_label": (
        "Look at the person in this image. Reply with exactly one word from "
        "this list and nothing else: standing, sitting, lying, empty."
    ),
}


def load_image(path):
    with open(path, "rb") as f:
        return f.read()


def ask(image, prompt):
    t0 = time.time()
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt, "images": [image]}],
    )
    elapsed = time.time() - t0
    return response["message"]["content"].strip(), elapsed


def main():
    image = load_image(IMAGE_PATH)
    print(f"Image: {IMAGE_PATH}")
    print(f"Model: {MODEL}")
    print(f"Repeats per prompt: {REPEATS}\n")

    for name, prompt in PROMPTS.items():
        print("=" * 70)
        print(f"{name}")
        print(f"  prompt: {prompt}")
        print("-" * 70)

        times = []
        for i in range(REPEATS):
            answer, elapsed = ask(image, prompt)
            times.append(elapsed)
            words = len(answer.split())
            print(f"  [{i + 1}] {elapsed:.2f}s | {words} words")
            print(f"      {answer}")

        print(f"  average: {sum(times) / len(times):.2f}s\n")


if __name__ == "__main__":
    main()
