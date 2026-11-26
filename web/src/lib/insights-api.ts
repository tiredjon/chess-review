// Клиент «Слабых мест» (сессия 16.1): `GET /insights/me` — зеркало `app/api/schemas_insights.py`.
// Общий транспорт (токен, обновление сессии, ошибки по коду) — из api.ts.
import { request } from "./api";
import type { ClassKey } from "./classes";
import type { Color, GameSource, Phase, TimeClass } from "./types";

export type FindingKind = "motif" | "phase" | "time" | "opening" | "conversion";
export type Severity = "high" | "medium" | "low";
export type TrainKind = "puzzles" | "endgames" | "course" | "play";

/** Показатель пользователя (`value`) против его же базы (`baseline`), в процентах;
 *  `count` из `total` — на чём вывод держится. Смысл чисел — по виду вывода (см. словарь). */
export type FindingStats = { value: number; baseline: number; count: number; total: number };

export type FindingExample = {
  game_id: string;
  ply: number;
  fen_before: string;
  san: string;
  best_san: string | null;
  /** Класс для показа: `miss`, если ход — упущение, но не mistake / blunder. */
  move_class: ClassKey;
  opponent: string;
  played_at: string | null;
};

export type TrainQuery = { theme: string | null; phase: Phase | null; eco: string | null };

export type Train = { kind: TrainKind; query: TrainQuery; available: number };

export type Finding = {
  id: string;
  kind: FindingKind;
  /** motif — тип мотива; phase — фаза; time — `trouble` | `hasty`; opening — `цвет:семейство`;
   *  conversion — `winning`. */
  key: string;
  severity: Severity;
  score: number;
  stats: FindingStats;
  examples: FindingExample[];
  train: Train | null;
};

export type Insights = {
  filters: { source: GameSource | null; time_class: TimeClass | null };
  analyzed_games: number;
  min_games: number;
  findings: Finding[];
};

/** Ключ вывода о дебюте: цвет и семейство («Italian Game»). */
export function openingKey(key: string): { color: Color; family: string } {
  const at = key.indexOf(":");
  return { color: key.slice(0, at) === "black" ? "black" : "white", family: key.slice(at + 1) };
}

export const insightsApi = {
  me: (params: { source?: GameSource | null; timeClass?: TimeClass | null } = {}) => {
    const query = new URLSearchParams();
    if (params.source) query.set("source", params.source);
    if (params.timeClass) query.set("time_class", params.timeClass);
    const qs = query.toString();
    return request<Insights>(`/insights/me${qs ? `?${qs}` : ""}`);
  },
};
