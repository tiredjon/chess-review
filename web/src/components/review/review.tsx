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
// Доска с панелью навигации помещается в экран по высоте.
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 16rem))" };
// Карточкам игроков под доской нужно хотя бы 36rem даже на низком экране.
const BELOW_BOARD_WIDTH = { maxWidth: "min(100%, max(36rem, calc(100dvh - 16rem)))" };
const LINE_STEP_MS = 900;
const EXPLAIN_DELAY_MS = 250;

const LAST_MOVE = "rgba(234, 196, 74, 0.42)";
const LINE_MOVE = "rgba(91, 139, 180, 0.45)";
const SELECTED = "rgba(43, 78, 181, 0.35)";

const alpha = (hex: string, value: string) => `${hex}${value}`;

function moveMarks(ply: Ply): BoardMarks {
  const { from, to } = uciSquares(ply.uci);
  const move = ply.move;
  if (!move) return { arrows: [], highlights: { [from]: LAST_MOVE, [to]: LAST_MOVE }, badge: null };
  const value = displayClass(move);
  const color = CLASS_META[value].color;
  const marks: BoardMarks = {
    arrows: [],
    highlights: { [from]: alpha(color, "55"), [to]: alpha(color, "77") },
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
  topPlayer,
  bottomPlayer,
  sidePanel,
  aside,
}: {
  plies: Ply[];
  startFen: string;
  initialOrientation: Color;
  topPlayer: (orientation: Color) => ReactNode;
  bottomPlayer: (orientation: Color) => ReactNode;
  /** Вместо панели хода, пока анализа нет (статус, кнопка запуска). */
  sidePanel: ReactNode;
  /** Карточки игроков и итог — под списком ходов. */
  aside: ReactNode;
}) {
  const [cursor, setCursor] = useState(0);
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
        highlights: { [from]: alpha(CLASS_META.best.color, "55"), [to]: alpha(CLASS_META.best.color, "77") },
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
  } else if (sidePanel && !analysed) {
    panel = sidePanel;
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

  // Сетка: доска (слева сверху), панель и список ходов (справа, вровень с доской),
  // график, карточки и итог (слева под доской). На телефоне — в этом же порядке DOM.
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-x-6">
      <div className="mx-auto flex w-full flex-col gap-2 lg:col-start-1 lg:row-start-1" style={BOARD_WIDTH}>
        {topPlayer(orientation)}
        <div className="flex gap-1.5 sm:gap-2">
          <div className="w-4 shrink-0 sm:w-6">
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
        {bottomPlayer(orientation)}
        <NavBar
          cursor={cursor}
          total={plies.length}
          onGo={goTo}
          onFlip={() => setOrientation((o) => (o === "white" ? "black" : "white"))}
        />
      </div>

      {/* h-0 + min-h-full: высота колонки = высота блока доски, список ходов прокручивается внутри. */}
      <div className="flex min-w-0 flex-col gap-3 lg:col-start-2 lg:row-start-1 lg:h-0 lg:min-h-full">
        {panel}
        <MoveList plies={plies} cursor={mode.kind === "game" ? cursor : -1} onSelect={goTo} />
      </div>

      <div className="mx-auto flex w-full min-w-0 flex-col gap-3 lg:col-start-1 lg:row-start-2" style={BELOW_BOARD_WIDTH}>
        {analysed && <EvalGraph evals={evals} plies={plies} cursor={cursor} onSelect={goTo} />}
        {aside}
      </div>
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
  const button =
    "flex h-11 flex-1 items-center justify-center rounded-lg border border-line bg-surface text-lg hover:bg-sunken disabled:opacity-40 disabled:hover:bg-surface";
  return (
    <div className="flex gap-1.5" role="toolbar" aria-label="Навигация по ходам">
      <button type="button" className={button} onClick={() => onGo(0)} disabled={cursor === 0} aria-label="К началу (↑)" title="К началу (↑)">
        ⏮
      </button>
      <button type="button" className={button} onClick={() => onGo(cursor - 1)} disabled={cursor === 0} aria-label="Ход назад (←)" title="Ход назад (←)">
        ◀
      </button>
      <button type="button" className={button} onClick={() => onGo(cursor + 1)} disabled={cursor >= total} aria-label="Ход вперёд (→)" title="Ход вперёд (→)">
        ▶
      </button>
      <button type="button" className={button} onClick={() => onGo(total)} disabled={cursor >= total} aria-label="К концу (↓)" title="К концу (↓)">
        ⏭
      </button>
      <button type="button" className={`${button} max-w-14`} onClick={onFlip} aria-label="Перевернуть доску (F)" title="Перевернуть доску (F)">
        ⇅
      </button>
    </div>
  );
}
