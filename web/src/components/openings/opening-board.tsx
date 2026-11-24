"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Arrow } from "react-chessboard";
import { boardMoveUci, pieceOn, uciSquares } from "@/lib/chess";
import { useI18n } from "@/lib/i18n/use-i18n";
import { playMove, preloadSounds } from "@/lib/sounds";
import type { Color } from "@/lib/types";
import { Board, NO_MARKS, type BoardMarks } from "../review/board";
import { moverColor, type NodeIndex, type OpeningNode } from "./types";

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const SELECTED = "rgba(127, 176, 74, 0.6)";
// Цвета стрелок — палитра доски разбора: ходы ученика — зелёные, ответы соперника — синие.
const ARROW_RGB = { learner: "150, 188, 75", opponent: "111, 152, 194", none: "150, 188, 75" } as const;

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
    return { ...NO_MARKS, key: `n${currentId}`, highlights, arrows: arrows ? childArrows(children, weights) : [] };
  }, [node, currentId, selected, arrows, children, weights]);

  if (!node) return null;
  return (
    <div aria-label={t.repertoire.shared.board}>
      <Board
        fen={fen}
        orientation={orientation}
        marks={marks}
        interactive={interactive}
        onMove={(from, to) => tryMove(from, to)}
        onSquareClick={interactive ? onSquareClick : undefined}
      />
    </div>
  );
}

/**
 * Стрелки на ходы-детей — стрелки самой доски (форма и анимация как в разборе). Вес хода
 * задаёт плотность стрелки; редкие ходы идут первыми, чтобы не перекрывать частые.
 */
function childArrows(children: OpeningNode[], weights?: Record<number, number>): Arrow[] {
  const weightOf = (child: OpeningNode) => Math.min(1, Math.max(0, weights?.[child.id] ?? 1));
  return [...children]
    .filter((child) => child.uci)
    .sort((a, b) => weightOf(a) - weightOf(b))
    .map((child) => {
      const { from, to } = uciSquares(child.uci as string);
      const alpha = (0.35 + 0.6 * weightOf(child)).toFixed(2);
      return { startSquare: from, endSquare: to, color: `rgba(${ARROW_RGB[child.mover ?? "none"]}, ${alpha})` };
    });
}
