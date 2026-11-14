# Passive engine evaluation: VLM selection (Moondream2 vs Qwen3-VL)

RO3 evaluation record for the passive classifier. Documents the change from
Moondream2 to Qwen3-VL-8B, the prompt-strategy experiments, and the dataset
recapture. Raw per-frame data is in `classify_results.csv` (overwritten each run).

- **Dates:** 2026-11-12 (model swap, dataset recapture), 2026-11-14 (model
  selection, thinking toggle, contention study)
- **Live engine (decided 2026-11-14):** `moondream` with the prompt "Describe
  the people in this image.", 60-token cap, 640 px, ~2 s cadence. Default in
  `live_system.py` via `moondream_vlm.py` (Runs 9-13 were made with the
  equivalent runner, archived as `archive/live_moondream_runner.py`). Qwen
  (`qwen3-vl:4b`, thinking off, 3 s cadence): `python live_system.py qwen`.
- **Hardware:** MacBook, Apple M5, 24 GB RAM. Local inference via Ollama.
- **Classifier:** `classify_passive.py` (offline, reads `frames/profile_*.jpg`).
- **Profiles:** T transitional/standing, A active/sitting, B resting/lying,
  C unoccupied.
- **Metric:** activity classification accuracy over the labelled frames; mean
  inference latency per frame (wall clock, includes model thinking).

## Datasets

| Set | Source | Frames | Notes |
|---|---|---|---|
| Old | Mac webcam, close-up | 12 (3/profile) | archived in `frames/old_macwebcam/`. The 3 "C" frames were **mislabelled** - a person was lying in bed, so they are not unoccupied. |
| New | Mounted iPhone 12, room scene | 12 (3/profile) | recaptured via `capture_frames.py` from the demo camera position; C frames are genuinely empty. Current `frames/`. |

## Runs

### Run 0 - Moondream2 (prior baseline, historical)
- Method: two-stage "describe this image" + keyword scan (the only thing that
  Moondream build answered).
- Result: reported 100% on the old frames, ~1-2 s/frame.
- Caveat found later: that 100% is unreliable. Moondream scored the "C" frames
  correct partly by **failing to notice** the person lying in bed. A sharper
  model (below) does notice, which exposed the mislabelled data.

### Run 1 - Qwen3-VL-8B, old pipeline unchanged, old frames
- Method: model name swapped to `qwen3-vl:8b`, describe + keyword scan kept.
- **Accuracy: 58.3% (7/12). Latency: 62.4 s/frame.**

| actual \ pred | T | A | B | C | ? |
|---|---|---|---|---|---|
| T | 3 | 0 | 0 | 0 | 0 |
| A | 2 | 1 | 0 | 0 | 0 |
| B | 0 | 0 | 3 | 0 | 0 |
| C | 0 | 1 | 2 | 0 | 0 |

- Findings:
  - **Keyword-scan bug:** Qwen's captions said "seated upright"; the keyword map
    checked T (which listed "upright") before A ("sitting"), so sitting frames
    were mis-scored as T.
  - **Latency:** the "describe" prompt makes an 8B model write paragraphs; that
    generation is the 62 s cost.
  - **C frames:** Qwen correctly reports a person in the (mislabelled) C frames.

### Run 2 - Qwen3-VL-8B, direct one-letter prompt, output capped (failed)
- Method: single prompt "reply with one letter T/A/B/C", `num_predict=4`.
- **Accuracy: 0% (0/12). All replies empty, 0.43 s/frame.**
- Finding: **Qwen3-VL is a thinking model.** It emits hidden `<think>` tokens
  before the answer; a small `num_predict` is consumed entirely by thinking, so
  the answer letter is never produced. Do **not** cap `num_predict`.

### Run 3 - Qwen3-VL-8B, direct one-letter prompt, uncapped, old frames
- Method: same prompt, `OPTIONS={"temperature":0}` (no cap).
- **Accuracy: 75% (9/12). Latency: 2.64 s/frame.**

| actual \ pred | T | A | B | C | ? |
|---|---|---|---|---|---|
| T | 3 | 0 | 0 | 0 | 0 |
| A | 0 | 3 | 0 | 0 | 0 |
| B | 0 | 0 | 3 | 0 | 0 |
| C | 0 | 0 | 3 | 0 | 0 |

- Finding: **every miss is a mislabelled C frame** (person in bed -> correctly B).
  On the 9 correctly-labelled frames the model is **9/9 = 100%**. Latency dropped
  from 62 s to 2.6 s purely from the prompt change (one letter vs paragraphs).

### Run 4 - Qwen3-VL-8B, direct one-letter prompt, NEW iPhone-12 room frames
- Method: same classifier, new recaptured dataset (real empty C).
- **Accuracy: 100% (12/12). Latency: 15.4 s/frame.**

| actual \ pred | T | A | B | C | ? |
|---|---|---|---|---|---|
| T | 3 | 0 | 0 | 0 | 0 |
| A | 0 | 3 | 0 | 0 | 0 |
| B | 0 | 0 | 3 | 0 | 0 |
| C | 0 | 0 | 0 | 3 | 0 |

- Per-frame latency: A 11-14 s, B 13 s, C 14-18 s, T 19-22 s.
- Finding: perfect classification at demo distance, including the empty room.
  Latency rose from 2.6 s to 15.4 s because the mounted-phone room scene is
  larger and busier than the webcam close-up (more image to encode, longer
  reasoning).

## Model selection, 2026-11-14

All runs below use the **current** 12 labelled iPhone-12 room frames
(`frames/profile_*.jpg`, 1920x1080, captured 2026-11-12), downscaled to 640 px
before inference. The archived Mac-webcam set was NOT used.

### Run 5 - does disabling "thinking" cost accuracy?

Qwen3-VL reasons before answering. For a one-letter classification that
reasoning is pure cost, so `think=False` was measured against the default on 6
frames (A and B profiles):

| thinking | accuracy | mean latency |
|---|---|---|
| ON (default) | 6/6 | 19.6 s |
| **OFF** | **6/6** | **10.0 s** |

**Half the latency, no accuracy loss.** Thinking is disabled in
`classify_passive.THINK`. Note this is the opposite failure to Run 2: capping
`num_predict` breaks a thinking model, but switching thinking off cleanly does
not.

### Run 6 - model comparison, 12 frames

`think=False` for the Qwen models. Models were swapped between sets, so these
absolute latencies include some model-load/swap overhead.

| model | size | prompt | accuracy | mean latency |
|---|---|---|---|---|
| **qwen3-vl:4b** | 3.3 GB | 1 letter | **12/12 (100%)** | 24.4 s |
| qwen3-vl:8b | 6.2 GB | 1 letter | 12/12 (100%) | 31.4 s |
| moondream | 1.7 GB | 1 letter | 3/12 (25%) | 3.6 s |

Steady-state re-measurement (one warm-up call discarded, so model-load time is
excluded - this is what the live system experiences):

| model | accuracy | mean latency |
|---|---|---|
| qwen3-vl:2b | 11/12 (92%) | 19.1 s |
| **qwen3-vl:4b** | **12/12 (100%)** | 20.0 s |

**2b is no faster than 4b.** A 1.9 GB model and a 3.3 GB model take the same
time, which means **latency is dominated by the vision encoder, not the language
model size**. Shrinking the model further buys nothing.

### Run 7 - Moondream on its OWN pipeline (fair comparison)

Run 6 gave Moondream the one-letter prompt designed for Qwen, which it cannot
follow (it is not instruction-tuned; the original project pipeline used
"Describe this image." + a keyword scan). Re-tested on its native pipeline,
same current frames, with the keyword precedence bug from Run 1 fixed:

**7/12 = 58%, mean 34.4 s** (range 3.0 s - 93.8 s).

| actual | predicted |
|---|---|
| A | A, A, A |
| T | T, T, T |
| B | ?, ?, B |
| C | ?, ?, ? |

- A fair prompt more than doubled Moondream's score (25% -> 58%), so the Run 6
  figure understated it. It still loses on **both** accuracy and latency.
- **All three unoccupied frames failed.** Moondream describes the room
  ("a cluttered dorm room with a bed...") but never states that nobody is
  present, so a keyword scan cannot conclude "empty". *Absence of evidence is
  not evidence of absence* - a structural flaw in describe+keyword, not a
  tuning problem. For an energy system this is the worst failure mode: the room
  never switches off.
- **Two of three lying frames failed**: it described the furniture and missed
  the person on the bed entirely.
- This also explains Run 0's suspicious "100%": that score came from a weaker
  model agreeing with mislabelled data, not from competence.

### Run 8 - the same model is 4x slower inside the live system

Identical model, prompt and frames measured two ways:

| context | mean latency |
|---|---|
| standalone benchmark | 10.0 s |
| inside `live_system.py` | **44 s** (range 35-69 s, climbing) |

**Cause: GPU contention.** MediaPipe Pose (full model, 4 poses) plus Hands were
running on every 1920x1080 frame on the same Metal GPU that Ollama needs. The
two were starving each other, which also explains the latency *climbing* over a
run rather than staying flat.

Fixes applied: detection runs on a 960 px copy (display stays full resolution),
pose runs every 2nd frame, and the VLM is throttled to the documented 3 s
cadence instead of re-inferring immediately.

| | mean latency |
|---|---|
| before | ~44 s, climbing to 69 s |
| after (qwen3-vl:4b) | **~12-19 s, stable** |

**Finding for the thesis: on a single-GPU edge device, how the vision pipeline
is scheduled matters more than which VLM is chosen.** Model selection bought
~35%; fixing contention bought ~70%.

### Decision (afternoon, superseded below)

**`qwen3-vl:4b`, `think=False`, 640 px input, 3 s cadence.** Best accuracy
(100%), better latency than 8b, half the memory, and the smaller 2b is both
less accurate and no faster. Revisited in the evening: see Runs 9-13, where a
better prompt made Moondream as accurate on these frames at ~1/25 of the latency.

## Moondream revisited, 2026-11-14 evening

Context: by this point the live system used pose for PRESENCE only and the VLM
for POSTURE (T/A/B), holding the profile while no answer exists. In that design
the VLM never has to declare an empty room on its own, so the Run 7 benchmark,
which counted C frames, overstated the gap between the models. Moondream was
re-tested in a separate runner, `live_moondream.py`, which reuses the
`live_system.py` loop unchanged and swaps only the VLM call.

### Run 9 - capping Moondream's output, offline and live

Moondream is not a thinking model, so its description can be cut short safely
(unlike Qwen, Run 2). The posture word appears in the first sentence.

| | accuracy (12 frames) | mean latency |
|---|---|---|
| uncapped (Run 7) | 7/12 (58%) | 34.4 s (3.0-93.8 s) |
| `num_predict=60` | 7/12 (58%) | **1.0 s** |

Same accuracy, ~34x faster. On the cases the VLM actually decides live (a person
present, T/A/B): Qwen 9/9, Moondream 7/9 (A 3/3, T 3/3, B 1/3). First 2-minute
live run: **1.3 s mean over 23 calls**, every answer usable, and the standing
(T) and lying (B) frames checked by eye were both correct. In the T frame pose
said "sitting 2.5" (chair hiding the legs) and Moondream's T was right.

### Run 10 - live lying test, every judged frame saved

82 frames judged, 1.3 s mean. Labels: B 38, T 10, A 5, no-posture-word 29. Each
of the 29 was checked by eye:

| what was actually in frame | frames | Moondream |
|---|---|---|
| person lying on the bed | 12 | **ignored the person**, described furniture |
| person far back in the hallway | 8 | not mentioned |
| empty room | ~9 | correct |

So with "Describe this image." Moondream caught lying ~3 times in 4 (38 vs 12).
The misses did no harm live, because a missing label HOLDS the profile: the room
stayed on B throughout. One label was a false B: a description of a monitor and
desk with no person in it matched a posture word.

**Why the room never reached C:** pose kept detecting phantom "people" on the
chair and clothes rack. Measured on the saved frames, phantom poses score
landmark visibility and presence **~1.00, identical to real people**, so no pose
threshold can separate them. Pose had the final say on presence.

### Run 11 - direct questions do not work with this build

"Is there a person in this image? Answer yes or no.", "How many people...",
Moondream's own "Question: ... Answer:" format and "Is anyone in this room?"
all returned an **empty string** on every frame (70 frames). This matches the
original project note that this Moondream build only answers description
prompts.

### Run 12 - prompt wording decides whether "no person mentioned" means empty

70 frames with eye-checked ground truth: 41 empty, the 12 lying frames Run 10
missed, 11 other person frames, 6 hallway frames. Metric: is a person mentioned.

| prompt | empty (41) | lying, missed before (12) | other person (11) | hallway (6) |
|---|---|---|---|---|
| "Describe this image." | 41/41 | **1/12** | 9/11 | 0/6 |
| **"Describe the people in this image."** | **41/41** | **12/12** | **11/11** | **6/6** |
| "Describe the person in this image and what they are doing." | **0/41** (invents a person every time) | 12/12 | 11/11 | 6/6 |

The second prompt makes Moondream account for people without inventing them;
the third, which presupposes a person, hallucinates one in every empty frame.

A matcher bug also surfaced: substring matching read "p**laying** a video game"
as "laying", so every sitting frame scored as lying. Posture words are now
matched on word boundaries, and a posture word only counts when a person is
described.

Full T/A/B/C labels with the chosen prompt and fixed matcher: **68/70 at 0.82 s
per frame**. Empty 41/41, lying 12/12, the 12 labelled iPhone frames 12/12. Both
misses are hallway frames where Moondream reported two people (one standing,
one sitting), which are ambiguous ground truth.

| | qwen3-vl:4b | moondream, people prompt |
|---|---|---|
| 12 labelled iPhone frames | 12/12 | 12/12 |
| latency per frame (offline) | ~20 s | **0.8 s** |

### Run 13 - live result with the people prompt

Settings: `PRESENCE_CONFIRM_SECONDS=10` (room occupied only while the VLM
described a person in the last 10 s; this overrides pose phantoms),
`VLM_MIN_INTERVAL=1.0`, `EMPTY_SECONDS=8`.

| | before (Run 10 prompt, 60 s window) | Run 13 |
|---|---|---|
| leaving -> C | 68 s (60 + 8, by design) | **10 s, 18 s, 18 s** (3 exits) |
| VLM latency | 1.3-2.6 s | **1.87 s mean, 3.6 s max, 199 answers, flat** |
| false gesture activations | some (unlogged) | **0: 10 activations, 10 real gestures** |

10 s = pose also lost the person; 18 s = pose was seeing phantoms, so the 10 s
VLM window plus the 8 s hysteresis applied. Amir's stopwatch read ~10 s.

Known limit: the camera sees down the hallway, and Moondream does describe a
person there (6/6), so standing in the hallway counts as occupied. On the
cardboard model house there is no hallway.

### Run 14 - Moondream as the default engine (`python live_system.py`)

First run after making Moondream the default (`moondream_vlm.py`), Qwen not
loaded. Log kept at `live_log.csv` / `vlm_descriptions.csv` as sample data for
the app.

| | Run 14 |
|---|---|
| VLM latency | **1.05 s mean, 2.9 s max, 241 answers** (faster than Run 13's 1.87 s; Qwen was not resident) |
| leaving -> C | **18 s, 10 s, 8 s** (3 exits) |
| labels | B 88, T 57, A 37, C 17, no posture word 42 (held) |
| phone flag | "yes" in 57 answers; checked by eye on a lying-with-phone frame: correct |
| gesture activations | 7: 5 followed by a gesture, **2 false** |

Both false activations were a hand resting ON TOP of the head (knuckles above
the eyes, so the face test passes). Neither changed an appliance (only a
completed gesture does) and both timed out back to PASSIVE after 6 s. Left as a
known limitation: re-detecting the snapshots to measure a better threshold
failed on 4 of 7 stills, too little data to tune without risking real raises.

## Summary

| Run | Model | Prompt | Dataset | Accuracy | Latency |
|---|---|---|---|---|---|
| 0 | Moondream2 | describe + keyword | old | 100% (unreliable) | ~1-2 s |
| 1 | Qwen3-VL-8B | describe + keyword | old | 58.3% | 62.4 s |
| 2 | Qwen3-VL-8B | 1 letter, capped | old | 0% (empty) | 0.43 s |
| 3 | Qwen3-VL-8B | 1 letter, uncapped | old | 75% (100% on valid) | 2.64 s |
| 4 | Qwen3-VL-8B | 1 letter, uncapped | **new (phone, room)** | **100%** | **15.4 s** |
| 6 | Qwen3-VL-2B | 1 letter, no thinking | new | 92% | 19.1 s |
| 6 | **Qwen3-VL-4B** | **1 letter, no thinking** | **new** | **100%** | **20.0 s** |
| 6 | Qwen3-VL-8B | 1 letter, no thinking | new | 100% | 31.4 s |
| 7 | Moondream2 | describe + keyword (fair) | new | 58% | 34.4 s |
| 9 | Moondream2 | describe + keyword, 60-token cap | new | 58% | 1.0 s |
| 12 | **Moondream2** | **"Describe the people", 60-token cap, word-boundary matcher** | **new + 58 eye-checked live frames** | **100% (12/12); 68/70 overall** | **0.82 s** |

## Conclusions for the thesis

1. **Qwen3-VL-8B classifies the four profiles at 100%** at the demo camera
   position (Run 4). Accuracy objective met for the passive branch.
2. **Prompt strategy dominates edge latency, not model size.** Switching from a
   free-form "describe" prompt to a direct one-letter prompt cut latency ~24x
   (62 s -> 2.6 s on the same frames) at no accuracy cost on valid labels.
3. **Qwen3-VL is a thinking model**; capping output tokens silently breaks it.
4. **Dataset quality matters:** the old "C" frames contained a person; a capable
   VLM exposed the mislabelling that the weaker model had hidden. Recapturing a
   clean dataset from the real camera position fixed it.
5. **15 s/frame on the full room scene is too slow for live passive control at a
   3 s cadence.** This justifies the fusion design: the real-time pose engine
   carries presence and instant response, while the VLM refines the activity on
   a slower sample. See `docs/VLM_vs_Pose.md` and the decision-logic flowchart.

## Conclusions added 2026-11-14

6. **Prompt fairness matters when comparing models.** Scoring Moondream with a
   prompt style it cannot follow understated it by more than half (25% vs 58%).
   Each model was re-tested on the pipeline it was designed for before the
   comparison was treated as valid.
7. **Latency is dominated by the vision encoder, not parameter count.** 2B and
   4B measure the same; 8B is only ~50% slower despite being 4x the size of 2B.
8. **Scheduling beats model choice on edge hardware.** Contention between
   MediaPipe and Ollama cost more (44 s vs 10 s, 4.4x) than the entire
   difference between candidate models.
9. **Pose posture is not usable in this room; VLM posture is.** Three attempts
   failed (torso angle, foreshortening ratio, body-extent ratio: a man standing
   bent over a desk measured 4.4, inside the seated range). Across a live run
   pose flipped T/B/A every few seconds while the subject sat still, and the VLM
   answered A correctly nearly every time. Pose is therefore used for PRESENCE
   only - where it is reliable, and where the energy saving comes from - and
   posture is the VLM's job. See `live_system.fuse_label`.

## Conclusions added 2026-11-14 evening

10. **Prompt wording matters more than model size.** The same 1.7 GB Moondream
    went from 1/12 to 12/12 on lying frames by changing "Describe this image."
    to "Describe the people in this image." A prompt that presupposes a person
    made it invent one in 41/41 empty frames. Every prompt change needs an
    empty-room check, not only a person check.
11. **A benchmark must match the job the model does in the system.** Once pose
    took over presence, C frames no longer measured anything the VLM decides,
    and the "Moondream 58% vs Qwen 100%" result reversed on the live task.
12. **Pose cannot filter its own phantoms.** False poses on furniture score the
    same landmark confidence as people (~1.00). Presence therefore needs a
    second, independent signal; a fast VLM can provide it, a 20 s one cannot.
13. **Absence of evidence is only evidence of absence when the model was asked
    the right question.** "No person described" was unsafe with a scene prompt
    (it ignored people lying down) and safe with a people prompt (0 misses in
    29 person frames).

## Open items
- ~~Engine decision~~ Done: Moondream is the default (decided by Amir,
  2026-11-14).
- Formal RO3 protocol wants >=10 trials per response path (>=70 data points);
  this record uses 3/profile. Scale up for the final evaluation.
- Measure the pose engine on the same new dataset for a like-for-like
  pose-vs-VLM accuracy table (live evidence above is observational).
- Quantify the end-to-end response time per profile transition (camera to LED),
  which is the number RO3 actually asks for; VLM inference is only part of it.
