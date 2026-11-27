"use client";

import type { Confidence, Forecast, ForecastStatus } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Panel } from "../ui";
import { BlockBody, Empty } from "./block";
import { formatDay, formatNumber } from "./copy";
import { ForecastChart } from "./forecast-chart";
import type { Section } from "./use-section";

const STATUS_COLOR: Record<ForecastStatus, string> = {
  achieved: "var(--green)",
  ahead: "var(--green)",
  on_track: "#5ca8de",
  behind: "#f59a4c",
  insufficient: "var(--muted)",
};

/** Доли 0–1 (контракт 17.2) → проценты; значение > 1 уже в процентах. */
const toPercent = (value: number) => Math.round(value <= 1 ? value * 100 : value);

const CONFIDENCE_DOTS: Record<Confidence, number> = { low: 1, medium: 2, high: 3 };

/** «Прогноз»: график, срок диапазоном («скорее всего к … , с запасом к …»), уверенность и основание. */
export function ForecastCard({ section }: { section: Section<Forecast> }) {
  const { t } = useI18n();
  return (
    <Panel title={t.coach.forecast.title} aside={section.data ? <StatusBadge status={section.data.status} /> : undefined}>
      <BlockBody section={section} height={320}>
        {(forecast) => <ForecastBody forecast={forecast} />}
      </BlockBody>
    </Panel>
  );
}

function StatusBadge({ status }: { status: ForecastStatus }) {
  const { t } = useI18n();
  return (
    <span className="rounded-md px-2 py-0.5 text-xs font-extrabold text-[#1e1c19]" style={{ background: STATUS_COLOR[status] }}>
      {t.coach.forecast.status[status]}
    </span>
  );
}

function ForecastBody({ forecast }: { forecast: Forecast }) {
  const { t, lang } = useI18n();
  const c = t.coach.forecast;
  if (forecast.status === "insufficient") {
    return (
      <Empty title={c.insufficientTitle}>
        <p>{c.insufficientText}</p>
      </Empty>
    );
  }
  const { basis } = forecast;
  const hasDates = forecast.date_p50 !== null && forecast.weeks_p50 !== null;
  return (
    <div className="flex flex-col gap-4">
      <ForecastChart forecast={forecast} />

      <div className="flex flex-col gap-1">
        {forecast.status === "achieved" ? (
          <p className="text-lg font-extrabold text-green">{c.reached(forecast.target_rating)}</p>
        ) : hasDates && forecast.date_p50 && forecast.weeks_p50 !== null ? (
          <>
            <p className="text-xl font-extrabold leading-snug">{c.likely(formatDay(forecast.date_p50, lang), forecast.weeks_p50)}</p>
            {forecast.date_p80 && forecast.weeks_p80 !== null && (
              <p className="font-semibold text-soft">{c.safe(formatDay(forecast.date_p80, lang), forecast.weeks_p80)}</p>
            )}
            {forecast.reach_probability_1y !== null && <p className="text-sm font-semibold text-muted">{c.probability(toPercent(forecast.reach_probability_1y))}</p>}
          </>
        ) : (
          <p className="font-bold text-[#f59a4c]">{c.never}</p>
        )}
      </div>

      <div className="flex flex-col gap-1.5 rounded-lg bg-raised/50 p-3 text-sm">
        <p className="flex items-center gap-2 font-extrabold">
          <span aria-hidden className="flex gap-0.5">
            {[1, 2, 3].map((i) => (
              <span key={i} className={`h-2 w-2 rounded-full ${i <= CONFIDENCE_DOTS[forecast.confidence] ? "bg-green" : "bg-sunken"}`} />
            ))}
          </span>
          {c.confidence[forecast.confidence]}
        </p>
        <p className="text-soft">{c.confidenceHint[forecast.confidence]}</p>
        <div className="mt-1">
          <p className="text-xs font-bold text-muted uppercase tracking-wide">{c.basisTitle}</p>
          <ul className="mt-1 list-disc pl-5 font-semibold text-soft">
            <li>{c.basis.players(basis.sample_players)}</li>
            <li>{c.basis.games(basis.user_games)}</li>
            {basis.weekly_trend !== null && <li>{c.basis.trend(Number(formatNumber(basis.weekly_trend, "en", 1)))}</li>}
            {basis.adherence !== null && <li>{c.basis.adherence(toPercent(basis.adherence))}</li>}
            <li>{c.basis.pace(Number(formatNumber(basis.games_per_week, "en", 1)))}</li>
          </ul>
        </div>
      </div>
      <p className="text-xs font-semibold text-muted">{c.disclaimer}</p>
    </div>
  );
}
