import type { Color, GameOut, GameSource } from "./types";

export const SOURCE_NAMES: Record<GameSource, string> = {
  lichess: "Lichess",
  chesscom: "Chess.com",
  pgn: "PGN",
};

const dateFormat = new Intl.DateTimeFormat("ru", { day: "numeric", month: "short", year: "numeric" });

export const formatDate = (iso: string | null) => (iso ? dateFormat.format(new Date(iso)) : null);

/** Контроль времени из PGN: `600+5` → `10+5`, `180` → `3 мин`, `1/86400` → `1 д.`. */
export function formatTimeControl(value: string | null): string | null {
  if (!value || value === "-" || value === "?") return null;
  const daily = value.match(/^1\/(\d+)$/);
  if (daily) return `${Math.round(Number(daily[1]) / 86400)} д.`;
  const match = value.match(/^(\d+)(?:\+(\d+))?$/);
  if (!match) return value;
  const base = Number(match[1]);
  const minutes = base >= 60 ? String(Math.round((base / 60) * 10) / 10) : `${base} с`;
  return match[2] && match[2] !== "0" ? `${minutes}+${match[2]}` : `${minutes} мин`;
}

export type Outcome = "win" | "loss" | "draw" | null;

/** Исход для пользователя (если известен его цвет). */
export function outcome(game: Pick<GameOut, "result" | "user_color">): Outcome {
  if (game.result === "1/2-1/2") return game.user_color ? "draw" : null;
  if (!game.user_color) return null;
  if (game.result === "1-0") return game.user_color === "white" ? "win" : "loss";
  if (game.result === "0-1") return game.user_color === "black" ? "win" : "loss";
  return null;
}

export const OUTCOME_LABELS = { win: "Победа", loss: "Поражение", draw: "Ничья" } as const;

export const formatResult = (result: string) => (result === "1/2-1/2" ? "½–½" : result.replace("-", "–"));

/** Очки игрока: `1`, `0`, `½`; незавершённая партия — `*`. */
export function score(result: string, color: Color): string {
  if (result === "1/2-1/2") return "½";
  if (result === "1-0") return color === "white" ? "1" : "0";
  if (result === "0-1") return color === "black" ? "1" : "0";
  return "*";
}

export const playerName = (game: Pick<GameOut, "white" | "black">, color: Color) =>
  color === "white" ? game.white : game.black;

export const playerElo = (game: Pick<GameOut, "white_elo" | "black_elo">, color: Color) =>
  color === "white" ? game.white_elo : game.black_elo;

export const opposite = (color: Color): Color => (color === "white" ? "black" : "white");

/** Куда ведёт партия из списков: без анализа — сразу с запуском анализа. */
export const gameHref = (game: Pick<GameOut, "id" | "analysis">) =>
  game.analysis ? `/games/${game.id}` : `/games/${game.id}?analyze=1`;
