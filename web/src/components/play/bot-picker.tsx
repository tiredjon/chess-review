"use client";

// Выбор бота: 25 рейтингов 400…2800, сгруппированных по уровням. Контракт для 14.3:
// `BotPicker` с `value`, `onChange`, `compact` (диалог партии по курсу).
import type { CSSProperties } from "react";
import { BOT_ELOS } from "@/lib/bots/types";
import type { Dict } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { PieceCode } from "@/lib/theme";
import { PieceImage } from "../board-theme";

export type BotPickerProps = {
  value: number;
  onChange: (elo: number) => void;
  /** Компактный вид (в диалоге курса), иначе — полный (страница /play). */
  compact?: boolean;
};

export type BotLevel = keyof Dict["play"]["levels"];

type LevelInfo = { key: BotLevel; max: number; piece: PieceCode; color: string };

// Верхняя граница рейтинга уровня, фигура на аватаре и цвет — как значки уровней Chess.com.
const LEVELS: LevelInfo[] = [
  { key: "beginner", max: 700, piece: "wP", color: "#7fa650" },
  { key: "amateur", max: 1100, piece: "wN", color: "#5d9bc9" },
  { key: "club", max: 1600, piece: "wB", color: "#9a6fc4" },
  { key: "strong", max: 2100, piece: "wR", color: "#e0913b" },
  { key: "master", max: 2400, piece: "wQ", color: "#d7564a" },
  { key: "grandmaster", max: Infinity, piece: "wK", color: "#c9a227" },
];

export const levelOf = (elo: number): LevelInfo => LEVELS.find((level) => elo <= level.max) ?? LEVELS[LEVELS.length - 1];

/** Аватар бота: фигура уровня на цветной плашке. */
export function BotAvatar({ elo, size = 40 }: { elo: number; size?: number }) {
  const level = levelOf(elo);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-md"
      style={{ width: size, height: size, background: level.color, padding: size * 0.1 }}
    >
      <PieceImage code={level.piece} style={{ filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.35))" }} />
    </span>
  );
}

export function BotPicker({ value, onChange, compact = false }: BotPickerProps) {
  const { t } = useI18n();
  const current = levelOf(value);

  if (compact) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2.5">
          <BotAvatar elo={value} size={36} />
          <p className="min-w-0 text-[15px]">
            <span className="font-extrabold">{t.play.botName(value)}</span>
            <span className="ml-1.5 font-semibold text-muted">{t.play.levels[current.key]}</span>
          </p>
        </div>
        <div role="radiogroup" aria-label={t.play.pickerLabel} className="grid grid-cols-5 gap-1.5">
          {BOT_ELOS.map((elo) => (
            <EloButton key={elo} elo={elo} active={elo === value} onSelect={onChange} compact />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div role="radiogroup" aria-label={t.play.pickerLabel} className="flex flex-col gap-4">
      {LEVELS.map((level, index) => {
        const min = index === 0 ? 0 : LEVELS[index - 1].max;
        const elos = BOT_ELOS.filter((elo) => elo > min && elo <= level.max);
        return (
          <div key={level.key} className="flex flex-col gap-2">
            <h3 className="flex items-center gap-2 text-sm font-bold text-soft">
              <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: level.color }} />
              {t.play.levels[level.key]}
              <span className="font-semibold text-muted">
                {elos[0]}–{elos[elos.length - 1]}
              </span>
            </h3>
            <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
              {elos.map((elo) => (
                <EloButton key={elo} elo={elo} active={elo === value} onSelect={onChange} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EloButton({
  elo,
  active,
  onSelect,
  compact = false,
}: {
  elo: number;
  active: boolean;
  onSelect: (elo: number) => void;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const level = levelOf(elo);
  const style = { "--level": level.color } as CSSProperties;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      aria-label={`${t.play.botName(elo)} — ${t.play.levels[level.key]}`}
      title={`${t.play.botName(elo)} — ${t.play.levels[level.key]}`}
      onClick={() => onSelect(elo)}
      style={style}
      className={`relative flex items-center justify-center gap-1.5 overflow-hidden rounded-lg font-extrabold tabular-nums transition-colors ${
        compact ? "min-h-10 text-sm" : "min-h-12 flex-col gap-0.5 text-base"
      } ${active ? "bg-raised text-ink ring-2 ring-green ring-inset" : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"}`}
    >
      <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-[var(--level)]" />
      {!compact && <BotAvatar elo={elo} size={22} />}
      {elo}
    </button>
  );
}
