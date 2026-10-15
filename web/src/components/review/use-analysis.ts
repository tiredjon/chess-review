"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AnalysisOut, JobStatus, ProgressEvent } from "@/lib/types";

export type AnalysisState = {
  id: string;
  status: JobStatus;
  done: number;
  total: number;
  error: string | null;
};

const POLL_MS = 2000;
const isActive = (status: JobStatus) => status === "queued" || status === "running";

function fromAnalysis(analysis: AnalysisOut): AnalysisState {
  return {
    id: analysis.id,
    status: analysis.status,
    done: analysis.progress?.done ?? 0,
    total: analysis.progress?.total ?? 0,
    error: analysis.error,
  };
}

/**
 * Запуск анализа и прогресс по SSE (`GET /analyses/{id}/events`). Если поток
 * недоступен — полинг `GET /analyses/{id}`. `onDone` — перезагрузить партию с ходами.
 */
export function useAnalysis(gameId: string, initial: AnalysisOut | null, onDone: () => void) {
  const [state, setState] = useState<AnalysisState | null>(initial ? fromAnalysis(initial) : null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const trackedId = state && isActive(state.status) ? state.id : null;

  useEffect(() => {
    if (!trackedId) return;
    let closed = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    const apply = (next: AnalysisState) => {
      if (closed) return;
      setState(next);
      if (!isActive(next.status)) {
        closed = true;
        source.close();
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

    const source = new EventSource(api.analysisEventsUrl(trackedId));
    source.addEventListener("progress", (event) => {
      const data = JSON.parse((event as MessageEvent<string>).data) as ProgressEvent;
      apply({ id: trackedId, ...data });
    });
    source.onerror = () => {
      // CONNECTING — браузер переподключится сам; CLOSED — поток недоступен, полинг.
      if (source.readyState === EventSource.CLOSED && !closed && pollTimer === undefined) {
        pollTimer = setTimeout(poll, 0);
      }
    };

    return () => {
      closed = true;
      source.close();
      clearTimeout(pollTimer);
    };
  }, [trackedId, onDone]);

  const start = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      const analysis = await api.analyze(gameId);
      setState(fromAnalysis(analysis));
      if (analysis.status === "done") onDone();
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Не удалось запустить анализ");
    } finally {
      setStarting(false);
    }
  }, [gameId, onDone]);

  return { state, start, starting, startError };
}
