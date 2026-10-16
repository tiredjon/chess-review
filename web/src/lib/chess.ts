// Позиции партии и линий: chess.js считает FEN после ходов и проверяет ходы на доске.
import { Chess } from "chess.js";
import type { Color, LineMove, MoveOut } from "./types";

/** Полуход партии; `move` — разбор, если анализ готов. */
export type Ply = {
  index: number;
  san: string;
  uci: string;
  fenBefore: string;
  fenAfter: string;
  color: Color;
  fullmove: number;
  move: MoveOut | null;
};

export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export function uciSquares(uci: string): { from: string; to: string; promotion?: string } {
  return { from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] };
}

/** FEN после хода в UCI; null — ход нелегален (или нулевой ход угрозы). */
export function applyUci(fen: string, uci: string): string | null {
  if (uci === "0000") return null;
  try {
    const board = new Chess(fen);
    board.move(uciSquares(uci));
    return board.fen();
  } catch {
    return null;
  }
}

export const sideToMove = (fen: string): Color => (fen.split(" ")[1] === "b" ? "black" : "white");

/** Полуходы из готового разбора. */
export function pliesFromMoves(moves: MoveOut[]): Ply[] {
  return moves.map((move, index) => ({
    index,
    san: move.san,
    uci: move.uci,
    fenBefore: move.fen_before,
    fenAfter: moves[index + 1]?.fen_before ?? applyUci(move.fen_before, move.uci) ?? move.fen_before,
    color: move.color,
    fullmove: move.fullmove,
    move,
  }));
}

/** Полуходы из PGN — чтобы смотреть партию до готовности анализа. */
export function pliesFromPgn(pgn: string): { plies: Ply[]; startFen: string } {
  const board = new Chess();
  try {
    board.loadPgn(pgn);
  } catch {
    return { plies: [], startFen: START_FEN };
  }
  const history = board.history({ verbose: true });
  const plies = history.map((move, index) => ({
    index,
    san: move.san,
    uci: move.lan,
    fenBefore: move.before,
    fenAfter: move.after,
    color: (move.color === "w" ? "white" : "black") as Color,
    fullmove: Number(move.before.split(" ")[5]),
    move: null,
  }));
  return { plies, startFen: history[0]?.before ?? START_FEN };
}

/** Позиции линии: [0] — исходная, [i] — после i-го хода; обрывается на нелегальном ходе. */
export function lineFens(fen: string, line: LineMove[]): string[] {
  const fens = [fen];
  for (const move of line) {
    const next = applyUci(fens[fens.length - 1], move.uci);
    if (next === null) break;
    fens.push(next);
  }
  return fens;
}

/** Ход с доски → UCI, если он легален (превращение — в ферзя, если не указано другое). */
export function boardMoveUci(fen: string, from: string, to: string, promotion = "q"): string | null {
  try {
    const board = new Chess(fen);
    const move = board.move({ from, to, promotion });
    return move.lan;
  } catch {
    return null;
  }
}

/** Номер хода для списка: `12.` у белых, `12…` у чёрных. */
export const moveNumber = (ply: Pick<Ply, "fullmove" | "color">) =>
  ply.color === "white" ? `${ply.fullmove}.` : `${ply.fullmove}…`;

/** Подписи ходов линии с номерами: `24. Rxd4`, `Qxd4`, `25. Bc3`; первый ход чёрных — `24… Qxd4`. */
export function lineLabels(fen: string, line: LineMove[]): string[] {
  let color = sideToMove(fen);
  let fullmove = Number(fen.split(" ")[5]) || 1;
  return line.map((move, i) => {
    const label =
      color === "white" ? `${fullmove}. ${move.san}` : i === 0 ? `${fullmove}… ${move.san}` : move.san;
    if (color === "black") fullmove += 1;
    color = color === "white" ? "black" : "white";
    return label;
  });
}

/** SAN хода в UCI; null — ход нелегален. */
export function uciSan(fen: string, uci: string): string | null {
  try {
    return new Chess(fen).move(uciSquares(uci)).san;
  } catch {
    return null;
  }
}

/** Фигура на клетке в FEN-обозначении (`N` — белый конь, `n` — чёрный) или null. */
export function pieceOn(fen: string, square: string): string | null {
  try {
    const piece = new Chess(fen).get(square as Parameters<Chess["get"]>[0]);
    if (!piece) return null;
    return piece.color === "w" ? piece.type.toUpperCase() : piece.type;
  } catch {
    return null;
  }
}
