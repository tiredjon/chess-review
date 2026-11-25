"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { coursesApi, isBuilding, type CourseOut } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { trainerApi, type CourseSummary } from "@/lib/trainer-api";
import { Button, ErrorText, Panel } from "../ui";
import { buildErrorText, ColorMark, errorText, ProgressBar, rebuildCourse } from "./shared";

const POLL_MS = 3000;

type Data = { courses: CourseOut[]; summary: Map<string, CourseSummary> };

/** «Мои курсы»: статус и прогресс сборки, сводка тренажёра, открыть / тренировать / убрать. */
export function MyCourses() {
  const { t } = useI18n();
  const l = t.courses.mine;
  const [data, setData] = useState<Data | null>(null);
  // Ошибка — как есть: текст берётся из словаря при рендере (язык мог смениться).
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([coursesApi.list(), trainerApi.summary()])
      .then(([courses, summary]) => {
        if (cancelled) return;
        setData({ courses, summary: new Map(summary.map((row) => [row.course_id, row])) });
        setError(null);
      })
      .catch((err) => !cancelled && setError(err ?? true));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // Пока какой-то курс собирается — опрос списка.
  const building = data?.courses.some(isBuilding) ?? false;
  useEffect(() => {
    if (!building) return;
    const timer = setInterval(() => {
      coursesApi
        .list()
        .then((courses) => setData((prev) => (prev ? { ...prev, courses } : prev)))
        .catch(() => undefined);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [building]);

  const removed = useCallback((id: string) => {
    setData((prev) => (prev ? { ...prev, courses: prev.courses.filter((course) => course.id !== id) } : prev));
  }, []);
  const replaced = useCallback((next: CourseOut) => {
    setData((prev) => (prev ? { ...prev, courses: prev.courses.map((course) => (course.id === next.id ? next : course)) } : prev));
  }, []);

  return (
    <Panel title={l.title}>
      {error && !data ? (
        <div>
          <ErrorText>{errorText(t, error, l.loadError)}</ErrorText>
          <Button variant="raised" className="mt-3" onClick={() => setAttempt((n) => n + 1)}>
            {t.courses.retry}
          </Button>
        </div>
      ) : !data ? (
        <div aria-busy className="grid gap-2 sm:grid-cols-2">
          <div className="h-28 animate-pulse rounded-lg bg-raised/50" />
          <div className="h-28 animate-pulse rounded-lg bg-raised/50 max-sm:hidden" />
        </div>
      ) : data.courses.length === 0 ? (
        <p className="text-soft">{l.empty}</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {data.courses.map((course) => (
            <li key={course.id}>
              <CourseCard course={course} summary={data.summary.get(course.id)} onRemoved={removed} onReplaced={replaced} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function CourseCard({
  course,
  summary,
  onRemoved,
  onReplaced,
}: {
  course: CourseOut;
  summary: CourseSummary | undefined;
  onRemoved: (id: string) => void;
  onReplaced: (course: CourseOut) => void;
}) {
  const { t } = useI18n();
  const l = t.courses.mine;
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const href = `/openings/courses/${course.id}`;
  const [family, ...rest] = course.name.split(":");

  const rebuild = async () => {
    setBusy(true);
    setError(null);
    try {
      onReplaced(await rebuildCourse(course));
    } catch (err) {
      setError(errorText(t, err, t.courses.building.rebuildError));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await coursesApi.remove(course.id);
      onRemoved(course.id);
    } catch (err) {
      setError(errorText(t, err, l.removeError));
      setBusy(false);
    }
  };

  return (
    <article className="flex h-full flex-col gap-2.5 rounded-lg bg-raised/50 p-3">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-sunken">
          <ColorMark color={course.color} size={26} />
        </span>
        <div className="min-w-0 flex-1">
          <Link href={href} className="block text-[15px] leading-snug font-bold hover:underline">
            {rest.length > 0 ? rest.join(":").trim() : family}
          </Link>
          <p className="truncate text-xs text-muted">
            {rest.length > 0 ? `${family} · ` : ""}
            {course.eco ? `${course.eco} · ` : ""}
            {course.color === "white" ? t.courses.color.whiteShort : t.courses.color.blackShort}
            {course.source === "repertoire" ? ` · ${l.fromRepertoire}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setConfirm(true)}
          aria-label={l.remove}
          title={l.remove}
          className="-mt-1 -mr-1 flex size-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-raised hover:text-ink"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
          </svg>
        </button>
      </div>

      <Status course={course} summary={summary} />

      {confirm ? (
        <div className="mt-auto flex flex-col gap-2 rounded-md bg-sunken/70 p-2.5">
          <p className="text-sm text-soft">{l.removeConfirm}</p>
          <div className="flex gap-2">
            <Button size="sm" variant="raised" onClick={() => setConfirm(false)} disabled={busy} className="flex-1">
              {l.removeNo}
            </Button>
            <Button size="sm" onClick={remove} disabled={busy} className="flex-1 !bg-danger !shadow-[0_3px_0_0_#a8473a]">
              {l.removeYes}
            </Button>
          </div>
          <ErrorText>{error}</ErrorText>
        </div>
      ) : (
        <div className="mt-auto flex gap-2">
          <Link
            href={href}
            className="inline-flex min-h-9 flex-1 items-center justify-center rounded-lg bg-raised px-3 text-sm font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink"
          >
            {l.open}
          </Link>
          {course.status === "failed" && (
            <Button size="sm" onClick={rebuild} disabled={busy} className="flex-1">
              {busy ? t.courses.building.rebuildBusy : t.courses.building.rebuild}
            </Button>
          )}
          {course.status === "ready" && (
            <Link
              href={`/openings/train?course=${course.id}`}
              className="inline-flex min-h-9 flex-1 items-center justify-center rounded-lg bg-green px-3 text-sm font-bold text-white shadow-[0_3px_0_0_var(--green-edge)] hover:bg-green-hover"
            >
              {l.train}
            </Link>
          )}
        </div>
      )}
      {!confirm && <ErrorText>{error}</ErrorText>}
    </article>
  );
}

function Status({ course, summary }: { course: CourseOut; summary: CourseSummary | undefined }) {
  const { t } = useI18n();
  const l = t.courses.mine;
  if (course.status === "queued" || course.status === "building") {
    return (
      <div>
        <p className="mb-1.5 text-xs font-semibold text-soft">
          {course.status === "queued" ? l.status.queued : l.status.building(course.progress)}
        </p>
        <ProgressBar value={course.status === "queued" ? 2 : course.progress} />
      </div>
    );
  }
  if (course.status === "failed") {
    return (
      <p className="text-xs">
        <span className="font-bold text-danger">{l.status.failed}</span>{" "}
        <span className="text-muted">{buildErrorText(t, course.error_code)}</span>
      </p>
    );
  }
  if (!summary || summary.total === 0) return <p className="text-xs text-muted">{l.notStarted}</p>;
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-xs font-semibold">
        {summary.due > 0 && <span className="text-[#f59a4c]">{l.due(summary.due)}</span>}
        {summary.new > 0 && <span className="text-soft">{l.fresh(summary.new)}</span>}
        <span className="text-muted">{l.learned(summary.learned, summary.total)}</span>
      </div>
      <div
        role="img"
        aria-label={l.progressLabel(summary.learned, summary.total)}
        className="h-1.5 overflow-hidden rounded-full bg-sunken"
      >
        <span className="block h-full rounded-full bg-green" style={{ width: `${(summary.learned / summary.total) * 100}%` }} />
      </div>
    </div>
  );
}
