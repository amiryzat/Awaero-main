"""Interpret a VLM scene DESCRIPTION into an ACTIVITY, not just a posture.

The VLM already describes the scene - "a man sitting at a desk using a laptop",
"a person lying on a bed", "no people are visible". The old pipeline kept only
sit/stand/lie and threw the context away. This reads the context too, so the
decision layer can light the desk lamp for desk work and not for lounging, per
FYP_Room_Activity_and_Appliance_Decision_Profiles.md (Activity -> Context ->
Decision).

Four activities, aligned 1:1 with the Capture labels:
    STUDYING      sitting at the desk (desk / laptop context)   -> capture "studying"
    RESTING       lying down / on the bed                       -> capture "resting"
    TRANSITIONAL  standing / moving around                      -> capture "standing"
    UNOCCUPIED    no person described                           -> capture "empty"

Pure text. No model, no camera. `python scene_activity.py selftest`.
"""

import re
import sys

# A bedroom-study has a bed in frame even while the person is at the desk, so
# "bed" alone must NOT mean resting - it only counts when nobody is clearly
# sitting. Order of checks below handles that.
PERSON = ("person", "man", "woman", "boy", "girl", "people", "someone",
          "individual", "guy", "figure", "he", "she")
NO_PERSON = ("no person", "no one", "no people", "nobody", "not occupied",
             "unoccupied", "empty room", "no visible", "there are no")
DESK = ("desk", "laptop", "computer", "keyboard", "monitor", "working", "studying")
# Whole words only (below): "laying" must NOT fire inside "playing a video game",
# and "lie" must not fire inside "believe" - a substring match got both wrong.
LIE = ("lying", "laying", "lie", "lies", "reclining", "reclined", "asleep", "sleeping")
BED = ("bed", "couch", "sofa", "mattress")
SIT = ("sitting", "seated", "sits")
STAND = ("standing", "stands", "walking", "walks")

LABEL_TO_ACTIVITY = {"studying": "STUDYING", "resting": "RESTING",
                     "standing": "TRANSITIONAL", "empty": "UNOCCUPIED"}

# The live system still speaks in profile letters (T/A/B/C); activities map 1:1.
ACTIVITY_TO_PROFILE = {"STUDYING": "A", "RESTING": "B",
                       "TRANSITIONAL": "T", "UNOCCUPIED": "C"}


def _has(text, words):
    """Whole-word match for single words (so 'laying' does not hit 'playing'),
    plain substring for multi-word phrases like 'no person'."""
    for w in words:
        if " " in w:
            if w in text:
                return True
        elif re.search(r"\b" + re.escape(w) + r"\b", text):
            return True
    return False


def present(text):
    """Is a person actually described? Explicit absence wins over a stray
    'person' in e.g. 'no person is visible'."""
    t = text.lower()
    if _has(t, NO_PERSON):
        return False
    return _has(t, PERSON)


def interpret(description):
    """Return (activity, detail). detail = {present, at_desk, posture} so the
    decision layer can use at_desk for the lamp. Checks go absence -> lying ->
    standing -> sitting, because a real description mixes cues (a sitting person
    in a room that also contains a bed)."""
    t = (description or "").lower()
    if not present(t):
        return "UNOCCUPIED", {"present": False, "at_desk": False, "posture": "none"}

    at_desk = _has(t, DESK)
    sitting = _has(t, SIT)

    # Lying beats the rest, but only when the person is not clearly sitting
    # (otherwise "sitting ... next to a bed" would read as resting).
    if _has(t, LIE) or (_has(t, BED) and not sitting and not at_desk and not _has(t, STAND)):
        return "RESTING", {"present": True, "at_desk": False, "posture": "lie"}
    if _has(t, STAND) and not sitting:
        return "TRANSITIONAL", {"present": True, "at_desk": at_desk, "posture": "stand"}
    # Default for a present, non-lying, non-standing person: sitting = at the
    # desk in this single-chair room -> studying.
    return "STUDYING", {"present": True, "at_desk": at_desk, "posture": "sit"}


def activity(description):
    """Just the activity label."""
    return interpret(description)[0]


def profile_and_desk(description):
    """For the live system: (profile letter, at_desk). The letter drives the
    existing fusion/appliance machinery; at_desk gates the desk lamp so it lights
    only when the person is actually working at the desk, not just 'sitting'."""
    act, detail = interpret(description)
    return ACTIVITY_TO_PROFILE[act], detail["at_desk"]


def _selftest():
    # Real-shape descriptions (the style Moondream/Qwen actually produce).
    cases = [
        ("The image shows a man sitting at a desk using a laptop. The room appears "
         "to be a bedroom, as there is a bed and a TV.", "STUDYING", True),
        ("A person sitting at a desk, possibly working or studying on a computer.",
         "STUDYING", True),
        ("A person is lying on a bed looking at their phone.", "RESTING", False),
        ("The image shows someone lying down, relaxing.", "RESTING", False),
        ("A man is standing in the middle of the room near the wardrobe.",
         "TRANSITIONAL", False),
        ("No people are visible in this image; it shows an empty bedroom with a "
         "desk and a bed.", "UNOCCUPIED", False),
        ("There are no people in the room.", "UNOCCUPIED", False),
        # tricky: sitting person while a bed is in frame must stay STUDYING
        ("A woman is sitting at her desk typing, with a bed behind her.",
         "STUDYING", True),
        # regression: 'playing' must not match 'laying', 'believe' not 'lie'
        ("A person sitting at a desk playing a video game with a controller; a "
         "bed is visible in the background.", "STUDYING", True),
        ("A person is standing; I believe they are near the desk.",
         "TRANSITIONAL", True),
        # standing but a desk is in the room: still transitional, lamp decision
        # later uses at_desk, but the activity is standing
        ("A person standing next to the desk.", "TRANSITIONAL", True),
        # a mattress/bed in the scene must not beat an explicit 'standing'
        ("A young man is standing on a green mattress in the room.",
         "TRANSITIONAL", False),
    ]
    for desc, want_act, want_desk in cases:
        act, detail = interpret(desc)
        assert act == want_act, f"{want_act} expected, got {act}: {desc!r}"
        assert detail["at_desk"] == want_desk, f"at_desk {want_desk}: {desc!r}"
    assert profile_and_desk("A man sitting at a desk using a laptop.") == ("A", True)
    assert profile_and_desk("A person lying on a bed.") == ("B", False)
    assert profile_and_desk("A person standing by the wardrobe.") == ("T", False)
    assert profile_and_desk("An empty room with a bed and a desk.") == ("C", False)
    assert activity("") == "UNOCCUPIED"                 # empty text -> nobody
    assert LABEL_TO_ACTIVITY["studying"] == "STUDYING"  # capture labels map 1:1
    print("scene_activity selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        print("usage: python scene_activity.py selftest")
