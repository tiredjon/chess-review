import Link from "next/link";
import { Suspense } from "react";
import { NavLinks } from "./nav-links";

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-2 text-[17px] font-semibold tracking-tight">
          <span aria-hidden className="text-2xl leading-none text-accent">
            ♞
          </span>
          Chess Review
        </Link>
        {/* Активный пункт зависит от URL — он известен только при запросе. */}
        <Suspense fallback={<NavLinks pathname={null} />}>
          <NavLinks />
        </Suspense>
      </div>
    </header>
  );
}
