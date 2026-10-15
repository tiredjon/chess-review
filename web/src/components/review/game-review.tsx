"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { pliesFromMoves, pliesFromPgn, START_FEN } from "@/lib/chess";
import { formatDate, formatResult, formatTimeControl, outcome, OUTCOME_LABELS, SOURCE_NAMES } from "@/lib/format";
import type { Color, GameDetail } from "@/lib/types";
import { Button, ErrorText } from "../ui";
import { PlayerCard } from "./player-card";
import { Review } from "./review";
import { GameSummary } from "./summary";
import { useAnalysis, type AnalysisState } from "./use-analysis";

/** Экран разбора: загрузка партии, запуск анализа с прогрессом, сам разбор. */
export function GameReview({ id, autoAnalyze }: { id: string; autoAnalyze: boolean }) {
  const [game, setGame] = useState<GameDetail | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  const reload = useCallback(() => {
    api
      .game(id)
      .then(setGame)
      .catch((err) =>
        setError(
          err instanceof ApiError ? { status: err.status, message: err.message } : { status: 0, message: "Не удалось загрузить партию" },
        ),
      );
  }, [id]);

  useEffect(reload, [reload]);

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 py-10">
        <p className="text-xl font-semibold">{error.status === 404 ? "Партия не найдена" : "Не удалось открыть партию"}</p>
        <ErrorText>{error.status === 404 ? null : error.message}</ErrorText>
        <Link href="/games" className="font-medium text-accent hover:underline">
          К списку партий
        </Link>
      </div>
    );
  }
  if (!game) return <ReviewSkeleton />;
  return <LoadedGame game={game} autoAnalyze={autoAnalyze} onAnalysisDone={reload} />;
}

function LoadedGame({
  game,
  autoAnalyze,
  onAnalysisDone,
}: {
  game: GameDetail;
  autoAnalyze: boolean;
  onAnalysisDone: () => void;
}) {
  const router = useRouter();
  const { state, start, starting, startError } = useAnalysis(game.id, game.analysis, onAnalysisDone);

  // `?analyze=1` (после вставки PGN): запустить анализ один раз и убрать параметр из адреса.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!autoAnalyze || autoStarted.current) return;
    autoStarted.current = true;
    if (!game.analysis) void start();
    router.replace(`/games/${game.id}`, { scroll: false });
  }, [autoAnalyze, game.analysis, game.id, router, start]);

  const analysis = game.analysis?.status === "done" ? game.analysis : null;
  const { plies, startFen } = useMemo(
    () =>
      analysis && analysis.moves.length > 0
        ? { plies: pliesFromMoves(analysis.moves), startFen: analysis.moves[0].fen_before }
        : pliesFromPgn(game.pgn),
    [analysis, game.pgn],
  );

  const strip = (color: Color) => <PlayerStrip game={game} color={color} />;
  const opposite = (color: Color): Color => (color === "white" ? "black" : "white");

  return (
    <div className="flex flex-col gap-5">
      <GameHeader game={game} />
      <Review
        plies={plies}
        startFen={plies.length > 0 ? startFen : START_FEN}
        initialOrientation={game.user_color ?? "white"}
        topPlayer={(orientation) => strip(opposite(orientation))}
        bottomPlayer={(orientation) => strip(orientation)}
        sidePanel={
          analysis ? null : <AnalysisStatus state={state} starting={starting} error={startError} onStart={start} />
        }
        aside={
          analysis && (
            <div className="grid gap-3 sm:grid-cols-2">
              {(["white", "black"] as const).map((color) => (
                <PlayerCard
                  key={color}
                  name={color === "white" ? game.white : game.black}
                  elo={color === "white" ? game.white_elo : game.black_elo}
                  color={color}
                  isUser={game.user_color === color}
                  accuracy={color === "white" ? analysis.white_accuracy : analysis.black_accuracy}
                  phases={analysis.phase_accuracy}
                  moves={analysis.moves}
                />
              ))}
              <div className="sm:col-span-2">
                <GameSummary analysisId={analysis.id} />
              </div>
            </div>
          )
        }
      />
    </div>
  );
}

function GameHeader({ game }: { game: GameDetail }) {
  const result = outcome(game);
  const details = [
    game.opening_name && `${game.opening_eco ? `${game.opening_eco} ` : ""}${game.opening_name}`,
    formatTimeControl(game.time_control),
    formatDate(game.played_at),
    SOURCE_NAMES[game.source],
  ].filter(Boolean);
  return (
    <div className="flex flex-col gap-1">
      <Link href="/games" className="text-sm text-muted hover:text-ink">
        ← Все партии
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">
        {game.white} – {game.black}
        <span className="ml-3 whitespace-nowrap text-muted">{formatResult(game.result)}</span>
        {result && <span className="ml-3 text-base font-medium text-muted">{OUTCOME_LABELS[result]}</span>}
      </h1>
      <p className="text-sm text-muted">{details.join(", ")}</p>
    </div>
  );
}

function PlayerStrip({ game, color }: { game: GameDetail; color: Color }) {
  const name = color === "white" ? game.white : game.black;
  const elo = color === "white" ? game.white_elo : game.black_elo;
  return (
    <p className="flex items-center gap-2 text-sm">
      <span
        aria-hidden
        className={`h-3 w-3 rounded-sm border border-muted/50 ${color === "white" ? "bg-white" : "bg-[#2a3240]"}`}
      />
      <span className={game.user_color === color ? "font-semibold" : "font-medium"}>{name}</span>
      {elo && <span className="text-muted">{elo}</span>}
    </p>
  );
}

function AnalysisStatus({
  state,
  starting,
  error,
  onStart,
}: {
  state: AnalysisState | null;
  starting: boolean;
  error: string | null;
  onStart: () => void;
}) {
  if (state && (state.status === "queued" || state.status === "running")) {
    const percent = state.total > 0 ? Math.round((state.done / state.total) * 100) : 0;
    return (
      <section aria-live="polite" className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="font-semibold">{state.status === "queued" ? "Анализ в очереди" : "Stockfish анализирует партию"}</p>
          {state.total > 0 && <span className="text-sm text-muted">{percent}%</span>}
        </div>
        <div
          role="progressbar"
          aria-label="Прогресс анализа"
          aria-valuemin={0}
          aria-valuemax={state.total || 1}
          aria-valuenow={state.done}
          className="h-2 overflow-hidden rounded-full bg-sunken"
        >
          <div
            className={`h-full rounded-full bg-accent transition-[width] duration-500 ${state.total === 0 ? "w-1/5 animate-pulse" : ""}`}
            style={state.total > 0 ? { width: `${percent}%` } : undefined}
          />
        </div>
        <p className="text-sm text-muted">
          {state.total > 0
            ? `Позиций: ${state.done} из ${state.total}. Обычно это занимает до минуты.`
            : "Ходы партии уже можно листать."}
        </p>
      </section>
    );
  }
  const failed = state?.status === "failed";
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
      <p className="font-semibold">{failed ? "Анализ не удался" : "Партия ещё не разобрана"}</p>
      {failed ? (
        <ErrorText>{state.error ?? "Неизвестная ошибка"}</ErrorText>
      ) : (
        <p className="text-sm text-muted">Stockfish оценит каждый ход, найдёт ошибки и упущенную тактику.</p>
      )}
      <ErrorText>{error}</ErrorText>
      <div>
        <Button onClick={onStart} disabled={starting}>
          {starting ? "Запускаю…" : failed ? "Запустить заново" : "Запустить анализ"}
        </Button>
      </div>
    </section>
  );
}

export function ReviewSkeleton() {
  return (
    <div aria-busy className="flex flex-col gap-5">
      <div className="h-8 w-72 animate-pulse rounded bg-sunken" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="mx-auto aspect-square w-full max-w-[min(100%,calc(100dvh-16rem))] animate-pulse rounded-md bg-sunken" />
        <div className="h-64 animate-pulse rounded-lg bg-sunken" />
      </div>
    </div>
  );
}
