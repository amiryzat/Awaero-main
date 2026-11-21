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

## 16x2 LCD (status display)
I2C at 0x27, on hardware I2C (A4 SDA, A5 SCL). Direct wires to the Arduino,
no breadboard middleman. VCC -> red (+) rail, GND -> blue (-) rail.

## 0.96" OLED SH1106 (TV display)
Software I2C on digital pins 12 (SDA) and 13 (SCL). The OLED represents the
TV appliance: when TV is on it shows content, when off it goes blank. Wired
with female-to-male jumpers from the OLED header to the Arduino digital pins.
VCC -> red (+) rail, GND -> blue (-) rail.

NOTE: The LCD and OLED use DIFFERENT I2C buses. Sharing hardware I2C (A4/A5)
caused library conflicts (U8g2 vs LiquidCrystal_I2C). The fix was to put the
OLED on software I2C (pins 12/13). The LCD stays on hardware I2C (A4/A5).
The OLED chip is SH1106, not SSD1306 (tested: SSD1306 driver shows nothing).

## Pin map (updated 2026-11-21)
| Pin | Use |
|-----|-----|
| 2-5 | stepper (parked, too slow) |
| 6 | (reserved for DHT22) |
| 7 | AC LED |
| 8 | Desk lamp LED |
| 9 | Light LED |
| 10 | Fan LED |
| 11 | TV LED |
| 12 | OLED SDA (software I2C) |
| 13 | OLED SCL (software I2C) |
| A4 | LCD SDA (hardware I2C) |
| A5 | LCD SCL (hardware I2C) |

## Still to do
- DHT22 temperature/humidity sensor on pin 6
- DC motor + IRF520 MOSFET on pin 3 (PWM) to replace the parked stepper
- optional: relay module for a higher-current appliance demo
