import type { Ply } from "./chess";
import type { Dict } from "./i18n";
import type { Color, GameClock } from "./types";

/** Остаток на часах: `2:57`, `1:02:05`; меньше 10 секунд — с десятыми, `0:09.8`. */
export function formatClock(cs: number): string {
  const total = Math.max(0, cs) / 100;
  if (total < 10) return `0:0${total.toFixed(1)}`;
  const seconds = Math.floor(total);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** Потрачено на ход: `0.4 с`, `12 с`, `2:05`. */
export function formatSpent(cs: number, t: Dict): string {
  const seconds = Math.max(0, cs) / 100;
  if (seconds < 10) return t.common.time.seconds(seconds.toFixed(1));
  if (seconds < 60) return t.common.time.seconds(Math.round(seconds));
  return formatClock(cs);
}

/** Остаток у `color` в позиции после `cursor` полуходов: после его последнего хода, иначе база. */
export function clockAt(clock: GameClock, plies: Ply[], cursor: number, color: Color): number | null {
  for (let index = Math.min(cursor, plies.length) - 1; index >= 0; index--) {
    if (plies[index].color === color) return clock.plies[index]?.clock_cs ?? null;
  }
  return clock.base_cs;
}
