// Тесты книги соперника в партии по курсу (сессия 14.3):
//   cd web && node --test src/components/courses/play-book.test.mjs
// .mjs, а не .ts: импорт `./play-book.ts` с расширением tsc без allowImportingTsExtensions не примет.
import assert from "node:assert/strict";
import { test } from "node:test";
import { courseBook, courseLines, lineProgress, lineThrough, nodeAfter, numbered, pickRandomLine, playIndex } from "./play-book.ts";

// Курс за чёрных: 1.e4 c5 2.Nf3 (70%) / 2.Nc3 (30%); после 2.Nf3 d6 — 3.d4 (80%) / 3.Bb5+ (20%);
// после 2.Nf3 у ученика есть и 2…e6 (другая ветка дерева).
const node = (id, parent, children, uci, san, mover, weight = 1, name = null) => ({
  id,
  parent,
  children,
  ply: 0,
  uci,
  san,
  mover,
  name,
  weight,
});
const nodes = [
  node(0, null, [1], null, null, null),
  node(1, 0, [2], "e2e4", "e4", "opponent", 1, "King's Pawn"),
  node(2, 1, [3, 4], "c7c5", "c5", "learner", 1, "Sicilian Defense"),
  node(3, 2, [5, 10], "g1f3", "Nf3", "opponent", 0.7),
  node(4, 2, [9], "b1c3", "Nc3", "opponent", 0.3, "Sicilian Defense: Closed"),
  node(5, 3, [6, 8], "d7d6", "d6", "learner"),
  node(6, 5, [7], "d2d4", "d4", "opponent", 0.8),
  node(7, 6, [], "c5d4", "cxd4", "learner", 1, "Sicilian Defense: Open"),
  node(8, 5, [], "f1b5", "Bb5+", "opponent", 0.2),
  node(9, 4, [], "b8c6", "Nc6", "learner"),
  node(10, 3, [11], "e7e6", "e6", "learner"),
  node(11, 10, [], "d2d4", "d4", "opponent"),
];
const index = playIndex(nodes);
const lines = courseLines(index);

test("варианты — листья в порядке обхода, с отходом от основной и названием", () => {
  assert.deepEqual(
    lines.map((l) => l.uci.join(" ")),
    ["e2e4 c7c5 g1f3 d7d6 d2d4 c5d4", "e2e4 c7c5 g1f3 d7d6 f1b5", "e2e4 c7c5 g1f3 e7e6 d2d4", "e2e4 c7c5 b1c3 b8c6"],
  );
  assert.deepEqual(
    lines.map((l) => l.fork),
    [-1, 4, 3, 2],
  );
  assert.deepEqual(
    lines.map((l) => l.name),
    ["Sicilian Defense: Open", "Sicilian Defense", "Sicilian Defense", "Sicilian Defense: Closed"],
  );
  assert.deepEqual(
    lines.map((l) => Math.round(l.weight * 100)),
    [56, 14, 70, 30],
  );
});

test("линия через узел — дальше по основным ходам", () => {
  assert.equal(lineThrough(index, lines, 2), 0);
  assert.equal(lineThrough(index, lines, 8), 1);
  assert.equal(lineThrough(index, lines, 10), 2);
  assert.equal(lineThrough(index, lines, 4), 3);
  assert.equal(lineThrough(index, lines, 99), null);
});

test("соперник ходит по выбранной линии", () => {
  const book = courseBook(index, lines[1]);
  assert.equal(book([]), "e2e4");
  assert.equal(book(["e2e4", "c7c5"]), "g1f3");
  // По дереву здесь был бы 3.d4 (80%), но выбрана линия с 3.Bb5+.
  assert.equal(book(["e2e4", "c7c5", "g1f3", "d7d6"]), "f1b5");
  assert.equal(courseBook(index, lines[3])(["e2e4", "c7c5"]), "b1c3");
});

test("ученик сошёл с линии в дереве — ответ по наибольшему весу; вне дерева — null", () => {
  // Линия 2 ждёт 2…d6 3.Bb5+, ученик сыграл 2…e6 — соперник отвечает по дереву.
  const book = courseBook(index, lines[1]);
  assert.equal(book(["e2e4", "c7c5", "g1f3", "e7e6"]), "d2d4");
  // Линия 4 (2.Nc3), но в партии 2.Nf3 d6 — ответ по наибольшему весу: 3.d4.
  assert.equal(courseBook(index, lines[3])(["e2e4", "c7c5", "g1f3", "d7d6"]), "d2d4");
  // Позиции нет в дереве.
  assert.equal(book(["e2e4", "e7e5"]), null);
  // Лист: соперникам больше нечем отвечать.
  assert.equal(book(["e2e4", "c7c5", "b1c3", "b8c6"]), null);
  // Линия кончилась ходом соперника, дальше дерева нет.
  assert.equal(book(["e2e4", "c7c5", "g1f3", "d7d6", "f1b5", "b8d7"]), null);
});

test("«случайная» — случайно по весам", () => {
  const history = ["e2e4", "c7c5", "g1f3", "d7d6"];
  const off = { uci: [] };
  assert.equal(courseBook(index, off, "random", () => 0.1)(history), "d2d4");
  assert.equal(courseBook(index, off, "random", () => 0.9)(history), "f1b5");
  // Веса линий 0.56 / 0.14 / 0.70 / 0.30 (из 1.70).
  assert.equal(pickRandomLine(lines, () => 0.0)?.n, 0);
  assert.equal(pickRandomLine(lines, () => 0.35)?.n, 1);
  assert.equal(pickRandomLine(lines, () => 0.6)?.n, 2);
  assert.equal(pickRandomLine(lines, () => 0.99)?.n, 3);
});

test("где мы: по линии, отход в дерево, выход из курса", () => {
  const line = lines[0];
  const onLine = lineProgress(index, line, ["e2e4", "c7c5", "g1f3"], false);
  assert.equal(onLine.matched, 3);
  assert.equal(onLine.lineExit, null);
  assert.equal(onLine.bookOver, false);

  // 2…e6 вместо d6 — другой ход из дерева.
  const branch = lineProgress(index, line, ["e2e4", "c7c5", "g1f3", "e7e6", "d2d4"], false);
  assert.equal(branch.lineExit?.ply, 4);
  assert.equal(branch.lineExit?.expectedSan, "d6");
  assert.equal(branch.lineExit?.playedSan, "e6");
  assert.equal(branch.lineExitInTree, true);
  assert.equal(branch.treeExit, null);
  assert.equal(branch.inTreePlies, 5);
  // Лист 3.d4 — ход ученика, а у дерева дальше ничего: курс кончился.
  assert.equal(branch.bookOver, true);

  // 2…Nc6 — такого хода в дереве нет: выход из курса.
  const out = lineProgress(index, line, ["e2e4", "c7c5", "g1f3", "b8c6"], false);
  assert.equal(out.matched, 3);
  assert.equal(out.lineExit?.ply, 4);
  assert.equal(out.lineExit?.nodeId, 3);
  assert.equal(out.lineExitInTree, false);
  assert.equal(out.treeExit?.expected, "d7d6");
  assert.equal(out.treeExit?.ply, 4);
  assert.equal(out.node, null);
  assert.equal(out.bookOver, true);

  // Соперник отошёл от линии (книга линии 2 сыграла бы Bb5+) — отхода ученика нет.
  const other = lineProgress(index, lines[1], ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4"], false);
  assert.equal(other.matched, 4);
  assert.equal(other.lineExit, null);
  assert.equal(other.bookOver, false);

  const done = lineProgress(index, line, line.uci, false);
  assert.equal(done.completed, true);
  assert.equal(done.bookOver, true);
});

test("узел после ходов и номер хода", () => {
  assert.equal(nodeAfter(index, ["e2e4", "c7c5"])?.id, 2);
  assert.equal(nodeAfter(index, ["d2d4"]), null);
  assert.equal(numbered(11, "Bg5"), "6.Bg5");
  assert.equal(numbered(12, "e5"), "6…e5");
});
