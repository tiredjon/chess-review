// Клиент тренера (сессия 17) — зеркало `backend/app/api/schemas_coach.py` (общий контракт
// 17.1–17.3). Менять поля — только согласованно со SPEC «Сессия 17» и схемами бэкенда.
import { request } from "./api";
import type { FindingExample, Severity, Train } from "./insights-api";
import type { TimeClass } from "./types";

// --- Цель ---

export type GoalSource = "chesscom" | "lichess";

export type GoalIn = {
  source: GoalSource;
  time_class: TimeClass;
  target_rating: number;
  minutes_per_day: number;
  days_per_week: number;
  /** IANA-зона браузера: `Intl.DateTimeFormat().resolvedOptions().timeZone`. */
  tz: string;
};

export type Goal = {
  id: number;
  source: GoalSource;
  time_class: TimeClass;
  start_rating: number;
  current_rating: number;
  target_rating: number;
  minutes_per_day: number;
  days_per_week: number;
  tz: string;
  created_at: string;
  achieved_at: string | null;
};

export type RatingOption = {
  source: GoalSource;
  time_class: TimeClass;
  rating: number;
  games: number;
  last_played_at: string | null;
};

export type GoalState = { goal: Goal | null; ratings: RatingOption[] };

// --- Диагностика (17.1) ---

export type MetricKey =
  | "accuracy"
  | "accuracy_opening"
  | "accuracy_middlegame"
  | "accuracy_endgame"
  | "blunders_per_100"
  | "mistakes_per_100"
  | "misses_per_100"
  | "conversion"
  | "resilience"
  | "time_trouble_share"
  | "hasty_per_100";
/** metric — ключ из MetricKey; motif — тип мотива (`common.motifs`); opening — `цвет:семейство`. */
export type MetricKind = "metric" | "motif" | "opening";
export type Direction = "higher_better" | "lower_better";
export type MetricStatus = "strength" | "weakness" | "neutral" | "insufficient";

export type Norm = { p25: number; p50: number; p75: number };

export type Metric = {
  kind: MetricKind;
  key: string;
  value: number | null;
  n: number;
  direction: Direction;
  current: Norm | null;
  target: Norm | null;
  /** Место среди целевой группы, 0–100 (больше — лучше с учётом direction). */
  percentile: number | null;
  status: MetricStatus;
};

export type Gap = {
  kind: MetricKind;
  key: string;
  severity: Severity;
  score: number;
  value: number;
  target_p50: number | null;
  train: Train | null;
  lesson: string | null;
  examples: FindingExample[];
};

export type Diagnosis = {
  goal: Goal;
  current_rating: number;
  current_band: number;
  target_band: number;
  /** Ближайшая собранная группа дальше ±100 от рейтинга: сравнения с ней нет. */
  current_band_far?: boolean;
  target_band_far?: boolean;
  norms_version: string;
  analyzed_games: number;
  min_games: number;
  metrics: Metric[];
  strengths: Gap[];
  weaknesses: Gap[];
};

// --- План и задания (17.2) ---

export type TaskKind = "puzzles" | "rush" | "endgames" | "course" | "play" | "review" | "lesson";
export type TaskUnit = "puzzles" | "runs" | "attempts" | "games" | "lessons";

export type CoachTask = {
  id: number;
  day: string;
  position: number;
  kind: TaskKind;
  params: Record<string, string | number>;
  target: number;
  progress: number;
  unit: TaskUnit;
  minutes: number;
  done: boolean;
  done_at: string | null;
  href: string;
  focus: string | null;
};

export type Today = {
  goal: Goal;
  day: string;
  rest_day: boolean;
  tasks: CoachTask[];
  minutes_total: number;
  minutes_done: number;
  streak_days: number;
};

export type Allocation = { kind: TaskKind; minutes_per_week: number; share: number; focus: string[] };

export type PlanDay = { day: string; rest_day: boolean; minutes: number; tasks: CoachTask[] };

export type Plan = {
  goal: Goal;
  week_start: string;
  created_at: string;
  focus: Gap[];
  allocation: Allocation[];
  days: PlanDay[];
  next_rebuild: string;
};

export type MetricDelta = { kind: MetricKind; key: string; before: number | null; after: number | null; direction: Direction };

export type WeekReport = {
  week_start: string;
  tasks_total: number;
  tasks_done: number;
  minutes_done: number;
  games_played: number;
  rating_start: number | null;
  rating_end: number | null;
  metrics: MetricDelta[];
};

// --- Прогноз (17.2) ---

export type ForecastStatus = "achieved" | "ahead" | "on_track" | "behind" | "insufficient";
export type Confidence = "low" | "medium" | "high";

export type Forecast = {
  start_rating: number;
  current_rating: number;
  target_rating: number;
  status: ForecastStatus;
  weeks_p50: number | null;
  weeks_p80: number | null;
  date_p50: string | null;
  date_p80: string | null;
  reach_probability_1y: number | null;
  confidence: Confidence;
  basis: {
    sample_players: number;
    user_games: number;
    weekly_trend: number | null;
    adherence: number | null;
    games_per_week: number;
  };
  history: { date: string; rating: number }[];
  projection: { date: string; p10: number; p50: number; p90: number }[];
};

// --- Уроки (17.2; тексты — `lib/coach-lessons/`) ---

export type LessonKind = "motif" | "phase" | "skill";
export type LessonItem = { key: string; kind: LessonKind; read: boolean };
export type Lesson = { key: string; kind: LessonKind; read: boolean; examples: FindingExample[]; train: Train | null };

const send = <T>(path: string, method: string, body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const coachApi = {
  goal: () => request<GoalState>("/coach/goal"),
  setGoal: (goal: GoalIn) => send<Goal>("/coach/goal", "PUT", goal),
  deleteGoal: () => send<null>("/coach/goal", "DELETE"),
  diagnosis: () => request<Diagnosis>("/coach/diagnosis"),
  today: () => request<Today>("/coach/today"),
  completeTask: (id: number) => send<CoachTask>(`/coach/tasks/${id}/done`, "POST"),
  plan: () => request<Plan>("/coach/plan"),
  rebuildPlan: () => send<Plan>("/coach/plan/rebuild", "POST"),
  report: () => request<{ report: WeekReport | null }>("/coach/report"),
  forecast: () => request<Forecast>("/coach/forecast"),
  lessons: () => request<{ lessons: LessonItem[] }>("/coach/lessons"),
  lesson: (key: string) => request<Lesson>(`/coach/lessons/${encodeURIComponent(key)}`),
  readLesson: (key: string) => send<LessonItem>(`/coach/lessons/${encodeURIComponent(key)}/read`, "POST"),
};
