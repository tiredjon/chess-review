// Партия с ботом по линии курса (сессия 14.3): чистая логика без React и алиасов `@/`,
// чтобы её исполнял Node напрямую (≥ 23 — .ts без компиляции).
//
//   Тесты: cd web && node --test src/components/courses/play-book.test.mjs
//
//  - `courseLines` — варианты курса «N из M»: линии дерева до листа в порядке обхода в
//    глубину (первый ребёнок — раньше). Так же их нумерует `useOpeningNav` на странице курса.
//  - `courseBook` — `OpponentBook` соперника: по выбранной линии, отошли — по дереву, вне
//    дерева — null (дальше бот сам).
//  - `lineProgress` — где партия относительно линии и дерева: для подсказок и итога.

/** Поля узла дерева курса, нужные здесь (подмножество `CourseNode`). */
export type PlayNode = {
  id: number;
  parent: number | null;
  children: number[];
  ply: number;
  uci: string | null;
  san: string | null;
  mover: "learner" | "opponent" | null;
  name: string | null;
  weight: number;
};

export type PlayIndex = ReadonlyMap<number, PlayNode>;

export type CourseLine = {
  /** Номер варианта с 0 (пользователь видит n + 1). */
  n: number;
  leaf: number;
  /** Узлы от первого хода до листа (без корня). */
  nodes: PlayNode[];
  uci: string[];
  /** Индекс первого хода, где линия отходит от основной (варианта 1); -1 — это она и есть. */
  fork: number;
  /** Название дебюта — самое глубокое на линии. */
  name: string | null;
  /** Вероятность линии по частоте ответов мастеров (произведение долей ответов соперника). */
  weight: number;
};

export const playIndex = (nodes: readonly PlayNode[]): Map<number, PlayNode> => new Map(nodes.map((node) => [node.id, node]));

/** Корень — как `rootOf` в openings/types.ts: первый узел без родителя. */
function rootOf(index: PlayIndex): PlayNode | null {
  for (const node of index.values()) if (node.parent === null) return node;
  return null;
}

function pathTo(index: PlayIndex, id: number): PlayNode[] {
  const path: PlayNode[] = [];
  let node = index.get(id);
  while (node) {
    path.push(node);
    node = node.parent === null ? undefined : index.get(node.parent);
  }
  return path.reverse();
}

const childrenOf = (index: PlayIndex, node: PlayNode): PlayNode[] => node.children.flatMap((id) => index.get(id) ?? []);

/** Доля ответа соперника среди братьев по `weight`; ходы ученика вес линии не меняют
 * (выбирает он сам, а «случайная линия» — про ответы соперника). */
function share(index: PlayIndex, node: PlayNode): number {
  const parent = node.parent === null ? undefined : index.get(node.parent);
  if (!parent) return 1;
  const siblings = childrenOf(index, parent);
  if (node.mover !== "opponent") return 1;
  const total = siblings.reduce((sum, child) => sum + Math.max(0, child.weight), 0);
  return total > 0 ? Math.max(0, node.weight) / total : 1 / siblings.length;
}

/** Варианты курса — как «Вариант N из M» на странице курса (`leavesOf` в use-opening-nav.ts). */
export function courseLines(index: PlayIndex): CourseLine[] {
  const root = rootOf(index);
  if (!root) return [];
  const leaves: number[] = [];
  const stack = [root.id];
  while (stack.length > 0) {
    const node = index.get(stack.pop()!);
    if (!node) continue;
    if (node.children.length === 0) leaves.push(node.id);
    else for (let i = node.children.length - 1; i >= 0; i -= 1) stack.push(node.children[i]);
  }
  return leaves.map((leaf, n) => {
    const nodes = pathTo(index, leaf).filter((node) => node.uci !== null);
    const fork = nodes.findIndex((node) => {
      const parent = node.parent === null ? undefined : index.get(node.parent);
      return parent !== undefined && parent.children[0] !== node.id;
    });
    const named = [...nodes].reverse().find((node) => node.name);
    return {
      n,
      leaf,
      nodes,
      uci: nodes.map((node) => node.uci!),
      fork,
      name: named?.name ?? null,
      weight: nodes.reduce((p, node) => p * share(index, node), 1),
    };
  });
}

/** Линия, которая идёт через узел дальше по основным ходам (как `nav.line` на странице курса). */
export function lineThrough(index: PlayIndex, lines: readonly CourseLine[], nodeId: number): number | null {
  let node = index.get(nodeId);
  if (!node) return null;
  while (node.children.length > 0) {
    const next = index.get(node.children[0]);
    if (!next) break;
    node = next;
  }
  const leaf = node.id;
  return lines.find((line) => line.leaf === leaf)?.n ?? null;
}

/** Случайный выбор по весам; `rand` — [0, 1). */
function pickWeighted<T>(items: readonly T[], weight: (item: T) => number, rand: () => number): T | null {
  const total = items.reduce((sum, item) => sum + Math.max(0, weight(item)), 0);
  if (items.length === 0) return null;
  if (total <= 0) return items[Math.floor(rand() * items.length)] ?? items[0];
  let r = rand() * total;
  for (const item of items) {
    r -= Math.max(0, weight(item));
    if (r < 0) return item;
  }
  return items[items.length - 1];
}

/** «Случайная линия»: вариант по частоте мастеров (вес линии). */
export const pickRandomLine = (lines: readonly CourseLine[], rand: () => number = Math.random): CourseLine | null =>
  pickWeighted(lines, (line) => line.weight, rand);

/** Узел дерева после ходов партии; null — партия вышла из дерева. */
export function nodeAfter(index: PlayIndex, historyUci: readonly string[]): PlayNode | null {
  let node = rootOf(index);
  for (const uci of historyUci) {
    if (!node) return null;
    node = childrenOf(index, node).find((child) => child.uci === uci) ?? null;
  }
  return node;
}

export type BookMode = "line" | "random";

/**
 * Ход соперника (UCI) или null — тогда бот играет сам:
 *  - партия идёт по линии `line` → следующий ход линии;
 *  - ученик сошёл с линии, но позиция в дереве → ответ соперника из дерева: с наибольшим
 *    `weight` (`mode` = "random" — случайно по весам);
 *  - позиции в дереве нет или у неё нет ответов соперника → null.
 * Сравнение — по ходам UCI с начала партии.
 */
export function courseBook(
  index: PlayIndex,
  line: Pick<CourseLine, "uci">,
  mode: BookMode = "line",
  rand: () => number = Math.random,
): (historyUci: readonly string[]) => string | null {
  return (historyUci) => {
    const onLine = historyUci.length < line.uci.length && historyUci.every((uci, i) => line.uci[i] === uci);
    if (onLine) return line.uci[historyUci.length];
    const node = nodeAfter(index, historyUci);
    if (!node) return null;
    const replies = childrenOf(index, node).filter((child) => child.mover === "opponent" && child.uci);
    if (replies.length === 0) return null;
    const pick =
      mode === "random"
        ? pickWeighted(replies, (child) => child.weight, rand)
        : replies.reduce((best, child) => (child.weight > best.weight ? child : best));
    return pick?.uci ?? null;
  };
}

export type Deviation = {
  /** Полуход отхода (с 1). */
  ply: number;
  /** Кто сошёл: ученик (с линии) или партия (из дерева). */
  played: string;
  /** SAN сыгранного хода — если известна (ход из дерева); иначе считает вызывающий. */
  playedSan: string | null;
  expected: string;
  expectedSan: string | null;
  /** Узел позиции перед отходом — «тренировать эту позицию». */
  nodeId: number;
};

export type LineProgress = {
  /** Сколько полуходов партии совпали с линией с начала. */
  matched: number;
  /** Длина линии в полуходах. */
  total: number;
  /** Линия пройдена до конца. */
  completed: boolean;
  /** Первый отход ученика от линии (пока линия ещё не кончилась). */
  lineExit: Deviation | null;
  /** Отход от линии был ходом из дерева курса (другая ветка). */
  lineExitInTree: boolean;
  /** Ход ученика, которым партия вышла из дерева курса (null — не выходила или вышла ходом соперника). */
  treeExit: Deviation | null;
  /** Ходы партии, прошедшие по дереву. */
  inTreePlies: number;
  /** Узел дерева после всей партии (null — вне дерева). */
  node: PlayNode | null;
  /** У соперника больше нет ходов курса: дальше бот играет сам. */
  bookOver: boolean;
};

/** Ход ученика в узле — основной (первый ребёнок ученика). */
const learnerMove = (index: PlayIndex, node: PlayNode): PlayNode | undefined =>
  childrenOf(index, node).find((child) => child.mover === "learner");

/** Где партия относительно линии и дерева курса. `learnerFirst` — ученик играет белыми. */
export function lineProgress(index: PlayIndex, line: Pick<CourseLine, "uci" | "nodes">, historyUci: readonly string[], learnerFirst: boolean): LineProgress {
  let matched = 0;
  while (matched < historyUci.length && matched < line.uci.length && historyUci[matched] === line.uci[matched]) matched += 1;
  const isLearnerPly = (ply: number) => (ply % 2 === 1) === learnerFirst;

  let lineExit: Deviation | null = null;
  let lineExitInTree = false;
  let treeExit: Deviation | null = null;
  let node = rootOf(index);
  let inTreePlies = 0;
  for (let i = 0; i < historyUci.length && node; i += 1) {
    const ply = i + 1;
    const next = childrenOf(index, node).find((child) => child.uci === historyUci[i]) ?? null;
    if (i === matched && i < line.uci.length && isLearnerPly(ply)) {
      const expected = line.nodes[i];
      lineExit = { ply, played: historyUci[i], playedSan: next?.san ?? null, expected: expected.uci!, expectedSan: expected.san, nodeId: node.id };
      lineExitInTree = next !== null;
    }
    if (!next) {
      const expected = isLearnerPly(ply) ? learnerMove(index, node) : undefined;
      if (expected)
        treeExit = { ply, played: historyUci[i], playedSan: null, expected: expected.uci!, expectedSan: expected.san, nodeId: node.id };
      node = null;
      break;
    }
    node = next;
    inTreePlies = ply;
  }
  const opponentToMove = isLearnerPly(historyUci.length);
  const bookOver =
    node === null || (opponentToMove ? !childrenOf(index, node).some((c) => c.mover === "opponent") : node.children.length === 0);
  return {
    matched,
    total: line.uci.length,
    completed: matched >= line.uci.length,
    lineExit,
    lineExitInTree,
    treeExit,
    inTreePlies,
    node,
    bookOver,
  };
}

/** «6.Bg5» / «6…e5» — номер хода для полухода (с 1). */
export const numbered = (ply: number, san: string) => `${Math.ceil(ply / 2)}${ply % 2 === 1 ? "." : "…"}${san}`;
