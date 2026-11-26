// Цель тренажёра эндшпиля и её выполнение (сессия 16.3): чистая логика без React и алиасов `@/`,
// чтобы её исполнял Node напрямую (≥ 23 — .ts без компиляции).
//
//   Тесты: cd web && node --test src/components/endgames/goal.test.mjs
//
// Правила (SPEC «Сессия 16.3»):
//  - win — поставить мат. Провал: ничья по правилам, свой мат или сдача, потеря выигрыша по
//    таблицам (после хода человека позиция по таблицам уже не выигрыш).
//  - draw — ничья по правилам или удержание DRAW_HOLD_MOVES своих ходов, после каждого из которых
//    таблицы не дают проигрыш (позиция > 7 фигур таблиц не имеет — там считаются просто ходы без
//    мата). Провал: проигрыш по таблицам после хода человека, мат, сдача. Мат сопернику — успех.
//  Таблицы проверяются по ходам человека по порядку; ответ ещё не пришёл — дальше не смотрим.

export type Goal = "win" | "draw";
export type TbCategory = "win" | "cursed-win" | "draw" | "blessed-loss" | "loss" | "unknown";
/** Результат по таблицам для плашки: правило 50 ходов учтено (cursed-win — ничья). */
export type Wdl = "win" | "draw" | "loss";
export type Color = "white" | "black";

/** Сколько своих ходов удержать ничью, чтобы цель «ничья» считалась выполненной. */
export const DRAW_HOLD_MOVES = 12;
/** Таблицы Syzygy — позиции не больше 7 фигур (вместе с королями). */
export const TB_MAX_PIECES = 7;

export function wdlOf(category: TbCategory): Wdl | null {
  if (category === "win") return "win";
  if (category === "loss") return "loss";
  if (category === "unknown") return null;
  return "draw";
}

export function flipWdl(wdl: Wdl): Wdl {
  return wdl === "win" ? "loss" : wdl === "loss" ? "win" : "draw";
}

/** Фигур на доске (вместе с королями) по FEN. */
export function pieceCount(fen: string): number {
  return (fen.split(" ")[0].match(/[prnbqk]/gi) ?? []).length;
}

/**
 * Ответ таблиц по позиции после хода человека — глазами человека: `undefined` — ответа ещё нет,
 * `null` — таблиц нет (> 7 фигур, таблицы недоступны, неизвестно).
 */
export type HumanTb = Wdl | null | undefined;

export type RulesEnd = {
  reason: "checkmate" | "stalemate" | "repetition" | "fifty_moves" | "insufficient_material" | "resign";
  winner: Color | null;
};

export type GoalStatus =
  | { state: "playing"; held: number }
  | { state: "success"; reason: "mate" | "draw_rules" | "held"; held: number }
  | {
      state: "failure";
      reason: "lost_win" | "lost_draw" | "draw_rules" | "mated" | "resigned";
      /** Число полуходов после хода, которым упущен результат (по таблицам); иначе null. */
      missedAt: number | null;
    };

export type GoalInput = {
  goal: Goal;
  human: Color;
  /** Очередь хода в начальной позиции. */
  firstMover: Color;
  /** Полуходов сыграно. */
  plies: number;
  /** Таблицы после каждого хода человека: ключ — число полуходов после этого хода. */
  tbAfter: ReadonlyMap<number, HumanTb>;
  end: RulesEnd | null;
};

/** Номера (число полуходов после хода) ходов человека в партии из `plies` полуходов. */
export function humanPlies(human: Color, firstMover: Color, plies: number): number[] {
  const result: number[] = [];
  for (let after = 1; after <= plies; after += 1) {
    const mover = (after - 1) % 2 === 0 ? firstMover : firstMover === "white" ? "black" : "white";
    if (mover === human) result.push(after);
  }
  return result;
}

export function evaluateGoal(input: GoalInput): GoalStatus {
  const { goal, human, end } = input;
  let held = 0;
  for (const after of humanPlies(human, input.firstMover, input.plies)) {
    const tb = input.tbAfter.get(after);
    if (tb === undefined) break;
    if (goal === "win" && tb !== null && tb !== "win") return { state: "failure", reason: "lost_win", missedAt: after };
    if (goal === "draw" && tb === "loss") return { state: "failure", reason: "lost_draw", missedAt: after };
    held += 1;
  }
  if (end) {
    if (end.reason === "resign") return { state: "failure", reason: "resigned", missedAt: null };
    if (end.winner === human) return { state: "success", reason: "mate", held };
    if (end.winner !== null) return { state: "failure", reason: "mated", missedAt: null };
    return goal === "draw"
      ? { state: "success", reason: "draw_rules", held }
      : { state: "failure", reason: "draw_rules", missedAt: null };
  }
  if (goal === "draw" && held >= DRAW_HOLD_MOVES) return { state: "success", reason: "held", held };
  return { state: "playing", held };
}

/**
 * Цель с поправкой на таблицы в начальной позиции (позиции из своих партий: цель по win% до
 * хода может расходиться с таблицами). `start` — таблицы глазами человека: win → выиграть,
 * draw → сделать ничью, loss → тренировать нечего (null); нет таблиц — цель как есть.
 */
export function effectiveGoal(goal: Goal, start: Wdl | null): Goal | null {
  if (start === null) return goal;
  if (start === "loss") return null;
  return start;
}

export type TbMove = { uci: string; san: string; category: TbCategory };

/** Ход соперника по таблицам: лучший для него (ходы уже упорядочены бэкендом). */
export function bookMoveFrom(moves: readonly TbMove[]): string | null {
  return moves[0]?.uci ?? null;
}

/** Лучшие ходы человека в позиции (с тем же результатом, что у лучшего), для подсказки. */
export function bestMoves(moves: readonly TbMove[], limit = 3): TbMove[] {
  const first = moves[0];
  if (!first) return [];
  return moves.filter((move) => move.category === first.category).slice(0, limit);
}
