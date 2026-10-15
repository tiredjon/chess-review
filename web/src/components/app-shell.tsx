import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { NavLinks } from "./nav-links";

/** Узкая колонка навигации слева (на телефоне — полоса сверху) и содержимое. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-sunken px-3 md:h-dvh md:w-[72px] md:flex-col md:gap-1 md:border-r md:border-b-0 md:px-0 md:py-3">
        <Link
          href="/"
          aria-label="Chess Review — на главную"
          className="flex h-11 w-11 items-center justify-center rounded-lg text-[30px] leading-none text-green md:mb-3"
        >
          <span aria-hidden>♞</span>
        </Link>
        {/* Активный пункт зависит от URL — он известен только при запросе. */}
        <Suspense fallback={<NavLinks pathname={null} />}>
          <NavLinks />
        </Suspense>
      </header>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
