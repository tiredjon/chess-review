"use client";

import { useEffect, useRef } from "react";
import { displayClass } from "@/lib/classes";
import type { Ply } from "@/lib/chess";
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

/** Бланк записи: ход белых и чёрных в строке; `cursor` — число сыгранных полуходов. */
export function MoveList({
  plies,
  cursor,
  onSelect,
}: {
  plies: Ply[];
  cursor: number;
  onSelect: (index: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);

  // Держать текущий ход в зоне видимости, не прокручивая страницу.
  // Высота списка меняется, когда панель хода над ним подгружает объяснение, — поэтому
  // и по ResizeObserver.
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
    <div
      ref={container}
      className="relative max-h-[22rem] overflow-y-auto rounded-lg border border-line bg-surface lg:max-h-none lg:min-h-32 lg:flex-1"
    >
      <ol className="text-[15px]">
        {rows(plies).map((row) => (
          <li
            key={`${row.fullmove}-${row.white?.index ?? row.black?.index}`}
            className="grid grid-cols-[3rem_1fr_1fr] items-center odd:bg-paper/60"
          >
            <span className="pl-3 text-sm text-muted">{row.fullmove}.</span>
            <MoveCell ply={row.white} cursor={cursor} onSelect={onSelect} />
            <MoveCell ply={row.black} cursor={cursor} onSelect={onSelect} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function MoveCell({
  ply,
  cursor,
  onSelect,
}: {
  ply: Ply | null;
  cursor: number;
  onSelect: (index: number) => void;
}) {
  if (!ply) return <span className="px-2 py-1.5 text-muted">…</span>;
  const current = cursor === ply.index + 1;
  const value = ply.move ? displayClass(ply.move) : null;
  // Значок — только там, где он что-то сообщает.
  const showBadge = value !== null && !["good", "excellent", "forced"].includes(value);
  return (
    <button
      type="button"
      aria-current={current ? "true" : undefined}
      onClick={() => onSelect(ply.index + 1)}
      className={`m-0.5 flex items-center gap-1.5 rounded-md px-2 py-1 text-left ${
        current ? "bg-accent font-semibold text-accent-ink" : "hover:bg-sunken"
      }`}
    >
      <span className="w-[18px]">{showBadge && <ClassBadge value={value} size={16} />}</span>
      {ply.san}
    </button>
  );
}
