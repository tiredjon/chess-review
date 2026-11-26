import { Suspense } from "react";
import { DocumentTitle } from "@/components/document-title";
import { EndgamesScreen, type EndgamesQuery } from "@/components/endgames/endgames-screen";

// Тренажёр эндшпиля (сессия 16.3): типовые эндшпили и позиции из своих партий против бота.
// `?tab=catalog|mine`, `&id=` — позиция каталога, `&key=` — позиция из партии (id хода).
export default function EndgamesPage({ searchParams }: PageProps<"/play/endgames">) {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
      <DocumentTitle page="endgames" />
      <Suspense fallback={null}>
        {searchParams.then((params) => {
          const value = (name: string) => (typeof params[name] === "string" && params[name] ? (params[name] as string) : null);
          const query: EndgamesQuery = {
            tab: value("tab") === "mine" ? "mine" : "catalog",
            id: value("id"),
            key: value("key"),
          };
          return <EndgamesScreen key={`${query.tab}:${query.id ?? ""}:${query.key ?? ""}`} query={query} />;
        })}
      </Suspense>
    </main>
  );
}
