import type { Metadata } from "next";
import { Suspense } from "react";
import { GameReview, ReviewSkeleton } from "@/components/review/game-review";

export const metadata: Metadata = { title: "Разбор партии" };

export default function GamePage({ params, searchParams }: PageProps<"/games/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <Suspense fallback={<ReviewSkeleton />}>
        {Promise.all([params, searchParams]).then(([{ id }, query]) => (
          <GameReview key={id} id={id} autoAnalyze={query.analyze === "1"} />
        ))}
      </Suspense>
    </main>
  );
}
