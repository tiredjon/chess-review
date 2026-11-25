"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { pliesFromPgn, uciSquares } from "@/lib/chess";
import type { ModelGame } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { playMove, preloadSounds } from "@/lib/sounds";
import type { Color } from "@/lib/types";
import { Board, NO_MARKS } from "../review/board";
import { MoveList } from "../review/move-list";

const LAST_MOVE = "rgba(247, 214, 92, 0.6)";
const AUTOPLAY_MS = 900;

/**
 * Образцовая партия мастеров на доске: с позиции курса (`startPly`) вперёд и назад,
 * автопроигрывание, список ходов. ← → — ходы, пробел — пауза.
 */
export function GameViewer({
  game,
  orientation,
  startPly,
  onClose,
}: {
  game: ModelGame;
  orientation: Color;
  startPly: number;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.games;
  const { plies, startFen } = useMemo(() => pliesFromPgn(game.pgn), [game.pgn]);
  const anchor = Math.min(startPly, plies.length);
  const [cursor, setCursor] = useState(anchor);
  const [playing, setPlaying] = useState(false);

  useEffect(preloadSounds, []);

  const go = useCallback(
    (next: number) => {
      const target = Math.max(0, Math.min(plies.length, next));
      // Звук — только на шаг вперёд (как в разборе).
      if (target === cursor + 1) {
        const ply = plies[target - 1];
        playMove(ply.san, ply.color, orientation, target === plies.length);
      }
      setCursor(target);
    },
    [cursor, plies, orientation],
  );

  // Автопроигрывание: шаг за шагом до конца партии.
  useEffect(() => {
    if (!playing || cursor >= plies.length) return;
    const timer = setTimeout(() => {
      go(cursor + 1);
      if (cursor + 1 >= plies.length) setPlaying(false);
    }, AUTOPLAY_MS);
    return () => clearTimeout(timer);
  }, [playing, cursor, plies.length, go]);

  const ref = useRef({ cursor, go });
  useEffect(() => {
    ref.current = { cursor, go };
  }, [cursor, go]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target instanceof HTMLElement && ["INPUT", "TEXTAREA"].includes(event.target.tagName)) return;
      const { cursor: at, go: step } = ref.current;
      const actions: Record<string, () => void> = {
        ArrowLeft: () => step(at - 1),
        ArrowRight: () => step(at + 1),
        Home: () => step(0),
        End: () => step(Number.MAX_SAFE_INTEGER),
        Escape: onClose,
        " ": () => setPlaying((value) => !value),
      };
      const action = actions[event.key];
      if (!action) return;
      event.preventDefault();
      action();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fen = cursor === 0 ? startFen : plies[cursor - 1].fenAfter;
  const marks = useMemo(() => {
    const ply = cursor > 0 ? plies[cursor - 1] : null;
    if (!ply) return NO_MARKS;
    const { from, to } = uciSquares(ply.uci);
    return { ...NO_MARKS, key: `g${game.id}-${cursor}`, highlights: { [from]: LAST_MOVE, [to]: LAST_MOVE } };
  }, [cursor, plies, game.id]);

  const result = game.result === "1/2-1/2" ? "½–½" : game.result.replace("-", "–");
  const button = (label: string, disabled: boolean, onClick: () => void, icon: string) => (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex min-h-11 flex-1 items-center justify-center rounded-lg bg-raised text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-40"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d={icon} />
      </svg>
    </button>
  );

  const player = (color: Color) => {
    const name = color === "white" ? game.white : game.black;
    const rating = color === "white" ? game.white_rating : game.black_rating;
    return (
      <p className="flex min-w-0 items-center gap-2 text-sm font-bold">
        <span className={`size-3 shrink-0 rounded-sm ${color === "white" ? "bg-[#f2efe9]" : "bg-[#403d39] ring-1 ring-white/40"}`} />
        <span className="truncate">{name}</span>
        {rating && <span className="font-normal text-muted">({rating})</span>}
      </p>
    );
  };
  const top: Color = orientation === "white" ? "black" : "white";

  return (
    <section aria-label={l.board} className="cc-slide-in flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onClose}
          className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-raised px-3 text-sm font-bold text-soft hover:bg-raised-hover hover:text-ink"
        >
          <span aria-hidden>←</span> {l.close}
        </button>
        <span className="ml-auto rounded bg-sunken px-2 py-1 text-sm font-extrabold tabular-nums">{result}</span>
        {game.year && <span className="text-xs text-muted">{game.year}</span>}
      </div>
      {player(top)}
      <Board fen={fen} orientation={orientation} marks={marks} />
      {player(orientation)}
      <div className="flex gap-2">
        {button(l.toStart, cursor === 0, () => go(0), "M18 6l-6 6 6 6M7 6v12")}
        {button(l.back, cursor === 0, () => go(cursor - 1), "M15 6l-6 6 6 6")}
        <button
          type="button"
          onClick={() => setPlaying((value) => !value)}
          disabled={cursor >= plies.length && !playing}
          aria-pressed={playing}
          className="flex min-h-11 flex-[1.4] items-center justify-center gap-1.5 rounded-lg bg-green text-sm font-bold text-white shadow-[0_3px_0_0_var(--green-edge)] hover:bg-green-hover active:translate-y-[2px] active:shadow-none disabled:opacity-40"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="currentColor">
            <path d={playing ? "M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" : "M8 5v14l11-7z"} />
          </svg>
          {playing ? l.pause : l.autoplay}
        </button>
        {button(l.forward, cursor >= plies.length, () => go(cursor + 1), "M9 6l6 6-6 6")}
        {button(l.toEnd, cursor >= plies.length, () => go(plies.length), "M6 6l6 6-6 6M17 6v12")}
      </div>
      {anchor > 0 && cursor !== anchor && (
        <button type="button" onClick={() => go(anchor)} className="self-start text-xs font-bold text-green hover:underline">
          {l.fromPosition}
        </button>
      )}
      <div className="rounded-xl bg-panel">
        <MoveList plies={plies} cursor={cursor} onSelect={go} className="max-h-48" />
      </div>
    </section>
  );
}
