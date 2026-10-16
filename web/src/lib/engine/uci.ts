// Разбор вывода UCI-движка (строки `info …`). Оценки — за сторону на ходу, как в UCI
// и в API (`ExternalLineIn`).

/** Линия движка в формате API: ровно одно из `cp` / `mate`. */
export type EngineLine = ({ cp: number; mate?: undefined } | { mate: number; cp?: undefined }) & {
  pv: string[];
};

export type UciInfo = {
  depth: number;
  multipv: number;
  /** Оценка — граница окна поиска (`lowerbound` / `upperbound`), а не точная. */
  bound: boolean;
  line: EngineLine;
};

/** `info depth 18 … multipv 2 score cp -35 … pv e2e4 e7e5` → UciInfo; null — не линия. */
export function parseInfo(text: string): UciInfo | null {
  if (!text.startsWith("info ")) return null;
  const tokens = text.split(" ");
  let depth = 0;
  let multipv = 1;
  let bound = false;
  let score: { cp: number } | { mate: number } | null = null;
  let pv: string[] = [];
  for (let i = 1; i < tokens.length; i++) {
    switch (tokens[i]) {
      case "depth":
        depth = Number(tokens[++i]);
        break;
      case "multipv":
        multipv = Number(tokens[++i]);
        break;
      case "score": {
        const kind = tokens[++i];
        const value = Number(tokens[++i]);
        score = kind === "mate" ? { mate: value } : { cp: value };
        break;
      }
      case "lowerbound":
      case "upperbound":
        bound = true;
        break;
      case "pv":
        pv = tokens.slice(i + 1).filter(Boolean);
        i = tokens.length;
        break;
    }
  }
  if (score === null || pv.length === 0 || !Number.isFinite(depth)) return null;
  return { depth, multipv, bound, line: { ...score, pv } as EngineLine };
}

/** `bestmove e2e4 ponder e7e5` → `e2e4`; `(none)` (ходов нет) → null. */
export function parseBestMove(text: string): string | null | undefined {
  if (!text.startsWith("bestmove")) return undefined;
  const move = text.split(" ")[1];
  return !move || move === "(none)" ? null : move;
}
