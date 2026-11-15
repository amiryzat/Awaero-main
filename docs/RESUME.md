# RESUME - where we left off

Newest-state pointer for a new chat. Read this first, then `CHECKLIST.md`
(what is built vs not), `CONTEXT.md` (decisions), `PROGRESS.md` (build state).
Last updated: 2026-11-15 (evening).

## One-line status
Web dashboard + Trials recorder BUILT. First real RO3 run done: **73 trials,
94.5%**. Three real flaws found in the live run, fixes listed and ranked. Next
step = build the posture debounce, then one clean re-run.

## What happened this session (2026-11-15, afternoon/evening)
- **Local web dashboard BUILT (React+Vite "Awaero").** Served by `state_server.py`
  at `/` from `web-dashboard/dist/` (login gate + Home/Live/Stats/Trials), follows
  the reference UI, path-traversal guarded, build stamp in the footer. Reachable in
  the Mac browser AND the phone browser (hit the Mac at 192.168.0.16:8000 from the
  phone this session). Commits: 6f744bf, c2ee697, cc80676.
- **Trials recorder BUILT - the RO3 instrument (closes the biggest gap).** You
  declare the ground truth (what it SHOULD read); the server snapshots its own live
  decision and scores it (`trials.csv`). A capture countdown (3/10/20s) lets you get
  into B (lying) / C (leaving) before the trial fires, since you cannot be in the
  state AND at the keyboard. Endpoints: POST/GET /trials, DELETE /trials/last; live
  accuracy flows into /metrics -> the Stats accuracy card. Selftest covers the math.
- **First real run: 73 trials, 94.5%** (T 11/11, A 9/10, B 8/10, C 10/10). All 73
  recorded online=True (valid). Data in `trials.csv` (now committed).
- **Live run flaws found (watched via sampled frames + the decision log):**
  1. VLM flip-flops T<->A on the same desk scene every ~2 s -> light/fan/TV flicker,
     and a STANDING person read as sitting (A) -> all appliances ON (IMG_0369). Pose
     was correct (T) there; the VLM is the posture authority and it erred.
  2. Fist turns all off, but when ACTIVE ends (6 s) PASSIVE re-commits A and powers
     everything back on - so fist is only a momentary all-off, not a "leaving" latch.
  3. App froze showing ACTIVE for a 5-min log gap while the LCD correctly showed
     PASSIVE - the app is decision-triggered, the LCD is frame-triggered.
  4. Cosmetic: pose phantom box parks on the clothes rail when lying down (VLM still
     gives B); pose "0 ppl" when an arm is raised. Document for Q&A, no fix.

## Decisions locked (still true)
- Backup = ONE local web app served by `state_server.py` at `/`. NOT Vercel (a cloud
  page can't reach the Mac LAN; would contradict RO2 edge/no-cloud). Mock-data Vercel
  OK later as portfolio only.
- Cable now; for the viva bring ONE network we control (hotspot / pocket router).
  Borrowed WiFi isolates clients (two APs share one SSID) - not our router to change.
- Single-room, single-occupant scope. Keep the scene to one person for clean data.
- Passive engine = Moondream (default). pose = presence, VLM = posture, profile HELD
  when no VLM answer. FUSED_APP is authoritative.

## NEXT STEP (just say "go")
**Build the posture debounce in `live_system.py`** - require N consistent VLM reads
before switching profile. One change kills flaw #1's flicker AND the standing->A
misfire. Read the fusion loop first; leave N as a tunable knob. Then: one clean trial
re-run (should beat 94.5%), keep BOTH sets for a before/after in Chapter 4.
After that, in order: fist "leaving" latch (#2), log a PASSIVE row on ACTIVE->PASSIVE
return (#3). All three are in CHECKLIST.md under "Fixes to do".

## Where the results live (for the writing / viva)
- `trials.csv` - the RO3 accuracy dataset (73 rows, expected/got/correct + latency). COMMITTED.
- `live_log.csv` - every decision, VLM inference, gesture, with latency (master log).
- `vlm_descriptions.csv` - every VLM frame + its text + latency.
- `classify_results.csv` - offline labelled set (12/12).
- `snapshots/` (220) + `snapshots/vlm/` (1833) - visual evidence (local, gitignored).
- The dashboard Stats tab renders activation reduction (~15.6% last window) + accuracy live.

## Run reminders
- Server: `python state_server.py` (prints the Mac address; also Amirv-Mac.local:8000).
  Serves the dashboard at `/`. `--selftest` checks the math.
- System: `python live_system.py` (Moondream) / `python live_system.py qwen`.
- Dashboard: build with `cd web-dashboard && npm run build` (serve dist/, never the
  dev server). Footer stamp must match HEAD or the dist/ is stale.
- **Next live test: launch `live_system.py` as a TRACKED background process** so Claude
  is pinged on exit and can analyze the whole run (it kept dying untracked this session
  when the Continuity Camera slept). See memory `feedback-live-test-tracked`.
- Resume this chat if VS Code closes: `claude --continue` (or `claude --resume`).

## LCD note
`lcd_scroll.py` added (scroll a message across the LCD top line; close live_system.py
first - one program per display board). LCD random-symbols issue still open; suspect
power/brown-out, fix = double lcd.init(). LEDs + app are the real actuation, not blocking.
