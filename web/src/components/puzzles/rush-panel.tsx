"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { PuzzleFilters, RushRunResult, RushRuns, RushVariant } from "@/lib/types";
import { Button, ErrorText, Panel } from "../ui";
import { PuzzleSession } from "./puzzle-trainer";
import {
  afterAnswer,
  clock,
  filtersBody,
  MAX_MISTAKES,
  RUSH_LIMITS,
  RUSH_VARIANTS,
  runDuration,
  secondsLeft,
  type RushRun,
} from "./puzzle-view";

// После третьей ошибки забег кончается не сразу: виден неверный ход и верный стрелкой.
const END_AFTER_MISTAKE_MS = 1500;
const TICK_MS = 250;

type EndReason = "time" | "mistakes" | "exhausted" | "finished";

type Finished = {
  variant: RushVariant;
  run: RushRun;
  durationS: number;
  reason: EndReason;
  /** Результат сохранения: рекорд с сервера или ошибка. */
  saved: { state: "saving" } | { state: "ok"; result: RushRunResult } | { state: "error"; message: string | null };
};

type Screen = { kind: "setup" } | { kind: "run"; variant: RushVariant } | { kind: "done"; finished: Finished };

/** «На время»: выбор варианта → забег → итог с рекордом и «ещё раз». */
export function RushPanel({ filters, onRunning }: { filters: PuzzleFilters; onRunning: (running: boolean) => void }) {
  const [screen, setScreen] = useState<Screen>({ kind: "setup" });
  const [variant, setVariant] = useState<RushVariant>("3min");
  const [token, setToken] = useState(0);

  // Новый забег — новый экземпляр (`key`): счёт, таймер и список показанных пазлов с нуля.
  const running = screen.kind === "run";
  useEffect(() => {
    onRunning(running);
    return () => onRunning(false);
  }, [onRunning, running]);

  const start = useCallback((next: RushVariant) => {
    setVariant(next);
    setToken((n) => n + 1);
    setScreen({ kind: "run", variant: next });
  }, []);

  const finish = useCallback(
    (variantRun: RushVariant, run: RushRun, elapsedMs: number, reason: EndReason) => {
      const durationS = runDuration(variantRun, elapsedMs);
      setScreen({ kind: "done", finished: { variant: variantRun, run, durationS, reason, saved: { state: "saving" } } });
      api
        .saveRushRun({ variant: variantRun, score: run.score, mistakes: run.mistakes, duration_s: durationS, filters: filtersBody(filters) })
        .then((result) =>
          setScreen((prev) =>
            prev.kind === "done" ? { kind: "done", finished: { ...prev.finished, saved: { state: "ok", result } } } : prev,
          ),
        )
        .catch((err) =>
          setScreen((prev) =>
            prev.kind === "done"
              ? { kind: "done", finished: { ...prev.finished, saved: { state: "error", message: err instanceof ApiError ? err.message : null } } }
              : prev,
          ),
        );
    },
    [filters],
  );

  if (screen.kind === "run") {
    return <RushRunView key={token} variant={screen.variant} filters={filters} onEnd={finish} />;
  }
  if (screen.kind === "done") {
    return (
      <Summary
        finished={screen.finished}
        onAgain={() => start(screen.finished.variant)}
        onBack={() => {
          setVariant(screen.finished.variant);
          setScreen({ kind: "setup" });
        }}
      />
    );
  }
  return <Setup variant={variant} onVariant={setVariant} filters={filters} onStart={start} />;
}

function Setup({
  variant,
  onVariant,
  filters,
  onStart,
}: {
  variant: RushVariant;
  onVariant: (variant: RushVariant) => void;
  filters: PuzzleFilters;
  onStart: (variant: RushVariant) => void;
}) {
  const { t } = useI18n();
  const copy = t.puzzles.rush;
  const [runs, setRuns] = useState<Partial<Record<RushVariant, RushRuns>>>({});
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all(RUSH_VARIANTS.map((v) => api.rushRuns(v)))
      .then((all) => {
        if (cancelled) return;
        setRuns(Object.fromEntries(RUSH_VARIANTS.map((v, i) => [v, all[i]])));
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : copy.loadError));
    return () => {
      cancelled = true;
    };
  }, [copy.loadError]);

  // Сначала убедиться, что по фильтрам есть пазлы: иначе таймер пошёл бы по пустому экрану.
  const begin = () => {
    setStarting(true);
    setEmpty(false);
    api
      .nextPuzzle({ ...filters, mode: "rush" })
      .then((next) => (next.puzzle ? onStart(variant) : setEmpty(true)))
      .catch((err) => setError(err instanceof ApiError ? err.message : copy.loadError))
      .finally(() => setStarting(false));
  };

  const recent = runs[variant]?.recent ?? [];
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Panel>
        <div role="radiogroup" aria-label={t.puzzles.tabs.rush} className="grid gap-2 sm:grid-cols-3">
          {RUSH_VARIANTS.map((v) => {
            const best = runs[v]?.best;
            const active = v === variant;
            return (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => onVariant(v)}
                className={`flex flex-col gap-1 rounded-lg px-4 py-3 text-left ${
                  active ? "bg-raised ring-2 ring-green ring-inset" : "bg-raised/60 hover:bg-raised"
                }`}
              >
                <span className="text-lg font-extrabold">{copy.variants[v].title}</span>
                <span className="text-sm text-soft">{copy.variants[v].text}</span>
                <span className="mt-1 text-sm font-bold text-green">
                  {best === undefined ? "…" : best === null ? <span className="text-muted">{copy.noBest}</span> : copy.best(best)}
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-3 text-sm text-muted">{copy.mistakesNote}</p>
        <div className="mt-4 flex flex-col gap-2">
          <Button size="lg" onClick={begin} disabled={starting}>
            {copy.start}
          </Button>
          <ErrorText>{error}</ErrorText>
          {empty && (
            <p role="alert" className="text-sm font-medium text-danger">
              {copy.noPuzzlesTitle}. {copy.noPuzzlesText}
            </p>
          )}
        </div>
      </Panel>

      {recent.length > 0 && (
        <Panel title={copy.recent}>
          <ul className="flex flex-col divide-y divide-line">
            {recent.map((run) => (
              <li key={run.id} className="py-2 text-sm text-soft">
                <span className="font-semibold text-ink">{copy.recentRow(run.score, run.mistakes, clock(run.duration_s))}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function RushRunView({
  variant,
  filters,
  onEnd,
}: {
  variant: RushVariant;
  filters: PuzzleFilters;
  onEnd: (variant: RushVariant, run: RushRun, elapsedMs: number, reason: EndReason) => void;
}) {
  const { t } = useI18n();
  const copy = t.puzzles.rush;
  const [run, setRun] = useState<RushRun>({ score: 0, mistakes: 0 });
  const runRef = useRef(run);
  const [elapsedMs, setElapsedMs] = useState(0);
  const startedAt = useRef<number | null>(null);
  const ended = useRef(false);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);

  const end = useCallback(
    (reason: EndReason) => {
      if (ended.current) return;
      ended.current = true;
      onEnd(variant, runRef.current, Date.now() - (startedAt.current ?? Date.now()), reason);
    },
    [onEnd, variant],
  );

  useEffect(() => {
    startedAt.current = Date.now();
    window.scrollTo(0, 0);
    const timer = setInterval(() => {
      const elapsed = Date.now() - (startedAt.current ?? Date.now());
      setElapsedMs(elapsed);
      if (secondsLeft(variant, elapsed) === 0) end("time");
    }, TICK_MS);
    return () => {
      clearInterval(timer);
      if (pending.current) clearTimeout(pending.current);
    };
  }, [end, variant]);

  const onResult = useCallback(
    (solved: boolean) => {
      if (ended.current) return;
      const step = afterAnswer(runRef.current, solved);
      runRef.current = step.run;
      setRun(step.run);
      if (step.over) pending.current = setTimeout(() => end("mistakes"), solved ? 0 : END_AFTER_MISTAKE_MS);
    },
    [end],
  );
  const onExhausted = useCallback(() => end("exhausted"), [end]);

  const left = secondsLeft(variant, elapsedMs);
  const low = left !== null && left <= 10;
  const hud = (
    <div className="flex items-center gap-3">
      <div className="min-w-0">
        <p className="text-xs font-semibold text-muted">{left === null ? copy.elapsed : copy.timeLeft}</p>
        <p
          role="timer"
          aria-label={`${left === null ? copy.elapsed : copy.timeLeft}: ${clock(left ?? elapsedMs / 1000)}`}
          className={`text-2xl font-extrabold tabular-nums ${low ? "text-danger" : ""}`}
        >
          {clock(left ?? elapsedMs / 1000)}
        </p>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <div className="text-right">
          <p className="text-xs font-semibold text-muted">{copy.score}</p>
          <p className="text-2xl font-extrabold tabular-nums">{run.score}</p>
        </div>
        <div role="img" aria-label={copy.mistakesLabel(run.mistakes)} className="flex gap-1">
          {Array.from({ length: MAX_MISTAKES }, (_, i) => (
            <Cross key={i} used={i < run.mistakes} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      {/* На телефоне панель с доской лежит под доской, а таймер нужен перед глазами: он над доской. */}
      <div className="rounded-xl bg-panel px-4 py-2 lg:hidden">{hud}</div>
      <PuzzleSession mode="rush" filters={filters} rush={{ onResult, onExhausted }} hud={<div className="max-lg:hidden">{hud}</div>} />
      <div className="flex justify-center">
        <button type="button" onClick={() => end("finished")} className="min-h-10 px-3 text-sm font-bold text-soft hover:text-ink">
          {copy.finish}
        </button>
      </div>
    </div>
  );
}

function Cross({ used }: { used: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex h-8 w-8 items-center justify-center rounded-md ${used ? "bg-danger/90 text-white" : "bg-sunken text-muted"}`}
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round">
        <path d="m6 6 12 12M18 6 6 18" />
      </svg>
    </span>
  );
}

function Summary({ finished, onAgain, onBack }: { finished: Finished; onAgain: () => void; onBack: () => void }) {
  const { t } = useI18n();
  const copy = t.puzzles.rush;
  const { run, saved, reason } = finished;
  const reasonText = {
    time: copy.summary.timeUp,
    mistakes: copy.summary.threeMistakes,
    exhausted: copy.summary.exhausted,
    finished: copy.summary.finished,
  }[reason];
  const limit = RUSH_LIMITS[finished.variant];
  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center gap-3 rounded-xl bg-panel px-6 py-8 text-center">
      <p className="text-sm font-bold uppercase tracking-wide text-muted">
        {copy.summary.title} · {reasonText}
      </p>
      <p className="text-6xl font-extrabold tabular-nums" aria-live="polite">
        {run.score}
      </p>
      <p className="text-soft">{copy.summary.solved(run.score)}</p>
      <p className="text-sm text-muted">
        {copy.mistakesLabel(run.mistakes)} · {clock(finished.durationS)}
        {limit !== null && ` / ${clock(limit)}`}
      </p>
      <div role="status" className="min-h-7">
        {saved.state === "saving" && <span className="text-sm text-muted">{copy.summary.saving}</span>}
        {saved.state === "ok" && (
          <span className={`inline-block rounded-lg px-3 py-1 text-base font-extrabold ${saved.result.is_best ? "bg-green text-white" : "bg-raised text-soft"}`}>
            {saved.result.is_best ? `${copy.summary.newBest} ${saved.result.best}` : copy.summary.best(saved.result.best)}
          </span>
        )}
        {saved.state === "error" && <ErrorText>{saved.message ?? copy.summary.saveError}</ErrorText>}
      </div>
      <div className="mt-2 grid w-full grid-cols-2 gap-2">
        <Button variant="raised" onClick={onBack}>
          {copy.summary.back}
        </Button>
        <Button onClick={onAgain}>{copy.summary.again}</Button>
      </div>
    </div>
  );
}
