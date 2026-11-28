// Контроль времени в партии с ботом: пресеты, формат часов, комментарии %clk для PGN.
import type { Color } from "@/lib/types";

/** Контроль времени: база и добавка за ход (Фишер), секунды. */
export type TimeControl = { initial: number; increment: number };

export type TimeClass = "bullet" | "blitz" | "rapid" | "classical";

/** Пресеты выбора на /play; id — «минуты+добавка», как принято на сайтах. */
export const TIME_PRESETS: readonly { id: string; control: TimeControl; group: TimeClass }[] = [
  { id: "1+0", control: { initial: 60, increment: 0 }, group: "bullet" },
  { id: "2+1", control: { initial: 120, increment: 1 }, group: "bullet" },
  { id: "3+0", control: { initial: 180, increment: 0 }, group: "blitz" },
  { id: "3+2", control: { initial: 180, increment: 2 }, group: "blitz" },
  { id: "5+0", control: { initial: 300, increment: 0 }, group: "blitz" },
  { id: "5+3", control: { initial: 300, increment: 3 }, group: "blitz" },
  { id: "10+0", control: { initial: 600, increment: 0 }, group: "rapid" },
  { id: "10+5", control: { initial: 600, increment: 5 }, group: "rapid" },
  { id: "15+10", control: { initial: 900, increment: 10 }, group: "rapid" },
  { id: "30+0", control: { initial: 1800, increment: 0 }, group: "classical" },
  { id: "30+20", control: { initial: 1800, increment: 20 }, group: "classical" },
];

/** Без часов — как до появления контроля времени. */
export const NO_CLOCK = "none";

export const presetControl = (id: string): TimeControl | null => TIME_PRESETS.find((preset) => preset.id === id)?.control ?? null;

export const isValidControl = (value: unknown): value is TimeControl =>
  typeof value === "object" &&
  value !== null &&
  Number.isFinite((value as TimeControl).initial) &&
  (value as TimeControl).initial > 0 &&
  Number.isFinite((value as TimeControl).increment) &&
  (value as TimeControl).increment >= 0;

/** Заголовок PGN TimeControl: «180+2». */
export const pgnTimeControl = (control: TimeControl) => `${control.initial}+${control.increment}`;

/** Часы на экране: «4:59», меньше 20 секунд — с десятыми «0:09.4», от часа — «1:00:00». */
export function formatClock(ms: number): string {
  const clamped = Math.max(0, ms);
  if (clamped < 20_000) {
    const tenths = Math.floor(clamped / 100);
    return `0:${String(Math.floor(tenths / 10)).padStart(2, "0")}.${tenths % 10}`;
  }
  const total = Math.floor(clamped / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

/** Комментарий PGN с остатком на часах после хода: «[%clk 0:02:55.4]». */
export function clkComment(ms: number): string {
  const tenths = Math.max(0, Math.floor(ms / 100));
  const seconds = Math.floor(tenths / 10);
  const hh = Math.floor(seconds / 3600);
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `[%clk ${hh}:${mm}:${ss}.${tenths % 10}]`;
}

/** Остаток на часах обеих сторон. `turnStart` — когда пошли часы ходящего (Date.now), null — стоят. */
export type ClockState = { white: number; black: number; turnStart: number | null };

/** Остаток стороны на момент `now`: у ходящего вычитается время с начала его хода. */
export function remainingAt(clock: ClockState, side: Color, turn: Color, now: number): number {
  const base = clock[side];
  return side === turn && clock.turnStart !== null ? base - (now - clock.turnStart) : base;
}
