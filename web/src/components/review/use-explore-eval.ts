"use client";

import { Chess } from "chess.js";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { sideToMove, uciSquares } from "@/lib/chess";
import type { EngineSource } from "@/lib/engine/preference";
import { EngineLoadError, Stockfish } from "@/lib/engine/stockfish";
import { lineEval, type WhiteEval } from "@/lib/eval";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { EngineConfig, LineMove } from "@/lib/types";

export type ExploreEval = {
  evaluation: WhiteEval | null;
  /** Лучшая линия из позиции. */
  line: LineMove[];
  depth: number;
  /** Расчёт ещё идёт (в браузере оценка уточняется с глубиной). */
  pending: boolean;
  error: string | null;
};

const EMPTY: ExploreEval = { evaluation: null, line: [], depth: 0, pending: true, error: null };
// Запрос к API — после паузы: при быстром переборе ходов не дёргать сервер на каждый.
const API_DELAY_MS = 300;
// Оценки API по позициям — на время жизни вкладки.
const apiCache = new Map<string, ExploreEval>();
let configPromise: Promise<EngineConfig> | null = null;

function engineConfig() {
  configPromise ??= api.engineConfig().catch((err) => {
    configPromise = null;
    throw err;
  });
  return configPromise;
}

function toLine(fen: string, pv: string[]): LineMove[] {
  const board = new Chess(fen);
  const line: LineMove[] = [];
  for (const uci of pv) {
    try {
      line.push({ uci, san: board.move(uciSquares(uci)).san });
    } catch {
      break;
    }
  }
  return line;
}

/** Позиция без ходов: мат или пат — оценка без движка. */
function terminal(fen: string): ExploreEval | null {
  const board = new Chess(fen);
  if (board.moves().length > 0) return null;
  const evaluation: WhiteEval = board.isCheckmate()
    ? { kind: "checkmate", winner: sideToMove(fen) === "white" ? "black" : "white" }
    : { kind: "cp", cp: 0 };
  return { evaluation, line: [], depth: 0, pending: false, error: null };
}

/**
 * Оценка и лучшая линия любой позиции для режима исследования: движком в браузере
 * (уточняется по мере углубления) или через API (`POST /engine/analyse`).
 */
export function useExploreEval(fen: string | null, source: EngineSource): ExploreEval {
  const { t } = useI18n();
  const [result, setResult] = useState<{ fen: string; source: EngineSource; value: ExploreEval } | null>(null);
  const engine = useRef<Promise<Stockfish> | null>(null);

  // Воркер — один на экран разбора, создаётся при первом исследовании в браузере.
  useEffect(
    () => () => {
      void engine.current?.then((sf) => sf.terminate()).catch(() => undefined);
      engine.current = null;
    },
    [],
  );

  // Мат / пат и уже известные оценки API — сразу, без эффекта.
  const immediate = fen === null ? undefined : (terminal(fen) ?? (source === "server" ? apiCache.get(fen) : undefined));

  useEffect(() => {
    if (fen === null || terminal(fen) || (source === "server" && apiCache.has(fen))) return;
    const controller = new AbortController();
    const { signal } = controller;
    const update = (value: ExploreEval) => {
      if (!signal.aborted) setResult({ fen, source, value });
    };
    const fail = (err: unknown) => {
      if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
      const message =
        err instanceof ApiError ? err.message : err instanceof EngineLoadError ? t.review.browserEngineFailed : t.review.exploreFailed;
      update({ ...EMPTY, pending: false, error: message });
    };
    const color = sideToMove(fen);

    if (source === "server") {
      const timer = setTimeout(() => {
        api
          .explore(fen, signal)
          .then((out) => {
            const best = out.lines[0];
            const value: ExploreEval = {
              evaluation: best ? lineEval(color, best.cp, best.mate) : null,
              line: best?.pv ?? [],
              depth: out.depth,
              pending: false,
              error: null,
            };
            apiCache.set(fen, value);
            update(value);
          })
          .catch(fail);
      }, API_DELAY_MS);
      return () => {
        clearTimeout(timer);
        controller.abort();
      };
    }

    engine.current ??= Stockfish.create();
    const current = engine.current;
    current.catch(() => {
      if (engine.current === current) engine.current = null;
    });
    Promise.all([current, engineConfig()])
      .then(([sf, config]) =>
        sf.search({
          fen,
          depth: config.explore_depth,
          signal,
          onUpdate: ({ depth, lines }) => {
            const best = lines[0];
            if (!best) return;
            update({
              evaluation: lineEval(color, best.cp ?? null, best.mate ?? null),
              line: toLine(fen, best.pv),
              depth,
              pending: true,
              error: null,
            });
          },
        }),
      )
      .then(({ depth, lines }) => {
        const best = lines[0];
        update({
          evaluation: best ? lineEval(color, best.cp ?? null, best.mate ?? null) : null,
          line: best ? toLine(fen, best.pv) : [],
          depth,
          pending: false,
          error: null,
        });
      })
      .catch(fail);
    return () => controller.abort();
  }, [fen, source, t]);

  if (immediate) return immediate;
  if (fen === null || result === null || result.fen !== fen || result.source !== source) return EMPTY;
  return result.value;
}
