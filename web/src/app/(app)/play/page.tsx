import { DocumentTitle } from "@/components/document-title";
import { PlayScreen } from "@/components/play/play-screen";

// Игра с ботами Stockfish 400…2800 (сессия 14.2): выбор бота и цвета → партия.
export default function PlayPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="play" />
      <PlayScreen />
    </main>
  );
}
