"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";
import { api, ApiError } from "@/lib/api";
import { pliesFromPgn, START_FEN } from "@/lib/chess";
import { gameHref, opposite, outcome, OUTCOME_LABELS, playerName } from "@/lib/format";
import type { Color, GameOut } from "@/lib/types";
import { EmptyGames } from "./games-list";
import { GamesTable, GamesTableSkeleton } from "./games-table";
import { ImportCard } from "./import-form";
import { PlayerAvatar } from "./player-avatar";
import { ErrorText, Panel } from "./ui";

const HISTORY_SIZE = 10;
const RECENT_SIZE = 3;

/** Главная: загрузка партий, последние партии с позицией, история. */
export function HomeDashboard() {
  const [games, setGames] = useState<GameOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .games({ limit: HISTORY_SIZE })
      .then((page) => setGames(page.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить партии"));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 rounded-xl bg-panel/70 p-3 sm:p-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="rounded-lg p-1 sm:p-2">
          <ImportCard onImported={load} />
        </div>
        {/* Телефон: лента с прокруткой вбок, чтобы доски не вытесняли историю. */}
        <div className="-mx-3 flex snap-x snap-mandatory gap-3 overflow-x-auto px-3 pb-1 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 sm:pb-0">
          {games === null
            ? Array.from({ length: RECENT_SIZE }, (_, i) => (
                <div key={i} className="aspect-[3/4] w-[46%] shrink-0 animate-pulse rounded-lg bg-raised/50 sm:w-auto" />
              ))
            : games.slice(0, RECENT_SIZE).map((game) => <RecentGame key={game.id} game={game} />)}
        </div>
      </div>

      <Panel
        title="История партий"
        aside={
          <Link href="/games" className="text-sm font-bold text-green hover:underline">
            Все партии
          </Link>
        }
        className="px-1 sm:px-2"
      >
        {error ? (
          <ErrorText>{error}</ErrorText>
        ) : games === null ? (
          <GamesTableSkeleton rows={4} />
        ) : games.length === 0 ? (
          <EmptyGames />
        ) : (
          <GamesTable games={games} />
        )}
      </Panel>
    </div>
  );
}

/** Карточка последней партии: финальная позиция, соперник, кнопка разбора. */
function RecentGame({ game }: { game: GameOut }) {
  const [fen, setFen] = useState<string | null>(null);
  const me: Color = game.user_color ?? "white";
  const result = outcome(game);

  // В списке нет PGN — позицию берём из карточки партии.
  useEffect(() => {
    let cancelled = false;
    api
      .game(game.id)
      .then((detail) => {
        if (cancelled) return;
        const { plies, startFen } = pliesFromPgn(detail.pgn);
        setFen(plies.at(-1)?.fenAfter ?? startFen);
      })
      .catch(() => !cancelled && setFen(START_FEN));
    return () => {
      cancelled = true;
    };
  }, [game.id]);

  return (
    <article className="flex w-[46%] min-w-40 shrink-0 snap-start flex-col overflow-hidden rounded-lg bg-panel sm:w-auto sm:min-w-0">
      <div className="aspect-square bg-raised/40">
        {fen && (
          <Chessboard
            options={{
              id: `recent-${game.id}`,
              position: fen,
              boardOrientation: me,
              showNotation: false,
              allowDragging: false,
              showAnimations: false,
              darkSquareStyle: { backgroundColor: "var(--board-dark)" },
              lightSquareStyle: { backgroundColor: "var(--board-light)" },
            }}
          />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <PlayerAvatar name={playerName(game, opposite(me))} color={opposite(me)} size={36} />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold">против {playerName(game, opposite(me))}</p>
            <p className="text-xs font-semibold text-muted">{result ? OUTCOME_LABELS[result] : game.result}</p>
          </div>
        </div>
        <Link
          href={gameHref(game)}
          className="mt-auto flex min-h-11 items-center justify-center rounded-lg bg-raised text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink"
        >
          {game.analysis?.status === "done" ? "Разбор" : "Разобрать"}
        </Link>
      </div>
    </article>
  );
}
