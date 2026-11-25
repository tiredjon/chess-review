"use client";

import type { ReactNode } from "react";
import type { CourseNode, CourseTree, ModelGame, RenderedIdeas } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Figurine } from "../review/move-list";
import { moverColor, nameAt, pathTo, type NodeIndex } from "../openings/types";
import { IdeasCard } from "./ideas-card";
import { EvalChip, MastersBar, moveLabel } from "./shared";

/** Узлы поддерева `id` (вместе с ним). */
export function subtreeIds(index: NodeIndex<CourseNode>, id: number): Set<number> {
  const out = new Set<number>();
  const stack = [id];
  while (stack.length > 0) {
    const next = stack.pop()!;
    if (out.has(next)) continue;
    out.add(next);
    stack.push(...(index.get(next)?.children ?? []));
  }
  return out;
}

/** Партии мастеров через позицию: якорь партии — в поддереве узла. */
export const gamesThrough = (tree: CourseTree, index: NodeIndex<CourseNode>, id: number): ModelGame[] => {
  const ids = subtreeIds(index, id);
  return tree.model_games.filter((game) => ids.has(game.node_id));
};

/** Идеи для узла: его собственные, иначе ближайшего предка (структура держится до смены). */
export function ideasFor(index: NodeIndex<CourseNode>, ideasText: Record<string, RenderedIdeas>, id: number) {
  const path = pathTo(index, id).reverse();
  const own = path.findIndex((node) => ideasText[String(node.id)] !== undefined);
  if (own === -1) return null;
  const node = path[own];
  return { node, text: ideasText[String(node.id)], inherited: own > 0 };
}

/** Ближайший узел с идеями ниже по основной линии (первые дети). */
function nextIdeas(index: NodeIndex<CourseNode>, ideasText: Record<string, RenderedIdeas>, id: number): CourseNode | null {
  let node = index.get(id);
  while (node && node.children.length > 0) {
    node = index.get(node.children[0]);
    if (node && ideasText[String(node.id)]) return node;
  }
  return null;
}

/**
 * Панель узла курса: где мы (линия / дальше теории), оценка движка, статистика мастеров,
 * ходы дальше, идеи позиции, образцовые партии через позицию.
 */
export function NodePanel({
  tree,
  index,
  currentId,
  ideasText,
  onSelect,
  onPlay,
}: {
  tree: CourseTree;
  index: NodeIndex<CourseNode>;
  currentId: number;
  ideasText: Record<string, RenderedIdeas>;
  onSelect: (id: number) => void;
  onPlay: (game: ModelGame) => void;
}) {
  const { t } = useI18n();
  const l = t.courses.node;
  const node = index.get(currentId);
  const lineEnd = index.get(tree.line_end);
  if (!node) return null;

  const name = nameAt(index, currentId);
  const lineIds = new Set(lineEnd ? pathTo(index, lineEnd.id).map((n) => n.id) : []);
  const place =
    node.ply === 0
      ? l.start
      : node.id === tree.line_end
        ? l.lineEnd
        : lineIds.has(node.id)
          ? l.inLine
          : l.beyond;
  const children = node.children.flatMap((id) => index.get(id) ?? []);
  const learnerMoves = children.filter((child) => child.mover === "learner");
  const opponentMoves = children.filter((child) => child.mover === "opponent").sort((a, b) => b.weight - a.weight);
  const ideas = ideasFor(index, ideasText, currentId);
  const ahead = ideas && !ideas.inherited ? null : nextIdeas(index, ideasText, currentId);
  const games = gamesThrough(tree, index, currentId);

  return (
    <div className="flex flex-col gap-3">
      <section aria-label={l.masters} className="rounded-xl bg-panel p-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[17px] leading-snug font-bold">
              {node.san ? (
                <span className="mr-1.5 whitespace-nowrap">
                  {moveLabel(node).replace(node.san, "")}
                  <Figurine san={node.san} color={moverColor(node)} />
                </span>
              ) : null}
              <span className={node.san ? "font-semibold text-soft" : ""}>{name ?? l.start}</span>
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[13px] text-muted">
              <span>{place}</span>
              {node.key_moment && <Tag tone="idea">{l.key[node.key_moment] ?? l.key.other}</Tag>}
              {!node.book && node.ply > 0 && <Tag tone="amber">{l.offBook}</Tag>}
            </div>
          </div>
          {node.eval && (
            <div className="flex shrink-0 flex-col items-end gap-0.5" title={l.eval}>
              <EvalChip value={node.eval} />
              <span className="text-[11px] text-muted">{l.evalDepth(node.eval.depth)}</span>
            </div>
          )}
        </div>

        {node.stats && node.stats.games > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
              <span className="font-semibold">{l.mastersGames(node.stats.games)}</span>
              {node.stats.average_rating && <span className="text-xs text-muted">{l.avgRating(node.stats.average_rating)}</span>}
            </div>
            <MastersBar stats={node.stats} showLabels />
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3">
          {learnerMoves.length > 0 && (
            <MoveGroup title={l.youPlay}>
              {learnerMoves.map((child) => (
                <MoveRow key={child.id} node={child} onSelect={onSelect} parentGames={node.stats?.games ?? 0}>
                  <span className="rounded bg-green/20 px-1.5 py-0.5 text-[11px] font-bold text-green">{l.courseMove}</span>
                </MoveRow>
              ))}
            </MoveGroup>
          )}
          {opponentMoves.length > 0 && (
            <MoveGroup title={l.theyPlay}>
              {opponentMoves.map((child) => (
                <MoveRow key={child.id} node={child} onSelect={onSelect} parentGames={node.stats?.games ?? 0}>
                  <span className="text-[13px] font-semibold text-soft">{l.share(Math.round(child.weight * 100))}</span>
                </MoveRow>
              ))}
            </MoveGroup>
          )}
          {children.length === 0 && <p className="text-sm text-muted">{l.leaf}</p>}
        </div>
      </section>

      <section aria-label={t.courses.ideas.title} className="rounded-xl bg-panel p-4">
        <h3 className="mb-3 flex items-center gap-2 text-base font-extrabold">
          <Bulb />
          {t.courses.ideas.title}
        </h3>
        {ideas ? (
          <>
            {ideas.inherited && (
              <p className="-mt-1.5 mb-3 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                {t.courses.ideas.fromNode(moveLabel(ideas.node))}
                <button type="button" onClick={() => onSelect(ideas.node.id)} className="font-bold text-green hover:underline">
                  {t.courses.ideas.jump}
                </button>
              </p>
            )}
            <IdeasCard text={ideas.text} raw={ideas.node.ideas} learner={tree.color} />
          </>
        ) : (
          <p className="text-sm text-muted">{t.courses.ideas.none}</p>
        )}
        {ahead && (
          <button
            type="button"
            onClick={() => onSelect(ahead.id)}
            className="mt-3 inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-raised px-3 text-sm font-bold text-soft hover:bg-raised-hover hover:text-ink"
          >
            {t.courses.ideas.nextKey(moveLabel(ahead))} <span aria-hidden>→</span>
          </button>
        )}
      </section>

      <section aria-label={t.courses.games.title} className="rounded-xl bg-panel p-4">
        <h3 className="text-base font-extrabold">{t.courses.games.title}</h3>
        <p className="mt-0.5 mb-3 text-xs text-muted">
          {games.length > 0 ? t.courses.games.through(games.length) : t.courses.games.none}
        </p>
        <ul className="flex flex-col gap-1.5">
          {games.map((game) => (
            <li key={game.id}>
              <GameRow game={game} onPlay={onPlay} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function MoveGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h4 className="mb-1.5 text-xs font-bold tracking-wide text-muted uppercase">{title}</h4>
      <ul className="flex flex-col gap-1">{children}</ul>
    </div>
  );
}

function MoveRow({
  node,
  parentGames,
  onSelect,
  children,
}: {
  node: CourseNode;
  parentGames: number;
  onSelect: (id: number) => void;
  children: ReactNode;
}) {
  const games = node.stats?.games ?? 0;
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(node.id)}
        className="grid w-full grid-cols-[4.75rem_1fr_auto] items-center gap-x-3 rounded-lg bg-raised/50 px-2.5 py-2 text-left hover:bg-raised"
      >
        <span className={`text-[15px] font-bold whitespace-nowrap ${node.book ? "text-ink" : "text-[#e0a84a]"}`}>
          {node.san && <Figurine san={node.san} color={moverColor(node)} />}
        </span>
        <span className="min-w-0">{node.stats && <MastersBar stats={node.stats} />}</span>
        <span className="flex items-center gap-2 text-right whitespace-nowrap">
          {children}
          {games > 0 && parentGames > 0 && <span className="text-xs text-muted tabular-nums">{games.toLocaleString()}</span>}
        </span>
      </button>
    </li>
  );
}

function GameRow({ game, onPlay }: { game: ModelGame; onPlay: (game: ModelGame) => void }) {
  const { t } = useI18n();
  const result = game.result === "1/2-1/2" ? "½–½" : game.result.replace("-", "–");
  return (
    <button
      type="button"
      onClick={() => onPlay(game)}
      className="flex w-full items-center gap-3 rounded-lg bg-raised/50 px-3 py-2 text-left hover:bg-raised"
    >
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-bold">
          <span className="mr-1 inline-block size-2.5 rounded-full bg-[#f2efe9] align-middle" />
          {game.white}
          {game.white_rating && <span className="ml-1 font-normal text-muted">({game.white_rating})</span>}
        </span>
        <span className="block truncate text-sm font-bold">
          <span className="mr-1 inline-block size-2.5 rounded-full bg-[#403d39] align-middle ring-1 ring-white/40" />
          {game.black}
          {game.black_rating && <span className="ml-1 font-normal text-muted">({game.black_rating})</span>}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-0.5">
        <span className="rounded bg-sunken px-1.5 py-0.5 text-xs font-extrabold tabular-nums">{result}</span>
        {game.year && <span className="text-[11px] text-muted">{game.year}</span>}
      </span>
      <span className="shrink-0 rounded-md bg-green px-2.5 py-1.5 text-xs font-bold text-white shadow-[0_2px_0_0_var(--green-edge)]">
        {t.courses.games.play}
      </span>
    </button>
  );
}

function Tag({ tone, children }: { tone: "idea" | "amber"; children: ReactNode }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
        tone === "idea" ? "bg-[#f7c631]/15 text-[#f7c631]" : "bg-[#e0a84a]/15 text-[#e0a84a]"
      }`}
    >
      {children}
    </span>
  );
}

export function Bulb({ className = "size-[18px]" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={`shrink-0 ${className}`} fill="#f7c631">
      <path d="M12 2a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.3A7 7 0 0 0 12 2zm-2.5 18h5a.5.5 0 0 1 .5.5 1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 9 20.5a.5.5 0 0 1 .5-.5z" />
    </svg>
  );
}
