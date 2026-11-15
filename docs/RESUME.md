# RESUME - where we left off

Newest-state pointer for a new chat. Read this first, then `CHECKLIST.md`
(what is built vs not), `CONTEXT.md` (decisions), `PROGRESS.md` (build state).
Last updated: 2026-11-15 (late).

## One-line status
Dashboard + Trials recorder BUILT. The three live-run fixes are BUILT and
VALIDATED in a second run. **Before: 73 trials, 94.5%. After: 77 trials, 89.6%
raw -> A & B both now 100% (were 90/80), and 98.0% (50/51) once operator timing
settled.** The before/after is the Chapter 4 story. Next = writing + the
per-transition latency table.

## What happened LATE (2026-11-15, the fixes + validation)
- **Three fixes built + validated** (all confirmed in `live_log.csv`):
  1. **Posture debounce** (`debounce_vlm`, `POSTURE_DEBOUNCE_N=2`): the fix is on the
     VLM READ SEQUENCE, not frames. The old 4 s vote window only smoothed pose
     frames; one VLM read is copied onto every frame, floods the window in ~1 s, so
     it never damped the VLM. Now 2 consecutive agreeing reads before the posture
     switches. Result: A 90->100%, B 80->100% (the two the flicker was wrecking).
     Cost: standing (T) is ~1 read slower to detect - documented tradeoff.
  2. **Fist "leaving" latch** (`leave_target` + `leaving_latch`): all-off until the
     room empties (C) or ANY gesture cancels it. Fist sets NO per-appliance holds
     anymore (`GESTURE_HOLDS["fist"]=[]`), so if you change your mind, one gesture
     releases the latch and the automatic profile fully restores (previously the
     fan/TV stayed stuck off ~60 s). Confirmed: `fist -> PASSIVE A` kept 0,0,0.
  3. **ACTIVE->PASSIVE log row**: app/LCD no longer freeze on ACTIVE. Confirmed a
     PASSIVE row logs ~3 s after every ACTIVE.
- **Per-trial latency**: each trial now records `vlm_latency_s` (detection) with
  decide/actuate. Shown in the result banner. `trials.csv` migrated to 9 columns.
- **Dashboard**: capture countdown lifted to App level so it survives tab switches
  (floating banner on EVERY tab - arm it, switch to Live, watch the profile). 15 s
  capture delay added.
- **Before set archived**: `archive/trials_before_debounce_2026-11-15.csv` (73 rows).

## What happened earlier (2026-11-15, afternoon/evening)
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

## NEXT STEP
All three fixes are done + validated. The remaining work is WRITING, not code:
- Chapter 4: the before/after (94.5% -> A&B 100%, 98% settled) + the T-lag tradeoff.
- The per-transition camera->LED wall-clock latency table (per-trial `vlm_latency_s`
  + decide/actuate are logged; still need the transition table).
- Document the two deliberate behaviours as limitations, not bugs: ~20 s to confirm
  unoccupied (`EMPTY_SECONDS` hysteresis); bent-over-desk can read A then self-correct.
If you want a tidier "after" headline, one short clean trial pass (timing now dialed
in) would land near 98%, but the 77-trial set is honest and usable as-is.

## Where the results live (for the writing / viva)
- `trials.csv` - the AFTER-fix RO3 dataset (77 rows, +`vlm_latency_s`). COMMITTED.
- `archive/trials_before_debounce_2026-11-15.csv` - the BEFORE set (73 rows, 94.5%). COMMITTED.
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
