// Тесты модели силы ботов (чистая логика `strength.ts`). Запуск из `web/`:
//
//   node --test src/lib/bots/strength.test.mjs
//
// Node 24 исполняет .ts без сборки (снятие типов), поэтому `strength.ts` без алиасов `@/`.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  candidatesFrom,
  clockBudgetMs,
  decideMove,
  lineCp,
  movePrior,
  pickCandidate,
  strengthFor,
  thinkTimeMs,
} from "./strength.ts";

/** Детерминированный генератор (mulberry32). */
function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ELOS = Array.from({ length: 25 }, (_, i) => 400 + i * 100);

test("таблица: опорные уровни и края", () => {
  assert.deepEqual(strengthFor(2800), {
    elo: 2800, depth: 18, multipv: 1, temperature: 0, window: 0, blunderChance: 0, blunderMax: 0,
  });
  assert.equal(strengthFor(400).depth, 1);
  assert.equal(strengthFor(100).depth, strengthFor(400).depth);
  assert.equal(strengthFor(3500).depth, 18);
  // Между опорами — интерполяция.
  const s = strengthFor(1100);
  assert.equal(s.temperature, (45 + 32) / 2);
  assert.ok(s.depth === 4 || s.depth === 5);
});

test("таблица: сила монотонно растёт, без скачков", () => {
  for (let i = 1; i < ELOS.length; i++) {
    const a = strengthFor(ELOS[i - 1]);
    const b = strengthFor(ELOS[i]);
    assert.ok(b.depth >= a.depth && b.depth - a.depth <= 2, `глубина ${a.elo}→${b.elo}`);
    assert.ok(b.temperature <= a.temperature, `T ${b.elo}`);
    assert.ok(b.window <= a.window, `окно ${b.elo}`);
    assert.ok(b.blunderChance <= a.blunderChance, `зевки ${b.elo}`);
    assert.ok(a.blunderChance - b.blunderChance <= 0.05 + 1e-9, `скачок зевков ${b.elo}`);
  }
});

test("оценка линии: мат ближе — лучше", () => {
  assert.equal(lineCp({ cp: 35, pv: ["e2e4"] }), 35);
  assert.ok(lineCp({ mate: 1, pv: ["a"] }) > lineCp({ mate: 3, pv: ["a"] }));
  assert.ok(lineCp({ mate: -1, pv: ["a"] }) < lineCp({ mate: -5, pv: ["a"] }));
  assert.ok(lineCp({ mate: -5, pv: ["a"] }) < -90_000);
});

/** Позиция с висящим конём: взятие +300, остальное ≈ 0, один зевок −500, мат в 1 нет. */
const LINES = [
  { cp: 320, pv: ["d1d5"] },
  { cp: 40, pv: ["g1f3"] },
  { cp: 30, pv: ["b1c3"] },
  { cp: 25, pv: ["h2h3"] },
  { cp: 10, pv: ["a2a3"] },
  { cp: -480, pv: ["f3e5"] },
];

function share(elo, uci, runs = 4000) {
  const rng = seeded(elo);
  const s = strengthFor(elo);
  const cands = candidatesFrom(LINES);
  let hits = 0;
  for (let i = 0; i < runs; i++) if (pickCandidate(cands, s, rng).uci === uci) hits++;
  return hits / runs;
}

test("выбор: висящую фигуру на 1000+ берут почти всегда", () => {
  assert.ok(share(1000, "d1d5") > 0.9, `1000: ${share(1000, "d1d5")}`);
  assert.ok(share(1500, "d1d5") > 0.97);
  assert.equal(share(2800, "d1d5"), 1);
});

test("выбор: 400 часто ошибается и зевает, сильнее — реже", () => {
  const take400 = share(400, "d1d5");
  assert.ok(take400 > 0.2 && take400 < 0.8, `400 берёт: ${take400}`);
  assert.ok(share(400, "f3e5") > 0.05, "400 иногда зевает фигуру");
  assert.ok(share(1200, "f3e5") < 0.03);
  assert.equal(share(2000, "f3e5"), 0);
  // Плавно: каждый следующий уровень берёт не реже предыдущего (с допуском на случайность).
  let prev = 0;
  for (const elo of [400, 600, 800, 1000, 1200, 1500]) {
    const v = share(elo, "d1d5");
    assert.ok(v + 0.03 >= prev, `${elo}: ${v} < ${prev}`);
    prev = v;
  }
});

test("выбор: детерминирован при одном генераторе", () => {
  const cands = candidatesFrom(LINES);
  const run = () => Array.from({ length: 50 }, ((rng) => () => pickCandidate(cands, strengthFor(700), rng).uci)(seeded(7)));
  assert.deepEqual(run(), run());
});

test("выбор: единственный ход и T=0 — лучший", () => {
  const one = candidatesFrom([{ cp: -900, pv: ["e1f1"] }]);
  assert.equal(pickCandidate(one, strengthFor(400), seeded(1)).uci, "e1f1");
});

/** Ход белых для `movePrior` (SAN условный). */
const mv = (piece, from, to, extra = {}) => ({ color: "w", piece, from, to, san: piece.toUpperCase() + to, flags: "n", ...extra });

test("предпочтения: король в миттельшпиле — редкость, рокировка и развитие — охотно", () => {
  const ctx = { fullmove: 8, heavyMaterial: true, undeveloped: 2 };
  const king = movePrior(mv("k", "e1", "e2"), ctx);
  const castle = movePrior(mv("k", "e1", "g1", { san: "O-O", flags: "k" }), ctx);
  const knight = movePrior(mv("n", "g1", "f3"), ctx);
  assert.ok(king < 0.1);
  assert.ok(castle > 1 && knight > 1);
  // В миттельшпиле король — реже, в эндшпиле — свободно.
  assert.equal(movePrior(mv("k", "e1", "e2"), { fullmove: 20, heavyMaterial: true }), 0.12);
  assert.equal(movePrior(mv("k", "e1", "e2"), { fullmove: 50, heavyMaterial: false }), 1);
});

test("предпочтения: в дебюте центр и развитие, а не выпады крайними пешками (4.h4 в сицилианской)", () => {
  const ctx = { fullmove: 4, heavyMaterial: true, undeveloped: 3 };
  const h4 = movePrior(mv("p", "h2", "h4", { san: "h4" }), ctx);
  const nc3 = movePrior(mv("n", "b1", "c3"), ctx);
  const e5 = movePrior(mv("p", "e4", "e5", { san: "e5" }), ctx);
  const dxc5 = movePrior(mv("p", "d4", "c5", { san: "dxc5", captured: "p", flags: "c" }), ctx);
  assert.ok(h4 <= 0.05);
  assert.ok(nc3 / h4 >= 10 && e5 / h4 >= 10 && dxc5 / h4 >= 10);
  // Фианкетто и «форточка» — мягче, чем выпад.
  assert.ok(movePrior(mv("p", "g2", "g3", { san: "g3" }), ctx) > movePrior(mv("p", "h2", "h3", { san: "h3" }), ctx));
  assert.ok(movePrior(mv("p", "h2", "h3", { san: "h3" }), ctx) > h4);
  // Конь на край, ладья, отступление на исходное — редкость; шах и взятие от штрафов свободны.
  assert.ok(movePrior(mv("n", "f3", "h4"), ctx) < 0.3);
  assert.ok(movePrior(mv("r", "h1", "h3"), ctx) < 0.3);
  assert.ok(movePrior(mv("b", "e2", "f1"), ctx) < 0.2);
  assert.ok(movePrior(mv("q", "d1", "a4", { san: "Qa4+" }), ctx) > 1);
  // После дебюта — без дебютных множителей.
  assert.equal(movePrior(mv("p", "h2", "h4", { san: "h4" }), { fullmove: 25, heavyMaterial: true }), 1);
});

test("время: единственный ход и взятие назад — быстро, сложная позиция — дольше, ≤ 3 с", () => {
  const rng = seeded(3);
  const close = candidatesFrom([0, -5, -10, -20, -30, -35].map((cp, i) => ({ cp, pv: [`m${i}`] })));
  const forced = candidatesFrom([{ cp: 0, pv: ["a"] }, { cp: -400, pv: ["b"] }]);
  for (let i = 0; i < 200; i++) {
    assert.ok(thinkTimeMs({ legalMoves: 1, fullmove: 20, recapture: false, candidates: forced }, rng) <= 500);
    assert.ok(thinkTimeMs({ legalMoves: 30, fullmove: 20, recapture: true, candidates: forced }, rng) <= 800);
    const hard = thinkTimeMs({ legalMoves: 30, fullmove: 20, recapture: false, candidates: close }, rng);
    assert.ok(hard >= 1500 && hard <= 3000, `сложная: ${hard}`);
    const opening = thinkTimeMs({ legalMoves: 20, fullmove: 1, recapture: false, candidates: close }, rng);
    assert.ok(opening >= 300 && opening <= 1200, `дебют: ${opening}`);
  }
});

/** Движок-заглушка: отдаёт готовые линии. */
const fakeEngine = (lines) => ({
  calls: [],
  async search(options) {
    this.calls.push(options);
    return { depth: options.depth, lines };
  },
});

test("decideMove: ход легален, MultiPV не больше числа ходов, нелегальные линии отброшены", async () => {
  const engine = fakeEngine([{ cp: 50, pv: ["e7e5"] }, { cp: 999, pv: ["e2e4"] }, { cp: 20, pv: ["g8f6"] }]);
  const fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
  const d = await decideMove(engine, { fen, historyUci: ["e2e4"] }, strengthFor(2800), seeded(1));
  assert.equal(d.uci, "e7e5");
  assert.equal(d.cp, 50);
  assert.equal(engine.calls[0].multipv, 1);
  assert.ok(d.thinkMs >= 300 && d.thinkMs <= 3000);
});

test("decideMove: выигрывая, не повторяет позицию в третий раз", async () => {
  // Кони туда-обратно дважды: следующий Ng1 даст троекратное повторение.
  const cycle = ["g1f3", "g8f6", "f3g1", "f6g8"];
  const history = [...cycle, ...cycle, "g1f3", "g8f6"];
  const fen = "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 10 6";
  const engine = fakeEngine([{ cp: 200, pv: ["f3g1"] }, { cp: 150, pv: ["e2e4"] }]);
  const d = await decideMove(engine, { fen, historyUci: history }, strengthFor(2800), seeded(1));
  assert.equal(d.uci, "e2e4");
  // Проигрывая — берёт ничью.
  const losing = fakeEngine([{ cp: -300, pv: ["e2e4"] }, { cp: -400, pv: ["f3g1"] }]);
  const d2 = await decideMove(losing, { fen, historyUci: history }, strengthFor(2800), seeded(1));
  assert.equal(d2.uci, "f3g1");
});

test("decideMove: взятие назад — быстро", async () => {
  // 1. e4 d5 2. exd5 — чёрные берут назад ферзём.
  const fen = "rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2";
  const engine = fakeEngine([{ cp: 0, pv: ["d8d5"] }, { cp: -250, pv: ["g8f6"] }]);
  const d = await decideMove(engine, { fen, historyUci: ["e2e4", "d7d5", "e4d5"] }, strengthFor(2800), seeded(2));
  assert.equal(d.uci, "d8d5");
  assert.ok(d.thinkMs <= 800, `${d.thinkMs}`);
});

test("clockBudgetMs: ~1/30 остатка плюс добавка, в цейтноте быстрее, не больше половины остатка", () => {
  assert.equal(clockBudgetMs(60_000, 0), 2000);
  assert.equal(clockBudgetMs(180_000, 2000), 7600);
  assert.ok(clockBudgetMs(5_000, 0) < 500);
  assert.equal(clockBudgetMs(150, 0), 100);
  assert.ok(clockBudgetMs(1_000, 5_000) <= 500);
});
