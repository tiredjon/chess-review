"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/use-i18n";
import { CoachIcon } from "./coach-card";

/** Ссылка на тренера (с /stats/weaknesses): слабые места ведут в план. */
export function CoachLink() {
  const { t } = useI18n();
  return (
    <Link href="/coach" className="group flex items-center gap-3 rounded-xl bg-panel px-4 py-3 hover:bg-raised sm:px-5">
      <CoachIcon />
      <span className="min-w-0 flex-1">
        <span className="block font-extrabold">{t.coach.link.title}</span>
        <span className="block text-sm font-semibold text-muted group-hover:text-soft">{t.coach.link.text}</span>
      </span>
      <span aria-hidden className="text-xl font-bold text-muted group-hover:text-ink">
        →
      </span>
    </Link>
  );
}
