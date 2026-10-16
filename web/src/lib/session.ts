// Сессия в браузере. Access-токен живёт только в памяти вкладки (XSS не достанет его из
// localStorage, а после перезагрузки он восстанавливается обновлением). Refresh-токен —
// в httpOnly-cookie с путём /api/v1/auth: JavaScript его не видит, браузер шлёт его только
// на эндпоинты auth. Обновление — одно на все вкладки (Web Locks): иначе две вкладки
// предъявят один и тот же токен, и сервер сочтёт второй повтор кражей.
import type { AuthOut, User } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Обновлять заранее, чтобы токен не истёк по дороге к API.
const EXPIRY_MARGIN_MS = 30_000;
const LOCK_NAME = "chess-review-auth-refresh";

let access: { token: string; expiresAt: number } | null = null;
let inflight: Promise<AuthOut | null> | null = null;

type SessionEvent = { type: "login"; user: User } | { type: "logout" };
const listeners = new Set<(event: SessionEvent) => void>();

// Вход и выход в одной вкладке видны в остальных.
const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("chess-review-auth");
channel?.addEventListener("message", (message: MessageEvent<SessionEvent["type"]>) => {
  if (message.data === "logout") {
    access = null;
    emit({ type: "logout" });
  } else if (message.data === "login") {
    void refreshSession().catch(() => undefined);
  }
});

function emit(event: SessionEvent) {
  listeners.forEach((listener) => listener(event));
}

export function onSessionChange(listener: (event: SessionEvent) => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Запомнить вход (ответ login / register / refresh). */
export function startSession(out: AuthOut, { broadcast = false } = {}) {
  access = { token: out.access_token, expiresAt: Date.now() + out.expires_in * 1000 };
  emit({ type: "login", user: out.user });
  if (broadcast) channel?.postMessage("login");
}

/** Сессия потеряна (выход, отозванный или истёкший refresh-токен). */
export function endSession({ broadcast = false } = {}) {
  access = null;
  emit({ type: "logout" });
  if (broadcast) channel?.postMessage("logout");
}

async function postRefresh(): Promise<Response> {
  return fetch(`${API_URL}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
}

async function doRefresh(): Promise<AuthOut | null> {
  let response = await postRefresh();
  if (response.status === 401) {
    const body = (await response.json().catch(() => null)) as { code?: string } | null;
    // Токен только что заменён в другой вкладке — cookie уже новый, повторить.
    if (body?.code === "refresh_rotated") {
      await new Promise((resolve) => setTimeout(resolve, 300));
      response = await postRefresh();
    }
  }
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      access = null;
      return null;
    }
    throw new Error(`refresh ${response.status}`);
  }
  const out = (await response.json()) as AuthOut;
  startSession(out);
  return out;
}

/**
 * Новый access-токен по refresh-cookie; null — сессии нет. Параллельные вызовы в вкладке
 * ждут один запрос, в разных вкладках — по очереди (Web Locks).
 */
export function refreshSession(): Promise<AuthOut | null> {
  if (inflight === null) {
    const run = (async (): Promise<AuthOut | null> =>
      typeof navigator !== "undefined" && navigator.locks
        ? await navigator.locks.request(LOCK_NAME, doRefresh)
        : await doRefresh())();
    inflight = run.finally(() => {
      inflight = null;
    });
  }
  return inflight;
}

/** Действующий access-токен (обновляется, если скоро истечёт); null — не вошли. */
export async function accessToken(): Promise<string | null> {
  if (access && access.expiresAt - Date.now() > EXPIRY_MARGIN_MS) return access.token;
  if (!access) return null;
  const out = await refreshSession();
  return out?.access_token ?? null;
}

export const hasSession = () => access !== null;
