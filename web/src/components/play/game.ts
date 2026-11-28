// Логика партии с ботом без React: позиции по ходам, конец партии по правилам, PGN, материал.
import { Chess } from "chess.js";
import { START_FEN, uciSquares } from "@/lib/chess";
import type { Color } from "@/lib/types";
import { clkComment, pgnTimeControl, type TimeControl } from "./clock";
import type { GameEndReason, GameResult } from "./types";

export type Replay = {
  /** [0] — начальная позиция, [i] — после i-го полуода. */
  fens: string[];
  sans: string[];
  /** Ходы, которые удалось сыграть (обрывается на нелегальном). */
  moves: string[];
  /** Конец партии по правилам (без сдачи); null — партия идёт. */
  end: { reason: Exclude<GameEndReason, "resign">; winner: Color | null } | null;
  inCheck: boolean;
};

export const opposite = (color: Color): Color => (color === "white" ? "black" : "white");

/** Очередь хода и номер хода позиции — с них нумеруются ходы партии с позиции. */
export function startOf(fen: string): { turn: Color; fullmove: number } {
  const [, turn, , , , fullmove] = fen.split(" ");
  return { turn: turn === "b" ? "black" : "white", fullmove: Math.max(1, Number(fullmove) || 1) };
}

/** Цвет полуода с номером `index` (0 — первый ход партии) при очереди `first` в начале. */
export const plyColorFrom = (first: Color, index: number): Color => (index % 2 === 0 ? first : opposite(first));

/** Корректный FEN, с которого можно начать партию (позиция легальна, партия не окончена). */
export function isPlayableFen(fen: string): boolean {
  try {
    const board = new Chess(fen);
    return !board.isGameOver();
  } catch {
    return false;
  }
}

/** Ходы партии с позиции `startFen` (по умолчанию — начальная позиция). */
export function replay(moves: readonly string[], startFen: string = START_FEN): Replay {
  const board = new Chess(startFen);
  const fens = [board.fen()];
  const sans: string[] = [];
  const played: string[] = [];
  for (const uci of moves) {
    try {
      sans.push(board.move(uciSquares(uci)).san);
    } catch {
      break;
    }
    played.push(uci);
    fens.push(board.fen());
  }
  return { fens, sans, moves: played, end: endOf(board), inCheck: board.inCheck() };
}

function endOf(board: Chess): Replay["end"] {
  if (board.isCheckmate()) return { reason: "checkmate", winner: board.turn() === "w" ? "black" : "white" };
  if (board.isStalemate()) return { reason: "stalemate", winner: null };
  if (board.isInsufficientMaterial()) return { reason: "insufficient_material", winner: null };
  if (board.isThreefoldRepetition()) return { reason: "repetition", winner: null };
  if (board.isDrawByFiftyMoves()) return { reason: "fifty_moves", winner: null };
  return null;
}

/** Легальные ходы фигуры с клетки: клетка → взятие ли это. */
export function targets(fen: string, from: string): Map<string, boolean> {
  const result = new Map<string, boolean>();
  try {
    for (const move of new Chess(fen).moves({ square: from as never, verbose: true })) {
      result.set(move.to, move.isCapture() || move.isEnPassant());
    }
  } catch {
    // Клетка без фигуры — ходов нет.
  }
  return result;
}

/** Ход с доски — превращение пешки (нужен выбор фигуры)? */
export function isPromotion(fen: string, from: string, to: string): boolean {
  try {
    return new Chess(fen).moves({ square: from as never, verbose: true }).some((move) => move.to === to && !!move.promotion);
  } catch {
    return false;
  }
}

/** Позиция, пока выбирается фигура превращения: пешка уже стоит на последней горизонтали.
 * FEN правится вручную — chess.js не ставит пешку на крайнюю горизонталь. */
export function pawnOnTarget(fen: string, from: string, to: string): string {
  const [placement, ...rest] = fen.split(" ");
  const rows = placement.split("/").map((row) => row.replace(/\d/g, (n) => ".".repeat(Number(n))).split(""));
  const cell = (square: string) => ({ row: 8 - Number(square[1]), col: square.charCodeAt(0) - 97 });
  const a = cell(from);
  const b = cell(to);
  const pawn = rows[a.row]?.[a.col];
  if (!pawn || pawn === "." || !rows[b.row]) return fen;
  rows[a.row][a.col] = ".";
  rows[b.row][b.col] = pawn;
  const packed = rows.map((row) => row.join("").replace(/\.+/g, (dots) => String(dots.length))).join("/");
  return [packed, ...rest].join(" ");
}

/** Легален ли ход (UCI) в позиции — для хода «книги». */
export function isLegal(fen: string, uci: string): boolean {
  try {
    new Chess(fen).move(uciSquares(uci));
    return true;
  } catch {
    return false;
  }
}

const pgnDate = (date: Date) =>
  `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}`;

export type ResultInput = {
  moves: readonly string[];
  reason: GameEndReason;
  winner: Color | null;
  /** Цвет человека и подписи сторон для PGN. */
  color: Color;
  you: string;
  botName: string;
  elo: number;
  event: string;
  headers?: Record<string, string>;
  /** Партия с позиции: в PGN — заголовки SetUp / FEN (chess.js ставит их сам). */
  startFen?: string;
  /** Партия с часами: заголовок TimeControl и остаток после каждого хода ([%clk …]). */
  timeControl?: TimeControl | null;
  /** Остаток на часах сходившего после каждого полухода, мс (по индексу хода). */
  clocks?: readonly number[];
};

export function buildResult(input: ResultInput): GameResult {
  const result: GameResult["result"] = input.winner === "white" ? "1-0" : input.winner === "black" ? "0-1" : "1/2-1/2";
  const board = new Chess(input.startFen ?? START_FEN);
  input.moves.forEach((uci, index) => {
    board.move(uciSquares(uci));
    const clock = input.timeControl ? input.clocks?.[index] : undefined;
    if (clock !== undefined) board.setComment(clkComment(clock));
  });
  const white = input.color === "white" ? input.you : input.botName;
  const black = input.color === "black" ? input.you : input.botName;
  const headers: Record<string, string> = {
    Event: input.event,
    Site: "Chess Review",
    Date: pgnDate(new Date()),
    White: white,
    Black: black,
    Result: result,
    ...(input.color === "white" ? { BlackElo: String(input.elo) } : { WhiteElo: String(input.elo) }),
    Termination: input.reason,
    ...(input.timeControl ? { TimeControl: pgnTimeControl(input.timeControl) } : {}),
    ...input.headers,
  };
  headers.Result = result;
  for (const [key, value] of Object.entries(headers)) board.setHeader(key, value);
  return { result, reason: input.reason, winner: input.winner, historyUci: [...input.moves], pgn: board.pgn() };
}

const VALUES = { p: 1, n: 3, b: 3, r: 5, q: 9 } as const;
const START_COUNT = { p: 8, n: 2, b: 2, r: 2, q: 1 } as const;
export type PieceKind = keyof typeof VALUES;
const KINDS: PieceKind[] = ["p", "n", "b", "r", "q"];

type Counts = Record<"w" | "b", Record<PieceKind, number>>;

function countPieces(fen: string): Counts {
  const counts: Counts = { w: { p: 0, n: 0, b: 0, r: 0, q: 0 }, b: { p: 0, n: 0, b: 0, r: 0, q: 0 } };
  for (const char of fen.split(" ")[0]) {
    const kind = char.toLowerCase() as PieceKind;
    if (!(kind in VALUES)) continue;
    counts[char === kind ? "b" : "w"][kind] += 1;
  }
  return counts;
}

/**
 * Взятые фигуры соперника (по видам) и перевес в материале для каждой стороны. Взятые считаются
 * от `startFen` (партия с позиции — от неё), иначе от полного комплекта.
 */
export function material(fen: string, startFen?: string): Record<Color, { captured: PieceKind[]; advantage: number }> {
  const counts = countPieces(fen);
  const base: Counts = startFen ? countPieces(startFen) : { w: START_COUNT, b: START_COUNT };
  const sum = (side: "w" | "b") => KINDS.reduce((total, kind) => total + counts[side][kind] * VALUES[kind], 0);
  const captured = (side: "w" | "b") =>
    KINDS.flatMap((kind) => Array<PieceKind>(Math.max(0, base[side][kind] - counts[side][kind])).fill(kind));
  const diff = sum("w") - sum("b");
  return {
    white: { captured: captured("b"), advantage: Math.max(0, diff) },
    black: { captured: captured("w"), advantage: Math.max(0, -diff) },
  };
}

/** Может ли сторона в принципе поставить мат (для флага): пешка, ладья, ферзь или две лёгкие. */
export function canMate(fen: string, side: Color): boolean {
  const counts = countPieces(fen)[side === "white" ? "w" : "b"];
  return counts.p + counts.r + counts.q > 0 || counts.n + counts.b >= 2;
}

/** Клетка короля под шахом в позиции или null. */
export function checkedKing(fen: string): string | null {
  try {
    const board = new Chess(fen);
    if (!board.inCheck()) return null;
    const turn = board.turn();
    for (const row of board.board()) {
      for (const cell of row) if (cell && cell.type === "k" && cell.color === turn) return cell.square;
    }
  } catch {
    // Некорректный FEN — шаха нет.
  }
  return null;
}
