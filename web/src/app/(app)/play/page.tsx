import { DocumentTitle } from "@/components/document-title";

// Игра с ботами Stockfish 400…2800 (сессия 14.2). Заглушка фундамента.
export default function PlayPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="play" />
      <p className="rounded-xl bg-panel p-6 text-muted">Игра с ботами — скоро.</p>
    </main>
  );
}
