import Link from "next/link";
import { SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { GameSource, TimeClass } from "@/lib/types";

// Без "use client": страница (серверная) берёт отсюда список ключей, а подписи — словарь
// `stats.timeClasses`; сами фильтры рисуются только внутри клиентского дашборда.
export const TIME_CLASSES: TimeClass[] = ["bullet", "blitz", "rapid", "daily"];

type Filters = { source: GameSource | null; timeClass: TimeClass | null };

function href({ source, timeClass }: Filters) {
  const query = new URLSearchParams();
  if (source) query.set("source", source);
  if (timeClass) query.set("tc", timeClass);
  const qs = query.toString();
  return qs ? `/stats?${qs}` : "/stats";
}

/** Фильтры одной строкой над всеми блоками: источник и контроль времени (в URL). */
export function StatsFilters(current: Filters) {
  const { t } = useI18n();
  const sources: [GameSource | null, string][] = [
    [null, t.stats.filters.allSources],
    ...(Object.entries(SOURCE_NAMES) as [GameSource, string][]),
  ];
  const classes: [TimeClass | null, string][] = [
    [null, t.stats.filters.anyTimeControl],
    ...TIME_CLASSES.map((timeClass): [TimeClass, string] => [timeClass, t.stats.timeClasses[timeClass]]),
  ];
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-5">
      <ChipRow label={t.stats.filters.source}>
        {sources.map(([source, label]) => (
          <FilterChip key={source ?? "all"} href={href({ ...current, source })} active={current.source === source}>
            {label}
          </FilterChip>
        ))}
      </ChipRow>
      <ChipRow label={t.stats.filters.timeControl}>
        {classes.map(([timeClass, label]) => (
          <FilterChip key={timeClass ?? "all"} href={href({ ...current, timeClass })} active={current.timeClass === timeClass}>
            {label}
          </FilterChip>
        ))}
      </ChipRow>
    </div>
  );
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <nav aria-label={label} className="flex flex-wrap gap-1.5">
      {children}
    </nav>
  );
}

function FilterChip({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-9 items-center rounded-lg px-3 text-sm font-semibold ${
        active ? "bg-raised text-ink ring-2 ring-green ring-inset" : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}
