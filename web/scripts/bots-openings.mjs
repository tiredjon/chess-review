// Частоты ходов ботов в типовых дебютных позициях — проверка, что клубные боты в дебюте
// играют «по-человечески» (развитие, центр, взятия), а не выпадами крайними пешками.
// Движок и выбор хода — как в `bots-match.mjs` (тот же `decideMove`).
//
//   node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON scripts/bots-openings.mjs [--samples 20] [--elos 1200,1600,2000] [--lines]
//
// `--lines` — ещё и оценки движка по кандидатам (глубина уровня), чтобы видеть, откуда ход.
import { Chess } from "chess.js";

import { candidatesFrom, decideMove, strengthFor } from "../src/lib/bots/strength.ts";
import { NodeEngine } from "./bots-engine.mjs";

const POSITIONS = [
  ["Сицилианская: 1.e4 c5 2.Nf3 d6 3.d4 Nf6", "e2e4 c7c5 g1f3 d7d6 d2d4 g8f6"],
  ["Сицилианская открытая: …4.Nxd4 Nf6", "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6"],
  ["Сицилианская, ход чёрных: 1.e4 c5 2.Nf3", "e2e4 c7c5 g1f3"],
  ["Испанская: 1.e4 e5 2.Nf3 Nc6 3.Bb5 a6", "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6"],
  ["Испанская, ход чёрных: …4.Ba4", "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4"],
  ["Итальянская: 1.e4 e5 2.Nf3 Nc6 3.Bc4", "e2e4 e7e5 g1f3 b8c6 f1c4"],
  ["Ферзевый гамбит: 1.d4 d5 2.c4", "d2d4 d7d5 c2c4"],
  ["Ферзевый гамбит: 1.d4 d5 2.c4 e6 3.Nc3 Nf6", "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6"],
  ["Принятый ферзевый: 1.d4 d5 2.c4 dxc4", "d2d4 d7d5 c2c4 d5c4"],
  ["Французская: 1.e4 e6 2.d4 d5", "e2e4 e7e6 d2d4 d7d5"],
];

const args = process.argv.slice(2);
const opt = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const samples = Number(opt("--samples", 20));
const elos = opt("--elos", "1200,1400,1600,1800,2000").split(",").map(Number);
const showLines = args.includes("--lines");

const engine = new NodeEngine();
await engine.init();
const san = (fen, uci) => new Chess(fen).move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san;

for (const [title, moves] of POSITIONS) {
  const history = moves.split(" ");
  const game = new Chess();
  history.forEach((u) => game.move({ from: u.slice(0, 2), to: u.slice(2, 4) }));
  const fen = game.fen();
  console.log(`\n${title}`);
  for (const elo of elos) {
    const s = strengthFor(elo);
    const counts = new Map();
    for (let i = 0; i < samples; i++) {
      await engine.newGame();
      const d = await decideMove(engine, { fen, historyUci: history }, s);
      const m = san(fen, d.uci);
      counts.set(m, (counts.get(m) ?? 0) + 1);
    }
    const freq = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([m, n]) => `${m} ${n}`).join(", ");
    console.log(`  ${elo}: ${freq}`);
    if (showLines) {
      const r = await engine.search({ fen, depth: s.depth, multipv: Math.min(s.multipv, 40) });
      const c = candidatesFrom(r.lines).slice(0, 12);
      console.log(`        d${r.depth}: ${c.map((x) => `${san(fen, x.uci)} ${x.cp}`).join(", ")}`);
    }
  }
}
engine.quit();
