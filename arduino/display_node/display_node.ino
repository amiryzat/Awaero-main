// Display node: the second (black) Arduino shows two lines of text sent by the Mac.
// Wiring: LCD GND->GND, VCC->5V, SDA->A4, SCL->A5.
// Protocol (9600 baud): "line one|line two\n". The Mac formats the text, so the
// wording can change without re-flashing this board.
// If nothing arrives for TIMEOUT_MS the screen says NO SIGNAL, so a frozen screen
// is never mistaken for a live one.

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const unsigned long TIMEOUT_MS = 10000;
LiquidCrystal_I2C lcd(0x27, 16, 2);   // 0x27 found by arduino/lcd_test

char buf[40];
uint8_t n = 0;
unsigned long lastMsg = 0;
bool stale = false;

// Print s on a row and pad with spaces, so no clear() flicker and no leftovers.
void row(uint8_t r, const char* s) {
  lcd.setCursor(0, r);
  uint8_t i = 0;
  for (; s[i] && i < 16; i++) lcd.print(s[i]);
  for (; i < 16; i++) lcd.print(' ');
}

void setup() {
  Serial.begin(9600);
  lcd.init();
  lcd.backlight();
  row(0, "Smart Power FYP");
  row(1, "waiting for Mac");
  lastMsg = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buf[n] = 0;
      char* sep = strchr(buf, '|');
      if (sep) *sep++ = 0; else sep = buf + n;   // no '|' -> second line empty
      row(0, buf);
      row(1, sep);
      n = 0;
      lastMsg = millis();
      stale = false;
    } else if (c != '\r' && n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
  if (!stale && millis() - lastMsg > TIMEOUT_MS) {
    row(0, "NO SIGNAL");
    row(1, "Mac not sending");
    stale = true;
  }
}
