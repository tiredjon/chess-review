"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { CoachTask } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button, ErrorText } from "../ui";
import { focusName } from "./copy";
import { coach } from "./source";

// Эти задания тренер не видит сам: их отмечает пользователь (SPEC «17.2», автозачёт — остальные).
export const isManual = (task: Pick<CoachTask, "kind">) => task.kind === "review" || task.kind === "lesson";

const KIND_ICONS: Record<CoachTask["kind"], string> = {
  puzzles: "M10 3.5a2 2 0 0 1 4 0V5h4a1 1 0 0 1 1 1v4h-1.5a2 2 0 0 0 0 4H19v4a1 1 0 0 1-1 1h-4v-1.5a2 2 0 0 0-4 0V19H6a1 1 0 0 1-1-1v-4h1.5a2 2 0 0 0 0-4H5V6a1 1 0 0 1 1-1h4z",
  rush: "M13 2 4 14h6l-1 8 9-12h-6z",
  endgames: "M12 3a3.5 3.5 0 0 0-2.2 6.2C8.4 10 7.5 11.3 7.5 13h2.2l-1.2 5H6v3h12v-3h-2.5l-1.2-5h2.2c0-1.7-.9-3-2.3-3.8A3.5 3.5 0 0 0 12 3z",
  course: "M3 5.5C5.5 4.3 8.5 4.3 11 5.8V20c-2.5-1.4-5.5-1.4-8-.3zM13 5.8c2.5-1.5 5.5-1.5 8-.3v14.2c-2.5-1.1-5.5-1.1-8 .3z",
  play: "M5 4h14v4H5zM7 10h10l1 10H6z",
  review: "M4 4h16v13H8l-4 4zM8 8h8v2H8zM8 12h5v2H8z",
  lesson: "M4 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H4zM20 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z",
};

export function KindIcon({ kind, className = "h-5 w-5" }: { kind: CoachTask["kind"]; className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={`${className} fill-current`}>
      <path d={KIND_ICONS[kind]} />
    </svg>
  );
}

/** Строка задания дня: вид, норма и прогресс, минуты, «Открыть» и (для разбора и урока) «Отметить». */
export function TaskRow({ task, onDone }: { task: CoachTask; onDone: (task: CoachTask) => void }) {
  const { t, lang } = useI18n();
  const c = t.coach.today;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const manual = isManual(task);
  const unit = t.coach.unit[task.unit](task.target);
  const percent = task.target > 0 ? Math.min(100, Math.round((100 * task.progress) / task.target)) : 0;

  const mark = async () => {
    setBusy(true);
    setError(null);
    try {
      onDone(await coach.completeTask(task.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : c.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`flex flex-col gap-2 rounded-lg bg-raised/50 p-3 ${task.done ? "opacity-75" : ""}`}>
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${task.done ? "bg-green text-white" : "bg-sunken text-soft"}`}
        >
          {task.done ? (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="m5 12.5 4.5 4.5L19 7.5" />
            </svg>
          ) : (
            <KindIcon kind={task.kind} />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-2 font-extrabold">
            <span className={task.done ? "line-through decoration-muted" : ""}>{t.coach.task[task.kind]}</span>
            <span className="text-sm font-semibold text-muted">{t.coach.plan.minutes(task.minutes)}</span>
          </p>
          <p className="text-sm font-semibold text-soft">
            {task.done ? `${c.marked}: ${task.target} ${unit}` : `${c.progress(task.progress, task.target)} ${unit}`}
            {task.focus && <span className="text-muted"> · {c.focus(focusName(t, task.focus, lang))}</span>}
          </p>
          {!task.done && !manual && task.target > 0 && (
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-green" style={{ width: `${Math.max(percent, 2)}%` }} />
            </div>
          )}
          <p className="mt-1 text-xs font-semibold text-muted">{manual ? c.manual : c.auto}</p>
        </div>
      </div>
      {!task.done && (
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Link
            href={task.href}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-green px-5 text-[15px] font-bold text-white shadow-[0_4px_0_0_var(--green-edge)] hover:bg-green-hover active:translate-y-[2px] active:shadow-none"
          >
            {c.open}
          </Link>
          {manual && (
            <Button variant="raised" disabled={busy} onClick={() => void mark()} className="min-h-11 px-5">
              {c.mark}
            </Button>
          )}
        </div>
      )}
      <ErrorText>{error}</ErrorText>
    </li>
  );
}
