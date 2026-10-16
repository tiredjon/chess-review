import type { Metadata } from "next";
import { Suspense } from "react";
import { StatsDashboard, StatsSkeleton } from "@/components/stats/stats-dashboard";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource, TimeClass } from "@/lib/types";
import { TIME_CLASS_NAMES } from "@/components/stats/filters";

export const metadata: Metadata = { title: "Статистика" };

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];
const TIME_CLASSES = Object.keys(TIME_CLASS_NAMES) as TimeClass[];

const pick = <T extends string>(options: T[], value: string | string[] | undefined): T | null =>
  options.find((option) => option === value) ?? null;

export default function StatsPage({ searchParams }: PageProps<"/stats">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <h1 className="text-2xl font-extrabold sm:text-3xl">Статистика</h1>
      <Suspense fallback={<StatsSkeleton />}>
        {searchParams.then((params) => (
          <StatsDashboard source={pick(SOURCES, params.source)} timeClass={pick(TIME_CLASSES, params.tc)} />
        ))}
      </Suspense>
    </main>
  );
}
