import { Suspense } from "react";
import { GamesHeader, GamesList, SourceFilter } from "@/components/games-list";
import { GamesTableSkeleton } from "@/components/games-table";
import { Panel } from "@/components/ui";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource } from "@/lib/types";

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];

const parseSource = (value: string | string[] | undefined): GameSource | null =>
  SOURCES.find((source) => source === value) ?? null;

export default function GamesPage({ searchParams }: PageProps<"/games">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <GamesHeader />
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
