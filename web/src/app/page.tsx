export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Chess Review</h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-400">
        Разбор партий с Lichess, Chess.com и из PGN: точность, классификация
        ходов и объяснения ошибок.
      </p>
    </main>
  );
}
