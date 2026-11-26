// Контракт компонента партии с ботом (сессия 14, фундамент): им пользуются страница /play
// (14.2), партия по курсу (14.3) и тренажёр эндшпиля (16.3). Меняется только совместимо.
import type { ReactNode } from "react";
import type { Arrow } from "react-chessboard";
import type { Color } from "@/lib/types";

/**
 * «Книга» соперника: ход бота по заданной линии (курс) или по таблицам (эндшпиль). Получает ходы
 * партии с начальной позиции (UCI), возвращает ход соперника (UCI) или null — тогда ходит сам бот
 * (Stockfish на своём рейтинге). Может вернуть Promise (запрос к таблицам): пока он не выполнен,
 * бот «думает»; ошибка Promise — тоже null. Вызывается перед каждым ходом бота.
 */
export type OpponentBook = (historyUci: readonly string[]) => string | null | Promise<string | null>;

/**
 * Итог партии, который решает страница (тренажёр эндшпиля: цель выполнена или провалена раньше
 * конца по правилам). Пока задан — ходов нет, бот не думает; вместо кнопок партии — `actions`,
 * собственное окно итога BotGame не показывается.
 */
export type BotGameVerdict = {
  /** Цвет плашки: успех — зелёная, провал — красная, нейтрально — серая. */
  tone: "success" | "failure" | "neutral";
  text: string;
  actions?: ReactNode;
};

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
  /**
   * Начальная позиция (FEN) вместо стартовой — тренажёр эндшпиля (сессия 16.3). Партия идёт
   * с неё: очередь хода и номер хода — из FEN, в PGN — заголовки SetUp / FEN, ходы книге
   * и в `onPlayerMove` / `onHistoryChange` — от этой позиции.
   */
  startFen?: string;
  /** Итог от страницы (см. BotGameVerdict); null / не задан — партия идёт по правилам. */
  verdict?: BotGameVerdict | null;
  /** Стрелки на доске по показанной позиции (ключ — число сыгранных полуходов). */
  arrows?: Readonly<Record<number, Arrow[]>>;
  /**
   * Показать позицию после `ply` полуходов (например, момент, где упущен выигрыш). Новый `key` —
   * новый переход, даже к тому же ходу.
   */
  focus?: { ply: number; key: number } | null;
  /** Прятать «Разобрать партию» в итоге (партия не из стартовой позиции и т. п.). */
  hideAnalyze?: boolean;
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
