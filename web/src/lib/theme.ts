"use client";

// Оформление доски. Если в web/public/chesscom/ лежат фигуры и доска Chess.com
// (скачиваются вручную, в git не идут — см. SPEC «Заметки по окружению»), берутся они;
// иначе — запасной набор «Celtic» (public/pieces, MIT) и доска CSS-цветами.
import { useSyncExternalStore } from "react";

export const PIECE_CODES = ["wK", "wQ", "wR", "wB", "wN", "wP", "bK", "bQ", "bR", "bB", "bN", "bP"] as const;
export type PieceCode = (typeof PIECE_CODES)[number];

const CHESSCOM = {
  piece: (code: PieceCode) => `/chesscom/pieces/${code.toLowerCase()}.png`,
  board: "/chesscom/board.png",
};
const FALLBACK_PIECE = (code: PieceCode) => `/pieces/${code}.svg`;

/** `ready` — пробы файлов Chess.com завершены; до этого фигуры не рисуются, чтобы не мигать. */
export type Theme = { ready: boolean; chesscomPieces: boolean; chesscomBoard: boolean };

const SERVER_THEME: Theme = { ready: false, chesscomPieces: false, chesscomBoard: false };
let theme: Theme = SERVER_THEME;
let probed = false;
const listeners = new Set<() => void>();

function probe(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(true);
    image.onerror = () => resolve(false);
    image.src = url;
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!probed) {
    probed = true;
    // Один запрос на файл за сессию; остальные фигуры проверяются по белому королю.
    void Promise.all([probe(CHESSCOM.piece("wK")), probe(CHESSCOM.board)]).then(([pieces, board]) => {
      theme = { ready: true, chesscomPieces: pieces, chesscomBoard: board };
      listeners.forEach((notify) => notify());
    });
  }
  return () => listeners.delete(listener);
}

export function useTheme(): Theme {
  return useSyncExternalStore(
    subscribe,
    () => theme,
    () => SERVER_THEME,
  );
}

export const pieceUrl = (code: PieceCode, current: Theme): string | null =>
  !current.ready ? null : current.chesscomPieces ? CHESSCOM.piece(code) : FALLBACK_PIECE(code);

export const boardUrl = CHESSCOM.board;
