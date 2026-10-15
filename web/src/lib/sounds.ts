"use client";

// Звуки ходов как в Chess.com. Файлы лежат локально в web/public/chesscom/sounds/ (в git не
// идут, как и фигуры); если их нет — играть просто нечего, ошибки глушатся.
import { useSyncExternalStore } from "react";
import type { Color } from "./types";

export type SoundName =
  | "move-self"
  | "move-opponent"
  | "capture"
  | "castle"
  | "move-check"
  | "promote"
  | "game-end"
  | "illegal"
  | "correct"
  | "incorrect";

const BASE = "/chesscom/sounds";
const MUTED_KEY = "chess-review:sound-muted";
// Последний ход партии: после звука хода — звук конца партии.
const GAME_END_DELAY_MS = 220;

const audios = new Map<SoundName, HTMLAudioElement>();
const listeners = new Set<() => void>();
let muted: boolean | null = null;

function readMuted(): boolean {
  if (muted === null) {
    try {
      muted = localStorage.getItem(MUTED_KEY) === "1";
    } catch {
      muted = false;
    }
  }
  return muted;
}

function audio(name: SoundName): HTMLAudioElement {
  let element = audios.get(name);
  if (!element) {
    element = new Audio(`${BASE}/${name}.mp3`);
    element.preload = "auto";
    audios.set(name, element);
  }
  return element;
}

export function playSound(name: SoundName) {
  if (typeof window === "undefined" || readMuted()) return;
  const element = audio(name);
  // Быстрое листание: предыдущий звук обрывается, как у Chess.com.
  element.currentTime = 0;
  element.play().catch(() => {});
}

/** Звук хода по SAN: шах > превращение > рокировка > взятие > обычный ход (свой / соперника). */
export function moveSound(san: string, self: boolean): SoundName {
  if (san.includes("+") || san.includes("#")) return "move-check";
  if (san.includes("=")) return "promote";
  if (san.startsWith("O-O")) return "castle";
  if (san.includes("x")) return "capture";
  return self ? "move-self" : "move-opponent";
}

export function playMove(san: string, color: Color, selfColor: Color, lastOfGame = false) {
  playSound(moveSound(san, color === selfColor));
  if (lastOfGame) setTimeout(() => playSound("game-end"), GAME_END_DELAY_MS);
}

/** Прогрев: браузер скачает файлы заранее, первый ход прозвучит без задержки. */
export function preloadSounds() {
  if (typeof window === "undefined") return;
  (["move-self", "move-opponent", "capture", "castle", "move-check"] as SoundName[]).forEach(audio);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSoundMuted(): boolean {
  return useSyncExternalStore(subscribe, readMuted, () => false);
}

export function toggleMuted() {
  muted = !readMuted();
  try {
    localStorage.setItem(MUTED_KEY, muted ? "1" : "0");
  } catch {
    // Приватный режим: настройка живёт до перезагрузки.
  }
  listeners.forEach((notify) => notify());
}
