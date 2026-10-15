// Классы ходов (SPEC §4.5): подписи и цвета для доски, списка ходов и графика.
// Значки — src/components/review/class-badge.tsx.
import type { MoveClass, MoveOut } from "./types";

export type ClassKey = MoveClass | "miss";

type ClassMeta = { label: string; plural: string; color: string };

export const CLASS_META: Record<ClassKey, ClassMeta> = {
  brilliant: { label: "Блестящий", plural: "Блестящие", color: "#1fb5a0" },
  great: { label: "Отличный", plural: "Отличные", color: "#6f98c2" },
  best: { label: "Лучший", plural: "Лучшие", color: "#7fb04a" },
  excellent: { label: "Превосходный", plural: "Превосходные", color: "#7fb04a" },
  good: { label: "Хороший", plural: "Хорошие", color: "#95b47a" },
  book: { label: "Теория", plural: "Теория", color: "#c99a72" },
  forced: { label: "Вынужденный", plural: "Вынужденные", color: "#9a948c" },
  inaccuracy: { label: "Неточность", plural: "Неточности", color: "#f1c232" },
  mistake: { label: "Ошибка", plural: "Ошибки", color: "#f59a4c" },
  miss: { label: "Упущение", plural: "Упущения", color: "#f2705e" },
  blunder: { label: "Зевок", plural: "Зевки", color: "#e8402e" },
};

/** Порядок строк в таблице классов. */
export const CLASS_ORDER: ClassKey[] = [
  "brilliant",
  "great",
  "book",
  "best",
  "excellent",
  "good",
  "inaccuracy",
  "mistake",
  "miss",
  "blunder",
];

/** Классы, которые в списке ходов отмечаются значком и цветом. */
export const NOTABLE: ClassKey[] = ["brilliant", "great", "inaccuracy", "mistake", "miss", "blunder"];

/** Класс для показа: флаг `miss` важнее класса хода, если ход не хуже неточности. */
export function displayClass(move: MoveOut): ClassKey {
  if (move.is_miss && !["mistake", "blunder"].includes(move.class)) return "miss";
  return move.class;
}

export const isError = (move: MoveOut) =>
  move.class === "inaccuracy" || move.class === "mistake" || move.class === "blunder";

/** Ход, для которого имеет смысл «Найти лучший ход». */
export const canRetry = (move: MoveOut) =>
  move.best_uci !== null && move.best_uci !== move.uci && (isError(move) || move.is_miss);

export const PHASE_LABELS = {
  opening: "Дебют",
  middlegame: "Миттельшпиль",
  endgame: "Эндшпиль",
} as const;

/** Значок фазы по её точности: как оценка хода (пороги — на глаз, для наглядности). */
export function phaseClass(accuracy: number): ClassKey {
  if (accuracy >= 90) return "best";
  if (accuracy >= 80) return "excellent";
  if (accuracy >= 70) return "good";
  if (accuracy >= 55) return "inaccuracy";
  if (accuracy >= 40) return "mistake";
  return "blunder";
}
