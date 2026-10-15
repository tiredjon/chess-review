import { HomeDashboard } from "@/components/home-dashboard";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-3 py-5 sm:px-6 sm:py-8">
      <h1 className="text-2xl font-extrabold sm:text-3xl">Разбор партий</h1>
      <HomeDashboard />
    </main>
  );
}
