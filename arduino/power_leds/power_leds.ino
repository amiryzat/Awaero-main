/*
  power_leds - receives LED states from the Python program over USB serial.

  Protocol: one line per update, three values 0/1 separated by commas,
  for GREEN, YELLOW, RED. Example: "1,0,0\n" turns GREEN on, others off.

  Wiring: same as blink_test.
    pin 9  -> GREEN   pin 10 -> YELLOW   pin 11 -> RED
*/

const int GREEN = 9;
const int YELLOW = 10;
const int RED = 11;

void setup() {
  pinMode(GREEN, OUTPUT);
  pinMode(YELLOW, OUTPUT);
  pinMode(RED, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    int c1 = line.indexOf(',');
    int c2 = line.indexOf(',', c1 + 1);
    if (c1 > 0 && c2 > c1) {
      int g = line.substring(0, c1).toInt();
      int y = line.substring(c1 + 1, c2).toInt();
      int r = line.substring(c2 + 1).toInt();
      digitalWrite(GREEN, g ? HIGH : LOW);
      digitalWrite(YELLOW, y ? HIGH : LOW);
      digitalWrite(RED, r ? HIGH : LOW);
    }
  }
}
