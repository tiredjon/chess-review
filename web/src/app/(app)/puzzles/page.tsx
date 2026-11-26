import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { PuzzleSkeleton } from "@/components/puzzles/puzzle-trainer";
import { PuzzlesScreen } from "@/components/puzzles/puzzles-screen";
import { parseView, viewKey } from "@/components/puzzles/puzzle-view";

// Пазлы: `/puzzles?mode=practice&theme=fork&phase=endgame&eco=B90` — режим и фильтры в URL
// (ссылки с экрана слабых мест). Новая ссылка — новый экземпляр экрана (`key`).
export default function PuzzlesPage({ searchParams }: PageProps<"/puzzles">) {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="puzzles" />
      <Suspense fallback={<PuzzleSkeleton />}>
        {searchParams.then((query) => {
          const view = parseView(query);
          return <PuzzlesScreen key={viewKey(view)} initial={view} />;
        })}
      </Suspense>
    </main>
  );
}
