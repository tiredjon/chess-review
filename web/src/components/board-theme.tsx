"use client";

import { useMemo, type CSSProperties } from "react";
import type { ChessboardOptions, PieceRenderObject } from "react-chessboard";
import { boardUrl, PIECE_CODES, pieceUrl, useTheme, type PieceCode } from "@/lib/theme";

// Запасная доска без картинки Chess.com: процедурное «дерево» (шум SVG) под полупрозрачными
// клетками — светлый клён и тёмный орех.
const GRAIN = `url("data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" preserveAspectRatio="none">' +
    '<filter id="g" x="0" y="0" width="100%" height="100%">' +
    '<feTurbulence type="fractalNoise" baseFrequency="0.006 0.09" numOctaves="4" seed="11"/>' +
    '<feColorMatrix values="0 0 0 0.30 0.66 0 0 0 0.24 0.47 0 0 0 0.18 0.29 0 0 0 0 1"/>' +
    '</filter><rect width="100%" height="100%" filter="url(#g)"/></svg>',
)}")`;

const NOTATION: CSSProperties = { fontSize: "clamp(9px, 1.6vw, 15px)", fontWeight: 800 };
// Координаты — цветом «противоположной» клетки, как на деревянной доске Chess.com.
const LIGHT_SQUARE_TEXT = "#9a7349";
const DARK_SQUARE_TEXT = "#ead6b8";

const imageStyle: CSSProperties = { width: "100%", height: "100%", display: "block", userSelect: "none" };

/** Картинка фигуры текущей темы. */
export function PieceImage({ code, style }: { code: PieceCode; style?: CSSProperties }) {
  const src = pieceUrl(code, useTheme());
  if (!src) return <span style={imageStyle} />;
  // eslint-disable-next-line @next/next/no-img-element -- статичные картинки фигур, оптимизация не нужна
  return <img src={src} alt="" draggable={false} style={{ ...imageStyle, ...style }} />;
}

/** Оформление для `<Chessboard options>`: фигуры, доска, координаты. */
export function useBoardTheme(): Pick<
  ChessboardOptions,
  | "pieces"
  | "boardStyle"
  | "lightSquareStyle"
  | "darkSquareStyle"
  | "lightSquareNotationStyle"
  | "darkSquareNotationStyle"
> {
  const theme = useTheme();
  return useMemo(() => {
    const pieces: PieceRenderObject = Object.fromEntries(
      PIECE_CODES.map((code) => {
        const src = pieceUrl(code, theme);
        return [
          code,
          // eslint-disable-next-line @next/next/no-img-element -- см. PieceImage
          () => (src ? <img src={src} alt="" draggable={false} style={imageStyle} /> : <span style={imageStyle} />),
        ];
      }),
    );
    const board: CSSProperties = !theme.ready
      ? { backgroundColor: "#8a6a4a" }
      : theme.chesscomBoard
        ? { backgroundImage: `url(${boardUrl})`, backgroundSize: "100% 100%" }
        : { backgroundImage: GRAIN, backgroundSize: "100% 100%" };
    const overlay = theme.ready && !theme.chesscomBoard;
    return {
      pieces,
      boardStyle: { ...board, borderRadius: "4px", overflow: "visible" },
      lightSquareStyle: { backgroundColor: overlay || !theme.ready ? "rgba(250, 224, 180, 0.55)" : "transparent" },
      darkSquareStyle: { backgroundColor: overlay || !theme.ready ? "rgba(96, 54, 22, 0.5)" : "transparent" },
      lightSquareNotationStyle: { ...NOTATION, color: LIGHT_SQUARE_TEXT },
      darkSquareNotationStyle: { ...NOTATION, color: DARK_SQUARE_TEXT },
    };
  }, [theme]);
}
