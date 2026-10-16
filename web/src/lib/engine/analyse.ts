// Анализ партии в браузере — та же схема, что `Analyzer` на сервере
// (backend/app/engine/analyzer.py): каждая позиция с MultiPV=1, а если из неё в партии
// сыгран лучший ход — ещё `multipv − 1` линий поиском без этого хода. Оценки уходят
// в API (`POST /games/{id}/browser-analysis`), разбор делает сервер — общей логикой `review/`.
import { Chess } from "chess.js";
import type { Stockfish, StockfishPool } from "./stockfish";
import type { EngineLine } from "./uci";

/** Оценка позиции в формате API (`ExternalEvalIn`, он же формат кэша `position_evals`). */
export type ExternalEval = { depth: number; lines: EngineLine[] };

export type PositionTask = { fen: string; played: string[] };

// Предел на один поиск. Обычно глубина достигается за доли секунды, но поиск альтернатив
// к ходу, который ставит мат (все прочие ходы проигрывают), lite-сеть на глубине 18 считает
// десятки секунд — такая позиция сохраняется с меньшей глубиной.
const SEARCH_CAP_MS = 8000;

function legalMoves(fen: string): string[] {
  return new Chess(fen).moves({ verbose: true }).map((move) => move.lan);
}

/** Ключ позиции без счётчиков ходов — повторы считаются один раз (как `fen_key`). */
const positionKey = (fen: string) => fen.split(" ").slice(0, 4).join(" ");

/** Оценка одной позиции; `played` — ходы, сыгранные из неё. null — ходов нет (мат, пат). */
export async function analysePosition(
  engine: Stockfish,
  { fen, played }: PositionTask,
  { depth, multipv, signal }: { depth: number; multipv: number; signal?: AbortSignal },
): Promise<ExternalEval | null> {
  const legal = legalMoves(fen);
  if (legal.length === 0) return null;
  const base = await engine.search({ fen, depth, multipv: 1, movetime: SEARCH_CAP_MS, signal });
  const best = base.lines[0]?.pv[0];
  if (!best) return null;
  const result: ExternalEval = { depth: base.depth, lines: base.lines.slice(0, 1) };
  if (multipv <= 1 || !played.includes(best) || legal.length < 2) return result;
  const alternatives = await engine.search({
    fen,
    depth,
    multipv: multipv - 1,
    searchmoves: legal.filter((move) => move !== best),
    movetime: SEARCH_CAP_MS,
    signal,
  });
  result.lines.push(...alternatives.lines);
  return result;
}

/** Позиции партии для анализа: после 0, 1, … полуходов и ход, сыгранный из каждой. */
export function gamePositions(startFen: string, plies: { uci: string; fenAfter: string }[]): PositionTask[] {
  return [
    { fen: startFen, played: plies[0] ? [plies[0].uci] : [] },
    ...plies.map((ply, index) => ({ fen: ply.fenAfter, played: plies[index + 1] ? [plies[index + 1].uci] : [] })),
  ];
}

/** Оценки всех позиций (повторы позиций — один раз, со всеми сыгранными из неё ходами). */
export async function analyseGame(
  pool: StockfishPool,
  positions: PositionTask[],
  options: { depth: number; multipv: number; signal?: AbortSignal; onProgress?: (done: number, total: number) => void },
): Promise<(ExternalEval | null)[]> {
  const unique = new Map<string, PositionTask>();
  for (const position of positions) {
    const key = positionKey(position.fen);
    const known = unique.get(key);
    if (known) known.played.push(...position.played);
    else unique.set(key, { fen: position.fen, played: [...position.played] });
  }
  let done = 0;
  const total = unique.size;
  options.onProgress?.(0, total);
  const results = new Map<string, ExternalEval | null>();
  await Promise.all(
    [...unique].map(([key, task]) =>
      pool.run(async (engine) => {
        results.set(key, await analysePosition(engine, task, options));
        options.onProgress?.(++done, total);
      }),
    ),
  );
  return positions.map((position) => results.get(positionKey(position.fen)) ?? null);
}

/** Проба для пазла (`puzzle_probes` из ответа API): MultiPV=2 при сыгранном `move`. */
export type PuzzleProbe = { fen: string; move: string };

export async function answerProbes(
  pool: StockfishPool,
  probes: PuzzleProbe[],
  { depth, signal }: { depth: number; signal?: AbortSignal },
): Promise<{ fen: string; move: string; eval: ExternalEval }[]> {
  const answers = await Promise.all(
    probes.map((probe) =>
      pool.run(async (engine) => {
        const result = await analysePosition(engine, { fen: probe.fen, played: [probe.move] }, { depth, multipv: 2, signal });
        return result && { ...probe, eval: result };
      }),
    ),
  );
  return answers.filter((answer) => answer !== null);
}
