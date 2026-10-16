// Клиент API v1. Запросы идут из браузера напрямую на API (CORS_ORIGINS в .env) с
// access-токеном в заголовке (lib/session.ts). Ошибки API приходят с кодом (`code`,
// `params`) — текст берётся из словаря текущего языка.
import { currentDict, currentLang, type Dict } from "./i18n";
import type { ErrorParams } from "./i18n/ru/errors";
import { accessToken, API_URL, endSession, refreshSession, startSession } from "./session";
import type {
  AnalysisOut,
  AuthOut,
  GameDetail,
  GameOut,
  GamePage,
  GameSource,
  ImportJob,
  MoveExplanation,
  ProfileUpdate,
  PuzzleAttempt,
  PuzzleNext,
  Stats,
  StreamToken,
  Summary,
  TimeClass,
  User,
} from "./types";

export { API_URL };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string | null = null,
    readonly params: ErrorParams = {},
  ) {
    super(message);
  }
}

type ErrorBody = { detail?: unknown; code?: string; params?: ErrorParams } | null;

/** Текст ошибки по коду; `fallback` — если кода нет в словаре. */
export function codeText(t: Dict, code: string | null | undefined, params: ErrorParams = {}, fallback?: string | null) {
  const text = code ? t.errors.codes[code]?.(params) : undefined;
  return text ?? fallback ?? t.errors.generic;
}

function errorFromResponse(status: number, body: ErrorBody): ApiError {
  const t = currentDict();
  let code = body?.code ?? null;
  const params: ErrorParams = { ...body?.params, status };
  const detail = body?.detail;
  if (code === "validation_error" && Array.isArray(detail) && detail.length > 0) {
    const field = (detail[0] as { loc?: unknown[] }).loc?.at(-1);
    if (field !== undefined) params.field = String(field);
    if (field === "email") code = "invalid_email";
  }
  const fallback = status >= 500 ? t.errors.server : t.errors.request(status);
  return new ApiError(status, codeText(t, code, params, fallback), code, params);
}

async function send(path: string, init: RequestInit | undefined, token: string | null): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept-Language", currentLang());
  try {
    return await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, currentDict().errors.network(API_URL));
  }
}

const AUTH_RETRY_CODES = new Set(["token_expired", "token_invalid", "not_authenticated"]);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await send(path, init, await accessToken());
  let body = (await response.json().catch(() => null)) as ErrorBody;
  if (response.status === 401 && AUTH_RETRY_CODES.has(body?.code ?? "")) {
    // Токен истёк или API перезапустился с другим ключом: обновить и повторить один раз.
    const session = await refreshSession().catch(() => null);
    if (session === null) {
      endSession();
      throw errorFromResponse(response.status, body);
    }
    response = await send(path, init, session.access_token);
    body = (await response.json().catch(() => null)) as ErrorBody;
  }
  if (!response.ok) throw errorFromResponse(response.status, body);
  return body as T;
}

const post = <T>(path: string, body?: unknown, method = "POST") =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

/** Запросы auth: с cookie (refresh-токен), без access-токена. */
async function authRequest(path: string, body?: unknown): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/auth${path}`, {
      method: "POST",
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, currentDict().errors.network(API_URL));
  }
  if (!response.ok) {
    throw errorFromResponse(response.status, (await response.json().catch(() => null)) as ErrorBody);
  }
  return response;
}

async function authenticate(path: string, body: unknown): Promise<AuthOut> {
  const out = (await (await authRequest(path, body)).json()) as AuthOut;
  startSession(out, { broadcast: true });
  return out;
}

export const auth = {
  login: (email: string, password: string) => authenticate("/login", { email, password }),
  register: (email: string, password: string, lang: string) =>
    authenticate("/register", { email, password, lang }),
  logout: async () => {
    try {
      await authRequest("/logout");
    } finally {
      endSession({ broadcast: true });
    }
  },
  me: () => request<User>("/auth/me"),
  updateMe: (update: ProfileUpdate) => post<User>("/auth/me", update, "PATCH"),
};

export const api = {
  importPgn: (pgn: string) => post<GameOut[]>("/games/pgn", { pgn }),
  importLichess: (username: string, max: number) =>
    post<ImportJob>("/imports/lichess", { username, max }),
  importChesscom: (username: string, months: number) =>
    post<ImportJob>("/imports/chesscom", { username, months }),
  importJob: (jobId: string) => request<ImportJob>(`/imports/${jobId}`),

  games: (params: { cursor?: string | null; source?: GameSource | null; limit?: number }) => {
    const query = new URLSearchParams();
    if (params.cursor) query.set("cursor", params.cursor);
    if (params.source) query.set("source", params.source);
    if (params.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return request<GamePage>(`/games${qs ? `?${qs}` : ""}`);
  },
  game: (id: string) => request<GameDetail>(`/games/${id}`),
  analyze: (id: string) => post<AnalysisOut>(`/games/${id}/analyze`),
  analysis: (id: string) => request<AnalysisOut>(`/analyses/${id}`),
  /** URL SSE-потока: EventSource не умеет заголовки, поэтому — с коротким токеном в query. */
  analysisEventsUrl: async (id: string) => {
    const { token } = await post<StreamToken>(`/analyses/${id}/events/token`);
    return `${API_URL}/api/v1/analyses/${id}/events?token=${encodeURIComponent(token)}`;
  },

  // Язык объяснений не передаётся: сервер берёт язык пользователя (users.lang).
  explainMove: (moveId: number) => post<MoveExplanation>(`/moves/${moveId}/explain`),
  summary: (analysisId: string) => request<Summary>(`/analyses/${analysisId}/summary`),

  stats: (params: { source?: GameSource | null; timeClass?: TimeClass | null }) => {
    const query = new URLSearchParams();
    if (params.source) query.set("source", params.source);
    if (params.timeClass) query.set("time_class", params.timeClass);
    const qs = query.toString();
    return request<Stats>(`/stats/me${qs ? `?${qs}` : ""}`);
  },

  nextPuzzle: (exclude: string[] = []) => {
    const query = new URLSearchParams();
    exclude.forEach((id) => query.append("exclude", id));
    const qs = query.toString();
    return request<PuzzleNext>(`/puzzles/next${qs ? `?${qs}` : ""}`);
  },
  attemptPuzzle: (id: string, body: { moves_uci: string[]; hint_used?: boolean; gave_up?: boolean }) =>
    post<PuzzleAttempt>(`/puzzles/${id}/attempt`, body),
};
