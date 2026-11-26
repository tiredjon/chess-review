// Матчи ботов друг с другом в Node — проверка модели силы (`src/lib/bots/strength.ts`).
// Движок — тот же Stockfish 19 lite single-threaded из `public/engine/` (`scripts/fetch-engine.mjs`),
// каждый бот — отдельный процесс Node; выбор хода — тот же `decideMove`, что в браузере
// (время на раздумье не ждём, только собираем). Дебюты — короткие начала из списка ниже,
// каждое дважды со сменой цветов.
//
//   node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/bots-match.mjs 400:600 1000:1200 [--games 20] [--jobs 3]
//
// Пара `A:B` — A против B; итог — очки B (обычно сильнее) и разница рейтингов по ним.
// Результаты (24 партии, Apple M1, 2026-11-26) — в шапке `src/lib/bots/strength.ts`.
import { cpus } from "node:os";

import { Chess } from "chess.js";

import { decideMove, strengthFor } from "../src/lib/bots/strength.ts";
import { NodeEngine } from "./bots-engine.mjs";

const MAX_PLIES = 400;

const OPENINGS = [
  ["e2e4", "e7e5", "g1f3", "b8c6"],
  ["e2e4", "c7c5", "g1f3", "d7d6"],
  ["d2d4", "d7d5", "c2c4", "e7e6"],
  ["d2d4", "g8f6", "c2c4", "g7g6"],
  ["e2e4", "e7e6", "d2d4", "d7d5"],
  ["e2e4", "c7c6", "d2d4", "d7d5"],
  ["c2c4", "e7e5", "b1c3", "g8f6"],
  ["g1f3", "d7d5", "g2g3", "g8f6"],
  ["e2e4", "d7d5", "e4d5", "d8d5"],
  ["d2d4", "f7f5", "g2g3", "g8f6"],
  ["e2e4", "e7e5", "f1c4", "g8f6"],
  ["d2d4", "d7d5", "c1f4", "g8f6"],
];

/** Партия: `white`, `black` — рейтинги. Итог за белых: 1, ½, 0. */
async function playGame(white, black, opening, engines) {
  const game = new Chess();
  const history = [];
  for (const uci of opening) {
    game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4) });
    history.push(uci);
  }
  await engines.w.newGame();
  await engines.b.newGame();
  const stats = { think: [], search: [] };
  while (!game.isGameOver() && history.length < MAX_PLIES) {
    const side = game.turn();
    const elo = side === "w" ? white : black;
    const started = performance.now();
    const d = await decideMove(engines[side], { fen: game.fen(), historyUci: history }, strengthFor(elo));
    stats.search.push(performance.now() - started);
    stats.think.push(d.thinkMs);
    game.move({ from: d.uci.slice(0, 2), to: d.uci.slice(2, 4), promotion: d.uci[4] });
    history.push(d.uci);
  }
  const result = game.isCheckmate() ? (game.turn() === "w" ? 0 : 1) : 0.5;
  return { result, plies: history.length, stats };
}

function eloDiff(score) {
  if (score <= 0) return -Infinity;
  if (score >= 1) return Infinity;
  return Math.round(-400 * Math.log10(1 / score - 1));
}

async function runPair(a, b, games, jobs) {
  const tasks = Array.from({ length: games }, (_, i) => ({
    opening: OPENINGS[Math.floor(i / 2) % OPENINGS.length],
    bWhite: i % 2 === 1,
  }));
  const results = [];
  const workers = Array.from({ length: Math.min(jobs, games) }, async () => {
    const engines = { w: new NodeEngine(), b: new NodeEngine() };
    await engines.w.init();
    await engines.b.init();
    while (tasks.length) {
      const t = tasks.shift();
      const [white, black] = t.bWhite ? [b, a] : [a, b];
      const g = await playGame(white, black, t.opening, engines);
      results.push({ ...g, scoreB: t.bWhite ? g.result : 1 - g.result });
    }
    engines.w.quit();
    engines.b.quit();
  });
  await Promise.all(workers);
  const sum = results.reduce((s, r) => s + r.scoreB, 0);
  const wins = results.filter((r) => r.scoreB === 1).length;
  const draws = results.filter((r) => r.scoreB === 0.5).length;
  const think = results.flatMap((r) => r.stats.think);
  const search = results.flatMap((r) => r.stats.search);
  const avg = (xs) => Math.round(xs.reduce((s, x) => s + x, 0) / xs.length);
  return {
    pair: `${a} vs ${b}`,
    score: `${sum}/${results.length}`,
    wld: `+${wins} =${draws} −${results.length - wins - draws}`,
    elo: eloDiff(sum / results.length),
    plies: avg(results.map((r) => r.plies)),
    thinkAvg: avg(think),
    thinkMax: Math.max(...think),
    searchMax: Math.round(Math.max(...search)),
  };
}

const args = process.argv.slice(2);
const opt = (name, fallback) => (args.includes(name) ? Number(args[args.indexOf(name) + 1]) : fallback);
const games = opt("--games", 20);
const jobs = opt("--jobs", Math.max(1, Math.floor((cpus().length - 1) / 2)));
const pairs = args.filter((x) => /^\d+:\d+$/.test(x)).map((x) => x.split(":").map(Number));
if (pairs.length === 0) {
  console.error("Пары рейтингов: node scripts/bots-match.mjs 400:600 1000:1200 [--games 20] [--jobs 3]");
  process.exit(1);
}
console.log("пара | очки сильного | +/=/− | Δ Elo | полуходов | раздумье ср/макс, мс | поиск макс, мс");
for (const [a, b] of pairs) {
  const r = await runPair(a, b, games, jobs);
  console.log(`${r.pair} | ${r.score} | ${r.wld} | ${r.elo} | ${r.plies} | ${r.thinkAvg}/${r.thinkMax} | ${r.searchMax}`);
}
