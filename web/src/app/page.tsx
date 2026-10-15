import { ImportForm } from "@/components/import-form";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10 sm:py-14">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Разбор партии</h1>
        <p className="mt-3 text-base leading-relaxed text-muted sm:text-lg">
          Stockfish оценит каждый ход, найдёт ошибки и покажет, что было лучше и почему.
        </p>
      </div>
      <ImportForm />
    </main>
  );
}
