import { DocumentTitle } from "@/components/document-title";

// Тренажёр эндшпиля (сессия 16.3): типовые эндшпили и позиции из своих партий против бота.
// Фундамент: заглушка, реализация — 16.3.
export default function EndgamesPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="endgames" />
    </main>
  );
}
