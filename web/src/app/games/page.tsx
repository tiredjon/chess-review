import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { GamesList, GamesListSkeleton } from "@/components/games-list";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource } from "@/lib/types";

export const metadata: Metadata = { title: "Партии" };

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];

const parseSource = (value: string | string[] | undefined): GameSource | null =>
  SOURCES.find((source) => source === value) ?? null;

export default function GamesPage({ searchParams }: PageProps<"/games">) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">Партии</h1>
        <Link href="/" className="text-sm font-medium text-accent underline-offset-2 hover:underline">
          Загрузить ещё
        </Link>
      </div>
      <Suspense fallback={<GamesListSkeleton />}>
        {searchParams.then((params) => {
          const source = parseSource(params.source);
          return (
            <>
              <SourceFilter current={source} />
              <GamesList key={source ?? "all"} source={source} />
            </>
          );
        })}
      </Suspense>
    </main>
  );
}

function SourceFilter({ current }: { current: GameSource | null }) {
  const options: [GameSource | null, string][] = [[null, "Все"], ...SOURCES.map((s) => [s, SOURCE_NAMES[s]] as [GameSource, string])];
  return (
    <nav aria-label="Источник" className="-mt-2 flex flex-wrap gap-1 text-sm">
      {options.map(([source, label]) => (
        <Link
          key={label}
          href={source ? `/games?source=${source}` : "/games"}
          aria-current={current === source ? "page" : undefined}
          className={`rounded-full border px-3 py-1 ${
            current === source
              ? "border-ink bg-ink text-paper"
              : "border-line text-muted hover:border-muted hover:text-ink"
          }`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
