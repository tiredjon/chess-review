"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { applyUci, START_FEN, uciSquares } from "@/lib/chess";
import { coursesApi, type CatalogFamily, type CatalogLine } from "@/lib/courses-api";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { Color } from "@/lib/types";
import { Board, NO_MARKS } from "../review/board";
import { Figurine } from "../review/move-list";
import { Button, Chip, ErrorText, fieldClass, Panel } from "../ui";
import { ColorMark, errorText } from "./shared";

// Самые частые дебюты — первыми (остальные по алфавиту).
const POPULAR = [
  "Sicilian Defense",
  "French Defense",
  "Caro-Kann Defense",
  "Ruy Lopez",
  "Italian Game",
  "Queen's Gambit Declined",
  "Slav Defense",
  "King's Indian Defense",
  "Nimzo-Indian Defense",
  "English Opening",
  "Scandinavian Defense",
  "Pirc Defense",
  "Grünfeld Defense",
  "Scotch Game",
  "Dutch Defense",
  "London System",
];
const SEARCH_LIMIT = 60;
const LAST_MOVE = "rgba(247, 214, 92, 0.6)";

type Indexed = CatalogLine & { family: string; variation: string; haystack: string };

/** Цвет по умолчанию — сторона, сделавшая последний ход линии (её дебют). */
const defaultColor = (line: CatalogLine): Color => (line.uci.length % 2 === 1 ? "white" : "black");

/** Короткое имя линии внутри варианта: «Najdorf Variation, English Attack» → «English Attack». */
function lineTitle(line: Indexed, mainLine: string): string {
  const prefix = line.variation === line.family ? line.family : `${line.family}: ${line.variation}`;
  const tail = line.name.startsWith(prefix) ? line.name.slice(prefix.length).replace(/^[,:]\s*/, "") : line.name;
  return tail || mainLine;
}

/** Каталог дебютов: семейства → варианты → линии, поиск, выбор цвета → новый курс. */
export function Catalog() {
  const { t } = useI18n();
  const l = t.courses.catalog;
  const [families, setFamilies] = useState<CatalogFamily[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState<string | null>(null);
  const [selected, setSelected] = useState<Indexed | null>(null);
  const preview = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    coursesApi
      .catalog()
      .then((value) => !cancelled && setFamilies(value))
      .catch((err) => !cancelled && setError(err ?? true));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const all = useMemo<Indexed[]>(
    () =>
      (families ?? []).flatMap((f) =>
        f.variations.flatMap((v) =>
          v.lines.map((line) => ({
            ...line,
            family: f.name,
            variation: v.name,
            haystack: `${line.name} ${line.eco} ${line.pgn}`.toLowerCase(),
          })),
        ),
      ),
    [families],
  );

  const sorted = useMemo(() => {
    const list = [...(families ?? [])];
    const rank = (name: string) => (POPULAR.includes(name) ? POPULAR.indexOf(name) : POPULAR.length);
    return list.sort((a, b) => rank(a.name) - rank(b.name) || a.name.localeCompare(b.name));
  }, [families]);

  const needle = query.trim().toLowerCase();
  const found = useMemo(() => {
    if (!needle) return [];
    const words = needle.split(/\s+/);
    return all.filter((line) => words.every((word) => line.haystack.includes(word)));
  }, [all, needle]);

  const choose = (line: Indexed) => {
    setSelected(line);
    // На телефоне карточка линии — над списком: прокрутить к ней.
    requestAnimationFrame(() => {
      if (window.matchMedia("(max-width: 1023px)").matches) preview.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const current = family ? sorted.find((f) => f.name === family) : undefined;

  return (
    <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]">
      <Panel title={l.title} className="min-w-0 !p-3 sm:!p-4">
        <p className="-mt-2 mb-3 text-sm text-muted">{l.hint}</p>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label={l.search}
          placeholder={l.searchPlaceholder}
          className={fieldClass}
        />
        <div className="mt-3">
          {error && !families ? (
            <div>
              <ErrorText>{errorText(t, error, l.loadError)}</ErrorText>
              <Button variant="raised" className="mt-3" onClick={() => setAttempt((n) => n + 1)}>
                {t.courses.retry}
              </Button>
            </div>
          ) : !families ? (
            <div aria-busy className="flex flex-col gap-1.5">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="h-11 animate-pulse rounded-lg bg-raised/50" />
              ))}
            </div>
          ) : needle ? (
            found.length === 0 ? (
              <p className="p-2 text-sm text-muted">{l.nothing}</p>
            ) : (
              <>
                <ul className="flex flex-col gap-1">
                  {found.slice(0, SEARCH_LIMIT).map((line) => (
                    <li key={`${line.name}-${line.uci.join("")}`}>
                      <LineButton line={line} title={line.name} selected={selected === line} onSelect={choose} />
                    </li>
                  ))}
                </ul>
                {found.length > SEARCH_LIMIT && <p className="p-2 text-sm text-muted">{l.more(found.length - SEARCH_LIMIT)}</p>}
              </>
            )
          ) : current ? (
            <FamilyLines
              family={current}
              lines={all.filter((line) => line.family === current.name)}
              selected={selected}
              onSelect={choose}
              onBack={() => setFamily(null)}
            />
          ) : (
            <FamilyList families={sorted} onOpen={setFamily} />
          )}
        </div>
      </Panel>

      {/* Колонка тянется на высоту списка, карточка линии внутри неё «липнет» к верху экрана. */}
      <div ref={preview} className="order-first scroll-mt-3 lg:order-none lg:self-stretch">
        <div className="lg:sticky lg:top-3">
          {selected ? (
            <NewCourse key={selected.name + selected.uci.join("")} line={selected} onClose={() => setSelected(null)} />
          ) : (
            <p className="rounded-xl bg-panel p-4 text-sm text-muted max-lg:hidden">{t.courses.catalog.pick}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function FamilyList({ families, onOpen }: { families: CatalogFamily[]; onOpen: (name: string) => void }) {
  const { t } = useI18n();
  const popular = families.filter((f) => POPULAR.includes(f.name));
  const rest = families.filter((f) => !POPULAR.includes(f.name));
  const count = (f: CatalogFamily) => f.variations.reduce((sum, v) => sum + v.lines.length, 0);
  const item = (f: CatalogFamily) => (
    <li key={f.name}>
      <button
        type="button"
        onClick={() => onOpen(f.name)}
        className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg bg-raised/50 px-3 py-2 text-left hover:bg-raised"
      >
        <span className="min-w-0 text-[15px] font-bold">{f.name}</span>
        <span className="shrink-0 text-xs text-muted">{t.courses.catalog.lines(count(f))}</span>
      </button>
    </li>
  );
  return (
    <div className="flex flex-col gap-4">
      <section>
        <h3 className="mb-1.5 px-1 text-xs font-bold tracking-wide text-muted uppercase">{t.courses.catalog.popular}</h3>
        <ul className="grid gap-1 sm:grid-cols-2">{popular.map(item)}</ul>
      </section>
      <section>
        <h3 className="mb-1.5 px-1 text-xs font-bold tracking-wide text-muted uppercase">{t.courses.catalog.all}</h3>
        <ul className="grid gap-1 sm:grid-cols-2">{rest.map(item)}</ul>
      </section>
    </div>
  );
}

function FamilyLines({
  family,
  lines,
  selected,
  onSelect,
  onBack,
}: {
  family: CatalogFamily;
  lines: Indexed[];
  selected: Indexed | null;
  onSelect: (line: Indexed) => void;
  onBack: () => void;
}) {
  const { t } = useI18n();
  const l = t.courses.catalog;
  const [open, setOpen] = useState<string | null>(family.variations[0]?.name ?? null);
  return (
    <div>
      <button type="button" onClick={onBack} className="mb-2 inline-flex min-h-9 items-center gap-1 rounded-md px-1.5 text-sm font-semibold text-muted hover:text-ink">
        <span aria-hidden>←</span> {l.back}
      </button>
      <h3 className="mb-2 px-1 text-lg font-extrabold">{family.name}</h3>
      <ul className="flex flex-col gap-1">
        {family.variations.map((variation) => {
          const own = lines.filter((line) => line.variation === variation.name);
          const expanded = open === variation.name;
          return (
            <li key={variation.name} className="rounded-lg bg-raised/40">
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : variation.name)}
                className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-raised"
              >
                <span aria-hidden className={`text-muted transition-transform ${expanded ? "rotate-90" : ""}`}>
                  ›
                </span>
                <span className="min-w-0 flex-1 text-[15px] font-bold">
                  {variation.name === family.name ? l.mainLine : variation.name}
                </span>
                <span className="shrink-0 text-xs text-muted">{l.lines(own.length)}</span>
              </button>
              {expanded && (
                <ul className="flex flex-col gap-1 px-1.5 pb-1.5">
                  {own.map((line) => (
                    <li key={`${line.name}-${line.uci.join("")}`}>
                      <LineButton line={line} title={lineTitle(line, l.mainLine)} selected={selected === line} onSelect={onSelect} />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function LineButton({
  line,
  title,
  selected,
  onSelect,
}: {
  line: Indexed;
  title: string;
  selected: boolean;
  onSelect: (line: Indexed) => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onSelect(line)}
      className={`flex w-full flex-col gap-0.5 rounded-md px-2.5 py-2 text-left ${
        selected ? "bg-raised ring-2 ring-green ring-inset" : "bg-panel/60 hover:bg-raised"
      }`}
    >
      <span className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 text-sm font-bold">{title}</span>
        <span className="shrink-0 text-xs font-semibold text-muted">{line.eco}</span>
      </span>
      <span className="truncate text-xs text-muted">{line.pgn}</span>
    </button>
  );
}

/** Линия: позиция в конце, ходы, выбор цвета и «Создать курс». */
function NewCourse({ line, onClose }: { line: Indexed; onClose: () => void }) {
  const { t } = useI18n();
  const l = t.courses.create;
  const router = useRouter();
  const [color, setColor] = useState<Color>(() => defaultColor(line));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fen = useMemo(() => line.uci.reduce((position, uci) => applyUci(position, uci) ?? position, START_FEN), [line]);
  const marks = useMemo(() => {
    const last = line.uci.at(-1);
    if (!last) return NO_MARKS;
    const { from, to } = uciSquares(last);
    return { ...NO_MARKS, key: line.name, highlights: { [from]: LAST_MOVE, [to]: LAST_MOVE } };
  }, [line]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const course = await coursesApi.create({ line_uci: line.uci, color, source: "catalog", name: line.name });
      router.push(`/openings/courses/${course.id}`);
    } catch (err) {
      setError(errorText(t, err, l.error));
      setBusy(false);
    }
  };

  return (
    <section aria-label={l.title} className="cc-slide-in flex flex-col gap-3 rounded-xl bg-panel p-3 sm:p-4">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold tracking-wide text-muted uppercase">
            {l.title} · {line.eco}
          </p>
          <h2 className="mt-0.5 text-[17px] leading-snug font-extrabold">{line.name}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={l.close}
          title={l.close}
          className="-mt-1 -mr-1 flex size-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-raised hover:text-ink"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </div>

      <div className="mx-auto w-full max-w-[min(100%,360px)]">
        <Board fen={fen} orientation={color} marks={marks} />
      </div>

      <PgnLine pgn={line.pgn} />

      <div role="radiogroup" aria-label={t.courses.color.label} className="grid grid-cols-2 gap-2">
        {(["white", "black"] as const).map((value) => (
          <Chip key={value} role="radio" aria-checked={color === value} active={color === value} onClick={() => setColor(value)}>
            <span className="inline-flex items-center gap-2">
              <ColorMark color={value} size={20} />
              {t.courses.color.label} {t.courses.color[value].toLowerCase()}
            </span>
          </Chip>
        ))}
      </div>

      <Button size="lg" onClick={create} disabled={busy}>
        {busy ? l.busy : l.button}
      </Button>
      <p className="text-xs text-muted">{l.hint(color === "white" ? t.courses.color.white.toLowerCase() : t.courses.color.black.toLowerCase())}</p>
      <ErrorText>{error}</ErrorText>
    </section>
  );
}

/** Токены PGN: номера ходов и ходы с цветом сделавшей их стороны. */
function pgnTokens(pgn: string): { text: string; color: Color | null }[] {
  let color: Color = "white";
  return pgn.split(/\s+/).map((text) => {
    if (/^\d+\.+$/.test(text)) {
      color = text.endsWith("...") ? "black" : "white";
      return { text, color: null };
    }
    const mover = color;
    color = color === "white" ? "black" : "white";
    return { text, color: mover };
  });
}

/** Ходы линии фигурной нотацией: «1. e4 c5 2. ♘f3». */
export function PgnLine({ pgn }: { pgn: string }) {
  const tokens = useMemo(() => pgnTokens(pgn), [pgn]);
  return (
    <p className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[15px] font-bold text-soft">
      {tokens.map((token, index) =>
        token.color === null ? (
          <span key={index} className="pl-1 text-sm font-semibold text-muted">
            {token.text}
          </span>
        ) : (
          <span key={index} className="whitespace-nowrap">
            <Figurine san={token.text} color={token.color} />
          </span>
        ),
      )}
    </p>
  );
}
