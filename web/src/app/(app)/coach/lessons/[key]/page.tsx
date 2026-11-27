import { LessonView } from "@/components/coach/lesson-view";
import { DocumentTitle } from "@/components/document-title";

// Урок тренера (сессия 17): текст по ключу из `lib/coach-lessons/`, позиции из своих партий,
// «Тренировать» и «Прочитано».
export default async function CoachLessonPage({ params }: PageProps<"/coach/lessons/[key]">) {
  const { key } = await params;
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <DocumentTitle page="coachLesson" />
      <LessonView lessonKey={decodeURIComponent(key)} />
    </main>
  );
}
