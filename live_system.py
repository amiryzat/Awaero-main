"""
Live integrated system - the documented five-layer pipeline, end to end.

Single-entry dual-mode runtime (Chapter 3). Reuses the engines already built and
wires them through the Mode Selection Layer (Layer 2) and the Decision Logic
Layer (Layer 4).

POSE RUNS ON EVERY FRAME, IN BOTH MODES. The room is always being sensed; the
mode only decides who OWNS the appliances. (The 2026-11-14 test failed because
pose only ran in passive mode and the router never left active - see below.)

    Layer 2 router - a DELIBERATE control hand, not mere hand presence:
      - hand held up, fingers up, away from the face -> ACTIVE (gesture control)
      - anything else (typing, resting, no hand)     -> PASSIVE (activity sensing)

    Layer 4 passive fusion (see fuse_label):
      - PRESENCE: pose sees a person AND (Moondream) the VLM described a person
        within PRESENCE_CONFIRM_SECONDS. Nobody -> Profile C after EMPTY_SECONDS.
      - POSTURE: the VLM decides T / A / B. With no answer yet the profile is
        HELD, never guessed from pose (pose posture is unreliable in this room).

Each profile maps to a per-appliance on/off vector (light, fan, tv). Both modes
write the SAME appliance state, so entering gesture control no longer wipes what
passive had set.

The VLM runs in a BACKGROUND thread on a downscaled frame; pose carries the
real-time path. Default engine: Moondream (moondream_vlm.py). Qwen3-VL
(classify_passive.py) is the evaluated alternative.

Keys:  q quit   0/1/... switch camera (Amvx excluded)
Usage: python live_system.py          Moondream (default)
       python live_system.py qwen     Qwen3-VL instead
       python live_system.py selftest
"""

import csv
import os
import sys
import threading
import time
from collections import deque, Counter

import cv2
import mediapipe as mp

from serial_actuator import Actuator
from display_node import LcdDisplay, status_lines
import camera
import classify_passive
import moondream_vlm
from live_active import (classify_gesture, hand_is_upright, apply, GESTURE_LABEL,
                         CONFIRM_FRAMES, HOLD_SECONDS, REARM_SECONDS)
# live_passive is imported inside main(): it builds the pose model at import time.

PASSIVE_FALLBACK_SECONDS = 2.0   # no control hand for this long -> back to passive
# Sustained absence before the room is called empty. 4s was too short: pose
# briefly loses a person who leans forward over a desk, and the room went to
# "unoccupied" with someone sitting right there.
EMPTY_SECONDS = 8.0

# Presence confirmation by the VLM. Pose cannot tell a phantom pose on a chair or
# clothes rack from a real person: measured 2026-11-14, both score landmark
# visibility/presence ~1.00, so with the room empty pose kept "seeing" someone and
# it never went to C. So the room only counts as occupied if the VLM described a
# person (T/A/B) within this many seconds: 10 s is ~4 Moondream answers, and its
# people prompt missed 0 of 29 person frames. Leaving -> C measured 10-18 s.
# use_qwen() sets None (pose alone): Qwen answers every ~15 s, which would leave
# the lights off that long as someone walks in.
PRESENCE_CONFIRM_SECONDS = 10.0

# Leave ACTIVE after this long with no gesture being held. Without it a hand on
# the table kept the system in ACTIVE indefinitely once it had been entered.
ACTIVE_IDLE_SECONDS = 6.0
# With no person box matched, fall back to an absolute height test. 0.4 was too
# strict: seated in a wide room shot, a hand raised fully above the head still
# landed at ~0.55 of frame height and the gesture was ignored.
HAND_RAISE_FRACTION = 0.55
# Process at this width instead of the camera's native 1080p. Running the full
# pose model (4 poses) plus Hands on every 1920x1080 frame saturated the Metal
# GPU that Ollama needs: the SAME model/prompt/frames measured 10 s standalone
# but 44 s inside the live loop. Vision and the VLM were starving each other.
PROC_WIDTH = 960
POSE_EVERY = 2                   # run pose every Nth frame; a room does not
                                 # change meaningfully at 30 fps
VLM_WIDTH = 640                  # downscale before inference (latency lever)
VLM_STALE_SECONDS = 45.0         # ignore a VLM answer older than this
# Minimum gap between VLM calls. Moondream takes ~1-2 s, so 1 s gives an answer
# every ~2 s (fast re-entry confirmation; live latency stayed flat at 1.87 s over
# 199 answers). use_qwen() sets 3 s: re-inferring back-to-back pegged the GPU and
# Qwen's latency climbed 8.8 s -> 70.5 s over one run.
VLM_MIN_INTERVAL = 1.0

# Passive VLM engine, called by the worker thread. Moondream is the default,
# chosen 2026-11-14 from docs/EVAL_passive_vlm.md Runs 9-13; use_qwen() swaps in
# Qwen3-VL. The worker looks these names up at call time.
ask = moondream_vlm.ask
parse_label = moondream_vlm.keyword_label
parse_phone = moondream_vlm.parse_phone
VLM_PROMPT = moondream_vlm.DESCRIBE
VLM_NAME = moondream_vlm.MODEL


def use_qwen():
    """Switch the passive VLM to Qwen3-VL, the evaluated alternative."""
    global ask, parse_label, parse_phone, VLM_PROMPT, VLM_NAME
    global VLM_MIN_INTERVAL, PRESENCE_CONFIRM_SECONDS
    ask, parse_label = classify_passive.ask, classify_passive.parse_label
    parse_phone = classify_passive.parse_phone
    VLM_PROMPT, VLM_NAME = classify_passive.CLASSIFY_PROMPT_PHONE, classify_passive.MODEL
    VLM_MIN_INTERVAL = 3.0
    PRESENCE_CONFIRM_SECONDS = None

# How long a gesture holds an appliance against the automatic scenario. Without
# an expiry a fist left the fan off forever, because no gesture turns the fan
# back on (there are only 3 gestures). With no hold at all, passive would
# overwrite every gesture immediately and gesture control would be pointless.
# The hold is PER APPLIANCE and also ends early when the room context changes.
OVERRIDE_SECONDS = 60.0
# peace/open_palm hold just the appliance they touch for OVERRIDE_SECONDS. Fist
# holds NOTHING here: its persistence comes from leaving_latch (all-off until the
# room empties or ANY gesture cancels it). If fist also set 60 s holds, a "changed
# my mind" gesture would release the latch but the fan/TV would stay stuck off
# under those holds - so the latch alone owns the fist.
GESTURE_HOLDS = {"peace": [0], "open_palm": [2], "fist": []}  # indexes into APPLIANCES

# Decision Logic Layer (Layer 4): each profile -> a per-appliance on/off vector.
# Five appliances, in pin order (arduino/room_node.ino):
#   pin 9 light, pin 10 fan, pin 11 tv, pin 8 desk lamp, pin 7 aircond.
APPLIANCES = ("light", "fan", "tv", "lamp", "ac")
NAPP = len(APPLIANCES)

# HOLD = the spec's "No change": that appliance keeps whatever it is doing.
# Standing is a TRANSITION, so it must not decide the TV or the AC - switching
# them because someone stood up for 5 seconds is the exact thrashing the
# supervisor's document warns about.
HOLD = None

# Policy from FYP_Room_Activity_and_Appliance_Decision_Profiles.md section 4.
# Two changes from the first prototype, both deliberate:
#   - sitting no longer turns the TV ON (sitting is not proof of watching), and
#   - standing no longer turns the fan OFF (brief movement should not switch it).
# ponytail: B's light is OFF, not dimmed (the 0/1 protocol cannot PWM).
# AC is an ASSUMED policy, not a measured one: with no temperature sensor the
# honest claim is "configurable assumption" (doc section 4). On while the
# occupant is settled, held during a transition, off when the room empties.
FUSED_APP  = {"A": (1, 1, 0, 1, 1),
              "T": (1, 1, HOLD, 0, HOLD),
              "B": (0, 1, 0, 0, 1),
              "C": (0, 0, 0, 0, 0)}
FUSED_NAME = {"T": "transitional (standing/walking)", "A": "active (sitting)",
              "B": "resting (lying)", "C": "unoccupied"}
FUSED_ACT  = {"T": "light+fan ON, lamp OFF, TV/AC held",
              "A": "light+fan+lamp+AC ON, TV OFF",
              "B": "fan+AC ON, light/TV/lamp OFF", "C": "all OFF"}

LOG_PATH = "live_log.csv"
LOG_FIELDS = ["time", "mode", "people", "pose", "vlm", "phone", "vlm_latency_s",
              "profile", "light", "fan", "tv",
              # RO3 response latency, appended so older parsers keep working.
              # decide = camera frame to committed decision (the real pipeline
              # cost, measured 21-42 ms). actuate = the serial write call only;
              # on macOS that returns in ~0.1 ms once the bytes are buffered, so
              # it is NOT time-until-the-LED-changes. Reporting it as end-to-end
              # actuation would overstate the measurement; an Arduino ack would
              # be needed for that.
              "decide_latency_ms", "actuate_latency_ms",
              # desk lamp + aircond, appended at the very end so the column order
              # every existing log and parser already relies on does not shift.
              "lamp", "ac"]
FRAME_PATH = "live_frame.jpg"   # latest annotated frame, relayed to the phone app
# Written here first, then renamed, so the server never serves a half-written
# file. It must keep the .jpg extension: OpenCV picks its encoder from that, and
# a plain ".tmp" makes imwrite fail.
FRAME_TMP = "live_frame.tmp.jpg"
RAW_PATH = "live_raw.jpg"        # latest CLEAN frame (no overlays) for eval capture
RAW_TMP = "live_raw.tmp.jpg"
# The Mac preview window is the ONLY way to quit (press q). For phone-driven
# capture sessions that is a liability - a stray q or a closed window ends the
# run. `headless` skips the window; the phone still sees the feed via /frame.jpg,
# and the run is stopped by killing the process.
SHOW_WINDOW = True
FRAME_EVERY = 0.5               # seconds between writes; also the app's heartbeat
SNAP_DIR = "snapshots"   # one annotated frame per decision: debugging evidence,
                         # and a labelled figure per response path for Chapter 4

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles


def log_row(**row):
    """Append one event to live_log.csv for RO3 (the dashboard reads this).

    mode=PASSIVE/ACTIVE rows are control decisions; mode=VLM rows are one per
    inference, so latency stats aren't double-counted across profile changes.

    A log written before the latency columns existed has a shorter header, and
    appending wider rows to it would silently misalign every column for whoever
    reads it. So a log whose header no longer matches is rotated aside, never
    appended to and never overwritten (it is evidence).
    """
    new = not os.path.exists(LOG_PATH)
    if not new and rotate_stale_log():
        new = True
    with open(LOG_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


def rotate_stale_log(path=None):
    """Rename the log aside when its header is not the current LOG_FIELDS.
    Returns True when it rotated."""
    path = path or LOG_PATH
    try:
        with open(path, newline="") as f:
            header = next(csv.reader(f), [])
    except OSError:
        return False
    if header == LOG_FIELDS:
        return False
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(os.path.getmtime(path)))
    kept = f"{os.path.splitext(path)[0]}_{stamp}.csv"
    os.replace(path, kept)
    print(f"[log] header changed; previous log kept as {os.path.basename(kept)}")
    return True


def control_hand_debug(lm, people, w, h):
    """(is_control, reason). The reason goes on screen: two rounds of guessing
    why gestures never fired produced two wrong fixes, so the system now says
    exactly which gate rejected the hand."""
    if not hand_is_upright(lm):
        return False, "not upright"
    cx = (lm[0].x + lm[9].x) / 2 * w
    cy = (lm[0].y + lm[9].y) / 2 * h          # for the no-person fallback
    knuckles = lm[9].y * h
    # Compared against the FACE (p[3], highest eye/ear landmark), not the box top.
    # The box is built from every pose landmark including wrist and fingers, so a
    # well-tracked raised hand stretched the box upward with it and was never
    # "above" it: only the far hand, which pose tracks poorly, ever got through
    # (observed 2026-11-14). Every person horizontally under the hand counts and
    # the hand must clear the highest face, so a phantom on a chair cannot help.
    heads = [p[3] for p in people if p[0][0] <= cx <= p[0][2]]
    if heads:
        ok = knuckles < min(heads)
        return ok, ("OK" if ok else "below head")
    hi = cy < HAND_RAISE_FRACTION * h
    return hi, ("OK" if hi else "too low in frame")


def timed_set(act, appl):
    """Drive the appliances and return how long the serial write took, in ms.
    This is RO3's actuation latency; without it only the VLM call is timed."""
    t0 = time.time()
    act.set(*appl)
    return round((time.time() - t0) * 1000, 1)


def since_ms(t0):
    """Milliseconds since t0, for the decide latency."""
    return round((time.time() - t0) * 1000, 1)


def is_control_hand(lm, people, w, h):
    """True only for a hand DELIBERATELY RAISED ABOVE THE HEAD.

    Two earlier versions were too permissive:
      1. any visible hand -> a hand on the keyboard pinned the system in ACTIVE
         mode, so passive sensing never ran at all;
      2. any upright hand not inside the top of a person's box -> a hand resting
         near the chin still fired OPEN PALM and switched the TV, because pose
         had only boxed the head so the "face region" test missed.

    So the command must now be unambiguous: fingers up AND the hand above the top
    of that person's own box, i.e. genuinely raised above their head. You cannot
    do that by accident while typing or resting your chin on your hand.
    """
    return control_hand_debug(lm, people, w, h)[0]   # one implementation, one truth


def decide_mode(current, control_hand, now, last_hand_time):
    """Layer 2 router. A deliberate hand -> ACTIVE at once; none past the grace ->
    PASSIVE; inside the grace the mode is held (stops flicker mid-gesture)."""
    if control_hand:
        return "ACTIVE"
    if now - last_hand_time > PASSIVE_FALLBACK_SECONDS:
        return "PASSIVE"
    return current


def fuse_label(pose_label, vlm_label, current="C"):
    """Layer 4 fusion. Pose = PRESENCE. VLM = POSTURE. Nothing guesses.

    Measured on 2026-11-14, pose posture is not usable in this room. Three
    separate attempts failed: the torso angle called a man leaning over his
    laptop "lying"; a foreshortening cue called the same pose "lying" again; and
    a body-extent ratio overlaps between sitting and standing (a man standing
    bent over the desk measured 4.4, inside the seated range). Across one run
    pose flipped T/B/A every few seconds while the subject sat still, and the
    VLM answered "A" correctly nearly every time.

    So pose now only answers "is anyone there" - which it does reliably, which
    is what blocks the VLM hallucinating an empty room, and which is where the
    energy saving actually comes from. Posture is the VLM's job alone.

    When no VLM answer has arrived yet the profile is HELD, never guessed. That
    is what removes the double switch: previously pose guessed a posture, the
    LEDs moved, then the VLM corrected it ~20 s later and they moved again. The
    cost is that a posture change waits for the VLM; the benefit is that the
    appliances stop blinking between states.
    """
    if pose_label == "C":              # presence gate: pose wins outright
        return "C"
    if vlm_label in ("T", "A", "B"):   # someone present -> the VLM judges what
        return vlm_label
    # No VLM answer yet. HOLD the current profile rather than guessing from pose:
    # pose's own guess was what made the LEDs switch twice for one event.
    return current if current in ("T", "A", "B") else "T"


# Posture debounce. The 4 s vote window above smooths POSE frame jitter, but it
# does NOT damp the VLM: one VLM read is replicated across every frame until the
# next read, so a single answer floods the window and saturates it in ~1 s. The
# VLM flip-flops T<->A on a static desk scene (and once read a standing person as
# A -> all appliances on). So debounce the VLM READ SEQUENCE, not frames: require
# N consecutive distinct reads to agree before the posture fed to fusion changes.
# N is the tunable knob (raise it = stickier, slower; lower it = twitchier).
POSTURE_DEBOUNCE_N = 2

def leave_target(latch, committed):
    """Appliance vector under the fist 'leaving' latch: all-off while the latch
    is held and someone is still present, otherwise the normal profile mapping.
    The caller clears the latch when this returns the normal mapping."""
    if latch and committed != "C":
        return (0,) * NAPP
    return FUSED_APP[committed]


def resolve_hold(target, current):
    """Turn a profile vector into real 0/1s. Any HOLD entry means "no change",
    so it takes the appliance's CURRENT value instead of a fixed one."""
    return tuple(current[i] if target[i] is HOLD else target[i]
                 for i in range(len(target)))

def debounce_vlm(label, history, stable, n=POSTURE_DEBOUNCE_N):
    """Call once per NEW VLM read. Returns the posture to feed fusion; mutates
    history (a deque of the last n real reads) in place. A None / phone-only read
    does not count and leaves the stable value untouched. The posture only moves
    once the last n reads all agree, so an alternating T/A scene just HOLDs."""
    if label not in ("T", "A", "B"):     # None or stale: don't let it reset the run
        return stable
    history.append(label)
    while len(history) > n:
        history.popleft()
    if len(history) == n and all(l == history[0] for l in history):
        return history[0]
    return stable


def main():
    from live_passive import (
        analyse, enhance_if_dark, SMOOTH_SECONDS, SWITCH_RATIO, MIN_VOTES,
    )

    os.makedirs(SNAP_DIR, exist_ok=True)

    act = Actuator()
    lcd = LcdDisplay(ser=act.ser)            # same Arduino drives LEDs + screen
    appl = list(FUSED_APP["C"])              # one shared appliance state vector
    act.set(*appl)

    cam_index = camera.find_index()
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {cam_index}.")

    print(f"Live integrated system on camera {cam_index}. Passive VLM: {VLM_NAME}")
    print("Hold a hand UP (fingers up) = ACTIVE gestures. Otherwise PASSIVE. 'q' quits.\n")

    # --- VLM background worker: classify the latest frame, store the result ---
    vlm = {"label": None, "phone": "", "latency": "", "ts": 0.0, "pose_ctx": None,
           "person_ts": 0.0}                 # last time the VLM described a person
    shared = {"frame": None, "want": False, "stop": False, "pose_ctx": None}
    vlm_lock = threading.Lock()

    def vlm_worker():
        next_ok = 0.0
        while not shared["stop"]:
            if shared["want"] and shared["frame"] is not None and time.time() >= next_ok:
                f = shared["frame"]
                ctx = shared["pose_ctx"]     # the pose reading this frame showed
                fh, fw = f.shape[:2]
                if fw > VLM_WIDTH:           # downscale: the main latency lever
                    f = cv2.resize(f, (VLM_WIDTH, int(fh * VLM_WIDTH / fw)))
                okj, buf = cv2.imencode(".jpg", f)
                if okj:
                    try:
                        ans, elapsed = ask(buf.tobytes(), VLM_PROMPT)
                        lab, ph = parse_label(ans), parse_phone(ans)
                        if lab in ("T", "A", "B", "C"):
                            with vlm_lock:
                                vlm["label"], vlm["phone"] = lab, ph
                                vlm["pose_ctx"] = ctx
                                if lab in ("T", "A", "B"):
                                    vlm["person_ts"] = time.time()
                                vlm["latency"], vlm["ts"] = round(elapsed, 1), time.time()
                            log_row(time=time.strftime("%H:%M:%S"), mode="VLM",
                                    vlm=lab, phone=ph, vlm_latency_s=round(elapsed, 1))
                    except Exception as e:                      # keep the loop alive
                        print("VLM worker error:", e)
                    next_ok = time.time() + VLM_MIN_INTERVAL
            time.sleep(0.3)

    threading.Thread(target=vlm_worker, daemon=True).start()

    mode = "PASSIVE"
    last_hand_time = 0.0
    last_person_time = 0.0
    pose_ts = 0                              # strictly-increasing ms for pose VIDEO mode

    window = deque()                         # passive smoothing (holds fused labels)
    committed = "C"
    leaving_latch = False                    # fist "leaving": hold all-off until C

    tv_on = lights_on = False                # active gesture state
    recent = deque(maxlen=CONFIRM_FRAMES)
    armed = True
    candidate = "none"
    hold_start = 0.0
    none_start = None
    stable = "none"
    progress = 0.0
    v = None                                 # latest VLM label, for the overlay
    vlm_stable = None                        # posture after debounce (fed to fusion)
    vlm_hist = deque()                        # last N distinct VLM reads
    last_vts = -1.0                           # ts of the last read we debounced
    vlm_phone = ""
    vlm_lat = ""
    vctx = None                              # pose reading the VLM was judging
    snap = None                              # set on a decision -> saved after overlay
    last_relay = 0.0                         # last write of live_frame.jpg
    hold_until = [0.0] * NAPP                # per-appliance gesture override expiry
    frame_i = 0
    pose_label, people = None, []            # cached between pose runs
    gesture_seen_time = 0.0                  # last time a gesture was being held

    # max_num_hands=2: with two people in the room a single tracked hand locked
    # onto the wrong person (the friend holding a phone) and the raised command
    # hand was never seen at all.
    # 0.5, not 0.7: across a whole room your hand is only a few dozen pixels and
    # 0.7 never fired once in a 19-minute run.
    with mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.5,
                        min_tracking_confidence=0.5) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            t_frame = time.time()            # RO3 clock starts at the camera frame
            act_ms = None                    # set when this frame writes to serial
            frame = enhance_if_dark(frame)   # rescue dark rooms
            now = time.time()
            h, w = frame.shape[:2]
            raw_frame = frame.copy()         # clean, before any overlay (eval capture)

            # DETECTION runs on a downscaled copy to leave GPU for Ollama; the
            # DISPLAY keeps full resolution. Shrinking the displayed frame made
            # the overlay text huge and the picture blurry on a Retina screen.
            proc, scale = frame, 1.0
            if w > PROC_WIDTH:
                proc = cv2.resize(frame, (PROC_WIDTH, int(h * PROC_WIDTH / w)))
                scale = w / float(PROC_WIDTH)

            # --- pose in BOTH modes (the room is always sensed), every Nth frame ---
            frame_i += 1
            if frame_i % POSE_EVERY == 0 or pose_label is None:
                pose_ts += 40
                pose_label, found = analyse(proc, pose_ts)    # boxes in proc coords
                people = [(tuple(int(v * scale) for v in box), post, ratio)
                          + (head_y * scale,)
                          for box, post, ratio, head_y in found]   # -> display coords
            confirmed = True                 # see PRESENCE_CONFIRM_SECONDS
            if PRESENCE_CONFIRM_SECONDS is not None:
                with vlm_lock:
                    confirmed = now - vlm["person_ts"] <= PRESENCE_CONFIRM_SECONDS
            present = bool(people) and confirmed
            real_people = people if present else []   # unconfirmed boxes: phantoms
            if present:
                last_person_time = now

            # Hands runs on the FULL-RES frame. At 960px a hand raised across the
            # room is only ~30px and was never detected: zero gestures fired in an
            # 8.5-minute run. Hands is much lighter than the pose model, so this
            # costs little, and pose keeps the downscaled input.
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hres = hands.process(rgb)
            # A RAISED hand ENTERS active mode; once there, ANY visible hand can
            # gesture. Requiring the hand to stay above the head to classify too
            # meant that lowering it to make a peace sign dropped the hand and no
            # gesture ever registered.
            hand_lms = None          # any detected hand -> used for GESTURING
            ctl = False              # strict raised hand -> used to ENTER ACTIVE
            hand_dbg = "no hand seen"
            for cand_hand in (hres.multi_hand_landmarks or []):
                if hand_lms is None:
                    hand_lms = cand_hand
                ok_hand, why = control_hand_debug(cand_hand.landmark, real_people, w, h)
                hand_dbg = why
                if ok_hand:
                    hand_lms, ctl = cand_hand, True
                    break
            # Keep ACTIVE alive only while a GESTURE-SHAPED hand (fingers up) is
            # visible. "Any visible hand" kept it alive forever on a hand resting
            # on the table or keyboard.
            if ctl or (mode == "ACTIVE" and hand_lms is not None
                       and hand_is_upright(hand_lms.landmark)):
                last_hand_time = now

            prev_mode = mode
            mode = decide_mode(mode, ctl, now, last_hand_time)
            if (mode == "ACTIVE" and prev_mode == "ACTIVE"
                    and now - gesture_seen_time > ACTIVE_IDLE_SECONDS):
                mode, last_hand_time = "PASSIVE", 0.0      # idle: hand back to auto

            if mode == "ACTIVE":
                shared["want"] = False       # no VLM while a hand is driving
                with vlm_lock:               # ...but someone gesturing is present:
                    vlm["person_ts"] = now   # without this, presence confirmation
                                             # expired during gestures and the room
                                             # blinked to C on returning to passive
                if prev_mode != "ACTIVE":    # seed from what is actually lit, so
                    lights_on = bool(appl[0])  # entering gesture control no longer
                    tv_on = bool(appl[2])      # blanks the appliances
                    recent.clear()
                    gesture_seen_time = now
                    # every entry is logged + snapshotted with the gate that let it
                    # in, so a false activation can be diagnosed from evidence
                    log_row(time=time.strftime("%H:%M:%S"), mode="ACTIVE_ENTER",
                            people=len(real_people), profile=hand_dbg)
                    snap = "enter"

                raw = "none"
                if hand_lms:
                    mp_draw.draw_landmarks(
                        frame, hand_lms, mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style())
                    raw = classify_gesture(hand_lms.landmark)

                recent.append(raw)
                stable = recent[0] if (len(recent) == CONFIRM_FRAMES
                                       and len(set(recent)) == 1) else "none"
                if stable != "none":
                    gesture_seen_time = now
                progress = 0.0
                if stable == "none":
                    candidate = "none"
                    if none_start is None:
                        none_start = now
                    elif now - none_start >= REARM_SECONDS:
                        armed = True
                else:
                    none_start = None
                    if stable != candidate:
                        candidate, hold_start = stable, now
                    else:
                        held = now - hold_start
                        progress = min(held / HOLD_SECONDS, 1.0)
                        if armed and held >= HOLD_SECONDS:
                            tv_on, lights_on = apply(stable, tv_on, lights_on)
                            if stable == "fist":
                                appl[1] = appl[3] = appl[4] = 0   # all-off: fan, lamp, AC too
                                leaving_latch = True # "leaving": stay off until room empties
                            else:
                                leaving_latch = False  # a staying gesture cancels the latch
                            appl[0], appl[2] = int(lights_on), int(tv_on)
                            for i in GESTURE_HOLDS.get(stable, []):
                                hold_until[i] = now + OVERRIDE_SECONDS
                            decide_ms = since_ms(t_frame)
                            act_ms = timed_set(act, appl)
                            log_row(time=time.strftime("%H:%M:%S"), mode="ACTIVE",
                                    people=len(people), profile=stable,
                                    light=appl[0], fan=appl[1], tv=appl[2],
                                    lamp=appl[3], ac=appl[4],
                                    decide_latency_ms=decide_ms,
                                    actuate_latency_ms=act_ms)
                            snap = stable
                            armed, candidate = False, "none"

            else:  # PASSIVE
                if prev_mode == "ACTIVE":
                    window.clear()
                    # Log the ACTIVE->PASSIVE flip so the app/LCD don't freeze on
                    # ACTIVE until the next profile change (can be minutes away).
                    log_row(time=time.strftime("%H:%M:%S"), mode="PASSIVE",
                            people=len(people), profile=committed,
                            light=appl[0], fan=appl[1], tv=appl[2],
                            lamp=appl[3], ac=appl[4])

                # feed the VLM a clean frame when a person is present (upright -> it
                # splits T/A; lying -> it only supplies the phone flag, which the
                # fusion ignores but we log as scene metadata).
                # run the VLM whenever ANYONE is present. This used to be
                # ("A","B"), so once pose learned to report T the VLM stopped
                # running entirely while the room was transitional.
                shared["want"] = pose_label != "C"
                if shared["want"]:
                    shared["frame"] = proc.copy()       # clean (before overlays)
                    shared["pose_ctx"] = pose_label     # what pose saw in it
                    with vlm_lock:
                        v, vlm_phone = vlm["label"], vlm["phone"]
                        vlm_lat, vts, vctx = vlm["latency"], vlm["ts"], vlm["pose_ctx"]
                    if now - vts > VLM_STALE_SECONDS:   # too old to trust
                        v = None
                    elif vts != last_vts:               # a NEW distinct VLM read
                        last_vts = vts
                        vlm_stable = debounce_vlm(v, vlm_hist, vlm_stable)
                else:
                    v, vlm_phone, vlm_lat, vctx = None, "", "", None

                # Feed fusion the DEBOUNCED posture, not the raw read: raw v stays
                # in the log as the honest VLM evidence, but a single flip no
                # longer moves the LEDs.
                feed = vlm_stable if v in ("T", "A", "B") else None
                fused = fuse_label(pose_label if present else "C", feed, committed)
                window.append((now, fused))
                while window and now - window[0][0] > SMOOTH_SECONDS:
                    window.popleft()
                cand, votes = Counter(l for _, l in window).most_common(1)[0]

                # presence hysteresis: a momentary pose dropout must NOT black the
                # room. Only call it empty after a sustained absence.
                if cand == "C" and now - last_person_time < EMPTY_SECONDS:
                    cand = committed

                switched = (cand != committed and votes >= MIN_VOTES
                            and votes >= SWITCH_RATIO * len(window))
                if switched:
                    committed = cand
                    hold_until = [0.0] * NAPP      # context changed -> auto resumes

                # Drive every appliance that is NOT currently held by a gesture.
                # Held ones keep the user's choice until their hold expires, so a
                # gesture is respected without disabling the automation forever.
                # Fist "leaving" latch: hold everything off until the room actually
                # empties (C), so a fist on the way out is not undone 6 s later when
                # ACTIVE drops to PASSIVE and re-commits a profile.
                if leaving_latch and committed != "C":
                    target = leave_target(True, committed)
                else:
                    leaving_latch = False
                    target = leave_target(False, committed)
                target = resolve_hold(target, appl)   # "No change" keeps what is on
                if any(now >= hold_until[i] and appl[i] != target[i] for i in range(NAPP)):
                    for i in range(NAPP):
                        if now >= hold_until[i]:
                            appl[i] = target[i]
                    act_ms = timed_set(act, appl)

                if switched:
                    print(f"[{time.strftime('%H:%M:%S')}] passive -> {committed}: "
                          f"{FUSED_ACT[committed]}")
                    log_row(time=time.strftime("%H:%M:%S"), mode="PASSIVE",
                            people=len(people), pose=pose_label, vlm=v or "",
                            phone=vlm_phone, vlm_latency_s=vlm_lat, profile=committed,
                            light=appl[0], fan=appl[1], tv=appl[2],
                            lamp=appl[3], ac=appl[4],
                            decide_latency_ms=since_ms(t_frame),
                            actuate_latency_ms="" if act_ms is None else act_ms)
                    snap = committed

            # --- people boxes drawn in BOTH modes, so detection is always visible ---
            for (x1, y1, x2, y2), post, ratio, _ in people:  # display coords
                c = (0, 200, 255) if post == "lying" else (0, 255, 0)
                if not present:
                    c, post = (128, 128, 128), "unconfirmed"   # VLM sees nobody
                cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
                # the ratio is shown so STAND_RATIO can be calibrated by eye
                cv2.putText(frame, f"{post} {ratio:.1f}", (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)

            lcd.show(*status_lines(mode, committed, stable, appl))   # model-house screen

            # --- overlay ---
            mcolor = (0, 200, 255) if mode == "ACTIVE" else (0, 255, 0)
            cv2.putText(frame, f"MODE: {mode}   ({len(people)} ppl)", (15, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, mcolor, 3)
            if mode == "ACTIVE":
                cv2.putText(frame, GESTURE_LABEL[stable], (15, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                tag = f"{committed}: {FUSED_NAME[committed]}"
                held = max(hold_until) - now         # why the LEDs != the profile
                if held > 0:
                    tag += f"  [MANUAL {held:.0f}s]"
                cv2.putText(frame, tag, (15, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            # the appliance truth = exactly what the three LEDs are doing
            on = lambda b: "ON " if b else "OFF"
            cv2.putText(frame, " ".join(f"{n.upper()}:{on(v)}"
                                        for n, v in zip(APPLIANCES, appl)),
                        (15, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            if mode == "PASSIVE" and shared["want"]:
                tag = f"VLM: {v or 'thinking...'}"
                if vlm_phone:
                    tag += f"   phone={vlm_phone}"
                cv2.putText(frame, tag, (15, 152),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
            cv2.putText(frame, f"HAND: {hand_dbg}", (15, h - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 0) if hand_dbg == "OK" else (0, 165, 255), 2)
            if mode == "ACTIVE" and progress > 0 and armed:
                cv2.rectangle(frame, (15, 165), (315, 185), (80, 80, 80), 1)
                cv2.rectangle(frame, (15, 165), (15 + int(300 * progress), 185),
                              (0, 255, 0), -1)

            if snap:          # annotated evidence frame for this decision
                cv2.imwrite(os.path.join(
                    SNAP_DIR, f"{time.strftime('%H%M%S')}_{mode}_{snap}.jpg"), frame)
                snap = None

            # Relay the annotated frame for the phone app (state_server serves it
            # at /frame.jpg). Written temp-then-rename so the server never reads a
            # half-written file, downscaled because it crosses WiFi twice a second.
            # Its mtime is also the app's heartbeat: decisions are change-triggered,
            # so a quiet log alone cannot tell "nobody moved" from "system stopped".
            if now - last_relay >= FRAME_EVERY:
                last_relay = now
                small = (cv2.resize(frame, (PROC_WIDTH, int(h * PROC_WIDTH / w)))
                         if w > PROC_WIDTH else frame)
                if cv2.imwrite(FRAME_TMP, small, [cv2.IMWRITE_JPEG_QUALITY, 70]):
                    os.replace(FRAME_TMP, FRAME_PATH)
                # clean frame (no overlays) at higher quality, for on-demand eval
                # capture from the web app (state_server serves /capture from it).
                small_raw = (cv2.resize(raw_frame, (PROC_WIDTH, int(h * PROC_WIDTH / w)))
                             if w > PROC_WIDTH else raw_frame)
                if cv2.imwrite(RAW_TMP, small_raw, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                    os.replace(RAW_TMP, RAW_PATH)

            if SHOW_WINDOW:
                cv2.imshow("live integrated system", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if ord("0") <= key <= ord("9"):
                    idx = key - ord("0")
                    if idx not in camera.allowed_indices():
                        print(f"Camera index {idx} not available; staying put.")
                    else:
                        cap.release()
                        cap = cv2.VideoCapture(idx)
                        print(f"Switched to camera index {idx}.")

    shared["stop"] = True
    lcd.close()
    act.close()
    cap.release()
    cv2.destroyAllWindows()


class _P:                                    # tiny landmark stand-in for the selftest
    def __init__(self, x, y):
        self.x, self.y = x, y


def _fake_hand(wrist_y, knuckle_y, x=0.5):
    lm = [_P(x, wrist_y) for _ in range(21)]
    for i in (5, 9, 17):
        lm[i] = _P(x, knuckle_y)
    return lm


def _selftest():
    """Router + fusion + control-hand truth tables (no camera / no VLM needed)."""
    assert decide_mode("PASSIVE", True, 100.0, 0.0) == "ACTIVE"      # hand -> active
    assert decide_mode("ACTIVE", False, 100.0, 99.5) == "ACTIVE"     # within grace -> held
    assert decide_mode("ACTIVE", False, 103.0, 100.0) == "PASSIVE"   # past grace -> passive
    assert decide_mode("PASSIVE", False, 103.0, 100.0) == "PASSIVE"  # stays passive

    # presence gate: pose says empty -> C, whatever the VLM claims
    assert fuse_label("C", "T", "A") == "C"
    assert fuse_label("C", "A", "A") == "C"
    # someone present + a VLM answer -> the VLM decides the posture, and pose's
    # own posture reading is ignored entirely (it is unreliable in this room)
    assert fuse_label("A", "T", "A") == "T"
    assert fuse_label("T", "A", "T") == "A"
    assert fuse_label("B", "A", "B") == "A"
    assert fuse_label("T", "B", "A") == "B"
    # no VLM answer yet -> HOLD the current profile, never guess from pose.
    # This is what stops the LEDs switching twice for one event.
    assert fuse_label("T", None, "A") == "A"
    assert fuse_label("B", None, "A") == "A"
    assert fuse_label("A", None, "B") == "B"
    # somebody just arrived (we were empty) and no answer yet -> transitional
    assert fuse_label("A", None, "C") == "T"
    # VLM "empty room" while pose sees somebody is never applied
    assert fuse_label("A", "C", "A") == "A"

    # posture debounce: N=2 reads must agree before the posture moves
    h = deque()
    assert debounce_vlm("A", h, None, n=2) is None          # one read: not enough
    assert debounce_vlm("A", h, None, n=2) == "A"           # two agree -> switch
    assert debounce_vlm("T", h, "A", n=2) == "A"            # one dissent: hold A
    assert debounce_vlm("A", h, "A", n=2) == "A"            # T,A -> no 2 in a row
    assert debounce_vlm("T", h, "A", n=2) == "A"            # A,T -> still holds
    assert debounce_vlm("T", h, "A", n=2) == "T"            # T,T -> now switches
    assert debounce_vlm(None, h, "T", n=2) == "T"           # None read: ignored
    assert list(h) == ["T", "T"]                            # None didn't enter history

    # fist "leaving" latch: all-off while present, resumes once the room empties
    assert leave_target(True, "A") == (0,) * NAPP           # latched + present -> off
    assert leave_target(True, "T") == (0,) * NAPP
    assert leave_target(True, "C") == FUSED_APP["C"]        # empty -> normal (all off)
    assert leave_target(False, "A") == FUSED_APP["A"]       # no latch -> normal profile

    # a hand high in the frame with nobody matched IS a command
    assert is_control_hand(_fake_hand(0.3, 0.1), [], 1000, 1000)
    # a hand on the keyboard (knuckles not above the wrist) is NOT - this is the
    # bug that pinned the system in ACTIVE while sitting at the desk
    assert not is_control_hand(_fake_hand(0.90, 0.88), [], 1000, 1000)
    # people entries: (box, posture, ratio, head_y). The hand's knuckles sit at
    # y=300 in every case below.
    # fingers up near the chin are NOT a command: knuckles (300) below the eyes
    # (250). The accidental OPEN PALM that switched the TV on 2026-11-14.
    chin = [((300, 200, 700, 1300), "sitting", 0.0, 250)]
    assert not is_control_hand(_fake_hand(0.5, 0.3), chin, 1000, 1000)
    # knuckles above the face IS a command
    raised = [((300, 200, 700, 1300), "sitting", 0.0, 400)]
    assert is_control_hand(_fake_hand(0.5, 0.3), raised, 1000, 1000)
    # REGRESSION: the raised hand stretches the box top up to the fingertips
    # (y1=100). Comparing with the box top rejected every well-tracked raised
    # hand; comparing with the face (400) accepts it.
    stretched = [((300, 100, 700, 1300), "sitting", 0.0, 400)]
    assert is_control_hand(_fake_hand(0.5, 0.3), stretched, 1000, 1000)
    # a phantom "person" on a chair has its "face" low (650); the hand clears it
    # but not the real person's face (250): it must NOT count as raised
    phantom = [((300, 600, 700, 900), "lying", 0.0, 650),
               ((300, 200, 700, 1300), "sitting", 0.0, 250)]
    assert not is_control_hand(_fake_hand(0.5, 0.3), phantom, 1000, 1000)

    # engine wiring: Moondream by default, and `qwen` really swaps everything
    assert ask is moondream_vlm.ask and VLM_NAME == moondream_vlm.MODEL
    assert PRESENCE_CONFIRM_SECONDS == 10.0 and VLM_MIN_INTERVAL == 1.0
    use_qwen()
    assert ask is classify_passive.ask and parse_label is classify_passive.parse_label
    assert PRESENCE_CONFIRM_SECONDS is None and VLM_MIN_INTERVAL == 3.0

    # Column order the dashboard + older parsers rely on: first 11 fixed, then
    # the latency fields, then lamp/ac appended LAST (5-appliance logging, so a
    # 3-appliance parser reading light/fan/tv by index still works).
    assert LOG_FIELDS[:11] == ["time", "mode", "people", "pose", "vlm", "phone",
                               "vlm_latency_s", "profile", "light", "fan", "tv"]
    assert LOG_FIELDS[-2:] == ["lamp", "ac"]
    assert {"decide_latency_ms", "actuate_latency_ms"} <= set(LOG_FIELDS)
    calls = []
    ms = timed_set(type("A", (), {"set": lambda self, *a: calls.append(a)})(), [1, 0, 1])
    assert calls == [(1, 0, 1)] and isinstance(ms, float) and ms >= 0
    assert since_ms(time.time()) >= 0

    # The relay's temp name must stay a .jpg: OpenCV chooses its encoder from the
    # extension, and a ".tmp" suffix made imwrite throw and killed the whole run.
    assert FRAME_TMP.endswith(".jpg") and FRAME_TMP != FRAME_PATH

    # A log with an older header is rotated aside, not appended to or destroyed.
    import contextlib, io as _io, tempfile
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(_io.StringIO()):
        p = os.path.join(d, "live_log.csv")
        with open(p, "w") as f:
            f.write("time,mode,profile\n10:00:00,PASSIVE,A\n")
        assert rotate_stale_log(p) is True
        assert not os.path.exists(p)                       # moved out of the way
        kept = [n for n in os.listdir(d) if n != "live_log.csv"]
        assert len(kept) == 1 and open(os.path.join(d, kept[0])).read().endswith("PASSIVE,A\n")
        with open(p, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS).writeheader()
        assert rotate_stale_log(p) is False                # current header: left alone

    assert set(FUSED_APP) == {"T", "A", "B", "C"}            # every profile mapped
    assert all(len(v) == NAPP for v in FUSED_APP.values())   # no short vector
    assert FUSED_APP["C"] == (0,) * NAPP
    # the two deliberate policy changes, pinned so they cannot regress silently
    assert FUSED_APP["A"][2] == 0, "sitting must NOT switch the TV on"
    assert FUSED_APP["T"][1] == 1, "standing must NOT switch the fan off"
    # HOLD resolves against what is currently on, and only for HOLD entries
    assert resolve_hold((1, 1, HOLD, 0, HOLD), [0, 0, 1, 1, 0]) == (1, 1, 1, 0, 0)
    assert resolve_hold((1, 1, HOLD, 0, HOLD), [0, 0, 0, 1, 1]) == (1, 1, 0, 0, 1)
    assert resolve_hold(FUSED_APP["C"], [1, 1, 1, 1, 1]) == (0,) * NAPP
    print("selftest ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "selftest" in args:
        _selftest()
    else:
        if "qwen" in args:
            use_qwen()
        if "headless" in args:
            SHOW_WINDOW = False       # no preview window: can't be q-quit or closed
            print("headless: no preview window; stop with Ctrl-C or by killing the process")
        main()
