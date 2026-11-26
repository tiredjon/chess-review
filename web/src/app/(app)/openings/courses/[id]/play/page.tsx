import { DocumentTitle } from "@/components/document-title";

// Партия с ботом по линии курса (сессия 14.3). Заглушка фундамента.
export default function CoursePlayPage() {
  return (
    <>
      <DocumentTitle page="coursePlay" />
      <p className="rounded-xl bg-panel p-6 text-muted">Партия по курсу — скоро.</p>
    </>
  );
}
