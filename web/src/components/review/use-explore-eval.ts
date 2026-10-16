"use client";

import { Chess } from "chess.js";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { sideToMove, uciSquares } from "@/lib/chess";
import type { ExternalEval } from "@/lib/engine/analyse";
import type { EngineSource } from "@/lib/engine/preference";
import { EngineLoadError, Stockfish } from "@/lib/engine/stockfish";
import type { EngineLine } from "@/lib/engine/uci";
import { lineEval, type WhiteEval } from "@/lib/eval";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { ClassifyOut, EngineConfig, LineMove, MoveClass } from "@/lib/types";

/** Линия движка: оценка за белых и ходы с SAN. */
export type ExploreLine = { evaluation: WhiteEval; moves: LineMove[] };

export type ExploreEval = {
  evaluation: WhiteEval | null;
  /** До трёх лучших линий (как в анализе Chess.com); пусто у финальной позиции. */
  lines: ExploreLine[];
  /** Оценка в формате API (за ходящего) — для класса хода; null у финальной позиции. */
  raw: ExternalEval | null;
  depth: number;
  /** Расчёт ещё идёт (в браузере оценка уточняется с глубиной). */
  pending: boolean;
  error: string | null;
};

// Линий в режиме исследования — как у сервера (`EXPLORE_LINES`).
const LINES = 3;
const PENDING: ExploreEval = { evaluation: null, lines: [], raw: null, depth: 0, pending: true, error: null };
// Запрос к API — после паузы: при быстром переборе ходов не дёргать сервер на каждый.
const API_DELAY_MS = 300;
// Готовые оценки и классы ходов — на время жизни вкладки (ключ — движок и позиция).
const evalCache = new Map<string, ExploreEval>();
const classCache = new Map<string, ClassifyOut>();
let configPromise: Promise<EngineConfig> | null = null;

function engineConfig() {
  configPromise ??= api.engineConfig().catch((err) => {
    configPromise = null;
    throw err;
  });
  return configPromise;
}

function toMoves(fen: string, pv: string[]): LineMove[] {
  const board = new Chess(fen);
  const moves: LineMove[] = [];
  for (const uci of pv) {
    try {
      moves.push({ uci, san: board.move(uciSquares(uci)).san });
    } catch {
      break;
    }
  }
  return moves;
}

/** Позиция без ходов: мат или пат — оценка без движка. */
function terminal(fen: string): ExploreEval | null {
  const board = new Chess(fen);
  if (board.moves().length > 0) return null;
  const evaluation: WhiteEval = board.isCheckmate()
    ? { kind: "checkmate", winner: sideToMove(fen) === "white" ? "black" : "white" }
    : { kind: "cp", cp: 0 };
  return { evaluation, lines: [], raw: null, depth: 0, pending: false, error: null };
}

function fromLines(fen: string, depth: number, lines: EngineLine[], pending: boolean): ExploreEval {
  const color = sideToMove(fen);
  const shown = lines.map((line) => ({
    evaluation: lineEval(color, line.cp ?? null, line.mate ?? null),
    moves: toMoves(fen, line.pv),
  }));
  return { evaluation: shown[0]?.evaluation ?? null, lines: shown, raw: { depth, lines }, depth, pending, error: null };
}

const cacheKey = (source: EngineSource, fen: string) => `${source}|${fen}`;

/**
 * Оценки позиций режима исследования: движком в браузере (уточняется по мере углубления)
 * или через API (`POST /engine/analyse`). Считаются по очереди позиции из `targets`
 * (текущая, затем позиция до хода — она нужна для класса хода); готовые — из кэша вкладки.
 */
export function useExploreEvals(targets: string[], source: EngineSource): (fen: string) => ExploreEval {
  const { t } = useI18n();
  const [partial, setPartial] = useState<{ key: string; value: ExploreEval } | null>(null);
  // Счётчик готовых оценок: кэш — вне React, перерисовка — по нему.
  const [, setCompleted] = useState(0);
  const engine = useRef<Promise<Stockfish> | null>(null);

  // Воркер — один на экран разбора, создаётся при первом исследовании в браузере.
  useEffect(
    () => () => {
      void engine.current?.then((sf) => sf.terminate()).catch(() => undefined);
      engine.current = null;
    },
    [],
  );

  const next = targets.find((fen) => !terminal(fen) && !evalCache.has(cacheKey(source, fen))) ?? null;

  useEffect(() => {
    if (next === null) return;
    const fen = next;
    const key = cacheKey(source, fen);
    const controller = new AbortController();
    const { signal } = controller;
    const update = (value: ExploreEval) => {
      if (signal.aborted) return;
      if (value.pending) {
        setPartial({ key, value });
      } else {
        if (!value.error) evalCache.set(key, value);
        else setPartial({ key, value });
        setCompleted((n) => n + 1);
      }
    };
    const fail = (err: unknown) => {
      if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
      const message =
        err instanceof ApiError ? err.message : err instanceof EngineLoadError ? t.review.browserEngineFailed : t.review.exploreFailed;
      update({ ...PENDING, pending: false, error: message });
    };

    if (source === "server") {
      const timer = setTimeout(() => {
        api
          .explore(fen, signal)
          .then((out) =>
            update(
              fromLines(
                fen,
                out.depth,
                out.lines.map((line) => ({
                  ...(line.mate !== null ? { mate: line.mate } : { cp: line.cp ?? 0 }),
                  pv: line.pv.map((move) => move.uci),
                })),
                false,
              ),
            ),
          )
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
          multipv: LINES,
          signal,
          onUpdate: ({ depth, lines }) => update(fromLines(fen, depth, lines, true)),
        }),
      )
      .then(({ depth, lines }) => update(fromLines(fen, depth, lines, false)))
      .catch(fail);
    return () => controller.abort();
  }, [next, source, t]);

  return (fen: string) => {
    const key = cacheKey(source, fen);
    return terminal(fen) ?? evalCache.get(key) ?? (partial?.key === key ? partial.value : PENDING);
  };
}

export type ExploreStep = {
  fenBefore: string;
  uci: string;
  before: ExploreEval;
  after: ExploreEval;
  /** Класс предыдущего хода (соперника) — для «упущения» — и позиция перед ним. */
  previous: MoveClass | null;
  priorFen: string | null;
};

/**
 * Класс хода исследования — на сервере той же логикой, что разбор партии
 * (`POST /engine/classify`), когда готовы оценки позиций до и после хода.
 */
export function useExploreClass(step: ExploreStep | null, source: EngineSource): ClassifyOut | null {
  const [, setDone] = useState(0);
  const ready =
    step !== null &&
    !step.before.pending &&
    step.before.raw !== null &&
    !step.after.pending &&
    !step.after.error &&
    (step.after.raw !== null || step.after.lines.length === 0);
  const key = step && `${source}|${step.fenBefore}|${step.uci}|${step.previous ?? ""}|${step.before.depth}`;

  useEffect(() => {
    if (!ready || key === null || !step || classCache.has(key)) return;
    let cancelled = false;
    api
      .classifyMove({
        fen: step.fenBefore,
        move: step.uci,
        before: step.before.raw!,
        after: step.after.raw,
        previous: step.previous,
        prior_fen: step.priorFen,
      })
      .then((result) => {
        classCache.set(key, result);
        if (!cancelled) setDone((n) => n + 1);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // `step` пересоздаётся на каждый рендер — его содержимое уже в ключе и `ready`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, key]);

  return key ? (classCache.get(key) ?? null) : null;
}

/** Готовый класс хода исследования из кэша (для списка ходов), без запроса. */
export function cachedExploreClass(source: EngineSource, fenBefore: string, uci: string): ClassifyOut | null {
  for (const [key, value] of classCache) {
    if (key.startsWith(`${source}|${fenBefore}|${uci}|`)) return value;
  }
  return null;
}
