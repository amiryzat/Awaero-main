"""Scroll a message across the LCD top line. Ctrl+C to stop.

    python lcd_scroll.py "HELLO FROM AMIR" ["fixed bottom line"] [seconds per step]
Close live_system.py first (only one program can use the display board).
"""
import sys
import time

from display_node import LcdDisplay, WIDTH

text = sys.argv[1] if len(sys.argv) > 1 else "SMART POWER MANAGEMENT"
bottom = sys.argv[2] if len(sys.argv) > 2 else ""
step = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3

lcd = LcdDisplay()
# blank padding so the text slides in from the right and fully out on the left
tape = " " * WIDTH + text + " " * WIDTH
try:
    while True:
        for i in range(len(tape) - WIDTH + 1):
            lcd.show(tape[i:i + WIDTH], bottom)
            time.sleep(step)
except KeyboardInterrupt:
    lcd.close("")
