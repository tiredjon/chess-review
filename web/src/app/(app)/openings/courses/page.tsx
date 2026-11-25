"use client";

import { Catalog } from "@/components/courses/catalog";
import { MyCourses } from "@/components/courses/my-courses";
import { DocumentTitle } from "@/components/document-title";
import { useI18n } from "@/lib/i18n/use-i18n";

// Каталог курсов и «Мои курсы» (сессия 13.7).
export default function CoursesPage() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-3">
      <DocumentTitle page="courses" />
      <h1 className="sr-only">{t.courses.title}</h1>
      <MyCourses />
      <Catalog />
    </div>
  );
}
