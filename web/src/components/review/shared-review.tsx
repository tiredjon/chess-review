"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { pliesFromMoves, pliesFromPgn, START_FEN } from "@/lib/chess";
import { formatResult } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { GameDetail } from "@/lib/types";
import { ErrorText } from "../ui";
import { PlayerBar, ReviewSkeleton, useGameSubtitle } from "./game-review";
import { Overview } from "./overview";
import { Review } from "./review";
import { ReviewSourceProvider, sharedSource } from "./review-source";
import { CoachBubble, GameSummary } from "./summary";

// Пока анализ идёт, страница по ссылке опрашивает API (SSE для гостей нет).
const POLL_MS = 3000;

/** Разбор по публичной ссылке (`/share/{token}`, ссылки бота): только чтение, без входа. */
export function SharedReview({ token, initialPly }: { token: string; initialPly: number }) {
  const { t } = useI18n();
  const [game, setGame] = useState<GameDetail | null>(null);
  const [error, setError] = useState<{ status: number; message: string | null } | null>(null);

  const load = useCallback(() => {
    api.shared
      .game(token)
      .then(setGame)
      .catch((err) =>
        setError(err instanceof ApiError ? { status: err.status, message: err.message } : { status: 0, message: null }),
      );
  }, [token]);
  useEffect(load, [load]);

  const active = game?.analysis?.status === "queued" || game?.analysis?.status === "running";
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [active, load]);

  const source = useMemo(() => sharedSource(token), [token]);

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 py-10">
        <p className="text-xl font-extrabold">{error.status === 404 ? t.review.shared.notFound : t.review.openFailed}</p>
        <ErrorText>{error.status === 404 ? t.review.shared.notFoundText : (error.message ?? t.review.loadFailed)}</ErrorText>
        <Link href="/register" className="font-bold text-green hover:underline">
          {t.review.shared.cta}
        </Link>
      </div>
    );
  }
  if (!game) return <ReviewSkeleton />;
  return (
    <ReviewSourceProvider value={source}>
      <SharedGame game={game} initialPly={initialPly} active={active} />
    </ReviewSourceProvider>
  );
}

function SharedGame({ game, initialPly, active }: { game: GameDetail; initialPly: number; active: boolean }) {
  const { t } = useI18n();
  const subtitle = useGameSubtitle(game);
  const analysis = game.analysis?.status === "done" ? game.analysis : null;
  const { plies, startFen } = useMemo(
    () =>
      analysis && analysis.moves.length > 0
        ? { plies: pliesFromMoves(analysis.moves), startFen: analysis.moves[0].fen_before }
        : pliesFromPgn(game.pgn),
    [analysis, game.pgn],
  );
  return (
    <>
      <h1 className="sr-only">
        {game.white} – {game.black}, {formatResult(game.result)}
      </h1>
      <Review
        // Ходы пришли после анализа — разбор строится заново (курсор, режимы).
        key={analysis?.id ?? "pgn"}
        plies={plies}
        startFen={plies.length > 0 ? startFen : START_FEN}
        initialCursor={Math.min(initialPly, plies.length)}
        initialOrientation={game.user_color ?? "white"}
        player={(color) => <PlayerBar game={game} color={color} />}
        subtitle={subtitle}
        status={<CoachBubble>{active ? t.review.shared.analyzing : t.review.shared.notAnalyzed}</CoachBubble>}
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
