"use client";

import { useState } from "react";
import type { BookPosition } from "@/lib/coach-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { GameViewer } from "../courses/game-viewer";
import { PositionThumb } from "../endgames/position-thumb";

/** «21. Qxb5» / «21… Qxb5» — номер хода по полуходу после хода. */
export const moveLabel = (ply: number, san: string) => `${Math.ceil(ply / 2)}${ply % 2 === 1 ? "." : "…"} ${san}`;

const year = (position: BookPosition) => (position.game.year ? `, ${position.game.year}` : "");

/**
 * Позиции статьи по книге: миниатюра после хода, партия и комментарий автора (на английском,
 * как в книге). Клик — партия целиком на доске с этого хода (`GameViewer`, с комментариями).
 */
export function BookPositions({ positions }: { positions: BookPosition[] }) {
  const { t } = useI18n();
  const c = t.coach.lesson;
  const [open, setOpen] = useState<BookPosition | null>(null);

  return (
    <div className="flex flex-col gap-4">
      {open && (
        <div className="mx-auto w-full max-w-[560px]">
          <GameViewer
            key={`${open.game.id}-${open.ply}`}
            game={open.game}
            orientation="white"
            startPly={open.ply}
            onClose={() => setOpen(null)}
          />
        </div>
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {positions.map((position) => {
          const title = `${position.game.white} — ${position.game.black}${year(position)}`;
          const move = moveLabel(position.ply, position.san);
          const active = open?.game.id === position.game.id && open.ply === position.ply;
          return (
            <li key={`${position.game.id}-${position.ply}`} className="min-w-0">
              <button
                type="button"
                onClick={() => setOpen(position)}
                aria-pressed={active}
                aria-label={c.openGame(title, move)}
                className={`flex w-full min-w-0 gap-3 rounded-lg p-2.5 text-left hover:bg-raised ${active ? "bg-raised ring-2 ring-green/60" : "bg-raised/60"}`}
              >
                <span className="w-28 shrink-0 sm:w-32">
                  <PositionThumb fen={position.fen} orientation="white" label={`${title}, ${move}`} />
                </span>
                <span className="flex min-w-0 flex-col gap-1 text-sm">
                  <span className="font-extrabold break-words">{title}</span>
                  <span className="font-bold text-green">{move}</span>
                  <span lang="en" className="line-clamp-5 leading-snug text-soft">
                    {position.comment}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
