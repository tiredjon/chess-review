// Клиент API «Моего репертуара» (сессия 13.3 / 13.4): дебюты и дерево из партий пользователя,
// создание курса по линии. Общий транспорт (токен, обновление сессии, ошибки по коду) — из api.ts.
import type { OpeningNode } from "@/components/openings/types";
import { request } from "./api";
import type { Color } from "./types";

/** Узел репертуара: поля узла дерева + партии через него (результат — глазами пользователя). */
export type RepertoireNode = OpeningNode & {
  games: number;
  wins: number;
  draws: number;
  losses: number;
  last_played_at: string | null;
};

export type RepertoireTree = {
  color: Color;
  /** Партий цвета с известным результатом; у пустого репертуара `nodes` пуст. */
  total_games: number;
  nodes: RepertoireNode[];
};

export type RepertoireOpening = {
  name: string;
  eco: string | null;
  games: number;
  wins: number;
  draws: number;
  losses: number;
  /** Самый частый путь из партий до позиции с этим названием. */
  line_uci: string[];
  /** Сколько первых полуходов партий (медиана) ещё в теории. */
  book_exit_ply: number;
  last_played_at: string | null;
};

/** Ответ `POST /courses` (контракт SPEC 13.4): нужен только id для перехода на страницу курса. */
export type CourseRef = { id: string | number };

export const repertoireApi = {
  openings: (color: Color) => request<RepertoireOpening[]>(`/repertoire/openings?color=${color}`),
  tree: (color: Color) => request<RepertoireTree>(`/repertoire/tree?color=${color}`),
  /** Курс по линии из репертуара; идемпотентно по ключу — повтор вернёт тот же курс. */
  createCourse: (body: { line_uci: string[]; color: Color; name?: string }) =>
    request<CourseRef>("/courses", { method: "POST", body: JSON.stringify({ ...body, source: "repertoire" }) }),
};
