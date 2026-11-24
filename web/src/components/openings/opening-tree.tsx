"use client";

import { Fragment, useEffect, useMemo, useRef, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Figurine } from "../review/move-list";
import { moverColor, moveNo, pathTo, type NodeIndex, type OpeningNode } from "./types";
import type { OpeningNav } from "./use-opening-nav";

// Сколько полуходов показывать в ветке, где нет текущего узла, и как глубоко вкладывать ветки.
const SIDE_LINE_PLIES = 10;
const MAX_DEPTH = 3;
// Дальше текущего узла основная линия показывается не бесконечно.
const TAIL_PLIES = 30;

/**
 * Дерево ходов: основная линия и ветки, как в PGN с вариантами.
 *
 * Пропсы:
 *  - `index`, `currentId`, `onSelect(id)` — как у `OpeningBoard`;
 *  - `renderMeta(node)` — необязательная приписка после хода (например, число партий);
 *  - `className` — размеры и прокрутка (дерево скроллится внутри себя и держит текущий ход в
 *    зоне видимости).
 *
 * Линия идёт от корня по пути к текущему узлу, дальше — по основным (первым) детям. Остальные
 * дети каждого узла — ветки отступом под ходом. Ходы вне теории (`book` = false) подсвечены
 * янтарём, название дебюта (`name`) стоит после хода, в котором оно появляется.
 */
export function OpeningTree<N extends OpeningNode>({
  index,
  currentId,
  onSelect,
  renderMeta,
  className = "",
}: {
  index: NodeIndex<N>;
  currentId: number;
  onSelect: (id: number) => void;
  renderMeta?: (node: N) => ReactNode;
  className?: string;
}) {
  const { t } = useI18n();
  const container = useRef<HTMLDivElement>(null);
  const onPath = useMemo(() => new Set(pathTo(index, currentId).map((node) => node.id)), [index, currentId]);
  const root = useMemo(() => [...index.values()].find((node) => node.parent === null), [index]);

  // Текущий ход — в зоне видимости контейнера (страницу не прокручиваем).
  useEffect(() => {
    const box = container.current;
    const item = box?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!box || !item) return;
    const boxRect = box.getBoundingClientRect();
    const rect = item.getBoundingClientRect();
    if (rect.top < boxRect.top + 8) box.scrollTop += rect.top - boxRect.top - 8;
    else if (rect.bottom > boxRect.bottom - 8) box.scrollTop += rect.bottom - boxRect.bottom + 8;
  }, [currentId]);

  if (!root) return null;
  const ctx: Ctx<N> = { index, currentId, onSelect, renderMeta, onPath, labels: t.repertoire.shared };
  return (
    <div ref={container} className={`overflow-auto ${className}`}>
      <div className="px-1 py-1 text-[15px] font-bold">
        <button
          type="button"
          aria-current={currentId === root.id ? "true" : undefined}
          onClick={() => onSelect(root.id)}
          className={`mb-1 rounded-md px-2 py-1 text-sm ${
            currentId === root.id ? "bg-raised-hover text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
          }`}
        >
          {t.repertoire.shared.start}
        </button>
        <Line ctx={ctx} startIds={root.children} depth={0} />
      </div>
    </div>
  );
}

type Ctx<N extends OpeningNode> = {
  index: NodeIndex<N>;
  currentId: number;
  onSelect: (id: number) => void;
  renderMeta?: (node: N) => ReactNode;
  onPath: Set<number>;
  labels: { offBook: string };
};

/** Линия из узлов: от `first` по пути к текущему узлу, дальше по основным детям. */
function followLine<N extends OpeningNode>(ctx: Ctx<N>, first: number, limit: number): number[] {
  const ids: number[] = [];
  let id: number | undefined = first;
  let tail = 0;
  while (id !== undefined && ids.length < limit) {
    const node = ctx.index.get(id);
    if (!node) break;
    ids.push(id);
    const next: number | undefined =
      node.children.find((child) => ctx.onPath.has(child)) ?? node.children[0];
    // Пройдя текущий узел, считаем «хвост».
    if (ctx.currentId === id || tail > 0) tail += 1;
    if (tail > TAIL_PLIES) break;
    id = next;
  }
  return ids;
}

/**
 * Одна линия: ходы подряд, а после каждого хода — ветки (его соседи-альтернативы). Первый
 * ход линии берётся из `startIds`; остальные дети — альтернативы к нему.
 */
function Line<N extends OpeningNode>({ ctx, startIds, depth }: { ctx: Ctx<N>; startIds: number[]; depth: number }) {
  const first = startIds.find((id) => ctx.onPath.has(id)) ?? startIds[0];
  if (first === undefined) return null;
  const onPath = ctx.onPath.has(first);
  const ids = followLine(ctx, first, onPath ? 200 : SIDE_LINE_PLIES);

  // Ходы подряд — в одной строке; ветки разрывают её и идут блоком с отступом.
  const groups: ReactNode[] = [];
  let run: ReactNode[] = [];
  const flush = (key: string) => {
    if (run.length > 0) groups.push(<div key={key} className="flex flex-wrap items-center">{run}</div>);
    run = [];
  };
  ids.forEach((id, i) => {
    const node = ctx.index.get(id)!;
    const siblings = i === 0 ? startIds : (ctx.index.get(node.parent!)?.children ?? []);
    const alternatives = siblings.filter((sibling) => sibling !== id);
    const afterBreak = i === 0 || groups.length > 0 && run.length === 0;
    run.push(<Move key={id} ctx={ctx} node={node} showNumber={moverColor(node) === "white" || afterBreak} />);
    if (alternatives.length > 0) {
      flush(`run-${id}`);
      groups.push(
        <div key={`alts-${id}`} className="my-0.5 ml-2 border-l-2 border-line pl-2">
          {alternatives.map((alt) => (
            <Fragment key={alt}>
              {depth < MAX_DEPTH ? (
                <Line ctx={ctx} startIds={[alt]} depth={depth + 1} />
              ) : (
                <div className="flex flex-wrap items-center">
                  <Move ctx={ctx} node={ctx.index.get(alt)!} showNumber />
                </div>
              )}
            </Fragment>
          ))}
        </div>,
      );
    }
  });
  flush("run-end");
  return <>{groups}</>;
}

function Move<N extends OpeningNode>({ ctx, node, showNumber }: { ctx: Ctx<N>; node: N; showNumber: boolean }) {
  const current = ctx.currentId === node.id;
  const color = moverColor(node);
  return (
    <>
      {showNumber && (
        <span className="pr-0.5 pl-1.5 text-sm font-semibold text-muted">
          {moveNo(node.ply)}
          {color === "white" ? "." : "…"}
        </span>
      )}
      <button
        type="button"
        aria-current={current ? "true" : undefined}
        title={node.book ? undefined : ctx.labels.offBook}
        onClick={() => ctx.onSelect(node.id)}
        className={`my-0.5 inline-flex items-center gap-1 rounded-md px-1.5 py-1 whitespace-nowrap ${
          current ? "bg-raised-hover shadow-[0_2px_0_0_rgba(0,0,0,0.4)]" : "hover:bg-raised/60"
        } ${node.book ? "text-soft" : "text-[#e0a84a]"}`}
      >
        {node.san ? <Figurine san={node.san} color={color} /> : null}
        {!node.book && <span aria-hidden className="size-1.5 rounded-full bg-[#e0a84a]" />}
        {!node.book && <span className="sr-only">{ctx.labels.offBook}</span>}
        {ctx.renderMeta?.(node)}
      </button>
      {node.name && <span className="px-1 text-[12px] font-medium text-muted">{node.name}</span>}
    </>
  );
}

/** Кнопки «в начало / назад / вперёд» (под доской). */
export function OpeningControls({ nav, className = "" }: { nav: OpeningNav; className?: string }) {
  const { t } = useI18n();
  const l = t.repertoire.shared;
  const button = (label: string, disabled: boolean, onClick: () => void, path: string) => (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex min-h-11 flex-1 items-center justify-center rounded-lg bg-raised text-soft shadow-[0_3px_0_0_rgba(0,0,0,0.35)] hover:bg-raised-hover hover:text-ink active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-40 disabled:active:translate-y-0"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d={path} />
      </svg>
    </button>
  );
  return (
    <div className={`flex gap-2 ${className}`}>
      {button(l.toStart, !nav.canBack, nav.toStart, "M18 6l-6 6 6 6M7 6v12")}
      {button(l.back, !nav.canBack, nav.back, "M15 6l-6 6 6 6")}
      {button(l.forward, !nav.canForward, nav.forward, "M9 6l6 6-6 6")}
    </div>
  );
}
