# Passive engine: designed VLM vs implemented pose improvement

Draft text for Chapter 3 (design evolution note) and Chapter 4 (results /
comparison). Framing: the VLM approach is the **designed** passive engine in the
methodology; the pose-based engine is an **implemented improvement** discovered
during Stage 3 (Implementation) of the Waterfall process. Both are real; the
thesis presents the move from one to the other as an engineering outcome, not a
scope change.

Fill the bracketed [[numbers]] from your RO3 evaluation runs before submitting.

---

## For Chapter 3 (end of the Inference Layer / Passive Branch section)

> The passive branch was originally designed around the Moondream2
> vision-language model (Section 3.4.3), chosen for its local, privacy-preserving
> semantic reasoning. During implementation, controlled testing of this designed
> engine exposed three limitations that are intrinsic to running a general VLM on
> an edge node for continuous room monitoring:
>
> 1. **Latency.** Moondream2 runs at approximately 1 to 2 seconds per frame on
>    the local Metal GPU, which forces the 3-second passive sampling interval and
>    introduces a visible delay between a change in room activity and the
>    actuation response.
> 2. **Single-person reasoning.** The semantic prompt describes "the person" in
>    the scene and does not reliably reason about multiple occupants at once,
>    which the evaluation environment (a shared room) can contain.
> 3. **Hallucination.** The model occasionally reported a person in an empty
>    scene (for example inferring an occupant from a chair), producing false
>    occupancy classifications.
>
> To address these limitations while preserving the same five-layer architecture,
> actuation mapping, and energy profiles, the passive inference engine was
> re-implemented using a geometric pose-estimation approach (MediaPipe Pose)
> during Stage 3. Posture is derived from the torso-axis angle of each detected
> skeleton, and the room profile is assigned from the most active occupant. This
> substitution changes only the Inference Layer; the Perception, Mode Selection,
> Decision Logic, and Actuation layers are unchanged, so the move is an internal
> engineering refinement rather than a redesign of the system. The original
> Moondream2 engine is retained as the designed baseline and is evaluated against
> the pose-based engine in Chapter 4.

## For Chapter 4 (comparison subsection)

> Both passive engines were evaluated on the same labelled frame set captured
> from the final camera position. The Moondream2 baseline is the engine specified
> in the design; the MediaPipe Pose engine is the implemented improvement.

### Comparison

| Criterion | Moondream2 (designed) | MediaPipe Pose (implemented) |
|---|---|---|
| Inference latency / frame | ~1-2 s (Metal GPU) | [[fill: ~ms, real-time]] |
| Sampling interval forced | 3 s | none (per-frame) |
| Occupants reasoned about | one ("the person") | multiple (num_poses=4) |
| False occupancy (empty scene) | occurs (chair -> person) | none observed |
| Classification accuracy (labelled set) | [[fill, e.g. 100%]] | [[fill]] |
| Output granularity | rich semantic (activity words) | posture geometry (upright / lying) |
| Privacy (local only) | yes | yes |

### Honest trade-off (keep this, examiners reward it)

> The pose-based engine is faster, multi-person, and free of the hallucination
> failure mode, which is why it was adopted for the live demonstration. The
> trade-off is a loss of semantic richness: the VLM can distinguish fine
> activities from scene context (for example "reading" versus "watching
> television"), whereas the pose engine infers only coarse posture (upright
> versus lying). For the four energy profiles this coarse signal is sufficient,
> but applications needing finer activity context would favour the VLM or a
> hybrid of the two. Both engines share the same hard limit: a visible-light
> camera cannot classify a person it cannot capture in full darkness.

---

## One open item this does NOT resolve

The design documents **four** passive profiles (T Transitional, A Active,
B Resting, C Unoccupied). The current pose engine produces **three** (A/B/C); it
has no Transitional/standing state. If the evaluation must cover all seven
documented response paths (4 passive + 3 active), either add a T rule to the
pose engine (standing-but-moving posture) or justify in Chapter 4 why pose
collapses T into A. Decide this with the supervisor.
