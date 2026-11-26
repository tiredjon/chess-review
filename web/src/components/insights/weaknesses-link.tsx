"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/use-i18n";

/** Ссылка на «Слабые места» из /stats (с теми же фильтрами). */
export function WeaknessesLink({ query }: { query: string }) {
  const { t } = useI18n();
  return (
    <Link
      href={query ? `/stats/weaknesses?${query}` : "/stats/weaknesses"}
      className="group flex items-center gap-3 rounded-xl bg-panel px-4 py-3 hover:bg-raised sm:px-5"
    >
      <WeaknessIcon />
      <span className="min-w-0 flex-1">
        <span className="block font-extrabold">{t.insights.link.title}</span>
        <span className="block text-sm font-semibold text-muted group-hover:text-soft">{t.insights.link.text}</span>
      </span>
      <span aria-hidden className="text-xl font-bold text-muted group-hover:text-ink">
        →
      </span>
    </Link>
  );
}

/** Значок «прицел»: слабое место, в которое целится тренировка. */
export function WeaknessIcon() {
  return (
    <span aria-hidden className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-raised text-[#f59a4c]">
      <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" />
        <path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" />
      </svg>
    </span>
  );
}
