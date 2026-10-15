// Клиент API v1. Запросы идут из браузера напрямую на API (CORS_ORIGINS в .env).
import type {
  AnalysisOut,
  GameDetail,
  GameOut,
  GamePage,
  GameSource,
  ImportJob,
  MoveExplanation,
  Summary,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Текст ошибки FastAPI: `detail` — строка или список ошибок валидации. */
function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const field = first.loc?.at(-1);
    return field ? `${String(field)}: ${first.msg}` : (first.msg ?? "Некорректный запрос");
  }
  if (status >= 500) return "Сервер не ответил. Попробуйте ещё раз через минуту.";
  return `Ошибка запроса (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new ApiError(0, `Нет связи с API (${API_URL}). Проверьте, что backend запущен.`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body));
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

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
  analysisEventsUrl: (id: string) => `${API_URL}/api/v1/analyses/${id}/events`,

  explainMove: (moveId: number) => post<MoveExplanation>(`/moves/${moveId}/explain`),
  summary: (analysisId: string) => request<Summary>(`/analyses/${analysisId}/summary`),
};
