"use client";

import { DocumentTitle } from "@/components/document-title";
import { OpeningsPlaceholder } from "@/components/openings/openings-tabs";
import { useI18n } from "@/lib/i18n/use-i18n";

// Страница курса: изучение дерева, планы, партии мастеров, тренировка — сессия 13.7.
export default function CoursePage() {
  const { t } = useI18n();
  return (
    <>
      <DocumentTitle page="course" />
      <OpeningsPlaceholder text={t.courses.placeholder} />
    </>
  );
}
