/*
  room_node - ONE Arduino drives the appliance LEDs, the 16x2 I2C LCD, AND a
  28BYJ-48 stepper (via a ULN2003 board) that is the PHYSICAL fan.

  Appliances (5): light, fan, tv, desk lamp, aircond.
    pin 9  light    pin 10 fan    pin 11 tv    pin 8 desk lamp    pin 7 aircond
  Fan stepper (ULN2003 IN1-IN4): pins 2, 3, 4, 5.

  Protocol over USB serial (9600 baud), one line per message:
    "1,0,1,1,0\n"       LEDs in order light,fan,tv,lamp,ac (0/1 each). Fewer
                        values is fine. The FAN value also runs the stepper:
                        fan=1 spins it, fan=0 stops and de-energises it.
    "top line|bottom\n" LCD: two lines of text; the Mac formats it.

  The stepper is driven NON-BLOCKING: loop() advances it one half-step only when
  STEP_INTERVAL_US has passed, so serial, LEDs and LCD stay responsive while it
  turns. The 28BYJ-48 is heavily geared (~4096 half-steps/rev) so even at full
  speed it turns slowly - that is the motor, not the code.

  The LCD is auto-detected at 0x27; with none attached the LEDs still work.
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Appliance order: light, fan, tv, lamp, ac
const int PINS[] = {9, 10, 11, 8, 7};
const int NPINS = 5;
const int FAN_IDX = 1;               // which appliance also drives the stepper
const uint8_t LCD_ADDR = 0x27;
const unsigned long TIMEOUT_MS = 10000;

// Stepper: ULN2003 IN1..IN4. Half-step sequence (the reliable one for the
// 28BYJ-48), one nibble per step; bit i is IN(i+1), bit0->pin2 ... bit3->pin5.
// Full-stepping stalls this geared motor, so half-step it is. ~4096 half-steps
// /rev; ~1100 us/step is about as fast as it turns before it buzzes instead.
const uint8_t STEP_PINS[4] = {2, 3, 4, 5};
const uint8_t STEP_SEQ[8]  = {0x1, 0x3, 0x2, 0x6, 0x4, 0xC, 0x8, 0x9};
const unsigned long STEP_INTERVAL_US = 1100;

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

bool hasLcd = false;
bool fanOn = false;
uint8_t stepIdx = 0;
unsigned long lastStepUs = 0;
char buf[40];
uint8_t n = 0;
unsigned long lastText = 0;
bool stale = false;

void row(uint8_t r, const char* s) {
  if (!hasLcd) return;
  lcd.setCursor(0, r);
  uint8_t i = 0;
  for (; s[i] && i < 16; i++) lcd.print(s[i]);
  for (; i < 16; i++) lcd.print(' ');
}

void coils(uint8_t bits) {           // energise the 4 stepper pins from a nibble
  for (uint8_t i = 0; i < 4; i++) digitalWrite(STEP_PINS[i], (bits >> i) & 1);
}

void runFan() {
  if (!fanOn) { coils(0); return; }  // stopped: de-energise so it does not hum/heat
  if (micros() - lastStepUs < STEP_INTERVAL_US) return;
  lastStepUs = micros();
  stepIdx = (stepIdx + 1) & 7;
  coils(STEP_SEQ[stepIdx]);
}

void handleLine() {
  buf[n] = 0;
  char* sep = strchr(buf, '|');
  if (sep) {                         // LCD text
    *sep++ = 0;
    row(0, buf);
    row(1, sep);
    lastText = millis();
    stale = false;
    return;
  }
  if (strchr(buf, ',')) {            // LED command "a,b,c,..." in pin order
    char* p = buf;
    for (int i = 0; i < NPINS && p; i++) {
      int v = atoi(p);
      digitalWrite(PINS[i], v ? HIGH : LOW);
      if (i == FAN_IDX) fanOn = v;   // the fan value also runs the stepper
      char* c = strchr(p, ',');
      p = c ? c + 1 : 0;
    }
  }
}

void setup() {
  for (int i = 0; i < NPINS; i++) pinMode(PINS[i], OUTPUT);
  for (int i = 0; i < 4; i++) pinMode(STEP_PINS[i], OUTPUT);
  coils(0);
  Serial.begin(9600);

  Wire.begin();
  Wire.beginTransmission(LCD_ADDR);
  hasLcd = (Wire.endTransmission() == 0);
  if (hasLcd) {
    lcd.init();
    lcd.backlight();
    row(0, "Smart Power FYP");
    row(1, "waiting for Mac");
  }
  lastText = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleLine();
      n = 0;
    } else if (c != '\r' && n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
  runFan();                          // non-blocking: steps only when due
  if (hasLcd && !stale && millis() - lastText > TIMEOUT_MS) {
    row(0, "NO SIGNAL");
    row(1, "Mac not sending");
    stale = true;
  }
}
