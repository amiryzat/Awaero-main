import { useSyncExternalStore } from "react";
import { AppState, Vibration } from "react-native";
import type { TrialRow } from "@/lib/state";
import { sendJson } from "@/lib/useSystem";

// The RO3 trial recorder, phone side. You declare the GROUND TRUTH (what the
// system SHOULD read); state_server.py snapshots its own live decision, scores
// it and appends trials.csv. This app only sends the label.
//
// The capture countdown lives in this module store, not in the Trials screen,
// so it survives a tab switch: arm it on Trials, move to Live, and the count and
// the result are still on screen (CaptureBanner sits in the tab layout).

export const DELAYS = [3, 10, 15, 20] as const;

export type Flash = { row: TrialRow } | { error: string };
type Snap = {
  delay: number;
  pending: { expected: string; left: number } | null;
  flash: Flash | null;
  version: number; // bumps whenever trials.csv changed, so screens re-fetch
};

let snap: Snap = { delay: 10, pending: null, flash: null, version: 0 };
const subs = new Set<() => void>();
const set = (p: Partial<Snap>) => {
  snap = { ...snap, ...p };
  subs.forEach((f) => f());
};

let timer: ReturnType<typeof setInterval> | undefined;
let flashTimer: ReturnType<typeof setTimeout> | undefined;

async function fire(expected: string) {
  // The phone is set down while you pose, so a buzz marks the capture instant.
  Vibration.vibrate();
  let flash: Flash;
  try {
    flash = { row: await sendJson<TrialRow>("POST", "/trials", { expected }) };
  } catch {
    flash = { error: "Trial NOT recorded. The Mac did not answer." };
  }
  set({ flash, version: snap.version + 1 });
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => set({ flash: null }), 6000);
}

export function arm(expected: string) {
  if (snap.pending) return;
  clearTimeout(flashTimer);
  // A deadline, not a decrementing counter: a slow tick cannot stretch the delay.
  const fireAt = Date.now() + snap.delay * 1000;
  set({ flash: null, pending: { expected, left: snap.delay } });
  timer = setInterval(() => {
    const left = Math.ceil((fireAt - Date.now()) / 1000);
    if (left <= 0) {
      cancel();
      void fire(expected);
    } else if (left !== snap.pending?.left) set({ pending: { expected, left } });
  }, 250);
}

export function cancel() {
  clearInterval(timer);
  set({ pending: null });
}

export const setDelay = (delay: number) => set({ delay });

export async function undoLast() {
  await sendJson("DELETE", "/trials/last");
  set({ version: snap.version + 1 });
}

// iOS freezes timers in the background, so a countdown left running would fire
// late, on return, when you are no longer in position. That would write a wrong
// row into the evidence file. Drop it instead.
AppState.addEventListener("change", (s) => {
  if (s === "background" && snap.pending) cancel();
});

const subscribe = (cb: () => void) => {
  subs.add(cb);
  return () => {
    subs.delete(cb);
  };
};

export const useTrials = () => useSyncExternalStore(subscribe, () => snap);
