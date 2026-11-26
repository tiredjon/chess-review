"use client";

// Миниатюра позиции для списков тренажёра: без react-chessboard (их на странице два десятка) —
// сетка 8×8 поверх доски темы, фигуры — картинками темы.
import { useMemo } from "react";
import { boardUrl, useTheme, type PieceCode } from "@/lib/theme";
import type { Color } from "@/lib/types";
import { PieceImage } from "../board-theme";

function cells(fen: string, orientation: Color): (PieceCode | null)[] {
  const rows = fen
    .split(" ")[0]
    .split("/")
    .map((row) =>
      row.split("").flatMap((char): (PieceCode | null)[] =>
        /\d/.test(char)
          ? Array<null>(Number(char)).fill(null)
          : [`${char === char.toUpperCase() ? "w" : "b"}${char.toUpperCase()}` as PieceCode],
      ),
    );
  const flat = rows.flat();
  return orientation === "white" ? flat : flat.reverse();
}

export function PositionThumb({ fen, orientation, label }: { fen: string; orientation: Color; label?: string }) {
  const theme = useTheme();
  const squares = useMemo(() => cells(fen, orientation), [fen, orientation]);
  const image = theme.ready && theme.chesscomBoard;
  return (
    <div
      role="img"
      aria-label={label}
      className="grid aspect-square w-full grid-cols-8 overflow-hidden rounded-[3px] bg-[#8a6a4a]"
      style={image ? { backgroundImage: `url(${boardUrl})`, backgroundSize: "100% 100%" } : undefined}
    >
      {squares.map((piece, index) => {
        const dark = (Math.floor(index / 8) + index) % 2 === 1;
        const tint = image ? undefined : dark ? "rgba(96, 54, 22, 0.5)" : "rgba(250, 224, 180, 0.55)";
        return (
          <span key={index} className="relative aspect-square" style={{ backgroundColor: tint }}>
            {piece && <PieceImage code={piece} />}
          </span>
        );
      })}
    </div>
  );
}
