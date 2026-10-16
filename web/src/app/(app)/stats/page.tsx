import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { StatsDashboard, StatsHeading, StatsSkeleton } from "@/components/stats/stats-dashboard";
import { TIME_CLASSES } from "@/components/stats/filters";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource } from "@/lib/types";

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];

const pick = <T extends string>(options: T[], value: string | string[] | undefined): T | null =>
  options.find((option) => option === value) ?? null;

export default function StatsPage({ searchParams }: PageProps<"/stats">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <DocumentTitle page="stats" />
      <StatsHeading />
      <Suspense fallback={<StatsSkeleton />}>
        {searchParams.then((params) => (
          <StatsDashboard source={pick(SOURCES, params.source)} timeClass={pick(TIME_CLASSES, params.tc)} />
        ))}
      </Suspense>
    </main>
  );
}
