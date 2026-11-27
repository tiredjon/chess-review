"use client";

import Link from "next/link";
import { useState } from "react";
import type { Diagnosis, Metric } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button, Panel } from "../ui";
import { BlockBody, Empty, GREEN_LINK, RAISED_LINK } from "./block";
import { formatValue, itemName, statusColor } from "./copy";
import { GapCard } from "./gap-card";
import type { Section } from "./use-section";

/** «Сильные и слабые стороны»: слабые и сильные (`Gap`) с примерами, список всех показателей;
 *  пока разобрано меньше `min_games` партий — состояние «мало данных» со ссылкой на импорт. */
export function DiagnosisCard({ section }: { section: Section<Diagnosis> }) {
  const { t } = useI18n();
  return (
    <Panel title={t.coach.diagnosis.title}>
      <BlockBody section={section} height={260}>
        {(diagnosis) => <DiagnosisBody diagnosis={diagnosis} />}
      </BlockBody>
    </Panel>
  );
}

function DiagnosisBody({ diagnosis }: { diagnosis: Diagnosis }) {
  const { t, lang } = useI18n();
  const c = t.coach.diagnosis;
  const [all, setAll] = useState(false);
  if (diagnosis.analyzed_games < diagnosis.min_games) {
    return (
      <Empty title={c.fewTitle}>
        <p>{c.fewText(diagnosis.analyzed_games, diagnosis.min_games)}</p>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Link href="/" className={GREEN_LINK}>
            {c.importLink}
          </Link>
          <Link href="/games" className={RAISED_LINK}>
            {c.gamesLink}
          </Link>
        </div>
      </Empty>
    );
  }
  const byKey = new Map<string, Metric>(diagnosis.metrics.map((m) => [`${m.kind}:${m.key}`, m]));
  const find = (kind: string, key: string) => byKey.get(`${kind}:${key}`) ?? null;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <p className="text-soft">{c.subtitle}</p>
        <p className="text-sm font-semibold text-muted">{c.basis(diagnosis.analyzed_games, diagnosis.norms_version)}</p>
        {diagnosis.norms_version === "placeholder" && <p className="text-sm font-bold text-[#f59a4c]">{c.placeholderNorms}</p>}
      </div>

      <section className="flex flex-col gap-3">
        <h3 className="text-base font-extrabold">{c.weak}</h3>
        {diagnosis.weaknesses.length === 0 ? (
          <p className="text-soft">{c.noWeak}</p>
        ) : (
          diagnosis.weaknesses.map((gap) => (
            <GapCard key={`${gap.kind}:${gap.key}`} gap={gap} metric={find(gap.kind, gap.key)} currentBand={diagnosis.current_band} targetBand={diagnosis.target_band} />
          ))
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-base font-extrabold">{c.strong}</h3>
        {diagnosis.strengths.length === 0 ? (
          <p className="text-soft">{c.noStrong}</p>
        ) : (
          diagnosis.strengths.map((gap) => (
            <GapCard key={`${gap.kind}:${gap.key}`} gap={gap} metric={find(gap.kind, gap.key)} currentBand={diagnosis.current_band} targetBand={diagnosis.target_band} strength />
          ))
        )}
      </section>

      {diagnosis.metrics.length > 0 && (
        <section className="flex flex-col gap-2">
          <Button variant="raised" size="sm" onClick={() => setAll((v) => !v)} aria-expanded={all} className="self-start">
            {all ? c.hideMetrics : c.showMetrics}
          </Button>
          {all && (
            <ul className="flex flex-col divide-y divide-line rounded-lg bg-raised/40">
              {diagnosis.metrics.map((m) => (
                <li key={`${m.kind}:${m.key}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-0.5 px-3 py-2.5 text-sm">
                  <span className="min-w-0 flex-1 font-bold">{itemName(t, m.kind, m.key)}</span>
                  <span className="tabular-nums font-extrabold">{formatValue(t, lang, m.kind, m.key, m.value)}</span>
                  <span className="w-full text-xs font-semibold sm:w-auto" style={{ color: statusColor(m.status) }}>
                    {c.status[m.status]}
                    {m.target && <span className="text-muted"> · {c.targetGroup(diagnosis.target_band)}: {formatValue(t, lang, m.kind, m.key, m.target.p50)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
