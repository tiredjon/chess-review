import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { WeaknessesHeading, WeaknessesSkeleton, WeaknessesView } from "@/components/insights/weaknesses-view";
import { SOURCE_NAMES } from "@/lib/format";
import type { GameSource, TimeClass } from "@/lib/types";

const SOURCES = Object.keys(SOURCE_NAMES) as GameSource[];
const TIME_CLASSES: TimeClass[] = ["bullet", "blitz", "rapid", "daily"];

const pick = <T extends string>(options: T[], value: string | string[] | undefined): T | null =>
  options.find((option) => option === value) ?? null;

// Слабые места (сессия 16.1): выводы по разобранным партиям → примеры → тренировка.
export default function WeaknessesPage({ searchParams }: PageProps<"/stats/weaknesses">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <DocumentTitle page="weaknesses" />
      <WeaknessesHeading />
      <Suspense fallback={<WeaknessesSkeleton />}>
        {searchParams.then((params) => (
          <WeaknessesView source={pick(SOURCES, params.source)} timeClass={pick(TIME_CLASSES, params.tc)} />
        ))}
      </Suspense>
    </main>
  );
}
