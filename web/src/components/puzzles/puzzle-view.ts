// Экран пазлов (сессия 16.2): чистая логика без React, чтобы её исполнял Node напрямую
// (≥ 23 — .ts без компиляции; `import type` стирается, алиас `@/` не нужен).
//
//   Тесты: cd web && node --test src/components/puzzles/puzzle-view.test.mjs

import type { Phase, PuzzleFilters, PuzzleMode, RushVariant } from "@/lib/types";

export type PuzzleView = { mode: PuzzleMode; filters: PuzzleFilters };

export const NO_FILTERS: PuzzleFilters = { theme: null, phase: null, eco: null };

export const hasFilters = (filters: PuzzleFilters) => Boolean(filters.theme || filters.phase || filters.eco);

export const PHASES: Phase[] = ["opening", "middlegame", "endgame"];
export const RUSH_VARIANTS: RushVariant[] = ["3min", "5min", "survival"];
export const MAX_MISTAKES = 3;
/** Лимит времени в секундах; null — «на выживание», без времени. */
export const RUSH_LIMITS: Record<RushVariant, number | null> = { "3min": 180, "5min": 300, survival: null };

// Как на сервере (`PuzzleTheme`, `PuzzleEco`): чужое значение из URL отбрасывается, а не уходит в API.
const THEME = /^[a-z][a-z0-9_]{0,31}$/;
const ECO = /^[A-Za-z0-9]{1,8}$/;

type Query = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

/** Режим и фильтры из `?mode=&theme=&phase=&eco=`; неизвестное — по умолчанию (`srs`, без фильтра). */
export function parseView(query: Query): PuzzleView {
  const mode = first(query.mode);
  const theme = first(query.theme);
  const phase = first(query.phase);
  const eco = first(query.eco);
  return {
    mode: mode === "practice" || mode === "rush" ? mode : "srs",
    filters: {
      theme: theme && THEME.test(theme) ? theme : null,
      phase: PHASES.find((p) => p === phase) ?? null,
      eco: eco && ECO.test(eco) ? eco.toUpperCase() : null,
    },
  };
}

/** Адрес экрана: `/puzzles?mode=practice&theme=fork` (режим повторения без `mode`). */
export function viewHref({ mode, filters }: PuzzleView): string {
  const query = new URLSearchParams();
  if (mode !== "srs") query.set("mode", mode);
  if (filters.theme) query.set("theme", filters.theme);
  if (filters.phase) query.set("phase", filters.phase);
  if (filters.eco) query.set("eco", filters.eco);
  const qs = query.toString();
  return qs ? `/puzzles?${qs}` : "/puzzles";
}

/** Ключ экземпляра: смена режима или фильтров — новая сессия пазлов. */
export const viewKey = (view: PuzzleView) => viewHref(view);

export type RushRun = { score: number; mistakes: number };

/** Итог ответа на пазл: счёт или ошибка; три ошибки — конец забега. */
export function afterAnswer(run: RushRun, solved: boolean): { run: RushRun; over: boolean } {
  const next = solved ? { ...run, score: run.score + 1 } : { ...run, mistakes: run.mistakes + 1 };
  return { run: next, over: next.mistakes >= MAX_MISTAKES };
}

/** Сколько секунд осталось (не меньше нуля); null — у забега без времени. */
export function secondsLeft(variant: RushVariant, elapsedMs: number): number | null {
  const limit = RUSH_LIMITS[variant];
  return limit === null ? null : Math.max(0, Math.ceil(limit - elapsedMs / 1000));
}

/** Длительность забега для сервера: целые секунды, у забега на время — не больше лимита. */
export function runDuration(variant: RushVariant, elapsedMs: number): number {
  const seconds = Math.max(0, Math.round(elapsedMs / 1000));
  const limit = RUSH_LIMITS[variant];
  return limit === null ? seconds : Math.min(seconds, limit);
}

/** `2:05`. */
export function clock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Фильтры для тела `POST /puzzles/rush`: только заданные. */
export function filtersBody(filters: PuzzleFilters): Partial<{ theme: string; phase: Phase; eco: string }> {
  const body: Partial<{ theme: string; phase: Phase; eco: string }> = {};
  if (filters.theme) body.theme = filters.theme;
  if (filters.phase) body.phase = filters.phase;
  if (filters.eco) body.eco = filters.eco;
  return body;
}
