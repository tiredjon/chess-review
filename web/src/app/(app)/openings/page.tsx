"use client";

import { DocumentTitle } from "@/components/document-title";
import { OpeningsPlaceholder } from "@/components/openings/openings-tabs";
import { useI18n } from "@/lib/i18n/use-i18n";

// Мой репертуар — сессия 13.5.
export default function RepertoirePage() {
  const { t } = useI18n();
  return (
    <>
      <DocumentTitle page="repertoire" />
      <OpeningsPlaceholder text={t.repertoire.placeholder} />
    </>
  );
}
