"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Dict } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameOut, GameSource } from "@/lib/types";
import { DocumentTitle } from "./document-title";
import { GamesTable, GamesTableSkeleton } from "./games-table";
import { Button, ErrorText } from "./ui";

const PAGE_SIZE = 30;

const errorText = (err: unknown, t: Dict) => (err instanceof ApiError ? err.message : t.home.gamesLoadFailed);

/** Список партий с курсорной пагинацией. */
export function GamesList({ source }: { source: GameSource | null }) {
  const { t } = useI18n();
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
      .catch((err) => !cancelled && setError(errorText(err, t)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [source, t]);

  async function loadMore() {
    setLoading(true);
    setError(null);
    try {
      const page = await api.games({ cursor, source, limit: PAGE_SIZE });
      setGames((current) => [...current, ...page.items]);
      setCursor(page.next_cursor);
    } catch (err) {
      setError(errorText(err, t));
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
            {loading ? t.common.actions.loading : t.common.actions.more}
          </Button>
        </div>
      )}
    </div>
  );
}

export function EmptyGames() {
  const { t } = useI18n();
  const copy = t.home.list;
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <p className="text-lg font-bold">{copy.empty}</p>
      <p className="text-soft">
        <Link href="/" className="font-bold text-green hover:underline">
          {copy.emptyLink}
        </Link>{" "}
        {copy.emptyRest}
      </p>
    </div>
  );
}

export function GamesHeader() {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <DocumentTitle page="games" />
      <h1 className="text-2xl font-extrabold sm:text-3xl">{t.home.historyTitle}</h1>
      <Link href="/" className="text-sm font-bold text-green hover:underline">
        {t.home.loadMore}
      </Link>
    </div>
  );
}

/** Фильтр по источнику — ссылками, состояние в URL (`?source=`). */
export function SourceFilter({ current }: { current: GameSource | null }) {
  const { t } = useI18n();
  const options: [GameSource | null, string][] = [
    [null, t.home.list.all],
    ...(Object.keys(SOURCE_NAMES) as GameSource[]).map((source): [GameSource, string] => [source, SOURCE_NAMES[source]]),
  ];
  return (
    <nav aria-label={t.home.list.filterLabel} className="flex flex-wrap gap-2">
      {options.map(([source, label]) => (
        <Link
          key={source ?? "all"}
          href={source ? `/games?source=${source}` : "/games"}
          aria-current={current === source ? "page" : undefined}
          className={`flex min-h-10 items-center rounded-lg px-4 text-sm font-semibold ${
            current === source
              ? "bg-raised text-ink ring-2 ring-green ring-inset"
              : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
          }`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
