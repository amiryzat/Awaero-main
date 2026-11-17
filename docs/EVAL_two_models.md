# Two-VLM activity A/B (Moondream vs Qwen) - methodology + results

The experiment that decides which VLM the activity-based system should use, and
the evidence Chapter 4 reports. This file is the METHOD (written once); the
NUMBERS are generated into `eval_two_models_findings.md` and
`eval_two_models_results.csv` each time the eval runs, so they are never typed
by hand and cannot drift from the data.

## Research question
The redesigned system does not map bare posture to a fixed appliance set; it
interprets the **activity** (what the occupant is doing) and powers only what
that activity needs - e.g. the desk lamp only when working at the desk
(`FYP_Room_Activity_and_Appliance_Decision_Profiles.md`). Reading the activity
from the scene is harder than reading posture, so the question is:

> **Which VLM reads the room activity more accurately - the small, fast
> Moondream, or the larger Qwen3-VL - on the same frames?**

Four activities, each the ground-truth label of a captured frame:

| Activity | Meaning | Capture label |
|---|---|---|
| STUDYING | sitting, working at the desk | `studying` |
| RESTING | lying down / on the bed | `resting` |
| TRANSITIONAL | standing / moving around | `standing` |
| UNOCCUPIED | no person in frame | `empty` |

## Data collection (how the set is built)
- Frames come from the **mounted iPhone 12** (the camera the deployed system
  uses), not a hand-held phone, so the eval sees what production sees.
- Captured from the **web app Capture tab** on the phone: the occupant gets into
  a position, taps the matching activity, and `state_server.py` saves the
  **current frame** under that label into `eval_frames/` with a manifest
  (`labels.csv`: file, label, time).
- The saved frame is the **clean frame** (`live_raw.jpg`) - no bounding boxes or
  "LIGHT:ON" overlays - because a VLM asked to describe an annotated image would
  describe the annotations. A biased input invalidates the comparison.
- **Label correctness is reviewed**: the Capture tab shows every captured frame
  as a thumbnail grouped by label, with a delete button, so a mislabelled frame
  or one caught mid-movement is removed before scoring. Ground truth is the
  occupant's reviewed label.
- Target **>= 10 frames per activity** (40+ total). Below that a per-activity
  percentage is not trustworthy and the eval prints a warning.

## Method (how the two models are compared)
- The evaluator (`eval_two_models.py`) runs **both models over the identical
  frames**, **sequentially** - never at the same time - so there is no GPU
  contention and the comparison is clean (the live-run notes measured contention
  nearly quadrupling latency, so a simultaneous A/B would be meaningless).
- Both models get the **same prompt** and the **same token budget**, so the only
  variable is the model.
- The activity is **parsed from each model's description by the same rule**
  (`scene_activity.interpret`), not by the model emitting a label. So the parser
  is held constant and both models are judged identically.
- Before scoring, `check_data()` verifies every manifest frame exists, is a valid
  JPEG, is not a duplicate, and reports the per-label counts. Invalid rows are
  dropped and listed; the warnings are recorded in the findings.

## Prompt choice (and a finding in its own right)
Both models get `"Describe the people in this image."` - plural, with no "what
are they doing?" demand and no presupposition that a person exists.

This was NOT the first choice, and the reason is a finding worth a sentence in
Chapter 4. The first clean run used `"Describe THE PERSON in this image and what
they are doing."` Because that prompt **presupposes a person**, the small model
(Moondream) **hallucinated a person in every empty-room frame** ("there is a
person sitting at a desk using a laptop") and scored 0/10 on UNOCCUPIED - while
the larger model (Qwen) ignored the false premise and read the empty room
correctly. Swapping to the plural, non-presuppositional prompt removed the bias
and both models read empty rooms correctly. So: a leading prompt corrupts a
small VLM's output and the measurement; the instrument had to be validated, not
assumed. The numbers reported are from the neutral prompt.

## What is logged (every finding)
`eval_two_models_findings.md` (generated) records:
- dataset counts per activity + any data warnings;
- **overall accuracy** per model, and **per-activity recall** (so a model that is
  great at STUDYING but blind to RESTING is visible, not hidden in the average);
- the full **confusion matrix** per model (what each activity gets mistaken for);
- **unparsed count** (descriptions the parser could not classify);
- **model agreement** (how often the two predict the same activity) and the list
  of **disagreement frames** - the cases worth inspecting by eye;
- **latency** mean/max per model (offline - see the caveat below).

`eval_two_models_results.csv` (generated) records, for every frame and every
model: the raw description, the parsed activity, correct/wrong, and latency - so
any number in the findings can be traced to a frame and a description.

## Relationship to the live A/B (don't conflate them)
This offline test answers **scene understanding** only. Real-world **latency and
trial accuracy under load** are measured separately by two live runs
(`live_system.py` on Moondream, then `live_system.py qwen`), one at a time, with
each trial tagged by engine. Offline latency here is a lower bound (no contention,
warm model) and must be reported as such, not as the deployed latency.

## How to run
```bash
# 1. start the camera pipeline, capture >=10 frames per activity from the phone,
#    review and delete any bad ones in the Capture tab
python live_system.py
# 2. run the A/B
python eval_two_models.py          # writes the two generated files above
python eval_two_models.py selftest # scoring logic only (no models)
```

## Limitations (state these in the write-up)
- Single room, single occupant; the set reflects this room's scene, not every
  bedroom-study.
- Offline latency != deployed latency (no GPU contention here).
- The result is prompt-sensitive, especially for the smaller model (see "Prompt
  choice" above); the neutral prompt is the one reported, and the sensitivity is
  itself reported rather than hidden.
- The parser is a keyword rule over free-text descriptions; a model could read
  the scene correctly yet phrase it in words the parser misses. The unparsed
  count and the per-frame descriptions make that failure visible rather than
  silent.

## Results (2026-11-17, n=40, neutral prompt)
Dataset: 40 reviewed frames (studying/resting/standing/empty = 10/10/10/10).

| model | overall | STUDYING | RESTING | TRANSITIONAL | UNOCCUPIED | latency mean/max |
|---|---|---|---|---|---|---|
| **Moondream** | **97.5%** (39/40) | 90% | 100% | 100% | 100% | **1.9s** / 3.1s |
| **Qwen3-VL 4b** | **92.5%** (37/40) | 100% | 100% | 70% | 100% | 12.9s / 24.0s |

- **Decision: Moondream.** It is both MORE accurate (97.5% vs 92.5%) and ~**7x
  faster** (1.9s vs 12.9s mean) on this activity task, which justifies the
  deployed choice rather than just asserting it.
- Qwen's one weakness is TRANSITIONAL (70%): it reads a person standing AT the
  desk as sitting/working (context over posture). Moondream's single miss is a
  genuinely ambiguous frame (person at the desk holding a phone - standing vs
  sitting is unclear even to a human).
- Agreement 90% (4/40 disagreements, all inspected and genuine).
- Validity: three measurement bugs were found and fixed before this run (Qwen
  token budget, parser word-boundaries, parser bed-vs-standing) plus a
  prompt-bias confound and a data-labelling error - the instrument was validated,
  not assumed. See the commit history and the "Prompt choice" section.
- Caveats: n=40, single room / single occupant; offline latency (no GPU
  contention) is a lower bound, not the deployed figure - the live A/B measures that.
