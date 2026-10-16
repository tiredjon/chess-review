"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { pliesFromPgn } from "@/lib/chess";
import { analyseGame, answerProbes, gamePositions } from "@/lib/engine/analyse";
import type { EngineSource } from "@/lib/engine/preference";
import { EngineLoadError, StockfishPool } from "@/lib/engine/stockfish";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { AnalysisOut, JobStatus, ProgressEvent } from "@/lib/types";

export type AnalysisState = {
  id: string;
  /** Где идёт анализ: прогресс серверного — по SSE, браузерного — от своего движка. */
  runner: EngineSource;
  status: JobStatus;
  done: number;
  total: number;
  error: string | null;
  /** Код ошибки — текст по нему (`codeText`), `error` — подробности. */
  error_code: string | null;
};

const POLL_MS = 2000;
const isActive = (status: JobStatus) => status === "queued" || status === "running";

function fromAnalysis(analysis: AnalysisOut): AnalysisState {
  return {
    id: analysis.id,
    runner: analysis.runner,
    status: analysis.status,
    done: analysis.progress?.done ?? 0,
    total: analysis.progress?.total ?? 0,
    error: analysis.error,
    error_code: analysis.error_code,
  };
}

const BROWSER_RUN = "browser";

/**
 * Запуск анализа. На сервере — прогресс по SSE (`GET /analyses/{id}/events`), если поток
 * недоступен — полинг `GET /analyses/{id}`. В браузере — пул Stockfish WASM считает оценки
 * (`lib/engine/analyse.ts`), сервер делает по ним разбор, затем браузер досчитывает пробы
 * для пазлов. `onDone` — перезагрузить партию с ходами.
 */
export function useAnalysis(game: { id: string; pgn: string }, initial: AnalysisOut | null, onDone: () => void) {
  const { t } = useI18n();
  const gameId = game.id;
  const [state, setState] = useState<AnalysisState | null>(initial ? fromAnalysis(initial) : null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const browserRun = useRef<AbortController | null>(null);

  const trackedId = state && state.runner === "server" && isActive(state.status) ? state.id : null;

  useEffect(() => {
    if (!trackedId) return;
    let closed = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    let source: EventSource | null = null;

    const apply = (next: AnalysisState) => {
      if (closed) return;
      setState(next);
      if (!isActive(next.status)) {
        closed = true;
        source?.close();
        if (next.status === "done") onDone();
      }
    };

    const poll = async () => {
      try {
        apply(fromAnalysis(await api.analysis(trackedId)));
      } catch {
        // Сеть мигнула — попробуем на следующем шаге.
      }
      if (!closed) pollTimer = setTimeout(poll, POLL_MS);
    };

    const startPolling = () => {
      if (!closed && pollTimer === undefined) pollTimer = setTimeout(poll, 0);
    };

    // EventSource не умеет заголовки: сначала короткий токен потока, он идёт в query.
    api
      .analysisEventsUrl(trackedId)
      .then((url) => {
        if (closed) return;
        const stream = new EventSource(url);
        source = stream;
        stream.addEventListener("progress", (event) => {
          const data = JSON.parse((event as MessageEvent<string>).data) as ProgressEvent;
          apply({ id: trackedId, runner: "server", ...data });
        });
        stream.onerror = () => {
          // CONNECTING — браузер переподключится сам; CLOSED — поток недоступен (в том числе
          // токен истёк при переподключении), дальше полинг.
          if (stream.readyState === EventSource.CLOSED) startPolling();
        };
      })
      .catch(startPolling);

    return () => {
      closed = true;
      source?.close();
      clearTimeout(pollTimer);
    };
  }, [trackedId, onDone]);

  const startServer = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      const analysis = await api.analyze(gameId);
      setState(fromAnalysis(analysis));
      if (analysis.status === "done") onDone();
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : t.review.startFailed);
    } finally {
      setStarting(false);
    }
  }, [gameId, onDone, t]);

  const startBrowser = useCallback(async () => {
    if (browserRun.current) return;
    const controller = new AbortController();
    browserRun.current = controller;
    const { signal } = controller;
    const previous = state;
    setStarting(true);
    setStartError(null);
    let pool: StockfishPool | null = null;
    try {
      const config = await api.engineConfig();
      const { plies, startFen } = pliesFromPgn(game.pgn);
      const options = { depth: config.analysis_depth, multipv: config.analysis_multipv, signal };
      pool = await StockfishPool.create();
      setStarting(false);
      const running = { id: BROWSER_RUN, runner: "browser", status: "running", error: null, error_code: null } as const;
      setState({ ...running, done: 0, total: 0 });
      const positions = await analyseGame(pool, gamePositions(startFen, plies), {
        ...options,
        onProgress: (done, total) => setState({ ...running, done, total }),
      });
      const saved = await api.saveBrowserAnalysis(gameId, {
        depth: config.analysis_depth,
        engine: pool.name,
        positions,
      });
      setState(fromAnalysis(saved.analysis));
      onDone();
      // Пазлы — после показа разбора: вторые линии в позициях решений (обычно секунды).
      // Разбор уже сохранён, поэтому сбой здесь только без пазлов.
      if (saved.puzzle_probes.length > 0) {
        try {
          const answers = await answerProbes(pool, saved.puzzle_probes, options);
          await api.saveBrowserPuzzles(saved.analysis.id, answers);
        } catch (err) {
          console.warn("Пазлы из анализа в браузере не сохранены", err);
        }
      }
    } catch (err) {
      setState((current) => (current?.id === BROWSER_RUN ? previous : current));
      if (!signal.aborted) {
        setStartError(
          err instanceof ApiError
            ? err.message
            : err instanceof EngineLoadError
              ? t.review.browserEngineFailed
              : t.review.startFailed,
        );
      }
    } finally {
      pool?.terminate();
      browserRun.current = null;
      setStarting(false);
    }
  }, [game.pgn, gameId, onDone, state, t]);

  const start = useCallback(
    (source: EngineSource) => (source === "browser" ? startBrowser() : startServer()),
    [startBrowser, startServer],
  );
  const cancel = useCallback(() => browserRun.current?.abort(), []);

  return { state, start, cancel, starting, startError };
}
