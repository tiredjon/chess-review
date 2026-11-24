"use client";

import { Figurine } from "../review/move-list";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { RepertoireNode } from "@/lib/repertoire-api";
import { ResultBar, scorePercent } from "./result-bar";
import { moverColor, moveNo, nameAt, pathTo, type NodeIndex } from "./types";

/** Статистика узла репертуара: партии, результат, ходы ученика и ответы соперников, теория. */
export function NodeStats({
  index,
  currentId,
  onSelect,
}: {
  index: NodeIndex<RepertoireNode>;
  currentId: number;
  onSelect: (id: number) => void;
}) {
  const { t } = useI18n();
  const l = t.repertoire.node;
  const node = index.get(currentId);
  if (!node) return null;

  const path = pathTo(index, currentId);
  const name = nameAt(index, currentId);
  const firstOff = path.find((n) => !n.book);
  const children = node.children
    .map((id) => index.get(id))
    .filter((child): child is RepertoireNode => child !== undefined)
    .sort((a, b) => b.games - a.games);
  const childrenMover = children[0]?.mover;

  // Где кончается теория: первый ход вне книги на пути, иначе — ниже по самой частой линии.
  let exitPly: number | null = firstOff ? firstOff.ply : null;
  if (exitPly === null) {
    let cursor: RepertoireNode | undefined = node;
    while (cursor) {
      const next: RepertoireNode | undefined = cursor.children
        .map((id) => index.get(id))
        .filter((c): c is RepertoireNode => c !== undefined)
        .sort((a, b) => b.games - a.games)[0];
      if (next && !next.book) {
        exitPly = next.ply;
        break;
      }
      cursor = next;
    }
  }

  return (
    <section className="rounded-xl bg-panel p-4" aria-label={l.title}>
      <div className="min-h-[2.75rem]">
        <p className="text-[17px] leading-snug font-bold">{name ?? l.start}</p>
        <p className="mt-0.5 text-[13px] text-muted">
          {node.ply === 0 ? l.start : node.book ? l.inTheory : l.offTheory(moveNo(node.ply))}
          {exitPly !== null && node.book && ` · ${l.theoryEnds(moveNo(exitPly))}`}
        </p>
      </div>

      {node.games > 0 && (
        <div className="mt-3">
          <div className="flex flex-wrap items-baseline gap-x-3 text-sm font-semibold">
            <span>{l.games(node.games)}</span>
            <span className="text-soft">{l.score(scorePercent(node.wins, node.draws, node.losses))}</span>
          </div>
          <ResultBar wins={node.wins} draws={node.draws} losses={node.losses} className="mt-1.5 h-2" />
          <p className="mt-1 text-xs text-muted">{l.wdl(node.wins, node.draws, node.losses)}</p>
        </div>
      )}

      <div className="mt-4">
        {children.length === 0 ? (
          <p className="text-sm text-muted">{l.noGames}</p>
        ) : (
          <>
            <h3 className="mb-1.5 text-xs font-bold tracking-wide text-muted uppercase">
              {childrenMover === "learner" ? l.youPlay : l.theyPlay}
            </h3>
            <ul className="flex flex-col gap-1">
              {children.map((child) => (
                <li key={child.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(child.id)}
                    className="grid w-full grid-cols-[4.5rem_1fr_auto] items-center gap-x-3 rounded-lg bg-raised/50 px-2.5 py-1.5 text-left hover:bg-raised"
                  >
                    <span className={`text-[15px] font-bold ${child.book ? "text-ink" : "text-[#e0a84a]"}`}>
                      {child.san && <Figurine san={child.san} color={moverColor(child)} />}
                    </span>
                    <span className="min-w-0">
                      <ResultBar wins={child.wins} draws={child.draws} losses={child.losses} />
                    </span>
                    <span className="text-right text-[13px] whitespace-nowrap text-soft">
                      {node.games > 0 ? l.share(Math.round((child.games / node.games) * 100)) : ""}
                      <span className="ml-2 text-muted">{child.games}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
