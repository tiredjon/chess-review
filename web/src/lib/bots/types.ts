// Контракт ботов (сессия 14): Stockfish в браузере, ослабленный до заданного рейтинга.
// Реализация — `lib/bots/` (14.1); игра — `components/play/` (14.2); курс — 14.3.
// Все файлы, кроме этого, меняет только их подсессия; этот — общий фундамент.

/** Рейтинги ботов: 400, 500, … 2800 (шаг 100) — все на выбор. */
export const BOT_MIN_ELO = 400;
export const BOT_MAX_ELO = 2800;
export const BOT_ELO_STEP = 100;
export const BOT_ELOS: readonly number[] = Array.from(
  { length: (BOT_MAX_ELO - BOT_MIN_ELO) / BOT_ELO_STEP + 1 },
  (_, i) => BOT_MIN_ELO + i * BOT_ELO_STEP,
);

export type BotMoveRequest = {
  /** Позиция, в которой ход за ботом. */
  fen: string;
  /** Ходы партии с начальной позиции (UCI) — для правила трёх повторений и «книги». */
  historyUci: readonly string[];
  signal?: AbortSignal;
  /** Часы бота в партии с контролем времени: раздумье и поиск укладываются в остаток. */
  clock?: { remainingMs: number; incrementMs: number };
};

export type BotMove = {
  uci: string;
  /** Оценка позиции после хода с точки зрения бота (сантипешки; мат — ±100000), если есть. */
  cp?: number;
};

export interface Bot {
  readonly elo: number;
  /** Ход бота. Включает «время на раздумье», похожее на человеческое (не мгновенно). */
  move(request: BotMoveRequest): Promise<BotMove>;
  /** Новая партия: сбросить состояние движка. */
  newGame(): Promise<void>;
  /** Освободить воркер. */
  dispose(): void;
}
