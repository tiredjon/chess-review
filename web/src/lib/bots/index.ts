// Боты Stockfish 400…2800 (сессия 14.1): у каждого бота — свой воркер Stockfish, сила — модель
// `strength.ts` (там же — почему не `UCI_LimitStrength`), «время на раздумье» — оттуда же.
// Сигнатура `createBot` и интерфейс `Bot` — контракт (`types.ts`), не меняются.
import { Stockfish } from "@/lib/engine/stockfish";

import { clockBudgetMs, decideMove, strengthFor } from "./strength";
import type { Bot, BotMove, BotMoveRequest } from "./types";

export * from "./types";
export { strengthFor, type Strength } from "./strength";

const abortError = () => new DOMException("aborted", "AbortError");

/** Пауза, прерываемая `signal`. */
function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(abortError());
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(abortError());
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** Бот рейтинга `elo` (прижимается к 400…2800). Отклоняется с `EngineLoadError`, если движок
 *  не загрузился. */
export async function createBot(elo: number): Promise<Bot> {
  const engine = await Stockfish.create();
  const strength = strengthFor(elo);
  let disposed = false;
  // `terminate` бросает идущий поиск без ответа — ожидающий ход отклоняется отсюда.
  const rejectPending = new Set<(err: unknown) => void>();

  return {
    elo,
    async move({ fen, historyUci, signal, clock }: BotMoveRequest): Promise<BotMove> {
      if (disposed) throw new Error("Бот освобождён");
      const started = performance.now();
      const maxThinkMs = clock ? clockBudgetMs(clock.remainingMs, clock.incrementMs) : undefined;
      let reject!: (err: unknown) => void;
      const disposedWhileThinking = new Promise<never>((_, r) => (reject = r));
      rejectPending.add(reject);
      const decision = await Promise.race([
        decideMove(engine, { fen, historyUci, signal, maxThinkMs }, strength),
        disposedWhileThinking,
      ]).finally(() => rejectPending.delete(reject));
      // Поиск уже занял часть «раздумья» — ждём остаток.
      await sleep(Math.max(0, decision.thinkMs - (performance.now() - started)), signal);
      const cp = Math.abs(decision.cp) > 90_000 ? Math.sign(decision.cp) * 100_000 : decision.cp;
      return { uci: decision.uci, cp };
    },
    async newGame() {
      if (!disposed) await engine.newGame();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      engine.terminate();
      rejectPending.forEach((reject) => reject(abortError()));
      rejectPending.clear();
    },
  };
}
