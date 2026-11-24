import type { ReactNode } from "react";
import { OpeningsTabs } from "@/components/openings/openings-tabs";

/** Раздел «Дебюты» (сессия 13): вкладки репертуар / курсы / тренажёр над содержимым. */
export default function OpeningsLayout({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <OpeningsTabs />
      {children}
    </main>
  );
}
