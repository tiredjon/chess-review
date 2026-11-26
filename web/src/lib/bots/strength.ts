// Модель силы ботов 400…2800 и выбор хода — чистая логика без браузера и без алиасов `@/`
// (её же исполняет Node: тесты `node --test`, матчи `scripts/bots-match.mjs`).
//
// Как играет бот. Один поиск Stockfish с MultiPV на малой глубине даёт оценки кандидатов;
// бот берёт ход случайно с весом exp(−потеря/T) среди ходов не хуже лучшего на «окно», а с
// вероятностью «зевка» — ход заметно хуже (до «предела зевка»). Глубина, MultiPV, T, окно и
// зевки плавно меняются с рейтингом (`strengthFor` — линейная интерполяция по опорной таблице).
// Поверх — «человеческие» поправки: король без нужды не гуляет, взятия и развитие охотнее.
//
// Почему не `UCI_LimitStrength`/`UCI_Elo` для 1320+: (1) при включённом Skill Stockfish
// выбирает ход уже после того, как напечатал линии, и сообщает его только в `bestmove`, а
// `Stockfish.search` (`lib/engine/stockfish.ts`) возвращает линии, не `bestmove`, — выбор Skill
// потерялся бы; (2) `UCI_Elo` откалиброван против движков на коротком контроле (шкала CCRL),
// а не против людей: Stockfish «1320» почти не зевает фигур, как зевают люди 1300, и его ошибки
// не похожи на человеческие; (3) одна модель на всю шкалу — без шва на 1320. Поэтому 2800 —
// почти полная сила lite-сети на глубине 18 (за пределом времени), а ниже сила снимается той же
// моделью: меньше глубина, больше разброс и зевков.
//
// Проверка матчами бот против бота (`node scripts/bots-match.mjs`, 24 партии, Apple M1),
// очки сильного и разница рейтингов по ним:
//   400 vs 600    17.5/24 (+14 =7 −3)   ≈ +172   (2026-11-26, после сглаживания низа)
//   1000 vs 1200  17.5/24 (+17 =1 −6)   ≈ +172   (то же)
//   1500 vs 1700  18.5/24 (+15 =7 −2)   ≈ +211   (до дебютных множителей `OPENING_PRIOR`)
//   2400 vs 2800  15.5/24 (+7 =17 −0)   ≈ +104   (то же)
// До сглаживания низ был круче номинала: 400 vs 600 — 23/24 (≈ +545), 1000 vs 1200 — 20.5/24.
// Дебютный вкус проверяет `node scripts/bots-openings.mjs` (частоты ходов по уровням).

import { Chess, type Move, type Square } from "chess.js";

/** Параметры силы одного уровня. */
export type Strength = {
  elo: number;
  /** Глубина поиска Stockfish. */
  depth: number;
  /** Сколько линий MultiPV (больше, чем ходов, — все ходы). */
  multipv: number;
  /** «Температура», сантипешки: чем больше, тем охотнее берутся не лучшие ходы окна. 0 — лучший. */
  temperature: number;
  /** Окно, сантипешки: обычный ход — не хуже лучшего на столько. */
  window: number;
  /** Вероятность зевка — хода хуже окна. */
  blunderChance: number;
  /** Предел зевка, сантипешки: насколько хуже лучшего может быть зевок. */
  blunderMax: number;
};

// Опорные уровни; между ними — линейная интерполяция (глубина и MultiPV округляются).
// 400 — зевает фигуры почти каждые несколько ходов; 1000 — висящую фигуру обычно берёт, но
// тактику видит на 2–3 полухода; 1500 — крепкий клубный, крупно зевает редко; 2000+ — точная
// игра с редкими неточностями; 2800 — без намеренных ошибок.
const ANCHORS: readonly Strength[] = [
  { elo: 400, depth: 1, multipv: 500, temperature: 110, window: 300, blunderChance: 0.24, blunderMax: 900 },
  { elo: 600, depth: 1, multipv: 500, temperature: 90, window: 250, blunderChance: 0.19, blunderMax: 800 },
  { elo: 800, depth: 2, multipv: 500, temperature: 70, window: 200, blunderChance: 0.14, blunderMax: 650 },
  { elo: 1000, depth: 4, multipv: 500, temperature: 45, window: 150, blunderChance: 0.08, blunderMax: 450 },
  { elo: 1200, depth: 5, multipv: 500, temperature: 32, window: 110, blunderChance: 0.05, blunderMax: 350 },
  { elo: 1500, depth: 7, multipv: 24, temperature: 20, window: 70, blunderChance: 0.025, blunderMax: 250 },
  { elo: 1800, depth: 9, multipv: 12, temperature: 12, window: 45, blunderChance: 0.012, blunderMax: 180 },
  { elo: 2100, depth: 11, multipv: 8, temperature: 7, window: 30, blunderChance: 0.005, blunderMax: 120 },
  { elo: 2400, depth: 13, multipv: 5, temperature: 3, window: 18, blunderChance: 0.002, blunderMax: 80 },
  { elo: 2800, depth: 18, multipv: 1, temperature: 0, window: 0, blunderChance: 0, blunderMax: 0 },
];

export const STRENGTH_MIN_ELO = ANCHORS[0].elo;
export const STRENGTH_MAX_ELO = ANCHORS[ANCHORS.length - 1].elo;

/** Предел времени одного поиска, мс: ответ не позже ~3 с и на слабом ноутбуке. В матчах при
 *  8 процессах на 8 ядрах поиск 2800 с пределом 2500 занимал до 4.4 с (перегруз CPU) — с
 *  запасом 2000. */
export const SEARCH_MOVETIME_MS = 2000;

/** Параметры уровня; рейтинг вне 400…2800 прижимается к краю. */
export function strengthFor(elo: number): Strength {
  const e = Math.min(STRENGTH_MAX_ELO, Math.max(STRENGTH_MIN_ELO, elo));
  const hi = ANCHORS.findIndex((a) => a.elo >= e);
  const b = ANCHORS[hi];
  if (b.elo === e) return { ...b, elo };
  const a = ANCHORS[hi - 1];
  const t = (e - a.elo) / (b.elo - a.elo);
  const lerp = (x: number, y: number) => x + (y - x) * t;
  return {
    elo,
    depth: Math.round(lerp(a.depth, b.depth)),
    multipv: Math.round(lerp(a.multipv, b.multipv)),
    temperature: lerp(a.temperature, b.temperature),
    window: lerp(a.window, b.window),
    blunderChance: lerp(a.blunderChance, b.blunderChance),
    blunderMax: lerp(a.blunderMax, b.blunderMax),
  };
}

/** Линия движка (как `EngineLine` в `lib/engine/uci.ts`): оценка за сторону на ходу. */
export type Line = { cp?: number; mate?: number; pv: string[] };

const MATE_CP = 100_000;

/** Оценка линии в сантипешках; мат в N — ±(100000 − N), чтобы быстрый мат был лучше. */
export function lineCp(line: Line): number {
  if (line.mate === undefined) return line.cp ?? 0;
  if (line.mate > 0) return MATE_CP - line.mate;
  return -MATE_CP - line.mate; // mate ≤ 0: −100000 + |N|
}

/** Потери считаются до этого предела: «зевнул ферзя» и «получил мат» — одинаково плохо. */
const LOSS_CAP = 2000;

export type Candidate = {
  uci: string;
  /** Оценка после хода за бота. */
  cp: number;
  /** Насколько хуже лучшего, сантипешки (0…LOSS_CAP). */
  loss: number;
  /** Множитель «человеческого» предпочтения хода (`movePrior`). */
  prior: number;
};

/** Ход, который удобно оценивать без доски: что ходит, что берёт. */
type MoveInfo = Pick<Move, "color" | "piece" | "from" | "to" | "captured" | "promotion" | "san" | "flags">;

/** Сколько полных ходов считается дебютом для `movePrior`. */
const OPENING_MOVES = 12;

/** Множители «дебютного вкуса»: на малой глубине движок оценивает многие ходы почти поровну
 *  (после 1.e4 c5 2.Nf3 на глубине 8 …h5 хуже лучшего всего на ~40 cp), и без них клубный
 *  бот играл 4.h4 в сицилианской. Человек в дебюте развивает фигуры, борется за центр, берёт
 *  и рокируется; выпады крайними пешками, конь на край, ранние ходы ладьёй, королём и ферзём,
 *  отступления на исходное — редкость. */
const OPENING_PRIOR = {
  develop: 1.5, // конь или слон с исходного поля
  castle: 2,
  centerPawn: 1.4, // пешки c–f
  fianchetto: 0.6, // b3/g3/b6/g6 на одно поле
  luft: 0.35, // a3/h3/a6/h6 на одно поле
  flankPawn: 0.05, // остальные ходы пешками a, b, g, h
  rimKnight: 0.25, // конь на вертикаль a или h
  rook: 0.25,
  earlyQueen: 0.35, // ферзь до 7-го хода
  king: 0.05,
  backToHome: 0.1, // лёгкая фигура назад на первую линию
  sameMinorAgain: 0.6, // лёгкая фигура ходит второй раз, пока другие не развиты
};

/** Человеческие предпочтения (множитель веса хода; взятия, шахи, превращения от дебютных
 *  штрафов освобождены): король в миттельшпиле без нужды не ходит (иначе слабый бот шагает
 *  королём «на равных» с другими ходами), взятия и шахи заметнее, в дебюте — `OPENING_PRIOR`. */
export function movePrior(move: MoveInfo, ctx: { fullmove: number; heavyMaterial: boolean; undeveloped?: number }): number {
  let prior = 1;
  const castle = move.flags.includes("k") || move.flags.includes("q");
  const forcing = Boolean(move.captured || move.promotion || move.san.includes("+"));
  if (move.captured) prior *= 1.6;
  if (move.san.includes("+")) prior *= 1.3;
  if (castle) return prior * (ctx.fullmove <= OPENING_MOVES ? OPENING_PRIOR.castle : 1);
  if (move.piece === "k" && ctx.heavyMaterial && !move.captured) prior *= ctx.fullmove <= OPENING_MOVES ? OPENING_PRIOR.king : 0.12;
  if (ctx.fullmove > OPENING_MOVES || forcing) return prior;

  const home = move.color === "w" ? "1" : "8";
  const file = move.from[0];
  const step = Math.abs(Number(move.to[1]) - Number(move.from[1]));
  const P = OPENING_PRIOR;
  switch (move.piece) {
    case "p":
      if ("cdef".includes(file)) prior *= P.centerPawn;
      else if (step === 1 && "bg".includes(file)) prior *= P.fianchetto;
      else if (step === 1 && "ah".includes(file)) prior *= P.luft;
      else prior *= P.flankPawn;
      break;
    case "n":
    case "b":
      if (move.from[1] === home) prior *= P.develop;
      else if (move.to[1] === home) prior *= P.backToHome;
      else if ((ctx.undeveloped ?? 0) >= 2) prior *= P.sameMinorAgain;
      if (move.piece === "n" && "ah".includes(move.to[0])) prior *= P.rimKnight;
      break;
    case "r":
      prior *= P.rook;
      break;
    case "q":
      if (ctx.fullmove < 7) prior *= P.earlyQueen;
      break;
  }
  return prior;
}

/** Кандидаты из линий MultiPV (линии без хода пропускаются). */
export function candidatesFrom(lines: readonly Line[], priorOf: (uci: string) => number = () => 1): Candidate[] {
  const scored = lines.filter((l) => l.pv.length > 0).map((l) => ({ uci: l.pv[0], cp: lineCp(l) }));
  if (scored.length === 0) return [];
  const best = Math.max(...scored.map((c) => c.cp));
  return scored.map((c) => ({ ...c, loss: Math.min(LOSS_CAP, best - c.cp), prior: priorOf(c.uci) }));
}

function weightedPick<T>(items: readonly T[], weight: (item: T) => number, rng: () => number): T {
  const weights = items.map(weight);
  const total = weights.reduce((s, w) => s + w, 0);
  if (!(total > 0)) return items[0];
  let r = rng() * total;
  for (let i = 0; i < items.length; i++) {
    r -= weights[i];
    if (r < 0) return items[i];
  }
  return items[items.length - 1];
}

/** Выбор хода по уровню. `candidates` — по убыванию оценки (как MultiPV), непустой. */
export function pickCandidate(candidates: readonly Candidate[], s: Strength, rng: () => number): Candidate {
  if (candidates.length === 1 || s.temperature <= 0) return minLoss(candidates);
  if (rng() < s.blunderChance) {
    // Зевок: ход хуже окна, но не хуже предела; чем грубее, тем реже.
    const bad = candidates.filter((c) => c.loss > s.window && c.loss <= s.blunderMax);
    if (bad.length > 0) return weightedPick(bad, (c) => c.prior * Math.exp(-c.loss / (s.blunderMax / 2)), rng);
  }
  const ok = candidates.filter((c) => c.loss <= s.window);
  return weightedPick(ok, (c) => c.prior * Math.exp(-c.loss / s.temperature), rng);
}

function minLoss(candidates: readonly Candidate[]): Candidate {
  return candidates.reduce((best, c) => (c.loss < best.loss ? c : best));
}

// --- Время на раздумье ---

export type ThinkContext = {
  /** Сколько легальных ходов. */
  legalMoves: number;
  /** Полный ход партии (FEN). */
  fullmove: number;
  /** Ход — взятие на поле, где соперник только что взял (размен). */
  recapture: boolean;
  /** Кандидаты (по ним — «сложность»: сколько ходов близки к лучшему). */
  candidates: readonly Candidate[];
};

/** Время на раздумье, мс (≈ 0.3–3 с): мгновенно не ходит, единственный ход и взятие назад —
 *  быстро, дебют — быстро, позиция с несколькими близкими ходами — дольше. */
export function thinkTimeMs(ctx: ThinkContext, rng: () => number): number {
  const jitter = 0.75 + rng() * 0.55;
  if (ctx.legalMoves <= 1) return Math.round(300 + rng() * 200);
  const sorted = [...ctx.candidates].sort((a, b) => a.loss - b.loss);
  const gap = sorted.length > 1 ? sorted[1].loss : LOSS_CAP;
  if (ctx.recapture && gap >= 150) return Math.round(400 + rng() * 400);
  if (ctx.fullmove <= 4) return Math.round((550 + ctx.fullmove * 120) * jitter);
  const close = ctx.candidates.filter((c) => c.loss <= 40).length;
  const complexity = Math.min(5, close) + (gap >= 300 ? -1 : 0);
  return Math.round(Math.min(3000, Math.max(600, (900 + 380 * complexity) * jitter)));
}

// --- Ход бота целиком: поиск → выбор → время ---

/** Что нужно от движка (подмножество `Stockfish` из `lib/engine/stockfish.ts`). */
export interface BotEngine {
  search(options: {
    fen: string;
    depth: number;
    multipv?: number;
    movetime?: number;
    signal?: AbortSignal;
  }): Promise<{ depth: number; lines: Line[] }>;
}

export type Decision = {
  uci: string;
  /** Оценка после хода за бота (мат — ±100000). */
  cp: number;
  /** Сколько бот «думает» всего, мс (включая сам поиск). */
  thinkMs: number;
};

/** Ключ позиции для повторений: расстановка, очередь, рокировки, взятие на проходе. */
function positionKey(fen: string): string {
  return fen.split(" ").slice(0, 4).join(" ");
}

type History = {
  /** Сколько раз встречалась каждая позиция партии (с текущей). */
  counts: Map<string, number>;
  /** Поле, на котором соперник только что взял фигуру. */
  lastCaptureSquare?: string;
};

/** Проигрывает историю с начальной позиции. История не ведёт к `fen` (партия с позиции) —
 *  повторения считаются только для текущей позиции. */
function replayHistory(fen: string, historyUci: readonly string[]): History {
  const counts = new Map<string, number>();
  const bump = (f: string) => counts.set(positionKey(f), (counts.get(positionKey(f)) ?? 0) + 1);
  const game = new Chess();
  bump(game.fen());
  let lastCaptureSquare: string | undefined;
  try {
    for (const uci of historyUci) {
      const move = game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
      lastCaptureSquare = move.captured ? move.to : undefined;
      bump(game.fen());
    }
    if (positionKey(game.fen()) === positionKey(fen)) return { counts, lastCaptureSquare };
  } catch {
    // нелегальная история — как партия с позиции
  }
  return { counts: new Map([[positionKey(fen), 1]]) };
}

const uciOf = (m: Move) => m.from + m.to + (m.promotion ?? "");

export async function decideMove(
  engine: BotEngine,
  request: { fen: string; historyUci: readonly string[]; signal?: AbortSignal },
  s: Strength,
  rng: () => number = Math.random,
): Promise<Decision> {
  const board = new Chess(request.fen);
  const legal = board.moves({ verbose: true });
  if (legal.length === 0) throw new Error("У бота нет ходов");
  const byUci = new Map(legal.map((m) => [uciOf(m), m]));
  const fullmove = Number(request.fen.split(" ")[5]) || 1;
  const pieces = board.board().flat().filter((sq) => sq && sq.type !== "p" && sq.type !== "k");
  // Король прячется, пока на доске ферзи или много фигур.
  const heavyMaterial = pieces.some((sq) => sq!.type === "q") || pieces.length > 6;
  // Сколько своих коней и слонов ещё на исходных полях.
  const homeSquares = board.turn() === "w" ? ["b1", "c1", "f1", "g1"] : ["b8", "c8", "f8", "g8"];
  const undeveloped = homeSquares.filter((sq) => {
    const p = board.get(sq as Square);
    return p && p.color === board.turn() && (p.type === "n" || p.type === "b");
  }).length;

  const result = await engine.search({
    fen: request.fen,
    depth: s.depth,
    multipv: Math.min(s.multipv, legal.length),
    movetime: SEARCH_MOVETIME_MS,
    signal: request.signal,
  });
  let candidates = candidatesFrom(
    result.lines.filter((l) => byUci.has(l.pv[0])),
    (uci) => movePrior(byUci.get(uci)!, { fullmove, heavyMaterial, undeveloped }),
  );
  if (candidates.length === 0) {
    // Движок не дал линий (отменён предел?) — любой легальный ход лучше зависания партии.
    return { uci: uciOf(legal[0]), cp: 0, thinkMs: 500 };
  }

  // Троекратное повторение: движок видит только FEN, без истории. Выигрывая — не повторяет,
  // проигрывая — берёт ничью.
  const history = replayHistory(request.fen, request.historyUci);
  const repeats = (uci: string) => {
    const after = new Chess(request.fen);
    after.move(byUci.get(uci)!);
    return (history.counts.get(positionKey(after.fen())) ?? 0) >= 2;
  };
  const best = Math.max(...candidates.map((c) => c.cp));
  if (best > 50) {
    const rest = candidates.filter((c) => !repeats(c.uci));
    if (rest.length > 0 && rest.length < candidates.length) candidates = rebase(rest);
  } else if (best < -150) {
    const draw = candidates.find((c) => repeats(c.uci));
    if (draw) candidates = [{ ...draw, cp: 0, loss: 0 }];
  }

  const chosen = pickCandidate(candidates, s, rng);
  const move = byUci.get(chosen.uci)!;
  const recapture = Boolean(move.captured && move.to === history.lastCaptureSquare);
  const thinkMs = thinkTimeMs({ legalMoves: legal.length, fullmove, recapture, candidates }, rng);
  return { uci: chosen.uci, cp: chosen.cp, thinkMs };
}

/** Потери заново — от лучшего из оставшихся кандидатов. */
function rebase(candidates: readonly Candidate[]): Candidate[] {
  const top = Math.max(...candidates.map((c) => c.cp));
  return candidates.map((c) => ({ ...c, loss: Math.min(LOSS_CAP, top - c.cp) }));
}
