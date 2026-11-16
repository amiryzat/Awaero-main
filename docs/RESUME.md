# RESUME - where we left off

Newest-state pointer for a new chat. Read this first, then `CHECKLIST.md`
(what is built vs not), `CONTEXT.md` (decisions), `PROGRESS.md` (build state).
Last updated: 2026-11-17 (after the 5-appliance hardware build + the Awaero phone-app session).

## One-line status
Dashboard + Trials recorder BUILT. The three live-run fixes are BUILT and
VALIDATED in a second run. **Before: 73 trials, 94.5%. After: 77 trials, 89.6%
raw -> A & B both now 100% (were 90/80), and 98.0% (50/51) once operator timing
settled.** The before/after is the Chapter 4 story. Next = writing + the
per-transition latency table.
**Hardware now: 5 appliances (light, fan, tv, desk lamp, aircond) + the LCD on
ONE Arduino, all tested; the decision policy was rewritten to the supervisor's
profiles doc.** Not yet done: a full camera->VLM->LED run with the 5 appliances.

## What happened 2026-11-16 (day): 5 appliances + LCD on one Arduino + new policy
The prototype went from 3 appliances to 5, the LCD moved onto the SAME Arduino as
the LEDs, and the decision policy was rewritten to
`FYP_Room_Activity_and_Appliance_Decision_Profiles.md`. Breadboard holes are all
recorded in the new `docs/WIRING.md`. Commits 4078b76, 3ff8338, 03adf11, 887bcec,
909efa3, ff173fb.
- **5 appliance LEDs**, wired and each tested lit: pin 9 light, 10 fan, 11 tv,
  **8 desk lamp, 7 aircond**. One Arduino GND feeds a blue (-) rail every LED short
  leg returns to; 5V feeds a red (+) rail for the LCD. (Closes the old GND-hole
  shortage item.)
- **LCD on the SAME Arduino** (`arduino/room_node.ino`), working at 0x27, no second
  board. The old "random symbols / boxes" was NOT an LCD fault: the firmware hung in
  setup() probing a not-yet-wired screen, which looked like dead LEDs. It now probes
  0x27 and skips every LCD call if nothing answers, so a missing screen never blocks
  the LEDs. `display_node.py` can share the actuator's open port
  (`LcdDisplay(ser=act.ser)`); `serial_actuator.set()` is variadic.
- **New 5-appliance policy** (`FUSED_APP`). Two deliberate reversals from the first
  prototype, both pinned by selftests: sitting (A) no longer turns the TV ON, and
  standing (T) no longer turns the fan OFF. The doc's "No change" rows use a HOLD
  sentinel (`resolve_hold`); T holds TV and AC. Desk lamp is ON only while sitting.
  **AC is an ASSUMED policy, NOT temperature-aware** (no sensor) - the writing must
  say so; a DHT11 later would make it genuine.

  | Profile | light | fan | tv | lamp | ac |
  |---|---|---|---|---|---|
  | A sitting | ON | ON | OFF | ON | ON |
  | T standing | ON | ON | hold | OFF | hold |
  | B lying | OFF | ON | OFF | OFF | ON |
  | C empty | OFF | OFF | OFF | OFF | OFF |

- **Activation-reduction metric fixed** (`state_server.py`): it now counts only
  appliances a log ACTUALLY recorded. An absent lamp/ac column was scored as "off
  the whole time" = a 100% saving for an appliance that never ran in that log, which
  would have inflated the headline Chapter 4 figure. Selftest added.
- **Stepper fan (PARKED)**: a 28BYJ-48 + ULN2003 was wired as the physical fan on
  pins 2-5 and spins (non-blocking, mirrors the fan value), but the geared motor
  tops out ~10-15 rpm - too slow to read as a fan. Owner is buying a fast DC motor
  (DC motor + fan blade + IRF520 MOSFET module) to replace it. Firmware kept as a
  working base (commit 887bcec).
- **Dashboard** shows all 5 (Home tiles, Live stage, Stats bars iterate whatever the
  server reports). Verified on real hardware: A lit light+fan+lamp+ac with the TV
  dark; T held AC through the transition; B dropped to fan+ac; C dark.
- **Still NOT done**: no full camera -> VLM -> LED run with 5 appliances yet (we only
  drove the LEDs directly). That live run is the next thing to verify.

## What happened 2026-11-16 (night): the Awaero phone app
- **New phone app `awaero-app/`, named Awaero** (`com.amiryzat.awaero`). It is a
  COPY of `app-monitor/`, made on the owner's instruction not to disturb the old
  app. `app-monitor/` is untouched and still installed; both sit on the iPhone 17
  side by side. Details: `awaero-app/PROGRESS.md`.
- **It now carries the same data as the web dashboard:** five appliances (light,
  fan, TV, desk lamp, AC), a Trials tab (same `/trials` endpoints, same
  `trials.csv`, capture countdown that survives tab switches, buzz at capture),
  and real trial accuracy with per-path bars on Stats.
- **Camera feed bug found and fixed in `state_server.py`:** every response carried
  `Cache-Control: no-store`, and React Native's image loader refuses a no-store
  image, so the phone's Live tab said "Camera feed offline" while the browser
  showed the frame. Frames now go out as `no-cache`; everything else stays
  `no-store`. This also fixes the old app. Selftest passes.
- **The running state server was stale.** It had been up since 2026-11-15 21:04,
  from before the 5-appliance change, so it was still reporting only light, fan
  and TV. Restarted from the current code on port 8000.
- **Verified:** simulator (all five tabs, camera frame, 5-appliance log) and one
  full trial end to end against an isolated copy of the server, so the real
  `trials.csv` was not written. tsc + expo lint clean. Installed and launched on
  the iPhone 17.
- **Open:** (1) the phone's connection to the Mac was not seen from the Mac side
  after install: a new app must be given Local Network permission on first
  launch, so check the phone; (2) no trial has been recorded from the phone on
  real hardware yet; (3) `awaero-app/` is untracked in this repo and has no git
  repo of its own, the owner has not said where it should live; (4) the web
  dashboard still shows the fan as "Auto" in gesture mode, which is stale now
  that gesture rows log the full appliance vector.

## What happened NIGHT (2026-11-15, web-dashboard UI session)
The dashboard got a full UI pass. No FYP Python changed in this session, only
`web-dashboard/` (spec `web-dashboard/PRD.md`, Section 11 lists every departure).
- **Web-first layout**: at >=900px a fixed left sidebar with icons (Home / Live /
  Stats / Trials, Sign out at the bottom) and a wide content area. Below 900px the
  topbar plus floating bottom tab bar, now a rubber (stretch then settle) segmented
  control. Resizing the window flips between them.
- **Live**: camera preview at the frame's native aspect, capped at 480px (was a
  cropped 4:3 box).
- **Stats**: 2 column grid; new Session timeline strip and Accuracy by response
  path bars (both animate on load, real data); the latency "Explain" modal is
  blur-only over the whole viewport; rubber Session/Today/All selector.
- **Trials**: button-cards match the div-cards; mobile overflow fixed (the capture
  delay row wraps).
- **Restyle to `DESIGN.md`** (hybrid): monochrome shadcn-style chrome, with profile
  and status colours kept so it stays readable as a monitor. Cards are borderless
  with a soft shadow (owner preference). System font, not Geist (a CDN font would
  break the no-cloud claim).
- **Decisions**: no new runtime dependencies. BoardUI, React Bits RubberSegment and
  a 21st.dev ChartLine were reviewed and rebuilt by hand (they need Tailwind,
  shadcn or `motion`). The Taste Skill is a landing-page tool and was not applied
  to the dashboard. Dev tooling (Emil Kowalski skills, taste-skill, BoardUI MCP)
  lives in gitignored `.agents/` and `.claude/`.
- **Open / unverified**: (1) per-path accuracy shows on both Stats and Trials, the
  owner has not chosen which tab owns it; (2) the final restyle was not reviewed
  again after the last tweak; (3) the Live tab with a fresh real camera frame was
  not re-checked this session (replay always shows "Camera feed offline").

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
**First: one full camera->VLM->LED live run with the 5 appliances** - the new policy
has only been driven directly, never through the camera pipeline yet. Then the fast
DC motor swap when it arrives. After that it is WRITING, not code:
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

## LCD note (RESOLVED 2026-11-16)
The LCD works at 0x27 on the SAME Arduino as the LEDs, via `arduino/room_node.ino`.
The old "random symbols / boxes" was an UNINITIALISED screen: the firmware hung in
setup() probing a missing LCD, so nothing drove it. It now probes 0x27 first and
skips all LCD calls when absent, so the LEDs never hang. The two-board `lcd_scroll.py`
util is superseded by the shared-port path (`LcdDisplay(ser=act.ser)`).
