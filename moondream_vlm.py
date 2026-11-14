"""
Moondream passive VLM engine - the DEFAULT engine of live_system.py.

Chosen 2026-11-14 over Qwen3-VL (docs/EVAL_passive_vlm.md, Runs 9-13): equal
accuracy on the labelled set (12/12 each) at 0.8 s per frame instead of ~20 s,
which also makes it fast enough to confirm presence and override pose's phantom
people on furniture.

Pipeline: ask Moondream to describe the PEOPLE in the frame, then read the
profile from the description with word-boundary keywords. Every judged frame and
its description are saved so any decision can be checked afterwards.

Same interface as classify_passive (Qwen): ask(image, prompt) -> (text, seconds),
plus keyword_label(text) and parse_phone(text).

Selftest: python moondream_vlm.py selftest
"""

import csv
import os
import re
import sys
import time

import ollama

MODEL = "moondream:latest"
# Prompt wording decides whether "no person mentioned" means "empty room".
# Measured on 70 frames with eye-checked ground truth (2026-11-14):
#   "Describe this image."                       person mentioned: empty 41/41 ok,
#                                                lying 1/12, hallway 0/6
#   "Describe the people in this image."         empty 41/41, lying 12/12,
#                                                other 11/11, hallway 6/6   <- used
#   "Describe the person ... what they are doing" INVENTS a person in 41/41 empty
# Direct questions ("Is there a person?") return an empty string from this build.
DESCRIBE = "Describe the people in this image."
# ponytail: num_predict caps the description. The posture word lands in the first
# sentence ("a young man sitting at a desk..."), and uncapped descriptions ran up
# to 93 s. Moondream is not a thinking model, so a cap is safe here (unlike Qwen).
OPTIONS = {"temperature": 0, "num_predict": 60}

# Most specific first. The original pipeline tested "upright" (T) before
# "sitting" (A), so "seated upright" scored as T. Matched on WORD boundaries:
# substring matching read "playing a video game" as "laying" and labelled every
# sitting frame as lying.
EMPTY = re.compile(r"\b(no one|nobody|empty room|no person|unoccupied|no people)\b")
LYING = re.compile(r"\b(lying|lies|laying|lays|asleep|sleeping|reclin\w*)\b")
SITTING = re.compile(r"\b(sitting|seated|sits)\b")
STANDING = re.compile(r"\b(standing|stands|walking|walks)\b")
# A posture word only counts if a PERSON is described. "a cable lying on the
# desk" with no person in frame scored B and started a whole run on B.
PERSON = re.compile(r"\b(man|men|woman|women|boy|girl|person|people|someone|"
                    r"guy|child|kid|individual)\b")
PHONE = re.compile(r"\b(phone|cellphone|smartphone|cell phone|mobile)\b")

VLM_DIR = "snapshots/vlm"            # every frame Moondream judged
DESC_LOG = "vlm_descriptions.csv"    # ...and what it said about it


def keyword_label(text):
    """T/A/B/C from a description, else '?' (the live loop then holds).

    No person described -> C. That is only safe with DESCRIBE above: with the old
    "Describe this image." Moondream ignored someone lying on the bed in 12 of 12
    such frames; "Describe the people in this image." mentioned them 12/12, and
    never invented a person in 41 empty-room frames (2026-11-14, checked by eye).
    """
    t = text.lower()
    if EMPTY.search(t) or not PERSON.search(t):
        return "C"
    if LYING.search(t):
        return "B"
    if SITTING.search(t):
        return "A"
    if STANDING.search(t):
        return "T"
    return "?"


def parse_phone(text):
    """'yes' if the description mentions a phone, else '' (unknown, not 'no').
    Scene metadata only; it never changes control."""
    return "yes" if PHONE.search(text.lower()) else ""


def ask(image, _prompt=None):
    """Describe the people in one JPEG frame. The prompt argument is ignored (it
    exists so the call matches classify_passive.ask). Saves the frame and the
    description as evidence."""
    t0 = time.time()
    r = ollama.chat(model=MODEL,
                    messages=[{"role": "user", "content": DESCRIBE, "images": [image]}],
                    options=OPTIONS)
    desc = r["message"]["content"].strip()
    dt = time.time() - t0
    stamp, label = time.strftime("%H%M%S"), keyword_label(desc)
    os.makedirs(VLM_DIR, exist_ok=True)
    with open(os.path.join(VLM_DIR, f"{stamp}_{label}.jpg"), "wb") as f:
        f.write(image)
    new = not os.path.exists(DESC_LOG)
    with open(DESC_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "label", "latency_s", "description"])
        w.writerow([stamp, label, round(dt, 1), desc])
    return desc, dt


def _selftest():
    assert keyword_label("A young man sitting at a desk in a room with a bed") == "A"
    assert keyword_label("a man is standing in a room with a bed") == "T"
    assert keyword_label("two people lying on a green bed") == "B"
    assert keyword_label("The room is an empty room with no one in it") == "C"
    assert keyword_label("a cluttered room with a bed and a desk") == "C"   # nobody
    assert keyword_label("a man seated upright at a desk") == "A"   # the old T/A bug
    # posture word with nobody described -> empty, not lying (was a false B)
    assert keyword_label("a monitor on the wall, a cable lying on the desk") == "C"
    # "playing" contains "laying": must read as sitting, not lying
    assert keyword_label("a young man sitting in a chair, playing a video game") == "A"
    assert keyword_label("a man in a black shirt near the desk") == "?"   # no posture
    assert parse_phone("a man lying on the bed holding a cell phone") == "yes"
    assert parse_phone("a man sitting at a desk") == ""
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
