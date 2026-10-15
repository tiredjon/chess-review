// Классы ходов (SPEC §4.5): подписи, цвета и значки для доски, списка ходов и графика.
import type { MoveClass, MoveOut } from "./types";

export type ClassKey = MoveClass | "miss";

type ClassMeta = { label: string; color: string; glyph: string };

export const CLASS_META: Record<ClassKey, ClassMeta> = {
  brilliant: { label: "Блестящий", color: "#1baca6", glyph: "!!" },
  great: { label: "Отличный", color: "#5b8bb4", glyph: "!" },
  best: { label: "Лучший", color: "#7fa650", glyph: "★" },
  excellent: { label: "Превосходный", color: "#96bc4b", glyph: "✓" },
  good: { label: "Хороший", color: "#8fa98a", glyph: "✓" },
  book: { label: "Теория", color: "#a88865", glyph: "≡" },
  forced: { label: "Вынужденный", color: "#8e9ba5", glyph: "→" },
  inaccuracy: { label: "Неточность", color: "#e6b32e", glyph: "?!" },
  mistake: { label: "Ошибка", color: "#e5862a", glyph: "?" },
  miss: { label: "Упущение", color: "#e2604b", glyph: "✕" },
  blunder: { label: "Зевок", color: "#c93430", glyph: "??" },
};

/** Порядок в счётчиках карточки игрока. */
export const CLASS_ORDER: ClassKey[] = [
  "brilliant",
  "great",
  "best",
  "excellent",
  "good",
  "book",
  "inaccuracy",
  "mistake",
  "miss",
  "blunder",
];

/** Класс для показа: флаг `miss` важнее класса хода, если ход не хуже неточности. */
export function displayClass(move: MoveOut): ClassKey {
  if (move.is_miss && !["mistake", "blunder"].includes(move.class)) return "miss";
  return move.class;
}

export const isError = (move: MoveOut) =>
  move.class === "inaccuracy" || move.class === "mistake" || move.class === "blunder";

/** Ходы, у которых есть содержательное объяснение (`explain/facts.is_explained`). */
export const isExplained = (move: MoveOut) =>
  isError(move) || move.is_miss || move.class === "brilliant" || move.class === "great";

/** Ход, для которого имеет смысл «Повтори лучший ход». */
export const canRetry = (move: MoveOut) =>
  move.best_uci !== null && move.best_uci !== move.uci && (isError(move) || move.is_miss);

export const MOTIF_LABELS: Record<string, string> = {
  hanging_piece: "незащищённая фигура",
  fork: "вилка",
  pin: "связка",
  skewer: "линейный удар",
  discovered_attack: "вскрытое нападение",
  discovered_check: "вскрытый шах",
  double_check: "двойной шах",
  mate_in_n: "мат",
  mate_threat: "угроза мата",
  back_rank: "слабость последней горизонтали",
  trapped_piece: "ловля фигуры",
  removing_defender: "уничтожение защитника",
  overload: "перегрузка",
  promotion: "превращение пешки",
  promotion_threat: "угроза превращения",
};

export const PHASE_LABELS = {
  opening: "Дебют",
  middlegame: "Миттельшпиль",
  endgame: "Эндшпиль",
} as const;

/** Цвет бейджа точности. */
export function accuracyTone(value: number): string {
  if (value >= 90) return "#5f9f3a";
  if (value >= 80) return "#8aa63c";
  if (value >= 70) return "#c99a1d";
  if (value >= 55) return "#d0742a";
  return "#c03a2f";
}
