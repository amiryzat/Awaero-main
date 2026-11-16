# Physical wiring map (breadboard holes used)

Full-size breadboard, columns 1-60. Rule: the 5 holes in one numbered
column (a5,b5,c5,d5,e5) are one connected node; a-e and f-j are separate
halves split by the centre gap.

LEDs live out on female-to-male jumper wires (cardboard house); the resistor
stays on the breadboard. Signal from an Arduino digital pin. 5 LEDs but only
3 Arduino GND holes, so grounds share the breadboard BLUE (-) rail:
one wire Arduino GND -> blue rail, then every LED short leg -> blue rail.
All LED short legs (green included) return to the blue rail.

Per LED: pin -> aN ; resistor bN -> b(N+5) ; fem-male a(N+5) -> LED long
leg (+) ; fem-male LED short leg (-) -> blue rail.

Firmware: arduino/room_node.ino, protocol "light,fan,tv,lamp,ac\n".

| Appliance   | Pin | Signal in | Resistor    | Wire to LED + | LED - (ground) |
|-------------|:---:|:---------:|:-----------:|:-------------:|----------------|
| Light green | 9   | a5        | b5 -> b10   | a10           | blue (-) rail  |  DONE, tested
| Fan yellow  | 10  | a15       | b15 -> b20  | a20           | blue (-) rail  |  DONE, tested
| TV red      | 11  | a25       | b25 -> b30  | a30           | blue (-) rail  |  DONE, tested
| Desk lamp   | 8   | a35       | b35 -> b40  | a40           | blue (-) rail  |  DONE, tested
| AC          | 7   | a45       | b45 -> b50  | a50           | blue (-) rail  |  DONE, tested

One-time: male-male wire Arduino GND (POWER row) -> blue (-) rail.

## Policy (live in code as of 2026-11-16, commit 3ff8338)
Implements FYP_Room_Activity_and_Appliance_Decision_Profiles.md section 4.
Order light,fan,tv,lamp,ac. HOLD = "No change" (keeps whatever is on).
  A sitting  : light ON, fan ON, TV OFF, lamp ON,  AC ON
  T standing : light ON, fan ON, TV HOLD, lamp OFF, AC HOLD
  B lying    : light OFF,fan ON, TV OFF, lamp OFF, AC ON
  C empty    : all OFF
AC is an ASSUMED policy (no temperature sensor). If a DHT11 is added later it
becomes genuinely temperature-aware; until then the writing must call it a
configurable assumption, per the doc.

## Still to do
- stepper motor (28BYJ-48 + ULN2003) as the physical fan, pins 2-5
- optional: servo as an AC vent flap; DHT11 for real temperature-based AC
