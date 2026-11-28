// Моки API тренера (сессия 17.3): показывают все состояния экрана, пока бэкенд не готов.
// Включаются только `NEXT_PUBLIC_COACH_MOCK=1` в дев-сборке (в продакшен-сборке — никогда).
// Сценарий — `?mock=<имя>` в адресе любой страницы (запоминается в sessionStorage):
//   default · nogoal · norating · insufficient · rest · behind · ahead · achieved · nodate · fresh
import type {
  CoachTask,
  Diagnosis,
  Forecast,
  Gap,
  Goal,
  GoalIn,
  GoalState,
  Lesson,
  LessonItem,
  Metric,
  Plan,
  PlanDay,
  TaskKind,
  Today,
  WeekReport,
} from "@/lib/coach-api";
import { ApiError } from "@/lib/api";
import type { FindingExample } from "@/lib/insights-api";

export const COACH_MOCK = process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_COACH_MOCK === "1";

export type Scenario =
  | "default"
  | "nogoal"
  | "norating"
  | "insufficient"
  | "rest"
  | "behind"
  | "ahead"
  | "achieved"
  | "nodate"
  | "fresh";

const SCENARIOS: Scenario[] = ["default", "nogoal", "norating", "insufficient", "rest", "behind", "ahead", "achieved", "nodate", "fresh"];
const KEY = "coach-mock";

let scenario: Scenario = "default";
let goal: Goal | null = null;
let doneIds = new Set<number>();
let readLessons = new Set<string>();

function readScenario(): Scenario {
  let next: Scenario = scenario;
  try {
    const param = new URLSearchParams(window.location.search).get("mock");
    const stored = sessionStorage.getItem(KEY);
    const wanted = param ?? stored;
    const found = SCENARIOS.find((s) => s === wanted);
    if (found) next = found;
    if (param) sessionStorage.setItem(KEY, param);
  } catch {
    // Нет window / хранилища — остаётся прежний сценарий.
  }
  if (next !== scenario || goal === null) {
    scenario = next;
    reset();
  }
  return scenario;
}

const iso = (offsetDays: number): string => {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

/** Смещение понедельника этой недели от сегодня, в днях. */
const monday = () => -((new Date().getDay() + 6) % 7);

function makeGoal(): Goal {
  const achieved = scenario === "achieved";
  return {
    id: 1,
    source: "chesscom",
    time_class: "rapid",
    start_rating: 1700,
    current_rating: achieved ? 2004 : scenario === "behind" ? 1722 : scenario === "ahead" ? 1905 : scenario === "fresh" ? 1700 : 1812,
    target_rating: 2000,
    minutes_per_day: 45,
    days_per_week: 5,
    tz: "Europe/Moscow",
    created_at: `${iso(-84)}T09:00:00Z`,
    achieved_at: achieved ? `${iso(-3)}T18:00:00Z` : null,
  };
}

function reset() {
  doneIds = new Set(scenario === "default" ? [101, 102] : scenario === "ahead" ? [101, 102, 103] : []);
  readLessons = new Set();
  goal = scenario === "nogoal" || scenario === "norating" ? null : makeGoal();
}

const wait = <T>(value: T, ms = 250): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(value), ms));
const fail = (status: number, code: string, message: string): never => {
  throw new ApiError(status, message, code);
};

const NO_GOAL = () => fail(404, "coach_goal_not_found", "Цель тренера не задана");

// --- Примеры позиций ---

const EXAMPLES: FindingExample[] = [
  {
    game_id: "mock-1",
    ply: 7,
    fen_before: "r1bqkbnr/1ppp1ppp/p1n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4",
    san: "Bxc6",
    best_san: "Ba4",
    move_class: "mistake",
    opponent: "knight_rider",
    played_at: `${iso(-5)}T18:20:00Z`,
  },
  {
    game_id: "mock-2",
    ply: 3,
    fen_before: "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2",
    san: "c4",
    best_san: "Nf3",
    move_class: "inaccuracy",
    opponent: "pawnstorm77",
    played_at: `${iso(-9)}T12:05:00Z`,
  },
  {
    game_id: "mock-3",
    ply: 2,
    fen_before: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    san: "e5",
    best_san: "c5",
    move_class: "blunder",
    opponent: "endgame_fan",
    played_at: `${iso(-12)}T20:40:00Z`,
  },
];

const gap = (kind: Gap["kind"], key: string, severity: Gap["severity"], value: number, target: number | null, lesson: string | null, train: Gap["train"], n = 3): Gap => ({
  kind,
  key,
  severity,
  score: severity === "high" ? 3 : severity === "medium" ? 2 : 1,
  value,
  target_p50: target,
  train,
  lesson,
  examples: EXAMPLES.slice(0, n),
});

const norm = (p50: number, spread: number) => ({ p25: p50 - spread, p50, p75: p50 + spread });
const metric = (key: string, value: number | null, cur: number, tgt: number, percentile: number | null, status: Metric["status"], lower = false, n = 60): Metric => ({
  kind: "metric",
  key,
  value,
  n,
  direction: lower ? "lower_better" : "higher_better",
  current: norm(cur, Math.abs(cur) * 0.12),
  target: norm(tgt, Math.abs(tgt) * 0.1),
  percentile,
  status,
});

function diagnosis(): Diagnosis {
  const g = goal ?? NO_GOAL();
  const insufficient = scenario === "insufficient" || scenario === "fresh";
  return {
    goal: g,
    current_rating: g.current_rating,
    current_band: 1800,
    target_band: 2000,
    norms_version: "placeholder",
    analyzed_games: insufficient ? 7 : 64,
    min_games: 20,
    metrics: insufficient
      ? []
      : [
          metric("accuracy", 78.4, 79, 84, 22, "weakness"),
          metric("accuracy_opening", 88, 85, 89, 38, "neutral"),
          metric("accuracy_middlegame", 74.2, 76, 81, 18, "weakness"),
          metric("accuracy_endgame", 83.5, 78, 82, 61, "strength"),
          metric("blunders_per_100", 2.6, 3.1, 1.9, 24, "weakness", true),
          metric("mistakes_per_100", 3.9, 4.4, 3.2, 33, "neutral", true),
          metric("misses_per_100", 4.1, 5.0, 3.6, 41, "neutral", true),
          metric("conversion", 71, 64, 74, 40, "neutral"),
          metric("resilience", 36, 28, 34, 66, "strength"),
          metric("time_trouble_share", 31, 22, 15, 12, "weakness", true),
          metric("hasty_per_100", null, 6, 4, null, "insufficient", true, 4),
        ],
    strengths: insufficient
      ? []
      : [
          gap("metric", "accuracy_endgame", "low", 83.5, 82, "endgame_technique", { kind: "endgames", query: { theme: null, phase: "endgame", eco: null }, available: 8 }, 2),
          gap("metric", "resilience", "low", 36, 34, "defense", { kind: "play", query: { theme: null, phase: null, eco: null }, available: 0 }, 0),
        ],
    weaknesses: insufficient
      ? []
      : [
          gap("motif", "fork", "high", 14.2, 8, "fork", { kind: "puzzles", query: { theme: "fork", phase: null, eco: null }, available: 120 }),
          gap("metric", "time_trouble_share", "medium", 31, 15, "time_management", { kind: "puzzles", query: { theme: null, phase: null, eco: null }, available: 200 }, 2),
          gap("metric", "accuracy_middlegame", "medium", 74.2, 81, "middlegame_plans", { kind: "puzzles", query: { theme: null, phase: "middlegame", eco: null }, available: 300 }, 3),
        ],
  };
}

// --- Задания ---

type Seed = { id: number; kind: TaskKind; target: number; unit: CoachTask["unit"]; minutes: number; focus: string | null; params?: CoachTask["params"]; progress?: number };

const HREF: Record<TaskKind, string> = {
  puzzles: "/puzzles?mode=practice&theme=fork",
  rush: "/puzzles?mode=rush",
  endgames: "/play/endgames?tab=mine",
  course: "/openings/courses",
  play: "/play",
  review: "/games",
  lesson: "/coach/lessons/fork",
};

const DAY_SEEDS: Seed[][] = [
  [
    { id: 101, kind: "puzzles", target: 15, unit: "puzzles", minutes: 15, focus: "fork" },
    { id: 102, kind: "lesson", target: 1, unit: "lessons", minutes: 5, focus: "time_management", params: { key: "time_management" } },
    { id: 103, kind: "play", target: 1, unit: "games", minutes: 25, focus: null },
  ],
  [
    { id: 111, kind: "endgames", target: 3, unit: "attempts", minutes: 15, focus: null },
    { id: 112, kind: "rush", target: 2, unit: "runs", minutes: 10, focus: "time_trouble_share" },
    { id: 113, kind: "review", target: 1, unit: "games", minutes: 20, focus: null },
  ],
  [],
  [
    { id: 121, kind: "puzzles", target: 20, unit: "puzzles", minutes: 20, focus: "pin" },
    { id: 122, kind: "course", target: 1, unit: "attempts", minutes: 10, focus: "Italian Game" },
    { id: 123, kind: "play", target: 1, unit: "games", minutes: 15, focus: null },
  ],
  [
    { id: 131, kind: "puzzles", target: 15, unit: "puzzles", minutes: 15, focus: "fork" },
    { id: 132, kind: "review", target: 1, unit: "games", minutes: 30, focus: null },
  ],
  [],
  [],
];

const REST_DAYS = new Set([2, 5, 6]);

function task(seed: Seed, day: string): CoachTask {
  const done = doneIds.has(seed.id);
  const auto = seed.kind !== "review" && seed.kind !== "lesson";
  const progress = done ? seed.target : (seed.progress ?? (auto && seed.id % 2 === 0 ? Math.floor(seed.target / 2) : 0));
  return {
    id: seed.id,
    day,
    position: seed.id % 10,
    kind: seed.kind,
    params: seed.params ?? {},
    target: seed.target,
    progress,
    unit: seed.unit,
    minutes: seed.minutes,
    done,
    done_at: done ? `${day}T10:00:00Z` : null,
    href: HREF[seed.kind],
    focus: seed.focus,
  };
}

function weekDays(): PlanDay[] {
  const start = monday();
  return DAY_SEEDS.map((seeds, i) => {
    const day = iso(start + i);
    const tasks = seeds.map((s) => task(s, day));
    return { day, rest_day: REST_DAYS.has(i), minutes: tasks.reduce((sum, t) => sum + t.minutes, 0), tasks };
  });
}

function todayPlan(): Today {
  const g = goal ?? NO_GOAL();
  const day = iso(0);
  // В демо «сегодня» — всегда рабочий день с заданиями первого дня плана, кроме сценария rest.
  const tasks = scenario === "rest" ? [] : weekDays()[0].tasks.map((t) => ({ ...t, day }));
  const minutesTotal = tasks.reduce((s, t) => s + t.minutes, 0);
  return {
    goal: g,
    day,
    rest_day: scenario === "rest",
    tasks,
    minutes_total: minutesTotal,
    minutes_done: tasks.filter((t) => t.done).reduce((s, t) => s + t.minutes, 0),
    streak_days: scenario === "fresh" || scenario === "behind" ? 0 : 6,
  };
}

function plan(): Plan {
  const g = goal ?? NO_GOAL();
  const days = weekDays();
  const total = days.reduce((s, d) => s + d.minutes, 0);
  const kinds: [TaskKind, number, string[]][] = [
    ["puzzles", 50, ["fork", "pin"]],
    ["play", 40, []],
    ["review", 50, []],
    ["endgames", 15, []],
    ["rush", 10, ["time_trouble_share"]],
    ["course", 10, ["Italian Game"]],
    ["lesson", 5, ["time_management"]],
  ];
  return {
    goal: g,
    week_start: iso(monday()),
    created_at: `${iso(monday())}T05:00:00Z`,
    focus: diagnosis().weaknesses,
    allocation: kinds.map(([kind, m, focus]) => ({ kind, minutes_per_week: m, share: Math.round((m / total) * 100) / 100, focus })),
    days,
    next_rebuild: iso(monday() + 7),
  };
}

function report(): { report: WeekReport | null } {
  if (scenario === "fresh" || scenario === "insufficient") return { report: null };
  const g = goal ?? NO_GOAL();
  return {
    report: {
      week_start: iso(monday() - 7),
      tasks_total: 14,
      tasks_done: scenario === "behind" ? 5 : 11,
      minutes_done: scenario === "behind" ? 95 : 205,
      games_played: scenario === "behind" ? 2 : 6,
      rating_start: g.current_rating - 14,
      rating_end: g.current_rating,
      metrics: [
        { kind: "metric", key: "accuracy", before: 77.8, after: 78.4, direction: "higher_better" },
        { kind: "metric", key: "blunders_per_100", before: 3.1, after: 2.6, direction: "lower_better" },
        { kind: "motif", key: "fork", before: 11, after: 14.2, direction: "lower_better" },
        { kind: "metric", key: "conversion", before: 71, after: 71, direction: "higher_better" },
      ],
    },
  };
}

function forecast(): Forecast {
  const g = goal ?? NO_GOAL();
  const insufficient = scenario === "insufficient" || scenario === "fresh";
  const achieved = scenario === "achieved";
  const never = scenario === "nodate";
  const history: Forecast["history"] = [];
  const start = g.start_rating;
  const now = g.current_rating;
  for (let w = 12; w >= 0; w--) {
    const t = (12 - w) / 12;
    const wiggle = Math.sin(w * 1.7) * 9;
    history.push({ date: iso(-w * 7), rating: Math.round(start + (now - start) * t + wiggle * (w === 0 ? 0 : 1)) });
  }
  const weeksTo = scenario === "behind" ? 52 : scenario === "ahead" ? 6 : 22;
  const projection: Forecast["projection"] = [];
  if (!achieved && !never && !insufficient) {
    const steps = Math.round(weeksTo * 1.45);
    for (let w = 1; w <= steps; w += 1) {
      const share = w / weeksTo;
      const p50 = now + (g.target_rating - now) * Math.min(share, 1.4);
      const spread = 8 + w * 3.2;
      projection.push({ date: iso(w * 7), p10: Math.round(p50 - spread), p50: Math.round(p50), p90: Math.round(p50 + spread) });
    }
  }
  const noEta = achieved || never || insufficient;
  return {
    start_rating: start,
    current_rating: now,
    target_rating: g.target_rating,
    status: achieved ? "achieved" : insufficient ? "insufficient" : scenario === "behind" ? "behind" : scenario === "ahead" ? "ahead" : "on_track",
    weeks_p50: noEta ? null : weeksTo,
    weeks_p80: noEta ? null : Math.round(weeksTo * 1.45),
    date_p50: noEta ? null : iso(weeksTo * 7),
    date_p80: noEta ? null : iso(Math.round(weeksTo * 1.45) * 7),
    reach_probability_1y: noEta ? null : scenario === "behind" ? 0.48 : 0.83,
    confidence: scenario === "default" || scenario === "ahead" ? "medium" : scenario === "achieved" ? "high" : "low",
    basis: {
      sample_players: 340,
      user_games: insufficient ? 7 : 64,
      weekly_trend: scenario === "behind" ? 1.4 : 5.6,
      adherence: scenario === "behind" ? 0.36 : 0.82,
      games_per_week: 4.5,
    },
    history: insufficient ? history.slice(-3) : history,
    projection,
  };
}

function lesson(key: string): Lesson {
  const read = readLessons.has(key);
  const motif = key === "fork" || key === "pin";
  const book = key.startsWith("book_");
  return {
    key,
    kind: motif ? "motif" : book ? "book" : key.endsWith("principles") || key.endsWith("plans") || key.endsWith("technique") ? "phase" : "skill",
    read,
    examples: key === "defense" ? [] : EXAMPLES,
    train: motif
      ? { kind: "puzzles", query: { theme: key, phase: null, eco: null }, available: 120 }
      : key === "endgame_technique"
        ? { kind: "endgames", query: { theme: null, phase: "endgame", eco: null }, available: 8 }
        : null,
    positions: [],
    related: key === "middlegame_plans" ? ["book_attack_targets", "book_open_files", "book_king_pawns"] : key === "endgame_technique" ? ["book_endgame_king", "book_rook_endings"] : [],
  };
}

const ratings = (): GoalState["ratings"] =>
  scenario === "norating"
    ? []
    : [
        { source: "chesscom", time_class: "rapid", rating: 1812, games: 214, last_played_at: `${iso(-1)}T20:00:00Z` },
        { source: "chesscom", time_class: "blitz", rating: 1694, games: 480, last_played_at: `${iso(-2)}T21:00:00Z` },
        { source: "lichess", time_class: "rapid", rating: 1905, games: 36, last_played_at: `${iso(-40)}T10:00:00Z` },
      ];

export const mockCoachApi = {
  goal: async (): Promise<GoalState> => {
    readScenario();
    return wait({ goal, ratings: ratings() });
  },
  setGoal: async (input: GoalIn): Promise<Goal> => {
    readScenario();
    const option = ratings().find((r) => r.source === input.source && r.time_class === input.time_class);
    const current = option?.rating ?? 1800;
    goal = { ...makeGoal(), source: input.source, time_class: input.time_class, start_rating: current, current_rating: current, target_rating: input.target_rating, minutes_per_day: input.minutes_per_day, days_per_week: input.days_per_week, tz: input.tz, achieved_at: null };
    if (scenario === "nogoal" || scenario === "norating") scenario = "default";
    return wait(goal);
  },
  deleteGoal: async (): Promise<null> => {
    readScenario();
    goal = null;
    scenario = "nogoal";
    return wait(null);
  },
  diagnosis: async (): Promise<Diagnosis> => {
    readScenario();
    return wait(diagnosis());
  },
  today: async (): Promise<Today> => {
    readScenario();
    return wait(todayPlan());
  },
  completeTask: async (id: number): Promise<CoachTask> => {
    readScenario();
    doneIds.add(id);
    const found = weekDays().flatMap((d) => d.tasks).find((t) => t.id === id) ?? todayPlan().tasks.find((t) => t.id === id);
    if (!found) return fail(404, "coach_task_not_found", "Задание не найдено");
    return wait({ ...found, done: true, progress: found.target });
  },
  plan: async (): Promise<Plan> => {
    readScenario();
    return wait(plan());
  },
  rebuildPlan: async (): Promise<Plan> => {
    readScenario();
    return wait(plan(), 700);
  },
  report: async (): Promise<{ report: WeekReport | null }> => {
    readScenario();
    return wait(report());
  },
  forecast: async (): Promise<Forecast> => {
    readScenario();
    return wait(forecast());
  },
  lessons: async (): Promise<{ lessons: LessonItem[] }> => wait({ lessons: [] }),
  lesson: async (key: string): Promise<Lesson> => {
    readScenario();
    return wait(lesson(key));
  },
  readLesson: async (key: string): Promise<LessonItem> => {
    readScenario();
    readLessons.add(key);
    return wait({ key, kind: lesson(key).kind, read: true });
  },
};
