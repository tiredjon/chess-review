"use client";

import type { CoachTask, Today } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Panel } from "../ui";
import { BlockBody, Empty } from "./block";
import { TaskRow } from "./task-row";
import type { Section } from "./use-section";

/** «Сегодня»: чек-лист заданий, сводка минут, серия; выходной день. */
export function TodayCard({ section }: { section: Section<Today> }) {
  const { t } = useI18n();
  const c = t.coach.today;

  const onDone = (task: CoachTask) => {
    const today = section.data;
    if (!today) return;
    const tasks = today.tasks.map((item) => (item.id === task.id ? task : item));
    section.setData({
      ...today,
      tasks,
      minutes_done: tasks.filter((item) => item.done).reduce((sum, item) => sum + item.minutes, 0),
    });
  };

  return (
    <Panel title={c.title} aside={section.data && !section.data.rest_day ? <Summary today={section.data} /> : undefined}>
      <BlockBody section={section} height={220}>
        {(today) =>
          today.rest_day ? (
            <Empty title={c.restTitle}>
              <p>{c.restText}</p>
              <Streak days={today.streak_days} />
            </Empty>
          ) : today.tasks.length === 0 ? (
            <Empty title={c.noTasks} />
          ) : (
            <div className="flex flex-col gap-3">
              {today.tasks.every((task) => task.done) && <p className="rounded-lg bg-green/15 px-3 py-2 font-bold text-green">{c.allDone}</p>}
              <div
                className="h-2 overflow-hidden rounded-full bg-sunken"
                role="progressbar"
                aria-valuenow={today.minutes_done}
                aria-valuemin={0}
                aria-valuemax={today.minutes_total}
              >
                <div
                  className="h-full rounded-full bg-green"
                  style={{ width: `${today.minutes_total > 0 ? Math.max(2, Math.round((100 * today.minutes_done) / today.minutes_total)) : 0}%` }}
                />
              </div>
              <ul className="flex flex-col gap-2">
                {today.tasks.map((task) => (
                  <TaskRow key={task.id} task={task} onDone={onDone} />
                ))}
              </ul>
              <Streak days={today.streak_days} />
            </div>
          )
        }
      </BlockBody>
    </Panel>
  );
}

function Summary({ today }: { today: Today }) {
  const { t } = useI18n();
  const done = today.tasks.filter((task) => task.done).length;
  return (
    <p className="text-right text-sm font-bold text-soft">
      {t.coach.today.done(done, today.tasks.length)}
      <span className="block text-xs font-semibold text-muted">{t.coach.today.minutes(today.minutes_done, today.minutes_total)}</span>
    </p>
  );
}

function Streak({ days }: { days: number }) {
  const { t } = useI18n();
  return (
    <p className="flex items-center gap-1.5 text-sm font-semibold text-muted">
      <span aria-hidden className={days > 0 ? "text-[#f59a4c]" : ""}>
        ●
      </span>
      {days > 0 ? t.coach.today.streak(days) : t.coach.today.noStreak}
    </p>
  );
}
