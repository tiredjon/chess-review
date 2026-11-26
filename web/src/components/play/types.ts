// Контракт компонента партии с ботом (сессия 14, фундамент): им пользуются страница /play
// (14.2) и партия по курсу (14.3). Меняет только 14.2 — и только совместимо.
import type { ReactNode } from "react";
import type { Color } from "@/lib/types";

/**
 * «Книга» соперника: ход бота по заданной линии (курс). Получает ходы партии с начала (UCI),
 * возвращает ход соперника (UCI) или null — тогда ходит сам бот (Stockfish на своём рейтинге).
 * Вызывается перед каждым ходом бота.
 */
export type OpponentBook = (historyUci: readonly string[]) => string | null;

export type GameEndReason =
  | "checkmate"
  | "stalemate"
  | "repetition"
  | "fifty_moves"
  | "insufficient_material"
  | "resign";

export type GameResult = {
  /** Результат в нотации PGN. */
  result: "1-0" | "0-1" | "1/2-1/2";
  reason: GameEndReason;
  /** Победитель; null — ничья. */
  winner: Color | null;
  historyUci: string[];
  /** PGN партии с заголовками (White / Black / Result / …). */
  pgn: string;
};

export type BotGameProps = {
  /** Рейтинг бота (один из BOT_ELOS). */
  elo: number;
  /** Цвет человека. */
  color: Color;
  book?: OpponentBook;
  /** После каждого хода человека: ходы партии с начала, последний — его ход. */
  onPlayerMove?: (historyUci: readonly string[]) => void;
  /** Ходы партии изменились — любой ход, «взять назад», восстановление после перезагрузки. */
  onHistoryChange?: (historyUci: readonly string[]) => void;
  /** Партия кончилась (мат, пат, ничья по правилам, сдача). */
  onFinished?: (result: GameResult) => void;
  /** «Новая партия» / «Другой бот» — страница сама решает, что показать. */
  onNewGame?: () => void;
  /** «Другой бот» в итоге партии (кнопка видна, только если передан). */
  onChangeBot?: () => void;
  /**
   * Ключ партии для sessionStorage: если задан, ходы сохраняются и восстанавливаются после
   * случайной перезагрузки (та же партия — тот же ключ, новая партия — новый).
   */
  storageKey?: string;
  /** Доп. блок в боковой панели (курс: где мы на линии, подсказки). */
  aside?: ReactNode;
  /** Заголовки PGN сверх стандартных (например, Event: название курса). */
  pgnHeaders?: Record<string, string>;
};
