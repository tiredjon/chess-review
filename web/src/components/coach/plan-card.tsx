"use client";

import Link from "next/link";
import type { Plan } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Panel } from "../ui";
import { BlockBody, Empty } from "./block";
import { focusName, formatDay, formatShortDay, itemName } from "./copy";
import { KindIcon } from "./task-row";
import type { Section } from "./use-section";

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** «План недели»: дни × задания, распределение времени по видам, фокус и дата пересборки. */
export function PlanCard({ section }: { section: Section<Plan> }) {
  const { t, lang } = useI18n();
  const c = t.coach.plan;
  return (
    <Panel title={c.title} aside={section.data ? <span className="text-sm font-semibold text-muted">{c.week(formatShortDay(section.data.week_start, lang))}</span> : undefined}>
      <BlockBody section={section} height={260}>
        {(plan) => <PlanBody plan={plan} />}
      </BlockBody>
    </Panel>
  );
}

function PlanBody({ plan }: { plan: Plan }) {
  const { t, lang } = useI18n();
  const c = t.coach.plan;
  if (plan.days.length === 0) return <Empty title={c.empty} />;
  const today = todayIso();
  return (
    <div className="flex flex-col gap-5">
      {/* Телефон: дни лентой прокрутки вбок; от sm — сетка из семи колонок. */}
      <ul className="-mx-4 flex snap-x gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-7 sm:overflow-visible sm:px-0 sm:pb-0">
        {plan.days.map((day, i) => {
          const isToday = day.day === today;
          return (
            <li
              key={day.day}
              className={`flex w-36 shrink-0 snap-start flex-col gap-1.5 rounded-lg bg-raised/40 p-2.5 sm:w-auto sm:min-w-0 ${isToday ? "ring-2 ring-green ring-inset" : ""}`}
            >
              <p className="flex items-baseline justify-between gap-1 text-xs font-extrabold">
                <span>{c.weekdays[i] ?? formatShortDay(day.day, lang)}</span>
                <span className="font-semibold text-muted">{isToday ? c.today : formatShortDay(day.day, lang)}</span>
              </p>
              {day.rest_day || day.tasks.length === 0 ? (
                <p className="py-3 text-center text-sm font-semibold text-muted">{c.rest}</p>
              ) : (
                <>
                  <ul className="flex flex-col gap-1">
                    {day.tasks.map((task) => (
                      <li key={task.id} className="min-w-0">
                        <Link
                          href={task.href}
                          title={t.coach.task[task.kind]}
                          className={`flex min-w-0 items-center gap-1.5 rounded-md bg-sunken/70 px-1.5 py-1 text-xs font-bold hover:bg-sunken ${task.done ? "text-green" : "text-soft"}`}
                        >
                          <KindIcon kind={task.kind} className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{t.coach.task[task.kind]}</span>
                          <span className="ml-auto shrink-0 tabular-nums text-muted">{task.done ? "✓" : task.minutes}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-auto text-xs font-semibold text-muted">{c.minutes(day.minutes)}</p>
                </>
              )}
            </li>
          );
        })}
      </ul>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-bold text-muted">{c.allocationTitle}</h3>
        <ul className="flex flex-col gap-2">
          {plan.allocation.map((a) => (
            <li key={a.kind} className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_auto] items-center gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 font-semibold text-soft">
                <KindIcon kind={a.kind} className="h-4 w-4 shrink-0" />
                <span className="truncate">{t.coach.task[a.kind]}</span>
              </span>
              <span className="h-2.5 overflow-hidden rounded-full bg-sunken">
                <span className="block h-full rounded-full bg-green" style={{ width: `${Math.max(2, Math.round(a.share * 100))}%` }} />
              </span>
              <span className="text-right text-xs font-semibold tabular-nums text-muted">{c.perWeek(a.minutes_per_week)}</span>
              {a.focus.length > 0 && (
                <span className="col-span-3 -mt-1 truncate pl-6 text-xs font-semibold text-muted">{a.focus.map((f) => focusName(t, f, lang)).join(", ")}</span>
              )}
            </li>
          ))}
        </ul>
      </section>

      {plan.focus.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-bold text-muted">{c.focusTitle}</h3>
          <ul className="flex flex-wrap gap-1.5">
            {plan.focus.map((gap) => (
              <li key={`${gap.kind}:${gap.key}`} className="rounded-md bg-raised px-2.5 py-1 text-sm font-bold text-soft">
                {itemName(t, gap.kind, gap.key)}
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-sm font-semibold text-muted">{c.nextRebuild(formatDay(plan.next_rebuild, lang))}</p>
    </div>
  );
}
