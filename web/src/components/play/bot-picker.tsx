"use client";

// ЗАГЛУШКА фундамента сессии 14 — настоящий выбор бота (карточки 400…2800) делает 14.2.
// Экспорт `BotPicker` и его props — контракт для 14.3 (выбор бота в партии по курсу).
import { BOT_ELOS } from "@/lib/bots/types";

export type BotPickerProps = {
  value: number;
  onChange: (elo: number) => void;
  /** Компактный вид (в диалоге курса), иначе — полный (страница /play). */
  compact?: boolean;
};

export function BotPicker({ value, onChange }: BotPickerProps) {
  return (
    <select value={value} onChange={(event) => onChange(Number(event.target.value))} className="rounded-lg bg-raised px-3 py-2">
      {BOT_ELOS.map((elo) => (
        <option key={elo} value={elo}>
          Stockfish {elo}
        </option>
      ))}
    </select>
  );
}
