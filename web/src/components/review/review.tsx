"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { CLASS_META, displayClass } from "@/lib/classes";
import { boardMoveUci, lineFens, sideToMove, uciSquares, type Ply } from "@/lib/chess";
import { lineEval, positionEvals, type WhiteEval } from "@/lib/eval";
import type { Color, LineMove } from "@/lib/types";
import { Board, NO_MARKS, type BoardMarks } from "./board";
import { EvalBar } from "./eval-bar";
import { EvalGraph } from "./eval-graph";
import { Button } from "../ui";
import { ClassBadge } from "./class-badge";
import { MoveList } from "./move-list";
import { LinePanel, MovePanel, RetryPanel, type Explanation, type LineKind, type RetryStatus } from "./move-panel";

type Mode =
  | { kind: "game" }
  | {
      kind: "line";
      title: string;
      baseFen: string;
      fens: string[];
      line: LineMove[];
      step: number;
      evaluation: WhiteEval | null;
    }
  | { kind: "retry"; plyIndex: number; status: RetryStatus; fen: string; selected: string | null };

const GAME: Mode = { kind: "game" };
// Доска с плашками игроков помещается в экран по высоте.
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 8.5rem))" };
const LINE_STEP_MS = 900;
const EXPLAIN_DELAY_MS = 250;

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const LINE_MOVE = "rgba(111, 152, 194, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";

const alpha = (hex: string, value: string) => `${hex}${value}`;

function moveMarks(ply: Ply): BoardMarks {
  const { from, to } = uciSquares(ply.uci);
  const move = ply.move;
  if (!move) return { arrows: [], highlights: { [from]: LAST_MOVE, [to]: LAST_MOVE }, badge: null };
  const value = displayClass(move);
  const color = CLASS_META[value].color;
  const marks: BoardMarks = {
    arrows: [],
    highlights: { [from]: alpha(color, "88"), [to]: alpha(color, "bb") },
    badge: { square: to, value },
  };
  // Лучший ход — зелёной стрелкой, сыгранный — стрелкой цвета класса (если они разные).
  if (move.best_uci && move.best_uci !== move.uci && !["book", "forced"].includes(move.class)) {
    const best = uciSquares(move.best_uci);
    marks.arrows = [
      { startSquare: from, endSquare: to, color: alpha(color, "cc") },
      { startSquare: best.from, endSquare: best.to, color: alpha(CLASS_META.best.color, "dd") },
    ];
  }
  return marks;
}

function isTyping(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function Review({
  plies,
  startFen,
  initialOrientation,
  player,
  subtitle,
  status,
  overview,
}: {
  plies: Ply[];
  startFen: string;
  initialOrientation: Color;
  /** Плашка игрока над / под доской. */
  player: (color: Color) => ReactNode;
  /** Дебют, дата — под заголовком панели. */
  subtitle: ReactNode;
  /** Пока анализа нет: статус и кнопка запуска. */
  status: ReactNode;
  /** Обзор партии (итог, точность, классы), когда анализ готов. */
  overview: ReactNode;
}) {
  const [cursor, setCursor] = useState(0);
  // Панель: обзор партии или разбор по ходам (как «Начать разбор»).
  const [view, setView] = useState<"overview" | "moves">("overview");
  const [mode, setMode] = useState<Mode>(GAME);
  const [playing, setPlaying] = useState(false);
  const [orientation, setOrientation] = useState<Color>(initialOrientation);
  const [explanations, setExplanations] = useState<Record<number, Explanation>>({});
  const requested = useRef(new Set<number>());

  const analysed = plies.length > 0 && plies.every((ply) => ply.move !== null);
  const evals = useMemo(
    () => (analysed ? positionEvals(plies.map((ply) => ply.move!)) : []),
    [analysed, plies],
  );
  const current = cursor > 0 ? plies[cursor - 1] : null;

  const goTo = useCallback(
    (index: number) => {
      setMode(GAME);
      setPlaying(false);
      setView("moves");
      setCursor(Math.max(0, Math.min(plies.length, index)));
    },
    [plies.length],
  );

  // Ленивая загрузка объяснения текущего хода; при быстром листании — только последнего.
  const currentMoveId = mode.kind === "game" ? (current?.move?.id ?? null) : null;
  useEffect(() => {
    if (currentMoveId === null || requested.current.has(currentMoveId)) return;
    const timer = setTimeout(() => {
      requested.current.add(currentMoveId);
      api
        .explainMove(currentMoveId)
        .then((result) => setExplanations((prev) => ({ ...prev, [currentMoveId]: { text: result.text } })))
        .catch((err) => {
          requested.current.delete(currentMoveId);
          const error = err instanceof ApiError ? err.message : "Объяснение недоступно";
          setExplanations((prev) => ({ ...prev, [currentMoveId]: { error } }));
        });
    }, EXPLAIN_DELAY_MS);
    return () => clearTimeout(timer);
  }, [currentMoveId]);

  // Проигрывание линии.
  useEffect(() => {
    if (!playing || mode.kind !== "line") return;
    if (mode.step >= mode.line.length) return;
    const timer = setTimeout(() => {
      setMode((prev) => (prev.kind === "line" ? { ...prev, step: prev.step + 1 } : prev));
    }, LINE_STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, mode]);

  const lineEnded = mode.kind === "line" && mode.step >= mode.line.length;
  const effectivePlaying = playing && !lineEnded;

  const showLine = useCallback(
    (kind: LineKind) => {
      const move = current?.move;
      if (!current || !move) return;
      const line = (kind === "best" ? move.pv : move.reply_pv) ?? [];
      const baseFen = kind === "best" ? current.fenBefore : current.fenAfter;
      const fens = lineFens(baseFen, line);
      const best = move.multipv?.[0];
      setMode({
        kind: "line",
        title: kind === "best" ? (move.best_uci === move.uci ? "Продолжение" : "Лучшая линия") : "Чем наказывается",
        baseFen,
        fens,
        line: line.slice(0, fens.length - 1),
        step: 0,
        evaluation:
          kind === "best"
            ? best
              ? lineEval(current.color, best.cp, best.mate)
              : (evals[cursor - 1] ?? null)
            : (evals[cursor] ?? null),
      });
      setPlaying(true);
    },
    [current, cursor, evals],
  );

  const startRetry = useCallback(() => {
    if (!current) return;
    setPlaying(false);
    setMode({ kind: "retry", plyIndex: current.index, status: "waiting", fen: current.fenBefore, selected: null });
  }, [current]);

  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      if (mode.kind !== "retry" || mode.status === "solved") return false;
      const ply = plies[mode.plyIndex];
      const uci = boardMoveUci(mode.fen, from, to);
      if (!uci) {
        setMode({ ...mode, selected: null });
        return false;
      }
      const best = ply.move?.best_uci ?? "";
      // Превращение с доски — всегда в ферзя; клетки «откуда-куда» достаточно.
      if (uci.slice(0, 4) === best.slice(0, 4)) {
        setMode({ ...mode, status: "solved", fen: lineFens(mode.fen, [{ uci: best, san: "" }]).at(-1)!, selected: null });
        return true;
      }
      setMode({ ...mode, status: "wrong", selected: null });
      return false;
    },
    [mode, plies],
  );

  const onSquareClick = useCallback(
    (square: string) => {
      if (mode.kind !== "retry" || mode.status === "solved") return;
      if (mode.selected && mode.selected !== square && tryMove(mode.selected, square)) return;
      if (mode.selected === square) {
        setMode({ ...mode, selected: null });
        return;
      }
      // Выбрать можно только свою фигуру; иначе сброс выбора (tryMove уже сбросил).
      const piece = pieceAt(mode.fen, square);
      const own = piece !== null && (piece === piece.toUpperCase()) === (sideToMove(mode.fen) === "white");
      setMode((prev) => (prev.kind === "retry" && prev.status !== "solved" ? { ...prev, selected: own ? square : null } : prev));
    },
    [mode, tryMove],
  );

  // Клавиатура: ← → по ходам (или по линии), ↑/Home — начало, ↓/End — конец, Esc — к партии, F — перевернуть.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      const key = event.key;
      if (key === "f" || key === "F" || key === "а" || key === "А") {
        setOrientation((o) => (o === "white" ? "black" : "white"));
        return;
      }
      if (key === "Escape") {
        setMode(GAME);
        setPlaying(false);
        return;
      }
      const delta =
        key === "ArrowLeft" ? -1 : key === "ArrowRight" ? 1 : key === "ArrowUp" || key === "Home" ? -Infinity : key === "ArrowDown" || key === "End" ? Infinity : 0;
      if (delta === 0) return;
      event.preventDefault();
      if (mode.kind === "line") {
        setPlaying(false);
        setMode({ ...mode, step: Math.max(0, Math.min(mode.line.length, mode.step + delta)) });
      } else if (mode.kind === "game") {
        setView("moves");
        setCursor((c) => Math.max(0, Math.min(plies.length, c + delta)));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, plies.length]);

  // Что на доске.
  let fen = cursor > 0 ? plies[cursor - 1].fenAfter : startFen;
  let marks: BoardMarks = current ? moveMarks(current) : NO_MARKS;
  let evaluation: WhiteEval | null = evals[cursor] ?? null;
  if (mode.kind === "line") {
    fen = mode.fens[mode.step];
    const last = mode.step > 0 ? mode.line[mode.step - 1] : null;
    const next = mode.line[mode.step];
    const highlights: Record<string, string> = {};
    if (last) {
      const { from, to } = uciSquares(last.uci);
      highlights[from] = LINE_MOVE;
      highlights[to] = LINE_MOVE;
    }
    marks = {
      arrows: next && !effectivePlaying ? [{ startSquare: next.uci.slice(0, 2), endSquare: next.uci.slice(2, 4), color: "rgba(91,139,180,0.75)" }] : [],
      highlights,
      badge: null,
    };
    evaluation = mode.evaluation;
  } else if (mode.kind === "retry") {
    fen = mode.fen;
    const ply = plies[mode.plyIndex];
    evaluation = evals[mode.plyIndex] ?? null;
    marks = { arrows: [], highlights: mode.selected ? { [mode.selected]: SELECTED } : {}, badge: null };
    if (mode.status === "solved" && ply.move?.best_uci) {
      const { from, to } = uciSquares(ply.move.best_uci);
      marks = {
        arrows: [],
        highlights: { [from]: alpha(CLASS_META.best.color, "88"), [to]: alpha(CLASS_META.best.color, "bb") },
        badge: { square: to, value: "best" },
      };
    }
  }

  let panel: ReactNode;
  if (mode.kind === "line") {
    panel = (
      <LinePanel
        title={mode.title}
        baseFen={mode.baseFen}
        line={mode.line}
        step={mode.step}
        playing={effectivePlaying}
        onStep={(step) => {
          setPlaying(false);
          setMode({ ...mode, step });
        }}
        onTogglePlay={() => {
          if (lineEnded) {
            setMode({ ...mode, step: 0 });
            setPlaying(true);
          } else setPlaying(!effectivePlaying);
        }}
        onClose={() => goTo(cursor)}
      />
    );
  } else if (mode.kind === "retry") {
    const ply = plies[mode.plyIndex];
    panel = (
      <RetryPanel
        ply={ply}
        status={mode.status}
        onShowAnswer={() => {
          const best = ply.move?.best_uci;
          if (best) tryMove(best.slice(0, 2), best.slice(2, 4));
        }}
        onShowLine={() => showLine("best")}
        onClose={() => goTo(cursor)}
      />
    );
  } else {
    panel = (
      <MovePanel
        ply={current}
        explanation={current?.move ? explanations[current.move.id] : undefined}
        onShowLine={showLine}
        onRetry={startRetry}
      />
    );
  }

  const showOverview = analysed && view === "overview" && mode.kind === "game";
  const flip = () => setOrientation((o) => (o === "white" ? "black" : "white"));

  // Десктоп: доска слева, панель справа высотой с блок доски, но не ниже экрана
  // (h-0 + min-h), внутри панели прокручивается список ходов или обзор.
  // Телефон: доска, затем панель целиком.
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      {/* На телефоне доска липнет под шапкой, панель прокручивается под ней. */}
      <div
        className="z-20 mx-auto flex w-full flex-col gap-2 max-lg:sticky max-lg:top-14 max-lg:-mx-3 max-lg:w-auto max-lg:bg-page max-lg:px-3 max-lg:pb-2"
        style={BOARD_WIDTH}
      >
        {player(orientation === "white" ? "black" : "white")}
        <div className="flex gap-1.5 sm:gap-2">
          <div className="w-4 shrink-0 sm:w-7">
            <EvalBar evaluation={evaluation} orientation={orientation} />
          </div>
          <div className="min-w-0 flex-1">
            <Board
              fen={fen}
              orientation={orientation}
              marks={marks}
              interactive={mode.kind === "retry" && mode.status !== "solved"}
              onMove={tryMove}
              onSquareClick={mode.kind === "retry" ? onSquareClick : undefined}
            />
          </div>
        </div>
        {player(orientation)}
      </div>

      <section
        aria-label="Разбор партии"
        className="flex min-w-0 flex-col rounded-xl bg-panel lg:h-0 lg:min-h-[max(100%,calc(100dvh-2rem))] lg:overflow-hidden"
      >
        <header className="flex items-center gap-3 rounded-t-xl border-b border-line bg-sunken/60 px-4 py-3">
          {analysed && view === "moves" && (
            <button
              type="button"
              onClick={() => {
                setMode(GAME);
                setPlaying(false);
                setView("overview");
              }}
              aria-label="К обзору партии"
              title="К обзору партии"
              className="flex h-9 w-9 items-center justify-center rounded-lg text-soft hover:bg-raised hover:text-ink"
            >
              <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5">
                <path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 text-lg font-extrabold">
              <ClassBadge value="best" size={22} title={false} />
              Разбор партии
            </h2>
            <p className="truncate text-xs font-semibold text-muted">{subtitle}</p>
          </div>
        </header>

        {showOverview ? (
          <>
            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
              {overview}
              <EvalGraph evals={evals} plies={plies} cursor={cursor} onSelect={goTo} />
            </div>
            {/* На телефоне главная кнопка и навигация липнут к низу экрана. */}
            <div className="sticky bottom-0 rounded-b-xl border-t border-line bg-panel p-4 lg:static">
              <Button size="lg" className="w-full" onClick={() => goTo(Math.max(cursor, 1))}>
                Начать разбор
              </Button>
            </div>
          </>
        ) : (
          <>
            {/* Верх (ход, объяснение, график) уступает место списку ходов и прокручивается сам. */}
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex flex-col gap-3 p-4 pb-3 lg:min-h-0 lg:shrink lg:overflow-y-auto">
                {analysed || mode.kind !== "game" ? panel : status}
                {analysed && <EvalGraph evals={evals} plies={plies} cursor={cursor} onSelect={goTo} compact />}
              </div>
              <MoveList
                plies={plies}
                cursor={mode.kind === "game" ? cursor : -1}
                onSelect={goTo}
                className="max-h-80 border-t border-line lg:max-h-none lg:flex-[1_0_13rem]"
              />
            </div>
            <NavBar cursor={cursor} total={plies.length} onGo={goTo} onFlip={flip} />
          </>
        )}
      </section>
    </div>
  );
}

function pieceAt(fen: string, square: string): string | null {
  const rows = fen.split(" ")[0].split("/");
  const file = square.charCodeAt(0) - 97;
  const rank = 8 - Number(square[1]);
  let col = 0;
  for (const char of rows[rank] ?? "") {
    if (/\d/.test(char)) col += Number(char);
    else {
      if (col === file) return char;
      col += 1;
    }
  }
  return null;
}

const NAV_ICONS = {
  first: "M7 6v12M18 6l-7 6 7 6z",
  prev: "M16 6l-8 6 8 6z",
  next: "M8 6l8 6-8 6z",
  last: "M17 6v12M6 6l7 6-7 6z",
  flip: "M8 4v14m0 0-3-3m3 3 3-3M16 20V6m0 0-3 3m3-3 3 3",
};

function NavBar({
  cursor,
  total,
  onGo,
  onFlip,
}: {
  cursor: number;
  total: number;
  onGo: (index: number) => void;
  onFlip: () => void;
}) {
  const buttons: [keyof typeof NAV_ICONS, string, () => void, boolean][] = [
    ["first", "К началу (↑)", () => onGo(0), cursor === 0],
    ["prev", "Ход назад (←)", () => onGo(cursor - 1), cursor === 0],
    ["next", "Ход вперёд (→)", () => onGo(cursor + 1), cursor >= total],
    ["last", "К концу (↓)", () => onGo(total), cursor >= total],
    ["flip", "Перевернуть доску (F)", onFlip, false],
  ];
  return (
    <div
      className="sticky bottom-0 grid grid-cols-[1fr_1fr_1.4fr_1fr_0.8fr] gap-1.5 rounded-b-xl border-t border-line bg-panel p-3 lg:static"
      role="toolbar"
      aria-label="Навигация по ходам"
    >
      {buttons.map(([icon, label, action, disabled]) => (
        <button
          key={icon}
          type="button"
          onClick={action}
          disabled={disabled}
          aria-label={label}
          title={label}
          className="flex h-12 items-center justify-center rounded-lg bg-raised text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink active:translate-y-[2px] active:shadow-none disabled:opacity-35 disabled:hover:bg-raised"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6">
            <path
              d={NAV_ICONS[icon]}
              fill={icon === "flip" ? "none" : "currentColor"}
              stroke="currentColor"
              strokeWidth={icon === "flip" ? 2.2 : 1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      ))}
    </div>
  );
}
