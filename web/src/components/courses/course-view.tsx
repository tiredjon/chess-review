"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { coursesApi, isBuilding, type CourseDetail, type CourseNode, type CourseTree, type ModelGame } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { trainerApi } from "@/lib/trainer-api";
import { OpeningBoard } from "../openings/opening-board";
import { LineSwitcher, OpeningControls, OpeningTree } from "../openings/opening-tree";
import { indexNodes } from "../openings/types";
import { useOpeningNav } from "../openings/use-opening-nav";
import { Button, ErrorText, Panel } from "../ui";
import { GameViewer } from "./game-viewer";
import { Bulb, NodePanel } from "./node-panel";
import { buildErrorText, ColorMark, errorText, ProgressBar, rebuildCourse } from "./shared";

const POLL_MS = 2000;
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 15rem))" };

/** Страница курса: сборка (опрос) → дерево на доске, идеи, мастера, партии, «Тренировать». */
export function CourseView({ id, initialNode }: { id: string; initialNode: number | null }) {
  const { t, lang } = useI18n();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  // Курс на языке интерфейса (тексты идей); при смене языка — заново.
  useEffect(() => {
    let cancelled = false;
    coursesApi
      .course(id, lang)
      .then((value) => {
        if (cancelled) return;
        setCourse(value);
        setError(null);
      })
      .catch((err) => !cancelled && setError(err ?? true));
    return () => {
      cancelled = true;
    };
  }, [id, lang, attempt]);

  // Пока курс собирается — опрос.
  const building = course !== null && isBuilding(course);
  useEffect(() => {
    if (!building) return;
    const timer = setTimeout(() => setAttempt((n) => n + 1), POLL_MS);
    return () => clearTimeout(timer);
  }, [building, course]);

  if (error && !course) {
    const missing = error instanceof ApiError && error.code === "course_not_found";
    return (
      <Panel>
        <ErrorText>{errorText(t, error, t.courses.page.loadError)}</ErrorText>
        <div className="mt-3 flex gap-2">
          {!missing && (
            <Button variant="raised" onClick={() => setAttempt((n) => n + 1)}>
              {t.courses.retry}
            </Button>
          )}
          <Link href="/openings/courses" className="inline-flex min-h-10 items-center px-2 font-bold text-green hover:underline">
            {t.courses.building.toCatalog}
          </Link>
        </div>
      </Panel>
    );
  }
  if (!course) return <CourseSkeleton />;
  if (course.status !== "ready" || !course.tree) return <Building course={course} onRequeued={() => setAttempt((n) => n + 1)} />;
  return <Explorer course={course} tree={course.tree} initialNode={initialNode} />;
}

export function Building({ course, onRequeued }: { course: CourseDetail; onRequeued: () => void }) {
  const { t } = useI18n();
  const l = t.courses.building;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rebuild = async () => {
    setBusy(true);
    setError(null);
    try {
      await rebuildCourse(course);
      onRequeued();
    } catch (err) {
      setError(errorText(t, err, l.rebuildError));
    } finally {
      setBusy(false);
    }
  };
  const failed = course.status === "failed";
  const progress = course.status === "queued" ? 2 : course.progress;
  // Шаги сборки — по прогрессу, примерно поровну.
  const step = Math.min(l.steps.length - 1, Math.floor((progress / 100) * l.steps.length));
  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-3">
      <CourseHeading course={course} />
      <section className="rounded-xl bg-panel p-5">
        {failed ? (
          <>
            <p className="text-lg font-extrabold text-danger">{l.failed}</p>
            <p className="mt-1 text-soft">{buildErrorText(t, course.error_code)}</p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button onClick={rebuild} disabled={busy}>
                {busy ? l.rebuildBusy : l.rebuild}
              </Button>
              <Link href="/openings/courses" className="font-bold text-green hover:underline">
                {l.toCatalog}
              </Link>
            </div>
            <div className="mt-2">
              <ErrorText>{error}</ErrorText>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-lg font-extrabold">{course.status === "queued" ? l.queued : l.title}</p>
              <span className="text-sm font-bold text-soft tabular-nums">{progress}%</span>
            </div>
            <ProgressBar value={progress} className="mt-3 h-3" />
            <ol className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {l.steps.map((label, index) => (
                <li
                  key={label}
                  className={`rounded-lg px-2.5 py-2 text-xs font-bold ${
                    index < step ? "bg-green/15 text-green" : index === step ? "bg-raised text-ink" : "bg-sunken/60 text-muted"
                  }`}
                >
                  {index < step ? "✓ " : index === step ? <span className="mr-1 inline-block size-2 animate-pulse rounded-full bg-green" /> : null}
                  {label}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-sm leading-snug text-muted">{l.text}</p>
          </>
        )}
      </section>
    </div>
  );
}

/** Название курса: «Najdorf Variation» крупно, семейство и цвет — мелко. */
export function CourseHeading({ course, aside }: { course: CourseDetail; aside?: ReactNode }) {
  const { t } = useI18n();
  const [family, ...rest] = course.name.split(":");
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-panel">
        <ColorMark color={course.color} size={32} />
      </span>
      <div className="min-w-0 flex-1">
        <h1 className="text-xl leading-tight font-extrabold">{rest.length > 0 ? rest.join(":").trim() : family}</h1>
        <p className="text-sm text-muted">
          {rest.length > 0 ? `${family} · ` : ""}
          {course.eco ? `${course.eco} · ` : ""}
          {t.courses.color.label.toLowerCase()} {t.courses.color[course.color].toLowerCase()}
        </p>
      </div>
      {aside}
    </div>
  );
}

function Explorer({ course, tree, initialNode }: { course: CourseDetail; tree: CourseTree; initialNode: number | null }) {
  const { t } = useI18n();
  const l = t.courses.page;
  const router = useRouter();
  const index = useMemo(() => indexNodes(tree.nodes), [tree]);
  // В дереве название дебюта — только новое для линии (база дебютов на переходах «мигает»
  // между общим и точным названием, иначе оно стоит почти у каждого хода).
  const treeIndex = useMemo(() => {
    const seen = new Map<number, ReadonlySet<string>>();
    return indexNodes(
      tree.nodes.map((n) => {
        const above = (n.parent !== null ? seen.get(n.parent) : undefined) ?? new Set<string>();
        const fresh = n.name !== null && !above.has(n.name);
        seen.set(n.id, fresh ? new Set([...above, n.name!]) : above);
        return fresh ? n : { ...n, name: null };
      }),
    );
  }, [tree]);
  const [currentId, setCurrentId] = useState(() =>
    initialNode !== null && index.has(initialNode) ? initialNode : index.has(tree.line_end) ? tree.line_end : (tree.nodes[0]?.id ?? 0),
  );
  const [game, setGame] = useState<ModelGame | null>(null);
  const [training, setTraining] = useState(false);
  const [trainError, setTrainError] = useState<string | null>(null);

  const select = useCallback((id: number) => {
    setCurrentId(id);
    setGame(null);
  }, []);
  const nav = useOpeningNav(index, currentId, select, { keyboard: game === null });
  const node = index.get(currentId);

  // Стрелки: ход ученика — полная, ответы соперника — по доле у мастеров.
  const weights = useMemo(() => {
    const children = (node?.children ?? []).flatMap((id) => index.get(id) ?? []);
    const top = Math.max(0.01, ...children.filter((c) => c.mover === "opponent").map((c) => c.weight));
    return Object.fromEntries(children.map((child) => [child.id, child.mover === "opponent" ? child.weight / top : 1]));
  }, [index, node]);

  const cards = useMemo(
    () => tree.nodes.filter((n) => n.children.some((id) => index.get(id)?.mover === "learner")).length,
    [tree, index],
  );

  const train = async () => {
    setTraining(true);
    setTrainError(null);
    try {
      await trainerApi.start(course.id);
      router.push(`/openings/train?course=${course.id}`);
    } catch (err) {
      setTrainError(errorText(t, err, t.trainer.loadError));
      setTraining(false);
    }
  };

  const meta = (n: CourseNode) => {
    const siblings = n.parent !== null ? (index.get(n.parent)?.children.length ?? 0) : 0;
    const hasIdeas = course.ideas_text[String(n.id)] !== undefined;
    if (!hasIdeas && !(n.mover === "opponent" && siblings > 1) && n.id !== tree.line_end) return null;
    return (
      <>
        {n.mover === "opponent" && siblings > 1 && (
          <span className="text-xs font-semibold text-muted">{Math.round(n.weight * 100)}%</span>
        )}
        {n.id === tree.line_end && <Flag />}
        {hasIdeas && <Bulb className="size-3.5" />}
      </>
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <CourseHeading
        course={course}
        aside={
          <div className="flex w-full flex-col items-stretch gap-1 sm:w-auto sm:items-end">
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <Button onClick={train} disabled={training} className="sm:min-w-44">
                {training ? l.trainBusy : l.train}
              </Button>
              <Link
                href={`/openings/courses/${course.id}/play?node=${currentId}`}
                className="inline-flex min-h-10 items-center justify-center rounded-lg bg-raised px-4 text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink active:translate-y-[2px] active:shadow-none"
              >
                {t.courses.play.button}
              </Link>
            </div>
            <p className="text-xs text-muted">{l.trainHint(cards)}</p>
            <ErrorText>{trainError}</ErrorText>
          </div>
        }
      />

      <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(340px,460px)] xl:grid-cols-[minmax(0,1fr)_minmax(380px,500px)]">
        <div className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-3">
          <div className="mx-auto w-full" style={BOARD_WIDTH}>
            {game ? (
              <GameViewer
                key={game.id}
                game={game}
                orientation={tree.color}
                startPly={index.get(game.node_id)?.ply ?? 0}
                onClose={() => setGame(null)}
              />
            ) : (
              <>
                <OpeningBoard index={index} currentId={currentId} orientation={tree.color} onSelect={select} weights={weights} />
                <OpeningControls nav={nav} className="mt-2" />
                <LineSwitcher nav={nav} className="mt-2" />
                <p className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1 w-5 rounded-full bg-[#96bc4b]" />
                    {l.legend.learner}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-1 w-5 rounded-full bg-[#6f98c2]" />
                    {l.legend.opponent}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Bulb className="size-3.5" />
                    {t.courses.ideas.title}
                  </span>
                </p>
              </>
            )}
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-3">
          <Panel className="!p-2">
            <OpeningTree
              index={treeIndex}
              currentId={currentId}
              onSelect={select}
              renderMeta={meta}
              className="max-h-[38dvh] lg:max-h-[34dvh]"
            />
          </Panel>
          <NodePanel
            tree={tree}
            index={index}
            currentId={currentId}
            ideasText={course.ideas_text}
            onSelect={select}
            onPlay={setGame}
          />
        </div>
      </div>
    </div>
  );
}

function Flag() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-3.5 shrink-0" fill="#7fb04a">
      <path d="M5 3a1 1 0 0 1 1 1v.4c1.6-.8 3.3-.9 5.2-.1 1.7.7 3.3.7 5.1-.1a1 1 0 0 1 1.4.9v8.6a1 1 0 0 1-.6.9c-2.2 1-4.3 1-6.4.1-1.6-.7-3.1-.6-4.7.3V21a1 1 0 1 1-2 0V4a1 1 0 0 1 1-1z" />
    </svg>
  );
}

export function CourseSkeleton() {
  return (
    <div aria-busy className="flex flex-col gap-3">
      <div className="h-11 w-72 max-w-full animate-pulse rounded-lg bg-panel" />
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(340px,460px)]">
        <div className="mx-auto aspect-square w-full animate-pulse rounded bg-raised/50" style={BOARD_WIDTH} />
        <div className="h-96 animate-pulse rounded-xl bg-panel" />
      </div>
    </div>
  );
}
