"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/use-i18n";
import { repertoireApi, type RepertoireNode, type RepertoireOpening, type RepertoireTree } from "@/lib/repertoire-api";
import type { Color } from "@/lib/types";
import { Button, Chip, ErrorText, fieldClass, Panel } from "../ui";
import { NodeStats } from "./node-stats";
import { OpeningBoard } from "./opening-board";
import { OpeningList } from "./opening-list";
import { OpeningControls, OpeningTree } from "./opening-tree";
import { indexNodes, lineUciTo, nameAt, nodeAtLine, rootOf } from "./types";
import { useOpeningNav } from "./use-opening-nav";

const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 12rem))" };

type Data = { tree: RepertoireTree; openings: RepertoireOpening[] };
type Load = { color: Color; data: Data } | { color: Color; error: string | null };

/** «Мой репертуар»: цвет, список дебютов, дерево ходов из партий на доске, «Учить эту линию». */
export function RepertoireView() {
  const { t } = useI18n();
  const [color, setColor] = useState<Color>("white");
  const [load, setLoad] = useState<Load | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([repertoireApi.tree(color), repertoireApi.openings(color)])
      .then(([tree, openings]) => !cancelled && setLoad({ color, data: { tree, openings } }))
      .catch((err) => !cancelled && setLoad({ color, error: err instanceof ApiError ? err.message : null }));
    return () => {
      cancelled = true;
    };
  }, [color, attempt]);

  const current = load?.color === color ? load : null;
  const retry = () => {
    setLoad(null);
    setAttempt((n) => n + 1);
  };

  return (
    <div className="flex flex-col gap-3">
      <h1 className="sr-only">{t.repertoire.title}</h1>
      <div role="radiogroup" aria-label={t.repertoire.color.label} className="flex gap-2">
        {(["white", "black"] as const).map((value) => (
          <Chip
            key={value}
            role="radio"
            aria-checked={color === value}
            active={color === value}
            onClick={() => setColor(value)}
          >
            {t.repertoire.color[value]}
          </Chip>
        ))}
      </div>

      {current === null ? (
        <p className="rounded-xl bg-panel p-6 text-muted">{t.repertoire.loading}</p>
      ) : "error" in current ? (
        <Panel>
          <ErrorText>{current.error ?? t.repertoire.loadError}</ErrorText>
          <Button variant="raised" className="mt-3" onClick={retry}>
            {t.repertoire.retry}
          </Button>
        </Panel>
      ) : current.data.tree.nodes.length === 0 || current.data.tree.total_games === 0 ? (
        <Panel>
          <p className="text-lg font-bold">{t.repertoire.empty.title(t.repertoire.empty[color])}</p>
          <p className="mt-1 text-soft">
            <Link href="/" className="font-bold text-green hover:underline">
              {t.repertoire.empty.importLink}
            </Link>{" "}
            {t.repertoire.empty.importText}
          </p>
        </Panel>
      ) : (
        // key: при смене цвета состояние просмотра начинается заново.
        <Loaded key={color} color={color} data={current.data} />
      )}
    </div>
  );
}

function Loaded({ color, data }: { color: Color; data: Data }) {
  const { t } = useI18n();
  const router = useRouter();
  const index = useMemo(() => indexNodes(data.tree.nodes), [data.tree]);
  const rootId = rootOf(index)?.id ?? 0;
  const [currentId, setCurrentId] = useState(rootId);
  const [tab, setTab] = useState<"openings" | "tree">("openings");
  const [query, setQuery] = useState("");
  const [learning, setLearning] = useState(false);
  const [learnError, setLearnError] = useState<string | null>(null);

  const select = useCallback((id: number) => {
    setCurrentId(id);
    setLearnError(null);
  }, []);
  const nav = useOpeningNav(index, currentId, select);

  const node = index.get(currentId);
  const name = nameAt(index, currentId);

  // Вес стрелки — доля самого частого хода из позиции.
  const weights = useMemo(() => {
    const children = (node?.children ?? []).flatMap((id) => index.get(id) ?? []);
    const top = Math.max(1, ...children.map((child) => child.games));
    return Object.fromEntries(children.map((child) => [child.id, child.games / top]));
  }, [index, node]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? data.openings.filter((o) => `${o.name} ${o.eco ?? ""}`.toLowerCase().includes(needle)) : data.openings;
  }, [data.openings, query]);

  const openOpening = (opening: RepertoireOpening) => {
    const target = nodeAtLine(index, opening.line_uci);
    if (target) select(target.id);
    setTab("tree");
  };

  const learn = async () => {
    setLearning(true);
    setLearnError(null);
    try {
      const course = await repertoireApi.createCourse({
        line_uci: lineUciTo(index, currentId),
        color,
        ...(name ? { name } : {}),
      });
      router.push(`/openings/courses/${course.id}`);
    } catch (err) {
      setLearnError(err instanceof ApiError ? err.message : t.repertoire.learn.error);
      setLearning(false);
    }
  };

  const meta = (n: RepertoireNode) =>
    n.parent !== null && (index.get(n.parent)?.children.length ?? 0) > 1 ? (
      <span className="text-xs font-semibold text-muted">{n.games}</span>
    ) : null;

  return (
    <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] xl:grid-cols-[minmax(0,1fr)_minmax(360px,480px)]">
      <div className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-3">
        <div className="mx-auto w-full" style={BOARD_WIDTH}>
          <OpeningBoard index={index} currentId={currentId} orientation={color} onSelect={select} weights={weights} />
          <OpeningControls nav={nav} className="mt-2" />
        </div>
        <NodeStats index={index} currentId={currentId} onSelect={select} />
        <div>
          <Button onClick={learn} disabled={learning || currentId === rootId} className="w-full">
            {learning ? t.repertoire.learn.busy : t.repertoire.learn.button}
          </Button>
          <p className="mt-1.5 text-xs text-muted">
            {currentId === rootId ? t.repertoire.learn.needMove : t.repertoire.learn.hint}
          </p>
          <div className="mt-1">
            <ErrorText>{learnError}</ErrorText>
          </div>
        </div>
      </div>

      <Panel className="flex min-w-0 flex-col gap-3 !p-3">
        <div role="tablist" aria-label={t.repertoire.tabs.label} className="flex gap-1">
          {(["openings", "tree"] as const).map((value) => (
            <Chip
              key={value}
              role="tab"
              aria-selected={tab === value}
              active={tab === value}
              onClick={() => setTab(value)}
              className="flex-1"
            >
              {t.repertoire.tabs[value]}
            </Chip>
          ))}
        </div>
        {tab === "openings" ? (
          <>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label={t.repertoire.search.label}
              placeholder={t.repertoire.search.placeholder}
              className={fieldClass}
            />
            <div className="max-h-[70dvh] overflow-y-auto lg:max-h-[calc(100dvh-14rem)]">
              {filtered.length === 0 ? (
                <p className="p-2 text-sm text-muted">{t.repertoire.search.none}</p>
              ) : (
                <OpeningList openings={filtered} selectedName={name} onSelect={openOpening} />
              )}
            </div>
          </>
        ) : (
          <OpeningTree
            index={index}
            currentId={currentId}
            onSelect={select}
            renderMeta={meta}
            className="max-h-[60dvh] lg:max-h-[calc(100dvh-14rem)]"
          />
        )}
      </Panel>
    </div>
  );
}
