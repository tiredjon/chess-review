"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { GameOut, GameSource } from "@/lib/types";
import { GamesTable, GamesTableSkeleton } from "./games-table";
import { Button, ErrorText } from "./ui";

const PAGE_SIZE = 30;

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : "Не удалось загрузить партии");

/** Список партий с курсорной пагинацией. */
export function GamesList({ source }: { source: GameSource | null }) {
  const [games, setGames] = useState<GameOut[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .games({ source, limit: PAGE_SIZE })
      .then((page) => {
        if (cancelled) return;
        setGames(page.items);
        setCursor(page.next_cursor);
      })
      .catch((err) => !cancelled && setError(errorText(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [source]);

  async function loadMore() {
    setLoading(true);
    setError(null);
    try {
      const page = await api.games({ cursor, source, limit: PAGE_SIZE });
      setGames((current) => [...current, ...page.items]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  if (loading && games.length === 0) return <GamesTableSkeleton />;
  if (error && games.length === 0) return <ErrorText>{error}</ErrorText>;
  if (games.length === 0) return <EmptyGames />;

  return (
    <div className="flex flex-col gap-4">
      <GamesTable games={games} />
      <ErrorText>{error}</ErrorText>
      {cursor && (
        <div className="flex justify-center">
          <Button variant="raised" disabled={loading} onClick={loadMore}>
            {loading ? "Загружаю…" : "Показать ещё"}
          </Button>
        </div>
      )}
    </div>
  );
}

export function EmptyGames() {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <p className="text-lg font-bold">Партий пока нет</p>
      <p className="text-soft">
        <Link href="/" className="font-bold text-green hover:underline">
          Загрузите партии
        </Link>{" "}
        с Lichess, Chess.com или вставьте PGN.
      </p>
    </div>
  );
}
