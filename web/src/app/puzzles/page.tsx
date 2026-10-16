import type { Metadata } from "next";
import { PuzzleTrainer } from "@/components/puzzles/puzzle-trainer";

export const metadata: Metadata = { title: "Пазлы" };

export default function PuzzlesPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <h1 className="sr-only">Пазлы из ваших ошибок</h1>
      <PuzzleTrainer />
    </main>
  );
}
