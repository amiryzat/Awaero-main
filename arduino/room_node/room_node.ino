/*
  room_node - ONE Arduino drives the 3 appliance LEDs AND the 16x2 I2C LCD.

  Protocol over USB serial (9600 baud), one line per message:
    "1,0,1\n"          LEDs: light, fan, tv on/off (pins 9, 10, 11) - same as power_leds
    "top line|bottom\n" LCD: two lines of text (16 letters each); the Mac formats it

  Wiring: LEDs as before (pin 9 light, 10 fan, 11 tv).
          LCD: GND -> GND, VCC -> 5V, SDA -> A4, SCL -> A5.

  If no LCD text arrives for TIMEOUT_MS the screen says NO SIGNAL, so a frozen
  screen is never mistaken for a live one. The LEDs keep working with no LCD
  plugged in (I2C writes to a missing screen just fail quietly).
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const int LIGHT = 9;
const int FAN = 10;
const int TV = 11;
const unsigned long TIMEOUT_MS = 10000;

LiquidCrystal_I2C lcd(0x27, 16, 2);   // address found by arduino/lcd_test

char buf[40];
uint8_t n = 0;
unsigned long lastText = 0;
bool stale = false;

// Print s on a row and pad with spaces: no clear() flicker, no leftovers.
void row(uint8_t r, const char* s) {
  lcd.setCursor(0, r);
  uint8_t i = 0;
  for (; s[i] && i < 16; i++) lcd.print(s[i]);
  for (; i < 16; i++) lcd.print(' ');
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
  char* c1 = strchr(buf, ',');       // LED command "a,b,c"
  char* c2 = c1 ? strchr(c1 + 1, ',') : 0;
  if (c1 && c2) {
    digitalWrite(LIGHT, atoi(buf) ? HIGH : LOW);
    digitalWrite(FAN, atoi(c1 + 1) ? HIGH : LOW);
    digitalWrite(TV, atoi(c2 + 1) ? HIGH : LOW);
  }
}

void setup() {
  pinMode(LIGHT, OUTPUT);
  pinMode(FAN, OUTPUT);
  pinMode(TV, OUTPUT);
  Serial.begin(9600);
  lcd.init();
  lcd.backlight();
  row(0, "Smart Power FYP");
  row(1, "waiting for Mac");
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
  if (!stale && millis() - lastText > TIMEOUT_MS) {
    row(0, "NO SIGNAL");
    row(1, "Mac not sending");
    stale = true;
  }
}
