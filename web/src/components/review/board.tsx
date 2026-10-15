"use client";

import { useCallback, type CSSProperties } from "react";
import { Chessboard, type Arrow, type SquareRenderer } from "react-chessboard";
import type { ClassKey } from "@/lib/classes";
import type { Color } from "@/lib/types";
import { ClassBadge } from "./class-badge";

export type BoardMarks = {
  arrows: Arrow[];
  /** Подсветка клеток: клетка → цвет (полупрозрачный). */
  highlights: Record<string, string>;
  /** Значок класса хода на клетке, куда пошла фигура. */
  badge: { square: string; value: ClassKey } | null;
};

export const NO_MARKS: BoardMarks = { arrows: [], highlights: {}, badge: null };

type BoardProps = {
  fen: string;
  orientation: Color;
  marks: BoardMarks;
  /** Режим «Повтори лучший ход»: можно двигать фигуры стороны на ходу. */
  interactive?: boolean;
  onMove?: (from: string, to: string) => boolean;
  onSquareClick?: (square: string) => void;
};

const darkSquare: CSSProperties = { backgroundColor: "var(--board-dark)" };
const lightSquare: CSSProperties = { backgroundColor: "var(--board-light)" };
const notation: CSSProperties = { fontSize: "13px", fontWeight: 800, fontFamily: "var(--font-main), sans-serif" };

export function Board({ fen, orientation, marks, interactive = false, onMove, onSquareClick }: BoardProps) {
  const { badge, highlights } = marks;

  // squareRenderer заменяет у react-chessboard div со squareStyles — подсветка здесь же.
  const squareRenderer = useCallback<SquareRenderer>(
    ({ square, children }) => (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          boxShadow: highlights[square] ? `inset 0 0 0 100px ${highlights[square]}` : undefined,
        }}
      >
        {children}
        {badge?.square === square && (
          <span className="pointer-events-none absolute -top-[14%] -right-[14%] z-10 drop-shadow-md">
            <ClassBadge value={badge.value} size={30} title={false} />
          </span>
        )}
      </div>
    ),
    [badge, highlights],
  );

  return (
    <Chessboard
      options={{
        id: "review-board",
        position: fen,
        boardOrientation: orientation,
        arrows: marks.arrows,
        squareRenderer,
        darkSquareStyle: darkSquare,
        lightSquareStyle: lightSquare,
        darkSquareNotationStyle: { ...notation, color: "var(--board-light)" },
        lightSquareNotationStyle: { ...notation, color: "var(--board-dark)" },
        boardStyle: { borderRadius: "3px", overflow: "visible" },
        allowDragging: interactive,
        // Клик по фигуре — выбор (ход кликами), а не перетаскивание на ту же клетку.
        dragActivationDistance: 4,
        allowDrawingArrows: false,
        animationDurationInMs: 160,
        arrowOptions: {
          colors: { default: "#7fb04a", shift: "#6f98c2", ctrl: "#f59a4c", alt: "#e8402e", meta: "#1fb5a0" },
          color: "#7fb04a",
          secondaryColor: "#6f98c2",
          tertiaryColor: "#f59a4c",
          arrowLengthReducerDenominator: 8,
          sameTargetArrowLengthReducerDenominator: 4,
          arrowWidthDenominator: 6,
          activeArrowWidthMultiplier: 0.9,
          opacity: 0.8,
          activeOpacity: 0.5,
          arrowStartOffset: 0,
        },
        canDragPiece: ({ piece }) =>
          interactive && piece.pieceType[0] === fen.split(" ")[1],
        onPieceDrop: ({ sourceSquare, targetSquare }) =>
          targetSquare !== null &&
          targetSquare !== sourceSquare &&
          onMove !== undefined &&
          onMove(sourceSquare, targetSquare),
        onSquareClick: onSquareClick ? ({ square }) => onSquareClick(square) : undefined,
      }}
    />
  );
}
