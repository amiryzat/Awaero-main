"""
state_server - LAN bridge between the FYP decision log and the phone app.

Reads live_log.csv (written by live_system.py), classify_results.csv, and the
latest camera frame, and serves them as JSON over the local network. Stdlib only.

Rules (app-monitor/PRD.md Section 3):
  - Never imports serial_actuator. Only live_system.py owns the serial port.
  - Never writes live_log.csv. That file is FYP evidence.
  - LAN only. No cloud, no account, no telemetry.

Usage:
    python state_server.py                               serve the real log
    python state_server.py --replay fixtures/replay_log.csv   serve a fixture
    python state_server.py --selftest                    check the math
"""

import argparse
import csv
import io
import json
import math
import mimetypes
import os
import socket
import threading
import time
from datetime import date, datetime, time as dtime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "live_log.csv")
EVAL_PATH = os.path.join(HERE, "classify_results.csv")
FRAME_PATH = os.path.join(HERE, "live_frame.jpg")   # written by live_system.py
DIST = os.path.join(HERE, "web-dashboard", "dist")  # the built web dashboard (PRD 6.2)
TRIALS_PATH = os.path.join(HERE, "trials.csv")      # written by the Trials recorder (RO3)

STALE_SECONDS = 30            # newest row older than this -> not online
SESSION_GAP_SECONDS = 30 * 60  # a gap this long, or time going backwards, splits sessions
FRAME_FRESH_SECONDS = 5       # a frame older than this is not "live"
APPLIANCES = ("light", "fan", "tv")
PROFILES = ("T", "A", "B", "C")

# live_log.csv holds three kinds of row and only the first kind is a DECISION
# (a committed profile or gesture that drove the appliances):
#   PASSIVE / ACTIVE / MANUAL -> a decision, carries light/fan/tv
#   VLM                       -> one per VLM inference: a latency sample + heartbeat
#   ACTIVE_ENTER              -> gesture mode was entered, diagnostic only
# Treating every row as a decision made the app show "mode VLM, appliances all
# off" while someone sat in a lit room, and inflated the activation reduction.
DECISION_MODES = ("PASSIVE", "ACTIVE", "MANUAL")


def is_decision(r):
    return r.get("mode") in DECISION_MODES


# ---- parsing ----------------------------------------------------------------

def parse_log(text, anchor_date):
    """CSV text -> rows with ts (epoch), session index and dur (seconds).

    The log has no date column, so dates are inferred: time going backwards
    means a new day, and the LAST row is pinned to anchor_date (the file's mtime
    date). A new day is NOT by itself a new session: a run that crosses midnight
    is one session, so the split is decided by the real elapsed gap once the day
    has rolled. The log is change-triggered, so a
    decision's duration is the gap to the NEXT DECISION, skipping the VLM and
    ACTIVE_ENTER rows logged in between. The last decision of a session gets 0:
    the log does not say when that session stopped.
    """
    rows, day, prev, session = [], 0, None, 0
    for r in csv.DictReader(io.StringIO(text)):
        try:
            h, m, s = (int(x) for x in r["time"].split(":"))
        except (KeyError, ValueError, AttributeError, TypeError):
            continue                      # half-written or malformed line
        secs = h * 3600 + m * 60 + s
        if prev is not None:
            gap = secs - prev
            if gap < 0:                   # past midnight: roll the day, then judge the gap
                day, gap = day + 1, gap + 86400
            if gap > SESSION_GAP_SECONDS:
                session += 1
        prev = secs
        rows.append({**r, "_day": day, "_secs": secs, "session": session})
    base = datetime.combine(anchor_date, dtime.min) - timedelta(days=day)
    for r in rows:
        r["ts"] = (base + timedelta(days=r.pop("_day"), seconds=r.pop("_secs"))).timestamp()
    dec = [r for r in rows if is_decision(r)]
    for a, b in zip(dec, dec[1:]):
        a["dur"] = b["ts"] - a["ts"] if a["session"] == b["session"] else 0.0
    if dec:
        dec[-1]["dur"] = 0.0
    for r in rows:
        r.setdefault("dur", 0.0)      # VLM / ACTIVE_ENTER rows hold no time
    return rows


def _num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def gate_active(r):
    """Pose and VLM disagreed and pose won: the VLM said something, and the
    committed profile is not what it said."""
    return r["mode"] == "PASSIVE" and bool(r.get("vlm")) and r["vlm"] != r["profile"]


def decision(r):
    return {
        "at": datetime.fromtimestamp(r["ts"]).astimezone().isoformat(timespec="seconds"),
        "date_inferred": True,
        "mode": r["mode"],
        "profile": r["profile"],
        "people": _num(r.get("people"), int),
        "pose": r.get("pose") or None,
        "vlm": r.get("vlm") or None,
        "phone": r.get("phone") or None,
        "vlm_latency_s": _num(r.get("vlm_latency_s")),
        "decide_latency_ms": _num(r.get("decide_latency_ms")),
        "actuate_latency_ms": _num(r.get("actuate_latency_ms")),
        "appliances": {k: r.get(k) == "1" for k in APPLIANCES},
    }


# ---- metrics ----------------------------------------------------------------

def stat(vals):
    """n / mean / p50 / p95, nearest-rank percentiles. None when there is no data."""
    if not vals:
        return None
    v = sorted(vals)
    pick = lambda q: v[max(0, math.ceil(q * len(v)) - 1)]
    return {"n": len(v), "mean": round(sum(v) / len(v), 2), "p50": pick(0.5), "p95": pick(0.95)}


def _iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def metrics(rows, window="session", tail=0.0, now=None):
    """tail = seconds the newest row has been running (only while live)."""
    if window == "session":
        win = [r for r in rows if r["session"] == rows[-1]["session"]] if rows else []
    elif window == "today":
        midnight = datetime.combine(date.fromtimestamp(now or time.time()), dtime.min).timestamp()
        win = [r for r in rows if r["ts"] >= midnight]
    else:
        win = rows
    sel = [r for r in win if is_decision(r)]      # only decisions hold time
    if not sel:
        return None
    durs = [r["dur"] for r in sel]
    all_dec = [r for r in rows if is_decision(r)]
    if sel[-1] is all_dec[-1]:                    # newest decision is still running
        durs[-1] += tail
    total = sum(durs)

    activation = None            # one row has no measurable duration yet
    if total > 0:
        per = {}
        for k in APPLIANCES:
            on = sum(d for r, d in zip(sel, durs) if r.get(k) == "1")
            per[k] = {"on_seconds": round(on, 1), "baseline_seconds": round(total, 1),
                      "reduction_pct": round(100 * (1 - on / total), 1)}
        activation = {
            "reduction_pct": round(sum(p["reduction_pct"] for p in per.values()) / len(per), 1),
            "per_appliance": per,
        }

    passive_total = sum(d for r, d in zip(sel, durs) if r["mode"] == "PASSIVE")
    dist = {}
    for p in PROFILES:
        s = sum(d for r, d in zip(sel, durs) if r["mode"] == "PASSIVE" and r["profile"] == p)
        dist[p] = {"seconds": round(s, 1),
                   "pct": round(100 * s / passive_total, 1) if passive_total else 0.0}

    def col(name, mode=None, src=None):
        return [x for x in (_num(r.get(name)) for r in (sel if src is None else src)
                            if mode in (None, r["mode"])) if x is not None]

    # One VLM latency sample per inference. A PASSIVE row repeats the latency of
    # whichever answer was current, so counting those too would double-count.
    # Older logs (before per-inference VLM rows) only have it on PASSIVE rows.
    vlm_rows = [r for r in win if r.get("mode") == "VLM"]
    vlm_s = stat(col("vlm_latency_s", src=vlm_rows) if vlm_rows else col("vlm_latency_s"))

    return {
        "window": {"from": _iso(sel[0]["ts"]), "to": _iso(sel[-1]["ts"] + durs[-1]),
                   "seconds": round(total, 1)},
        "activation": activation,
        "latency": {
            "decide_ms": {m: stat(col("decide_latency_ms", m)) for m in ("PASSIVE", "ACTIVE")},
            "actuate_ms": stat(col("actuate_latency_ms")),
            "vlm_s": vlm_s,
        },
        "profile_distribution": dist,
        # One entry per row in the window, oldest first, for the timeline chart.
        "timeline": [{"at": _iso(r["ts"]), "seconds": round(d, 1), "mode": r["mode"],
                      "profile": r["profile"],
                      "appliances": {k: r.get(k) == "1" for k in APPLIANCES}}
                     for r, d in zip(sel, durs)],
        "accuracy": {"live": live_accuracy(), "offline": offline_accuracy()},   # live: Trials recorder
    }


def offline_accuracy(path=EVAL_PATH):
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        captured = os.path.getmtime(path)
    except OSError:
        return None
    if not rows:
        return None
    correct = sum(r.get("correct") == "True" for r in rows)
    return {"n": len(rows), "correct": correct,
            "pct": round(100 * correct / len(rows), 1), "captured_at": _iso(captured)}


# ---- trials (RO3 live accuracy) ---------------------------------------------
# A trial = the human declares the GROUND TRUTH ("I am now sitting -> A") and the
# server snapshots its own current decision as the MEASURED value. correct is
# computed, never trusted from the client. One new file (trials.csv); live_log.csv
# is never touched. RO3 wants >=10 trials per response path.

TRIAL_PATHS = ("T", "A", "B", "C", "open_palm", "peace", "fist")
TRIAL_FIELDS = ["time", "expected", "got", "correct", "mode", "online",
                "decide_latency_ms", "actuate_latency_ms", "vlm_latency_s"]
_trial_lock = threading.Lock()


def _read_trials(path=TRIALS_PATH):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _summ(rows):
    if not rows:
        return None
    c = sum(r.get("correct") == "True" for r in rows)
    return {"n": len(rows), "correct": c, "pct": round(100 * c / len(rows), 1)}


def live_accuracy(path=TRIALS_PATH):
    """Overall + per-profile, for /metrics.accuracy.live (the dashboard card)."""
    rows = _read_trials(path)
    if not rows:
        return None
    out = _summ(rows)
    out["per_profile"] = {p: _summ([r for r in rows if r.get("expected") == p]) for p in PROFILES}
    return out


def trials_report(path=TRIALS_PATH):
    """Rows + per-path counts incl. gestures, for the Trials tab."""
    rows = _read_trials(path)
    per = {p: _summ([r for r in rows if r.get("expected") == p]) for p in TRIAL_PATHS}
    return {"rows": rows[::-1][:50], "n": len(rows),
            "overall": _summ(rows), "per_path": {k: v for k, v in per.items() if v}}


def record_trial(expected):
    """Snapshot the live decision now and score it against the declared label."""
    cur = (SRC.state().get("current") or {}) if SRC else {}
    online = SRC.state().get("online", False) if SRC else False
    got = cur.get("profile")
    row = {"time": _iso(time.time()), "expected": expected, "got": got or "",
           "correct": str(got == expected), "mode": cur.get("mode", ""),
           "online": str(bool(online)),
           # latency of the decision this trial captured: VLM inference (detection)
           # + decide compute (decision-making) + serial write (actuation).
           "vlm_latency_s": cur.get("vlm_latency_s") or "",
           "decide_latency_ms": cur.get("decide_latency_ms") or "",
           "actuate_latency_ms": cur.get("actuate_latency_ms") or ""}
    with _trial_lock:
        new = not os.path.exists(TRIALS_PATH)
        with open(TRIALS_PATH, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=TRIAL_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
    return row


def delete_last_trial():
    with _trial_lock:
        rows = _read_trials()
        if not rows:
            return None
        with open(TRIALS_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=TRIAL_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows[:-1])
        return rows[-1]


# ---- source -----------------------------------------------------------------

class Source:
    """The log file, re-parsed only when its mtime or size changes."""

    def __init__(self, path, replay=False):
        self.path, self.replay = path, replay
        self.started = time.time()
        self.sig, self.rows = None, []
        self.lock = threading.Lock()

    def load(self):
        with self.lock:
            try:
                st = os.stat(self.path)
            except OSError:
                self.sig, self.rows = None, []       # missing log is a normal empty state
                return self.rows
            sig = (st.st_mtime, st.st_size)
            if sig != self.sig:
                with open(self.path, newline="") as f:
                    rows = parse_log(f.read(), date.fromtimestamp(st.st_mtime))
                if self.replay and rows:
                    # Slide the fixture so its newest row lands at server start.
                    # A constant shift, so every duration stays exactly as written.
                    shift = self.started - rows[-1]["ts"]
                    for r in rows:
                        r["ts"] += shift
                self.sig, self.rows = sig, rows
            return self.rows

    def online(self, rows, now):
        """Decisions are change-triggered, so a quiet log does not mean a dead
        system. Liveness comes from the newest row of ANY kind: VLM rows land
        every couple of seconds while the loop runs, so they are a heartbeat on
        their own. A fresh camera frame also counts."""
        if not rows:
            return False
        return self.replay or frame_fresh(now) or now - rows[-1]["ts"] <= STALE_SECONDS

    def state(self):
        rows, now = self.load(), time.time()
        dec = [r for r in rows if is_decision(r)]
        cur = dec[-1] if dec else None               # the appliances follow decisions
        return {
            "online": self.online(rows, now),
            # age of the newest row of any kind: how fresh the feed is
            "stale_seconds": round(now - rows[-1]["ts"]) if rows else 0,
            "source": "replay" if self.replay else "live",
            "current": decision(cur) if cur else None,
            "gate_active": gate_active(cur) if cur else False,
            "override": None,                         # Phase 7
        }

    def metrics(self, window):
        rows, now = self.load(), time.time()
        dec = [r for r in rows if is_decision(r)]
        live = dec and not self.replay and self.online(rows, now)
        return metrics(rows, window, tail=now - dec[-1]["ts"] if live else 0.0, now=now)


def frame_fresh(now=None):
    try:
        return (now or time.time()) - os.path.getmtime(FRAME_PATH) <= FRAME_FRESH_SECONDS
    except OSError:
        return False


def local_name():
    """The Mac's Bonjour name, e.g. Amirv-Mac.local. Unlike the LAN IP this
    survives a DHCP lease change, which silently broke the phone's connection
    once already (the IP moved .31 -> .35 mid-session). iOS resolves it."""
    try:
        import subprocess
        n = subprocess.run(["scutil", "--get", "LocalHostName"],
                           capture_output=True, text=True, timeout=2).stdout.strip()
        return f"{n}.local" if n else None
    except Exception:
        return None


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))     # UDP connect sends nothing, just picks a route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---- http -------------------------------------------------------------------

SRC = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if ctype == "application/json":
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/trials":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            expected = str(json.loads(self.rfile.read(n) or b"{}").get("expected", "")).strip()
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "bad json"})
        if expected not in TRIAL_PATHS:
            return self._send(400, {"error": "expected must be one of %s" % (TRIAL_PATHS,)})
        self._send(200, record_trial(expected))

    def do_DELETE(self):
        if urlparse(self.path).path != "/trials/last":
            return self._send(404, {"error": "not found"})
        removed = delete_last_trial()
        self._send(200 if removed else 404, {"removed": removed})

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/health":
            self._send(200, {"ok": True, "source": "replay" if SRC.replay else "live",
                             "rows": len(SRC.load()), "log_path": SRC.path,
                             "lan_ip": lan_ip(), "local_name": local_name()})
        elif url.path == "/state":
            self._send(200, SRC.state())
        elif url.path == "/history":
            limit = _num(q.get("limit", ["200"])[0], int) or 200
            dec = [r for r in SRC.load() if is_decision(r)]
            self._send(200, [decision(r) for r in dec[::-1][:max(1, limit)]])
        elif url.path == "/metrics":
            self._send(200, SRC.metrics(q.get("window", ["session"])[0]))
        elif url.path == "/trials":
            self._send(200, trials_report())
        elif url.path == "/frame.jpg":
            if not frame_fresh():
                return self._send(404, {"error": "no live frame"})
            try:
                with open(FRAME_PATH, "rb") as f:
                    self._send(200, f.read(), "image/jpeg")
            except OSError:
                self._send(404, {"error": "no live frame"})
        else:
            self._serve_static(url.path)   # the built web dashboard (PRD 6.2)

    def _serve_static(self, path):
        """Serve web-dashboard/dist/ for any path the API routes above did not
        claim. Read-only. The only disk-by-request serving this project does, so
        the traversal guard below is a hard trust boundary even on a LAN."""
        index = os.path.join(DIST, "index.html")
        if not os.path.isfile(index):      # normal state before the first build
            return self._send(503, b"web-dashboard not built yet. "
                              b"Run: cd web-dashboard && npm run build\n", "text/plain")
        dist_real = os.path.realpath(DIST)
        target = os.path.realpath(os.path.join(DIST, path.lstrip("/") or "index.html"))
        if target != dist_real and not target.startswith(dist_real + os.sep):
            return self._send(403, {"error": "forbidden"})   # escaped dist/
        if not os.path.isfile(target):
            target = index                 # SPA fallback: unknown route -> index.html
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        try:
            with open(target, "rb") as f:
                self._send(200, f.read(), ctype)
        except OSError:
            self._send(404, {"error": "not found"})

    def log_message(self, *args):      # the phone polls every 2 s, keep the terminal quiet
        pass


# ---- selftest ---------------------------------------------------------------

SELFTEST_CSV = """time,mode,people,pose,vlm,phone,vlm_latency_s,profile,light,fan,tv
10:00:00,PASSIVE,0,C,,,,C,0,0,0
10:01:00,PASSIVE,1,A,T,no,15.0,T,1,0,0
10:03:00,PASSIVE,1,A,B,no,16.0,A,1,1,1
10:06:00,PASSIVE,1,B,,,,B,0,1,0
10:06:40,ACTIVE,,,,,,open_palm,0,0,1
09:00:00,PASSIVE,0,C,,,,C,0,0,0
09:01:40,PASSIVE,1,A,,,,A,1,1,1
"""


# The log as live_system.py writes it today: VLM rows between the decisions, and
# an ACTIVE_ENTER row. Only the 4 PASSIVE/ACTIVE rows are decisions.
MIXED_CSV = """time,mode,people,pose,vlm,phone,vlm_latency_s,profile,light,fan,tv
10:00:00,PASSIVE,0,C,,,,C,0,0,0
10:00:30,VLM,,,C,,1.0,,,,
10:01:00,PASSIVE,1,A,A,,2.0,A,1,1,1
10:01:30,VLM,,,A,,3.0,,,,
10:02:00,ACTIVE_ENTER,1,,,,,OK,,,
10:03:00,ACTIVE,1,,,,,open_palm,1,0,1
10:04:00,PASSIVE,1,A,B,,1.0,B,0,1,0
10:04:30,VLM,,,B,,1.2,,,,
"""


# A run that crosses midnight. live_log.csv has no date, so 00:01:00 looks
# EARLIER than 23:59:00; treating that as a new session chopped the real
# 2026-11-14 run in two and left Stats showing a 110 s window with every profile
# at 0%. A new day is not a new session; only a long gap is.
MIDNIGHT_CSV = """time,mode,people,pose,vlm,phone,vlm_latency_s,profile,light,fan,tv
23:58:00,PASSIVE,1,A,A,,1.0,A,1,1,1
23:59:00,VLM,,,A,,1.0,,,,
00:00:00,PASSIVE,1,A,B,,1.0,B,0,1,0
00:01:00,PASSIVE,0,C,,,,C,0,0,0
"""


def _selftest_midnight():
    rows = parse_log(MIDNIGHT_CSV, date(2026, 11, 15))
    assert [r["session"] for r in rows] == [0, 0, 0, 0]       # one run, not two
    assert [r["dur"] for r in rows] == [120, 0, 60, 0]        # 23:58 -> 00:00 is 120 s
    assert date.fromtimestamp(rows[0]["ts"]) == date(2026, 11, 14)
    assert date.fromtimestamp(rows[-1]["ts"]) == date(2026, 11, 15)
    m = metrics(rows, "session")
    assert m["window"]["seconds"] == 180
    assert m["profile_distribution"]["A"]["pct"] == 66.7     # not 0.0
    # A real stop and restart still splits, even across midnight.
    far = MIDNIGHT_CSV.replace("00:01:00", "01:01:00")
    assert [r["session"] for r in parse_log(far, date(2026, 11, 15))] == [0, 0, 0, 1]
    print("selftest midnight ok")


def _selftest_mixed():
    """The format that broke the old parser. Decisions at 10:00, 10:01, 10:03,
    10:04, so durations 60, 120, 60, 0 and a 240 s window."""
    rows = parse_log(MIXED_CSV, date(2026, 11, 14))
    assert len(rows) == 8
    dec = [r for r in rows if is_decision(r)]
    assert [r["profile"] for r in dec] == ["C", "A", "open_palm", "B"]
    assert [r["dur"] for r in dec] == [60, 120, 60, 0]
    assert all(r["dur"] == 0 for r in rows if not is_decision(r))

    # The newest ROW is a VLM row; the newest DECISION is the B row. The app must
    # show the decision, not "mode VLM" with every appliance off.
    assert rows[-1]["mode"] == "VLM" and dec[-1]["profile"] == "B"
    d = decision(dec[-1])
    assert d["mode"] == "PASSIVE" and d["appliances"] == {"light": False, "fan": True, "tv": False}

    m = metrics(rows, "all")
    assert m["window"]["seconds"] == 240
    per = m["activation"]["per_appliance"]
    assert per["light"]["on_seconds"] == 180 and per["light"]["reduction_pct"] == 25.0
    assert per["fan"]["on_seconds"] == 120 and per["fan"]["reduction_pct"] == 50.0
    assert per["tv"]["on_seconds"] == 180 and per["tv"]["reduction_pct"] == 25.0
    assert m["activation"]["reduction_pct"] == 33.3
    dist = m["profile_distribution"]                      # passive seconds = 180
    assert [dist[p]["pct"] for p in PROFILES] == [0.0, 66.7, 0.0, 33.3]
    assert len(m["timeline"]) == 4                        # decisions only

    # One latency sample per inference: the 3 VLM rows, NOT the copies that the
    # PASSIVE rows carry (counting those too would report n=6).
    assert m["latency"]["vlm_s"] == {"n": 3, "mean": 1.73, "p50": 1.2, "p95": 3.0}
    print("selftest mixed ok")


def _selftest():
    """Hand-checked. Durations: 60, 120, 180, 40, 0 (session ends), 100, 0."""
    rows = parse_log(SELFTEST_CSV, date(2026, 11, 14))
    assert [r["dur"] for r in rows] == [60, 120, 180, 40, 0, 100, 0]
    assert [r["session"] for r in rows] == [0, 0, 0, 0, 0, 1, 1]     # backwards jump splits
    assert date.fromtimestamp(rows[0]["ts"]) == date(2026, 11, 13)   # earlier session, day before
    assert date.fromtimestamp(rows[-1]["ts"]) == date(2026, 11, 14)  # last row on the anchor date
    assert [gate_active(r) for r in rows] == [False, False, True, False, False, False, False]

    m = metrics(rows, "all")
    assert m["window"]["seconds"] == 500
    per = m["activation"]["per_appliance"]
    assert per["light"]["on_seconds"] == 300 and per["light"]["reduction_pct"] == 40.0
    assert per["fan"]["on_seconds"] == 220 and per["fan"]["reduction_pct"] == 56.0
    assert per["tv"]["on_seconds"] == 180 and per["tv"]["reduction_pct"] == 64.0
    assert m["activation"]["reduction_pct"] == 53.3                  # (40 + 56 + 64) / 3
    dist = m["profile_distribution"]                                  # passive seconds = 500
    assert [dist[p]["pct"] for p in PROFILES] == [24.0, 36.0, 8.0, 32.0]
    assert m["latency"]["vlm_s"] == {"n": 2, "mean": 15.5, "p50": 15.0, "p95": 16.0}
    assert m["latency"]["decide_ms"] == {"PASSIVE": None, "ACTIVE": None}   # not logged, not zero

    assert [t["seconds"] for t in m["timeline"]] == [60, 120, 180, 40, 0, 100, 0]
    assert m["timeline"][2]["profile"] == "A" and m["timeline"][2]["appliances"]["fan"] is True

    s = metrics(rows, "session")                                      # newest session only
    assert s["window"]["seconds"] == 100 and s["activation"]["reduction_pct"] == 100.0
    assert metrics(rows, "session", tail=100)["activation"]["per_appliance"]["tv"]["reduction_pct"] == 50.0
    assert metrics([], "all") is None and metrics(rows[-1:], "all")["activation"] is None

    d = decision(rows[4])                                             # active row: blanks are null
    assert d["people"] is None and d["vlm_latency_s"] is None and d["appliances"]["tv"] is True

    with open(os.path.join(HERE, "fixtures", "replay_log.csv")) as f:
        fx = parse_log(f.read(), date(2026, 11, 14))
    assert len(fx) == 39 and fx[-1]["session"] == 1 and gate_active(fx[-1])
    assert metrics(fx, "session")["window"]["seconds"] == 8700        # 08:00:00 to 10:25:00
    print("selftest ok")
    _selftest_mixed()
    _selftest_midnight()
    _selftest_trials()


def _selftest_trials():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "trials.csv")
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=TRIAL_FIELDS)
            w.writeheader()
            for exp, got in [("A", "A"), ("A", "A"), ("A", "T"), ("B", "B"), ("C", "C")]:
                w.writerow({"time": "t", "expected": exp, "got": got,
                            "correct": str(got == exp), "mode": "PASSIVE", "online": "True",
                            "decide_latency_ms": "", "actuate_latency_ms": ""})
        a = live_accuracy(p)
        assert a["n"] == 5 and a["correct"] == 4 and a["pct"] == 80.0, a
        assert a["per_profile"]["A"] == {"n": 3, "correct": 2, "pct": 66.7}, a["per_profile"]["A"]
        assert a["per_profile"]["T"] is None, a["per_profile"]["T"]   # no T trial -> null
        assert live_accuracy(os.path.join(d, "none.csv")) is None     # no file -> no figure
    print("selftest trials ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="LAN state server for app-monitor")
    ap.add_argument("--replay", metavar="CSV", help="serve a fixture instead of live_log.csv")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    else:
        SRC = Source(os.path.abspath(args.replay) if args.replay else LOG_PATH, bool(args.replay))
        print(f"state server ({'REPLAY ' + SRC.path if SRC.replay else 'live log'})")
        name = local_name()
        print(f"Phone address: {lan_ip()}  (port {args.port})")
        if name:
            print(f"  or, better: {name}   (keeps working when the IP changes)")
        ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
