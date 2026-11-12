"""
Isolate why some prompts return empty output from Moondream2.

Hypothesis: the model handles plain questions and plain imperatives, but
returns an immediate stop token when the prompt contains meta-instructions
about output format or length.

Prints response metadata (done_reason, eval_count) so empty replies can be
distinguished from genuine generation failures.

Usage:
    python prompt_test2.py [image_path]
"""

import sys
import time

import ollama

IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else "test_frame.jpg"
MODEL = "moondream"

PROMPTS = {
    # Known-good control
    "01_describe_doing": "Describe what the person in this image is doing.",
    # Plain questions, no meta-instruction
    "02_plain_question": "What is the person doing?",
    "03_posture_question": "What is the person's posture?",
    "04_binary": "Is the person sitting or standing?",
    "05_presence": "Is there a person in this image?",
    # Plain imperatives, no meta-instruction
    "06_describe_posture": "Describe the person's posture.",
    "07_describe_activity": "Describe the person's activity.",
    # Question plus meta-instruction (expected to fail)
    "08_question_brief": "What is the person doing? Answer briefly.",
    "09_question_oneword": "What is the person doing? Answer with one word.",
    # Imperative plus meta-instruction (expected to fail)
    "10_describe_brief": "Describe the person's activity in a few words.",
}


def main():
    with open(IMAGE_PATH, "rb") as f:
        image = f.read()

    print(f"Image: {IMAGE_PATH}   Model: {MODEL}\n")

    for name, prompt in PROMPTS.items():
        t0 = time.time()
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt, "images": [image]}],
        )
        elapsed = time.time() - t0

        answer = response["message"]["content"].strip()
        done_reason = response.get("done_reason", "?")
        eval_count = response.get("eval_count", 0)
        status = "EMPTY" if not answer else f"{len(answer.split())}w"

        print(f"{name}")
        print(f"  prompt : {prompt}")
        print(f"  result : {status} | {elapsed:.2f}s | "
              f"done_reason={done_reason} | eval_count={eval_count}")
        if answer:
            print(f"  answer : {answer}")
        print()


if __name__ == "__main__":
    main()
