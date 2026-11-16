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

## Policy note (new, per FYP_Room_Activity_and_Appliance_Decision_Profiles.md)
Code FUSED_APP still the OLD 3-appliance policy; NOT yet updated to the doc.
New policy to apply (order light,fan,tv,lamp,ac):
  A sitting  : light ON, fan ON, TV OFF, lamp ON,  AC (tbd)
  T standing : light ON, fan ON, TV hold, lamp OFF, AC hold
  B lying    : light OFF,fan ON, TV OFF, lamp OFF, AC (tbd)
  C empty    : all OFF
AC rule deferred (owner: decide later; no temp sensor yet -> assumed policy).

## LCD (16x2 I2C, addr 0x27) - same Arduino as the LEDs
| LCD pin | Goes to                                      |
|---------|----------------------------------------------|
| GND     | blue (-) rail                                |
| VCC     | red (+) rail  (one wire: Arduino 5V -> red rail) |
| SDA     | Arduino A4                                    |
| SCL     | Arduino A5                                    |
Status: WORKING (verified 2026-11-16 at 0x27, same Arduino as the LEDs).
Earlier "boxes" was the LCD not yet fully wired, plus a stale python process
