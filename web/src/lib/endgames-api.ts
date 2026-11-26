// Клиент API тренажёра эндшпиля (сессия 16.3, `backend/app/api/endgames.py`): каталог типовых
// позиций, позиции из своих партий, таблицы Syzygy, попытки.
import type { Goal, TbCategory } from "@/components/endgames/goal";
import { request } from "./api";
import type { Color } from "./types";

export type EndgameCategory = "pawn" | "rook" | "queen" | "mate";

export type Progress = { attempts: number; successes: number };

export type CatalogPosition = Progress & {
  id: string;
  category: EndgameCategory;
  fen: string;
  goal: Goal;
  /** 1 — азы, 2 — техника, 3 — трудно. */
  difficulty: number;
  /** Цвет ученика — сторона на ходу. */
  color: Color;
  pieces: number;
};

export type Catalog = { categories: EndgameCategory[]; positions: CatalogPosition[] };

export type GamePosition = Progress & {
  /** Id хода — ключ попытки. */
  key: string;
  fen: string;
  goal: Goal;
  game_id: string;
  ply: number;
  played_at: string | null;
  opponent: string;
  /** Ход, сыгранный в партии (ошибка). */
  san: string;
  best_san: string | null;
  win_before: number;
  pieces: number;
};

export type TablebaseMove = { uci: string; san: string; category: TbCategory; dtz: number | null; dtm: number | null };

/** Глазами стороны на ходу; ходы — от лучшего к худшему. */
export type Tablebase = {
  category: TbCategory;
  dtz: number | null;
  dtm: number | null;
  checkmate: boolean;
  stalemate: boolean;
  moves: TablebaseMove[];
};

export type EndgameSource = "catalog" | "game";

export const endgamesApi = {
  catalog: () => request<Catalog>("/endgames/catalog"),
  mine: (limit?: number) => request<{ positions: GamePosition[] }>(`/endgames/mine${limit ? `?limit=${limit}` : ""}`),
  tablebase: (fen: string) => request<Tablebase>(`/endgames/tablebase?fen=${encodeURIComponent(fen)}`),
  attempt: (body: { source: EndgameSource; key: string; goal: Goal; success: boolean; plies: number }) =>
    request<Progress>("/endgames/attempts", { method: "POST", body: JSON.stringify(body) }),
};
