// Тесты чистой логики экрана пазлов (сессия 16.2):
//   cd web && node --test src/components/puzzles/puzzle-view.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { afterAnswer, clock, filtersBody, parseView, runDuration, secondsLeft, viewHref } from "./puzzle-view.ts";

const none = { theme: null, phase: null, eco: null };

test("parseView: ссылка с экрана слабых мест", () => {
  assert.deepEqual(parseView({ mode: "practice", theme: "fork", phase: "endgame", eco: "b90" }), {
    mode: "practice",
    filters: { theme: "fork", phase: "endgame", eco: "B90" },
  });
  assert.deepEqual(parseView({ mode: "rush", theme: "pin" }), { mode: "rush", filters: { ...none, theme: "pin" } });
});

test("parseView: по умолчанию — повторение без фильтров", () => {
  assert.deepEqual(parseView({}), { mode: "srs", filters: none });
  assert.deepEqual(parseView({ mode: "srs" }), { mode: "srs", filters: none });
});

test("parseView: чужие значения отбрасываются, массив — первое значение", () => {
  assert.deepEqual(parseView({ mode: "blitz", theme: "Fork!", phase: "midgame", eco: "B 90" }), { mode: "srs", filters: none });
  assert.equal(parseView({ theme: ["fork", "pin"] }).filters.theme, "fork");
  assert.equal(parseView({ theme: "x".repeat(40) }).filters.theme, null);
});

test("viewHref: формат ссылки, round-trip", () => {
  assert.equal(viewHref({ mode: "srs", filters: none }), "/puzzles");
  assert.equal(viewHref({ mode: "practice", filters: { theme: "fork", phase: null, eco: null } }), "/puzzles?mode=practice&theme=fork");
  const view = { mode: "rush", filters: { theme: "fork", phase: "opening", eco: "C50" } };
  assert.equal(viewHref(view), "/puzzles?mode=rush&theme=fork&phase=opening&eco=C50");
  assert.deepEqual(parseView(Object.fromEntries(new URL(viewHref(view), "http://x").searchParams)), view);
  // Фильтры живут и в режиме повторения.
  assert.equal(viewHref({ mode: "srs", filters: { ...none, phase: "endgame" } }), "/puzzles?phase=endgame");
});

test("afterAnswer: счёт, ошибки и конец на третьей ошибке", () => {
  let step = afterAnswer({ score: 0, mistakes: 0 }, true);
  assert.deepEqual(step, { run: { score: 1, mistakes: 0 }, over: false });
  step = afterAnswer(step.run, false);
  step = afterAnswer(step.run, false);
  assert.deepEqual(step, { run: { score: 1, mistakes: 2 }, over: false });
  step = afterAnswer(step.run, false);
  assert.deepEqual(step, { run: { score: 1, mistakes: 3 }, over: true });
});

test("secondsLeft и runDuration", () => {
  assert.equal(secondsLeft("3min", 0), 180);
  assert.equal(secondsLeft("3min", 500), 180);
  assert.equal(secondsLeft("3min", 1500), 179);
  assert.equal(secondsLeft("5min", 400_000), 0);
  assert.equal(secondsLeft("survival", 99_000), null);
  // Таймер мог сработать с запозданием — серверу уходит не больше лимита.
  assert.equal(runDuration("3min", 181_400), 180);
  assert.equal(runDuration("3min", 95_600), 96);
  assert.equal(runDuration("survival", 400_000), 400);
});

test("clock и filtersBody", () => {
  assert.equal(clock(125), "2:05");
  assert.equal(clock(0), "0:00");
  assert.equal(clock(-3), "0:00");
  assert.deepEqual(filtersBody({ theme: "fork", phase: null, eco: null }), { theme: "fork" });
  assert.deepEqual(filtersBody(none), {});
});
