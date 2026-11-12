"""
serial_actuator - sends LED states to the Arduino over USB serial.

Replaces the mock-actuation print in live_passive.py / live_active.py.
Auto-detects the board's serial port, so you do not hardcode /dev/cu.*.

Protocol matches arduino/power_leds/power_leds.ino: "g,y,r\n" (0/1 each).

Usage:
    from serial_actuator import Actuator
    act = Actuator()           # opens the port, or runs in mock mode if none
    act.set(green=1, yellow=0, red=0)
    act.close()

If no Arduino is found it prints instead of failing, so the pipeline still
runs without hardware.
"""

import glob
import time

try:
    import serial  # pyserial
except ImportError:
    serial = None

BAUD = 9600


def find_port():
    # macOS Arduino ports look like /dev/cu.usbmodem* or /dev/cu.usbserial*
    for pattern in ("/dev/cu.usbmodem*", "/dev/cu.usbserial*", "/dev/cu.wchusbserial*"):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    return None


class Actuator:
    def __init__(self, port=None):
        self.ser = None
        if serial is None:
            print("[actuator] pyserial not installed - mock mode")
            return
        port = port or find_port()
        if not port:
            print("[actuator] no Arduino port found - mock mode")
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=1)
            time.sleep(2)  # Arduino resets on connect; wait for it
            print(f"[actuator] connected on {port}")
        except Exception as e:
            print(f"[actuator] could not open {port}: {e} - mock mode")
            self.ser = None

    def set(self, green, yellow, red):
        msg = f"{int(bool(green))},{int(bool(yellow))},{int(bool(red))}\n"
        if self.ser:
            try:
                self.ser.write(msg.encode())
                return
            except Exception as e:
                print(f"[actuator] write failed: {e}")
        print(f"[actuator mock] {msg.strip()}")

    def close(self):
        if self.ser:
            try:
                self.set(0, 0, 0)
                self.ser.close()
            except Exception:
                pass


if __name__ == "__main__":
    # Self-test: cycle the LEDs one by one, forever. Ctrl-C to stop.
    act = Actuator()
    try:
        while True:
            for g, y, r in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                act.set(g, y, r)
                print("sent", g, y, r)
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        act.close()
