import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";
import { AppState } from "react-native";
import type { Decision, SystemState } from "@/lib/state";

// One poller for the whole app, talking to state_server.py on the Mac.
//
// Addressing is automatic. The Mac's /health reports its own WiFi address and
// its Bonjour name; both are remembered, and every reconnect races every
// address we know, highest priority first. That covers three things that each
// broke the link once: the Mac's DHCP lease moving (192.168.0.31 -> .35), the
// owner having to type an address at all, and the phone being plugged in by
// USB, which makes "Amirv-Mac.local" resolve over the cable so that unplugging
// looks like the system died. The WiFi address is tried BEFORE the Bonjour
// name for exactly that reason: the WiFi path is the one the demo depends on.

const TYPED_KEY = "mac_host";       // the owner's override, from Settings
const LEARNED_KEY = "mac_learned";  // { lan_ip, local_name } reported by /health
const PORT = 8000;
// Only used before the app has ever reached the Mac. `scutil --get LocalHostName`.
const FALLBACK_HOST = "Amirv-Mac.local";
// A poll fails on any dropped packet, so do not throw the address away at once.
const FAILS_BEFORE_RESEARCH = 3;

export type Status = "loading" | "searching" | "ok" | "unreachable";
export type Health = {
  ok: boolean;
  source: "live" | "replay";
  rows: number;
  log_path: string;
  lan_ip: string;
  local_name: string | null;
};
type Learned = { lan_ip?: string; local_name?: string };
type Snap = {
  host: string; // the address in use; "" while searching
  typed: string;
  learned: Learned;
  status: Status;
  state: SystemState | null;
  history: Decision[];
};

let snap: Snap = { host: "", typed: "", learned: {}, status: "loading", state: null, history: [] };
const subs = new Set<() => void>();
const set = (p: Partial<Snap>) => {
  snap = { ...snap, ...p };
  subs.forEach((f) => f());
};

export const baseUrl = (host = snap.host) => `http://${host}:${PORT}`;

// Every address worth trying, in priority order.
export const candidateHosts = (s: Snap = snap): string[] =>
  [...new Set([s.typed, s.learned.lan_ip, s.learned.local_name, FALLBACK_HOST])].filter(
    (h): h is string => !!h,
  );

export async function getJson<T>(path: string, host?: string, init?: RequestInit): Promise<T> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 2500);
  try {
    const r = await fetch(baseUrl(host) + path, { ...init, signal: ctl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

// POST / DELETE to the address in use. Throws on a non-2xx or a timeout.
export const sendJson = <T>(method: "POST" | "DELETE", path: string, body?: unknown) =>
  getJson<T>(path, undefined, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

async function learn(h: Health) {
  const next: Learned = { lan_ip: h.lan_ip || undefined, local_name: h.local_name || undefined };
  if (next.lan_ip === snap.learned.lan_ip && next.local_name === snap.learned.local_name) return;
  set({ learned: next });
  await AsyncStorage.setItem(LEARNED_KEY, JSON.stringify(next)).catch(() => {});
}

// Ask every candidate at once and take the highest-priority answer.
// allSettled keeps the input order, so "first fulfilled" is "best that replied".
async function probe() {
  const list = candidateHosts();
  if (list.length === 0) return null;
  const got = await Promise.allSettled(
    list.map(async (host) => {
      const health = await getJson<Health>("/health", host);
      if (!health?.ok) throw new Error("not a state server");
      return { host, health };
    }),
  );
  for (const r of got) if (r.status === "fulfilled") return r.value;
  return null;
}

let busy = false;
let fails = 0;

async function tick() {
  if (busy) return;
  busy = true;
  try {
    if (!snap.host) {
      const found = await probe();
      if (!found) {
        set({ status: "unreachable", state: null, history: [] });
        return;
      }
      learn(found.health);
      set({ host: found.host });
    }
    const host = snap.host;
    try {
      const [state, history] = await Promise.all([
        getJson<SystemState>("/state", host),
        getJson<Decision[]>("/history?limit=20", host),
      ]);
      if (host !== snap.host) return; // the address changed under us
      fails = 0;
      set({ status: "ok", state, history });
    } catch {
      if (host !== snap.host) return;
      if (++fails >= FAILS_BEFORE_RESEARCH) {
        fails = 0;
        // Drop the address and search again on the next tick. This is what
        // recovers the app by itself when the USB cable is pulled and the same
        // Mac is still there on the WiFi.
        set({ host: "", status: "searching", state: null, history: [] });
      } else {
        set({ status: "unreachable" });
      }
    }
  } finally {
    busy = false;
  }
}

export async function setHost(input: string) {
  // Accept "192.168.0.35", "http://192.168.0.35:8000/" and similar. Empty means
  // fully automatic.
  const typed = input.trim().replace(/^https?:\/\//, "").replace(/[:/].*$/, "");
  await AsyncStorage.setItem(TYPED_KEY, typed).catch(() => {});
  fails = 0;
  set({ typed, host: "", status: "searching", state: null, history: [] });
  tick();
}

export function reconnect() {
  fails = 0;
  set({ host: "", status: "searching" });
  tick();
}

// Is the Mac reachable at its own WiFi address, whatever address we happen to be
// using? If this fails while the app is connected, the link is going over the
// USB cable and unplugging will kill it. That question has to be answerable
// before a demo, not during one.
export async function checkWifiPath(): Promise<{ ip: string | null; ok: boolean }> {
  const ip = snap.learned.lan_ip ?? null;
  if (!ip) return { ip: null, ok: false };
  try {
    const h = await getJson<Health>("/health", ip);
    return { ip, ok: !!h?.ok };
  } catch {
    return { ip, ok: false };
  }
}

// 2 s in the foreground, 30 s otherwise (iOS suspends timers in the background anyway).
let timer: ReturnType<typeof setInterval>;
const schedule = () => {
  clearInterval(timer);
  timer = setInterval(tick, AppState.currentState === "active" ? 2000 : 30_000);
};

let started = false;
function start() {
  if (started) return;
  started = true;
  Promise.all([
    AsyncStorage.getItem(TYPED_KEY).catch(() => null),
    AsyncStorage.getItem(LEARNED_KEY).catch(() => null),
  ]).then(([typed, learnedRaw]) => {
    let learned: Learned = {};
    try {
      learned = learnedRaw ? (JSON.parse(learnedRaw) as Learned) : {};
    } catch {
      learned = {};
    }
    set({ typed: typed ?? "", learned, status: "searching" });
    tick();
  });
  AppState.addEventListener("change", (s) => {
    schedule();
    if (s === "active") tick();
  });
  schedule();
}

const subscribe = (cb: () => void) => {
  start();
  subs.add(cb);
  return () => {
    subs.delete(cb);
  };
};

// Why there is no trustworthy current decision, or null when there is one.
function problemOf(s: Snap): string | null {
  if (s.status === "loading" || s.status === "searching") return "Looking for the Mac";
  if (s.status === "unreachable") return "Cannot reach the Mac";
  if (!s.state?.online || !s.state.current) return "System not running";
  return null;
}

export function useSystem() {
  const s = useSyncExternalStore(subscribe, () => snap);
  const problem = problemOf(s);
  // Never present a stale decision as current: any problem hides it.
  return {
    ...s,
    problem,
    candidates: candidateHosts(s),
    current: problem ? null : (s.state?.current ?? null),
  };
}
