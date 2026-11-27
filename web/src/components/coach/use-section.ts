"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

export type Section<T> = {
  data: T | null;
  error: string | null;
  /** Код ошибки сервера (`coach_goal_not_found` и т. д.). */
  code: string | null;
  loading: boolean;
  reload: () => void;
  setData: (data: T) => void;
};

/** Загрузка одного блока экрана: свои ошибка и перезагрузка, чтобы блок не ронял остальные. */
export function useSection<T>(load: () => Promise<T>, fallbackError: string, enabled = true): Section<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; code: string | null; loading: boolean }>({
    data: null,
    error: null,
    code: null,
    loading: true,
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    load()
      .then((data) => !cancelled && setState({ data, error: null, code: null, loading: false }))
      .catch((err) => {
        if (cancelled) return;
        const failed = err instanceof ApiError;
        setState((prev) => ({ data: prev.data, error: failed ? err.message : fallbackError, code: failed ? err.code : null, loading: false }));
      });
    return () => {
      cancelled = true;
    };
    // `load` — стабильная ссылка на метод клиента; перезапуск только по nonce / enabled.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, enabled]);

  const reload = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true }));
    setNonce((n) => n + 1);
  }, []);
  const setData = useCallback((data: T) => setState({ data, error: null, code: null, loading: false }), []);
  return { ...state, reload, setData };
}
