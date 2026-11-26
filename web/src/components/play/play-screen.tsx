"use client";

// Страница /play: выбор бота и цвета → партия; «Новая партия» и «Другой бот».
// Последний выбор — в localStorage, идущая партия — в sessionStorage (переживает перезагрузку).
import { useState } from "react";
import { BOT_ELOS } from "@/lib/bots/types";
import { START_FEN } from "@/lib/chess";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { PieceCode } from "@/lib/theme";
import type { Color } from "@/lib/types";
import { PieceImage } from "../board-theme";
import { Board, NO_MARKS } from "../review/board";
import { Button } from "../ui";
import { BotAvatar, BotPicker, levelOf } from "./bot-picker";
import { BotGame } from "./bot-game";

type ColorChoice = Color | "random";
type Setup = { elo: number; color: ColorChoice };
type Active = { id: string; elo: number; color: Color };

const SETUP_KEY = "chess-review:play:setup";
const ACTIVE_KEY = "chess-review:play:active";
const DEFAULT_SETUP: Setup = { elo: 1200, color: "white" };
const BOARD_WIDTH = { maxWidth: "min(100%, calc(100dvh - 8.5rem))" };

function readSetup(): Setup {
  try {
    const saved = JSON.parse(localStorage.getItem(SETUP_KEY) ?? "null") as Partial<Setup> | null;
    return {
      elo: saved && BOT_ELOS.includes(saved.elo as number) ? (saved.elo as number) : DEFAULT_SETUP.elo,
      color: saved?.color === "black" || saved?.color === "random" ? saved.color : "white",
    };
  } catch {
    return DEFAULT_SETUP;
  }
}

function readActive(): Active | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(ACTIVE_KEY) ?? "null") as Active | null;
    if (!saved || typeof saved.id !== "string" || !BOT_ELOS.includes(saved.elo)) return null;
    if (saved.color !== "white" && saved.color !== "black") return null;
    return saved;
  } catch {
    return null;
  }
}

function store(storage: () => Storage, key: string, value: unknown) {
  try {
    if (value === null) storage().removeItem(key);
    else storage().setItem(key, JSON.stringify(value));
  } catch {
    // Хранилище недоступно — выбор живёт до перезагрузки.
  }
}

export function PlayScreen() {
  const { t } = useI18n();
  const [setup, setSetup] = useState<Setup>(readSetup);
  const [active, setActive] = useState<Active | null>(readActive);

  const updateSetup = (next: Setup) => {
    setSetup(next);
    store(() => localStorage, SETUP_KEY, next);
  };

  const start = (choice: Setup) => {
    const color: Color = choice.color === "random" ? (Math.random() < 0.5 ? "white" : "black") : choice.color;
    const next = { id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, elo: choice.elo, color };
    setActive(next);
    store(() => sessionStorage, ACTIVE_KEY, next);
    window.scrollTo({ top: 0 });
  };

  const toSetup = () => {
    setActive(null);
    store(() => sessionStorage, ACTIVE_KEY, null);
  };

  if (active) {
    return (
      <>
        <h1 className="sr-only">{t.play.title}</h1>
        <BotGame
          key={active.id}
          elo={active.elo}
          color={active.color}
          storageKey={`play:${active.id}`}
          // Закончилась — после перезагрузки снова экран выбора, а не пустая партия.
          onFinished={() => store(() => sessionStorage, ACTIVE_KEY, null)}
          onNewGame={() => start({ ...setup, elo: active.elo })}
          onChangeBot={toSetup}
        />
      </>
    );
  }

  const preview: Color = setup.color === "black" ? "black" : "white";
  const level = levelOf(setup.elo);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="mx-auto w-full max-lg:hidden" style={BOARD_WIDTH}>
        <Board fen={START_FEN} orientation={preview} marks={NO_MARKS} />
      </div>

      <section className="flex min-w-0 flex-col rounded-xl bg-panel lg:h-0 lg:min-h-[max(100%,calc(100dvh-2rem))]">
        <header className="rounded-t-xl border-b border-line bg-sunken/60 px-4 py-3">
          <h1 className="text-lg font-extrabold">{t.play.setup.heading}</h1>
          <p className="text-xs font-semibold text-muted">{t.play.setup.subtitle}</p>
        </header>

        <div className="flex items-center gap-3 border-b border-line px-4 py-4">
          <BotAvatar elo={setup.elo} size={56} />
          <div className="min-w-0">
            <p className="text-xl font-extrabold">{t.play.botName(setup.elo)}</p>
            <p className="text-sm font-semibold" style={{ color: level.color }}>
              {t.play.levels[level.key]}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 p-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          <h2 className="text-sm font-bold text-soft">{t.play.setup.bot}</h2>
          <BotPicker value={setup.elo} onChange={(elo) => updateSetup({ ...setup, elo })} />
        </div>

        <div className="sticky bottom-0 flex flex-col gap-3 rounded-b-xl border-t border-line bg-panel p-4 lg:static">
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-bold text-soft">{t.play.setup.color}</h2>
            <div role="radiogroup" aria-label={t.play.setup.color} className="grid grid-cols-3 gap-2">
              {(["white", "random", "black"] as const).map((choice) => (
                <ColorButton
                  key={choice}
                  choice={choice}
                  label={t.play.setup.colors[choice]}
                  active={setup.color === choice}
                  onSelect={() => updateSetup({ ...setup, color: choice })}
                />
              ))}
            </div>
          </div>
          <Button size="lg" onClick={() => start(setup)}>
            {t.play.setup.start}
          </Button>
        </div>
      </section>
    </div>
  );
}

function ColorButton({
  choice,
  label,
  active,
  onSelect,
}: {
  choice: ColorChoice;
  label: string;
  active: boolean;
  onSelect: () => void;
}) {
  const king: PieceCode | null = choice === "white" ? "wK" : choice === "black" ? "bK" : null;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onSelect}
      className={`flex min-h-16 flex-col items-center justify-center gap-1 rounded-lg text-xs font-bold ${
        active ? "bg-raised text-ink ring-2 ring-green ring-inset" : "bg-raised/60 text-soft hover:bg-raised hover:text-ink"
      }`}
    >
      <span className="relative h-8 w-8">
        {king ? (
          <PieceImage code={king} />
        ) : (
          <>
            <span className="absolute inset-0 [clip-path:inset(0_50%_0_0)]">
              <PieceImage code="wK" />
            </span>
            <span className="absolute inset-0 [clip-path:inset(0_0_0_50%)]">
              <PieceImage code="bK" />
            </span>
          </>
        )}
      </span>
      {label}
    </button>
  );
}
