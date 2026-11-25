import { Suspense } from "react";
import { TrainerSkeleton, TrainerView } from "@/components/courses/trainer-view";
import { DocumentTitle } from "@/components/document-title";

// Тренажёр дебютов (сессия 13.7): общая очередь по всем курсам; `?course=<id>` — один курс.
export default function TrainerPage({ searchParams }: PageProps<"/openings/train">) {
  return (
    <>
      <DocumentTitle page="trainer" />
      <Suspense fallback={<TrainerSkeleton />}>
        {searchParams.then((query) => {
          const course = typeof query.course === "string" && query.course ? query.course : null;
          return <TrainerView key={course ?? "all"} courseId={course} />;
        })}
      </Suspense>
    </>
  );
}
