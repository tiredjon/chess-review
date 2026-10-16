import Link from "next/link";
import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { LanguageSwitch } from "@/components/language-switch";
import { ReviewSkeleton } from "@/components/review/game-review";
import { SharedReview } from "@/components/review/shared-review";
import { SharedCta } from "@/components/review/shared-cta";

/** Публичный разбор по ссылке: без входа и навигации приложения. */
export default function SharedPage({ params, searchParams }: PageProps<"/share/[token]">) {
  return (
    <div className="flex min-h-dvh flex-col">
      <DocumentTitle page="shared" />
      <header className="flex items-center justify-between gap-3 px-3 py-2.5 sm:px-5">
        <Link href="/" className="flex items-center gap-2 text-lg font-extrabold">
          <span aria-hidden className="text-[30px] leading-none text-green">
            ♞
          </span>
          <span className="max-sm:sr-only">Chess Review</span>
        </Link>
        <div className="flex items-center gap-3">
          <SharedCta />
          <LanguageSwitch />
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 pb-3 sm:px-5 sm:pb-4">
        <Suspense fallback={<ReviewSkeleton />}>
          {Promise.all([params, searchParams]).then(([{ token }, query]) => (
            <SharedReview key={token} token={token} initialPly={parsePly(query.ply)} />
          ))}
        </Suspense>
      </main>
    </div>
  );
}

/** `?ply=N` — открыть разбор на N-м полуходе (ссылки на ошибки из бота). */
function parsePly(value: string | string[] | undefined): number {
  const ply = Number(value);
  return Number.isInteger(ply) && ply > 0 ? ply : 0;
}
