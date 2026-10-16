"use client";

import { useEffect } from "react";
import type { Dict } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";

export type TitleKey = keyof Dict["common"]["titles"];

/** Заголовок вкладки на языке интерфейса (metadata страниц статична и одноязычна). */
export function DocumentTitle({ page }: { page: TitleKey }) {
  const { t } = useI18n();
  const title = `${t.common.titles[page]} — ${t.common.appName}`;
  useEffect(() => {
    document.title = title;
  }, [title]);
  return null;
}
