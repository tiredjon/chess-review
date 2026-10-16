"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { applyUci, boardMoveUci, pieceOn, sideToMove, uciSan, uciSquares } from "@/lib/chess";
import { CLASS_META, type ClassKey } from "@/lib/classes";
import { formatDate } from "@/lib/format";
import { motifName } from "@/lib/motifs";
import { playMove, playSound, preloadSounds, toggleMuted, useSoundMuted } from "@/lib/sounds";
import type { Color, Puzzle, PuzzleAttempt, PuzzleCounts } from "@/lib/types";
import { Board, type BoardMarks } from "../review/board";
import { ClassBadge } from "../review/class-badge";
import { CoachBubble } from "../review/summary";
import { Button, ErrorText } from "../ui";

// Ход соперника (перед пазлом и ответы в решении) — с паузой, как у Chess.com.
const REPLY_DELAY_MS = 450;
const INTRO_DELAY_MS = 600;
const SOLUTION_STEP_MS = 800;
// Неверный ход виден на доске, потом откатывается.
const WRONG_SHOW_MS = 700;
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 6rem))" };

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";
const HINT = "rgba(92, 168, 222, 0.7)";
const BEST_ARROW = "rgba(127, 176, 74, 0.9)";

type Status = "intro" | "playing" | "waiting" | "solved" | "failed";

type Game = {
  puzzle: Puzzle;
  status: Status;
  fen: string;
  /** Сыгранные ходы пазла: игрок, ответ соперника, … */
  moves: string[];
  lastMove: string | null;
  /** Значок на клетке последнего хода игрока: верно / неверно. */
  badge: { square: string; value: ClassKey } | null;
  selected: string | null;
  hintShown: boolean;
  hintUsed: boolean;
  /** Итог попытки (solved / failed). */
  outcome: PuzzleAttempt | null;
  /** Верный ход стрелкой (после ошибки). */
  arrow: string | null;
  /** Индекс хода в решении, на котором игрок ошибся или сдался. */
  failedAt: number | null;
};

const opposite = (color: Color): Color => (color === "white" ? "black" : "white");

function startGame(puzzle: Puzzle): Game {
  return {
    puzzle,
    status: puzzle.last_move ? "intro" : "playing",
    fen: puzzle.last_move?.fen_before ?? puzzle.fen,
    moves: [],
    lastMove: null,
    badge: null,
    selected: null,
    hintShown: false,
    hintUsed: false,
    outcome: null,
    arrow: null,
    failedAt: null,
  };
}

/** Пазлы из своих ошибок: сначала пора повторить, затем новые. Ход проверяет сервер. */
export function PuzzleTrainer() {
  const [game, setGame] = useState<Game | null>(null);
  const [counts, setCounts] = useState<PuzzleCounts | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
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

  const fetchNext = useCallback(() => {
    api
      .nextPuzzle()
      .then((next) => {
        setCounts(next.counts);
        setGame(next.puzzle ? startGame(next.puzzle) : null);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить пазл"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(fetchNext, [fetchNext]);

  const load = useCallback(() => {
    clearTimers();
    setLoading(true);
    fetchNext();
  }, [clearTimers, fetchNext]);

  // Ход соперника, после которого возникла позиция пазла.
  const introId = game?.status === "intro" ? game.puzzle.id : null;
  useEffect(() => {
    if (!introId) return;
    const timer = setTimeout(() => {
      setGame((prev) => {
        if (!prev || prev.status !== "intro" || !prev.puzzle.last_move) return prev;
        const { uci, san } = prev.puzzle.last_move;
        playMove(san, opposite(prev.puzzle.color), prev.puzzle.color);
        return { ...prev, status: "playing", fen: prev.puzzle.fen, lastMove: uci };
      });
    }, INTRO_DELAY_MS);
    return () => clearTimeout(timer);
  }, [introId]);

  const finish = useCallback(
    (result: PuzzleAttempt) => {
      if (result.streak !== null) setCounts((prev) => (prev ? { ...prev, streak: result.streak! } : prev));
      setGame((prev) => (prev ? { ...prev, outcome: result } : prev));
    },
    [],
  );

  /** Проиграть решение с позиции после `from` ходов (после ошибки или «Показать решение»). */
  const playSolution = useCallback(
    (solution: string[], from: number) => {
      setGame((prev) => {
        if (!prev) return prev;
        let fen = prev.puzzle.fen;
        for (const uci of solution.slice(0, from)) fen = applyUci(fen, uci) ?? fen;
        return { ...prev, fen, moves: solution.slice(0, from), lastMove: null, badge: null, arrow: null };
      });
      solution.slice(from).forEach((uci, offset) => {
        later(SOLUTION_STEP_MS * (offset + 1), () =>
          setGame((prev) => {
            if (!prev) return prev;
            const san = uciSan(prev.fen, uci) ?? "";
            const mover = sideToMove(prev.fen);
            playMove(san, mover, prev.puzzle.color);
            const last = from + offset === solution.length - 1;
            return {
              ...prev,
              fen: applyUci(prev.fen, uci) ?? prev.fen,
              moves: [...prev.moves, uci],
              lastMove: uci,
              badge: last ? { square: uciSquares(uci).to, value: "best" } : null,
            };
          }),
        );
      });
    },
    [later],
  );

  const submit = useCallback(
    (current: Game, moves: string[], extra: { gave_up?: boolean } = {}) => {
      api
        .attemptPuzzle(current.puzzle.id, { moves_uci: moves, hint_used: current.hintUsed, ...extra })
        .then((result) => {
          if (result.result === "continue" && result.reply_uci) {
            const reply = result.reply_uci;
            later(REPLY_DELAY_MS, () =>
              setGame((prev) => {
                if (!prev || prev.puzzle.id !== current.puzzle.id) return prev;
                playMove(uciSan(prev.fen, reply) ?? "", opposite(prev.puzzle.color), prev.puzzle.color);
                return {
                  ...prev,
                  status: "playing",
                  fen: applyUci(prev.fen, reply) ?? prev.fen,
                  moves: [...prev.moves, reply],
                  lastMove: reply,
                  badge: null,
                  hintShown: false,
                };
              }),
            );
            return;
          }
          finish(result);
          const last = moves.at(-1);
          if (result.result === "solved") {
            later(200, () => playSound("correct"));
            setGame((prev) =>
              prev ? { ...prev, status: "solved", badge: last ? { square: uciSquares(last).to, value: "best" } : null } : prev,
            );
            return;
          }
          const solution = result.solution_uci ?? [];
          if (extra.gave_up) {
            // Сдался: решение проигрывается с текущей позиции.
            setGame((prev) => (prev ? { ...prev, status: "failed", hintShown: false, failedAt: moves.length } : prev));
            playSolution(solution, moves.length);
            return;
          }
          // Неверный ход виден со значком, затем откат и верный ход стрелкой.
          const prefix = moves.slice(0, -1);
          playSound("incorrect");
          setGame((prev) =>
            prev
              ? {
                  ...prev,
                  status: "failed",
                  hintShown: false,
                  failedAt: prefix.length,
                  badge: last ? { square: uciSquares(last).to, value: "blunder" } : null,
                }
              : prev,
          );
          later(WRONG_SHOW_MS, () =>
            setGame((prev) => {
              if (!prev) return prev;
              let fen = prev.puzzle.fen;
              for (const uci of prefix) fen = applyUci(fen, uci) ?? fen;
              return { ...prev, fen, moves: prefix, lastMove: prefix.at(-1) ?? null, badge: null, arrow: result.expected_uci };
            }),
          );
        })
        .catch((err) => {
          setError(err instanceof ApiError ? err.message : "Не удалось проверить ход");
          setGame((prev) => (prev ? startGame(prev.puzzle) : prev));
        });
    },
    [finish, later, playSolution],
  );

  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      if (!game || game.status !== "playing") return false;
      const uci = boardMoveUci(game.fen, from, to);
      if (!uci) {
        playSound("illegal");
        setGame({ ...game, selected: null });
        return false;
      }
      const san = uciSan(game.fen, uci) ?? "";
      playMove(san, game.puzzle.color, game.puzzle.color);
      const moves = [...game.moves, uci];
      const next: Game = {
        ...game,
        status: "waiting",
        fen: applyUci(game.fen, uci) ?? game.fen,
        moves,
        lastMove: uci,
        selected: null,
        badge: null,
        hintShown: false,
      };
      setGame(next);
      submit(next, moves);
      return true;
    },
    [game, submit],
  );

  const onSquareClick = useCallback(
    (square: string) => {
      if (!game || game.status !== "playing") return;
      if (game.selected && game.selected !== square && tryMove(game.selected, square)) return;
      if (game.selected === square) {
        setGame({ ...game, selected: null });
        return;
      }
      const piece = pieceOn(game.fen, square);
      const own = piece !== null && (piece === piece.toUpperCase()) === (game.puzzle.color === "white");
      setGame((prev) => (prev && prev.status === "playing" ? { ...prev, selected: own ? square : null } : prev));
    },
    [game, tryMove],
  );

  const showHint = () => setGame((prev) => (prev && prev.status === "playing" ? { ...prev, hintShown: true, hintUsed: true } : prev));

  const giveUp = () => {
    if (!game || game.status !== "playing") return;
    const next: Game = { ...game, status: "waiting" };
    setGame(next);
    submit(next, game.moves, { gave_up: true });
  };

  // Клавиши: M — звук, N / → — следующий пазл после завершения.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "m" || event.key === "M" || event.key === "ь" || event.key === "Ь") toggleMuted();
      if ((event.key === "n" || event.key === "ArrowRight") && (game?.status === "solved" || game?.status === "failed")) load();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [game?.status, load]);

  if (loading && !game) return <PuzzleSkeleton />;
  if (!game) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorText>{error}</ErrorText>
        {counts && <NoPuzzles counts={counts} />}
      </div>
    );
  }

  const { puzzle } = game;
  const playerMove = Math.floor(game.moves.length / 2);
  const highlights: Record<string, string> = {};
  if (game.lastMove) {
    const { from, to } = uciSquares(game.lastMove);
    const color =
      game.badge?.value === "blunder" ? `${CLASS_META.blunder.color}aa` : game.badge ? `${CLASS_META.best.color}aa` : LAST_MOVE;
    highlights[from] = color;
    highlights[to] = color;
  }
  if (game.selected) highlights[game.selected] = SELECTED;
  if (game.hintShown && puzzle.hints[playerMove]) highlights[puzzle.hints[playerMove]] = HINT;
  const marks: BoardMarks = {
    key: `${puzzle.id}-${game.moves.length}-${game.badge?.value ?? ""}-${game.arrow ?? ""}`,
    arrows: game.arrow
      ? [{ startSquare: uciSquares(game.arrow).from, endSquare: uciSquares(game.arrow).to, color: BEST_ARROW }]
      : [],
    highlights,
    badge: game.badge,
  };
  const finished = game.status === "solved" || game.status === "failed";

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="mx-auto w-full" style={BOARD_WIDTH}>
        <Board
          fen={game.fen}
          orientation={puzzle.color}
          marks={marks}
          interactive={game.status === "playing"}
          onMove={tryMove}
          onSquareClick={onSquareClick}
        />
      </div>

      <section aria-label="Пазл" className="flex min-w-0 flex-col rounded-xl bg-panel">
        <header className="flex items-center gap-3 rounded-t-xl border-b border-line bg-sunken/60 px-4 py-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-extrabold">
              Пазлы<span className="max-sm:hidden"> из ваших ошибок</span>
            </h2>
            {counts && (
              <p className="text-xs font-semibold text-muted">
                повторить {counts.due} · новых {counts.new} · всего {counts.total}
              </p>
            )}
          </div>
          <Streak value={counts?.streak ?? 0} />
          <button
            type="button"
            onClick={toggleMuted}
            aria-pressed={muted}
            aria-label={muted ? "Включить звук (M)" : "Выключить звук (M)"}
            title={muted ? "Включить звук (M)" : "Выключить звук (M)"}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-soft hover:bg-raised hover:text-ink"
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" />
              {muted ? <path d="m16 9.5 5 5m0-5-5 5" /> : <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />}
            </svg>
          </button>
        </header>

        <div key={puzzle.id} className="cc-slide-in flex flex-1 flex-col gap-4 p-4">
          <TurnBanner color={puzzle.color} status={game.status} />
          <CoachBubble>
            <StatusText game={game} />
          </CoachBubble>
          <ErrorText>{error}</ErrorText>

          {finished && game.outcome?.solution_san && (
            <div className="flex flex-col gap-2">
              <p className="text-sm font-semibold text-soft">Решение</p>
              <p className="flex flex-wrap gap-x-2 gap-y-1 text-[15px] font-bold">
                {game.outcome.solution_san.map((san, index) => (
                  <span key={index} className={index % 2 === 0 ? "text-ink" : "text-muted"}>
                    {san}
                  </span>
                ))}
              </p>
              {puzzle.themes.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {puzzle.themes.map((theme) => (
                    <span key={theme} className="rounded-md bg-raised px-2 py-1 text-xs font-semibold text-soft">
                      {motifName(theme)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {puzzle.source && <SourceLink source={puzzle.source} color={puzzle.color} />}

          {/* На телефоне действия липнут к низу экрана, как навигация в разборе. */}
          <div className="sticky bottom-0 -mx-4 -mb-4 mt-auto flex flex-col gap-2 rounded-b-xl border-t border-line bg-panel p-4 lg:static lg:mx-0 lg:mb-0 lg:border-0 lg:p-0 lg:pt-2">
            {finished ? (
              <>
                <Button size="lg" onClick={load} disabled={loading}>
                  {loading ? "Загружаю…" : "Следующий пазл"}
                </Button>
                {game.status === "failed" && game.outcome?.solution_uci && (
                  <Button
                    variant="raised"
                    onClick={() => {
                      clearTimers();
                      playSolution(game.outcome!.solution_uci!, 0);
                    }}
                  >
                    Показать решение с начала
                  </Button>
                )}
              </>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <Button variant="raised" onClick={showHint} disabled={game.status !== "playing" || game.hintShown}>
                  Подсказка
                </Button>
                <Button variant="raised" onClick={giveUp} disabled={game.status !== "playing"}>
                  Решение
                </Button>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function TurnBanner({ color, status }: { color: Color; status: Status }) {
  const text =
    status === "solved" ? "Решено" : status === "failed" ? "Не решено" : color === "white" ? "Ход белых" : "Ход чёрных";
  const tone =
    status === "solved" ? "bg-green text-white" : status === "failed" ? "bg-danger/90 text-white" : color === "white" ? "bg-white text-[#2c2925]" : "bg-sunken text-ink";
  return (
    <div className={`flex items-center gap-2 rounded-lg px-4 py-3 text-lg font-extrabold ${tone}`}>
      {status === "solved" && <ClassBadge value="best" size={24} title={false} />}
      {status === "failed" && <ClassBadge value="blunder" size={24} title={false} />}
      {text}
    </div>
  );
}

const relative = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

function whenText(iso: string | null): string {
  if (!iso) return "";
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (minutes < 60) return relative.format(Math.max(1, minutes), "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

function StatusText({ game }: { game: Game }) {
  const { puzzle, outcome } = game;
  if (game.status === "intro") return <>Соперник делает ход…</>;
  if (game.status === "solved" && outcome) {
    return (
      <>
        <span className="font-bold">Верно!</span>{" "}
        {game.hintUsed ? "С подсказкой — интервал не растёт." : "Отличная работа."} Снова покажем {whenText(outcome.next_review_at)}.
      </>
    );
  }
  if (game.status === "failed" && outcome) {
    const san = game.failedAt !== null ? outcome.solution_san?.[game.failedAt] : null;
    return (
      <>
        <span className="font-bold">Не то.</span> {san ? <>Верный ход — <span className="font-bold">{san}</span> (зелёная стрелка). </> : null}
        Пазл вернётся {whenText(outcome.next_review_at)}.
      </>
    );
  }
  if (game.status === "waiting") return <>Проверяю ход…</>;
  const total = puzzle.player_moves;
  const done = Math.floor(game.moves.length / 2);
  if (done > 0) return <>Верно, продолжайте! Ход {done + 1} из {total}.</>;
  return (
    <>
      В партии здесь была ошибка. Найдите лучший ход
      {total > 1 ? ` — решение в ${total} ${total < 5 ? "хода" : "ходов"}` : ""}.
      {puzzle.box > 0 || puzzle.attempts > 0 ? " Это повторение." : ""}
    </>
  );
}

function SourceLink({ source, color }: { source: NonNullable<Puzzle["source"]>; color: Color }) {
  const value: ClassKey = source.is_miss && !["mistake", "blunder"].includes(source.class) ? "miss" : source.class;
  const number = `${source.fullmove}${color === "white" ? "." : "…"}`;
  return (
    <Link
      href={`/games/${source.game_id}?ply=${source.ply}`}
      className="flex items-center gap-2 rounded-lg bg-raised/60 px-3 py-2.5 text-sm text-soft hover:bg-raised hover:text-ink"
    >
      <ClassBadge value={value} size={20} />
      <span className="min-w-0 flex-1">
        Из партии против <span className="font-bold text-ink">{source.opponent}</span>
        {source.played_at && <>, {formatDate(source.played_at)}</>}: в партии было{" "}
        <span className="font-bold text-ink">
          {number} {source.san}
        </span>{" "}
        ({CLASS_META[value].label.toLowerCase()})
      </span>
      <span aria-hidden className="text-muted">
        →
      </span>
    </Link>
  );
}

function Streak({ value }: { value: number }) {
  return (
    <div
      title="Решено подряд"
      aria-label={`Решено подряд: ${value}`}
      className="flex h-9 items-center gap-1 rounded-lg bg-raised px-2.5 text-sm font-extrabold"
    >
      <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill={value > 0 ? "#f59a4c" : "var(--muted)"}>
        <path d="M12 2c1 3.5 5 5.5 5 11a5 5 0 0 1-10 0c0-2.2 1-3.8 2-5 .2 1.7 1 2.8 2 3 0-3.5-.5-6 1-9z" />
      </svg>
      {value}
    </div>
  );
}

function NoPuzzles({ counts }: { counts: PuzzleCounts }) {
  if (counts.total === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl bg-panel px-6 py-12 text-center">
        <p className="text-lg font-bold">Пазлов пока нет</p>
        <p className="max-w-md text-soft">
          Пазлы появляются из ваших ошибок в разобранных партиях (нужен ваш цвет в партии).{" "}
          <Link href="/games" className="font-bold text-green hover:underline">
            Разберите партии
          </Link>
          .
        </p>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl bg-panel px-6 py-12 text-center">
      <ClassBadge value="best" size={40} />
      <p className="text-lg font-bold">На сейчас всё решено</p>
      <p className="text-soft">
        Следующее повторение — {whenText(counts.next_review_at)}. Решено подряд: {counts.streak}.
      </p>
    </div>
  );
}

export function PuzzleSkeleton() {
  return (
    <div aria-busy className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="mx-auto aspect-square w-full animate-pulse rounded bg-raised/50" style={BOARD_WIDTH} />
      <div className="h-96 animate-pulse rounded-xl bg-panel" />
    </div>
  );
}
