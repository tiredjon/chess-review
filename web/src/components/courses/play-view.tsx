"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type Ref } from "react";
import { ApiError } from "@/lib/api";
import { BOT_ELOS } from "@/lib/bots/types";
import { uciSan } from "@/lib/chess";
import { coursesApi, isBuilding, type CourseDetail, type CourseNode, type CourseTree } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { BotGame } from "../play/bot-game";
import { BotPicker } from "../play/bot-picker";
import type { GameResult } from "../play/types";
import { indexNodes } from "../openings/types";
import { Button, ErrorText, Panel } from "../ui";
import { Building, CourseHeading, CourseSkeleton } from "./course-view";
import {
  courseBook,
  courseLines,
  lineProgress,
  lineThrough,
  nodeAfter,
  numbered,
  pickRandomLine,
  type CourseLine,
  type LineProgress,
} from "./play-book";
import { errorText, ProgressBar } from "./shared";

const POLL_MS = 2000;
const BOT_KEY = "chess-review:course-play-bot";
const DEFAULT_ELO = 1200;
/** Сколько полуходов линии показывать в списке вариантов. */
const SHOWN_PLIES = 10;

/** Выбор линии: номер варианта (с 0) или «случайная по частоте мастеров». */
export type LineChoice = number | "random";

type Game = { no: number; line: CourseLine; random: boolean };

function readElo(): number {
  try {
    const value = Number(localStorage.getItem(BOT_KEY));
    return BOT_ELOS.includes(value) ? value : DEFAULT_ELO;
  } catch {
    return DEFAULT_ELO;
  }
}

function saveElo(elo: number) {
  try {
    localStorage.setItem(BOT_KEY, String(elo));
  } catch {
    // Нет доступа к хранилищу — просто не запомним.
  }
}

/** «Sicilian Defense: Najdorf Variation, English Attack» → «Najdorf Variation, English Attack». */
const shortName = (name: string) => (name.includes(":") ? name.slice(name.indexOf(":") + 1).trim() : name);

/**
 * Партия с ботом по линии курса: курс (сборка — как на странице курса) → выбор линии и бота →
 * партия (`BotGame` с книгой соперника из дерева) → итог.
 */
export function CoursePlayView({ id, initialNode, initialLine }: { id: string; initialNode: number | null; initialLine: LineChoice | null }) {
  const { t, lang } = useI18n();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

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
  return <CoursePlay course={course} tree={course.tree} initialNode={initialNode} initialLine={initialLine} />;
}

function CoursePlay({
  course,
  tree,
  initialNode,
  initialLine,
}: {
  course: CourseDetail;
  tree: CourseTree;
  initialNode: number | null;
  initialLine: LineChoice | null;
}) {
  const index = useMemo(() => indexNodes(tree.nodes), [tree]);
  const lines = useMemo(() => courseLines(index), [index]);
  const [choice, setChoice] = useState<LineChoice>(() => {
    if (initialLine === "random") return "random";
    if (initialLine !== null && initialLine >= 0 && initialLine < lines.length) return initialLine;
    if (initialNode !== null) return lineThrough(index, lines, initialNode) ?? 0;
    return 0;
  });
  // Компонент появляется только после загрузки курса в браузере — localStorage доступен.
  const [elo, setElo] = useState(readElo);
  const [game, setGame] = useState<Game | null>(null);

  const start = useCallback(
    (next: LineChoice) => {
      const line = next === "random" ? pickRandomLine(lines) : lines[next];
      if (!line) return;
      setChoice(next);
      setGame((prev) => ({ no: (prev?.no ?? 0) + 1, line, random: next === "random" }));
      window.scrollTo({ top: 0 });
    },
    [lines],
  );
  const pickElo = (value: number) => {
    setElo(value);
    saveElo(value);
  };

  if (game)
    return (
      <PlayGame
        key={game.no}
        course={course}
        index={index}
        lines={lines}
        game={game}
        elo={elo}
        onAgain={() => start(game.random ? "random" : game.line.n)}
        onNext={() => start(game.random ? "random" : (game.line.n + 1) % lines.length)}
        onSetup={() => setGame(null)}
      />
    );
  return (
    <Setup
      course={course}
      tree={tree}
      lines={lines}
      choice={choice}
      onChoice={setChoice}
      elo={elo}
      onElo={pickElo}
      onStart={() => start(choice)}
    />
  );
}

// --- Настройка: линия и бот ---

function Setup({
  course,
  tree,
  lines,
  choice,
  onChoice,
  elo,
  onElo,
  onStart,
}: {
  course: CourseDetail;
  tree: CourseTree;
  lines: CourseLine[];
  choice: LineChoice;
  onChoice: (choice: LineChoice) => void;
  elo: number;
  onElo: (elo: number) => void;
  onStart: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.play;
  const total = lines.reduce((sum, line) => sum + line.weight, 0) || 1;
  const lineEndPly = tree.nodes.find((node) => node.id === tree.line_end)?.ply ?? 0;
  const selected = useRef<HTMLButtonElement>(null);
  // Предвыбранная линия (?node= / ?line=) — на виду.
  useEffect(() => {
    selected.current?.scrollIntoView({ block: "nearest" });
  }, []);
  const color = course.color === "white" ? t.courses.color.whiteShort : t.courses.color.blackShort;

  return (
    <div className="flex flex-col gap-3">
      <CourseHeading
        course={course}
        aside={
          <Link
            href={`/openings/courses/${course.id}`}
            className="inline-flex min-h-10 items-center font-bold text-green hover:underline"
          >
            ‹ {l.back}
          </Link>
        }
      />
      {/* Телефон: бот, линии, кнопка «Играть» липнет к низу. Десктоп: линии слева, бот и кнопка справа. */}
      <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,400px)] lg:grid-rows-[auto_1fr]">
        <Panel title={l.bot} className="min-w-0 lg:col-start-2 lg:row-start-1">
          <BotPicker value={elo} onChange={onElo} compact />
          <p className="mt-3 text-sm text-soft">{l.youPlay(color.toLowerCase())}</p>
        </Panel>
        <Panel title={l.lines} className="min-w-0 lg:col-start-1 lg:row-span-2 lg:row-start-1">
          <p className="-mt-2 mb-3 text-sm leading-snug text-muted">{l.hint}</p>
          <div role="radiogroup" aria-label={l.lines} className="flex flex-col gap-1.5">
            <LineOption
              ref={choice === "random" ? selected : undefined}
              active={choice === "random"}
              onClick={() => onChoice("random")}
              title={l.random}
              meta={null}
            >
              <span className="text-sm text-muted">{l.randomHint}</span>
            </LineOption>
            {lines.map((line) => (
              <LineOption
                key={line.leaf}
                ref={choice === line.n ? selected : undefined}
                active={choice === line.n}
                onClick={() => onChoice(line.n)}
                title={
                  <>
                    {l.lineOf(line.n + 1, lines.length)}
                    {line.fork < 0 && <span className="ml-2 text-xs font-semibold text-green">{l.main}</span>}
                  </>
                }
                meta={l.share(Math.round((line.weight / total) * 100))}
              >
                {line.name && <span className="block truncate text-sm text-soft">{shortName(line.name)}</span>}
                <LineMoves line={line} from={lineEndPly} />
              </LineOption>
            ))}
          </div>
        </Panel>

        <div className="sticky bottom-0 -mx-3 min-w-0 bg-page/95 px-3 py-3 backdrop-blur sm:-mx-5 sm:px-5 lg:top-3 lg:bottom-auto lg:col-start-2 lg:row-start-2 lg:mx-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
          <Button size="lg" className="w-full" onClick={onStart}>
            {l.start}
          </Button>
          <p className="mt-1.5 truncate text-center text-xs text-muted">
            {l.chosen}: {choice === "random" ? l.random : l.lineOf(choice + 1, lines.length)} · Stockfish {elo}
          </p>
        </div>
      </div>
    </div>
  );
}

function LineOption({
  ref,
  active,
  onClick,
  title,
  meta,
  children,
}: {
  ref?: Ref<HTMLButtonElement>;
  active: boolean;
  onClick: () => void;
  title: ReactNode;
  meta: string | null;
  children: ReactNode;
}) {
  return (
    <button
      ref={ref}
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={`w-full min-w-0 rounded-lg px-3 py-2.5 text-left ${
        active ? "bg-raised ring-2 ring-green ring-inset" : "bg-raised/50 hover:bg-raised"
      }`}
    >
      <span className="flex items-baseline justify-between gap-2">
        <span className="font-bold text-ink">{title}</span>
        {meta && <span className="shrink-0 text-xs font-semibold text-muted tabular-nums">{meta}</span>}
      </span>
      {children}
    </button>
  );
}

/** Ходы варианта коротко: с конца исходной линии курса; отход от основной — выделен. */
function LineMoves({ line, from }: { line: CourseLine; from: number }) {
  const start = Math.min(from, line.fork >= 0 ? line.fork : from);
  const shown = line.nodes.slice(start, start + SHOWN_PLIES);
  return (
    <span className="mt-0.5 block text-sm leading-snug break-words text-muted">
      {start > 0 && "… "}
      {shown.map((node, i) => {
        const at = start + i;
        const label = node.ply % 2 === 1 || i === 0 ? numbered(node.ply, node.san ?? "") : node.san;
        const forked = line.fork >= 0 && at >= line.fork;
        return (
          <Fragment key={node.id}>
            <span className={`whitespace-nowrap ${at === line.fork ? "font-bold text-green" : forked ? "text-ink" : ""}`}>{label}</span>{" "}
          </Fragment>
        );
      })}
      {start + SHOWN_PLIES < line.nodes.length && "…"}
    </span>
  );
}

// --- Партия ---

function PlayGame({
  course,
  index,
  lines,
  game,
  elo,
  onAgain,
  onNext,
  onSetup,
}: {
  course: CourseDetail;
  index: ReadonlyMap<number, CourseNode>;
  lines: CourseLine[];
  game: Game;
  elo: number;
  onAgain: () => void;
  onNext: () => void;
  onSetup: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.play;
  const [history, setHistory] = useState<readonly string[]>([]);
  const [result, setResult] = useState<GameResult | null>(null);

  // Книга стабильна на всю партию; ходы партии (и «взять назад») приходят из onHistoryChange.
  const book = useMemo(() => courseBook(index, game.line, game.random ? "random" : "line"), [index, game]);

  const lineLabel = game.random ? `${l.random} (${l.lineNo(game.line.n + 1)})` : l.lineOf(game.line.n + 1, lines.length);
  const headers = useMemo(() => ({ Event: `${course.name} — ${lineLabel}` }), [course.name, lineLabel]);
  const onFinished = useCallback((value: GameResult) => setResult(value), []);
  const onHistoryChange = useCallback((value: readonly string[]) => setHistory([...value]), []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl leading-tight font-extrabold">{shortName(course.name)}</h1>
          <p className="truncate text-sm text-muted">
            {game.random ? l.random : l.lineOf(game.line.n + 1, lines.length)} · Stockfish {elo}
          </p>
        </div>
        <Button variant="raised" size="sm" onClick={onSetup} title={l.game.change}>
          <span className="sm:hidden">{l.game.changeShort}</span>
          <span className="max-sm:hidden">{l.game.change}</span>
        </Button>
      </div>
      <BotGame
        elo={elo}
        color={course.color}
        book={book}
        onHistoryChange={onHistoryChange}
        onFinished={onFinished}
        onNewGame={onSetup}
        pgnHeaders={headers}
        aside={
          <PlayAside
            course={course}
            index={index}
            game={game}
            history={history}
            result={result}
            lines={lines}
            onAgain={onAgain}
            onNext={onNext}
            onSetup={onSetup}
          />
        }
      />
    </div>
  );
}

/** SAN хода из позиции узла (для ходов вне дерева). */
function sanFrom(index: ReadonlyMap<number, CourseNode>, nodeId: number, uci: string): string {
  const fen = index.get(nodeId)?.fen;
  return (fen && uciSan(fen, uci)) || uci;
}

function PlayAside({
  course,
  index,
  game,
  history,
  result,
  lines,
  onAgain,
  onNext,
  onSetup,
}: {
  course: CourseDetail;
  index: ReadonlyMap<number, CourseNode>;
  game: Game;
  history: readonly string[];
  result: GameResult | null;
  lines: CourseLine[];
  onAgain: () => void;
  onNext: () => void;
  onSetup: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.play;
  const learnerFirst = course.color === "white";
  const progress = useMemo(() => lineProgress(index, game.line, history, learnerFirst), [index, game.line, history, learnerFirst]);
  // Название дебюта — у последнего узла дерева, через который прошла партия.
  const name = useMemo(() => {
    const reached = nodeAfter(index, history.slice(0, progress.inTreePlies));
    let node = reached ? index.get(reached.id) : undefined;
    while (node) {
      if (node.name) return node.name;
      node = node.parent === null ? undefined : index.get(node.parent);
    }
    return null;
  }, [index, history, progress.inTreePlies]);

  return (
    <div className="flex flex-col gap-3">
      {result && <Summary course={course} index={index} game={game} lines={lines} progress={progress} result={result} onAgain={onAgain} onNext={onNext} onSetup={onSetup} />}
      <section className="rounded-lg bg-sunken/60 p-3">
        <p className="text-xs font-bold tracking-wide text-muted uppercase">
          {game.random && !result ? l.random : l.lineOf(game.line.n + 1, lines.length)}
        </p>
        {name && <p className="mt-0.5 truncate text-sm font-semibold text-soft">{shortName(name)}</p>}
        <p className="mt-2 text-sm font-bold text-ink">{whereText(t, game.line, progress)}</p>
        <ProgressBar value={(progress.matched / Math.max(1, progress.total)) * 100} className="mt-2 h-2" />
        <Notes index={index} progress={progress} historyLength={history.length} finished={result !== null} />
      </section>
    </div>
  );
}

function whereText(t: ReturnType<typeof useI18n>["t"], line: CourseLine, progress: LineProgress): string {
  const l = t.courses.play.game;
  if (progress.matched === 0) return l.start;
  if (progress.completed) return l.lineDone;
  const node = line.nodes[progress.matched - 1];
  return l.onLine(numbered(node.ply, node.san ?? ""));
}

function Notes({
  index,
  progress,
  historyLength,
  finished,
}: {
  index: ReadonlyMap<number, CourseNode>;
  progress: LineProgress;
  historyLength: number;
  finished: boolean;
}) {
  const { t } = useI18n();
  const l = t.courses.play.game;
  const notes: { key: string; tone: "warn" | "info"; title: string; text?: string }[] = [];
  const exit = progress.lineExit;
  if (exit) {
    const played = numbered(exit.ply, exit.playedSan ?? sanFrom(index, exit.nodeId, exit.played));
    notes.push({
      key: "line",
      tone: "warn",
      title: l.courseMoveWas(numbered(exit.ply, exit.expectedSan ?? exit.expected)),
      text: `${progress.lineExitInTree ? l.branch(played) : l.offCourse(played)}${finished ? "" : ` ${l.takeBack}`}`,
    });
  }
  const tree = progress.treeExit;
  if (tree && tree.ply !== exit?.ply) {
    notes.push({
      key: "tree",
      tone: "warn",
      title: l.treeExit(numbered(tree.ply, sanFrom(index, tree.nodeId, tree.played)), numbered(tree.ply, tree.expectedSan ?? tree.expected)),
    });
  }
  if (progress.completed && progress.inTreePlies > progress.matched) {
    const node = progress.node;
    if (node) notes.push({ key: "inTree", tone: "info", title: l.inTree(numbered(node.ply, node.san ?? "")) });
  }
  if (historyLength > 0 && progress.bookOver) notes.push({ key: "over", tone: "info", title: l.bookOver });

  if (notes.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-col gap-2" aria-live="polite">
      {notes.map((note) => (
        <li key={note.key} className="flex gap-2.5 rounded-md bg-panel px-3 py-2 text-sm">
          <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${note.tone === "warn" ? "bg-[#f7c045]" : "bg-[#6f98c2]"}`} />
          <div className="min-w-0">
            <p className="font-bold text-ink">{note.title}</p>
            {note.text && <p className="mt-0.5 leading-snug text-soft">{note.text}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Summary({
  course,
  index,
  game,
  lines,
  progress,
  result,
  onAgain,
  onNext,
  onSetup,
}: {
  course: CourseDetail;
  index: ReadonlyMap<number, CourseNode>;
  game: Game;
  lines: CourseLine[];
  progress: LineProgress;
  result: GameResult;
  onAgain: () => void;
  onNext: () => void;
  onSetup: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.play.summary;
  const outcome = result.winner === null ? "draw" : result.winner === course.color ? "win" : "loss";
  const exit = progress.lineExit ?? progress.treeExit;
  const totalMoves = Math.ceil(progress.total / 2);
  let line: string;
  if (exit) {
    const played = numbered(exit.ply, exit.playedSan ?? sanFrom(index, exit.nodeId, exit.played));
    line = l.exit(Math.ceil(exit.ply / 2), played, numbered(exit.ply, exit.expectedSan ?? exit.expected));
  } else if (progress.completed) line = l.passedAll(totalMoves);
  else line = l.passedTo(Math.ceil(progress.matched / 2), totalMoves);

  const linkClass =
    "inline-flex min-h-10 items-center justify-center rounded-lg bg-raised px-4 text-center text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink";
  return (
    <section aria-label={l.title} className="rounded-lg bg-sunken/60 p-3">
      <p className="text-xs font-bold tracking-wide text-muted uppercase">{l.title}</p>
      <p className={`mt-1 text-xl font-extrabold ${outcome === "win" ? "text-green" : outcome === "loss" ? "text-danger" : "text-ink"}`}>
        {l[outcome]} <span className="text-base font-bold text-soft">· {l.reasons[result.reason] ?? result.reason}</span>
      </p>
      <p className="mt-2 text-sm font-semibold text-ink">{line}</p>
      {game.random && <p className="mt-1 text-sm text-muted">{l.wasLine(t.courses.play.lineOf(game.line.n + 1, lines.length))}</p>}
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Button onClick={onAgain} className="sm:col-span-2">
          {game.random ? l.anotherRandom : l.again}
        </Button>
        {!game.random && (
          <Button variant="raised" onClick={onNext}>
            {l.next}
          </Button>
        )}
        {exit && (
          <Link href={`/openings/courses/${course.id}?node=${exit.nodeId}`} className={linkClass}>
            {l.trainHere}
          </Link>
        )}
        {/* Вторая строка — по две кнопки; нечётная последняя растягивается. */}
        <Button variant="raised" onClick={onSetup} className={(game.random ? 0 : 1) + (exit ? 1 : 0) === 1 ? "" : "sm:col-span-2"}>
          {l.setup}
        </Button>
      </div>
    </section>
  );
}
