import { DocumentTitle } from "@/components/document-title";

// Слабые места (сессия 16.1): выводы по разобранным партиям → примеры → тренировка.
// Фундамент: заглушка, реализация — 16.1.
export default function WeaknessesPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="weaknesses" />
    </main>
  );
}
