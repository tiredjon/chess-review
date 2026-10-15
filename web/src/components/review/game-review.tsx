"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { pliesFromMoves, pliesFromPgn, START_FEN } from "@/lib/chess";
import {
  formatDate,
  formatResult,
  formatTimeControl,
  outcome,
  OUTCOME_LABELS,
  playerElo,
  playerName,
  SOURCE_NAMES,
} from "@/lib/format";
import type { Color, GameDetail } from "@/lib/types";
import { PlayerAvatar } from "../player-avatar";
import { Button, ErrorText } from "../ui";
import { Overview } from "./overview";
import { Review } from "./review";
import { CoachBubble, GameSummary } from "./summary";
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
          err instanceof ApiError
            ? { status: err.status, message: err.message }
            : { status: 0, message: "Не удалось загрузить партию" },
        ),
      );
  }, [id]);

  useEffect(reload, [reload]);

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 py-10">
        <p className="text-xl font-extrabold">
          {error.status === 404 ? "Партия не найдена" : "Не удалось открыть партию"}
        </p>
        <ErrorText>{error.status === 404 ? null : error.message}</ErrorText>
        <Link href="/games" className="font-bold text-green hover:underline">
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

  // `?analyze=1` (из списков и после вставки PGN): запустить анализ один раз и убрать параметр.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!autoAnalyze || autoStarted.current) return;
    autoStarted.current = true;
    if (!game.analysis || game.analysis.status === "failed") void start();
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

  const result = outcome(game);
  const subtitle = [
    `${formatResult(game.result)}${result ? ` (${OUTCOME_LABELS[result].toLowerCase()})` : ""}`,
    game.opening_name,
    formatTimeControl(game.time_control),
    formatDate(game.played_at),
    SOURCE_NAMES[game.source],
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <h1 className="sr-only">
        {game.white} – {game.black}, {formatResult(game.result)}
      </h1>
      <Review
        plies={plies}
        startFen={plies.length > 0 ? startFen : START_FEN}
        initialOrientation={game.user_color ?? "white"}
        player={(color) => <PlayerBar game={game} color={color} />}
        subtitle={subtitle}
        status={<AnalysisStatus state={state} starting={starting} error={startError} onStart={start} />}
        overview={
          analysis && (
            <>
              <GameSummary analysisId={analysis.id} />
              <Overview game={game} analysis={analysis} />
            </>
          )
        }
      />
    </>
  );
}

function PlayerBar({ game, color }: { game: GameDetail; color: Color }) {
  const name = playerName(game, color);
  const elo = playerElo(game, color);
  const accuracy = color === "white" ? game.analysis?.white_accuracy : game.analysis?.black_accuracy;
  return (
    <div className="flex min-h-10 items-center gap-2.5">
      <PlayerAvatar name={name} color={color} size={36} />
      <p className="min-w-0 flex-1 truncate text-[15px]">
        <span className="font-bold">{name}</span>
        {elo && <span className="ml-1.5 font-semibold text-muted">({elo})</span>}
      </p>
      {game.analysis?.status === "done" && accuracy != null && (
        <span
          title="Точность"
          className={`rounded-md px-2.5 py-1 text-sm font-extrabold ${
            color === "white" ? "bg-white text-[#2c2925]" : "bg-sunken text-ink"
          }`}
        >
          {accuracy.toFixed(1)}
        </span>
      )}
    </div>
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
      <div aria-live="polite" className="flex flex-col gap-3">
        <CoachBubble>
          {state.status === "queued"
            ? "Партия в очереди на анализ. Ходы уже можно листать."
            : "Stockfish разбирает партию. Обычно это занимает до минуты."}
        </CoachBubble>
        <div className="flex items-center gap-3">
          <div
            role="progressbar"
            aria-label="Прогресс анализа"
            aria-valuemin={0}
            aria-valuemax={state.total || 1}
            aria-valuenow={state.done}
            className="h-3 flex-1 overflow-hidden rounded-full bg-sunken"
          >
            <div
              className={`h-full rounded-full bg-green transition-[width] duration-500 ${
                state.total === 0 ? "w-1/5 animate-pulse" : ""
              }`}
              style={state.total > 0 ? { width: `${percent}%` } : undefined}
            />
          </div>
          <span className="w-24 text-right text-sm font-bold text-soft">
            {state.total > 0 ? `${state.done} из ${state.total}` : "…"}
          </span>
        </div>
      </div>
    );
  }
  const failed = state?.status === "failed";
  return (
    <div className="flex flex-col gap-3">
      <CoachBubble>
        {failed
          ? `Анализ не удался: ${state.error ?? "неизвестная ошибка"}`
          : "Партия ещё не разобрана. Stockfish оценит каждый ход, найдёт ошибки и упущенную тактику."}
      </CoachBubble>
      <ErrorText>{error}</ErrorText>
      <Button size="lg" onClick={onStart} disabled={starting}>
        {starting ? "Запускаю…" : failed ? "Запустить заново" : "Запустить анализ"}
      </Button>
    </div>
  );
}

export function ReviewSkeleton() {
  return (
    <div aria-busy className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="mx-auto aspect-square w-full max-w-[min(100%,calc(100dvh-8.5rem))] animate-pulse rounded bg-raised/50" />
      <div className="h-96 animate-pulse rounded-xl bg-panel" />
    </div>
  );
}
