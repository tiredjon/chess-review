"use client";

import Link from "next/link";
import { shownAccuracy } from "@/lib/accuracy";
import { formatDate, formatTimeControl, gameHref, outcome, score, SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Color, GameOut } from "@/lib/types";
import { ColorSquare } from "./player-avatar";

const GRID =
  "grid grid-cols-[minmax(0,1fr)_auto_4.5rem] items-center gap-x-3 sm:grid-cols-[4.5rem_minmax(0,1fr)_4rem_5.5rem_7.5rem]";

/** «История партий»: строка — ссылка на разбор (без анализа — с его запуском). */
export function GamesTable({ games }: { games: GameOut[] }) {
  const { t } = useI18n();
  const copy = t.home.table;
  return (
    <div role="table" aria-label={copy.label} className="text-[15px]">
      <div role="row" className={`${GRID} border-b border-line px-3 pb-2 text-xs font-semibold text-muted`}>
        <span role="columnheader" className="hidden sm:block">
          {copy.timeControl}
        </span>
        <span role="columnheader">{copy.players}</span>
        <span role="columnheader" className="text-center">
          {copy.result}
        </span>
        <span role="columnheader" className="text-center">
          {copy.accuracy}
        </span>
        <span role="columnheader" className="hidden text-right sm:block">
          {copy.date}
        </span>
      </div>
      {games.map((game) => (
        <GameRow key={game.id} game={game} />
      ))}
    </div>
  );
}

function GameRow({ game }: { game: GameOut }) {
  const { t, lang } = useI18n();
  const result = outcome(game);
  return (
    <Link
      role="row"
      href={gameHref(game)}
      className={`${GRID} border-b border-line px-3 py-3 last:border-b-0 hover:bg-raised/40`}
    >
      <span role="cell" className="hidden flex-col items-center gap-0.5 text-center sm:flex">
        <ClockIcon />
        <span className="text-xs font-semibold text-soft">{formatTimeControl(game.time_control, t) ?? "—"}</span>
      </span>
      <span role="cell" className="flex min-w-0 flex-col gap-1">
        <Player game={game} color="white" />
        <Player game={game} color="black" />
        <span className="truncate text-xs text-muted sm:hidden">
          {[SOURCE_NAMES[game.source], formatDate(game.played_at, lang)].filter(Boolean).join(", ")}
        </span>
      </span>
      <span role="cell" className="flex items-center justify-center gap-2">
        <span className="flex flex-col text-center font-semibold leading-6 text-soft">
          <span>{score(game.result, "white")}</span>
          <span>{score(game.result, "black")}</span>
        </span>
        {result && <OutcomeIcon outcome={result} />}
      </span>
      <span role="cell" className="flex justify-center">
        <Accuracy game={game} />
      </span>
      <span role="cell" className="hidden text-right text-sm font-medium text-soft sm:block">
        {formatDate(game.played_at, lang) ?? "—"}
        <span className="block text-xs text-muted">{SOURCE_NAMES[game.source]}</span>
      </span>
    </Link>
  );
}

function Player({ game, color }: { game: GameOut; color: Color }) {
  const name = color === "white" ? game.white : game.black;
  const elo = color === "white" ? game.white_elo : game.black_elo;
  return (
    <span className="flex min-w-0 items-center gap-2">
      <ColorSquare color={color} />
      <span className={`truncate ${game.user_color === color ? "font-bold text-ink" : "font-semibold text-soft"}`}>
        {name}
      </span>
      {elo && <span className="shrink-0 text-sm text-muted">({elo})</span>}
    </span>
  );
}

function Accuracy({ game }: { game: GameOut }) {
  const { t } = useI18n();
  const analysis = game.analysis;
  const white = shownAccuracy(game, "white");
  const black = shownAccuracy(game, "black");
  if (white && black) {
    return (
      <span
        className="flex flex-col text-center font-semibold leading-6 text-soft"
        title={white.official ? t.home.table.officialAccuracy : t.home.table.accuracy}
      >
        <span>{white.value.toFixed(1)}</span>
        <span>{black.value.toFixed(1)}</span>
      </span>
    );
  }
  if (!analysis || analysis.status === "failed") {
    return (
      <span className="rounded-md bg-raised px-2.5 py-1.5 text-sm font-bold text-soft shadow-[0_2px_0_0_rgba(0,0,0,0.35)]">
        {t.home.table.review}
      </span>
    );
  }
  return <span className="text-xs font-semibold text-muted">{t.home.table.analyzing}</span>;
}

function OutcomeIcon({ outcome: value }: { outcome: NonNullable<ReturnType<typeof outcome>> }) {
  const { t } = useI18n();
  const label = t.common.outcome[value];
  const look = {
    win: ["bg-green", "M5 10h10M10 5v10"],
    loss: ["bg-[#e8402e]", "M5 10h10"],
    draw: ["bg-muted", "M5 7.5h10M5 12.5h10"],
  }[value];
  return (
    <span title={label} className={`flex h-5 w-5 items-center justify-center rounded ${look[0]}`}>
      <svg role="img" aria-label={label} viewBox="0 0 20 20" className="h-3.5 w-3.5">
        <path d={look[1]} stroke="white" strokeWidth="3" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function ClockIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6 text-green">
      <circle cx="12" cy="13" r="8" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <path d="M12 9v4.5l2.5 1.5M9.5 2.5h5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function GamesTableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div aria-busy className="flex flex-col">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4 border-b border-line px-3 py-4 last:border-b-0">
          <span className="h-8 w-10 animate-pulse rounded bg-raised" />
          <span className="h-4 w-56 animate-pulse rounded bg-raised" />
        </div>
      ))}
    </div>
  );
}
