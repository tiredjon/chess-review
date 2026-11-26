// ЗАГЛУШКА фундамента сессии 14: случайный легальный ход. Заменяет подсессия 14.1
// (настоящие боты на Stockfish). Сигнатура `createBot` — часть контракта, не меняется.
import { Chess } from "chess.js";
import type { Bot, BotMove, BotMoveRequest } from "./types";

export * from "./types";

export async function createBot(elo: number): Promise<Bot> {
  return {
    elo,
    async move({ fen, signal }: BotMoveRequest): Promise<BotMove> {
      await new Promise((resolve) => setTimeout(resolve, 400));
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      const moves = new Chess(fen).moves({ verbose: true });
      const move = moves[Math.floor(Math.random() * moves.length)];
      return { uci: `${move.from}${move.to}${move.promotion ?? ""}` };
    },
    async newGame() {},
    dispose() {},
  };
}
