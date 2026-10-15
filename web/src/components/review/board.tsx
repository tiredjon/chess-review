"use client";

import { useCallback, useEffect, useState } from "react";
import { Chessboard, type Arrow, type SquareRenderer } from "react-chessboard";
import type { ClassKey } from "@/lib/classes";
import type { Color } from "@/lib/types";
import { useBoardTheme } from "../board-theme";
import { ClassBadge } from "./class-badge";

export type BoardMarks = {
  /** Меняется вместе с позицией: по нему заново проигрываются анимации подсветки и значка. */
  key: string;
  arrows: Arrow[];
  /** Подсветка клеток: клетка → цвет (полупрозрачный). */
  highlights: Record<string, string>;
  /** Значок класса хода на клетке, куда пошла фигура. */
  badge: { square: string; value: ClassKey } | null;
};

export const NO_MARKS: BoardMarks = { key: "none", arrows: [], highlights: {}, badge: null };

type BoardProps = {
  fen: string;
  orientation: Color;
  marks: BoardMarks;
  /** Режим «Найдите лучший ход»: можно двигать фигуры стороны на ходу. */
  interactive?: boolean;
  onMove?: (from: string, to: string) => boolean;
  onSquareClick?: (square: string) => void;
};

// Фигура едет ~200 мс; подсветка, стрелки и значок появляются, когда она доехала
// (задержки — в globals.css, классы cc-*).
const MOVE_MS = 200;

export function Board({ fen, orientation, marks, interactive = false, onMove, onSquareClick }: BoardProps) {
  const theme = useBoardTheme();
  const { badge, highlights, key } = marks;

  // Стрелки — после того как фигура доехала (новые стрелки затем проявляются по CSS).
  const [arrowsKey, setArrowsKey] = useState<string | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setArrowsKey(key), MOVE_MS);
    return () => clearTimeout(timer);
  }, [key]);

  // squareRenderer заменяет у react-chessboard div со squareStyles — подсветка здесь же.
  const squareRenderer = useCallback<SquareRenderer>(
    ({ square, children }) => (
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        {highlights[square] && (
          <span
            key={`${key}-hl`}
            aria-hidden
            className="cc-highlight pointer-events-none absolute inset-0"
            style={{ background: highlights[square] }}
          />
        )}
        <div style={{ position: "relative", width: "100%", height: "100%" }}>{children}</div>
        {badge?.square === square && (
          <span
            key={`${key}-badge`}
            className={`cc-badge pointer-events-none absolute -top-[16%] -right-[16%] z-30 w-[46%] drop-shadow-[0_2px_2px_rgba(0,0,0,0.45)] ${
              badge.value === "brilliant" || badge.value === "great" ? "cc-badge-shine" : ""
            }`}
          >
            <ClassBadge value={badge.value} size="100%" title={false} />
          </span>
        )}
      </div>
    ),
    [badge, highlights, key],
  );

  return (
    <div className="cc-board">
      <Chessboard
        options={{
          ...theme,
          id: "review-board",
          position: fen,
          boardOrientation: orientation,
          arrows: arrowsKey === key ? marks.arrows : [],
          squareRenderer,
          allowDragging: interactive,
          // Клик по фигуре — выбор (ход кликами), а не перетаскивание на ту же клетку.
          dragActivationDistance: 4,
          allowDrawingArrows: false,
          animationDurationInMs: MOVE_MS,
          arrowOptions: {
            colors: { default: "#96bc4b", shift: "#6f98c2", ctrl: "#f59a4c", alt: "#e8402e", meta: "#1fb5a0" },
            color: "#96bc4b",
            secondaryColor: "#6f98c2",
            tertiaryColor: "#f59a4c",
            arrowLengthReducerDenominator: 8,
            sameTargetArrowLengthReducerDenominator: 4,
            arrowWidthDenominator: 5,
            activeArrowWidthMultiplier: 0.9,
            opacity: 0.85,
            activeOpacity: 0.5,
            arrowStartOffset: 0,
          },
          canDragPiece: ({ piece }) => interactive && piece.pieceType[0] === fen.split(" ")[1],
          onPieceDrop: ({ sourceSquare, targetSquare }) =>
            targetSquare !== null && targetSquare !== sourceSquare && onMove !== undefined && onMove(sourceSquare, targetSquare),
          onSquareClick: onSquareClick ? ({ square }) => onSquareClick(square) : undefined,
        }}
      />
    </div>
  );
}
