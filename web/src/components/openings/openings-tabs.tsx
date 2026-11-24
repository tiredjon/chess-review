"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useI18n } from "@/lib/i18n/use-i18n";

// Вкладки раздела «Дебюты» (сессия 13): репертуар — /openings, курсы — /openings/courses
// (и страница курса), тренажёр — /openings/train.
const TABS = [
  { href: "/openings", key: "repertoire" },
  { href: "/openings/courses", key: "courses" },
  { href: "/openings/train", key: "trainer" },
] as const;

const isActive = (href: string, pathname: string | null) =>
  pathname !== null && (href === "/openings" ? pathname === "/openings" : pathname.startsWith(href));

export function OpeningsTabs() {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <nav aria-label={t.openings.tabs.label} className="mb-3 flex gap-1 overflow-x-auto">
      {TABS.map(({ href, key }) => {
        const active = isActive(href, pathname);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`shrink-0 rounded-lg px-3 py-2 text-sm font-semibold ${
              active ? "bg-raised text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
            }`}
          >
            {t.openings.tabs[key]}
          </Link>
        );
      })}
    </nav>
  );
}

/** Заглушка части раздела, которую ещё не сделали. */
export function OpeningsPlaceholder({ text }: { text: string }) {
  return <p className="rounded-xl bg-panel p-6 text-muted">{text}</p>;
}
