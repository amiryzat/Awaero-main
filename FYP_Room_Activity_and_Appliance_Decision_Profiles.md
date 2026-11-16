# FYP: Context-Aware Room-Level Smart Power Management

## 1. Purpose

This document consolidates the proposed room-use scenarios, activity profiles, appliance decisions, transition handling, and system-design recommendations for the FYP:

**Context-Aware Vision-Based Smart Power Management System for Room-Level Energy Optimisation Based on Activity Detection**

The proposed system observes a room, interprets the occupant's activity and context, and determines suitable appliance states. The Arduino prototype can represent appliance states using LEDs rather than directly controlling household electrical appliances.

---

## 2. Design principle

The system should not switch appliances based only on a person's posture.

Posture is useful evidence, but it does not always reveal the person's intention:

- A person sitting is not necessarily watching television.
- A person standing is not necessarily leaving the room.
- A person lying down is not necessarily sleeping.
- Air-conditioning requirements depend on environmental conditions and occupancy, not posture alone.

The system should therefore use **activity-based profiles combined with context-aware appliance decisions**.

A useful conceptual pipeline is:

1. **Activity detection:** Identify observable states such as sitting, standing, lying, and no person detected.
2. **Context interpretation:** Interpret what the person may be doing, based on available visual evidence and other available context.
3. **Appliance decision:** Determine which appliances should be ON, OFF, or remain unchanged.

Do not claim that posture alone can reliably identify activities such as studying, entertainment, relaxation, or sleeping. These contexts may require additional visual evidence, and some situations will remain ambiguous.

---

## 3. Real-world room-use scenarios

Assume the prototype represents a typical bedroom that is also used as a study room.

### Scenario A: Studying or working

**Situation:** The occupant is sitting at a desk, using a laptop, and concentrating on work.

| Appliance | Suggested state | Reason |
|---|---|---|
| Main light | ON | Provides general room illumination |
| Fan | ON | Provides air circulation |
| TV | OFF | Studying does not require the TV |
| Desk lamp | ON | Supports desk-based work |
| Air conditioner | Conditional | Depends on temperature and comfort requirements |

### Scenario B: Moving around the room

**Situation:** The occupant stands up and walks to the wardrobe, collects an item, or moves around the room.

| Appliance | Suggested state | Reason |
|---|---|---|
| Main light | ON | Maintains visibility |
| Fan | ON | Avoids unnecessary switching during brief movement |
| TV | No change | Standing does not imply a change in TV usage |
| Desk lamp | OFF | The occupant is no longer working at the desk |
| Air conditioner | No change | Avoid switching it off during a brief transition |

Standing should be treated as a possible temporary transition, not immediate evidence that the room is unoccupied.

### Scenario C: Resting or relaxing

**Situation:** The occupant lies on the bed, uses a phone, or relaxes.

| Appliance | Suggested state | Reason |
|---|---|---|
| Main light | OFF or DIM | Lower lighting may be more suitable for relaxation |
| Fan | ON | Provides air circulation |
| TV | OFF by default | Lying down does not necessarily mean watching TV |
| Desk lamp | OFF | Desk lighting is not required |
| Air conditioner | Conditional | Depends on temperature and comfort requirements |

If the prototype cannot support dimming, represent the main light as simply ON or OFF.

### Scenario D: Leaving the room

**Situation:** The occupant leaves for class, food, or another activity.

| Appliance | Suggested state | Reason |
|---|---|---|
| Main light | OFF | No occupant needs the lighting |
| Fan | OFF | Reduces unnecessary energy use |
| TV | OFF | No occupant is using it |
| Desk lamp | OFF | No occupant is using it |
| Air conditioner | OFF | Avoids cooling an unoccupied room |

The system should confirm unoccupancy over a defined period before switching appliances off. A single missed camera detection should not immediately trigger the unoccupied profile.

### Scenario E: Sleeping

**Situation:** The occupant is sleeping in bed.

| Appliance | Suggested state | Reason |
|---|---|---|
| Main light | OFF | Suitable for sleeping |
| Fan | ON | May provide air circulation |
| TV | OFF | Avoids unnecessary operation |
| Desk lamp | OFF | Not required |
| Air conditioner | Conditional | Depends on temperature and occupant preference |

Sleeping should only be a separate profile if the system has sufficient evidence to distinguish it. Otherwise, classify the situation as Resting rather than claiming reliable sleep detection.

---

## 4. Recommended appliance decision table

The following table is a practical initial configuration for the prototype. It is a proposed policy, not a universal rule for every household.

| Profile | Main light | Fan | TV | Desk lamp | Air conditioner |
|---|---|---|---|---|---|
| A: Active (sitting) | ON | ON | OFF | ON | Conditional |
| T: Transitional (standing) | ON | ON | No change | OFF | No change |
| B: Resting (lying) | OFF | ON | OFF | OFF | Conditional |
| S: Sleeping | OFF | ON | OFF | OFF | Conditional |
| C: Unoccupied | OFF | OFF | OFF | OFF | OFF |

### Important appliance decisions

#### TV

Do not automatically turn the TV ON when the occupant is sitting. Sitting does not prove that the person wants to watch television. Keep it OFF by default unless the system has reliable evidence of an entertainment context or the user has selected that preference.

#### Air conditioner

Air-conditioning should be temperature-dependent rather than determined by posture alone.

Illustrative starting policy:

- If the room temperature is above 27°C, the AC may be turned ON.
- If the room temperature falls below 25°C, the AC may be turned OFF.
- If the room is confirmed unoccupied, the AC should be turned OFF after the configured delay.

These values are example thresholds only. They are not universal comfort settings and should be calibrated or justified for the prototype. A temperature sensor is needed if the system is expected to make temperature-based decisions. Without one, AC operation should remain a configurable assumption rather than a measured context-aware decision.

#### Fan

Keeping the fan ON during resting and sleeping is a reasonable initial assumption for a typical Malaysian bedroom. It should still be treated as a configurable room preference.

#### Desk lamp

The desk lamp can be associated with desk-based work. It should be ON for the Active/studying scenario and OFF when the occupant is resting or moving away from the desk.

---

## 5. Transition handling and delay logic

The system should avoid abrupt appliance switching when the occupant changes posture temporarily.

### Example problem

1. The occupant is sitting and studying.
2. The occupant stands up to collect an item.
3. The vision system detects standing.
4. A naive system immediately switches off the fan and other appliances.
5. The occupant returns to the desk moments later.

This would create a poor user experience and unnecessary switching.

### Recommended transition behaviour

1. Detect standing or movement.
2. Enter the Transitional profile.
3. Start a transition timer.
4. Keep essential appliances operating during the transition.
5. If the occupant returns to sitting, return to Active.
6. If the person is no longer detected for a configured period, evaluate whether the room is Unoccupied.
7. Only switch appliances off after unoccupancy is sufficiently confirmed.

Conceptual flow:

```text
ACTIVE
  |
  | Standing detected
  v
TRANSITIONAL
  |
  +---- Returns to sitting ----> ACTIVE
  |
  +---- No person detected for configured period
                                  |
                                  v
                             UNOCCUPIED
```

The exact delay should be selected during testing. Avoid presenting an arbitrary delay as scientifically established unless it is supported by testing or a cited source.

### Avoid rapid profile changes

The system should also avoid repeatedly switching profiles because of small movements, temporary occlusion, or inconsistent VLM outputs.

Possible safeguards include:

- Require a state to be detected consistently before changing profiles.
- Use a minimum time interval before accepting a new profile.
- Use a separate unoccupied timeout.
- Preserve the previous appliance state when the new observation is uncertain.
- Avoid switching an appliance repeatedly when the requested state has not changed.

---

## 6. Proposed final activity profiles

Start with these five conceptual profiles:

### A. Active

**Typical activity:** Sitting, studying, working, or using a computer.

Initial appliance policy:

- Main light: ON
- Fan: ON
- TV: OFF
- Desk lamp: ON
- AC: Conditional

### T. Transitional

**Typical activity:** Standing or temporarily moving around the room.

Initial appliance policy:

- Main light: ON
- Fan: ON
- TV: No change
- Desk lamp: OFF
- AC: No change

### B. Resting

**Typical activity:** Lying down or relaxing.

Initial appliance policy:

- Main light: OFF
- Fan: ON
- TV: OFF
- Desk lamp: OFF
- AC: Conditional

### S. Sleeping

**Typical activity:** Sleeping or prolonged nighttime inactivity, but only if sufficiently detectable.

Initial appliance policy:

- Main light: OFF
- Fan: ON
- TV: OFF
- Desk lamp: OFF
- AC: Conditional

If the vision system cannot reliably distinguish sleeping from resting, keep both under the Resting profile. Do not claim sleep detection based only on a person lying down.

### C. Unoccupied

**Typical activity:** No person detected for a configured confirmation period.

Initial appliance policy:

- Main light: OFF
- Fan: OFF
- TV: OFF
- Desk lamp: OFF
- AC: OFF

---

## 7. Recommended system architecture

Keep the responsibilities of each stage separate:

| Layer | Responsibility | Example output |
|---|---|---|
| Activity detection | Identify observable human activity or posture | Sitting, standing, lying, no person detected |
| Context interpretation | Interpret likely room-use context using available evidence | Studying, temporary movement, resting, uncertain |
| Appliance decision | Apply the configured energy-management policy | Light ON, fan ON, TV OFF, etc. |

### Example interpretations

- Sitting + visible laptop use at a desk → likely studying or working.
- Sitting + visible TV use → potentially entertainment.
- Lying + phone use → potentially relaxation.
- Lying + prolonged inactivity at night → possibly sleeping, but not conclusive.
- No person detected over the configured timeout → potentially unoccupied.

These are examples of possible interpretations, not guaranteed classifications. The VLM must have sufficient visual evidence, and uncertain cases should be handled conservatively.

---

## 8. Prototype implementation considerations

- Use Arduino LEDs to represent appliance states during the prototype demonstration.
- Do not connect household mains-powered appliances directly to the Arduino.
- Ensure the decision engine only changes an output when the desired appliance state changes.
- Keep activity recognition separate from appliance-control rules so the policy can be adjusted without rewriting the detection stage.
- Log the detected profile, interpreted context, appliance decisions, and timestamps during testing. This will help evaluate incorrect decisions and unnecessary switching.
- If no temperature sensor is included, describe AC control as a configurable or assumed policy, not a temperature-aware feature.
- If the system cannot distinguish sleeping from resting, do not claim that it can.

---

## 9. Recommended scope decision

A **bedroom + study room** is a useful demonstration environment because it supports multiple realistic activities:

- Studying or working at a desk.
- Standing and moving around temporarily.
- Resting on the bed.
- Sleeping, if detectable.
- Leaving the room.

This provides more meaningful activity scenarios than a room used for only one purpose.

However, keep the first implementation manageable. Implement and test the core profiles first:

1. Active
2. Transitional
3. Resting
4. Unoccupied

Treat Sleeping and more detailed contexts such as entertainment as extensions unless the available visual evidence and project scope support them.

---

## 10. Key design decisions to settle before implementation

1. **Room type:** Confirm whether the prototype represents a bedroom + study room or another room type.
2. **Appliance representation:** Confirm which appliances are represented by the available Arduino LEDs.
3. **Temperature input:** Confirm whether a temperature sensor is available. If not, AC decisions cannot genuinely be temperature-aware.
4. **Sleep detection:** Decide whether Sleeping is a separate profile or whether it remains part of Resting.
5. **Transition timeout:** Determine the delay through testing rather than choosing an arbitrary value.
6. **Unoccupied timeout:** Determine how long the system must fail to detect a person before it considers the room unoccupied.
7. **Uncertain observations:** Define a safe fallback, such as retaining the previous appliance states instead of making a sudden change.

## 11. Core recommendation

The central design principle is:

**Detect what the occupant is doing, interpret the likely room-use context, and then make appliance decisions using explicit rules and environmental inputs where available.**

Do not equate a posture directly with a complete appliance configuration. A context-aware system should account for temporary movement, uncertainty, occupant comfort, and the actual purpose of each appliance.
