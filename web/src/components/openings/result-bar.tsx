import { useI18n } from "@/lib/i18n/use-i18n";

/** Очки в процентах: победа — 1, ничья — ½. */
export const scorePercent = (w: number, d: number, l: number) => {
  const games = w + d + l;
  return games === 0 ? 0 : Math.round(((w + d / 2) / games) * 100);
};

/** Полоска побед / ничьих / поражений (с точки зрения пользователя). */
export function ResultBar({ wins, draws, losses, className = "" }: { wins: number; draws: number; losses: number; className?: string }) {
  const { t } = useI18n();
  const games = wins + draws + losses;
  if (games === 0) return null;
  return (
    <div
      role="img"
      aria-label={t.repertoire.list.resultBar(wins, draws, losses)}
      className={`flex h-1.5 overflow-hidden rounded-full bg-sunken ${className}`}
    >
      <span className="bg-green" style={{ width: `${(wins / games) * 100}%` }} />
      <span className="bg-muted" style={{ width: `${(draws / games) * 100}%` }} />
      <span className="bg-danger" style={{ width: `${(losses / games) * 100}%` }} />
    </div>
  );
}
