"use client";

import { CLASS_COLORS, phaseClass } from "@/lib/classes";
import { formatSpent } from "@/lib/clock";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { TimeStats } from "@/lib/types";
import { Panel } from "../ui";

const TROUBLE = "#e06c5a";

/** Время на ход: точность и ошибки по остатку на часах, цейтнот, поспешные ошибки, фазы. */
export function TimePanel({ time }: { time: TimeStats }) {
  const { t } = useI18n();
  const s = t.stats.time;
  const ofErrors = (n: number) => (time.errors > 0 ? s.ofErrors(Math.round((100 * n) / time.errors), time.errors) : s.noErrors);
  const calm = time.buckets.find((bucket) => bucket.bucket === "over_half")?.errors_per_100 ?? null;
  const rush = time.buckets.find((bucket) => bucket.bucket === "under_tenth")?.errors_per_100 ?? null;
  const ratio = calm && rush ? rush / calm : null;

  return (
    <Panel title={s.title} aside={<span className="text-xs font-semibold text-muted">{t.common.games(time.games)}</span>}>
      <div className="grid gap-3 sm:grid-cols-3">
        <Tile label={s.troubleErrors} value={`${time.trouble_errors}`} note={ofErrors(time.trouble_errors)} warn={time.trouble_errors > 0} />
        <Tile label={s.hastyErrors} value={`${time.hasty_errors}`} note={ofErrors(time.hasty_errors)} warn={time.hasty_errors > 0} />
        <Tile label={s.troubleGames} value={`${time.trouble_games}`} note={s.ofGames(time.games)} />
      </div>
      {ratio !== null && ratio >= 1.5 && <p className="mt-4 font-bold">{s.ratio(ratio.toFixed(1))}</p>}

      <h3 className="mt-5 mb-3 text-sm font-bold text-soft">{s.bucketsTitle}</h3>
      <ul className="flex flex-col gap-3">
        {time.buckets.map((bucket) => {
          const color =
            bucket.accuracy === null ? "transparent" : bucket.bucket === "under_tenth" ? TROUBLE : CLASS_COLORS[phaseClass(bucket.accuracy)];
          return (
            <li key={bucket.bucket} className="grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)_3rem_5.5rem] items-center gap-2 text-sm">
              <span className="flex flex-col">
                <span className="truncate font-semibold">{s.buckets[bucket.bucket]}</span>
                <span className="text-xs text-muted">{s.moves(bucket.moves)}</span>
              </span>
              <div className="h-2 w-full overflow-hidden rounded-full bg-sunken">
                <div className="h-full rounded-full" style={{ width: `${bucket.accuracy ?? 0}%`, background: color }} />
              </div>
              <span className="text-right font-extrabold">{bucket.accuracy === null ? "—" : bucket.accuracy.toFixed(1)}</span>
              <span className="text-right text-xs whitespace-nowrap text-soft" title={s.errorsHint}>
                {bucket.errors_per_100 === null ? "—" : s.errorsPer100(bucket.errors_per_100.toFixed(1))}
              </span>
            </li>
          );
        })}
      </ul>

      <h3 className="mt-5 mb-3 text-sm font-bold text-soft">{s.phasesTitle}</h3>
      <dl className="grid grid-cols-3 gap-3">
        {time.phases.map((phase) => (
          <div key={phase.phase} className="rounded-lg bg-sunken px-3 py-2">
            <dt className="text-xs font-semibold text-muted">{t.common.phases[phase.phase]}</dt>
            <dd className="text-lg font-extrabold">{phase.avg_spent_cs === null ? "—" : formatSpent(phase.avg_spent_cs, t)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-muted">{s.note}</p>
    </Panel>
  );
}

function Tile({ label, value, note, warn = false }: { label: string; value: string; note: string; warn?: boolean }) {
  return (
    <div className="rounded-lg bg-sunken px-3 py-2.5">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="text-2xl font-extrabold" style={warn ? { color: "#f08a78" } : undefined}>
        {value}
      </p>
      <p className="text-xs text-soft">{note}</p>
    </div>
  );
}
