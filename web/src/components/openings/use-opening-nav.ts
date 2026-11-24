"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { NodeIndex, OpeningNode } from "./types";

/**
 * Навигация по дереву дебютов: кнопки и клавиатура.
 *
 *  - `index` — узлы по id, `currentId` — текущий узел, `onSelect(id)` — перейти в узел;
 *  - `keyboard` — слушать стрелки на странице: ← назад по линии, → вперёд (в ту ветку, из
 *    которой вернулись, иначе в основную), ↑ ↓ — соседняя ветка того же хода, Home — в начало.
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
};

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

  const nav = useMemo<OpeningNav>(() => {
    const parent = node?.parent != null ? index.get(node.parent) : undefined;
    const next = () => {
      if (!node || node.children.length === 0) return null;
      const last = lastChild.current.get(node.id);
      return last !== undefined && node.children.includes(last) ? last : node.children[0];
    };
    return {
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
  }, [index, node, onSelect]);

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
    const action = actions[event.key];
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
