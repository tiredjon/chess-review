"use client";

// Экран тренажёра эндшпиля /play/endgames (сессия 16.3): вкладки «Типовые» (каталог по
// категориям, прогресс) и «Из моих партий» (ошибки в эндшпиле разобранных партий); выбор
// позиции → доигрывание против бота. Состояние — в URL: `?tab=catalog|mine`, `&id=` (позиция
// каталога) или `&key=` (позиция из партии) — по ссылке `/play/endgames?tab=mine` из 16.1.
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { endgamesApi, type Catalog, type CatalogPosition, type GamePosition, type Progress } from "@/lib/endgames-api";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n/use-i18n";
import { Button } from "../ui";
import { EndgamePlay, type PlayTarget } from "./endgame-play";
import { PositionThumb } from "./position-thumb";

export type EndgamesTab = "catalog" | "mine";
export type EndgamesQuery = { tab: EndgamesTab; id: string | null; key: string | null };

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ok"; data: T };

const MINE_LIMIT = 30;

function useLoad<T>(enabled: boolean, load: () => Promise<T>, fallback: string) {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    load()
      .then((data) => !cancelled && setState({ status: "ok", data }))
      .catch((error: unknown) => !cancelled && setState({ status: "error", message: error instanceof ApiError ? error.message : fallback }));
    return () => {
      cancelled = true;
    };
  }, [enabled, load, fallback, attempt]);
  const retry = () => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  };
  return { state, setState, retry };
}

const loadCatalog = () => endgamesApi.catalog();
const loadMine = () => endgamesApi.mine(MINE_LIMIT).then((body) => body.positions);

export function urlOf(query: Partial<EndgamesQuery>): string {
  const params = new URLSearchParams({ tab: query.tab ?? "catalog" });
  if (query.id) params.set("id", query.id);
  if (query.key) params.set("key", query.key);
  return `/play/endgames?${params}`;
}

export function EndgamesScreen({ query }: { query: EndgamesQuery }) {
  const { t, lang } = useI18n();
  const router = useRouter();
  const e = t.endgames;
  const catalog = useLoad<Catalog>(query.tab === "catalog", loadCatalog, e.loadError);
  const mine = useLoad<GamePosition[]>(query.tab === "mine", loadMine, e.loadError);

  const go = useCallback((next: Partial<EndgamesQuery>) => router.push(urlOf(next), { scroll: true }), [router]);

  // Прогресс после попытки — сразу в списке (без перезапроса).
  const { setState: setCatalog } = catalog;
  const { setState: setMine } = mine;
  const recordCatalog = useCallback(
    (id: string, progress: Progress) =>
      setCatalog((state) =>
        state.status === "ok"
          ? { ...state, data: { ...state.data, positions: state.data.positions.map((p) => (p.id === id ? { ...p, ...progress } : p)) } }
          : state,
      ),
    [setCatalog],
  );
  const recordMine = useCallback(
    (key: string, progress: Progress) =>
      setMine((state) =>
        state.status === "ok" ? { ...state, data: state.data.map((p) => (p.key === key ? { ...p, ...progress } : p)) } : state,
      ),
    [setMine],
  );

  // Выбранная позиция → партия.
  if (query.tab === "catalog" && query.id && catalog.state.status === "ok") {
    const positions = catalog.state.data.positions;
    const index = positions.findIndex((p) => p.id === query.id);
    if (index >= 0) {
      const position = positions[index];
      const next = positions[index + 1];
      const copy = e.positions[position.id];
      const target: PlayTarget = {
        source: "catalog",
        key: position.id,
        fen: position.fen,
        goal: position.goal,
        name: copy?.name ?? position.id,
        hint: copy?.hint ?? null,
      };
      return (
        <PlayFrame title={target.name} onBack={() => go({ tab: "catalog" })}>
          <EndgamePlay
            key={position.id}
            target={target}
            onBack={() => go({ tab: "catalog" })}
            onNext={next ? () => go({ tab: "catalog", id: next.id }) : null}
            onRecorded={(progress) => recordCatalog(position.id, progress)}
          />
        </PlayFrame>
      );
    }
  }
  if (query.tab === "mine" && query.key && mine.state.status === "ok") {
    const positions = mine.state.data;
    const index = positions.findIndex((p) => p.key === query.key);
    if (index >= 0) {
      const position = positions[index];
      const next = positions[index + 1];
      const target: PlayTarget = {
        source: "game",
        key: position.key,
        fen: position.fen,
        goal: position.goal,
        name: `${e.game.fromGame}: ${e.mine.title(position.opponent)}`,
        hint: position.best_san ? `${e.mine.played(position.san)}, ${e.mine.best(position.best_san)}.` : null,
        game: { id: position.game_id, ply: position.ply },
      };
      return (
        <PlayFrame title={target.name} onBack={() => go({ tab: "mine" })}>
          <EndgamePlay
            key={position.key}
            target={target}
            onBack={() => go({ tab: "mine" })}
            onNext={next ? () => go({ tab: "mine", key: next.key }) : null}
            onRecorded={(progress) => recordMine(position.key, progress)}
          />
        </PlayFrame>
      );
    }
  }

  const tabs: EndgamesTab[] = ["catalog", "mine"];
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-extrabold">{e.title}</h1>
        <p className="text-sm text-soft">{e.subtitle}</p>
      </header>
      <div role="tablist" aria-label={e.title} className="flex gap-1 border-b border-line">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={query.tab === tab}
            onClick={() => go({ tab })}
            className={`-mb-px min-h-11 border-b-2 px-4 text-[15px] font-bold ${
              query.tab === tab ? "border-green text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {e.tabs[tab]}
          </button>
        ))}
      </div>
      {query.tab === "catalog" ? (
        <Loaded state={catalog.state} onRetry={catalog.retry}>
          {(data) => <CatalogList catalog={data} onOpen={(id) => go({ tab: "catalog", id })} />}
        </Loaded>
      ) : (
        <Loaded state={mine.state} onRetry={mine.retry}>
          {(data) => <MineList positions={data} lang={lang} onOpen={(key) => go({ tab: "mine", key })} />}
        </Loaded>
      )}
    </div>
  );
}

function PlayFrame({ title, onBack, children }: { title: string; onBack: () => void; children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex min-h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-bold text-soft hover:bg-raised hover:text-ink"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6" />
          </svg>
          {t.endgames.game.back}
        </button>
        <h1 className="min-w-0 truncate text-lg font-extrabold">{title}</h1>
      </div>
      {children}
    </div>
  );
}

function Loaded<T>({ state, onRetry, children }: { state: Load<T>; onRetry: () => void; children: (data: T) => React.ReactNode }) {
  const { t } = useI18n();
  if (state.status === "loading")
    return (
      <div aria-busy className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="aspect-[4/5] animate-pulse rounded-xl bg-panel" />
        ))}
      </div>
    );
  if (state.status === "error")
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-xl bg-panel p-4">
        <p className="text-sm font-semibold text-danger">{state.message}</p>
        <Button variant="raised" size="sm" onClick={onRetry}>
          {t.endgames.retry}
        </Button>
      </div>
    );
  return <>{children(state.data)}</>;
}

function GoalPill({ goal }: { goal: "win" | "draw" }) {
  const { t } = useI18n();
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] font-extrabold tracking-wide uppercase ${
        goal === "win" ? "bg-green/20 text-green" : "bg-raised text-soft"
      }`}
    >
      {t.endgames.goal[goal]}
    </span>
  );
}

function Difficulty({ value }: { value: number }) {
  const { t } = useI18n();
  return (
    <span className="flex items-center gap-0.5" title={t.endgames.difficulty[value]} aria-label={t.endgames.difficulty[value]}>
      {[1, 2, 3].map((n) => (
        <span key={n} aria-hidden className={`h-1.5 w-1.5 rounded-full ${n <= value ? "bg-soft" : "bg-raised"}`} />
      ))}
    </span>
  );
}

function CatalogList({ catalog, onOpen }: { catalog: Catalog; onOpen: (id: string) => void }) {
  const { t } = useI18n();
  const e = t.endgames;
  return (
    <div className="flex flex-col gap-6">
      {catalog.categories.map((category) => {
        const positions = catalog.positions.filter((p) => p.category === category);
        if (positions.length === 0) return null;
        const done = positions.filter((p) => p.successes > 0).length;
        return (
          <section key={category} aria-labelledby={`eg-${category}`} className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <h2 id={`eg-${category}`} className="text-lg font-extrabold">
                {e.categories[category]}
              </h2>
              <span className="text-sm font-semibold text-muted">{e.categoryProgress(done, positions.length)}</span>
              <span aria-hidden className="h-1.5 min-w-12 flex-1 overflow-hidden rounded-full bg-raised sm:max-w-48">
                <span className="block h-full rounded-full bg-green" style={{ width: `${(done / positions.length) * 100}%` }} />
              </span>
            </div>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {positions.map((position) => (
                <li key={position.id}>
                  <CatalogCard position={position} onOpen={() => onOpen(position.id)} />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function CatalogCard({ position, onOpen }: { position: CatalogPosition; onOpen: () => void }) {
  const { t } = useI18n();
  const e = t.endgames;
  const name = e.positions[position.id]?.name ?? position.id;
  const solved = position.successes > 0;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex h-full w-full flex-col gap-2 rounded-xl bg-panel p-2.5 text-left hover:bg-raised/70 focus-visible:ring-2 focus-visible:ring-green focus-visible:outline-none"
    >
      <span className="relative block">
        <PositionThumb fen={position.fen} orientation={position.color} label={name} />
        {solved && (
          <span
            className="absolute top-1 right-1 flex h-6 w-6 items-center justify-center rounded-full bg-green text-white shadow"
            title={e.solved}
            aria-label={e.solved}
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m5 12.5 4.5 4.5L19 7.5" />
            </svg>
          </span>
        )}
      </span>
      <span className="line-clamp-2 min-h-[2.5em] text-sm leading-tight font-bold group-hover:text-ink">{name}</span>
      <span className="mt-auto flex items-center justify-between gap-2">
        <GoalPill goal={position.goal} />
        <Difficulty value={position.difficulty} />
      </span>
      <span className="truncate text-xs text-muted">{e.progress(position.attempts, position.successes)}</span>
    </button>
  );
}

function MineList({ positions, lang, onOpen }: { positions: GamePosition[]; lang: "ru" | "en"; onOpen: (key: string) => void }) {
  const { t } = useI18n();
  const e = t.endgames;
  if (positions.length === 0)
    return (
      <div className="rounded-xl bg-panel p-5">
        <p className="font-bold">{e.mine.empty}</p>
        <p className="mt-1 text-sm text-soft">{e.mine.emptyHint}</p>
      </div>
    );
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {positions.map((position) => {
        const color = position.fen.split(" ")[1] === "b" ? "black" : "white";
        const date = formatDate(position.played_at, lang);
        return (
          <li key={position.key}>
            <button
              type="button"
              onClick={() => onOpen(position.key)}
              className="group flex h-full w-full flex-col gap-2 rounded-xl bg-panel p-2.5 text-left hover:bg-raised/70 focus-visible:ring-2 focus-visible:ring-green focus-visible:outline-none"
            >
              <PositionThumb fen={position.fen} orientation={color} label={e.mine.title(position.opponent)} />
              <span className="truncate text-sm font-bold">{e.mine.title(position.opponent)}</span>
              <span className="truncate text-xs text-muted">
                {[date, e.mine.pieces(position.pieces)].filter(Boolean).join(" · ")}
              </span>
              <span className="line-clamp-2 text-xs text-soft">
                {e.mine.played(position.san)}
                {position.best_san ? `, ${e.mine.best(position.best_san)}` : ""}
              </span>
              <span className="mt-auto flex items-center justify-between gap-2">
                <GoalPill goal={position.goal} />
                <span className="text-[11px] font-semibold text-muted">{e.mine.win(position.win_before)}</span>
              </span>
              <span className="truncate text-xs text-muted">{e.progress(position.attempts, position.successes)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
