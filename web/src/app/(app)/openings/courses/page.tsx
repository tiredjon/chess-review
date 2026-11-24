"use client";

import { DocumentTitle } from "@/components/document-title";
import { OpeningsPlaceholder } from "@/components/openings/openings-tabs";
import { useI18n } from "@/lib/i18n/use-i18n";

// Каталог курсов и «Мои курсы» — сессия 13.7.
export default function CoursesPage() {
  const { t } = useI18n();
  return (
    <>
      <DocumentTitle page="courses" />
      <OpeningsPlaceholder text={t.courses.placeholder} />
    </>
  );
}
