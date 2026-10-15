"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV: { href: string; label: string; icon: ReactNode }[] = [
  {
    href: "/",
    label: "Главная",
    icon: (
      <path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-5.5h-5V21H5a1 1 0 0 1-1-1z" />
    ),
  },
  {
    href: "/games",
    label: "Партии",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="2" fill="none" strokeWidth="2" stroke="currentColor" />
        <path d="M4 4h4v4H4zM12 4h4v4h-4zM8 8h4v4H8zM16 8h4v4h-4zM4 12h4v4H4zM12 12h4v4h-4zM8 16h4v4H8zM16 16h4v4h-4z" />
      </>
    ),
  },
];

function CurrentNavLinks() {
  return <Links pathname={usePathname()} />;
}

/** Без `pathname` берёт его из URL; `null` — без активного пункта (fallback). */
export function NavLinks({ pathname }: { pathname?: string | null }) {
  if (pathname === undefined) return <CurrentNavLinks />;
  return <Links pathname={pathname} />;
}

function Links({ pathname }: { pathname: string | null }) {
  return (
    <nav className="flex gap-1 md:flex-col md:gap-2">
      {NAV.map(({ href, label, icon }) => {
        const active = pathname !== null && (href === "/" ? pathname === "/" : pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold md:w-[60px] md:flex-col md:gap-1 md:px-0 md:py-2 md:text-[11px] ${
              active ? "bg-raised text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
            }`}
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6 fill-current">
              {icon}
            </svg>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
