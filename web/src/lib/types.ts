// Типы ответов API v1 (backend/app/api/schemas.py). Оценки хода — с точки зрения
// игрока, сделавшего ход; формат линий и мотивов — backend/app/workers/serialize.py.

export type GameSource = "lichess" | "chesscom" | "pgn";
export type Color = "white" | "black";
export type JobStatus = "queued" | "running" | "done" | "failed";
export type Phase = "opening" | "middlegame" | "endgame";

export type MoveClass =
  | "book"
  | "forced"
  | "brilliant"
  | "great"
  | "best"
  | "excellent"
  | "good"
  | "inaccuracy"
  | "mistake"
  | "blunder";

export type Progress = { done: number; total: number };

export type AnalysisSummary = {
  id: string;
  status: JobStatus;
  depth: number;
  /** Точность по формуле Lichess. */
  white_accuracy: number | null;
  black_accuracy: number | null;
  /** Точность «как у Chess.com» — приближение их формулы (backend/app/review/cc_accuracy.py). */
  cc_white_accuracy: number | null;
  cc_black_accuracy: number | null;
  created_at: string;
  finished_at: string | null;
};

/** Ход линии; нулевой ход угрозы — `{uci: "0000", san: "--"}`. */
export type LineMove = { uci: string; san: string };

export type EngineLine = { cp: number | null; mate: number | null; pv: LineMove[] };

export type Motif = {
  type: string;
  squares: string[];
  pieces: string[];
  gain_cp: number | null;
  line: LineMove[];
};

export type MoveMotifs = {
  played: Motif[];
  missed: Motif[];
  refutation: Motif[];
  sacrifice: { squares: string[]; material_drop: number } | null;
};

export type MoveOut = {
  id: number;
  ply: number;
  san: string;
  uci: string;
  fen_before: string;
  eval_before_cp: number | null;
  eval_after_cp: number | null;
  mate_before: number | null;
  /** 0 — ход поставил мат. */
  mate_after: number | null;
  win_before: number;
  win_after: number;
  accuracy: number;
  class: MoveClass;
  is_miss: boolean;
  best_uci: string | null;
  best_san: string | null;
  pv: LineMove[] | null;
  multipv: EngineLine[] | null;
  reply_pv: LineMove[] | null;
  motifs: MoveMotifs | null;
  phase: Phase;
  color: Color;
  fullmove: number;
};

export type PhaseAccuracy = Record<Color, Partial<Record<Phase, number | null>>>;

export type AnalysisOut = AnalysisSummary & {
  game_id: string;
  engine_version: string | null;
  phase_accuracy: PhaseAccuracy | null;
  error: string | null;
  started_at: string | null;
  progress: Progress | null;
  moves: MoveOut[];
};

export type GameOut = {
  id: string;
  source: GameSource;
  white: string;
  black: string;
  white_elo: number | null;
  black_elo: number | null;
  result: string;
  time_control: string | null;
  played_at: string | null;
  user_color: Color | null;
  opening_eco: string | null;
  opening_name: string | null;
  /** Точность по версии Chess.com — у партий, разобранных там. */
  source_white_accuracy: number | null;
  source_black_accuracy: number | null;
  /** Рейтинг партии по точности (как «Game Rating» Chess.com); null — точности нет. */
  game_rating: { white: number | null; black: number | null } | null;
  created_at: string;
  analysis: AnalysisSummary | null;
};

export type GameDetail = Omit<GameOut, "analysis"> & {
  pgn: string;
  analysis: AnalysisOut | null;
};

export type GamePage = { items: GameOut[]; next_cursor: string | null };

export type ImportJob = {
  job_id: string;
  source: GameSource;
  username: string;
  max_games: number | null;
  months: number | null;
  status: JobStatus;
  fetched: number;
  imported: number;
  skipped: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

/** Событие `progress` SSE-потока анализа. */
export type ProgressEvent = {
  status: JobStatus;
  done: number;
  total: number;
  error: string | null;
};

export type MoveExplanation = {
  move_id: number;
  ply: number;
  text: string;
  /** "template" — шаблон без LLM, иначе имя провайдера. */
  provider: string;
  cached: boolean;
};

export type Summary = { analysis_id: string; text: string; provider: string; cached: boolean };
