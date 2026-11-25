// Клиент API тренажёра дебютов (сессия 13.6, `backend/app/api/trainer.py`): карточки курса,
// очередь повторения, проверка хода, сводка по курсам.
import { request } from "./api";
import type { Color } from "./types";

export type StartOut = { course_id: string; total: number; created: number };

export type TrainerCard = {
  course_id: string;
  /** Узел дерева курса — позиция перед ходом ученика. */
  node_id: number;
  fen: string;
  /** Ходы от начальной позиции до позиции карточки. */
  path_uci: string[];
  color: Color;
  box: number;
  /** true — повторение просроченной карточки, false — новая. */
  due: boolean;
};

export type Verdict = "main" | "alternative" | "wrong";

export type TrainerAnswer = {
  verdict: Verdict;
  /** Ходы курса в позиции (основной — первым). */
  expected: { uci: string; san: string }[];
  /** Потеря win% против лучшего хода; null — ход курса (движок не вызывался). */
  win_loss: number | null;
  box: number;
  next_review_at: string;
  /** Ближайший узел пути с идеями (текст — в `ideas_text` курса). */
  ideas_node_id: number | null;
};

export type CourseSummary = {
  course_id: string;
  name: string;
  total: number;
  due: number;
  new: number;
  /** Карточек в коробке ≥ 3. */
  learned: number;
};

/** Коробка, начиная с которой позиция считается выученной (`app/trainer/srs.py`). */
export const LEARNED_BOX = 3;
/** Последняя коробка Лейтнера (`app/puzzles/srs.py`). */
export const MAX_BOX = 5;

export const trainerApi = {
  start: (courseId: string) =>
    request<StartOut>(`/trainer/courses/${encodeURIComponent(courseId)}/start`, { method: "POST" }),
  next: (courseId?: string | null) =>
    request<TrainerCard | null>(`/trainer/next${courseId ? `?course_id=${encodeURIComponent(courseId)}` : ""}`),
  answer: (card: Pick<TrainerCard, "course_id" | "node_id">, body: { uci: string; hint_used: boolean }) =>
    request<TrainerAnswer>(
      `/trainer/courses/${encodeURIComponent(card.course_id)}/nodes/${card.node_id}/answer`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  summary: () => request<CourseSummary[]>("/trainer/summary"),
};
