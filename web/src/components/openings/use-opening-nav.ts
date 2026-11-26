"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { pathTo, type NodeIndex, type OpeningNode } from "./types";

/**
 * Навигация по дереву дебютов: кнопки и клавиатура.
 *
 *  - `index` — узлы по id, `currentId` — текущий узел, `onSelect(id)` — перейти в узел;
 *  - `keyboard` — слушать стрелки на странице: ← назад по линии, → вперёд (в ту ветку, из
 *    которой вернулись, иначе в основную), ↑ ↓ — соседняя ветка того же хода, Home — в начало,
 *    N / P — следующий / предыдущий вариант (линия до листа).
 *    Не срабатывает в полях ввода и с модификаторами.
 */
export type OpeningNav = {
  toStart: () => void;
  back: () => void;
  forward: () => void;
  /** Соседняя ветка: -1 — выше в списке детей родителя, +1 — ниже. */
  sibling: (step: -1 | 1) => void;
  canBack: boolean;
  canForward: boolean;
  /**
   * Варианты — все линии дерева от начала до листа, в порядке важности (обход в глубину,
   * первый ребёнок — основной). `line` — номер текущей линии (с 0): та, что идёт через
   * текущий узел дальше по основным ходам (как её показывает дерево). `nextLine` / `prevLine`
   * переходят в узел, где соседняя линия отходит от текущей.
   */
  line: number;
  lines: number;
  nextLine: () => void;
  prevLine: () => void;
};

/** Листья дерева в порядке обхода в глубину (первый ребёнок — раньше). */
function leavesOf<N extends OpeningNode>(index: NodeIndex<N>): number[] {
  const root = [...index.values()].find((node) => node.parent === null);
  if (!root) return [];
  const leaves: number[] = [];
  const stack = [root.id];
  while (stack.length > 0) {
    const node = index.get(stack.pop()!);
    if (!node) continue;
    if (node.children.length === 0) leaves.push(node.id);
    else for (let i = node.children.length - 1; i >= 0; i -= 1) stack.push(node.children[i]);
  }
  return leaves;
}

const isEditable = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

export function useOpeningNav<N extends OpeningNode>(
  index: NodeIndex<N>,
  currentId: number,
  onSelect: (id: number) => void,
  { keyboard = true }: { keyboard?: boolean } = {},
): OpeningNav {
  const node = index.get(currentId);
  // Какой ребёнок был выбран у родителя последним: «→» после «←» возвращает в ту же ветку.
  const lastChild = useRef(new Map<number, number>());
  useEffect(() => {
    if (node?.parent != null) lastChild.current.set(node.parent, node.id);
  }, [node]);

  const leaves = useMemo(() => leavesOf(index), [index]);
  const leafNo = useMemo(() => new Map(leaves.map((id, i) => [id, i])), [leaves]);

  const nav = useMemo<OpeningNav>(() => {
    const parent = node?.parent != null ? index.get(node.parent) : undefined;
    const next = () => {
      if (!node || node.children.length === 0) return null;
      const last = lastChild.current.get(node.id);
      return last !== undefined && node.children.includes(last) ? last : node.children[0];
    };
    // Лист текущей линии: от текущего узла по основным ходам.
    let leaf = node;
    while (leaf && leaf.children.length > 0) leaf = index.get(leaf.children[0]);
    const line = leaf ? (leafNo.get(leaf.id) ?? 0) : 0;
    const toLine = (target: number) => {
      const targetLeaf = leaves[target];
      if (targetLeaf === undefined || !leaf) return;
      // Первый ход соседней линии, которого нет в текущей, — там она и отходит.
      const shared = new Set(pathTo(index, leaf.id).map((n) => n.id));
      const fork = pathTo(index, targetLeaf).find((n) => !shared.has(n.id));
      onSelect(fork?.id ?? targetLeaf);
    };
    return {
      line,
      lines: leaves.length,
      nextLine: () => toLine(line + 1),
      prevLine: () => toLine(line - 1),
      toStart: () => {
        for (const candidate of index.values()) if (candidate.parent === null) onSelect(candidate.id);
      },
      back: () => parent && onSelect(parent.id),
      forward: () => {
        const id = next();
        if (id !== null) onSelect(id);
      },
      sibling: (step) => {
        if (!parent || !node) return;
        const siblings = parent.children;
        const target = siblings[siblings.indexOf(node.id) + step];
        if (target !== undefined) onSelect(target);
      },
      canBack: parent !== undefined,
      canForward: node !== undefined && node.children.length > 0,
    };
  }, [index, node, onSelect, leaves, leafNo]);

  const ref = useRef(nav);
  useEffect(() => {
    ref.current = nav;
  }, [nav]);

  const onKey = useCallback((event: KeyboardEvent) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || isEditable(event.target)) return;
    const actions: Record<string, () => void> = {
      ArrowLeft: () => ref.current.back(),
      ArrowRight: () => ref.current.forward(),
      ArrowUp: () => ref.current.sibling(-1),
      ArrowDown: () => ref.current.sibling(1),
      Home: () => ref.current.toStart(),
    };
    // N / P — по физической клавише, чтобы работало и в русской раскладке.
    const byCode: Record<string, () => void> = {
      KeyN: () => ref.current.nextLine(),
      KeyP: () => ref.current.prevLine(),
    };
    const action = actions[event.key] ?? byCode[event.code];
    if (!action) return;
    event.preventDefault();
    action();
  }, []);

  useEffect(() => {
    if (!keyboard) return;
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [keyboard, onKey]);

  return nav;
}
