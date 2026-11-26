"use client";

// ЗАГЛУШКА фундамента сессии 14 — настоящую партию делает подсессия 14.2.
// Экспорт `BotGame` и его props (`./types`) — контракт для 14.3.
import type { BotGameProps } from "./types";

export function BotGame({ elo, color }: BotGameProps) {
  return (
    <p className="rounded-xl bg-panel p-6 text-muted">
      Партия с ботом {elo} за {color === "white" ? "белых" : "чёрных"} — скоро.
    </p>
  );
}
