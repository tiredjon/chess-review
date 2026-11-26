"use client";

// Части партии с ботом: полоса игрока, список ходов, выбор превращения, итог партии.
import { useEffect, useRef, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n/use-i18n";
import type { PieceCode } from "@/lib/theme";
import type { Color } from "@/lib/types";
import { PieceImage } from "../board-theme";
import { PlayerAvatar } from "../player-avatar";
import { Button } from "../ui";
import { BotAvatar } from "./bot-picker";
import type { PieceKind } from "./game";
import type { GameResult } from "./types";

/** Полоса над / под доской: аватар, имя, взятые фигуры и перевес; у бота — «думает…». */
export function PlayerBar({
  name,
  elo,
  color,
  captured,
  advantage,
  status,
}: {
  name: string;
  /** Рейтинг бота; у человека — нет. */
  elo?: number;
  color: Color;
  captured: PieceKind[];
  advantage: number;
  status?: ReactNode;
}) {
  // Взятые фигуры — соперника: у белых чёрные и наоборот.
  const prefix = color === "white" ? "b" : "w";
  return (
    <div className="flex min-h-10 items-center gap-2.5">
      {elo !== undefined ? <BotAvatar elo={elo} size={36} /> : <PlayerAvatar name={name} color={color} size={36} />}
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <p className="truncate text-[15px] leading-tight">
          <span className="font-bold">{name}</span>
          {elo !== undefined && <span className="ml-1.5 font-semibold text-muted">({elo})</span>}
        </p>
        <div className="flex h-[18px] items-center">
          {captured.map((kind, index) => (
            <span
              key={index}
              className={`h-[18px] w-[18px] shrink-0 ${index > 0 && captured[index - 1] === kind ? "-ml-[11px]" : index > 0 ? "-ml-1" : ""}`}
            >
              <PieceImage code={`${prefix}${kind.toUpperCase()}` as PieceCode} />
            </span>
          ))}
          {advantage > 0 && <span className="ml-1 text-xs font-bold text-muted">+{advantage}</span>}
        </div>
      </div>
      {status}
    </div>
  );
}

/** «думает…» — три точки, как индикатор хода соперника. */
export function Thinking({ label }: { label: string }) {
  return (
    <span aria-live="polite" className="flex items-center gap-1.5 rounded-md bg-raised px-2.5 py-1 text-xs font-bold text-soft">
      <span aria-hidden className="flex gap-0.5">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-soft" style={{ animationDelay: `${i * 160}ms` }} />
        ))}
      </span>
      {label}
    </span>
  );
}

/** Список ходов парами; клик — смотреть позицию после хода. */
export function MoveList({
  sans,
  current,
  onSelect,
  empty,
}: {
  sans: string[];
  /** Сколько полуходов сыграно в показанной позиции. */
  current: number;
  onSelect: (plies: number) => void;
  empty: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Текущий ход — в видимой области списка (не прокручивая страницу).
    const container = box.current;
    const active = container?.querySelector<HTMLElement>("[data-active]");
    if (!container) return;
    if (!active) {
      if (current >= sans.length) container.scrollTop = container.scrollHeight;
      return;
    }
    const top = active.offsetTop - container.offsetTop;
    if (top < container.scrollTop) container.scrollTop = top;
    else if (top + active.offsetHeight > container.scrollTop + container.clientHeight)
      container.scrollTop = top + active.offsetHeight - container.clientHeight;
  }, [current, sans.length]);

  const rows = Math.ceil(sans.length / 2);
  return (
    <div ref={box} className="relative max-h-56 min-h-24 overflow-y-auto lg:max-h-none lg:flex-1">
      {sans.length === 0 ? (
        <p className="px-4 py-3 text-sm text-muted">{empty}</p>
      ) : (
        <ol className="py-1 text-[15px]">
          {Array.from({ length: rows }, (_, row) => (
            <li key={row} className={`grid grid-cols-[3rem_1fr_1fr] items-center px-2 ${row % 2 ? "bg-sunken/30" : ""}`}>
              <span className="pl-2 text-sm font-semibold text-muted">{row + 1}.</span>
              {[0, 1].map((side) => {
                const index = row * 2 + side;
                if (index >= sans.length) return <span key={side} />;
                const active = index + 1 === current;
                return (
                  <button
                    key={side}
                    type="button"
                    data-active={active || undefined}
                    aria-current={active || undefined}
                    onClick={() => onSelect(index + 1)}
                    className={`my-0.5 justify-self-start rounded px-2 py-0.5 text-left font-bold ${
                      active ? "bg-raised text-ink shadow-[inset_0_-2px_0_rgba(255,255,255,0.08)]" : "text-soft hover:bg-raised/60 hover:text-ink"
                    }`}
                  >
                    {sans[index]}
                  </button>
                );
              })}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Выбор фигуры превращения поверх доски — столбик на вертикали хода, как у Chess.com. */
export function PromotionPicker({
  square,
  color,
  orientation,
  onChoose,
  onCancel,
}: {
  square: string;
  color: Color;
  orientation: Color;
  onChoose: (piece: "q" | "n" | "r" | "b") => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const file = square.charCodeAt(0) - 97;
  const column = orientation === "white" ? file : 7 - file;
  const rank = square[1];
  const atTop = (rank === "8") === (orientation === "white");
  const prefix = color === "white" ? "w" : "b";
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div className="absolute inset-0 z-40 bg-black/35" onClick={onCancel}>
      <div
        role="dialog"
        aria-label={t.play.promotion}
        onClick={(event) => event.stopPropagation()}
        className={`absolute flex w-[12.5%] overflow-hidden rounded-[3px] bg-white shadow-[0_4px_14px_rgba(0,0,0,0.55)] ${
          atTop ? "top-0 flex-col" : "bottom-0 flex-col-reverse"
        }`}
        style={{ left: `${column * 12.5}%` }}
      >
        {(["q", "n", "r", "b"] as const).map((piece) => (
          <button
            key={piece}
            type="button"
            autoFocus={piece === "q"}
            onClick={() => onChoose(piece)}
            aria-label={piece.toUpperCase()}
            className="aspect-square w-full p-[6%] hover:bg-[#e8e6e1] focus-visible:bg-[#e8e6e1] focus-visible:outline-none"
          >
            <PieceImage code={`${prefix}${piece.toUpperCase()}` as PieceCode} />
          </button>
        ))}
        <button
          type="button"
          onClick={onCancel}
          aria-label={t.play.cancel}
          className="flex h-6 items-center justify-center bg-[#f1f1f1] text-[#8b8987] hover:text-[#312e2b]"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/** Модалка итога: кто выиграл и чем, участники, «Разобрать партию», «Новая партия». */
export function ResultModal({
  result,
  color,
  elo,
  onClose,
  actions,
}: {
  result: GameResult;
  color: Color;
  elo: number;
  onClose: () => void;
  actions: ReactNode;
}) {
  const { t } = useI18n();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const outcome = result.winner === null ? "draw" : result.winner === color ? "win" : "loss";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal
        aria-labelledby="bot-game-result"
        onClick={(event) => event.stopPropagation()}
        className="cc-bubble relative w-full max-w-[22rem] overflow-hidden rounded-xl bg-panel shadow-[0_12px_40px_rgba(0,0,0,0.6)]"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t.play.close}
          className="absolute top-2 right-2 z-10 flex h-8 w-8 items-center justify-center rounded-lg text-white/70 hover:bg-black/20 hover:text-white"
        >
          <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>
        <header className={`px-6 pt-5 pb-4 text-center ${outcome === "win" ? "bg-green" : "bg-sunken"}`}>
          <h2 id="bot-game-result" className="flex items-center justify-center gap-2 text-2xl font-extrabold text-white">
            {outcome === "win" && <Trophy />}
            {t.play.result[outcome]}
          </h2>
          <p className={`mt-0.5 text-sm font-semibold ${outcome === "win" ? "text-white/85" : "text-muted"}`}>
            {t.play.result.reasons[result.reason]}
          </p>
        </header>
        <div className="flex items-center justify-center gap-5 px-6 py-5">
          <Side
            label={t.play.you}
            avatar={<PlayerAvatar name={t.play.you} color={color} size={56} />}
            winner={result.winner === color}
          />
          <span className="text-sm font-bold text-muted">{result.result.replace("1/2", "½").replace("1/2", "½")}</span>
          <Side label={t.play.botName(elo)} avatar={<BotAvatar elo={elo} size={56} />} winner={result.winner !== null && result.winner !== color} />
        </div>
        <div className="flex flex-col gap-2 px-5 pb-5">{actions}</div>
      </div>
    </div>
  );
}

function Side({ label, avatar, winner }: { label: string; avatar: ReactNode; winner: boolean }) {
  return (
    <div className="flex w-24 flex-col items-center gap-1.5">
      <span className={`rounded-lg p-0.5 ${winner ? "ring-3 ring-green" : ""}`}>{avatar}</span>
      <span className="w-full truncate text-center text-xs font-bold text-soft">{label}</span>
    </div>
  );
}

function Trophy() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6" fill="#ffd56a">
      <path d="M7 3h10v2h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 14.9V18h3v3H8v-3h3v-3.1A5 5 0 0 1 8.3 12H8a4 4 0 0 1-4-4V5h3zm0 4H6v1a2 2 0 0 0 1.2 1.8A5 5 0 0 1 7 8.5zm10 0v1.5c0 .5 0 .9-.2 1.3A2 2 0 0 0 18 8V7z" />
    </svg>
  );
}

/** Кнопка-иконка панели (перевернуть, звук, навигация). */
export function IconButton({
  label,
  onClick,
  disabled,
  pressed,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  pressed?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-soft hover:bg-raised hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

/** Навигация по ходам: в начало, назад, вперёд, в конец — крупные кнопки как в разборе. */
export function MoveNav({
  current,
  total,
  onGo,
}: {
  current: number;
  total: number;
  onGo: (plies: number) => void;
}) {
  const { t } = useI18n();
  const items: { label: string; target: number; path: string }[] = [
    { label: t.play.first, target: 0, path: "M6 5v14M18 5l-8 7 8 7z" },
    { label: t.play.prev, target: current - 1, path: "M16 5l-9 7 9 7z" },
    { label: t.play.next, target: current + 1, path: "M8 5l9 7-9 7z" },
    { label: t.play.last, target: total, path: "M18 5v14M6 5l8 7-8 7z" },
  ];
  return (
    <div className="grid grid-cols-4 gap-1.5">
      {items.map((item) => {
        const disabled = item.target < 0 || item.target > total || item.target === current;
        return (
          <Button
            key={item.label}
            variant="raised"
            size="sm"
            aria-label={item.label}
            title={item.label}
            disabled={disabled}
            onClick={() => onGo(item.target)}
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
              <path d={item.path} />
            </svg>
          </Button>
        );
      })}
    </div>
  );
}
