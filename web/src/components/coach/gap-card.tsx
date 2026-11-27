"use client";

import Link from "next/link";
import type { Gap, Metric } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { SEVERITY_COLORS } from "../insights/finding-card";
import { ExampleBoard } from "../insights/example-board";
import { TrainButton } from "../insights/train-button";
import { RAISED_LINK } from "./block";
import { formatValue, gapFinding, itemName, metricUnit } from "./copy";

/** Сильная или слабая сторона: значение против медианы целевой группы, примеры позиций, «Тренировать», «Урок». */
export function GapCard({
  gap,
  metric,
  currentBand,
  targetBand,
  strength = false,
}: {
  gap: Gap;
  metric: Metric | null;
  currentBand: number;
  targetBand: number;
  strength?: boolean;
}) {
  const { t, lang } = useI18n();
  const c = t.coach.diagnosis;
  const color = strength ? "var(--green)" : SEVERITY_COLORS[gap.severity];
  const unit = metricUnit(t, gap.kind, gap.key);
  const value = formatValue(t, lang, gap.kind, gap.key, gap.value);
  const target = gap.target_p50 === null ? null : formatValue(t, lang, gap.kind, gap.key, gap.target_p50);
  const lowerBetter = metric?.direction === "lower_better";
  const currentP50 = metric?.current?.p50 ?? null;
  const scale = Math.max(gap.value, gap.target_p50 ?? 0, currentP50 ?? 0, 1);
  return (
    <article className="overflow-hidden rounded-lg bg-raised/40">
      <div className="flex flex-col gap-3 border-l-4 p-3 sm:p-4" style={{ borderColor: color }}>
        <header className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2 text-xs font-bold">
            <span className="rounded-md px-2 py-0.5 text-[#1e1c19]" style={{ background: color }}>
              {strength ? c.status.strength : t.insights.severity[gap.severity]}
            </span>
            {metric && <span className="text-muted">{lowerBetter ? c.lowerBetter : c.higherBetter}</span>}
          </div>
          <h3 className="text-lg font-extrabold leading-tight break-words">{itemName(t, gap.kind, gap.key)}</h3>
        </header>

        <dl className="grid max-w-xl gap-2 text-sm">
          <Row label={c.you} value={`${value}${unit ? ` ${unit}` : ""}`} width={(100 * gap.value) / scale} color={color} strong />
          {currentP50 !== null && (
            <Row
              label={c.yourGroup(currentBand)}
              value={formatValue(t, lang, gap.kind, gap.key, currentP50)}
              width={(100 * currentP50) / scale}
              color="#8d877e"
            />
          )}
          {target !== null && gap.target_p50 !== null && (
            <Row label={c.targetGroup(targetBand)} value={target} width={(100 * gap.target_p50) / scale} color="#f5c451" />
          )}
        </dl>
        {metric?.percentile != null && <p className="text-sm font-semibold text-muted">{c.percentile(Math.round(metric.percentile))}</p>}

        {gap.examples.length > 0 && (
          <section className="flex flex-col gap-2">
            <h4 className="text-sm font-bold text-muted">{c.examples}</h4>
            <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
              {gap.examples.map((example) => (
                <li key={`${example.game_id}-${example.ply}`} className="min-w-0">
                  <ExampleBoard example={example} />
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          {!strength && <TrainButton finding={gapFinding(gap)} />}
          {gap.lesson && (
            <Link href={`/coach/lessons/${encodeURIComponent(gap.lesson)}`} className={RAISED_LINK}>
              {c.lesson}
            </Link>
          )}
        </div>
      </div>
    </article>
  );
}

function Row({ label, value, width, color, strong = false }: { label: string; value: string; width: number; color: string; strong?: boolean }) {
  return (
    <div className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)_minmax(3.5rem,auto)] items-center gap-3">
      <dt className="truncate font-semibold text-soft">{label}</dt>
      <dd className="h-2.5 overflow-hidden rounded-full bg-sunken">
        <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, width))}%`, background: color }} />
      </dd>
      <dd className={`text-right tabular-nums ${strong ? "font-extrabold" : "font-semibold text-soft"}`}>{value}</dd>
    </div>
  );
}
