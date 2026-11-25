import { Suspense } from "react";
import { CourseSkeleton, CourseView } from "@/components/courses/course-view";
import { DocumentTitle } from "@/components/document-title";

// Страница курса: дерево, идеи позиции, мастера, образцовые партии, «Тренировать» (сессия 13.7).
// `?node=N` — открыть курс сразу на узле N (ссылка из тренажёра).
export default function CoursePage({ params, searchParams }: PageProps<"/openings/courses/[id]">) {
  return (
    <>
      <DocumentTitle page="course" />
      <Suspense fallback={<CourseSkeleton />}>
        {Promise.all([params, searchParams]).then(([{ id }, query]) => (
          <CourseView key={id} id={id} initialNode={parseNode(query.node)} />
        ))}
      </Suspense>
    </>
  );
}

function parseNode(value: string | string[] | undefined): number | null {
  const node = Number(value);
  return typeof value === "string" && Number.isInteger(node) && node >= 0 ? node : null;
}
