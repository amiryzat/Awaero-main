# Passive engine evaluation: VLM swap (Moondream2 -> Qwen3-VL)

RO3 evaluation record for the passive classifier. Documents the change from
Moondream2 to Qwen3-VL-8B, the prompt-strategy experiments, and the dataset
recapture. Raw per-frame data is in `classify_results.csv` (overwritten each run).

- **Date:** 2026-11-12
- **Hardware:** MacBook, Apple M5, 24 GB RAM. Local inference via Ollama.
- **Classifier:** `classify_passive.py` (offline, reads `frames/profile_*.jpg`).
- **Profiles:** T transitional/standing, A active/sitting, B resting/lying,
  C unoccupied.
- **Metric:** activity classification accuracy over the labelled frames; mean
  inference latency per frame (wall clock, includes model thinking).

## Datasets

| Set | Source | Frames | Notes |
|---|---|---|---|
| Old | Mac webcam, close-up | 12 (3/profile) | archived in `frames/old_macwebcam/`. The 3 "C" frames were **mislabelled** — a person was lying in bed, so they are not unoccupied. |
| New | Mounted iPhone 12, room scene | 12 (3/profile) | recaptured via `capture_frames.py` from the demo camera position; C frames are genuinely empty. Current `frames/`. |

## Runs

### Run 0 — Moondream2 (prior baseline, historical)
- Method: two-stage "describe this image" + keyword scan (the only thing that
  Moondream build answered).
- Result: reported 100% on the old frames, ~1-2 s/frame.
- Caveat found later: that 100% is unreliable. Moondream scored the "C" frames
  correct partly by **failing to notice** the person lying in bed. A sharper
  model (below) does notice, which exposed the mislabelled data.

### Run 1 — Qwen3-VL-8B, old pipeline unchanged, old frames
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

### Run 2 — Qwen3-VL-8B, direct one-letter prompt, output capped (failed)
- Method: single prompt "reply with one letter T/A/B/C", `num_predict=4`.
- **Accuracy: 0% (0/12). All replies empty, 0.43 s/frame.**
- Finding: **Qwen3-VL is a thinking model.** It emits hidden `<think>` tokens
  before the answer; a small `num_predict` is consumed entirely by thinking, so
  the answer letter is never produced. Do **not** cap `num_predict`.

### Run 3 — Qwen3-VL-8B, direct one-letter prompt, uncapped, old frames
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

### Run 4 — Qwen3-VL-8B, direct one-letter prompt, NEW iPhone-12 room frames
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

## Summary

| Run | Model | Prompt | Dataset | Accuracy | Latency |
|---|---|---|---|---|---|
| 0 | Moondream2 | describe + keyword | old | 100% (unreliable) | ~1-2 s |
| 1 | Qwen3-VL-8B | describe + keyword | old | 58.3% | 62.4 s |
| 2 | Qwen3-VL-8B | 1 letter, capped | old | 0% (empty) | 0.43 s |
| 3 | Qwen3-VL-8B | 1 letter, uncapped | old | 75% (100% on valid) | 2.64 s |
| 4 | Qwen3-VL-8B | 1 letter, uncapped | **new (phone, room)** | **100%** | **15.4 s** |

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

## Open items
- Latency lever not yet tested: downscale the frame (~640 px) before sending to
  the VLM; expected to cut Run-4 latency with little accuracy loss.
- Formal RO3 protocol wants >=10 trials per response path (>=70 data points);
  this record uses 3/profile. Scale up for the final evaluation.
- Measure the pose engine on the same new dataset for the pose-vs-VLM comparison.
