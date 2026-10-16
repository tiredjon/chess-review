// Где считать: на сервере (воркер / пул API) или движком в браузере. Выбор запоминается
// в localStorage — это удобство одного браузера, без него всё работает со значениями по умолчанию.
import { useCallback, useSyncExternalStore } from "react";
import { engineSupported } from "./stockfish";

export type EngineSource = "browser" | "server";

function createPreference(key: string, fallback: () => EngineSource) {
  const listeners = new Set<() => void>();
  let cached: EngineSource | null = null;

  const get = (): EngineSource => {
    if (cached !== null) return cached;
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(key);
    } catch {
      // Приватный режим / запрет хранилища — значение по умолчанию.
    }
    cached = (stored === "browser" || stored === "server") && (stored === "server" || engineSupported())
      ? stored
      : fallback();
    return cached;
  };

  const set = (value: EngineSource) => {
    cached = value;
    try {
      localStorage.setItem(key, value);
    } catch {
      // см. выше
    }
    listeners.forEach((listener) => listener());
  };

  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };

  return function usePreference(): [EngineSource, (value: EngineSource) => void] {
    const value = useSyncExternalStore(subscribe, get, () => "server" as EngineSource);
    return [value, useCallback(set, [])];
  };
}

/** Анализ партии: по умолчанию на сервере (сильнее движок, браузер не занят). */
export const useAnalysisSource = createPreference("cr.analysis-engine", () => "server");

/** Режим исследования: по умолчанию в браузере (мгновенно, без лимитов), если он умеет WASM. */
export const useExploreSource = createPreference("cr.explore-engine", () =>
  engineSupported() ? "browser" : "server",
);
