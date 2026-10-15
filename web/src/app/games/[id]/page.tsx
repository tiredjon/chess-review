import type { Metadata } from "next";
import { Suspense } from "react";
import { GameReview, ReviewSkeleton } from "@/components/review/game-review";

export const metadata: Metadata = { title: "Разбор партии" };

export default function GamePage({ params, searchParams }: PageProps<"/games/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-5 sm:py-6">
      <Suspense fallback={<ReviewSkeleton />}>
        {Promise.all([params, searchParams]).then(([{ id }, query]) => (
          <GameReview key={id} id={id} autoAnalyze={query.analyze === "1"} />
        ))}
      </Suspense>
    </main>
  );
}
