"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { LanguageSwitch } from "@/components/language-switch";
import { useI18n } from "@/lib/i18n/use-i18n";

/** Рамка страниц входа (как у Chess.com): логотип сверху, карточка по центру, язык гостя. */
export function AuthFrame({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/login" className="flex items-center gap-2 text-lg font-extrabold">
          <span aria-hidden className="text-[30px] leading-none text-green">
            ♞
          </span>
          {t.common.appName}
        </Link>
        <LanguageSwitch />
      </header>
      <main className="flex flex-1 flex-col items-center px-4 pt-6 pb-12 sm:justify-center sm:pt-0">
        <div className="w-full max-w-[420px]">{children}</div>
      </main>
    </div>
  );
}
