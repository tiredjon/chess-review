"use client";

import { useEffect, useRef } from "react";
import { defaultPieces } from "react-chessboard";
import { CLASS_META, displayClass, NOTABLE } from "@/lib/classes";
import type { Ply } from "@/lib/chess";
import type { Color } from "@/lib/types";
import { ClassBadge } from "./class-badge";

type Row = { fullmove: number; white: Ply | null; black: Ply | null };

function rows(plies: Ply[]): Row[] {
  const result: Row[] = [];
  for (const ply of plies) {
    const last = result.at(-1);
    if (ply.color === "black" && last && last.fullmove === ply.fullmove && last.black === null) {
      last.black = ply;
    } else {
      result.push({
        fullmove: ply.fullmove,
        white: ply.color === "white" ? ply : null,
        black: ply.color === "black" ? ply : null,
      });
    }
  }
  return result;
}

const PIECE_STYLE = {
  white: { width: "1.3em", height: "1.3em" },
  // Чёрная фигура на тёмной панели — со светлым контуром.
  black: {
    width: "1.3em",
    height: "1.3em",
    filter: "drop-shadow(0 0 0.7px #e8e3db) drop-shadow(0 0 0.7px #e8e3db)",
  },
};

/** Фигурная нотация: буква фигуры заменяется её изображением (те же фигуры, что на доске). */
export function Figurine({ san, color }: { san: string; color: Color }) {
  const render = "KQRBN".includes(san[0]) ? defaultPieces[`${color === "white" ? "w" : "b"}${san[0]}`] : undefined;
  if (!render) return <>{san}</>;
  return (
    <>
      <span aria-hidden className="mr-px inline-block align-[-0.3em]">
        {render({ svgStyle: PIECE_STYLE[color] })}
      </span>
      <span className="sr-only">{san[0]}</span>
      {san.slice(1)}
    </>
  );
}

/** Список ходов; `cursor` — число сыгранных полуходов (-1 — не выделять). */
export function MoveList({
  plies,
  cursor,
  onSelect,
  className = "",
}: {
  plies: Ply[];
  cursor: number;
  onSelect: (index: number) => void;
  className?: string;
}) {
  const container = useRef<HTMLDivElement>(null);

  // Держать текущий ход в зоне видимости, не прокручивая страницу; высота списка меняется
  // вместе с панелью над ним, поэтому и по ResizeObserver.
  useEffect(() => {
    const box = container.current;
    if (!box) return;
    const reveal = () => {
      const item = box.querySelector<HTMLElement>('[aria-current="true"]');
      if (!item) {
        if (cursor === 0) box.scrollTop = 0;
        return;
      }
      // Контейнер — `relative`, offsetTop кнопки отсчитывается от него.
      const top = item.offsetTop;
      if (top < box.scrollTop + 8) box.scrollTop = top - 8;
      else if (top + item.offsetHeight > box.scrollTop + box.clientHeight - 8)
        box.scrollTop = top + item.offsetHeight - box.clientHeight + 8;
    };
    reveal();
    const observer = new ResizeObserver(reveal);
    observer.observe(box);
    return () => observer.disconnect();
  }, [cursor]);

  return (
    <div ref={container} className={`relative overflow-y-auto ${className}`}>
      <ol className="py-1 text-[15px] font-bold">
        {rows(plies).map((row) => (
          <li
            key={`${row.fullmove}-${row.white?.index ?? row.black?.index}`}
            className="grid grid-cols-[2.75rem_1fr_1fr] items-center"
          >
            <span className="pl-3 text-muted">{row.fullmove}.</span>
            <MoveCell ply={row.white} cursor={cursor} onSelect={onSelect} />
            <MoveCell ply={row.black} cursor={cursor} onSelect={onSelect} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function MoveCell({ ply, cursor, onSelect }: { ply: Ply | null; cursor: number; onSelect: (index: number) => void }) {
  if (!ply) return <span className="px-2 py-1.5 text-muted">…</span>;
  const current = cursor === ply.index + 1;
  const value = ply.move ? displayClass(ply.move) : null;
  const notable = value !== null && NOTABLE.includes(value);
  return (
    <button
      type="button"
      aria-current={current ? "true" : undefined}
      onClick={() => onSelect(ply.index + 1)}
      className={`my-0.5 mr-1 flex items-center gap-1.5 rounded-md px-1.5 py-1 text-left ${
        current ? "bg-raised-hover shadow-[0_2px_0_0_rgba(0,0,0,0.4)]" : "hover:bg-raised/60"
      }`}
      style={notable ? { color: CLASS_META[value].color } : { color: "var(--soft)" }}
    >
      <span className="flex w-[22px] justify-center">{notable && <ClassBadge value={value} size={22} />}</span>
      <span className="whitespace-nowrap">
        <Figurine san={ply.san} color={ply.color} />
      </span>
    </button>
  );
}
