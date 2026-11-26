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
  /** Где считались оценки: воркер или Stockfish WASM в браузере (сессия 11). */
  runner: "server" | "browser";
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
  /** Код ошибки (backend/app/core/errors.py) — текст по нему в словаре `errors.codes`. */
  error_code: string | null;
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
  /** Средняя точность игроков рейтинга и контроля каждого игрока (только Chess.com). */
  group_accuracy: { white: number | null; black: number | null } | null;
  created_at: string;
  analysis: AnalysisSummary | null;
};

/** Часы на полуходе (сотые секунды): остаток после хода и потрачено на него (backend
 * `app/review/clock.py`): цейтнот перед ходом, быстрый ход, долгое раздумье. */
export type PlyClock = {
  clock_cs: number | null;
  spent_cs: number | null;
  trouble: boolean;
  fast: boolean;
  long: boolean;
};

export type PlayerClock = {
  moves: number;
  avg_spent_cs: number | null;
  longest_ply: number | null;
  longest_spent_cs: number | null;
  trouble_moves: number;
  first_trouble_ply: number | null;
};

export type GameClock = {
  base_cs: number;
  increment_cs: number;
  plies: PlyClock[];
  white: PlayerClock;
  black: PlayerClock;
};

export type GameDetail = Omit<GameOut, "analysis"> & {
  pgn: string;
  analysis: AnalysisOut | null;
  /** Время на ход по `%clk`; null — в партии нет часов. */
  clock?: GameClock | null;
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
  error_code: string | null;
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
  error_code: string | null;
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

// --- Статистика (GET /stats/me) ---

export type TimeClass = "bullet" | "blitz" | "rapid" | "daily";
export type AccuracyKind = "official" | "cc" | "lichess";
export type GameOutcome = "win" | "draw" | "loss";

export type AccuracyPoint = {
  game_id: string;
  played_at: string | null;
  accuracy: number;
  /** Откуда точность: официальная Chess.com, наша «как у Chess.com», формула Lichess. */
  kind: AccuracyKind;
  moving_avg: number;
  /** Рейтинг пользователя и средняя точность его рейтинговой группы (только Chess.com). */
  rating: number | null;
  group_accuracy: number | null;
  group_moving_avg: number | null;
  opponent: string;
  outcome: GameOutcome | null;
  time_class: TimeClass;
  color: Color;
};

export type OpeningStat = {
  eco: string | null;
  name: string;
  games: number;
  wins: number;
  draws: number;
  losses: number;
  accuracy: number | null;
};

export type MotifExample = {
  game_id: string;
  move_id: number;
  ply: number;
  fullmove: number;
  color: Color;
  san: string;
  class: MoveClass;
  is_miss: boolean;
  played_at: string | null;
  opponent: string;
};

export type BrilliantMove = {
  game_id: string;
  move_id: number;
  ply: number;
  fullmove: number;
  color: Color;
  san: string;
  uci: string;
  fen_before: string;
  played_at: string | null;
  opponent: string;
  time_class: TimeClass;
  outcome: "win" | "draw" | "loss" | null;
};

export type Stats = {
  filters: { source: GameSource | null; time_class: TimeClass | null };
  totals: {
    games: number;
    games_without_color: number;
    analyzed: number;
    wins: number;
    draws: number;
    losses: number;
    accuracy: number | null;
    with_accuracy: number;
  };
  accuracy: { window: number; points: AccuracyPoint[] };
  /** Точность пользователя против рейтинговой группы — по контролям времени. */
  rating_groups: { time_class: TimeClass; games: number; rating: number; accuracy: number; group_accuracy: number }[];
  openings: { white: OpeningStat[]; black: OpeningStat[] };
  /** Точность фаз — по формуле Lichess. */
  phases: { phase: Phase; accuracy: number | null; games: number }[];
  classes: {
    games: number;
    moves: number;
    items: { class: MoveClass | "miss"; count: number; per_game: number; share: number }[];
  };
  motifs: { type: string; count: number; examples: MotifExample[] }[];
  /** Блестящие ходы пользователя: счётчики по всем, `moves` — последние (до 100). */
  brilliant: { count: number; games: number; moves: BrilliantMove[] };
  /** Время на ход — только разобранные партии с часами; null — таких нет. */
  time?: TimeStats | null;
};

export type ClockBucket = "over_half" | "quarter_half" | "tenth_quarter" | "under_tenth";

export type TimeStats = {
  games: number;
  moves: number;
  trouble_games: number;
  /** По остатку на часах перед ходом (доля базы); последнее — цейтнот. */
  buckets: { bucket: ClockBucket; moves: number; accuracy: number | null; errors_per_100: number | null }[];
  phases: { phase: Phase; moves: number; avg_spent_cs: number | null }[];
  /** Ошибки (mistake + blunder): всего, в цейтноте, «поспешные» — быстрый ход вне цейтнота. */
  errors: number;
  trouble_errors: number;
  hasty_errors: number;
};

// --- Пазлы ---

export type Puzzle = {
  id: string;
  fen: string;
  color: Color;
  themes: string[];
  player_moves: number;
  /** Подсказка: поле, с которого ходит игрок, на каждый его ход. */
  hints: string[];
  box: number;
  attempts: number;
  next_review_at: string | null;
  last_move: { uci: string; san: string; fen_before: string } | null;
  source: {
    game_id: string;
    ply: number;
    fullmove: number;
    san: string;
    class: MoveClass;
    is_miss: boolean;
    opponent: string;
    played_at: string | null;
  } | null;
};

export type PuzzleCounts = {
  due: number;
  new: number;
  total: number;
  streak: number;
  next_review_at: string | null;
};

export type PuzzleNext = { puzzle: Puzzle | null; counts: PuzzleCounts };

/** `srs` — повторение, `practice` — по темам, `rush` — на время. */
export type PuzzleMode = "srs" | "practice" | "rush";

/** Фильтры тренировки (в URL `/puzzles?theme=&phase=&eco=`): тема — тип мотива, фаза — хода-источника, eco — дебют партии. */
export type PuzzleFilters = { theme: string | null; phase: Phase | null; eco: string | null };

export type PuzzleThemes = {
  themes: { theme: string; total: number; due: number; solved: number }[];
  phases: { phase: Phase; total: number; solved: number }[];
  openings: { eco: string; name: string | null; total: number }[];
};

export type RushVariant = "3min" | "5min" | "survival";

export type RushRunBody = {
  variant: RushVariant;
  score: number;
  mistakes: number;
  duration_s: number;
  filters: Partial<{ theme: string; phase: Phase; eco: string }>;
};

export type RushRunResult = { id: number; best: number; is_best: boolean };

export type RushRuns = {
  best: number | null;
  recent: {
    id: number;
    score: number;
    mistakes: number;
    duration_s: number;
    filters: PuzzleFilters;
    created_at: string;
  }[];
};

export type PuzzleAttempt = {
  result: "continue" | "solved" | "failed";
  reply_uci: string | null;
  expected_uci: string | null;
  solution_uci: string[] | null;
  solution_san: string[] | null;
  box: number | null;
  next_review_at: string | null;
  streak: number | null;
};

export type Lang = "ru" | "en";

export type User = {
  id: string;
  email: string;
  lang: Lang;
  lichess_username: string | null;
  chesscom_username: string | null;
  created_at: string;
};

/** Ответ входа / регистрации / обновления: access-токен (держим в памяти) и пользователь;
 * refresh-токен — в httpOnly-cookie, JavaScript его не видит. */
export type AuthOut = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type ProfileUpdate = Partial<Pick<User, "lang" | "lichess_username" | "chesscom_username">>;

export type StreamToken = { token: string; expires_in: number };

// --- Движок (сессия 11): анализ в браузере, режим исследования ---

export type EngineConfig = {
  analysis_depth: number;
  analysis_multipv: number;
  browser_min_depth: number;
  explore_depth: number;
};

/** Класс хода режима исследования (`POST /engine/classify`); оценки — за сделавшего ход. */
export type ClassifyOut = {
  class: MoveClass;
  is_miss: boolean;
  best_uci: string | null;
  best_san: string | null;
  eval_before_cp: number | null;
  eval_after_cp: number | null;
  mate_before: number | null;
  mate_after: number | null;
  accuracy: number;
};

/** Публичная ссылка на разбор партии. */
export type ShareOut = { token: string; url: string };

export type BrowserAnalysisOut = {
  analysis: AnalysisOut;
  /** Позиции для проверки пазлов: посчитать в браузере (MultiPV=2) и прислать обратно. */
  puzzle_probes: { fen: string; move: string }[];
};

/** Оценка позиции движком API: за сторону на ходу в `fen`; пусто — позиция финальная. */
export type ExploreOut = {
  fen: string;
  depth: number;
  lines: { cp: number | null; mate: number | null; pv: LineMove[] }[];
};
