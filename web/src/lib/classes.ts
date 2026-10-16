// Классы ходов (SPEC §4.5): цвета и подписи для доски, списка ходов и графика.
// Значки — src/components/review/class-badge.tsx.
import type { Dict } from "./i18n";
import type { MoveClass, MoveOut } from "./types";

export type ClassKey = MoveClass | "miss";

/** Цвет класса; подписи — `classLabel` / `classPlural` (словарь `common.classes`). */
export const CLASS_COLORS: Record<ClassKey, string> = {
  brilliant: "#1fb5a0",
  great: "#6f98c2",
  best: "#7fb04a",
  excellent: "#7fb04a",
  good: "#95b47a",
  book: "#c99a72",
  forced: "#9a948c",
  inaccuracy: "#f1c232",
  mistake: "#f59a4c",
  miss: "#f2705e",
  blunder: "#e8402e",
};

export const classLabel = (t: Dict, key: ClassKey) => t.common.classes[key].label;
export const classPlural = (t: Dict, key: ClassKey) => t.common.classes[key].plural;

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

/** Подпись фазы — `t.common.phases[phase]`. */
/** Значок фазы по её точности: как оценка хода (пороги — на глаз, для наглядности). */
export function phaseClass(accuracy: number): ClassKey {
  if (accuracy >= 90) return "best";
  if (accuracy >= 80) return "excellent";
  if (accuracy >= 70) return "good";
  if (accuracy >= 55) return "inaccuracy";
  if (accuracy >= 40) return "mistake";
  return "blunder";
}
