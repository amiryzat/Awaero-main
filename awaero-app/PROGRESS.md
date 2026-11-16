# Progress: awaero-app

Read with `CONTEXT.md`. Last updated: 2026-11-16.
Newest cross-project state: `../docs/RESUME.md`.

## Status
Built and installed on the iPhone 17 as **Awaero**, next to the old
`app-monitor`. Everything on screen comes from `../state_server.py`.

## What changed versus app-monitor (2026-11-16)
The app was brought up to the data the web dashboard already shows.

- **Five appliances** (light, fan, TV, desk lamp, AC) on Home, Live, Stats and
  Controls. The old app only knew three.
- **Trials tab** (new, 4th of 5 tabs): the RO3 recorder. Tap what the system
  SHOULD read, get into position, and the server scores its own decision when
  the countdown hits zero. Same `/trials` endpoints and the same `trials.csv`
  as the web dashboard, so a trial recorded on either shows on both.
- **Stats**: Trial accuracy is now the real figure from `trials.csv`, with a
  bar per response path (4 postures, 3 gestures). It used to be hard-coded to
  "Not yet measured".
- **Live**: a note when more than one person is in frame (the system is scoped
  to one occupant).
- **Fan in gesture mode**: shows the logged value. The fused `live_system.py`
  logs the full appliance vector on gesture rows, so the old "unknown in ACTIVE"
  rule no longer applies.

## Structure
```
src/app/_layout.tsx            Root stack (tabs + Settings modal)
src/app/(tabs)/_layout.tsx     Five tabs + the floating CaptureBanner
src/app/(tabs)/index.tsx       Home: profile, 5 appliance tiles, recent decisions
src/app/(tabs)/live.tsx        Live: camera frame + decision pipeline
src/app/(tabs)/stats.tsx       Stats: the RO3 report
src/app/(tabs)/trials.tsx      Trials: the RO3 recorder
src/app/(tabs)/controls.tsx    Controls: read-only mirror (override not wired)
src/app/settings.tsx           Connection status, Wireless check, manual address
src/components/CaptureBanner.tsx  Trial countdown / result, shown on every tab
src/components/PillTabBar.tsx  Floating glass tab bar
src/lib/state.ts               The server's JSON shapes + labels
src/lib/useSystem.ts           The one poller + Mac auto-discovery
src/lib/trials.ts              Trial countdown store (survives tab switches)
```

## Talking to the Mac
`src/lib/useSystem.ts` finds the server by itself on port 8000. It tries, in
order: an address typed in Settings, the Mac's network IP learned from
`/health`, the Bonjour name learned from `/health`, then `Amirv-Mac.local`.
After 3 failed polls it searches again. Plain HTTP on the local network is
allowed by the app (`NSAllowsLocalNetworking`); nothing leaves the LAN.

On the Mac: `source venv/bin/activate && python state_server.py`.
Settings in the app has a "Wireless check" that says whether the USB cable is
carrying the link. On a network that isolates clients the cable is required
(see `../docs/RESUME.md`); for the viva use one network we control.

## Safety rules built into Trials
- Recording is blocked while the system is offline and on replay data. A trial
  is only evidence when it scores the live system.
- "Undo last" asks for confirmation: it deletes a row of the RO3 dataset.
- A countdown is dropped if the app goes to the background (iOS freezes timers,
  so it would fire late and score the wrong moment).
- The phone buzzes at the capture instant, since it is set down while you pose.

## Build and run
```bash
npm run ios:sim     # Release build on the Test iPhone 17 simulator, no Metro
npm run ios:phone   # Release build, installs on the iPhone 17
xcrun devicectl device process launch --device 00008150-00021CC836F3C01C com.amiryzat.awaero
npx tsc --noEmit && npx expo lint    # before calling anything done
```
Both scripts build Release on purpose: the JS is compiled into the app, and
never mixing Debug and Release avoids the prebuilt-pods flavor trap that hit
app-monitor. `npm install` needs `--legacy-peer-deps`.

Navigate the simulator without tapping: `xcrun simctl openurl <udid> awaero:///trials`
(also `live`, `stats`, `controls`).

## How it was verified (2026-11-16)
- Simulator: all five tabs rendered against a 5-appliance log, camera frame shown.
- One full trial driven end to end (arm, countdown, switch to Live, capture,
  count 11 to 12, undo) against an isolated copy of the server, so the real
  `trials.csv` was never written.
- Not yet done on real hardware: a trial recorded from the phone while
  `live_system.py` is running.

## Not built
- Controls is read-only. Manual override (`override.json`) is not wired in
  `live_system.py` or the server.
- No session runner or CSV export for trials (PRD 7.4 extras).
