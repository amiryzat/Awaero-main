// ponytail: this is a COSMETIC demo gate, not security. No server-side auth, no
// stored credentials, no hashing. A localStorage flag gives the "real product"
// feel the owner wants with zero security surface (PRD 7.0). try/catch so a
// private window (where storage throws) cannot break the app.
const KEY = "awaero_session";

export function isSignedIn(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function signIn(): void {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    // ignore: the gate just won't persist across reloads in private mode
  }
}

export function signOut(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
