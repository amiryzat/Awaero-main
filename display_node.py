"""
Display node driver: sends two 16-character lines to the 16x2 I2C LCD.

The screen now lives on the SAME Arduino as the appliance LEDs (firmware
arduino/room_node.ino accepts both "a,b,c,d,e" for LEDs and "top|bottom" for
the screen on one wire), so the normal use is to hand it the actuator's open
port. Passing nothing still hunts for a separate board, which is how the old
two-board rig worked.

    lcd = LcdDisplay(ser=act.ser)        # one board: share the open port
    lcd.show("PASSIVE Sitting", "L+ F+ T- D+ A+")

Call show() as often as you like: it only writes when the text changes, plus a
heartbeat every few seconds so the board's NO SIGNAL timeout never fires while
the system is running.

Selftest: python display_node.py selftest
"""

import glob
import sys
import time

try:
    import serial  # pyserial
except ImportError:
    serial = None

BAUD = 9600
WIDTH = 16
HEARTBEAT_SECONDS = 3.0      # firmware shows NO SIGNAL after 10 s of silence
NAMES = {"T": "Standing", "A": "Sitting", "B": "Resting", "C": "Empty"}


def find_port(exclude=None):
    """The LCD board is a CH340 clone (/dev/cu.usbserial*). The LED board is an
    original Uno (/dev/cu.usbmodem*), so the two never share a pattern. `exclude`
    stops this grabbing the port the LED actuator already opened."""
    for p in sorted(glob.glob("/dev/cu.usbserial*")):
        if p != exclude:
            return p
    return None


def status_lines(mode, profile, gesture, appl):
    """The two screen lines for the current state (max 16 characters each).
    appl = (light, fan, tv, lamp, ac) as 0/1; gesture is ACTIVE mode only.
    Five appliances cannot fit "L:ON F:ON ..." in 16 columns, so each gets one
    initial and a +/- : "L+ F+ T- D+ A-" (Light Fan Tv Desklamp Ac) = 14."""
    if mode == "ACTIVE":
        top = "ACTIVE " + (gesture if gesture and gesture != "none" else "ready")
    else:
        top = "PASSIVE " + NAMES.get(profile, "?")
    bottom = " ".join(f"{c}{'+' if v else '-'}" for c, v in zip("LFTDA", appl))
    return top[:WIDTH], bottom[:WIDTH]


class LcdDisplay:
    def __init__(self, port=None, exclude=None, ser=None):
        self.ser = None
        self._last = None
        self._sent = 0.0
        self._owned = True          # False when we borrow someone else's port
        if ser is not None:         # one-board rig: share the actuator's port
            self.ser, self._owned = ser, False
            print("[lcd] sharing the appliance board's serial port")
            return
        if serial is None:
            print("[lcd] pyserial not installed - mock mode")
            return
        port = port or find_port(exclude)
        if not port:
            print("[lcd] no display board found - mock mode")
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=1)
            time.sleep(2)  # the board resets when the port opens
            print(f"[lcd] connected on {port}")
        except Exception as e:
            print(f"[lcd] could not open {port}: {e} - mock mode")
            self.ser = None

    def show(self, line1, line2=""):
        # The screen only knows plain ASCII, and '|' separates the two lines.
        clean = lambda s: s.replace("|", "/").replace("\n", " ").encode("ascii", "replace").decode()[:WIDTH]
        line1, line2 = clean(line1), clean(line2)
        msg = f"{line1}|{line2}\n"
        now = time.time()
        if msg == self._last and now - self._sent < HEARTBEAT_SECONDS:
            return
        changed = msg != self._last
        self._last, self._sent = msg, now
        if self.ser:
            try:
                self.ser.write(msg.encode())
                return
            except Exception as e:
                print(f"[lcd] write failed: {e}")
        if changed:
            print(f"[lcd mock] {line1!r} / {line2!r}")

    def close(self, bye="System stopped"):
        if self.ser:
            try:
                self.show(bye, "")
                if self._owned:     # never close a port we only borrowed
                    self.ser.close()
            except Exception:
                pass


def _selftest():
    assert status_lines("PASSIVE", "A", "none", (1, 1, 0, 1, 1)) == ("PASSIVE Sitting", "L+ F+ T- D+ A+")
    assert status_lines("PASSIVE", "C", "none", (0, 0, 0, 0, 0)) == ("PASSIVE Empty", "L- F- T- D- A-")
    assert status_lines("PASSIVE", "T", "none", (1, 1, 0, 0, 0))[0] == "PASSIVE Standing"
    assert status_lines("ACTIVE", "A", "open_palm", (0, 0, 1, 0, 0))[0] == "ACTIVE open_palm"
    assert status_lines("ACTIVE", "A", "none", (0, 0, 0, 0, 0))[0] == "ACTIVE ready"
    # nothing may ever exceed the 16-character screen width
    for mode in ("PASSIVE", "ACTIVE"):
        for prof in "TABC":
            for g in ("none", "open_palm", "peace", "fist"):
                assert all(len(s) <= WIDTH for s in status_lines(mode, prof, g, (1, 1, 1, 1, 1)))
    sent = []
    fake = LcdDisplay(port="/dev/does-not-exist")
    fake.ser = type("S", (), {"write": lambda self, b: sent.append(b)})()
    fake.show("a|bé\U0001F600", "x")             # '|' and non-ASCII must be cleaned
    assert sent == [b"a/b??|x\n"], sent
    lcd = LcdDisplay(port="/dev/does-not-exist")     # mock mode: must not crash
    lcd.show("a", "b")
    lcd.show("a", "b")                                # duplicate: silently skipped
    lcd.close()
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
