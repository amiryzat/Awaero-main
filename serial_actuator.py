"""
serial_actuator - sends LED states to the Arduino over USB serial.

Replaces the mock-actuation print in live_passive.py / live_active.py.
Auto-detects the board's serial port, so you do not hardcode /dev/cu.*.

Protocol matches arduino/room_node/room_node.ino: one 0/1 per appliance,
comma separated, in pin order light,fan,tv,lamp,ac ("1,0,1,1,0\n"). The
firmware sets only the values it is given, so a 3-value line still works.

Usage:
    from serial_actuator import Actuator
    act = Actuator()           # opens the port, or runs in mock mode if none
    act.set(1, 0, 0, 1, 0)     # light, fan, tv, lamp, ac
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
        self.port = None          # the port actually opened (the LCD driver avoids it)
        if serial is None:
            print("[actuator] pyserial not installed - mock mode")
            return
        port = port or find_port()
        if not port:
            print("[actuator] no Arduino port found - mock mode")
            return
        try:
            self.ser = serial.Serial(port, BAUD, timeout=1)
            self.port = port
            time.sleep(2)  # Arduino resets on connect; wait for it
            print(f"[actuator] connected on {port}")
        except Exception as e:
            print(f"[actuator] could not open {port}: {e} - mock mode")
            self.ser = None

    def set(self, *values):
        """Send one 0/1 per appliance in pin order (light, fan, tv, lamp, ac).
        Variadic so the appliance count can change without touching callers;
        the firmware only drives the pins it is actually given values for."""
        msg = ",".join(str(int(bool(v))) for v in values) + "\n"
        if self.ser:
            try:
                self.ser.write(msg.encode())
                # write() only fills the OS buffer. flush() asks for it to drain,
                # but on macOS USB-serial it still returns in ~0.1 ms, so the
                # timing around this call measures HOST-SIDE write time only, not
                # the moment the LED changes. Measured 0.1 ms over 6 writes
                # (2026-11-14). A true end-to-end number needs the Arduino to ack.
                self.ser.flush()
                return
            except Exception as e:
                print(f"[actuator] write failed: {e}")
        print(f"[actuator mock] {msg.strip()}")

    def close(self):
        if self.ser:
            try:
                self.set(0, 0, 0, 0, 0)
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
