import { DocumentTitle } from "@/components/document-title";

// Тренер (сессия 17): цель «с R на R'», диагностика против эталонов, план на день и неделю,
// прогноз срока. Фундамент: заглушка, реализация — 17.3.
export default function CoachPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="coach" />
    </main>
  );
}
