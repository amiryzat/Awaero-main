/*
  room_node - ONE Arduino drives the appliance LEDs AND the 16x2 I2C LCD.

  Appliances (5): light, fan, tv, desk lamp, aircond.
    pin 9  light    pin 10 fan    pin 11 tv    pin 8 desk lamp    pin 7 aircond

  Protocol over USB serial (9600 baud), one line per message:
    "1,0,1,1,0\n"       LEDs in order light,fan,tv,lamp,ac (0/1 each).
                        Fewer values is fine: only the ones given are set,
                        so an old "1,0,1" still drives light,fan,tv.
    "top line|bottom\n" LCD: two lines of text; the Mac formats it.

  Wiring (each LED): digital pin -> 1k resistor -> LED long leg (anode);
  LED short leg (cathode) -> breadboard blue (-) rail -> one wire to Arduino GND.
  LCD (optional): GND->blue rail, VCC->5V, SDA->A4, SCL->A5.

  The LCD is auto-detected at boot. With no LCD plugged in the LEDs still work
  (we probe address 0x27 first and skip all LCD calls if nothing answers, so a
  missing screen can never hang startup).
*/

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Appliance order: light, fan, tv, lamp, ac
const int PINS[] = {9, 10, 11, 8, 7};
const int NPINS = 5;
const uint8_t LCD_ADDR = 0x27;
const unsigned long TIMEOUT_MS = 10000;

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

bool hasLcd = false;          // set at boot by probing the I2C bus
char buf[40];
uint8_t n = 0;
unsigned long lastText = 0;
bool stale = false;

// Print s on a row and pad with spaces: no clear() flicker, no leftovers.
void row(uint8_t r, const char* s) {
  if (!hasLcd) return;
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
  if (strchr(buf, ',')) {            // LED command "a,b,c,..." in pin order
    char* p = buf;
    for (int i = 0; i < NPINS && p; i++) {
      digitalWrite(PINS[i], atoi(p) ? HIGH : LOW);
      char* c = strchr(p, ',');
      p = c ? c + 1 : 0;             // stop early if fewer values were sent
    }
  }
}

void setup() {
  for (int i = 0; i < NPINS; i++) pinMode(PINS[i], OUTPUT);
  Serial.begin(9600);

  // Probe for the LCD so a missing screen never blocks the LEDs.
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
  if (hasLcd && !stale && millis() - lastText > TIMEOUT_MS) {
    row(0, "NO SIGNAL");
    row(1, "Mac not sending");
    stale = true;
  }
}
