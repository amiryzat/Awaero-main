"""
LCD playground: type two lines, see them appear on the little screen.

How to run (Terminal):
    cd ~/fyp-prototype
    source venv/bin/activate
    python lcd_playground.py

Then type something for the top line, press Enter, type the bottom line, press
Enter. The screen updates at once. Type  q  as the top line to quit.

Rules of the screen: 16 letters per line, 2 lines, plain English letters,
numbers and symbols (no emoji). Longer text is cut off.

Only ONE program can use the black board at a time, so close live_system.py
first.
"""

import threading
import time

from display_node import LcdDisplay, WIDTH


def preview(top, bottom):
    """Draw what the screen should look like, right in the Terminal."""
    box = lambda s: "|" + s[:WIDTH].ljust(WIDTH) + "|"
    print("  +" + "-" * WIDTH + "+")
    print("  " + box(top))
    print("  " + box(bottom))
    print("  +" + "-" * WIDTH + "+")


def main():
    lcd = LcdDisplay()
    state = {"lines": ("LCD playground", "type in Terminal"), "stop": False}

    # The board shows NO SIGNAL if it hears nothing for 10 s, and you will take
    # longer than that to type. This thread keeps repeating the current text.
    def keep_alive():
        while not state["stop"]:
            lcd.show(*state["lines"])
            time.sleep(0.2)

    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()

    print(__doc__.split("Rules")[0].strip().split("\n\n")[0])
    print("\nType q as the top line to quit.\n")
    try:
        while True:
            top = input("Top line    : ")
            if top.strip().lower() == "q":
                break
            bottom = input("Bottom line : ")
            if len(top) > WIDTH or len(bottom) > WIDTH:
                print(f"  (more than {WIDTH} letters, so it gets cut off)")
            state["lines"] = (top, bottom)
            preview(top, bottom)
            print()
    except (KeyboardInterrupt, EOFError):
        pass
    state["stop"] = True
    t.join()
    lcd.close(bye="Bye!")
    print("Bye!")


if __name__ == "__main__":
    main()
