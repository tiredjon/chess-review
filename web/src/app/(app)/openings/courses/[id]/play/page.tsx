import { Suspense } from "react";
import { CourseSkeleton } from "@/components/courses/course-view";
import { CoursePlayView, type LineChoice } from "@/components/courses/play-view";
import { DocumentTitle } from "@/components/document-title";

// Партия с ботом по линии курса (сессия 14.3): выбор линии и бота → партия → итог.
// `?node=N` — предвыбрать линию через узел N (кнопка со страницы курса или из тренажёра);
// `?line=N` — вариант N (с 1, как «Вариант N из M»), `?line=random` — случайная линия.
export default function CoursePlayPage({ params, searchParams }: PageProps<"/openings/courses/[id]/play">) {
  return (
    <>
      <DocumentTitle page="coursePlay" />
      <Suspense fallback={<CourseSkeleton />}>
        {Promise.all([params, searchParams]).then(([{ id }, query]) => (
          <CoursePlayView key={id} id={id} initialNode={parseIndex(query.node, 0)} initialLine={parseLine(query.line)} />
        ))}
      </Suspense>
    </>
  );
}

function parseIndex(value: string | string[] | undefined, min: number): number | null {
  const n = Number(value);
  return typeof value === "string" && value !== "" && Number.isInteger(n) && n >= min ? n : null;
}

function parseLine(value: string | string[] | undefined): LineChoice | null {
  if (value === "random") return "random";
  const n = parseIndex(value, 1);
  return n === null ? null : n - 1;
}
