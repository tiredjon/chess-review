"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { Goal, GoalState } from "@/lib/coach-api";
import { SOURCE_NAMES } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button, ErrorText } from "../ui";
import { BlockBody } from "./block";
import { DiagnosisCard } from "./diagnosis-card";
import { ForecastCard } from "./forecast-card";
import { GoalWizard } from "./goal-wizard";
import { PlanCard } from "./plan-card";
import { ReportCard } from "./report-card";
import { COACH_MOCK, coach } from "./source";
import { TodayCard } from "./today-card";
import { useSection } from "./use-section";

export function CoachHeading() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-extrabold sm:text-3xl">{t.coach.title}</h1>
      <p className="max-w-3xl text-soft">{t.coach.subtitle}</p>
      {COACH_MOCK && <p className="w-fit rounded-md bg-[#f59a4c]/20 px-2 py-0.5 text-xs font-extrabold text-[#f59a4c]">{t.coach.mockBadge}</p>}
    </div>
  );
}

/** Тренер: нет цели — мастер цели, есть цель — «Сегодня», «Прогноз», стороны, план, отчёт. */
export function CoachView() {
  const { t } = useI18n();
  const state = useSection(coach.goal, t.coach.loadError);
  return (
    <BlockBody section={state} height={320}>
      {(data) =>
        data.goal === null ? (
          <GoalWizard state={data} onSaved={state.reload} />
        ) : (
          <Dashboard key={`${data.goal.id}-${data.goal.target_rating}-${data.goal.minutes_per_day}-${data.goal.days_per_week}-${data.goal.time_class}`} state={data} goal={data.goal} onChanged={state.reload} />
        )
      }
    </BlockBody>
  );
}

function Dashboard({ state, goal, onChanged }: { state: GoalState; goal: Goal; onChanged: () => void }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const today = useSection(coach.today, t.coach.sectionError);
  const forecast = useSection(coach.forecast, t.coach.sectionError);
  const diagnosis = useSection(coach.diagnosis, t.coach.sectionError);
  const plan = useSection(coach.plan, t.coach.sectionError);
  const report = useSection(coach.report, t.coach.sectionError);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const rebuild = async () => {
    setRebuilding(true);
    setError(null);
    setNotice(null);
    try {
      const before = plan.data?.created_at;
      const next = await coach.rebuildPlan();
      // План моложе часа бэкенд не пересобирает и возвращает как есть — скажем об этом.
      if (before !== undefined && next.created_at === before) setNotice(t.coach.head.rebuildTooSoon);
      plan.setData(next);
      today.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.coach.head.rebuildFailed);
    } finally {
      setRebuilding(false);
    }
  };

  if (editing) {
    return (
      <GoalWizard
        state={state}
        current={goal}
        onSaved={() => {
          setEditing(false);
          onChanged();
        }}
        onCancel={() => setEditing(false)}
        onRemoved={() => {
          setEditing(false);
          onChanged();
        }}
      />
    );
  }

  const head = t.coach.head;
  return (
    <div className="flex flex-col gap-4">
      <section aria-label={t.coach.title} className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl bg-panel px-4 py-3 sm:px-5">
        <div className="min-w-0 flex-1 basis-60">
          <p className="text-xl font-extrabold">
            {head.goal(`${SOURCE_NAMES[goal.source]} · ${t.stats.timeClasses[goal.time_class]}`, goal.start_rating, goal.target_rating)}
          </p>
          <p className="text-sm font-semibold text-muted">
            {goal.achieved_at ? head.achieved : head.now(goal.current_rating)} · {head.pace(goal.minutes_per_day, goal.days_per_week)}
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Button variant="raised" onClick={() => setEditing(true)} className="min-h-11 px-5">
            {head.edit}
          </Button>
          <Button variant="raised" onClick={() => void rebuild()} disabled={rebuilding} className="min-h-11 px-5">
            {rebuilding ? head.rebuilding : head.rebuild}
          </Button>
        </div>
        {error && <ErrorText>{error}</ErrorText>}
        {notice && <p className="w-full text-sm font-semibold text-muted">{notice}</p>}
      </section>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2 lg:items-start">
        <TodayCard section={today} />
        <ForecastCard section={forecast} />
      </div>
      <DiagnosisCard section={diagnosis} />
      <PlanCard section={plan} />
      <ReportCard section={report} />
    </div>
  );
}
