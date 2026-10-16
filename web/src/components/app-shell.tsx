import { Suspense, type ReactNode } from "react";
import { HomeLink, NavLinks, UserLinks } from "./nav-links";

/** Узкая колонка навигации слева (на телефоне — полоса сверху) и содержимое. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-1 border-b border-line bg-sunken px-2 sm:gap-2 sm:px-3 md:h-dvh md:w-[72px] md:flex-col md:gap-1 md:border-r md:border-b-0 md:px-0 md:py-3">
        <HomeLink />
        {/* Активный пункт зависит от URL — он известен только при запросе. */}
        <Suspense fallback={<NavLinks pathname={null} />}>
          <NavLinks />
        </Suspense>
        <Suspense fallback={<UserLinks pathname={null} />}>
          <UserLinks />
        </Suspense>
      </header>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
