"use client";

import { type CSSProperties, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { PuzzleFilters, PuzzleMode, PuzzleThemes } from "@/lib/types";
import { ErrorText } from "../ui";
import { ActiveFilters, FilterBar } from "./filter-bar";
import { PuzzleSession } from "./puzzle-trainer";
import { RushPanel } from "./rush-panel";
import { type PuzzleView, viewHref } from "./puzzle-view";

const MODES: PuzzleMode[] = ["srs", "practice", "rush"];

/** `/puzzles`: вкладки «Повторение» / «По темам» / «На время». Режим и фильтры — в URL
 * (`?mode=&theme=&phase=&eco=`): читаются на сервере страницы, пишутся через `history.replaceState`,
 * чтобы выбор фильтра не перезагружал страницу. Смена вида — новая сессия пазлов. */
export function PuzzlesScreen({ initial }: { initial: PuzzleView }) {
  const { t } = useI18n();
  const [view, setView] = useState(initial);
  const [themes, setThemes] = useState<PuzzleThemes | null>(null);
  const [themesError, setThemesError] = useState<string | null>(null);
  // Идёт забег: фильтры скрыты, на доску больше места.
  const [running, setRunning] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .puzzleThemes()
      .then((data) => !cancelled && setThemes(data))
      .catch((err) => !cancelled && setThemesError(err instanceof ApiError ? err.message : t.puzzles.filters.loadError));
    return () => {
      cancelled = true;
    };
  }, [t.puzzles.filters.loadError]);

  const change = useCallback((next: PuzzleView) => {
    setView(next);
    window.history.replaceState(null, "", viewHref(next));
  }, []);
  // Что над доской: вкладки (+ фильтры в «По темам» / «На время», + «Завершить» в забеге).
  const chrome = running ? "12rem" : view.mode === "srs" ? "9.5rem" : "21rem";
  const setFilters = (filters: PuzzleFilters) => change({ ...view, filters });

  return (
    <div className="flex flex-col gap-3" style={{ "--puzzle-chrome": chrome } as CSSProperties}>
      <div role="tablist" aria-label={t.puzzles.tabs.label} className="grid grid-cols-3 gap-1 rounded-xl bg-panel p-1 sm:max-w-md">
        {MODES.map((mode) => (
          <button
            key={mode}
            type="button"
            role="tab"
            id={`puzzles-tab-${mode}`}
            aria-selected={view.mode === mode}
            aria-controls="puzzles-view"
            onClick={() => view.mode !== mode && change({ ...view, mode })}
            className={`min-h-11 rounded-lg px-2 text-sm font-bold sm:text-[15px] ${
              view.mode === mode ? "bg-raised text-ink shadow-[0_2px_0_0_rgba(0,0,0,0.3)]" : "text-soft hover:bg-raised/60 hover:text-ink"
            }`}
          >
            {t.puzzles.tabs[mode]}
          </button>
        ))}
      </div>

      {view.mode !== "srs" && !running ? <FilterBar filters={view.filters} themes={themes} onChange={setFilters} /> : null}
      {view.mode === "srs" ? <ActiveFilters filters={view.filters} onChange={setFilters} /> : null}
      <ErrorText>{themesError}</ErrorText>

      <div role="tabpanel" id="puzzles-view" aria-labelledby={`puzzles-tab-${view.mode}`}>
        {view.mode === "rush" ? (
          <RushPanel key={JSON.stringify(view.filters)} filters={view.filters} onRunning={setRunning} />
        ) : (
          <PuzzleSession key={`${view.mode}${JSON.stringify(view.filters)}`} mode={view.mode} filters={view.filters} />
        )}
      </div>
    </div>
  );
}
