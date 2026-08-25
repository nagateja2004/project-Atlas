/**
 * Session token storage.
 *
 * Deliberately has no imports. api.ts needs the token to sign requests and the
 * login flow needs to store it; putting the storage here rather than in api.ts
 * keeps that from becoming an import cycle.
 *
 * localStorage rather than a cookie because the token is sent as an
 * Authorization header, so there is no CSRF surface to protect with SameSite,
 * and the dashboard is a client component that reads it directly. Every access
 * is wrapped: localStorage throws outright in a private window with site data
 * blocked, and during a server render it does not exist at all.
 */

const KEY = "atlas.access_token";

type Listener = (token: string | null) => void;
const listeners = new Set<Listener>();

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  if (typeof window !== "undefined") {
    try {
      if (token) window.localStorage.setItem(KEY, token);
      else window.localStorage.removeItem(KEY);
    } catch {
      // A viewer with site data blocked can still use the app for this tab;
      // they will just have to sign in again after a reload.
    }
  }
  for (const listener of listeners) listener(token);
}

export function clearToken(): void {
  setToken(null);
}

/** Notifies on sign-in and sign-out, including the forced sign-out on a 401. */
export function onTokenChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
