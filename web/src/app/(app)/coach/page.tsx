import { CoachHeading, CoachView } from "@/components/coach/coach-view";
import { DocumentTitle } from "@/components/document-title";

// Тренер (сессия 17): цель «с R на R'», диагностика против эталонов, план на день и неделю,
// прогноз срока. Данные — `components/coach/source.ts` (настоящий API или моки по флагу).
export default function CoachPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <DocumentTitle page="coach" />
      <CoachHeading />
      <CoachView />
    </main>
  );
}
