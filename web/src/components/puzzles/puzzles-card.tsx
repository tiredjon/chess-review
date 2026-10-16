"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PuzzleCounts } from "@/lib/types";

/** Карточка на главной: сколько пазлов на сегодня (пора повторить + новые) и серия. */
export function PuzzlesCard() {
  const [counts, setCounts] = useState<PuzzleCounts | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .nextPuzzle()
      .then((next) => !cancelled && setCounts(next.counts))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (counts === null) return <div className="h-[76px] animate-pulse rounded-xl bg-panel" />;
  const today = counts.due + counts.new;
  return (
    <section
      aria-label="Пазлы на сегодня"
      className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl bg-panel px-4 py-3 sm:px-5"
    >
      <span aria-hidden className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-raised text-green">
        <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
          <path d="M10 3.5a2 2 0 0 1 4 0V5h4a1 1 0 0 1 1 1v4h-1.5a2 2 0 0 0 0 4H19v4a1 1 0 0 1-1 1h-4v-1.5a2 2 0 0 0-4 0V19H6a1 1 0 0 1-1-1v-4h1.5a2 2 0 0 0 0-4H5V6a1 1 0 0 1 1-1h4z" />
        </svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-lg font-extrabold">
          {counts.total === 0 ? "Пазлы из ваших ошибок" : `Пазлов на сегодня: ${today}`}
        </p>
        <p className="text-sm font-semibold text-muted">
          {counts.total === 0
            ? "Появятся после разбора партий: каждая ошибка — позиция, где нужно найти лучший ход."
            : today === 0
              ? `Всё решено. Решено подряд: ${counts.streak}.`
              : `${counts.due} на повторение · ${counts.new} новых · решено подряд ${counts.streak}`}
        </p>
      </div>
      {today > 0 && (
        <Link
          href="/puzzles"
          className="flex min-h-11 items-center justify-center rounded-lg bg-green px-5 text-[15px] font-bold text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover max-sm:w-full"
        >
          Решать
        </Link>
      )}
    </section>
  );
}
