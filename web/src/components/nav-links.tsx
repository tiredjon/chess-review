"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Импорт" },
  { href: "/games", label: "Партии" },
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
    <nav className="flex gap-1 text-sm">
      {NAV.map(({ href, label }) => {
        const active =
          pathname !== null && (href === "/" ? pathname === "/" : pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 ${
              active ? "bg-sunken font-medium text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
