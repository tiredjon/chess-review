"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import { insightsApi, type Insights } from "@/lib/insights-api";
import type { GameSource, TimeClass } from "@/lib/types";
import { ErrorText, Panel } from "../ui";
import { FindingCard } from "./finding-card";

type Filters = { source: GameSource | null; timeClass: TimeClass | null };

// Те же контроли, что у фильтров /stats (`components/stats/filters.tsx`).
const TIME_CLASSES: TimeClass[] = ["bullet", "blitz", "rapid", "daily"];

/** Заголовок страницы на языке интерфейса (серверная page.tsx его не знает). */
export function WeaknessesHeading() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-1">
      <Link href="/stats" className="w-fit text-sm font-bold text-muted hover:text-ink">
        ← {t.stats.title}
      </Link>
      <h1 className="text-2xl font-extrabold sm:text-3xl">{t.insights.title}</h1>
      <p className="text-soft">{t.insights.subtitle}</p>
    </div>
  );
}

/** Слабые места: фильтры в URL (`?source=&tc=`, как у /stats), карточки выводов по важности. */
export function WeaknessesView({ source, timeClass }: Filters) {
  const { t } = useI18n();
  const key = `${source ?? ""}|${timeClass ?? ""}`;
  const [result, setResult] = useState<{ key: string; data: Insights | null; error: string | null; failed: boolean } | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;
    insightsApi
      .me({ source, timeClass })
      .then((data) => !cancelled && setResult({ key, data, error: null, failed: false }))
      .catch(
        (err) =>
          !cancelled &&
          setResult((prev) => ({
            key,
            data: prev?.data ?? null,
            failed: true,
            error: err instanceof ApiError ? err.message : null,
          })),
      );
    return () => {
      cancelled = true;
    };
  }, [key, source, timeClass]);

  const loading = result?.key !== key;
  const data = result?.data ?? null;
  const error = loading || !result?.failed ? null : (result.error ?? t.insights.loadError);
  const filtered = source !== null || timeClass !== null;
  return (
    <div className="flex flex-col gap-5">
      <InsightsFilters source={source} timeClass={timeClass} />
      <ErrorText>{error}</ErrorText>
      {data === null ? (
        !error && <WeaknessesSkeleton />
      ) : (
        <div className={`flex flex-col gap-4 transition-opacity ${loading ? "opacity-50" : ""}`} aria-busy={loading}>
          <Body data={data} filtered={filtered} />
        </div>
      )}
    </div>
  );
}

function Body({ data, filtered }: { data: Insights; filtered: boolean }) {
  const { t } = useI18n();
  const copy = t.insights.empty;
  if (data.analyzed_games < data.min_games) {
    return (
      <Panel>
        <Empty title={copy.fewTitle}>
          <p>{copy.fewText(data.analyzed_games, data.min_games)}</p>
          {filtered && <p className="mt-2 text-sm text-muted">{copy.filteredText}</p>}
          <Link
            href="/games"
            className="mt-4 inline-flex min-h-11 items-center justify-center rounded-lg bg-green px-5 text-[15px] font-bold text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover"
          >
            {copy.gamesLink}
          </Link>
        </Empty>
      </Panel>
    );
  }
  if (data.findings.length === 0) {
    return (
      <Panel>
        <Empty title={copy.noneTitle}>
          <p>{copy.noneText}</p>
          <p className="mt-2 text-sm text-muted">{t.insights.basis(data.analyzed_games)}</p>
        </Empty>
      </Panel>
    );
  }
  return (
    <>
      <p className="text-sm font-semibold text-muted">{t.insights.basis(data.analyzed_games)}</p>
      {data.findings.map((finding) => (
        <FindingCard key={finding.id} finding={finding} />
      ))}
    </>
  );
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-2 py-8 text-center">
      <p className="text-lg font-bold">{title}</p>
      <div className="flex max-w-md flex-col items-center text-soft">{children}</div>
    </div>
  );
}

export function WeaknessesSkeleton() {
  return (
    <div aria-busy className="flex flex-col gap-4">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="h-72 animate-pulse rounded-xl bg-panel" />
      ))}
    </div>
  );
}

function href({ source, timeClass }: Filters) {
  const query = new URLSearchParams();
  if (source) query.set("source", source);
  if (timeClass) query.set("tc", timeClass);
  const qs = query.toString();
  return qs ? `/stats/weaknesses?${qs}` : "/stats/weaknesses";
}

/** Фильтры как у /stats, но ссылки — на этот экран. */
function InsightsFilters(current: Filters) {
  const { t } = useI18n();
  const sources: [GameSource | null, string][] = [
    [null, t.stats.filters.allSources],
    ...(Object.entries(SOURCE_NAMES) as [GameSource, string][]),
  ];
  const classes: [TimeClass | null, string][] = [
    [null, t.stats.filters.anyTimeControl],
    ...TIME_CLASSES.map((timeClass): [TimeClass, string] => [timeClass, t.stats.timeClasses[timeClass]]),
  ];
  const chip = (target: string, active: boolean, label: string, id: string) => (
    <Link
      key={id}
      href={target}
      scroll={false}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-9 items-center rounded-lg px-3 text-sm font-semibold ${
        active ? "bg-raised text-ink ring-2 ring-green ring-inset" : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-5">
      <nav aria-label={t.stats.filters.source} className="flex flex-wrap gap-1.5">
        {sources.map(([source, label]) =>
          chip(href({ ...current, source }), current.source === source, label, source ?? "all"),
        )}
      </nav>
      <nav aria-label={t.stats.filters.timeControl} className="flex flex-wrap gap-1.5">
        {classes.map(([timeClass, label]) =>
          chip(href({ ...current, timeClass }), current.timeClass === timeClass, label, timeClass ?? "all"),
        )}
      </nav>
    </div>
  );
}
