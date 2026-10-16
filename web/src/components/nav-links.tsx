"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth, useUser } from "@/components/auth/auth-provider";
import { LogoutIcon } from "@/components/auth/profile-form";
import type { Dict } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";

type NavKey = keyof Pick<Dict["common"]["nav"], "home" | "games" | "stats" | "puzzles">;

const NAV: { href: string; key: NavKey; icon: ReactNode }[] = [
  {
    href: "/",
    key: "home",
    icon: <path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-5.5h-5V21H5a1 1 0 0 1-1-1z" />,
  },
  {
    href: "/games",
    key: "games",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="2" fill="none" strokeWidth="2" stroke="currentColor" />
        <path d="M4 4h4v4H4zM12 4h4v4h-4zM8 8h4v4H8zM16 8h4v4h-4zM4 12h4v4H4zM12 12h4v4h-4zM8 16h4v4H8zM16 16h4v4h-4z" />
      </>
    ),
  },
  {
    href: "/stats",
    key: "stats",
    icon: <path d="M4 20h16v-2H4zM5 16h3v-5H5zM10.5 16h3V5h-3zM16 16h3V9h-3z" />,
  },
  {
    href: "/puzzles",
    key: "puzzles",
    // Кусочек пазла.
    icon: (
      <path d="M10 3.5a2 2 0 0 1 4 0V5h4a1 1 0 0 1 1 1v4h-1.5a2 2 0 0 0 0 4H19v4a1 1 0 0 1-1 1h-4v-1.5a2 2 0 0 0-4 0V19H6a1 1 0 0 1-1-1v-4h1.5a2 2 0 0 0 0-4H5V6a1 1 0 0 1 1-1h4z" />
    ),
  },
];

const isActive = (href: string, pathname: string | null) =>
  pathname !== null && (href === "/" ? pathname === "/" : pathname.startsWith(href));

const itemClass = (active: boolean) =>
  `flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-semibold sm:px-3 md:w-[60px] md:flex-col md:gap-1 md:px-0 md:py-2 md:text-[11px] ${
    active ? "bg-raised text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
  }`;

export function HomeLink() {
  const { t } = useI18n();
  return (
    <Link
      href="/"
      aria-label={t.common.nav.toHome}
      className="flex h-11 w-10 shrink-0 items-center justify-center rounded-lg text-[30px] leading-none text-green sm:w-11 md:mb-3"
    >
      <span aria-hidden>♞</span>
    </Link>
  );
}

function CurrentNavLinks() {
  return <Links pathname={usePathname()} />;
}

/** Без `pathname` берёт его из URL; `null` — без активного пункта (fallback). */
export function NavLinks({ pathname }: { pathname?: string | null }) {
  if (pathname === undefined) return <CurrentNavLinks />;
  return <Links pathname={pathname} />;
}

function Links({ pathname }: { pathname: string | null }) {
  const { t } = useI18n();
  return (
    <nav aria-label={t.common.nav.label} className="flex gap-0.5 sm:gap-1 md:flex-col md:gap-2">
      {NAV.map(({ href, key, icon }) => {
        const active = isActive(href, pathname);
        const label = t.common.nav[key];
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} title={label} className={itemClass(active)}>
            <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6 fill-current">
              {icon}
            </svg>
            {/* На телефоне — только значки: подписи не помещаются в полосу. */}
            <span className="max-sm:sr-only">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function CurrentUserLinks() {
  return <UserLinksAt pathname={usePathname()} />;
}

/** Профиль (буква email) и выход: внизу колонки, на телефоне — справа в полосе. */
export function UserLinks({ pathname }: { pathname?: string | null }) {
  if (pathname === undefined) return <CurrentUserLinks />;
  return <UserLinksAt pathname={pathname} />;
}

function UserLinksAt({ pathname }: { pathname: string | null }) {
  const user = useUser();
  const { logout } = useAuth();
  const { t } = useI18n();
  const active = isActive("/profile", pathname);
  return (
    <div className="ml-auto flex items-center gap-0.5 md:mt-auto md:ml-0 md:flex-col md:gap-2">
      <Link
        href="/profile"
        aria-current={active ? "page" : undefined}
        title={`${t.common.nav.profile}: ${user.email}`}
        className={itemClass(active)}
      >
        <span
          aria-hidden
          className="flex h-6 w-6 items-center justify-center rounded-md bg-green text-[13px] font-extrabold text-white"
        >
          {user.email.charAt(0).toUpperCase()}
        </span>
        <span className="max-md:sr-only">{t.common.nav.profile}</span>
      </Link>
      {/* На телефоне выход — на странице профиля: в полосе нет места. */}
      <button
        type="button"
        onClick={() => void logout().catch(() => undefined)}
        title={t.common.nav.logout}
        className={`${itemClass(false)} max-md:hidden`}
      >
        <LogoutIcon className="h-6 w-6" />
        <span>{t.common.nav.logout}</span>
      </button>
    </div>
  );
}
