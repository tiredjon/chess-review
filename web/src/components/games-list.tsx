"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { accuracyTone } from "@/lib/classes";
import {
  formatDate,
  formatResult,
  formatTimeControl,
  outcome,
  OUTCOME_LABELS,
  SOURCE_NAMES,
} from "@/lib/format";
import type { Color, GameOut, GameSource } from "@/lib/types";
import { Button, ErrorText } from "./ui";

const PAGE_SIZE = 30;

export function GamesList({ source }: { source: GameSource | null }) {
  const [games, setGames] = useState<GameOut[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(after: string | null) {
    setLoading(true);
    setError(null);
    try {
      const page = await api.games({ cursor: after, source, limit: PAGE_SIZE });
      setGames((current) => (after ? [...current, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось загрузить партии");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    api
      .games({ source, limit: PAGE_SIZE })
      .then((page) => {
        if (cancelled) return;
        setGames(page.items);
        setCursor(page.next_cursor);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Не удалось загрузить партии");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source]);

  if (loading && games.length === 0) return <GamesListSkeleton />;
  if (error && games.length === 0) return <ErrorText>{error}</ErrorText>;
  if (games.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line px-6 py-12 text-center">
        <p className="text-lg font-medium">Партий пока нет</p>
        <p className="mt-1 text-muted">
          <Link href="/" className="font-medium text-accent underline-offset-2 hover:underline">
            Загрузите партии
          </Link>{" "}
          с Lichess, Chess.com или вставьте PGN.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {games.map((game) => (
          <li key={game.id}>
            <GameRow game={game} />
          </li>
        ))}
      </ul>
      <ErrorText>{error}</ErrorText>
      {cursor && (
        <div className="flex justify-center">
          <Button variant="quiet" disabled={loading} onClick={() => load(cursor)}>
            {loading ? "Загружаю…" : "Показать ещё"}
          </Button>
        </div>
      )}
    </div>
  );
}

function GameRow({ game }: { game: GameOut }) {
  const result = outcome(game);
  const meta = [
    SOURCE_NAMES[game.source],
    formatTimeControl(game.time_control),
    formatDate(game.played_at),
  ].filter(Boolean);
  return (
    <Link
      href={`/games/${game.id}`}
      className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-paper sm:grid-cols-[auto_minmax(0,1.3fr)_minmax(0,1fr)_auto]"
    >
      <ResultMark result={game.result} outcome={result} />
      <div className="min-w-0">
        <Player game={game} color="white" />
        <Player game={game} color="black" />
      </div>
      <div className="order-last col-span-3 min-w-0 text-sm text-muted sm:order-none sm:col-span-1">
        <p className="truncate text-ink">
          {game.opening_name ?? "Дебют не определён"}
          {game.opening_eco && <span className="ml-1.5 text-muted">{game.opening_eco}</span>}
        </p>
        <p className="truncate">{meta.join(", ")}</p>
      </div>
      <AnalysisBadge game={game} />
    </Link>
  );
}

function ResultMark({ result, outcome: value }: { result: string; outcome: ReturnType<typeof outcome> }) {
  const tone =
    value === "win"
      ? "bg-[#5f9f3a] text-white"
      : value === "loss"
        ? "bg-[#c03a2f] text-white"
        : "bg-sunken text-muted";
  return (
    <span
      className={`flex h-9 w-12 items-center justify-center rounded-md text-sm font-semibold ${tone}`}
      title={value ? OUTCOME_LABELS[value] : undefined}
    >
      {formatResult(result)}
    </span>
  );
}

function Player({ game, color }: { game: GameOut; color: Color }) {
  const name = color === "white" ? game.white : game.black;
  const elo = color === "white" ? game.white_elo : game.black_elo;
  const isUser = game.user_color === color;
  return (
    <p className="flex items-center gap-2 truncate">
      <span
        aria-label={color === "white" ? "белые" : "чёрные"}
        className={`h-3 w-3 shrink-0 rounded-sm border border-muted/50 ${color === "white" ? "bg-white" : "bg-[#2a3240]"}`}
      />
      <span className={`truncate ${isUser ? "font-semibold" : ""}`}>{name}</span>
      {elo && <span className="text-sm text-muted">{elo}</span>}
    </p>
  );
}

function AnalysisBadge({ game }: { game: GameOut }) {
  const analysis = game.analysis;
  if (!analysis) return <span className="text-sm text-muted">Не разобрана</span>;
  if (analysis.status === "failed") return <span className="text-sm text-danger">Ошибка анализа</span>;
  if (analysis.status !== "done") return <span className="text-sm text-accent">Анализ идёт…</span>;
  return (
    <span className="flex gap-1.5" aria-label="Точность белых и чёрных">
      <AccuracyChip value={analysis.white_accuracy} color="white" strong={game.user_color !== "black"} />
      <AccuracyChip value={analysis.black_accuracy} color="black" strong={game.user_color !== "white"} />
    </span>
  );
}

function AccuracyChip({ value, color, strong }: { value: number | null; color: Color; strong: boolean }) {
  if (value === null) return null;
  return (
    <span
      title={`Точность ${color === "white" ? "белых" : "чёрных"}`}
      className={`min-w-12 rounded-md px-2 py-1 text-center text-sm font-semibold text-white ${strong ? "" : "opacity-55"}`}
      style={{ background: accuracyTone(value) }}
    >
      {value.toFixed(1)}
    </span>
  );
}

export function GamesListSkeleton() {
  return (
    <ul aria-busy className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
      {Array.from({ length: 6 }, (_, i) => (
        <li key={i} className="flex items-center gap-4 px-4 py-4">
          <span className="h-9 w-12 animate-pulse rounded-md bg-sunken" />
          <span className="h-4 w-48 animate-pulse rounded bg-sunken" />
        </li>
      ))}
    </ul>
  );
}
