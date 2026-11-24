"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { boardMoveUci, pieceOn, uciSquares } from "@/lib/chess";
import { useI18n } from "@/lib/i18n/use-i18n";
import { playMove, preloadSounds } from "@/lib/sounds";
import type { Color } from "@/lib/types";
import { Board, NO_MARKS, type BoardMarks } from "../review/board";
import { moverColor, type NodeIndex, type OpeningNode } from "./types";

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";
// Цвета стрелок: ходы ученика — зелёные, ответы соперника — синие.
const ARROW_COLORS = { learner: "#96bc4b", opponent: "#6f98c2", none: "#96bc4b" } as const;
// Стрелки появляются, когда фигура доехала (как отметки на доске разбора).
const ARROW_DELAY_MS = 200;

/**
 * Доска позиции узла дерева дебютов (репертуар и курс).
 *
 * Пропсы:
 *  - `index` — узлы по id (`NodeIndex`), `currentId` — показываемый узел;
 *  - `orientation` — цвет ученика внизу;
 *  - `onSelect(id)` — переход в узел: по клику / перетаскиванию фигуры ходом из детей текущего
 *    узла (ход вне дерева возвращает фигуру и вызывает `onMiss(uci)`, если он легален);
 *  - `weights` — вес хода-ребёнка (по id ребёнка), 0…1: толщина и плотность его стрелки; без
 *    него все стрелки одинаковые. `arrows={false}` — без стрелок;
 *  - `interactive={false}` — доска только показывает позицию;
 *  - звук хода играется при каждой смене узла (приглушается общим переключателем звука).
 */
export function OpeningBoard<N extends OpeningNode>({
  index,
  currentId,
  orientation,
  onSelect,
  onMiss,
  weights,
  arrows = true,
  interactive = true,
}: {
  index: NodeIndex<N>;
  currentId: number;
  orientation: Color;
  onSelect: (id: number) => void;
  onMiss?: (uci: string) => void;
  weights?: Record<number, number>;
  arrows?: boolean;
  interactive?: boolean;
}) {
  const { t } = useI18n();
  const node = index.get(currentId);
  const fen = node?.fen ?? "";
  // Выбранная клетка (ход кликами) относится к узлу, где её выбрали: при смене узла сбрасывается.
  const [pick, setPick] = useState<{ id: number; square: string } | null>(null);
  const selected = pick?.id === currentId ? pick.square : null;

  const children = useMemo(
    () => (node?.children ?? []).flatMap((id) => index.get(id) ?? []),
    [index, node],
  );

  // Звук хода при переходе в узел (первый показ без звука); выбор клетки сбрасывается.
  const previousId = useRef<number | null>(null);
  useEffect(preloadSounds, []);
  useEffect(() => {
    if (previousId.current !== null && previousId.current !== currentId && node?.san) {
      playMove(node.san, moverColor(node), orientation);
    }
    previousId.current = currentId;
  }, [currentId, node, orientation]);

  const childByUci = useCallback(
    (uci: string) => children.find((child) => child.uci === uci),
    [children],
  );

  /** Ход с доски: переход в ребёнка, если такой ход есть в дереве. */
  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      const uci = boardMoveUci(fen, from, to);
      if (uci === null) return false;
      const child = childByUci(uci);
      if (child) {
        onSelect(child.id);
        return true;
      }
      onMiss?.(uci);
      return false;
    },
    [fen, childByUci, onSelect, onMiss],
  );

  const onSquareClick = useCallback(
    (square: string) => {
      if (!interactive) return;
      if (selected && selected !== square && tryMove(selected, square)) return;
      const piece = pieceOn(fen, square);
      const ownTurn = piece !== null && (piece === piece.toUpperCase()) === (fen.split(" ")[1] === "w");
      setPick(ownTurn && square !== selected ? { id: currentId, square } : null);
    },
    [interactive, selected, fen, tryMove, currentId],
  );

  const marks = useMemo<BoardMarks>(() => {
    const highlights: Record<string, string> = {};
    if (node?.uci) {
      const { from, to } = uciSquares(node.uci);
      highlights[from] = LAST_MOVE;
      highlights[to] = LAST_MOVE;
    }
    if (selected) highlights[selected] = SELECTED;
    return { ...NO_MARKS, key: `n${currentId}`, highlights };
  }, [node, currentId, selected]);

  if (!node) return null;
  return (
    <div className="relative" aria-label={t.repertoire.shared.board}>
      <Board
        fen={fen}
        orientation={orientation}
        marks={marks}
        interactive={interactive}
        onMove={(from, to) => tryMove(from, to)}
        onSquareClick={interactive ? onSquareClick : undefined}
      />
      {arrows && children.length > 0 && (
        <Arrows key={currentId} orientation={orientation} nodes={children} weights={weights} />
      )}
    </div>
  );
}

// ---------- стрелки на ходы-детей (свой SVG: у react-chessboard одна толщина на все) ----------

const square = (name: string, orientation: Color) => {
  const file = name.charCodeAt(0) - 97;
  const rank = Number(name[1]) - 1;
  return orientation === "white" ? { x: file + 0.5, y: 7 - rank + 0.5 } : { x: 7 - file + 0.5, y: rank + 0.5 };
};

function Arrows({
  nodes,
  orientation,
  weights,
}: {
  nodes: OpeningNode[];
  orientation: Color;
  weights?: Record<number, number>;
}) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setShown(true), ARROW_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);
  if (!shown) return null;
  // Тонкие — позади, чтобы редкий ход не перекрывал частый.
  const sorted = [...nodes].sort((a, b) => (weights?.[a.id] ?? 1) - (weights?.[b.id] ?? 1));
  return (
    <svg
      aria-hidden
      viewBox="0 0 8 8"
      className="pointer-events-none absolute inset-0 z-20 h-full w-full"
    >
      {sorted.map((child) => {
        if (!child.uci) return null;
        const { from, to } = uciSquares(child.uci);
        const weight = Math.min(1, Math.max(0, weights?.[child.id] ?? 1));
        return (
          <polygon
            key={child.id}
            points={arrowPoints(square(from, orientation), square(to, orientation), 0.1 + 0.14 * weight)}
            fill={ARROW_COLORS[child.mover ?? "none"]}
            opacity={0.5 + 0.4 * weight}
          />
        );
      })}
    </svg>
  );
}

/** Стрелка-многоугольник от клетки к клетке: древко толщиной `width`, голова крупнее. */
function arrowPoints(from: { x: number; y: number }, to: { x: number; y: number }, width: number): string {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy);
  const ux = dx / length;
  const uy = dy / length;
  const px = -uy;
  const py = ux;
  const head = Math.min(0.45, length * 0.5);
  const headHalf = width * 0.5 + 0.13;
  // Начало — чуть дальше центра клетки, конец — чуть не доходит до центра цели.
  const startX = from.x + ux * 0.2;
  const startY = from.y + uy * 0.2;
  const tipX = to.x - ux * 0.12;
  const tipY = to.y - uy * 0.12;
  const baseX = tipX - ux * head;
  const baseY = tipY - uy * head;
  const half = width / 2;
  return [
    [startX + px * half, startY + py * half],
    [baseX + px * half, baseY + py * half],
    [baseX + px * headHalf, baseY + py * headHalf],
    [tipX, tipY],
    [baseX - px * headHalf, baseY - py * headHalf],
    [baseX - px * half, baseY - py * half],
    [startX - px * half, startY - py * half],
  ]
    .map(([x, y]) => `${x.toFixed(3)},${y.toFixed(3)}`)
    .join(" ");
}
