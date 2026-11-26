"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { insightsApi, type Insights } from "@/lib/insights-api";
import { findingCopy } from "./copy";
import { SEVERITY_COLORS } from "./finding-card";
import { WeaknessIcon } from "./weaknesses-link";

/** Карточка на главной: главное слабое место (или сколько партий ещё разобрать) → экран. */
export function WeaknessesCard() {
  const { t, lang } = useI18n();
  const copy = t.insights.card;
  const [data, setData] = useState<Insights | null>(null);

  useEffect(() => {
    let cancelled = false;
    insightsApi
      .me()
      .then((insights) => !cancelled && setData(insights))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (data === null) return <div className="h-[76px] animate-pulse rounded-xl bg-panel" />;
  const top = data.findings[0];
  const few = data.analyzed_games < data.min_games;
  return (
    <section aria-label={copy.label} className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl bg-panel px-4 py-3 sm:px-5">
      <WeaknessIcon />
      <div className="min-w-0 flex-1">
        {top ? (
          <>
            <p className="flex min-w-0 items-center gap-2 text-lg font-extrabold">
              <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: SEVERITY_COLORS[top.severity] }} />
              <span className="truncate">{findingCopy(t, lang, top).title}</span>
            </p>
            <p className="text-sm font-semibold text-muted">{copy.top(data.findings.length)}</p>
          </>
        ) : (
          <>
            <p className="text-lg font-extrabold">{copy.title}</p>
            <p className="text-sm font-semibold text-muted">
              {few ? copy.few(data.min_games - data.analyzed_games) : copy.none}
            </p>
          </>
        )}
      </div>
      {!few && (
        <Link
          href="/stats/weaknesses"
          className="flex min-h-11 items-center justify-center rounded-lg bg-raised px-5 text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink max-sm:w-full"
        >
          {copy.open}
        </Link>
      )}
    </section>
  );
}
