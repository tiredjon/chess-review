import { DocumentTitle } from "@/components/document-title";

// Урок тренера (сессия 17): текст по ключу из `lib/coach-lessons/`, позиции из своих партий,
// ссылка на тренировку. Фундамент: заглушка, реализация — 17.3 (тексты — 17.2).
export default function CoachLessonPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="coachLesson" />
    </main>
  );
}
