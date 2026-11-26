// Тесты цели тренажёра эндшпиля (сессия 16.3):
//   cd web && node --test src/components/endgames/goal.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  bestMoves,
  bookMoveFrom,
  DRAW_HOLD_MOVES,
  effectiveGoal,
  evaluateGoal,
  flipWdl,
  humanPlies,
  pieceCount,
  wdlOf,
} from "./goal.ts";

const tb = (entries) => new Map(entries);

test("ходы человека считаются от очереди в начальной позиции", () => {
  assert.deepEqual(humanPlies("white", "white", 5), [1, 3, 5]);
  assert.deepEqual(humanPlies("black", "black", 4), [1, 3]);
  assert.deepEqual(humanPlies("black", "white", 4), [2, 4]);
});

test("win: мат — успех, таблицы держат выигрыш", () => {
  const status = evaluateGoal({
    goal: "win",
    human: "white",
    firstMover: "white",
    plies: 5,
    tbAfter: tb([[1, "win"], [3, "win"], [5, "win"]]),
    end: { reason: "checkmate", winner: "white" },
  });
  assert.equal(status.state, "success");
  assert.equal(status.reason, "mate");
});

test("win: первый ход, после которого таблицы не выигрыш, — момент упущенного выигрыша", () => {
  const status = evaluateGoal({
    goal: "win",
    human: "white",
    firstMover: "white",
    plies: 6,
    tbAfter: tb([[1, "win"], [3, "draw"], [5, "loss"]]),
    end: null,
  });
  assert.deepEqual(status, { state: "failure", reason: "lost_win", missedAt: 3 });
});

test("win: ничья по правилам — провал, даже если таблиц нет (> 7 фигур)", () => {
  const status = evaluateGoal({
    goal: "win",
    human: "black",
    firstMover: "black",
    plies: 4,
    tbAfter: tb([[1, null], [3, null]]),
    end: { reason: "stalemate", winner: null },
  });
  assert.deepEqual(status, { state: "failure", reason: "draw_rules", missedAt: null });
});

test("ответа таблиц ещё нет — дальше не проверяем, партия идёт", () => {
  const status = evaluateGoal({
    goal: "win",
    human: "white",
    firstMover: "white",
    plies: 5,
    tbAfter: tb([[1, "win"], [5, "draw"]]),
    end: null,
  });
  assert.deepEqual(status, { state: "playing", held: 1 });
});

test("draw: удержание DRAW_HOLD_MOVES ходов при ничьей по таблицам — успех", () => {
  const plies = DRAW_HOLD_MOVES * 2;
  const entries = humanPlies("black", "black", plies).map((after) => [after, "draw"]);
  const status = evaluateGoal({ goal: "draw", human: "black", firstMover: "black", plies, tbAfter: tb(entries), end: null });
  assert.deepEqual(status, { state: "success", reason: "held", held: DRAW_HOLD_MOVES });

  const short = evaluateGoal({
    goal: "draw",
    human: "black",
    firstMover: "black",
    plies: plies - 2,
    tbAfter: tb(entries.slice(0, -1)),
    end: null,
  });
  assert.deepEqual(short, { state: "playing", held: DRAW_HOLD_MOVES - 1 });
});

test("draw: проигрыш по таблицам — провал с моментом; ничья по правилам — успех", () => {
  assert.deepEqual(
    evaluateGoal({ goal: "draw", human: "black", firstMover: "black", plies: 4, tbAfter: tb([[1, "draw"], [3, "loss"]]), end: null }),
    { state: "failure", reason: "lost_draw", missedAt: 3 },
  );
  assert.deepEqual(
    evaluateGoal({
      goal: "draw",
      human: "black",
      firstMover: "black",
      plies: 3,
      tbAfter: tb([[1, "draw"], [3, "draw"]]),
      end: { reason: "insufficient_material", winner: null },
    }),
    { state: "success", reason: "draw_rules", held: 2 },
  );
});

test("draw: мат сопернику — успех, свой мат и сдача — провал", () => {
  const base = { goal: "draw", human: "white", firstMover: "white", plies: 3, tbAfter: tb([[1, "win"], [3, "win"]]) };
  assert.equal(evaluateGoal({ ...base, end: { reason: "checkmate", winner: "white" } }).state, "success");
  assert.equal(evaluateGoal({ ...base, end: { reason: "checkmate", winner: "black" } }).reason, "mated");
  assert.equal(evaluateGoal({ ...base, end: { reason: "resign", winner: "black" } }).reason, "resigned");
});

test("провал по таблицам важнее позднего конца по правилам", () => {
  const status = evaluateGoal({
    goal: "win",
    human: "white",
    firstMover: "white",
    plies: 3,
    tbAfter: tb([[1, "draw"], [3, "draw"]]),
    end: { reason: "repetition", winner: null },
  });
  assert.equal(status.reason, "lost_win");
  assert.equal(status.missedAt, 1);
});

test("цель по таблицам начальной позиции", () => {
  assert.equal(effectiveGoal("win", null), "win");
  assert.equal(effectiveGoal("win", "draw"), "draw");
  assert.equal(effectiveGoal("draw", "win"), "win");
  assert.equal(effectiveGoal("draw", "loss"), null);
});

test("категории таблиц → плашка", () => {
  assert.equal(wdlOf("win"), "win");
  assert.equal(wdlOf("cursed-win"), "draw");
  assert.equal(wdlOf("blessed-loss"), "draw");
  assert.equal(wdlOf("loss"), "loss");
  assert.equal(wdlOf("unknown"), null);
  assert.equal(flipWdl("win"), "loss");
  assert.equal(flipWdl("draw"), "draw");
});

test("фигуры, книга и лучшие ходы", () => {
  assert.equal(pieceCount("1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"), 5);
  assert.equal(pieceCount("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"), 32);
  const moves = [
    { uci: "c1d1", san: "Rd1+", category: "win" },
    { uci: "c1c4", san: "Rc4", category: "win" },
    { uci: "a2a1", san: "Ra1", category: "draw" },
  ];
  assert.equal(bookMoveFrom(moves), "c1d1");
  assert.equal(bookMoveFrom([]), null);
  assert.deepEqual(
    bestMoves(moves).map((m) => m.san),
    ["Rd1+", "Rc4"],
  );
});
