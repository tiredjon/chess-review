"use client";

import { useI18n } from "@/lib/i18n/use-i18n";
import type { RepertoireOpening } from "@/lib/repertoire-api";
import { moveNo } from "./types";
import { ResultBar, scorePercent } from "./result-bar";

/** Список дебютов пользователя за цвет; клик по строке выбирает дебют. */
export function OpeningList({
  openings,
  selectedName,
  onSelect,
}: {
  openings: RepertoireOpening[];
  selectedName: string | null;
  onSelect: (opening: RepertoireOpening) => void;
}) {
  const { t } = useI18n();
  const l = t.repertoire.list;
  return (
    <ul className="flex flex-col gap-1">
      {openings.map((opening) => {
        const active = opening.name === selectedName;
        return (
          <li key={opening.name}>
            <button
              type="button"
              aria-current={active ? "true" : undefined}
              onClick={() => onSelect(opening)}
              className={`w-full rounded-lg px-3 py-2 text-left ${
                active ? "bg-raised-hover ring-2 ring-green ring-inset" : "bg-raised/50 hover:bg-raised"
              }`}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 font-bold break-words text-ink">{opening.name}</span>
                {opening.eco && <span className="shrink-0 text-xs font-semibold text-muted">{opening.eco}</span>}
              </span>
              <span className="mt-0.5 flex flex-wrap items-baseline gap-x-3 text-[13px] text-soft">
                <span>{l.games(opening.games)}</span>
                <span>{l.score(scorePercent(opening.wins, opening.draws, opening.losses))}</span>
              </span>
              <ResultBar wins={opening.wins} draws={opening.draws} losses={opening.losses} className="mt-1.5" />
              <span className="mt-1 block text-xs text-muted">
                {l.exit(moveNo(opening.book_exit_ply + 1))}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
