"use client";

import type { WeekReport } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Panel } from "../ui";
import { BlockBody } from "./block";
import { deltaTone, formatShortDay, formatValue, itemName } from "./copy";
import type { Section } from "./use-section";

const TONE_COLOR = { better: "var(--green)", worse: "var(--danger)", same: "var(--muted)" } as const;
const TONE_ARROW = { better: "▲", worse: "▼", same: "●" } as const;

/** «Отчёт за неделю»: сколько заданий и минут, партии, рейтинг, динамика показателей. */
export function ReportCard({ section }: { section: Section<{ report: WeekReport | null }> }) {
  const { t, lang } = useI18n();
  const c = t.coach.report;
  const week = section.data?.report?.week_start;
  return (
    <Panel title={c.title} aside={week ? <span className="text-sm font-semibold text-muted">{c.week(formatShortDay(week, lang))}</span> : undefined}>
      <BlockBody section={section} height={140}>
        {({ report }) =>
          report === null ? (
            <p className="text-soft">{c.none}</p>
          ) : (
            <div className="flex flex-col gap-4">
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label={c.tasks} value={`${report.tasks_done}/${report.tasks_total}`} />
                <Stat label={c.minutes} value={String(report.minutes_done)} />
                <Stat label={c.games} value={String(report.games_played)} />
                <Stat
                  label={c.rating}
                  value={report.rating_start !== null && report.rating_end !== null ? c.ratingChange(report.rating_start, report.rating_end) : "—"}
                  tone={report.rating_start !== null && report.rating_end !== null ? Math.sign(report.rating_end - report.rating_start) : 0}
                />
              </dl>
              <section className="flex flex-col gap-2">
                <h3 className="text-sm font-bold text-muted">{c.dynamics}</h3>
                {report.metrics.length === 0 ? (
                  <p className="text-soft">{c.noMetrics}</p>
                ) : (
                  <ul className="flex flex-col divide-y divide-line rounded-lg bg-raised/40">
                    {report.metrics.map((m) => {
                      const tone = deltaTone(m);
                      return (
                        <li key={`${m.kind}:${m.key}`} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 px-3 py-2.5 text-sm">
                          <span className="min-w-0 flex-1 font-bold">{itemName(t, m.kind, m.key)}</span>
                          <span className="tabular-nums font-semibold text-soft">
                            {formatValue(t, lang, m.kind, m.key, m.before)} → {formatValue(t, lang, m.kind, m.key, m.after)}
                          </span>
                          <span className="w-24 text-right text-xs font-extrabold" style={{ color: TONE_COLOR[tone] }}>
                            <span aria-hidden>{TONE_ARROW[tone]}</span> {c[tone]}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            </div>
          )
        }
      </BlockBody>
    </Panel>
  );
}

function Stat({ label, value, tone = 0 }: { label: string; value: string; tone?: number }) {
  return (
    <div className="rounded-lg bg-raised/50 px-3 py-2.5">
      <dt className="text-xs font-bold text-muted">{label}</dt>
      <dd className="text-xl font-extrabold tabular-nums" style={{ color: tone > 0 ? "var(--green)" : tone < 0 ? "var(--danger)" : undefined }}>
        {value}
      </dd>
    </div>
  );
}
