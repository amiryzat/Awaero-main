# Passive engine: how the VLM and pose ended up sharing the job

Draft text for Chapter 3 (design evolution note) and Chapter 4 (results). Every
number comes from `EVAL_passive_vlm.md`; the live evidence (logs, frames) is in
`archive/`. Rewritten 2026-11-14: the earlier draft said pose replaced the VLM,
which live testing contradicted.

Framing: the VLM is the designed passive engine (Chapter 3). During Stage 3
(Implementation), testing showed that pose estimation and the VLM each fail where
the other succeeds, so the implemented system divides the work between them:
pose decides **whether** someone is present, the VLM decides **what** they are
doing. This changes only the Inference and Decision Logic layers; Perception,
Mode Selection and Actuation are as designed.

**Engine:** Moondream (decided 2026-11-14, and the model Chapter 3 specifies).
Qwen3-VL is presented as the evaluated alternative.

---

## For Chapter 3 (end of the Inference Layer / Passive Branch section)

> The passive branch was designed around a vision-language model (VLM) sampling
> the scene periodically. During implementation, a geometric pose estimator
> (MediaPipe Pose, up to four people per frame) was added alongside it, and live
> testing in the target room established a division of labour based on measured
> failure modes.
>
> Pose estimation runs in real time and reliably answers whether a person is
> present, but it cannot read posture from a single fixed camera: a person
> leaning forward over a desk compresses the shoulder-to-hip axis in the same
> way as a person lying towards the camera, and the body-extent ratios of
> sitting and standing overlap. Three geometric rules were implemented and
> rejected on this evidence. Pose estimation also produces phantom detections on
> furniture with landmark confidence indistinguishable from real people.
>
> The VLM reads posture correctly from scene context but is slower and, depending
> on its prompt, can overlook people. The implemented Decision Logic Layer
> therefore uses pose for presence and the VLM for posture (Transitional, Active
> or Resting). While no VLM answer is available the current profile is held
> rather than estimated, which prevents appliances switching twice for a single
> change in activity. When the VLM is fast enough (Moondream2, about 2 seconds
> per answer), the room is additionally treated as occupied only if the VLM has
> described a person within the last 10 seconds, which removes the pose
> phantoms.

## For Chapter 4 (comparison subsection)

### Inference engines on the labelled set (12 frames, iPhone 12 room scene)

| Engine | Accuracy | Latency / frame |
|---|---|---|
| Moondream2, "Describe this image." + keywords | 7/12 (58%) | 1.0 s (60-token cap) |
| **Moondream2, "Describe the people in this image." + keywords** | **12/12** | **0.82 s** |
| Qwen3-VL-4B, one-letter prompt, thinking off | 12/12 | ~20 s |
| Qwen3-VL-8B, one-letter prompt, thinking off | 12/12 | ~31 s |

On 70 eye-checked frames from live testing, the people-focused prompt mentioned
a person in every frame that contained one (including 12 lying-down frames the
scene prompt had missed) and in none of the 41 empty frames. A prompt that
presupposed a person ("Describe the person in this image...") invented one in
all 41 empty frames.

### Pose vs VLM, by role

| Question | Pose (MediaPipe) | VLM (Moondream2, people prompt) |
|---|---|---|
| Is anyone present? | real time, but phantoms on furniture at ~1.00 confidence | 0 misses in 29 person frames, 0 false people in 41 empty |
| Sitting / standing / lying? | unreliable here (three rules failed) | 12/12 labelled; caught lying 12/12 where the scene prompt got 1/12 |
| Speed | ~30 fps | ~2 s per answer live |
| Multiple people | up to 4, boxed individually | described together |

### Live system result (Moondream configuration)

| Measure | Result |
|---|---|
| VLM latency, live | 1.87 s mean, 3.6 s max (199 answers, flat) |
| Leaving the room -> unoccupied | 10-18 s (was 68 s with the scene prompt) |
| Gesture activations | 10 of 10 deliberate (0 false) |

### Honest trade-offs (keep these; examiners reward them)

> The VLM's latency means a posture change is reflected after a few seconds
> rather than instantly; this was preferred to an instant but unstable signal
> that switched appliances twice per event. Occupancy detection is only as good
> as the camera's field of view: in the test room the camera also sees a hallway,
> so a person standing there is counted as present. A visible-light camera cannot
> perceive a person in complete darkness; an infrared camera is the production
> answer. Finally, the VLM's behaviour depends strongly on prompt wording, so the
> chosen prompt was validated on empty rooms as well as occupied ones.

---

## Thesis numbers still to collect (RO3)
- >=10 trials per response path (4 passive + 3 active = 7 paths, >=70 points).
- End-to-end response time per transition (camera to LED), per mode.
- Simulated Appliance Activation Reduction (exact mandated term).
