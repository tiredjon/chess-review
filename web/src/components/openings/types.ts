// Общие типы и хелперы дерева дебютов (сессия 13). Дерево репертуара (13.3) и дерево курса
// (13.4) повторяют одни и те же поля узла — компоненты в этой папке не знают, чьё оно: они
// принимают `OpeningNode` (или его расширение со статистикой) и индекс узлов по id.
import type { Color } from "@/lib/types";

/** Чей ход привёл в позицию: ученика (`learner`) или соперника (`opponent`). */
export type Mover = "learner" | "opponent";

/**
 * Узел дерева. Корень (`parent` = null, `ply` = 0) — начальная позиция: `uci` / `san` /
 * `mover` у него null. `children` — в порядке важности: первый — «основной» ход.
 */
export type OpeningNode = {
  id: number;
  parent: number | null;
  children: number[];
  ply: number;
  uci: string | null;
  san: string | null;
  mover: Mover | null;
  fen: string;
  /** Позиция ещё в теории (по базе дебютов). */
  book: boolean;
  /** Название дебюта, если оно появляется в этом узле. */
  name: string | null;
};

/** Узлы по id — так их ждут все компоненты. */
export type NodeIndex<N extends OpeningNode = OpeningNode> = ReadonlyMap<number, N>;

export const indexNodes = <N extends OpeningNode>(nodes: N[]): Map<number, N> =>
  new Map(nodes.map((node) => [node.id, node]));

/** Корень дерева (узел без родителя). */
export function rootOf<N extends OpeningNode>(index: NodeIndex<N>): N | null {
  for (const node of index.values()) if (node.parent === null) return node;
  return null;
}

/** Узлы от корня до `id` включительно. */
export function pathTo<N extends OpeningNode>(index: NodeIndex<N>, id: number): N[] {
  const path: N[] = [];
  let node = index.get(id);
  while (node) {
    path.push(node);
    node = node.parent === null ? undefined : index.get(node.parent);
  }
  return path.reverse();
}

/** Ходы (UCI) от начальной позиции до узла. */
export const lineUciTo = <N extends OpeningNode>(index: NodeIndex<N>, id: number): string[] =>
  pathTo(index, id).flatMap((node) => (node.uci ? [node.uci] : []));

/** Узел после ходов `line`; если линия в дереве обрывается — самый глубокий достигнутый. */
export function nodeAtLine<N extends OpeningNode>(index: NodeIndex<N>, line: string[]): N | null {
  let node = rootOf(index);
  if (!node) return null;
  for (const uci of line) {
    const next: N | undefined = node.children.map((id) => index.get(id)).find((child) => child?.uci === uci);
    if (!next) break;
    node = next;
  }
  return node;
}

/** Цвет фигур, сделавших ход в узле (нечётный полуход — белые). */
export const moverColor = (node: Pick<OpeningNode, "ply">): Color => (node.ply % 2 === 1 ? "white" : "black");

/** Номер хода (с 1) для полухода: 1–2 → 1, 3–4 → 2. */
export const moveNo = (ply: number) => Math.ceil(ply / 2);

/** Название дебюта в узле: ближайшее у него самого или у предков. */
export function nameAt<N extends OpeningNode>(index: NodeIndex<N>, id: number): string | null {
  for (const node of pathTo(index, id).reverse()) if (node.name) return node.name;
  return null;
}
