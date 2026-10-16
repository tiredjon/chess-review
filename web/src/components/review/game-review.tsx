"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { shownAccuracy } from "@/lib/accuracy";
import { api, ApiError, codeText } from "@/lib/api";
import { pliesFromMoves, pliesFromPgn, START_FEN } from "@/lib/chess";
import {
  formatDate,
  formatResult,
  formatTimeControl,
  outcome,
  playerElo,
  playerName,
  SOURCE_NAMES,
} from "@/lib/format";
import { useAnalysisSource, type EngineSource } from "@/lib/engine/preference";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Color, GameDetail } from "@/lib/types";
import { PlayerAvatar } from "../player-avatar";
import { Button, ErrorText } from "../ui";
import { EngineSourceSwitch } from "./move-panel";
import { Overview } from "./overview";
import { ShareButton } from "./share-button";
import { Review } from "./review";
import { CoachBubble, GameSummary } from "./summary";
import { useAnalysis, type AnalysisState } from "./use-analysis";

/** Экран разбора: загрузка партии, запуск анализа с прогрессом, сам разбор. */
export function GameReview({ id, autoAnalyze, initialPly = 0 }: { id: string; autoAnalyze: boolean; initialPly?: number }) {
  const { t } = useI18n();
  const [game, setGame] = useState<GameDetail | null>(null);
  // `message: null` — сеть/неизвестная ошибка: текст по текущему языку при показе.
  const [error, setError] = useState<{ status: number; message: string | null } | null>(null);

  const reload = useCallback(() => {
    api
      .game(id)
      .then(setGame)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? { status: err.status, message: err.message }
            : { status: 0, message: null },
        ),
      );
  }, [id]);

  useEffect(reload, [reload]);

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 py-10">
        <p className="text-xl font-extrabold">
          {error.status === 404 ? t.review.notFound : t.review.openFailed}
        </p>
        <ErrorText>{error.status === 404 ? null : (error.message ?? t.review.loadFailed)}</ErrorText>
        <Link href="/games" className="font-bold text-green hover:underline">
          {t.review.toGames}
        </Link>
      </div>
    );
  }
  if (!game) return <ReviewSkeleton />;
  return <LoadedGame game={game} autoAnalyze={autoAnalyze} initialPly={initialPly} onAnalysisDone={reload} />;
}

function LoadedGame({
  game,
  autoAnalyze,
  initialPly,
  onAnalysisDone,
}: {
  game: GameDetail;
  autoAnalyze: boolean;
  initialPly: number;
  onAnalysisDone: () => void;
}) {
  const router = useRouter();
  const { state, start, cancel, starting, startError } = useAnalysis(game, game.analysis, onAnalysisDone);
  const [source, setSource] = useAnalysisSource();

  // `?analyze=1` (из списков и после вставки PGN): запустить анализ один раз и убрать параметр.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!autoAnalyze || autoStarted.current) return;
    autoStarted.current = true;
    if (!game.analysis || game.analysis.status === "failed") void start(source);
    router.replace(`/games/${game.id}`, { scroll: false });
  }, [autoAnalyze, game.analysis, game.id, router, source, start]);

  const analysis = game.analysis?.status === "done" ? game.analysis : null;
  const { plies, startFen } = useMemo(
    () =>
      analysis && analysis.moves.length > 0
        ? { plies: pliesFromMoves(analysis.moves), startFen: analysis.moves[0].fen_before }
        : pliesFromPgn(game.pgn),
    [analysis, game.pgn],
  );

  const subtitle = useGameSubtitle(game);

  return (
    <>
      <h1 className="sr-only">
        {game.white} – {game.black}, {formatResult(game.result)}
      </h1>
      <Review
        plies={plies}
        startFen={plies.length > 0 ? startFen : START_FEN}
        initialCursor={Math.min(initialPly, plies.length)}
        initialOrientation={game.user_color ?? "white"}
        player={(color) => <PlayerBar game={game} color={color} />}
        subtitle={subtitle}
        actions={<ShareButton gameId={game.id} />}
        status={
          <AnalysisStatus
            state={state}
            starting={starting}
            error={startError}
            source={source}
            onSource={setSource}
            onStart={() => void start(source)}
            onCancel={cancel}
          />
        }
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

/** Подзаголовок панели: результат, дебют, контроль, дата, площадка. */
export function useGameSubtitle(game: GameDetail): string {
  const { t, lang } = useI18n();
  const result = outcome(game);
  return [
    `${formatResult(game.result)}${result ? ` (${t.common.outcome[result].toLowerCase()})` : ""}`,
    game.opening_name,
    formatTimeControl(game.time_control, t),
    formatDate(game.played_at, lang),
    SOURCE_NAMES[game.source],
  ]
    .filter(Boolean)
    .join(", ");
}

export function PlayerBar({ game, color }: { game: GameDetail; color: Color }) {
  const name = playerName(game, color);
  const elo = playerElo(game, color);
  const accuracy = shownAccuracy(game, color);
  const group = game.group_accuracy?.[color] ?? null;
  const { t } = useI18n();
  return (
    <div className="flex min-h-10 items-center gap-2.5">
      <PlayerAvatar name={name} color={color} size={36} />
      <p className="min-w-0 flex-1 truncate text-[15px]">
        <span className="font-bold">{name}</span>
        {elo && <span className="ml-1.5 font-semibold text-muted">({elo})</span>}
      </p>
      {accuracy && group !== null && elo && (
        <span title={t.review.groupAccuracyHint(Number(elo))} className="hidden text-xs font-bold whitespace-nowrap text-muted sm:inline">
          {t.review.groupAccuracyShort(group.toFixed(1))}
        </span>
      )}
      {accuracy && (
        <span
          title={accuracy.official ? t.review.accuracyOfficial : t.review.accuracy}
          className={`rounded-md px-2.5 py-1 text-sm font-extrabold ${
            color === "white" ? "bg-white text-[#2c2925]" : "bg-sunken text-ink"
          }`}
        >
          {accuracy.value.toFixed(1)}
        </span>
      )}
    </div>
  );
}

function AnalysisStatus({
  state,
  starting,
  error,
  source,
  onSource,
  onStart,
  onCancel,
}: {
  state: AnalysisState | null;
  starting: boolean;
  error: string | null;
  source: EngineSource;
  onSource: (source: EngineSource) => void;
  onStart: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  if (state && (state.status === "queued" || state.status === "running")) {
    const percent = state.total > 0 ? Math.round((state.done / state.total) * 100) : 0;
    const browser = state.runner === "browser";
    return (
      <div aria-live="polite" className="flex flex-col gap-3">
        <CoachBubble>
          {browser ? t.review.runningBrowser : state.status === "queued" ? t.review.queued : t.review.running}
        </CoachBubble>
        <div className="flex items-center gap-3">
          <div
            role="progressbar"
            aria-label={t.review.progressLabel}
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
            {state.total > 0 ? t.review.progress(state.done, state.total) : "…"}
          </span>
        </div>
        {browser && (
          <div>
            <Button variant="raised" onClick={onCancel}>
              {t.review.cancel}
            </Button>
          </div>
        )}
      </div>
    );
  }
  const failed = state?.status === "failed";
  return (
    <div className="flex flex-col gap-3">
      <CoachBubble>
        {failed
          ? t.review.failed(codeText(t, state.error_code, {}, state.error ?? t.review.unknownError))
          : t.review.notAnalyzed}
      </CoachBubble>
      <ErrorText>{error}</ErrorText>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-bold uppercase tracking-wide text-muted">{t.review.runnerLabel}</span>
          <EngineSourceSwitch
            label={t.review.runnerLabel}
            value={source}
            onChange={onSource}
            options={{ browser: t.review.runnerBrowser, server: t.review.runnerServer }}
          />
        </div>
        <p className="text-xs font-semibold text-muted">
          {source === "browser" ? t.review.runnerBrowserHint : t.review.runnerServerHint}
        </p>
      </div>
      <Button size="lg" onClick={onStart} disabled={starting}>
        {starting ? t.review.starting : failed ? t.review.restart : t.review.start}
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
