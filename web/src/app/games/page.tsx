import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { GamesList } from "@/components/games-list";
import { GamesTableSkeleton } from "@/components/games-table";
import { Panel } from "@/components/ui";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource } from "@/lib/types";

export const metadata: Metadata = { title: "Партии" };

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];

const parseSource = (value: string | string[] | undefined): GameSource | null =>
  SOURCES.find((source) => source === value) ?? null;

export default function GamesPage({ searchParams }: PageProps<"/games">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold sm:text-3xl">История партий</h1>
        <Link href="/" className="text-sm font-bold text-green hover:underline">
          Загрузить ещё
        </Link>
      </div>
      <Panel>
        <Suspense fallback={<GamesTableSkeleton />}>
          {searchParams.then((params) => {
            const source = parseSource(params.source);
            return (
              <div className="flex flex-col gap-4">
                <SourceFilter current={source} />
                <GamesList key={source ?? "all"} source={source} />
              </div>
            );
          })}
        </Suspense>
      </Panel>
    </main>
  );
}

function SourceFilter({ current }: { current: GameSource | null }) {
  const options: [GameSource | null, string][] = [
    [null, "Все"],
    ...SOURCES.map((source): [GameSource, string] => [source, SOURCE_NAMES[source]]),
  ];
  return (
    <nav aria-label="Источник" className="flex flex-wrap gap-2">
      {options.map(([source, label]) => (
        <Link
          key={label}
          href={source ? `/games?source=${source}` : "/games"}
          aria-current={current === source ? "page" : undefined}
          className={`flex min-h-10 items-center rounded-lg px-4 text-sm font-semibold ${
            current === source
              ? "bg-raised text-ink ring-2 ring-green ring-inset"
              : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
          }`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
