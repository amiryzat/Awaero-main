/*
  room_node - ONE Arduino drives the appliance LEDs, the 16x2 I2C LCD, AND a
  0.96" SH1106 OLED that represents the TV screen.

  Appliances (5): light, fan, tv, desk lamp, aircond.
    pin 9  light    pin 10 fan    pin 11 tv    pin 8 desk lamp    pin 7 aircond
  OLED (TV display): software I2C on pins 12 (SDA) and 13 (SCL).
  Fan stepper (ULN2003 IN1-IN4): pins 2, 3, 4, 5 (parked).

  Protocol over USB serial (9600 baud), one line per message:
    "1,0,1,1,0\n"       LEDs in order light,fan,tv,lamp,ac (0/1 each). Fewer
                        values is fine. The FAN value also runs the stepper:
                        fan=1 spins it, fan=0 stops and de-energises it.
                        The TV value (index 2) also drives the OLED: tv=1 shows
                        content, tv=0 blanks the screen.
    "top line|bottom\n" LCD: two lines of text; the Mac formats it.

  The LCD is on hardware I2C (A4/A5, addr 0x27).
  The OLED is on software I2C (pins 12/13) so the two libraries don't clash.
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <U8g2lib.h>

// Appliance order: light, fan, tv, lamp, ac
const int PINS[] = {9, 10, 11, 8, 7};
const int NPINS = 5;
const int FAN_IDX = 1;               // which appliance also drives the stepper
const int TV_IDX = 2;                // which appliance also drives the OLED
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
// Software I2C: SCL=pin13, SDA=pin12 (separate from LCD on A4/A5)
U8G2_SH1106_128X64_NONAME_1_SW_I2C oled(U8G2_R0, /*clock=*/13, /*data=*/12);

bool hasLcd = false;
bool hasOled = false;
bool fanOn = false;
bool tvOn = false;
bool tvChanged = true;               // redraw on first loop
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
      if (i == TV_IDX) {
        bool now = v;
        if (now != tvOn) { tvOn = now; tvChanged = true; }
      }
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
  // OLED on software I2C (pins 12/13), begin() always succeeds
  oled.begin();
  hasOled = true;
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

  // OLED TV screen: redraw only when the tv state changes
  if (hasOled && tvChanged) {
    tvChanged = false;
    oled.firstPage();
    do {
      if (tvOn) {
        oled.setFont(u8g2_font_ncenB14_tr);
        oled.drawStr(30, 30, "AWAERO");
        oled.setFont(u8g2_font_6x10_tr);
        oled.drawStr(40, 50, "TV is ON");
      }
      // tv off: draw nothing (blank screen)
    } while (oled.nextPage());
  }

  if (hasLcd && !stale && millis() - lastText > TIMEOUT_MS) {
    row(0, "NO SIGNAL");
    row(1, "Mac not sending");
    stale = true;
  }
}
