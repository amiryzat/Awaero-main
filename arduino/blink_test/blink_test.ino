/*
  blink_test - proves the Arduino uploads and the 3 LEDs are wired right.

  Onboard LED (pin 13) blinks the whole time, so even with no LEDs wired you
  can confirm the upload worked. Pins 9/10/11 light GREEN, YELLOW, RED in
  sequence once the LEDs are on the breadboard.

  Wiring (each LED): digital pin -> 220 ohm resistor -> LED long leg (anode);
  LED short leg (cathode) -> GND rail. Arduino GND -> GND rail.
    pin 9  -> GREEN
    pin 10 -> YELLOW
    pin 11 -> RED
*/

const int GREEN = 9;
const int YELLOW = 10;
const int RED = 11;
const int ONBOARD = 13;

void setup() {
  pinMode(GREEN, OUTPUT);
  pinMode(YELLOW, OUTPUT);
  pinMode(RED, OUTPUT);
  pinMode(ONBOARD, OUTPUT);
}

void flash(int pin) {
  digitalWrite(ONBOARD, HIGH);
  digitalWrite(pin, HIGH);
  delay(400);
  digitalWrite(pin, LOW);
  digitalWrite(ONBOARD, LOW);
  delay(200);
}

void loop() {
  flash(GREEN);
  flash(YELLOW);
  flash(RED);
}
