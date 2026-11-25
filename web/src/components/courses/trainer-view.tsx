"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { applyUci, boardMoveUci, pieceOn, START_FEN, uciSan, uciSquares } from "@/lib/chess";
import { CLASS_COLORS, type ClassKey } from "@/lib/classes";
import { coursesApi, type CourseDetail, type CourseNode } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { playMove, playSound, preloadSounds, toggleMuted, useSoundMuted } from "@/lib/sounds";
import { LEARNED_BOX, MAX_BOX, trainerApi, type CourseSummary, type TrainerAnswer, type TrainerCard } from "@/lib/trainer-api";
import type { Color } from "@/lib/types";
import { indexNodes, moverColor, moveNo, pathTo } from "../openings/types";
import { Board, type BoardMarks } from "../review/board";
import { ClassBadge } from "../review/class-badge";
import { Figurine } from "../review/move-list";
import { CoachBubble } from "../review/summary";
import { Button, Chip, ErrorText } from "../ui";
import { IdeasCard } from "./ideas-card";
import { Bulb } from "./node-panel";
import { errorText, whenText } from "./shared";

// Ход соперника перед позицией — с паузой, как в пазлах; неверный ход виден, потом откат.
const INTRO_DELAY_MS = 600;
const REVERT_MS = 800;
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 6rem))" };

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";
const HINT = "rgba(92, 168, 222, 0.7)";
const BEST_ARROW = "rgba(127, 176, 74, 0.9)";

type Phase = "intro" | "playing" | "checking" | "done";

const VERDICT_BADGE: Record<TrainerAnswer["verdict"], ClassKey> = { main: "best", alternative: "excellent", wrong: "mistake" };

type Game = {
  card: TrainerCard;
  phase: Phase;
  fen: string;
  lastMove: string | null;
  selected: string | null;
  hintShown: boolean;
  hintUsed: boolean;
  /** Сыгранный учеником ход и ответ сервера. */
  played: string | null;
  answer: TrainerAnswer | null;
  badge: { square: string; value: ClassKey } | null;
  /** Ход курса стрелкой (после альтернативы или ошибки). */
  arrow: string | null;
};

/** Позиция перед последним ходом соперника — его ход проигрывается анимацией. */
function startGame(card: TrainerCard): Game {
  const last = card.path_uci.at(-1);
  const lastMover: Color = card.path_uci.length % 2 === 1 ? "white" : "black";
  const intro = last !== undefined && lastMover !== card.color;
  const before = intro ? card.path_uci.slice(0, -1).reduce((fen, uci) => applyUci(fen, uci) ?? fen, START_FEN) : card.fen;
  return {
    card,
    phase: intro ? "intro" : "playing",
    fen: before,
    lastMove: intro ? null : (last ?? null),
    selected: null,
    hintShown: false,
    hintUsed: false,
    played: null,
    answer: null,
    badge: null,
    arrow: null,
  };
}

type Load =
  | { kind: "loading" }
  | { kind: "card"; game: Game }
  | { kind: "empty" }
  | { kind: "notReady"; courseId: string }
  | { kind: "error"; error: unknown };

/**
 * Тренажёр дебютов: общая очередь по всем курсам (`courseId` = null) или один курс.
 * Позицию и проверку хода даёт API тренажёра; дерево курса (подсказка, идеи, путь) — API курса.
 */
export function TrainerView({ courseId }: { courseId: string | null }) {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [summary, setSummary] = useState<CourseSummary[] | null>(null);
  const [courses, setCourses] = useState<Record<string, CourseDetail>>({});
  const [checkError, setCheckError] = useState<unknown>(null);
  const [session, setSession] = useState({ right: 0, wrong: 0 });
  const [busy, setBusy] = useState(false);
  const muted = useSoundMuted();
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const later = useCallback((ms: number, action: () => void) => {
    timers.current.push(setTimeout(action, ms));
  }, []);
  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);
  useEffect(() => clearTimers, [clearTimers]);
  useEffect(preloadSounds, []);

  const refreshSummary = useCallback(() => {
    trainerApi
      .summary()
      .then(setSummary)
      .catch(() => undefined);
  }, []);

  /** Курс карточки (дерево и идеи) — один раз на курс и язык. */
  const ensureCourse = useCallback(
    async (id: string) => {
      const key = `${id}:${lang}`;
      if (courses[key]) return;
      const detail = await coursesApi.course(id, lang);
      setCourses((prev) => ({ ...prev, [key]: detail }));
    },
    [courses, lang],
  );

  const fetchNext = useCallback(async () => {
    clearTimers();
    setBusy(true);
    setCheckError(null);
    try {
      const card = await trainerApi.next(courseId);
      if (card === null) {
        setLoad({ kind: "empty" });
      } else {
        // Без дерева курса тренажёр работает (подсказки и идей не будет).
        await ensureCourse(card.course_id).catch(() => undefined);
        setLoad({ kind: "card", game: startGame(card) });
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "course_not_ready" && courseId) setLoad({ kind: "notReady", courseId });
      else setLoad({ kind: "error", error: err ?? true });
    } finally {
      setBusy(false);
    }
  }, [clearTimers, courseId, ensureCourse]);

  // Старт: у курса — сначала карточки (идемпотентно), затем сводка и первая позиция.
  const [attempt, setAttempt] = useState(0);
  const fetchRef = useRef(fetchNext);
  useEffect(() => {
    fetchRef.current = fetchNext;
  }, [fetchNext]);
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (courseId) {
        try {
          await trainerApi.start(courseId);
        } catch (err) {
          if (cancelled) return;
          if (err instanceof ApiError && err.code === "course_not_ready") setLoad({ kind: "notReady", courseId });
          else setLoad({ kind: "error", error: err ?? true });
          return;
        }
      }
      if (cancelled) return;
      refreshSummary();
      await fetchRef.current();
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [courseId, attempt, refreshSummary]);

  const game = load.kind === "card" ? load.game : null;
  const setGame = useCallback((update: (prev: Game) => Game) => {
    setLoad((prev) => (prev.kind === "card" ? { kind: "card", game: update(prev.game) } : prev));
  }, []);

  // Ход соперника, приведший к позиции карточки.
  const introKey = game?.phase === "intro" ? `${game.card.course_id}:${game.card.node_id}` : null;
  useEffect(() => {
    if (!introKey) return;
    const timer = setTimeout(() => {
      setGame((prev) => {
        if (prev.phase !== "intro") return prev;
        const last = prev.card.path_uci.at(-1)!;
        playMove(uciSan(prev.fen, last) ?? "", prev.card.color === "white" ? "black" : "white", prev.card.color);
        return { ...prev, phase: "playing", fen: prev.card.fen, lastMove: last };
      });
    }, INTRO_DELAY_MS);
    return () => clearTimeout(timer);
  }, [introKey, setGame]);

  const course = game ? courses[`${game.card.course_id}:${lang}`] : undefined;
  const index = useMemo(() => (course?.tree ? indexNodes(course.tree.nodes) : null), [course]);
  const cardNode = game && index ? index.get(game.card.node_id) : undefined;
  const mainMove = useMemo(() => {
    if (!cardNode || !index) return null;
    const kids = cardNode.children.flatMap((id) => index.get(id) ?? []).filter((kid) => kid.mover === "learner");
    return (kids.find((kid) => kid.main) ?? kids[0])?.uci ?? null;
  }, [cardNode, index]);

  const submit = useCallback(
    (current: Game, uci: string) => {
      trainerApi
        .answer(current.card, { uci, hint_used: current.hintUsed })
        .then((answer) => {
          const to = uciSquares(uci).to;
          setGame((prev) => ({ ...prev, phase: "done", answer, badge: { square: to, value: VERDICT_BADGE[answer.verdict] } }));
          setSession((prev) =>
            answer.verdict === "wrong" ? { ...prev, wrong: prev.wrong + 1 } : { ...prev, right: prev.right + 1 },
          );
          refreshSummary();
          if (answer.verdict === "main") {
            later(200, () => playSound("correct"));
            return;
          }
          playSound(answer.verdict === "wrong" ? "incorrect" : "correct");
          // Сыгранный ход виден со значком, затем откат и ход курса стрелкой.
          const expected = answer.expected[0]?.uci ?? null;
          later(REVERT_MS, () =>
            setGame((prev) =>
              prev.answer === answer
                ? { ...prev, fen: prev.card.fen, lastMove: prev.card.path_uci.at(-1) ?? null, badge: null, arrow: expected }
                : prev,
            ),
          );
        })
        .catch((err) => {
          setCheckError(err ?? true);
          setGame((prev) => ({ ...prev, phase: "playing", fen: prev.card.fen, lastMove: prev.card.path_uci.at(-1) ?? null, played: null }));
        });
    },
    [later, refreshSummary, setGame],
  );

  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      if (!game || game.phase !== "playing") return false;
      const uci = boardMoveUci(game.fen, from, to);
      if (!uci) {
        playSound("illegal");
        setGame((prev) => ({ ...prev, selected: null }));
        return false;
      }
      playMove(uciSan(game.fen, uci) ?? "", game.card.color, game.card.color);
      const next: Game = {
        ...game,
        phase: "checking",
        fen: applyUci(game.fen, uci) ?? game.fen,
        lastMove: uci,
        selected: null,
        hintShown: false,
        played: uci,
      };
      setCheckError(null);
      setGame(() => next);
      submit(next, uci);
      return true;
    },
    [game, setGame, submit],
  );

  const onSquareClick = useCallback(
    (square: string) => {
      if (!game || game.phase !== "playing") return;
      if (game.selected && game.selected !== square && tryMove(game.selected, square)) return;
      const piece = pieceOn(game.fen, square);
      const own = piece !== null && (piece === piece.toUpperCase()) === (game.card.color === "white");
      setGame((prev) => ({ ...prev, selected: own && square !== prev.selected ? square : null }));
    },
    [game, tryMove, setGame],
  );

  const showHint = () => setGame((prev) => (prev.phase === "playing" ? { ...prev, hintShown: true, hintUsed: true } : prev));

  /** «Показать ход курса»: ход курса анимацией из позиции карточки. */
  const replay = () => {
    if (!game?.answer) return;
    const move = game.answer.expected[0];
    if (!move) return;
    clearTimers();
    setGame((prev) => ({ ...prev, fen: prev.card.fen, lastMove: prev.card.path_uci.at(-1) ?? null, badge: null, arrow: null }));
    later(350, () =>
      setGame((prev) => {
        playMove(move.san, prev.card.color, prev.card.color);
        return { ...prev, fen: applyUci(prev.card.fen, move.uci) ?? prev.fen, lastMove: move.uci, badge: { square: uciSquares(move.uci).to, value: "best" } };
      }),
    );
  };

  const next = useCallback(() => {
    void fetchNext();
  }, [fetchNext]);

  // Клавиши: M — звук, N / → — следующая позиция после ответа.
  const phase = game?.phase;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.target instanceof HTMLElement && ["INPUT", "TEXTAREA"].includes(event.target.tagName)) return;
      if (["m", "M", "ь", "Ь"].includes(event.key)) toggleMuted();
      if ((event.key === "n" || event.key === "ArrowRight") && phase === "done") next();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, next]);

  const selectCourse = (id: string | null) => router.replace(id ? `/openings/train?course=${id}` : "/openings/train");
  const rows = summary ?? [];
  const scope = courseId ? rows.filter((row) => row.course_id === courseId) : rows;
  const totals = scope.reduce(
    (acc, row) => ({ due: acc.due + row.due, fresh: acc.fresh + row.new, learned: acc.learned + row.learned, total: acc.total + row.total }),
    { due: 0, fresh: 0, learned: 0, total: 0 },
  );
  const soundLabel = muted ? t.trainer.sound.on : t.trainer.sound.off;

  return (
    <div className="flex flex-col gap-3">
      <h1 className="sr-only">{t.trainer.title}</h1>
      {rows.length > 1 && (
        <div role="radiogroup" aria-label={t.trainer.filter} className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          <Chip role="radio" aria-checked={!courseId} active={!courseId} onClick={() => selectCourse(null)} className="shrink-0">
            {t.trainer.allCourses}
          </Chip>
          {rows.map((row) => (
            <Chip
              key={row.course_id}
              role="radio"
              aria-checked={courseId === row.course_id}
              active={courseId === row.course_id}
              onClick={() => selectCourse(row.course_id)}
              className="max-w-64 shrink-0 truncate"
            >
              {shortName(row.name)}
              {row.due > 0 && <span className="ml-1.5 rounded bg-[#f59a4c] px-1 text-[11px] font-extrabold text-white">{row.due}</span>}
            </Chip>
          ))}
        </div>
      )}

      {load.kind === "loading" ? (
        <TrainerSkeleton />
      ) : load.kind === "error" ? (
        <div className="rounded-xl bg-panel p-5">
          <ErrorText>{errorText(t, load.error, t.trainer.loadError)}</ErrorText>
          <Button variant="raised" className="mt-3" onClick={() => setAttempt((n) => n + 1)}>
            {t.trainer.retry}
          </Button>
        </div>
      ) : load.kind === "notReady" ? (
        <div className="rounded-xl bg-panel p-5">
          <p className="text-soft">{t.trainer.notReady}</p>
          <Link href={`/openings/courses/${load.courseId}`} className="mt-3 inline-block font-bold text-green hover:underline">
            {t.trainer.done.course}
          </Link>
        </div>
      ) : load.kind === "empty" ? (
        <EmptyQueue totals={totals} courseId={courseId} hasCards={rows.length > 0} />
      ) : (
        game && (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="mx-auto w-full" style={BOARD_WIDTH}>
              <Board
                fen={game.fen}
                orientation={game.card.color}
                marks={boardMarks(game, mainMove)}
                interactive={game.phase === "playing"}
                onMove={tryMove}
                onSquareClick={onSquareClick}
              />
            </div>

            <section aria-label={t.trainer.title} className="flex min-w-0 flex-col rounded-xl bg-panel">
              <header className="flex items-center gap-3 rounded-t-xl border-b border-line bg-sunken/60 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-lg font-extrabold">{course ? shortName(course.name) : t.trainer.heading}</h2>
                  {summary && <p className="text-xs font-semibold text-muted">{t.trainer.counts(totals.due, totals.fresh, totals.learned, totals.total)}</p>}
                </div>
                <button
                  type="button"
                  onClick={toggleMuted}
                  aria-pressed={muted}
                  aria-label={soundLabel}
                  title={soundLabel}
                  className="flex size-9 shrink-0 items-center justify-center rounded-lg text-soft hover:bg-raised hover:text-ink"
                >
                  <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" />
                    {muted ? <path d="m16 9.5 5 5m0-5-5 5" /> : <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />}
                  </svg>
                </button>
              </header>

              <div key={`${game.card.course_id}:${game.card.node_id}`} className="cc-slide-in flex flex-1 flex-col gap-4 p-4">
                <Banner game={game} />
                {cardNode && index && <PathLine nodes={pathTo(index, cardNode.id)} />}
                <CoachBubble>
                  <StatusText game={game} />
                </CoachBubble>
                <ErrorText>{checkError ? errorText(t, checkError, t.trainer.checkError) : null}</ErrorText>
                <BoxMeter box={game.answer?.box ?? game.card.box} />

                {game.answer && game.answer.verdict !== "main" && course && (
                  <IdeasPanel game={game} course={course} open={game.answer.verdict === "wrong"} />
                )}

                <p className="text-xs text-muted">{t.trainer.session(session.right, session.wrong)}</p>

                {/* На телефоне действия липнут к низу экрана, как в пазлах. */}
                <div className="sticky bottom-0 -mx-4 -mb-4 mt-auto flex flex-col gap-2 rounded-b-xl border-t border-line bg-panel p-4 lg:static lg:mx-0 lg:mb-0 lg:border-0 lg:p-0 lg:pt-2">
                  {game.phase === "done" ? (
                    <>
                      <Button size="lg" onClick={next} disabled={busy}>
                        {busy ? t.trainer.nextLoading : t.trainer.next}
                      </Button>
                      <div className="grid grid-cols-2 gap-2">
                        {game.answer?.verdict !== "main" && (
                          <Button variant="raised" onClick={replay}>
                            {t.trainer.replay}
                          </Button>
                        )}
                        <Link
                          href={`/openings/courses/${game.card.course_id}?node=${game.card.node_id}`}
                          className={`inline-flex min-h-10 items-center justify-center rounded-lg bg-raised px-4 text-[15px] font-bold text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink ${
                            game.answer?.verdict === "main" ? "col-span-2" : ""
                          }`}
                        >
                          {t.trainer.openCourse}
                        </Link>
                      </div>
                    </>
                  ) : (
                    <Button variant="raised" onClick={showHint} disabled={game.phase !== "playing" || game.hintShown || !mainMove}>
                      {game.hintShown ? t.trainer.hintShown : t.trainer.hint}
                    </Button>
                  )}
                </div>
              </div>
            </section>
          </div>
        )
      )}
    </div>
  );
}

/** «Sicilian Defense: Najdorf Variation» → «Najdorf Variation». */
const shortName = (name: string) => (name.includes(":") ? name.slice(name.indexOf(":") + 1).trim() : name);

function boardMarks(game: Game, mainMove: string | null): BoardMarks {
  const highlights: Record<string, string> = {};
  if (game.lastMove) {
    const { from, to } = uciSquares(game.lastMove);
    const value = game.badge?.value;
    const color = value ? `${CLASS_COLORS[value]}aa` : LAST_MOVE;
    highlights[from] = color;
    highlights[to] = color;
  }
  if (game.selected) highlights[game.selected] = SELECTED;
  if (game.hintShown && mainMove) highlights[uciSquares(mainMove).from] = HINT;
  return {
    key: `${game.card.node_id}-${game.fen}-${game.badge?.value ?? ""}-${game.arrow ?? ""}`,
    arrows: game.arrow ? [{ startSquare: uciSquares(game.arrow).from, endSquare: uciSquares(game.arrow).to, color: BEST_ARROW }] : [],
    highlights,
    badge: game.badge,
  };
}

function Banner({ game }: { game: Game }) {
  const { banner } = useI18n().t.trainer;
  const verdict = game.answer?.verdict;
  const text = verdict ? banner[verdict] : banner[game.card.color];
  const tone =
    verdict === "main" || verdict === "alternative"
      ? "bg-green text-white"
      : verdict === "wrong"
        ? "bg-[#f59a4c] text-white"
        : game.card.color === "white"
          ? "bg-white text-[#2c2925]"
          : "bg-sunken text-ink";
  return (
    <div className={`flex items-center gap-2 rounded-lg px-4 py-3 text-lg font-extrabold ${tone}`}>
      {verdict && <ClassBadge value={VERDICT_BADGE[verdict]} size={24} title={false} />}
      {text}
    </div>
  );
}

function StatusText({ game }: { game: Game }) {
  const { t, lang } = useI18n();
  const s = t.trainer.status;
  const { answer } = game;
  if (game.phase === "intro") return <>{s.intro}</>;
  if (game.phase === "checking") return <>{s.checking}</>;
  if (answer) {
    const move = answer.expected[0];
    const courseMove = move && (
      <>
        {" "}
        {s.courseMove}{" "}
        <span className="font-bold">
          <Figurine san={move.san} color={game.card.color} />
        </span>
        .
      </>
    );
    if (answer.verdict === "main") {
      return (
        <>
          <span className="font-bold">{s.main}</span> {game.hintUsed ? `${s.withHint} ` : ""}
          {s.showAgain(whenText(answer.next_review_at, lang))}
        </>
      );
    }
    if (answer.verdict === "alternative") {
      return (
        <>
          <span className="font-bold">{t.trainer.banner.alternative}.</span>{" "}
          {s.alternative(answer.win_loss !== null ? s.lossSuffix(answer.win_loss) : "")}
          {courseMove} {s.showAgain(whenText(answer.next_review_at, lang))}
        </>
      );
    }
    return (
      <>
        <span className="font-bold">{s.wrong(answer.win_loss !== null ? s.wrongLoss(answer.win_loss) : "")}</span>
        {courseMove} {s.returns(whenText(answer.next_review_at, lang))}
      </>
    );
  }
  return (
    <>
      {s.task}
      {game.card.due || game.card.box > 0 ? s.repeat : s.fresh}
    </>
  );
}

/** Коробка Лейтнера карточки: 5 делений, с LEARNED_BOX — «выучено». */
function BoxMeter({ box }: { box: number }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-3" aria-label={t.trainer.box(box, MAX_BOX)} role="img">
      <span className="text-xs font-bold tracking-wide text-muted uppercase">{box >= LEARNED_BOX ? t.trainer.learned : t.trainer.boxLabel}</span>
      <span className="flex flex-1 gap-1">
        {Array.from({ length: MAX_BOX }, (_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i < box ? "bg-green" : "bg-sunken"}`} />
        ))}
      </span>
      <span className="text-xs font-semibold text-soft tabular-nums">
        {box}/{MAX_BOX}
      </span>
    </div>
  );
}

/** Идеи позиции после ошибки (раскрыты) или альтернативы (свёрнуты). */
function IdeasPanel({ game, course, open }: { game: Game; course: CourseDetail; open: boolean }) {
  const { t } = useI18n();
  const id = game.answer?.ideas_node_id;
  if (id === null || id === undefined) return null;
  const text = course.ideas_text[String(id)];
  const raw = course.tree?.nodes.find((node) => node.id === id)?.ideas ?? null;
  if (!text && !raw) return null;
  return (
    <details open={open} className="group rounded-lg bg-sunken/50 p-3">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-extrabold">
        <Bulb />
        {t.trainer.ideasTitle}
        <span aria-hidden className="ml-auto text-muted transition-transform group-open:rotate-90">
          ›
        </span>
      </summary>
      <div className="mt-3">
        <IdeasCard text={text} raw={raw} learner={game.card.color} compact />
      </div>
    </details>
  );
}

/** Ходы до позиции (последние): «… 5. Nc3 a6 6. Be3». */
function PathLine({ nodes }: { nodes: CourseNode[] }) {
  const moves = nodes.filter((node) => node.san);
  const shown = moves.slice(-8);
  return (
    <p className="flex flex-wrap items-center gap-x-1 text-sm font-bold text-soft">
      {shown.length < moves.length && <span className="text-muted">…</span>}
      {shown.map((node, i) => {
        const white = moverColor(node) === "white";
        return (
          <span key={node.id} className="whitespace-nowrap">
            {(white || i === 0) && (
              <span className="mr-0.5 font-semibold text-muted">
                {moveNo(node.ply)}
                {white ? "." : "…"}
              </span>
            )}
            <Figurine san={node.san!} color={moverColor(node)} />
          </span>
        );
      })}
    </p>
  );
}

function EmptyQueue({
  totals,
  courseId,
  hasCards,
}: {
  totals: { learned: number; total: number };
  courseId: string | null;
  hasCards: boolean;
}) {
  const { t } = useI18n();
  if (!hasCards) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl bg-panel px-6 py-12 text-center">
        <p className="text-lg font-bold">{t.trainer.empty.title}</p>
        <p className="max-w-md text-soft">{t.trainer.empty.text}</p>
        <Link href="/openings/courses" className="mt-2 font-bold text-green hover:underline">
          {t.trainer.empty.link}
        </Link>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl bg-panel px-6 py-12 text-center">
      <ClassBadge value="best" size={40} />
      <p className="text-lg font-bold">{t.trainer.done.title}</p>
      <p className="max-w-md text-soft">{t.trainer.done.text(totals.learned, totals.total)}</p>
      <div className="mt-2 flex flex-wrap justify-center gap-4">
        {courseId && (
          <Link href={`/openings/courses/${courseId}`} className="font-bold text-green hover:underline">
            {t.trainer.done.course}
          </Link>
        )}
        <Link href="/openings/courses" className="font-bold text-green hover:underline">
          {t.trainer.done.all}
        </Link>
      </div>
    </div>
  );
}

export function TrainerSkeleton() {
  return (
    <div aria-busy className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="mx-auto aspect-square w-full animate-pulse rounded bg-raised/50" style={BOARD_WIDTH} />
      <div className="h-96 animate-pulse rounded-xl bg-panel" />
    </div>
  );
}
