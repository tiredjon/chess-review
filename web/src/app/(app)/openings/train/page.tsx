"use client";

import { DocumentTitle } from "@/components/document-title";
import { OpeningsPlaceholder } from "@/components/openings/openings-tabs";
import { useI18n } from "@/lib/i18n/use-i18n";

// Тренажёр: очередь повторения по всем курсам — сессия 13.7.
export default function TrainerPage() {
  const { t } = useI18n();
  return (
    <>
      <DocumentTitle page="trainer" />
      <OpeningsPlaceholder text={t.trainer.placeholder} />
    </>
  );
}
