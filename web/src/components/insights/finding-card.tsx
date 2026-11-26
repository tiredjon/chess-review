"use client";

import { CLASS_COLORS } from "@/lib/classes";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Finding, Severity } from "@/lib/insights-api";
import { ExampleBoard } from "./example-board";
import { findingCopy, formatPercent } from "./copy";
import { TrainButton } from "./train-button";

// Важность — цветами классов ходов: зевок, ошибка, неточность.
export const SEVERITY_COLORS: Record<Severity, string> = {
  high: CLASS_COLORS.blunder,
  medium: CLASS_COLORS.mistake,
  low: CLASS_COLORS.inaccuracy,
};

/** Карточка вывода: вид и важность, заголовок, текст с числами, сравнение столбиками,
 *  примеры из партий и «Тренировать». */
export function FindingCard({ finding }: { finding: Finding }) {
  const { t, lang } = useI18n();
  const copy = findingCopy(t, lang, finding);
  const color = SEVERITY_COLORS[finding.severity];
  const digits = finding.kind === "opening" || finding.kind === "conversion" ? 0 : 1;
  const max = Math.max(finding.stats.value, finding.stats.baseline, 1);
  return (
    <article className="overflow-hidden rounded-xl bg-panel">
      <div className="flex flex-col gap-4 border-l-4 p-4 sm:p-5" style={{ borderColor: color }}>
        <header className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2 text-xs font-bold">
            <span className="rounded-md px-2 py-0.5 text-[#1e1c19]" style={{ background: color }}>
              {t.insights.severity[finding.severity]}
            </span>
            <span className="text-muted uppercase tracking-wide">{copy.kind}</span>
          </div>
          <h2 className="text-xl font-extrabold leading-tight break-words">{copy.title}</h2>
          <p className="max-w-3xl text-soft">{copy.text}</p>
        </header>

        <dl className="grid max-w-xl gap-2 text-sm">
          <Bar
            label={copy.valueLabel}
            value={`${formatPercent(finding.stats.value, lang, digits)}%`}
            width={(100 * finding.stats.value) / max}
            color={color}
            strong
          />
          <Bar
            label={copy.baseLabel}
            value={`${formatPercent(finding.stats.baseline, lang, digits)}%`}
            width={(100 * finding.stats.baseline) / max}
            color="var(--muted)"
          />
        </dl>

        {finding.examples.length > 0 && (
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-bold text-muted">{t.insights.examples}</h3>
            <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
              {finding.examples.map((example) => (
                <li key={`${example.game_id}-${example.ply}`} className="min-w-0">
                  <ExampleBoard example={example} />
                </li>
              ))}
            </ul>
          </section>
        )}

        <TrainButton finding={finding} />
      </div>
    </article>
  );
}

function Bar({
  label,
  value,
  width,
  color,
  strong = false,
}: {
  label: string;
  value: string;
  width: number;
  color: string;
  strong?: boolean;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_3.5rem] items-center gap-3">
      <dt className="truncate font-semibold text-soft">{label}</dt>
      <dd className="h-2.5 overflow-hidden rounded-full bg-sunken">
        <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, width))}%`, background: color }} />
      </dd>
      <dd className={`text-right tabular-nums ${strong ? "font-extrabold" : "font-semibold text-soft"}`}>{value}</dd>
    </div>
  );
}
