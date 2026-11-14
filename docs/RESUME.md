# RESUME - where we left off

Newest-state pointer for a new chat. Read this first, then `CONTEXT.md`
(decisions) and `PROGRESS.md` (build state). Last updated: 2026-11-15.

## One-line status
Cable-connected phone app works. Building a LOCAL web dashboard as the
can't-fail backup. No cloud. Networking over borrowed WiFi is a dead end
(explained below), so the cable stays for now.

## What happened this session (2026-11-15)
- **state_server.py midnight bug FIXED + tested.** The log has no date, so a run
  crossing 00:00 was split into two sessions and Stats showed a 110 s window
  with every profile at 0%. `parse_log` now rolls the day without starting a new
  session; only a real >30 min gap splits. New `_selftest_midnight` case passes
  (`python state_server.py --selftest`). Same run now reads correctly: 470 s
  window, profile A 100%, PASSIVE latency present.
- **Phone-to-Mac wireless: diagnosed, not fixable here.** The friend's WiFi
  ("Kamaruln73...@unifi", router is an AZ-Tech WR744 at 192.168.0.1, a ZTE F620
  is just the fibre ONT) has TWO access points sharing one SSID and it isolates
  clients. The Mac lands on one AP (confirmed: Mac 192.168.0.31 is in the
  router's ARP table), the phone lands on the other (phone 192.168.0.20 is NOT
  in the ARP table). Total L2 block both directions even with Relay Blocking
  (this firmware's name for client isolation) OFF on both bands. A logging probe
  confirmed the phone's HTTP request never reaches the Mac. It is NOT a code or
  app bug, and it is not our router to reconfigure.
- **app-monitor auto-discovery REWRITTEN (installed on the iPhone 17, builds
  clean).** `src/lib/useSystem.ts` now learns the Mac's lan_ip + Bonjour name
  from /health, races all known addresses on every reconnect (WiFi IP first,
  .local second), and re-searches after 3 failed polls, so it survives the DHCP
  move (.35 -> .31) and recovers itself when the cable is pulled IF the phone can
  reach the Mac. `src/app/settings.tsx` got a "Wireless check" that says plainly
  whether the cable is needed. tsc + expo lint clean.

## Decisions locked
- **Backup = ONE local web app served by state_server.py at `/`** (login screen
  + live dashboard reusing /state, /metrics, /history, /frame.jpg). Runs in the
  Mac's own browser (zero networking, guaranteed) and the phone's browser over
  the cable. NOT hosted on Vercel: a cloud page cannot reach the Mac's LAN data,
  and tunnelling the camera to the cloud would contradict RO2's edge/no-cloud
  claim (a judge could use that against us). A mock-data Vercel build is fine
  later as a portfolio showcase only.
- Cable now; for the viva bring ONE network we control (a hotspot or pocket
  router), join both Mac and phone to it. Demo needs no internet, so speed is
  irrelevant. The phone app is a monitoring/eval tool, not the graded system
  (camera -> Mac -> Arduino is the system).

## NEXT STEP (just say "go")
Build `web/dashboard.html` and add a `/` route to `state_server.py` do_GET
(serve it as text/html; 404 if missing). Patch point is already located:
insert a branch before the `/health` branch in `Handler.do_GET`. Server read
cleanly, do not touch the FYP Python or the native app.

## Run reminders
- Server: `source venv/bin/activate && python state_server.py` (prints the Mac
  address; also reachable as Amirv-Mac.local:8000).
- System: `python live_system.py` (Moondream) / `python live_system.py qwen`.
- Resume this chat if VS Code closes: `claude --continue` (or `claude --resume`).
