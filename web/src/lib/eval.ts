// Оценки в API — за игрока, сделавшего ход (SPEC §4.1). Eval-бару и графику нужна
// оценка за белых: здесь перевод и форматирование.
import type { Color, MoveOut } from "./types";

/** Оценка позиции с точки зрения белых. */
export type WhiteEval =
  | { kind: "cp"; cp: number }
  /** `moves > 0` — мат ставят белые, `< 0` — чёрные. */
  | { kind: "mate"; moves: number }
  /** На доске мат. */
  | { kind: "checkmate"; winner: Color };

function toWhite(color: Color, cp: number | null, mate: number | null): WhiteEval {
  const sign = color === "white" ? 1 : -1;
  if (mate === 0) return { kind: "checkmate", winner: color };
  if (mate !== null) return { kind: "mate", moves: sign * mate };
  return { kind: "cp", cp: sign * (cp ?? 0) };
}

/** Оценка позиции перед ходом. */
export const evalBefore = (move: MoveOut) =>
  toWhite(move.color, move.eval_before_cp, move.mate_before);

/** Оценка позиции после хода. */
export const evalAfter = (move: MoveOut) => toWhite(move.color, move.eval_after_cp, move.mate_after);

/** Оценки всех позиций партии: [0] — начальная, [i] — после i-го полухода. */
export function positionEvals(moves: MoveOut[]): WhiteEval[] {
  if (moves.length === 0) return [];
  return [evalBefore(moves[0]), ...moves.map(evalAfter)];
}

/** Win% белых по формуле Lichess (SPEC §4.2); мат — 0 или 100. */
export function whiteWinPercent(evaluation: WhiteEval): number {
  switch (evaluation.kind) {
    case "checkmate":
      return evaluation.winner === "white" ? 100 : 0;
    case "mate":
      return evaluation.moves > 0 ? 100 : 0;
    case "cp": {
      const cp = Math.max(-1000, Math.min(1000, evaluation.cp));
      return 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1);
    }
  }
}

/** `+1.20`, `−0.35`, `#3` (мат ставят белые), `#−2` (чёрные), `1-0` — мат на доске. */
export function formatEval(evaluation: WhiteEval): string {
  switch (evaluation.kind) {
    case "checkmate":
      return evaluation.winner === "white" ? "1-0" : "0-1";
    case "mate":
      return evaluation.moves > 0 ? `#${evaluation.moves}` : `#−${-evaluation.moves}`;
    case "cp": {
      const pawns = evaluation.cp / 100;
      if (Math.abs(pawns) < 0.005) return "0.00";
      return `${pawns > 0 ? "+" : "−"}${Math.abs(pawns).toFixed(2)}`;
    }
  }
}

/** Короткая подпись для eval-бара: `1.2`, `M3`. */
export function formatEvalShort(evaluation: WhiteEval): string {
  switch (evaluation.kind) {
    case "checkmate":
      return "#";
    case "mate":
      return `M${Math.abs(evaluation.moves)}`;
    case "cp": {
      const pawns = Math.abs(evaluation.cp / 100);
      return pawns >= 10 ? pawns.toFixed(0) : pawns.toFixed(1);
    }
  }
}

/** Чья позиция лучше (для цвета подписи); равенство — белые. */
export function leader(evaluation: WhiteEval): Color {
  return whiteWinPercent(evaluation) >= 50 ? "white" : "black";
}

/** Оценка линии MultiPV (за ходящего) с точки зрения белых. */
export function lineEval(color: Color, cp: number | null, mate: number | null): WhiteEval {
  return toWhite(color, cp, mate);
}
