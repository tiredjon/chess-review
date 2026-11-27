"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Forecast, Goal, Today } from "@/lib/coach-api";
import { SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import { formatDay } from "./copy";
import { coach } from "./source";

type Data = { goal: Goal | null; today: Today | null; forecast: Forecast | null };

/** Карточка на главной: цель, «сегодня X из Y», срок p50 → /coach; без цели — приглашение поставить. */
export function CoachCard() {
  const { t, lang } = useI18n();
  const c = t.coach.card;
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const state = await coach.goal();
      if (state.goal === null) return { goal: null, today: null, forecast: null };
      const [today, forecast] = await Promise.all([coach.today().catch(() => null), coach.forecast().catch(() => null)]);
      return { goal: state.goal, today, forecast };
    })()
      .then((next) => !cancelled && setData(next))
      .catch(() => !cancelled && setData({ goal: null, today: null, forecast: null }));
    return () => {
      cancelled = true;
    };
  }, []);

  if (data === null) return <div className="h-[76px] animate-pulse rounded-xl bg-panel" />;
  const { goal, today, forecast } = data;
  let detail: string | null = null;
  if (goal && !goal.achieved_at) {
    const parts: string[] = [];
    if (today) {
      const done = today.tasks.filter((task) => task.done).length;
      parts.push(today.rest_day ? c.rest : c.today(done, today.tasks.length));
    }
    if (forecast) parts.push(forecast.date_p50 ? c.eta(formatDay(forecast.date_p50, lang)) : forecast.status === "insufficient" ? c.noEta : c.noEta);
    detail = parts.join(" · ") || null;
  } else if (goal) detail = c.achieved;

  return (
    <section aria-label={c.label} className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl bg-panel px-4 py-3 sm:px-5">
      <CoachIcon />
      <div className="min-w-0 flex-1">
        <p className={`text-lg font-extrabold ${goal ? "truncate" : ""}`}>
          {goal ? c.goal(`${SOURCE_NAMES[goal.source]} · ${t.stats.timeClasses[goal.time_class]}`, goal.start_rating, goal.target_rating) : c.noGoalTitle}
        </p>
        <p className="text-sm font-semibold text-muted">{goal ? detail : c.noGoalText}</p>
      </div>
      <Link
        href="/coach"
        className="flex min-h-11 items-center justify-center rounded-lg bg-raised px-5 text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink max-sm:w-full"
      >
        {goal ? c.open : c.setGoal}
      </Link>
    </section>
  );
}

/** Мишень — как значок пункта меню «Тренер». */
export function CoachIcon() {
  return (
    <span aria-hidden className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-raised text-green">
      <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
        <path
          fillRule="evenodd"
          d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"
        />
      </svg>
    </span>
  );
}
