import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { GameReview, ReviewSkeleton } from "@/components/review/game-review";

export default function GamePage({ params, searchParams }: PageProps<"/games/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="review" />
      <Suspense fallback={<ReviewSkeleton />}>
        {Promise.all([params, searchParams]).then(([{ id }, query]) => (
          <GameReview key={id} id={id} autoAnalyze={query.analyze === "1"} initialPly={parsePly(query.ply)} />
        ))}
      </Suspense>
    </main>
  );
}

/** `?ply=N` — открыть разбор сразу на N-м полуходе (ссылки из статистики и пазлов). */
function parsePly(value: string | string[] | undefined): number {
  const ply = Number(value);
  return Number.isInteger(ply) && ply > 0 ? ply : 0;
}
