// First test of the 16x2 I2C LCD on the second (black) board.
// Wiring: GND->GND, VCC->5V, SDA->A4, SCL->A5.
// The I2C backpack answers at 0x27 or 0x3F depending on the maker, so scan for it.

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

uint8_t findLcd() {
  const uint8_t candidates[] = {0x27, 0x3F};
  for (uint8_t a : candidates) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) return a;
  }
  return 0;
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  uint8_t addr = findLcd();
  if (!addr) {
    Serial.println("LCD NOT FOUND (check SDA/SCL wires)");
    return;
  }
  Serial.print("LCD found at 0x");
  Serial.println(addr, HEX);

  LiquidCrystal_I2C lcd(addr, 16, 2);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Smart Power FYP");
  lcd.setCursor(0, 1);
  lcd.print("LCD works!");
}

void loop() {}
