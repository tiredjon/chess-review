import { DocumentTitle } from "@/components/document-title";
import { PuzzleTrainer } from "@/components/puzzles/puzzle-trainer";

export default function PuzzlesPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="puzzles" />
      <PuzzleTrainer />
    </main>
  );
}
